# Changelog — Radar B2B

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

---

## [2.1.0] — 2026-09-08

Correção de fonte de dados. Todos os endereços do projeto foram revisados
contra o que está efetivamente no ar.

### Corrigido — CRÍTICO

- **Host de download desativado.** O projeto apontava para
  `dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/AAAA-MM/` e variações em
  `arquivos.receitafederal.gov.br/.../dados_abertos_cnpj/`. **Ao final de
  janeiro/2026 a Receita Federal migrou a publicação** para um
  compartilhamento WebDAV (Nextcloud), e os caminhos antigos deixaram de
  existir. Isso explica por que nenhum espelho respondia e por que a
  ingestão de `Estabelecimentos` nunca concluiu.
  → Novo módulo `src/receita.py` conversa com o share atual:
  - listagem via `PROPFIND` em
    `arquivos.receitafederal.gov.br/public.php/webdav`;
  - download em
    `arquivos.receitafederal.gov.br/public.php/dav/files/<token>/<AAAA-MM>/<arquivo>`.

- **Adivinhação de competência substituída por descoberta.** A versão anterior
  varria até 12 meses testando URLs para achar qual existia — desperdício de
  requisições e fonte de falsos negativos.
  → O pipeline agora **lista** o que a Receita publicou. `--competencia`
  passou a ser opcional (default: a mais recente publicada), e
  `python -m src.ingestao --listar` mostra competências e arquivos
  disponíveis.

- **Mirror comunitário removido.** A versão anterior caía, como último
  recurso, num mirror do GitHub congelado em `2024.09`. Um pipeline de
  detecção de eventos que silenciosamente usa dados de dois anos atrás produz
  um digest inteiro de "empresas novas" falsas.
  → Removido. Falha explícita é melhor que dado velho disfarçado de atual.

### Alterado

- **Share token configurável.** `RADAR_RFB_SHARE_TOKEN` permite trocar o token
  sem editar código, caso a Receita publique um novo compartilhamento. A
  mensagem de erro ensina como obtê-lo.
- **Diagnóstico acionável.** Falhas de listagem distinguem "host fora do ar"
  de "token inválido/mudou", com instruções específicas em cada caso.
- **README** ganhou tabela de endereços oficiais, nota sobre a migração de
  janeiro/2026 e o procedimento de troca de token.
- `src/config.py` centraliza os endereços, incluindo o catálogo no
  [dados.gov.br](https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj)
  e o [dicionário de layout](https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf).

### Adicionado

- 5 testes de regressão: extração de competências e de arquivos do XML
  WebDAV, exclusão de não-ZIP na listagem, formato da URL de download e —
  via AST — a garantia de que nenhum módulo volte a **apontar** para os hosts
  desativados (comentários e docstrings podem citá-los para documentar a
  migração).

### Verificação

| Verificação | Resultado |
|---|---|
| Lint (ruff) | limpo |
| Testes pytest | 19 passando (antes: 14) |
| Testes dbt | 34 passando |
| Pipeline end-to-end | OK |
| Parser WebDAV | validado contra XML no formato Nextcloud |

> O download com dados reais ainda depende da disponibilidade da
> infraestrutura da RFB, historicamente instável. Os endereços agora estão
> corretos; a primeira carga real segue pendente.

---

## [2.0.0] — 2026-09-07

Refatoração estrutural após auditoria completa do código. O objetivo foi
fechar a distância entre o que o Plano Diretor V2 **declara** e o que o
repositório **implementava**: vários princípios inegociáveis (idempotência,
"a IA nunca inventa", ICP desacoplado, score explicável com fatores) estavam
escritos no documento mas ausentes do código.

Estado anterior: o pipeline nunca havia executado com dados reais. O banco
versionado continha 3 estabelecimentos fictícios (`11111111`, `22222222`,
`33333333`), e o digest gerado era integralmente sintético.

### Corrigido — CRÍTICO

- **Conteúdo fabricado apresentado como análise de IA.**
  `gerar_mock()` devolvia texto inventado ("Escritório focado em assessoria
  contábil e fiscal") com `confianca_ia: "Alta"` fixo, renderizado pelo digest
  sob o título "Inteligência Comercial (Contexto da IA)", indistinguível de
  saída real. Violava os princípios 6 e 7 do Plano Diretor e representava
  risco reputacional direto na validação com clientes.
  → Agora toda linha enriquecida carrega `origem` (`llm` | `heuristica`) e
  `modelo`. O digest estampa a procedência em cada oportunidade e exibe um
  aviso no topo quando há itens sem interpretação de IA. O fallback deixou de
  imitar análise: declara "não inferido" nos campos que dependem do modelo.

- **Falhas de IA mascaradas silenciosamente.**
  Um `except Exception` genérico capturava qualquer erro (chave inválida,
  rate limit, modelo aposentado, timeout) e o substituía por texto inventado,
  sem contagem nem alerta.
  → Falhas passam a ser contadas, registradas e reportadas. Acima de 30% de
  taxa de falha, a execução é interrompida com mensagem acionável, em vez de
  produzir um digest degradado.

- **Ausência de diff entre competências — o Event Store não existia de fato.**
  A ingestão usava `CREATE OR REPLACE TABLE`, sem coluna de competência nem
  particionamento: existia uma única foto, sobrescrita a cada execução.
  `evt_new_company` detectava empresas novas por
  `data_inicio_atividade >= current_date - 30`, o atalho que a cartilha havia
  descartado. Consequências: resultado variava conforme o dia da execução
  (não idempotente); empresas incluídas com data retroativa eram perdidas; e
  não havia fundação para nenhum outro evento do catálogo.
  → Competência passa a ser cidadã de primeira classe. Bronze grava
  `data/bronze/<tabela>/competencia=AAAA-MM/*.parquet`. `evt_new_company` usa
  **set difference** real entre a competência atual e a anterior — a mesma
  mecânica que sustentará `STATUS_CHANGED`, `PARTNER_*` e demais eventos.

- **Ingestão incompleta.** Baixava apenas `Estabelecimentos0.zip` (1 de 10
  fatias, ~10% do país) — insuficiente para um ICP municipal, podendo zerar
  o digest.
  → Baixa as 10 fatias de `Estabelecimentos` e `Empresas`, com filtro
  opcional por UF para desenvolvimento (`--uf MG`).

### Corrigido — ALTO

- **Filtro de ICP inócuo (`ilike '%ti%'`).** O padrão casava com
  "A-**TI**-vidades", presente em boa parte dos CNAEs brasileiros, além de
  "cosmé**ti**cos" e "Par**ti**cipação". Na prática, o filtro de segmento não
  filtrava: o ICP era "qualquer empresa em Varginha".
  → Casamento passa a ser por **código CNAE**, com listas de primários,
  secundários e **excluídos** (um escritório de contabilidade não deve
  prospectar outro escritório de contabilidade). Teste de regressão em
  `tests/test_pipeline.py` documenta o bug.

- **Tabela `empresas` ausente — digest sem nome de empresa.** O produto
  identificava a oportunidade apenas por `CNPJ 11111111000199`, inacionável
  para o usuário final. Também impedia os fatores de score `porte` e
  `capital`.
  → `slv_empresas` adicionado, trazendo razão social, capital social e porte.
  `nome_fantasia` (coluna 04), antes descartado, também passa a ser ingerido.

- **Score com apenas 3 valores possíveis.** A fórmula era base fixa 50 +
  recência (35/15/0), resultando em 50, 65 ou 85 — sem discriminar dentro da
  mesma faixa. A "base ICP +50" era constante para todos os aprovados, logo
  não pontuava nada. `where opportunity_score >= 50` era logicamente inerte.
  → Seis fatores ponderados (recência com decaimento linear, aderência de
  CNAE, porte, localização, capital social, completude de contato), com pesos
  vindos do ICP. Distribuição verificada: 16 valores distintos no conjunto de
  teste.

- **Score não auditável.** A explicação era uma string concatenada, sem os
  valores por trás.
  → `score_fatores` persistido como JSON estruturado; o texto exibido é
  derivado dele. Teste de dados garante que a soma dos fatores é exatamente
  igual ao score exibido.

- **ICP hardcoded em SQL.** `municipio_nome = 'VARGINHA'` cravado no model —
  cada cliente novo exigiria editar SQL.
  → ICP em `config/icp/*.yaml`, carregado para tabelas de configuração por
  `scripts/carregar_icp.py`. Novo cliente = novo arquivo YAML.

- **Projeto não reproduzível.** Não havia `requirements.txt`, `pyproject.toml`
  nem `environment.yml` — impossível clonar e executar.
  → `pyproject.toml` com dependências, extras (`ia`, `dev`) e configuração de
  `ruff`/`pytest`.

- **`.gitignore.txt`** — a extensão `.txt` fazia o Git ignorar o próprio
  arquivo de ignore. → Renomeado para `.gitignore`.

- **CI quebrado por construção.** O workflow era o template padrão do GitHub:
  usava conda, referenciava um `environment.yml` inexistente e rodava
  `pytest` sem testes — falhava em todo push.
  → Substituído por `ci.yml` (lint + testes + **pipeline end-to-end com
  fixtures sintéticas**) e `pipeline-mensal.yml` (execução agendada).

### Corrigido — MÉDIO

- **`verify=False` em todos os downloads**, desabilitando verificação TLS.
  → Verificação ativada por padrão; desligamento apenas explícito via
  `RADAR_TLS_INSECURE=1`.

- **SDK e modelo defasados.** `google.generativeai` (legado) com
  `gemini-1.5-flash` (aposentado) — a chamada real provavelmente já falhava,
  e falhava silenciosamente virando texto fabricado.
  → Migrado para `google-genai`, modelo configurável via `RADAR_LLM_MODEL`
  (default `gemini-2.0-flash`).

- **Enriquecimento sem cache.** Cada execução fazia `DROP TABLE` e
  reprocessava tudo, re-gastando tokens — contrariando "pré-computado, nunca
  re-pagar pela mesma empresa".
  → Tabela persistente com `event_id` como chave; apenas oportunidades
  inéditas são enviadas ao modelo.

- **Prompt sem grounding.** Não proibia invenção, não recebia o ICP nem o
  score/fatores, e pedia `dor_provavel` como se fosse fato apurado.
  → `system_instruction` com regras explícitas; ICP, score e fatores passam a
  compor o contexto; o campo foi renomeado para `hipotese_de_dor` e é
  apresentado como hipótese setorial, não como fato sobre a empresa.

- **Schemas inconsistentes.** O dbt gravava tudo em `main` (o `profiles.yml`
  não definia schema) enquanto o script Python gravava em `gold`; as pastas
  `silver/`/`gold/` eram puramente cosméticas.
  → Schemas configurados por camada em `dbt_project.yml`.

- **Zero testes de dados.** `tests/` vazio, nenhum `schema.yml`.
  → 24 testes dbt (`unique`, `not_null`, `accepted_values`) mais 5 testes
  singulares, incluindo o teste central do Event Store: nenhum evento
  `NEW_COMPANY` pode referenciar CNPJ já existente na competência anterior.

- **Ausência de observabilidade** (§16 do Plano Diretor).
  → `src/observabilidade.py` registra em `meta.run_log` etapa, competência,
  status, contagens, chamadas ao LLM, duração e falhas.

- **Ausência de ciclo de feedback** (§13).
  → Tabela `gold.opportunity_feedback` e campos de marcação em cada
  oportunidade do digest.

- **`extrair_csv` assumia um único arquivo por ZIP** (`namelist()[0]`).
  → Extrai todos os membros.

- **Download sem verificação de integridade.** Bastava o arquivo existir; um
  ZIP truncado passava como válido.
  → `_zip_integro()` valida via `testzip()`; arquivos corrompidos são
  rebaixados. Coberto por testes.

- **Orquestrador frágil.** Usava `python` literal e `shell=True`, quebrando
  fora do venv ativo; não recebia competência; não rodava testes.
  → `sys.executable` com lista de argumentos; competência parametrizada e
  propagada ao dbt via `--vars`; usa `dbt build` (models + testes), de modo
  que dado ruim interrompe o pipeline antes de virar digest.

- **README desatualizado**, descrevendo a V1 e um roadmap terminando em BI.
  → Reescrito para a V2.

### Adicionado

- `scripts/gerar_fixtures.py` — gera dados sintéticos no formato exato da
  Receita (30 colunas, `latin-1`, `;`), em duas competências, permitindo
  desenvolver e testar o pipeline sem depender do download de ~85 GB nem da
  instabilidade dos espelhos oficiais. Usado também pelo CI.
- `src/config.py` — layout oficial e caminhos centralizados. Uma mudança de
  layout da Receita passa a ser alteração de uma linha, não uma caçada por
  índices espalhados no SQL.
- `src/observabilidade.py` — run log estruturado.
- `dbt_radar/models/bronze/` — camada Bronze explícita lendo os Parquet
  particionados via `hive_partitioning`.
- `slv_dominios` — CNAEs e municípios deduplicados pela competência mais
  recente.
- Priorização por faixas (alta/média/baixa) no digest, conforme §12 do Plano
  Diretor.
- Campo `confidence` no Event Store: distingue abertura recente de inclusão
  retroativa/correção cadastral.

### Verificação

Pipeline executado de ponta a ponta com duas competências sintéticas
(400 e 460 estabelecimentos, 60 empresas exclusivas da competência mais
recente):

| Verificação | Resultado |
|---|---|
| Set difference | 58 eventos detectados (60 novas − 2 inativas, corretamente filtradas por `situacao_cadastral`) |
| Testes dbt | 34 passando, 0 erros |
| Testes pytest | 14 passando |
| Lint (ruff) | limpo |
| Idempotência | duas execuções completas → `event_id` idênticos |
| Cache de enriquecimento | segunda execução: 0 chamadas ao LLM |
| Distribuição de score | 16 valores distintos (antes: 3) |

### Pendências conhecidas

- O pipeline **ainda não foi executado com dados reais da Receita** — os
  espelhos oficiais não responderam durante a refatoração. A ingestão está
  pronta e parametrizada; falta a primeira carga real.
- Catálogo de eventos permanece com `NEW_COMPANY` apenas, por decisão de
  escopo. A fundação (competência + Parquet particionado) já suporta os
  demais.
- Snapshots SCD-2 não implementados: só serão necessários para eventos de
  mudança de atributo.
- Pesos do score são hipóteses iniciais, a calibrar com dados reais de
  conversão.
- Envio de e-mail permanece manual (concierge), conforme o MVP.

---

## [1.0.0] — 2026-08-25

- Versão inicial: ingestão de `Estabelecimentos0`, models dbt
  (`slv_estabelecimentos`, `evt_new_company`, `gld_icp_matches`,
  `gld_opportunities`), enriquecimento via Gemini e geração de digest em
  Markdown. Encadeamento ponta a ponta funcionando com dados de exemplo.
