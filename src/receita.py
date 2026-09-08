"""Cliente do compartilhamento WebDAV da Receita Federal.

Até janeiro/2026 a RFB publicava os dados em caminhos previsíveis
(`dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/AAAA-MM/`), e os scripts
adivinhavam a competência testando URL por URL. Esse host foi desativado.

Hoje a publicação é um compartilhamento WebDAV (Nextcloud). Isso é melhor
para nós: em vez de adivinhar, LISTAMOS o que existe de fato — o pipeline
descobre sozinho qual é a última competência publicada e quais arquivos ela
contém, e falha com mensagem clara se o share mudar.

Protocolo: método HTTP PROPFIND com header `Depth: 1`, autenticando com o
share token como usuário e senha vazia.
"""
from __future__ import annotations

import re
from xml.etree import ElementTree

import httpx

from .config import RFB_PAGINA_HUMANA, RFB_SHARE_TOKEN, RFB_WEBDAV

DAV_NS = {"d": "DAV:"}
TIMEOUT = httpx.Timeout(60.0, connect=15.0)
PADRAO_COMPETENCIA = re.compile(r"(\d{4}-\d{2})/?$")
PADRAO_ZIP = re.compile(r"/([^/]+\.zip)$", re.IGNORECASE)


class ReceitaIndisponivel(RuntimeError):
    """O share da RFB não respondeu ou mudou de endereço/token."""


def _propfind(caminho: str = "") -> ElementTree.Element:
    url = f"{RFB_WEBDAV}/{caminho}"
    try:
        resposta = httpx.request(
            "PROPFIND", url,
            auth=(RFB_SHARE_TOKEN, ""),      # share token como usuário
            headers={"Depth": "1"},
            timeout=TIMEOUT,
        )
        resposta.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise ReceitaIndisponivel(
            f"O share da Receita respondeu HTTP {e.response.status_code}.\n"
            f"O token pode ter mudado. Abra {RFB_PAGINA_HUMANA}, navegue até "
            f"Dados > Cadastros > CNPJ, copie o código que aparece na URL "
            f"depois de /index.php/s/ e exporte-o em RADAR_RFB_SHARE_TOKEN."
        ) from e
    except httpx.HTTPError as e:
        raise ReceitaIndisponivel(
            f"Não foi possível alcançar {url}: {type(e).__name__}. "
            f"Verifique a conexão ou tente mais tarde — a infraestrutura da "
            f"RFB é instável."
        ) from e
    return ElementTree.fromstring(resposta.content)


def listar_competencias() -> list[str]:
    """Competências publicadas, da mais antiga para a mais recente."""
    raiz = _propfind()
    competencias = []
    for item in raiz.findall("d:response", DAV_NS):
        href = item.find("d:href", DAV_NS)
        if href is None or not href.text:
            continue
        achado = PADRAO_COMPETENCIA.search(href.text)
        if achado:
            competencias.append(achado.group(1))
    if not competencias:
        raise ReceitaIndisponivel(
            "O share respondeu, mas nenhuma pasta AAAA-MM foi encontrada. "
            "A estrutura de publicação pode ter mudado."
        )
    return sorted(set(competencias))


def listar_arquivos(competencia: str) -> list[str]:
    """Nomes dos .zip publicados numa competência."""
    raiz = _propfind(f"{competencia}/")
    arquivos = []
    for item in raiz.findall("d:response", DAV_NS):
        href = item.find("d:href", DAV_NS)
        if href is None or not href.text:
            continue
        achado = PADRAO_ZIP.search(href.text)
        if achado:
            arquivos.append(achado.group(1))
    return sorted(set(arquivos))


def ultima_competencia() -> str:
    return listar_competencias()[-1]
