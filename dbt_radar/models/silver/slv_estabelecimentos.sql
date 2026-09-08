{{ config(materialized='table') }}

-- Silver: tipagem, limpeza e chaves consistentes.
-- Mantém TODAS as competências: o diff entre elas é a base do Event Store.

with fonte as (
    select * from {{ ref('brz_estabelecimentos') }}
)

select
    -- Chave de negócio: CNPJ completo, 14 dígitos com zeros à esquerda
    lpad(cnpj_basico, 8, '0')
      || lpad(cnpj_ordem, 4, '0')
      || lpad(cnpj_dv,    2, '0')                    as cnpj,
    lpad(cnpj_basico, 8, '0')                        as cnpj_basico,
    competencia,

    nullif(trim(nome_fantasia), '')                  as nome_fantasia,
    identificador_matriz_filial,
    situacao_cadastral,
    lpad(cnae_principal, 7, '0')                     as cnae_principal,
    id_municipio,
    uf,
    nullif(trim(bairro), '')                         as bairro,
    nullif(trim(cep), '')                            as cep,
    -- Contato: mantido para viabilizar a ação comercial. Ver nota de LGPD
    -- no README — dado público, finalidade registrada, sem enriquecimento
    -- de pessoa física.
    nullif(trim(correio_eletronico), '')             as email,
    nullif(trim(ddd_1 || telefone_1), '')            as telefone,

    -- try_strptime devolve NULL em vez de quebrar com '00000000' ou sujeira
    try_strptime(data_inicio_atividade, '%Y%m%d')::date  as data_inicio_atividade,
    try_strptime(data_situacao_cadastral, '%Y%m%d')::date as data_situacao_cadastral

from fonte
where cnpj_basico is not null
  and trim(cnpj_basico) <> ''
