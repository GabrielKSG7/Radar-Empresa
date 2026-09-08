"""Observabilidade do pipeline (§16 do Plano Diretor V2).

Registra, em tabela DuckDB, cada etapa executada: competência, duração,
contagem de registros, chamadas ao LLM e falhas. Sem isso não há como saber
se uma execução foi saudável nem auditar um digest depois de enviado.
"""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager

import duckdb

from .config import DB_PATH

DDL = """
CREATE SCHEMA IF NOT EXISTS meta;
CREATE TABLE IF NOT EXISTS meta.run_log (
    run_id            VARCHAR,
    etapa             VARCHAR,
    competencia       VARCHAR,
    status            VARCHAR,      -- OK | FALHA
    registros         BIGINT,
    chamadas_llm      BIGINT,
    duracao_segundos  DOUBLE,
    detalhe           VARCHAR,
    executado_em      TIMESTAMP
);
"""

RUN_ID = uuid.uuid4().hex[:12]


def _con():
    con = duckdb.connect(str(DB_PATH))
    con.execute(DDL)
    return con


def registrar(etapa: str, status: str, competencia: str | None = None,
              registros: int = 0, chamadas_llm: int = 0,
              duracao: float = 0.0, detalhe: str = "") -> None:
    con = _con()
    con.execute(
        """INSERT INTO meta.run_log VALUES (?,?,?,?,?,?,?,?, current_timestamp)""",
        [RUN_ID, etapa, competencia, status, registros, chamadas_llm,
         duracao, detalhe[:500]],
    )
    con.close()


@contextmanager
def etapa(nome: str, competencia: str | None = None):
    """Cronometra uma etapa e registra o desfecho, inclusive em caso de erro.

    Uso:
        with etapa("ingestao", "2026-08") as ctx:
            ...
            ctx["registros"] = 1234
    """
    inicio = time.time()
    ctx: dict = {"registros": 0, "chamadas_llm": 0, "detalhe": ""}
    try:
        yield ctx
    except Exception as exc:
        registrar(nome, "FALHA", competencia, ctx["registros"],
                  ctx["chamadas_llm"], time.time() - inicio, str(exc))
        raise
    registrar(nome, "OK", competencia, ctx["registros"], ctx["chamadas_llm"],
              time.time() - inicio, ctx["detalhe"])


def resumo(limite: int = 20):
    con = _con()
    linhas = con.execute(
        """SELECT etapa, competencia, status, registros, chamadas_llm,
                  round(duracao_segundos, 2), detalhe
           FROM meta.run_log WHERE run_id = ? ORDER BY executado_em""",
        [RUN_ID],
    ).fetchall()
    con.close()
    return linhas[:limite]
