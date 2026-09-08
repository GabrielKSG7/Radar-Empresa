"""Orquestrador do pipeline Radar B2B.

Correções em relação à versão anterior:
  * usava `python` literal + shell=True — quebrava fora do venv ativo e
    dependia do shell. Agora usa sys.executable e lista de argumentos.
  * não recebia competência — a etapa dbt rodava sempre com os vars default.
    Agora a competência é parâmetro e é propagada para o dbt.
  * não rodava os testes de dados. Agora usa `dbt build` (models + tests),
    de modo que dado ruim interrompe o pipeline antes de virar digest.
  * não havia registro de execução. Agora imprime o resumo do run_log.

Uso:
    python run_pipeline.py --competencia 2026-08 --anterior 2026-07 --uf MG
    python run_pipeline.py --pular-ingestao --sem-ia
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from src import observabilidade as obs
from src.config import competencia_anterior, competencia_atual

ROOT = Path(__file__).resolve().parent


def passo(titulo: str, comando: list[str], cwd: Path | None = None) -> None:
    print(f"\n{'=' * 62}\n>> {titulo}\n{'=' * 62}")
    inicio = time.time()
    resultado = subprocess.run(comando, cwd=cwd or ROOT, text=True)
    if resultado.returncode != 0:
        print(f"\n[FALHA] {titulo} (código {resultado.returncode}). "
              f"Pipeline interrompido para não propagar dado ruim.")
        sys.exit(resultado.returncode)
    print(f"[OK] {titulo} — {time.time() - inicio:.1f}s")


def main() -> None:
    ap = argparse.ArgumentParser(description="Pipeline Radar B2B")
    ap.add_argument("--competencia", default=competencia_atual())
    ap.add_argument("--anterior", default=None,
                    help="competência de comparação (default: mês anterior)")
    ap.add_argument("--uf", default=None)
    ap.add_argument("--icp", default="contabilidade_sul_mg")
    ap.add_argument("--pular-ingestao", action="store_true")
    ap.add_argument("--somente-local", action="store_true",
                    help="ingestão sem download, usando data/raw")
    ap.add_argument("--sem-ia", action="store_true")
    ap.add_argument("--top", type=int, default=None)
    args = ap.parse_args()

    anterior = args.anterior or competencia_anterior(args.competencia)
    py = sys.executable

    print(f"\nRADAR B2B — competência {args.competencia} "
          f"(comparando com {anterior}) — ICP: {args.icp}")

    if not args.pular_ingestao:
        cmd = [py, "-m", "src.ingestao", "--competencia", anterior]
        if args.uf:
            cmd += ["--uf", args.uf]
        if args.somente_local:
            cmd += ["--somente-local"]
        passo(f"1a. INGESTÃO — competência anterior ({anterior})", cmd)

        cmd = [py, "-m", "src.ingestao", "--competencia", args.competencia]
        if args.uf:
            cmd += ["--uf", args.uf]
        if args.somente_local:
            cmd += ["--somente-local"]
        passo(f"1b. INGESTÃO — competência atual ({args.competencia})", cmd)

    passo("2. CARGA DO ICP", [py, "scripts/carregar_icp.py"])

    passo("3. TRANSFORMAÇÃO + TESTES (dbt build)",
          ["dbt", "build", "--profiles-dir", ".",
           "--vars", f"{{competencia_atual: '{args.competencia}', "
                     f"competencia_anterior: '{anterior}', "
                     f"icp_ativo: '{args.icp}'}}"],
          cwd=ROOT / "dbt_radar")

    cmd = [py, "-m", "src.enriquecimento"]
    if args.sem_ia:
        cmd.append("--sem-ia")
    passo("4. ENRIQUECIMENTO SEMÂNTICO", cmd)

    cmd = [py, "-m", "src.digest"]
    if args.top:
        cmd += ["--top", str(args.top)]
    passo("5. GERAÇÃO DO DIGEST", cmd)

    print(f"\n{'=' * 62}\nRESUMO DA EXECUÇÃO\n{'=' * 62}")
    for etapa, comp, status, regs, llm, dur, _det in obs.resumo():
        print(f"  {status:5s} {etapa:22s} comp={comp or '-':9s} "
              f"registros={regs:<8} llm={llm:<5} {dur}s")
    print("\nDigests em data/digests/")


if __name__ == "__main__":
    main()
