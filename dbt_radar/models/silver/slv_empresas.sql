{{ config(materialized='table') }}

-- Traz razão social, capital e porte — sem isso o digest não consegue
-- sequer nomear a empresa, e o score não pode ponderar porte/capital.

with fonte as (
    select * from {{ ref('brz_empresas') }}
)

select
    lpad(cnpj_basico, 8, '0')                        as cnpj_basico,
    competencia,
    nullif(trim(razao_social), '')                   as razao_social,
    natureza_juridica,
    -- Capital social vem com vírgula decimal (padrão brasileiro)
    try_cast(replace(capital_social, ',', '.') as double) as capital_social,
    porte,
    case porte
        when '01' then 'Micro Empresa'
        when '03' then 'Empresa de Pequeno Porte'
        when '05' then 'Demais'
        else 'Não informado'
    end                                              as porte_descricao
from fonte
where cnpj_basico is not null
  and trim(cnpj_basico) <> ''
