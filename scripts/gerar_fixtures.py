"""Gera dados SINTÉTICOS no formato exato da Receita Federal.

Objetivo: permitir desenvolver e testar o pipeline de ponta a ponta sem
depender do download de ~85 GB (e da instabilidade dos espelhos oficiais).

Produz DUAS competências para que o diff (set difference) tenha o que comparar:
a competência mais nova contém empresas que não existem na anterior — são
essas que devem virar eventos NEW_COMPANY.

IMPORTANTE: são dados fictícios, para desenvolvimento. Nunca use um digest
gerado a partir deles com um cliente real.

Uso:
    python scripts/gerar_fixtures.py --anterior 2026-07 --atual 2026-08
"""
from __future__ import annotations

import argparse
import random
import zipfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

random.seed(42)

MUNICIPIOS = [
    ("5403", "VARGINHA"), ("5401", "TRES CORACOES"), ("5445", "ELOI MENDES"),
    ("5297", "POCOS DE CALDAS"), ("4123", "BELO HORIZONTE"), ("7107", "SAO PAULO"),
]

CNAES = [
    ("6920601", "Atividades de contabilidade"),
    ("6920602", "Atividades de consultoria e auditoria contabil e tributaria"),
    ("7020400", "Atividades de consultoria em gestao empresarial"),
    ("6201501", "Desenvolvimento de programas de computador sob encomenda"),
    ("5611201", "Restaurantes e similares"),
    ("4781400", "Comercio varejista de artigos do vestuario"),
    ("9602501", "Cabeleireiros, manicure e pedicure"),
    ("4120400", "Construcao de edificios"),
    ("8630501", "Atividade medica ambulatorial"),
    ("4930202", "Transporte rodoviario de carga"),
]

RAZOES = [
    "ALPHA", "BETA", "GAMA", "DELTA", "OMEGA", "SIGMA", "AURORA", "HORIZONTE",
    "PRIMAVERA", "ATLANTICO", "PLANALTO", "VERTICE", "NOVA ERA", "PONTUAL",
]
SUFIXOS = ["LTDA", "ME", "EIRELI", "SOCIEDADE SIMPLES", "S/A"]
PORTES = ["01", "03", "05"]


def _linha_estabelecimento(cnpj_basico: str, cnae: str, municipio: str,
                           uf: str, dt_inicio: str, situacao: str,
                           fantasia: str) -> str:
    cols = [""] * 30
    cols[0] = cnpj_basico
    cols[1] = "0001"
    cols[2] = "99"
    cols[3] = "1"
    cols[4] = fantasia
    cols[5] = situacao
    cols[6] = dt_inicio
    cols[10] = dt_inicio
    cols[11] = cnae
    cols[12] = ""
    cols[13] = "RUA"
    cols[14] = "DAS FLORES"
    cols[15] = str(random.randint(10, 999))
    cols[17] = "CENTRO"
    cols[18] = "37000000"
    cols[19] = uf
    cols[20] = municipio
    cols[21] = "35"
    cols[22] = f"3{random.randint(1000000, 9999999)}"
    cols[27] = f"contato{cnpj_basico[:4]}@exemplo.com.br"
    return ";".join(f'"{c}"' for c in cols)


def _linha_empresa(cnpj_basico: str, razao: str, porte: str, capital: str) -> str:
    cols = [""] * 7
    cols[0] = cnpj_basico
    cols[1] = razao
    cols[2] = "2062"
    cols[3] = "49"
    cols[4] = capital
    cols[5] = porte
    return ";".join(f'"{c}"' for c in cols)


def _zipar(destino: Path, nome_interno: str, linhas: list[str]) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    conteudo = "\n".join(linhas).encode("latin-1", errors="replace")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(nome_interno, conteudo)


def gerar(competencia: str, cnpjs: list[dict], ref: date) -> None:
    destino = RAW / competencia
    est, emp = [], []
    for c in cnpjs:
        est.append(_linha_estabelecimento(
            c["cnpj_basico"], c["cnae"], c["municipio"], c["uf"],
            c["dt_inicio"], c["situacao"], c["fantasia"]))
        emp.append(_linha_empresa(
            c["cnpj_basico"], c["razao"], c["porte"], c["capital"]))

    _zipar(destino / "Estabelecimentos0.zip", "K3241.K03200Y0.D60808.ESTABELE", est)
    _zipar(destino / "Empresas0.zip", "K3241.K03200Y0.D60808.EMPRECSV", emp)
    _zipar(destino / "Cnaes.zip", "F.K03200$Z.D60808.CNAECSV",
           [f'"{c}";"{d}"' for c, d in CNAES])
    _zipar(destino / "Municipios.zip", "F.K03200$Z.D60808.MUNICCSV",
           [f'"{c}";"{d}"' for c, d in MUNICIPIOS])
    print(f"  {competencia}: {len(cnpjs)} estabelecimentos, {len(cnpjs)} empresas")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anterior", default="2026-07")
    ap.add_argument("--atual", default="2026-08")
    ap.add_argument("--base", type=int, default=400, help="empresas na competência anterior")
    ap.add_argument("--novas", type=int, default=60, help="empresas novas na atual")
    args = ap.parse_args()

    hoje = date.today()

    def _fabricar(idx: int, nova: bool) -> dict:
        cnae, _ = random.choice(CNAES)
        mun, _ = random.choice(MUNICIPIOS)
        uf = "SP" if mun == "7107" else "MG"
        if nova:
            dias = random.randint(0, 40)
            dt = (hoje - timedelta(days=dias)).strftime("%Y%m%d")
        else:
            dt = (hoje - timedelta(days=random.randint(400, 4000))).strftime("%Y%m%d")
        razao = f"{random.choice(RAZOES)} {random.choice(RAZOES)} {random.choice(SUFIXOS)}"
        return {
            "cnpj_basico": f"{idx:08d}",
            "cnae": cnae,
            "municipio": mun,
            "uf": uf,
            "dt_inicio": dt,
            # ~8% inativas, para exercitar o filtro de situação cadastral
            "situacao": "08" if random.random() < 0.08 else "02",
            "razao": razao,
            "fantasia": razao.split()[0],
            "porte": random.choice(PORTES),
            "capital": str(random.choice([0, 1000, 10000, 50000, 200000])) + ",00",
        }

    print("Gerando fixtures sintéticas (formato real da Receita)...")
    antigas = [_fabricar(i, nova=False) for i in range(1, args.base + 1)]
    gerar(args.anterior, antigas, hoje)

    # A competência atual = as antigas + um bloco de empresas realmente novas.
    novas = [_fabricar(args.base + i, nova=True) for i in range(1, args.novas + 1)]
    gerar(args.atual, antigas + novas, hoje)

    print(f"\nOK. {args.novas} empresas existem apenas em {args.atual} — "
          f"são elas que o diff deve detectar como NEW_COMPANY.")
    print(f"Arquivos em: {RAW}")


if __name__ == "__main__":
    main()
