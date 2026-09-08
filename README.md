# Radar B2B

> Detecte mudanças. Encontre oportunidades. Aja primeiro.

Motor de inteligência de eventos empresariais construído sobre os dados
públicos do CNPJ. Observa mudanças no universo de empresas, converte-as em
**eventos estruturados**, cruza com um **ICP** e gera **oportunidades
comerciais priorizadas e explicáveis**.

O produto não vende dados brutos, listas de leads nem busca de CNPJ. Vende
**contexto, prioridade, oportunidade e ação**.

```
DADO → EVENTO → CONTEXTO → ICP → SCORE → OPORTUNIDADE → AÇÃO → FEEDBACK
```

---

## Estado atual

MVP em desenvolvimento. Um único evento (`NEW_COMPANY`), um ICP
(contabilidade/BPO no Sul de Minas), entrega por digest em Markdown.

O pipeline roda de ponta a ponta e é validado no CI a cada push usando
**fixtures sintéticas** no formato exato da Receita. A primeira carga com
dados reais ainda está pendente (ver `CHANGELOG.md`).

---

## Arquitetura

| Camada | Responsabilidade | Tecnologia |
|---|---|---|
| Ingestão | Download, validação e preparo dos dumps | Python, httpx |
| Bronze | Dados brutos **versionados por competência** | Parquet particionado |
| Silver | Tipagem, limpeza, joins, qualidade | dbt + DuckDB |
| Event Store | Eventos detectados por *set difference* | dbt + DuckDB |
| Opportunity Layer | ICP matching e scoring explicável | dbt + config YAML |
| Enrichment | Interpretação semântica controlada | Pydantic + LLM |
| Digest | Entrega ao usuário | Markdown |
| Observabilidade | Run log de todas as etapas | DuckDB (`meta.run_log`) |

**Decisão central:** a competência (mês de publicação) é cidadã de primeira
classe. Empresas novas são detectadas comparando a competência atual com a
anterior — não filtrando por data de abertura. É essa mecânica que torna o
pipeline idempotente e que sustentará os demais eventos do catálogo.

---

## Instalação

```bash
git clone <repo> && cd radar-b2b
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # acrescente ",ia" para o enriquecimento por LLM
```

## Execução

### Com dados sintéticos (recomendado para começar)

Não depende do download de ~85 GB nem da estabilidade dos espelhos oficiais:

```bash
python scripts/gerar_fixtures.py --anterior 2026-07 --atual 2026-08
python run_pipeline.py --competencia 2026-08 --anterior 2026-07 \
                       --somente-local --sem-ia
```

O digest sai em `data/digests/`.

### Com dados reais da Receita

Primeiro, veja o que está publicado (o pipeline **descobre** as competências,
não as adivinha):

```bash
python -m src.ingestao --listar
```

Depois:

```bash
export GEMINI_API_KEY=...                    # opcional
python run_pipeline.py --competencia 2026-08 --uf MG
```

A primeira execução baixa duas competências (atual e anterior) — são muitos
gigabytes. O filtro `--uf` reduz drasticamente o volume processado.

#### Sobre a fonte dos dados

Até janeiro/2026 a Receita publicava em
`dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/AAAA-MM/`. **Esse host foi
desativado.** Desde então a publicação é um compartilhamento WebDAV
(Nextcloud) em `arquivos.receitafederal.gov.br`, acessado por um *share
token*.

| Recurso | Endereço |
|---|---|
| Página do compartilhamento (humano) | `arquivos.receitafederal.gov.br/index.php/s/<token>` |
| Listagem WebDAV (usada pelo código) | `arquivos.receitafederal.gov.br/public.php/webdav` |
| Download direto | `arquivos.receitafederal.gov.br/public.php/dav/files/<token>/<AAAA-MM>/<arquivo>` |
| Catálogo oficial | [dados.gov.br — CNPJ](https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj) |
| Dicionário de dados (layout) | [cnpj-metadados.pdf](https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf) |

**Se o download parar de funcionar**, o token provavelmente mudou. Abra a
página do compartilhamento, navegue até *Dados > Cadastros > CNPJ*, copie o
código que aparece na URL depois de `/index.php/s/` e exporte:

```bash
export RADAR_RFB_SHARE_TOKEN=<novo_token>
```

Nenhuma alteração de código é necessária.

### Etapas isoladas

```bash
python -m src.ingestao --competencia 2026-08 --uf MG
python scripts/carregar_icp.py
cd dbt_radar && dbt build --profiles-dir . \
  --vars "{competencia_atual: '2026-08', competencia_anterior: '2026-07'}"
python -m src.enriquecimento
python -m src.digest --top 20
```

---

## Configurando um ICP

O ICP é **configuração, não código**. Para atender um novo cliente, crie um
arquivo em `config/icp/` e rode `python scripts/carregar_icp.py`:

```yaml
nome: meu_cliente
oferta: "Descrição do serviço oferecido"
geografia:
  municipios: [VARGINHA, TRES CORACOES]
cnae:
  primarios: ['5611201', '4781400']    # sempre por CÓDIGO, nunca por texto
  secundarios: ['6201501']
  excluidos: ['6920601']
porte:
  alvo: ['01', '03']
recencia_dias: 45
pesos: {recencia: 30, cnae: 25, porte: 15, localizacao: 10, capital: 10, contexto: 10}
score_minimo: 40
```

Depois: `python run_pipeline.py --icp meu_cliente ...`

---

## O que a IA faz — e o que não faz

O LLM é **camada de interpretação**, nunca fonte da verdade.

| Responsabilidade | Determinístico | LLM |
|---|---|---|
| Fato do evento | sim | não |
| Score e fatores | sim | não |
| Aderência ao ICP | sim | não |
| Interpretação semântica | não | sim |
| Explicação e ação sugerida | não | sim |

A saída é validada com Pydantic e o prompt proíbe explicitamente inventar
faturamento, funcionários, contatos ou patrimônio. Toda oportunidade carrega
a **procedência** do enriquecimento (`llm` ou `heuristica`), e o digest a
exibe. Se a IA estiver indisponível, o digest sai marcado — nunca com texto
fabricado se passando por análise.

---

## Qualidade

```bash
ruff check src scripts tests run_pipeline.py
pytest -q
cd dbt_radar && dbt build --profiles-dir .    # inclui os testes de dados
```

Destaque: `assert_evento_nao_existe_na_competencia_anterior` — nenhum evento
`NEW_COMPANY` pode referenciar um CNPJ já presente na competência anterior.
Se esse teste falhar, o set difference está errado e o produto perde
credibilidade.

---

## Governança e LGPD

Dado público não elimina responsabilidade de tratamento. O projeto:

- utiliza exclusivamente dados empresariais dos Dados Abertos da Receita;
- **não** ingere a tabela de sócios (dados de pessoa física) no MVP;
- registra origem (competência) e finalidade de cada dado processado;
- mantém e-mail e telefone **do estabelecimento** apenas para viabilizar o
  contato comercial, sem cruzamento com outras bases;
- não faz enriquecimento indiscriminado.

---

## Roadmap

- [x] Bronze com competência e Parquet particionado
- [x] Silver com testes de qualidade
- [x] `NEW_COMPANY` por set difference
- [x] ICP configurável e Opportunity Score explicável
- [x] Enriquecimento com grounding e procedência
- [x] Digest priorizado + captura de feedback
- [x] Observabilidade e CI
- [ ] Primeira carga com dados reais
- [ ] Validação concierge com escritórios em Varginha
- [ ] Novos eventos (`STATUS_CHANGED`, `PARTNER_*`) — só após validação
- [ ] Dashboard / API — só após validação comercial

---

## Documentos

- `Plano_Diretor_Radar_B2B_V2.pdf` — estratégia (o porquê e o quê)
- `Cartilha_Radar_B2B_V2.pdf` — execução (o como)
- `CHANGELOG.md` — histórico de mudanças
