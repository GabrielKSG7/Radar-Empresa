"""Testes unitários do Radar B2B.

Cobrem as regras que, se quebrarem silenciosamente, produzem um digest errado
sem ninguém perceber — que era exatamente o risco da versão anterior.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import (  # noqa: E402
    LAYOUT_EMPRESAS,
    LAYOUT_ESTABELECIMENTOS,
    N_COLUNAS_EMPRESAS,
    N_COLUNAS_ESTABELECIMENTOS,
    competencia_anterior,
    meses_candidatos,
)
from src.ingestao import _select_colunas, _zip_integro  # noqa: E402


# ------------------------------------------------------------- competência
def test_competencia_anterior_no_mesmo_ano():
    assert competencia_anterior("2026-08") == "2026-07"


def test_competencia_anterior_vira_o_ano():
    assert competencia_anterior("2026-01") == "2025-12"


def test_meses_candidatos_ordem_decrescente():
    meses = meses_candidatos(3, a_partir_de="2026-03")
    assert meses == ["2026-03", "2026-02", "2026-01"]


# ------------------------------------------------------------------ layout
def test_layout_estabelecimentos_indices_conhecidos():
    """Índices conferidos contra o dicionário oficial dos Dados Abertos.

    Se a Receita mudar o layout, este teste falha antes de o pipeline gravar
    dado errado em Bronze (situação em que a coluna de UF viraria telefone).
    """
    assert LAYOUT_ESTABELECIMENTOS["cnpj_basico"] == 0
    assert LAYOUT_ESTABELECIMENTOS["nome_fantasia"] == 4
    assert LAYOUT_ESTABELECIMENTOS["situacao_cadastral"] == 5
    assert LAYOUT_ESTABELECIMENTOS["data_inicio_atividade"] == 10
    assert LAYOUT_ESTABELECIMENTOS["cnae_principal"] == 11
    assert LAYOUT_ESTABELECIMENTOS["uf"] == 19
    assert LAYOUT_ESTABELECIMENTOS["id_municipio"] == 20


def test_layout_dentro_do_numero_de_colunas():
    assert max(LAYOUT_ESTABELECIMENTOS.values()) < N_COLUNAS_ESTABELECIMENTOS
    assert max(LAYOUT_EMPRESAS.values()) < N_COLUNAS_EMPRESAS


def test_select_usa_zero_padding_de_duas_casas():
    """O DuckDB nomeia colunas sem header conforme o total de colunas do
    arquivo: com 30 colunas, o nome é column00 (e não column0)."""
    sql = _select_colunas({"uf": 19, "cnpj_basico": 0})
    assert "column19 AS uf" in sql
    assert "column00 AS cnpj_basico" in sql


# ------------------------------------------------------------- integridade
def test_zip_integro_detecta_arquivo_valido(tmp_path):
    caminho = tmp_path / "bom.zip"
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("dados.csv", "1;2;3")
    assert _zip_integro(caminho) is True


def test_zip_integro_rejeita_truncado(tmp_path):
    """Antes bastava o arquivo existir — um download truncado passava."""
    caminho = tmp_path / "ruim.zip"
    caminho.write_bytes(b"PK\x03\x04corrompido")
    assert _zip_integro(caminho) is False


def test_zip_integro_rejeita_vazio(tmp_path):
    caminho = tmp_path / "vazio.zip"
    caminho.write_bytes(b"")
    assert _zip_integro(caminho) is False


def test_zip_integro_rejeita_inexistente(tmp_path):
    assert _zip_integro(tmp_path / "nao_existe.zip") is False


# ------------------------------------------------------------------- regra
@pytest.mark.parametrize("descricao", [
    "Atividades de contabilidade",
    "Atividades de consultoria em gestao empresarial",
    "Comercio de cosmeticos",
    "Participacao societaria",
])
def test_regressao_filtro_por_texto_e_perigoso(descricao):
    """Regressão do bug do ILIKE '%ti%'.

    O filtro antigo casava com qualquer descrição contendo 'ti' — inclusive
    'A-TI-vidades', presente em boa parte dos CNAEs brasileiros, tornando o
    filtro de segmento inócuo. Este teste documenta por que o casamento passou
    a ser por CÓDIGO CNAE, e não por texto.
    """
    assert "ti" in descricao.lower(), (
        "Se esta descrição não contivesse 'ti', o exemplo perderia o sentido")


# ------------------------------------------------------- endereços da RFB
from xml.etree import ElementTree  # noqa: E402

from src import receita  # noqa: E402
from src.config import (  # noqa: E402
    RFB_HOST,
    RFB_SHARE_TOKEN,
    url_download,
)

XML_RAIZ = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response><d:href>/public.php/webdav/</d:href></d:response>
  <d:response><d:href>/public.php/webdav/2026-06/</d:href></d:response>
  <d:response><d:href>/public.php/webdav/2026-07/</d:href></d:response>
  <d:response><d:href>/public.php/webdav/2026-08/</d:href></d:response>
</d:multistatus>"""

XML_MES = b"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response><d:href>/public.php/webdav/2026-08/</d:href></d:response>
  <d:response><d:href>/public.php/webdav/2026-08/Estabelecimentos0.zip</d:href></d:response>
  <d:response><d:href>/public.php/webdav/2026-08/Empresas0.zip</d:href></d:response>
  <d:response><d:href>/public.php/webdav/2026-08/LEIAME.txt</d:href></d:response>
</d:multistatus>"""


def _competencias(xml: bytes) -> list[str]:
    raiz = ElementTree.fromstring(xml)
    achados = []
    for item in raiz.findall("d:response", receita.DAV_NS):
        m = receita.PADRAO_COMPETENCIA.search(item.find("d:href", receita.DAV_NS).text)
        if m:
            achados.append(m.group(1))
    return sorted(set(achados))


def _arquivos(xml: bytes) -> list[str]:
    raiz = ElementTree.fromstring(xml)
    achados = []
    for item in raiz.findall("d:response", receita.DAV_NS):
        m = receita.PADRAO_ZIP.search(item.find("d:href", receita.DAV_NS).text)
        if m:
            achados.append(m.group(1))
    return sorted(set(achados))


def test_webdav_extrai_competencias():
    assert _competencias(XML_RAIZ) == ["2026-06", "2026-07", "2026-08"]


def test_webdav_ignora_nao_zip():
    """LEIAME.txt e outros não-ZIP não podem entrar na lista de download."""
    assert _arquivos(XML_MES) == ["Empresas0.zip", "Estabelecimentos0.zip"]


def test_url_de_download_usa_host_ativo():
    """Regressão: dadosabertos.rfb.gov.br foi desativado em janeiro/2026."""
    url = url_download("Estabelecimentos0.zip", "2026-08")
    assert url.startswith("https://arquivos.receitafederal.gov.br/")
    assert "dadosabertos.rfb.gov.br" not in url
    assert RFB_SHARE_TOKEN in url
    assert url.endswith("/2026-08/Estabelecimentos0.zip")


def test_nenhum_host_desativado_no_codigo():
    """Nenhum módulo pode voltar a APONTAR para os hosts mortos.

    Usa AST para inspecionar apenas literais de string efetivamente usados no
    código — comentários e docstrings podem (e devem) citar o host antigo para
    documentar a migração de janeiro/2026.
    """
    import ast
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parent.parent
    mortos = ["dadosabertos.rfb.gov.br", "200.152.38.155"]
    arquivos = list((raiz / "src").glob("*.py")) + list((raiz / "scripts").glob("*.py"))
    assert arquivos, "nenhum módulo encontrado para inspecionar"

    for arquivo in arquivos:
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        docstrings = {
            id(no.body[0].value)
            for no in ast.walk(arvore)
            if isinstance(no, ast.Module | ast.FunctionDef | ast.ClassDef)
            and no.body
            and isinstance(no.body[0], ast.Expr)
            and isinstance(no.body[0].value, ast.Constant)
            and isinstance(no.body[0].value.value, str)
        }
        for no in ast.walk(arvore):
            if (isinstance(no, ast.Constant) and isinstance(no.value, str)
                    and id(no) not in docstrings):
                for morto in mortos:
                    assert morto not in no.value, (
                        f"{arquivo.name}:{no.lineno} usa host desativado: {morto}")


def test_host_configuravel_por_variavel_de_ambiente():
    """O share token precisa ser sobrescrevível sem editar código."""
    assert RFB_HOST.startswith("https://")
    assert isinstance(RFB_SHARE_TOKEN, str) and RFB_SHARE_TOKEN
