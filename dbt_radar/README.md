# Radar B2B 🎯

**DADO -> EVENTO -> CONTEXTO -> ICP -> SCORE -> OPORTUNIDADE -> AÇÃO**

O Radar B2B é um motor de inteligência comercial. Ele não é um buscador de CNPJs. Ele monitora a base pública da Receita Federal para detectar **mudanças no universo empresarial** (ex: empresas abertas, alteração de quadro societário), cruza esses eventos com um Perfil de Cliente Ideal (ICP) e entrega Oportunidades pontuadas e enriquecidas por IA para times de vendas (BPO, Contabilidades, Consultorias).

## Arquitetura (MVP Local / R$ 0)
- **Ingestão:** Python (`httpx`, `polars`)
- **Storage/DW:** DuckDB (Out-of-core process, `.parquet`)
- **Transformação (Medallion):** dbt-core
- **Enriquecimento:** LLM local (Ollama) / Free Tier estruturado com `Pydantic`