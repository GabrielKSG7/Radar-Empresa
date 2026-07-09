# Radar Empresas: Pipeline de Dados da Receita Federal 🏢📊

Este projeto consiste no desenvolvimento de um pipeline de dados ponta a ponta (End-to-End) focado no processamento, transformação e análise dos dados públicos de CNPJ da Receita Federal do Brasil. 

O objetivo principal é construir um ambiente analítico local robusto, eficiente e de custo zero, simulando práticas reais de engenharia de dados em cenários de grande volume de informações.

---

## 🛠️ Stack Tecnológica & Decisões de Arquitetura

Para este projeto, optei por utilizar a **Modern Data Stack (MDS)** adaptada para um ambiente standalone/local, priorizando performance e eficiência de recursos:

- **Python (com `uv`)**: Utilizado para a fase de ingestão. A escolha do gerenciador de pacotes `uv` (escrito em Rust) visa a substituição do `pip/venv` tradicional devido à sua velocidade extrema na resolução de dependências.
- **HTTPX**: Biblioteca escolhida para realizar o download dos arquivos brutos via streaming, garantindo baixo consumo de memória RAM ao manipular arquivos de múltiplos gigabytes.
- **DuckDB**: Nosso motor analítico (OLAP) embutido. Ele foi escolhido por sua capacidade de processar consultas colunares pesadas diretamente do disco local (arquivos CSV e Parquet de dentro de arquivos `.zip`), dispensando o custo e a complexidade de provisionar um banco de dados em nuvem nesta etapa.
- **dbt (Data Build Tool)**: Responsável por toda a orquestração da camada de transformação de dados utilizando SQL, aplicando boas práticas como controle de versão, testes e documentação de linhagem de dados.

---

## 📐 Arquitetura de Dados (Padrão Medalhão)

O pipeline segue a divisão lógica da arquitetura medalhão:

1. **Camada Bronze (Raw):** Dados extraídos do portal da Receita Federal em formato `.zip` e espelhados de forma bruta no DuckDB.
2. **Camada Prata (Silver):** Limpeza, tipagem de dados, tratamento de nulos e codificações de caracteres (ex: acentuações).
3. **Camada Ouro (Gold):** Modelagem dimensional (Star Schema) focada em responder dores de negócio e otimizada para ferramentas de BI.

---

## 🗺️ Roadmap do Projeto

- [x] **Fase 0: Setup do Ambiente** - Configuração do ambiente virtual (`uv`), inicialização do projeto `dbt` e integração com o `DuckDB`.
- [/] **Fase 1: Ingestão (Bronze)** - Desenvolvimento dos scripts em Python para streaming dos dados de CNAEs, Empresas, Sócios, Estabelecimentos, etc. *(Em andamento)*
- [ ] **Fase 2: Transformação (Prata)** - Padronização e higienização dos dados analíticos via dbt.
- [ ] **Fase 3: Modelagem (Ouro)** - Criação de tabelas Fato e Dimensão prontas para análise.
- [ ] **Fase 4: Visualização** - Conexão dos dados modelados a uma ferramenta de BI.

---

## 🚀 Como Executar o Projeto (Estado Atual)

### Pré-requisitos
- Python 3.10+
- Gerenciador de pacotes `uv` instalado globalmente (`pip install uv`)

### Passo a Passo

1. Clone o repositório:
```bash
git clone [https://github.com/SEU_USUARIO/radar-empresas.git](https://github.com/SEU_USUARIO/radar-empresas.git)
cd radar-empresas
