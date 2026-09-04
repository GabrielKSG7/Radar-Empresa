{{ config(materialized='table') }}

with eventos as (
    select * from {{ ref('evt_new_company') }}
)

select
    event_id,
    cnpj,
    event_type,
    event_date,
    municipio_nome,
    cnae_descricao,
    
    -- Princípio 8: Todo score/match deve ser explicável. 
    -- Já começamos a gerar contexto para o usuário final aqui.
    'Match: Localização (' || municipio_nome || ') + Setor B2B Alvo' as match_reason

from eventos
where 
    -- 1. Filtro Geográfico (Beachhead)
    municipio_nome = 'VARGINHA'
    
    -- 2. Filtro de Segmento (Contabilidades, Consultorias, TI)
    -- Usamos ILIKE no DuckDB para busca case-insensitive (ignora maiúsculas/minúsculas)
    and (
        cnae_descricao ilike '%contabilidade%'
        or cnae_descricao ilike '%consultoria%'
        or cnae_descricao ilike '%tecnologia%'
        or cnae_descricao ilike '%ti%'
    )