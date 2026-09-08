"""Ingestão Bronze — Dados Abertos do CNPJ.

Mudanças estruturais em relação à versão anterior:
  * COMPETÊNCIA é cidadã de primeira classe. Cada carga grava
    data/bronze/<tabela>/competencia=AAAA-MM/*.parquet. Sem isso não existe
    diff entre meses e o Event Store é impossível.
  * Baixa as 10 fatias de Estabelecimentos e Empresas (antes: 1 de 10 = ~10%
    do país, insuficiente para um ICP municipal).
  * Ingere EMPRESAS (razão social, capital, porte) — antes ausente, o que
    deixava o digest sem o nome da empresa.
  * Filtro de UF opcional na carga, para desenvolvimento rápido.
  * Verificação de integridade do ZIP (antes: bastava o arquivo existir).
  * TLS verificado por padrão (antes: verify=False em tudo).
  * Idempotente: recarregar a mesma competência substitui a partição.

Uso:
    python -m src.ingestao --competencia 2026-08 --uf MG
    python -m src.ingestao --competencia 2026-08 --fatias 0,1  # amostra
"""
from __future__ import annotations

import argparse
import os
import shutil
import time
import zipfile
from pathlib import Path

import duckdb
import httpx

from . import observabilidade as obs
from . import receita
from .config import (
    ARQUIVOS_DOMINIO,
    BRONZE_DIR,
    DB_PATH,
    FATIAS,
    LAYOUT_EMPRESAS,
    LAYOUT_ESTABELECIMENTOS,
    N_COLUNAS_EMPRESAS,
    N_COLUNAS_ESTABELECIMENTOS,
    RAW_DIR,
    url_download,
)

TIMEOUT = httpx.Timeout(600.0, connect=15.0)
# A cadeia TLS da Receita já causou problemas; permitimos desligar a
# verificação por variável de ambiente, mas NUNCA por padrão.
VERIFICAR_TLS = os.environ.get("RADAR_TLS_INSECURE", "0") != "1"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


# ---------------------------------------------------------------- download
def _baixar(url: str, destino: Path, tentativas: int = 3) -> str:
    """Baixa uma URL. Retorna OK | NOT_FOUND | FALHOU."""
    tmp = destino.with_suffix(destino.suffix + ".part")
    for n in range(1, tentativas + 1):
        try:
            with httpx.stream("GET", url, headers=HEADERS, timeout=TIMEOUT,
                              verify=VERIFICAR_TLS, follow_redirects=True) as r:
                if r.status_code == 404:
                    return "NOT_FOUND"
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=1 << 16):
                        f.write(chunk)
            tmp.replace(destino)
            return "OK"
        except (httpx.ConnectTimeout, httpx.ConnectError) as e:
            print(f"    tentativa {n}: sem conexão ({type(e).__name__})")
        except Exception as e:  # noqa: BLE001 - queremos continuar tentando
            print(f"    tentativa {n}: {type(e).__name__}: {e}")
        if n < tentativas:
            time.sleep(min(10 * 2 ** (n - 1), 60))
    if tmp.exists():
        tmp.unlink()
    return "FALHOU"


def _zip_integro(caminho: Path) -> bool:
    """Um ZIP truncado passava como válido só por existir. Agora validamos."""
    if not caminho.exists() or caminho.stat().st_size == 0:
        return False
    try:
        with zipfile.ZipFile(caminho) as z:
            return z.testzip() is None and len(z.namelist()) > 0
    except zipfile.BadZipFile:
        return False


def baixar_arquivo(nome_arquivo: str, competencia: str, destino_dir: Path) -> Path:
    """Baixa um arquivo da competência informada do share WebDAV da RFB.

    A cascata de espelhos da versão anterior (dadosabertos.rfb.gov.br e
    variações de caminho) apontava para hosts hoje DESATIVADOS. Agora há um
    endereço único e correto, montado a partir do share token.
    """
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / nome_arquivo

    if _zip_integro(destino):
        print(f"  [SKIP] {nome_arquivo} já presente e íntegro.")
        return destino
    if destino.exists():
        print(f"  [REBAIXAR] {nome_arquivo} existe mas está corrompido/truncado.")
        destino.unlink()

    url = url_download(nome_arquivo, competencia)
    print(f"  [GET] {nome_arquivo} ({competencia})")
    status = _baixar(url, destino, tentativas=4)

    if status == "OK" and _zip_integro(destino):
        print(f"  [OK] {nome_arquivo}")
        return destino
    destino.unlink(missing_ok=True)

    if status == "NOT_FOUND":
        raise RuntimeError(
            f"{nome_arquivo} não existe na competência {competencia}.\n"
            f"Use --listar para ver o que está publicado."
        )
    raise RuntimeError(
        f"Falha ao baixar {nome_arquivo} da competência {competencia}. "
        f"A infraestrutura da RFB é instável; tente novamente mais tarde."
    )


def extrair(zip_path: Path, destino_dir: Path) -> list[Path]:
    """Extrai TODOS os membros do ZIP (antes assumia-se um único arquivo)."""
    destino_dir.mkdir(parents=True, exist_ok=True)
    saidas = []
    with zipfile.ZipFile(zip_path) as z:
        for membro in z.namelist():
            if membro.endswith("/"):
                continue
            z.extract(membro, destino_dir)
            saidas.append(destino_dir / membro)
    return saidas


# ------------------------------------------------------------------- carga
def _select_colunas(layout: dict[str, int]) -> str:
    """Monta o SELECT posicional a partir do layout oficial.

    O DuckDB nomeia colunas sem header como column00, column01... com
    zero-padding conforme o total de colunas do arquivo.
    """
    return ",\n        ".join(
        f"column{idx:02d} AS {nome}" for nome, idx in layout.items()
    )


def _carregar_parquet(con, tabela: str, csvs: list[Path], layout: dict[str, int],
                      n_colunas: int, competencia: str, uf: str | None) -> int:
    """Lê os CSVs crus e grava a partição Parquet da competência."""
    if not csvs:
        raise RuntimeError(f"Nenhum CSV encontrado para {tabela}")

    saida = BRONZE_DIR / tabela / f"competencia={competencia}"
    if saida.exists():
        shutil.rmtree(saida)  # idempotência: recarregar substitui a partição
    saida.mkdir(parents=True, exist_ok=True)

    lista = ", ".join(f"'{p.as_posix()}'" for p in csvs)
    filtro_uf = ""
    if uf and "uf" in layout:
        filtro_uf = f"WHERE column{layout['uf']:02d} = '{uf}'"

    # Truque Sênior: quote='' desliga o parser de aspas e evita quebra em dados sujos
    con.execute(f"""
        COPY (
            SELECT {_select_colunas(layout)},
                   '{competencia}' AS competencia
            FROM read_csv([{lista}],
                          delim=';', header=false, quote='',
                          encoding='latin-1', all_varchar=true,
                          columns={{{', '.join(f"'column{i:02d}': 'VARCHAR'" for i in range(n_colunas))}}})
            {filtro_uf}
        ) TO '{(saida / "dados.parquet").as_posix()}' (FORMAT PARQUET)
    """)
    return con.execute(
        f"SELECT count(*) FROM read_parquet('{(saida / 'dados.parquet').as_posix()}')"
    ).fetchone()[0]


def _carregar_dominio(con, tabela: str, csvs: list[Path], competencia: str) -> int:
    """Tabelas de domínio (CNAE, Município): sempre 2 colunas id;descrição."""
    saida = BRONZE_DIR / tabela / f"competencia={competencia}"
    if saida.exists():
        shutil.rmtree(saida)
    saida.mkdir(parents=True, exist_ok=True)
    lista = ", ".join(f"'{p.as_posix()}'" for p in csvs)
    
    # Truque Sênior: quote='' aplicado aqui também por segurança
    con.execute(f"""
        COPY (
            SELECT column00 AS codigo, column01 AS descricao,
                   '{competencia}' AS competencia
            FROM read_csv([{lista}], delim=';', header=false, quote='',
                          encoding='latin-1', all_varchar=true,
                          columns={{'column00':'VARCHAR','column01':'VARCHAR'}})
        ) TO '{(saida / "dados.parquet").as_posix()}' (FORMAT PARQUET)
    """)
    return con.execute(
        f"SELECT count(*) FROM read_parquet('{(saida / 'dados.parquet').as_posix()}')"
    ).fetchone()[0]


def ingerir(competencia: str, uf: str | None = None,
            fatias: list[int] | None = None, somente_local: bool = False) -> dict:
    """Executa a ingestão completa de uma competência."""
    fatias = list(FATIAS) if fatias is None else fatias
    raw = RAW_DIR / competencia
    print(f"\n=== INGESTÃO BRONZE — competência {competencia} ===")
    if uf:
        print(f"    filtro de UF: {uf}")

    zips: dict[str, list[Path]] = {"estabelecimentos": [], "empresas": []}
    dominio: dict[str, Path] = {}

    if not somente_local:
        for nome, arq in ARQUIVOS_DOMINIO.items():
            dominio[nome] = baixar_arquivo(arq, competencia, raw)
        for i in fatias:
            zips["estabelecimentos"].append(
                baixar_arquivo(f"Estabelecimentos{i}.zip", competencia, raw))
            zips["empresas"].append(
                baixar_arquivo(f"Empresas{i}.zip", competencia, raw))
    else:
        # Modo offline: usa o que já estiver em data/raw/<competencia>/
        for nome, arq in ARQUIVOS_DOMINIO.items():
            p = raw / arq
            if p.exists():
                dominio[nome] = p
        zips["estabelecimentos"] = sorted(raw.glob("Estabelecimentos*.zip"))
        zips["empresas"] = sorted(raw.glob("Empresas*.zip"))

    print("\n[EXTRAÇÃO]")
    csvs: dict[str, list[Path]] = {}
    for tabela, lista in zips.items():
        csvs[tabela] = []
        for z in lista:
            csvs[tabela].extend(extrair(z, raw / "csv"))
    for nome, z in dominio.items():
        csvs[nome] = extrair(z, raw / "csv")

    print("\n[CARGA -> Parquet particionado]")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    contagens = {}
    contagens["cnaes"] = _carregar_dominio(con, "cnaes", csvs.get("cnaes", []), competencia)
    contagens["municipios"] = _carregar_dominio(con, "municipios", csvs.get("municipios", []), competencia)
    contagens["estabelecimentos"] = _carregar_parquet(
        con, "estabelecimentos", csvs["estabelecimentos"],
        LAYOUT_ESTABELECIMENTOS, N_COLUNAS_ESTABELECIMENTOS, competencia, uf)
    contagens["empresas"] = _carregar_parquet(
        con, "empresas", csvs["empresas"],
        LAYOUT_EMPRESAS, N_COLUNAS_EMPRESAS, competencia, None)
    con.close()

    for t, n in contagens.items():
        print(f"    {t:20s} {n:>12,} linhas")
    return contagens


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingestão Bronze do Radar B2B")
    ap.add_argument("--competencia", default=None,
                    help="AAAA-MM (default: última publicada pela Receita)")
    ap.add_argument("--uf", default=None, help="filtra estabelecimentos por UF")
    ap.add_argument("--fatias", default=None,
                    help="fatias a baixar, ex: 0,1 (default: todas)")
    ap.add_argument("--somente-local", action="store_true",
                    help="não baixa; usa os ZIPs já presentes em data/raw")
    ap.add_argument("--listar", action="store_true",
                    help="lista as competências publicadas e sai")
    args = ap.parse_args()

    # Descoberta: em vez de adivinhar meses testando URLs (como fazia a versão
    # anterior), consultamos o que a Receita realmente publicou.
    if args.listar:
        comps = receita.listar_competencias()
        print("Competências publicadas pela Receita Federal:")
        for c in comps:
            print(f"  {c}" + ("   <- mais recente" if c == comps[-1] else ""))
        print(f"\nArquivos em {comps[-1]}:")
        for a in receita.listar_arquivos(comps[-1]):
            print(f"  {a}")
        return

    competencia = args.competencia
    if competencia is None:
        if args.somente_local:
            raise SystemExit("--somente-local exige --competencia explícita.")
        competencia = receita.ultima_competencia()
        print(f"[INFO] Competência não informada; usando a mais recente "
              f"publicada: {competencia}")

    fatias = ([int(x) for x in args.fatias.split(",")] if args.fatias else None)

    with obs.etapa("ingestao_bronze", competencia) as ctx:
        contagens = ingerir(competencia, args.uf, fatias, args.somente_local)
        ctx["registros"] = contagens.get("estabelecimentos", 0)
        ctx["detalhe"] = str(contagens)
    print("\n--- INGESTÃO CONCLUÍDA ---")


if __name__ == "__main__":
    main()
