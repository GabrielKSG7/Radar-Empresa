{{ config(materialized='table') }}

with estabelecimentos as (
    select * from {{ ref('slv_estabelecimentos') }}
),

municipios as (
    select * from {{ source('rfb_bronze', 'municipios') }}
),

cnaes as (
    select * from {{ source('rfb_bronze', 'cnaes') }}
)

select
    -- 1. Identificação do Evento (Padrão Event Store)
    md5(e.cnpj || 'NEW_COMPANY' || e.data_inicio_atividade::varchar) as event_id,
    e.cnpj,
    'NEW_COMPANY' as event_type,
    e.data_inicio_atividade as event_date,
    current_date as detected_at,
    
    -- 2. Contexto Básico (Necessário para a próxima fase: ICP Matching)
    m.descricao as municipio_nome,
    e.uf,
    c.descricao as cnae_descricao
    
from estabelecimentos e
left join municipios m on e.id_municipio = m.id_municipio
left join cnaes c on e.cnae_principal = c.id_cnae

where 
    -- Regra de negócio: Apenas filiais/matrizes ativas
    e.situacao_cadastral = '02' 
    
    -- Simulando um filtro de evento recente (empresas abertas nos últimos 30 dias)
    -- Como nossos mocks usaram a data de "hoje" e "2020", isso vai filtrar exatamente o que queremos
    and e.data_inicio_atividade >= current_date - interval 30 day