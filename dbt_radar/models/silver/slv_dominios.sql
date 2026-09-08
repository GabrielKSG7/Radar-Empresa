{{ config(materialized='table') }}

-- Domínios (CNAE e município) da competência mais recente disponível.
-- Deduplicado: o mesmo código se repete a cada competência carregada.

with cnaes as (
    select 'CNAE' as dominio, lpad(codigo, 7, '0') as codigo, descricao, competencia
    from {{ ref('brz_cnaes') }}
),
municipios as (
    select 'MUNICIPIO' as dominio, codigo, descricao, competencia
    from {{ ref('brz_municipios') }}
),
unificado as (
    select * from cnaes
    union all
    select * from municipios
),
ranqueado as (
    select *,
           row_number() over (partition by dominio, codigo
                              order by competencia desc) as rn
    from unificado
)
select dominio, codigo, descricao
from ranqueado
where rn = 1
