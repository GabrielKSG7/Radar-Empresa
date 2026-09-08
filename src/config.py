"""Configuração central do Radar B2B.

Concentra caminhos, layout oficial dos arquivos da Receita e utilitários de
competência. Nenhum outro módulo deve hardcodar caminho ou índice de coluna.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

# --------------------------------------------------------------------------
# Caminhos
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"          # ZIPs e CSVs crus, por competência
BRONZE_DIR = DATA_DIR / "bronze"    # Parquet particionado por competência
DIGEST_DIR = DATA_DIR / "digests"
DB_PATH = DATA_DIR / "radar.duckdb"
CONFIG_DIR = ROOT / "config"
ICP_DIR = CONFIG_DIR / "icp"

# --------------------------------------------------------------------------
# Fontes da Receita Federal
# --------------------------------------------------------------------------
# Estabelecimentos e Empresas são publicados em 10 fatias (0..9), particionadas
# por hash do CNPJ básico. Baixar apenas uma fatia significa ver ~10% do país —
# insuficiente para um ICP municipal.
FATIAS = range(10)

ARQUIVOS_DOMINIO = {
    "cnaes": "Cnaes.zip",
    "municipios": "Municipios.zip",
}

# --------------------------------------------------------------------------
# Endereços oficiais (verificados em setembro/2026)
#
# ATENÇÃO — HISTÓRICO: até janeiro/2026 os arquivos ficavam em
#   https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/AAAA-MM/
# Esse caminho foi DESATIVADO. Ao final de janeiro/2026 a RFB migrou a
# publicação para um compartilhamento WebDAV (Nextcloud) em
# arquivos.receitafederal.gov.br, acessado por um "share token".
#
# Vantagem da nova forma: em vez de adivinhar quais competências existem
# testando URLs mês a mês, agora nós LISTAMOS o que está publicado.
# --------------------------------------------------------------------------
RFB_HOST = "https://arquivos.receitafederal.gov.br"

# Token do compartilhamento público. É estável, mas se a RFB publicar um novo
# share, basta exportar RADAR_RFB_SHARE_TOKEN — sem alterar código.
# Para descobrir o token atual: acesse RFB_PAGINA_HUMANA abaixo, navegue até
# Dados > Cadastros > CNPJ e copie o código que aparece na URL depois de
# /index.php/s/.
RFB_SHARE_TOKEN = os.environ.get("RADAR_RFB_SHARE_TOKEN", "YggdBLfdninEJX9")

# Endpoint WebDAV usado para LISTAR competências e arquivos (método PROPFIND).
RFB_WEBDAV = f"{RFB_HOST}/public.php/webdav"

# Template de download direto (HTTP GET comum, sem WebDAV).
RFB_DOWNLOAD_TEMPLATE = (
    f"{RFB_HOST}/public.php/dav/files/{{token}}/{{competencia}}/{{arquivo}}"
)

# Páginas para consulta humana (não usadas pelo código, mas úteis no README
# e para diagnóstico quando o download falhar).
RFB_PAGINA_HUMANA = f"{RFB_HOST}/index.php/s/{RFB_SHARE_TOKEN}"
RFB_PORTAL_DADOS_GOV = (
    "https://dados.gov.br/dados/conjuntos-dados/"
    "cadastro-nacional-da-pessoa-juridica---cnpj"
)
RFB_DICIONARIO_LAYOUT = "https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf"


def url_download(arquivo: str, competencia: str) -> str:
    """Monta a URL de download de um arquivo de uma competência."""
    return RFB_DOWNLOAD_TEMPLATE.format(
        token=RFB_SHARE_TOKEN, competencia=competencia, arquivo=arquivo)


# --------------------------------------------------------------------------
# Layout oficial — ESTABELECIMENTOS (30 colunas, 0-indexed)
# Fonte: dicionário de dados dos Dados Abertos do CNPJ.
# Mantemos o mapa explícito para que uma mudança de layout seja uma alteração
# de UMA linha, e não uma caçada por índices espalhados no SQL.
# --------------------------------------------------------------------------
LAYOUT_ESTABELECIMENTOS = {
    "cnpj_basico": 0,
    "cnpj_ordem": 1,
    "cnpj_dv": 2,
    "identificador_matriz_filial": 3,
    "nome_fantasia": 4,
    "situacao_cadastral": 5,
    "data_situacao_cadastral": 6,
    "data_inicio_atividade": 10,
    "cnae_principal": 11,
    "cnae_secundaria": 12,
    "logradouro": 14,
    "numero": 15,
    "bairro": 17,
    "cep": 18,
    "uf": 19,
    "id_municipio": 20,
    "ddd_1": 21,
    "telefone_1": 22,
    "correio_eletronico": 27,
}
N_COLUNAS_ESTABELECIMENTOS = 30

# Layout oficial — EMPRESAS (7 colunas)
LAYOUT_EMPRESAS = {
    "cnpj_basico": 0,
    "razao_social": 1,
    "natureza_juridica": 2,
    "qualificacao_responsavel": 3,
    "capital_social": 4,
    "porte": 5,
    "ente_federativo": 6,
}
N_COLUNAS_EMPRESAS = 7

# Códigos de porte da Receita
PORTE_DESCRICAO = {
    "00": "Não informado",
    "01": "Micro Empresa",
    "03": "Empresa de Pequeno Porte",
    "05": "Demais",
}

SITUACAO_ATIVA = "02"


# --------------------------------------------------------------------------
# Competência
# --------------------------------------------------------------------------
def competencia_atual() -> str:
    """Competência corrente no formato AAAA-MM."""
    hoje = date.today()
    return f"{hoje.year:04d}-{hoje.month:02d}"


def competencia_anterior(competencia: str) -> str:
    """Dada 'AAAA-MM', devolve a competência do mês anterior."""
    ano, mes = (int(p) for p in competencia.split("-"))
    mes -= 1
    if mes == 0:
        mes, ano = 12, ano - 1
    return f"{ano:04d}-{mes:02d}"


def meses_candidatos(qtd: int = 12, a_partir_de: str | None = None) -> list[str]:
    """Lista de competências do mais recente ao mais antigo."""
    base = a_partir_de or competencia_atual()
    meses = [base]
    for _ in range(qtd - 1):
        meses.append(competencia_anterior(meses[-1]))
    return meses


def env(nome: str, default: str | None = None) -> str | None:
    return os.environ.get(nome, default)
