"""Carrega os ICPs de config/icp/*.yaml para o DuckDB.

Assim o SQL do dbt consulta tabelas de configuração em vez de ter regras de
negócio hardcoded (antes: `where municipio_nome = 'VARGINHA'` dentro do model).
Adicionar um cliente passa a ser criar um YAML e rodar este script.

Uso:
    python scripts/carregar_icp.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import DB_PATH, ICP_DIR  # noqa: E402

DDL = """
CREATE SCHEMA IF NOT EXISTS config;

CREATE OR REPLACE TABLE config.icp (
    icp_nome        VARCHAR,
    descricao       VARCHAR,
    oferta          VARCHAR,
    recencia_dias   INTEGER,
    score_minimo    INTEGER,
    peso_recencia   INTEGER,
    peso_cnae       INTEGER,
    peso_porte      INTEGER,
    peso_localizacao INTEGER,
    peso_capital    INTEGER,
    peso_contexto   INTEGER
);

CREATE OR REPLACE TABLE config.icp_cnae (
    icp_nome    VARCHAR,
    cnae        VARCHAR,
    prioridade  VARCHAR      -- primario | secundario | excluido
);

CREATE OR REPLACE TABLE config.icp_municipio (
    icp_nome    VARCHAR,
    municipio   VARCHAR
);

CREATE OR REPLACE TABLE config.icp_porte (
    icp_nome    VARCHAR,
    porte       VARCHAR
);
"""


def carregar() -> None:
    arquivos = sorted(ICP_DIR.glob("*.yaml")) + sorted(ICP_DIR.glob("*.yml"))
    if not arquivos:
        raise SystemExit(f"Nenhum ICP encontrado em {ICP_DIR}")

    con = duckdb.connect(str(DB_PATH))
    con.execute(DDL)

    for caminho in arquivos:
        icp = yaml.safe_load(caminho.read_text(encoding="utf-8"))
        nome = icp["nome"]
        pesos = icp.get("pesos", {})

        con.execute(
            "INSERT INTO config.icp VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [nome, icp.get("descricao", "").strip(), icp.get("oferta", ""),
             icp.get("recencia_dias", 45), icp.get("score_minimo", 0),
             pesos.get("recencia", 30), pesos.get("cnae", 25),
             pesos.get("porte", 15), pesos.get("localizacao", 10),
             pesos.get("capital", 10), pesos.get("contexto", 10)],
        )

        cnae = icp.get("cnae", {})
        for prioridade in ("primarios", "secundarios", "excluidos"):
            for codigo in cnae.get(prioridade, []) or []:
                con.execute("INSERT INTO config.icp_cnae VALUES (?,?,?)",
                            [nome, str(codigo).zfill(7), prioridade[:-1]])

        for municipio in icp.get("geografia", {}).get("municipios", []) or []:
            con.execute("INSERT INTO config.icp_municipio VALUES (?,?)",
                        [nome, municipio.upper()])

        for porte in icp.get("porte", {}).get("alvo", []) or []:
            con.execute("INSERT INTO config.icp_porte VALUES (?,?)",
                        [nome, str(porte).zfill(2)])

        print(f"  [OK] ICP '{nome}' carregado de {caminho.name}")

    total = con.execute("SELECT count(*) FROM config.icp").fetchone()[0]
    con.close()
    print(f"--- {total} ICP(s) disponíveis no banco ---")


if __name__ == "__main__":
    carregar()
