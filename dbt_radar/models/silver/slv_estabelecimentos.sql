{{ config(materialized='table') }}

with source as (
    select * from {{ source('rfb_bronze', 'estabelecimentos') }}
)

select
    -- 1. Unificando o CNPJ (14 dígitos com zeros à esquerda)
    lpad(cnpj_basico::VARCHAR, 8, '0') || lpad(cnpj_ordem::VARCHAR, 4, '0') || lpad(cnpj_dv::VARCHAR, 2, '0') as cnpj,

    -- 2. Colunas de Domínio
    identificador_matriz_filial,
    situacao_cadastral,
    cnae_principal,
    id_municipio,
    uf,

    -- 3. Tipagem de Data (Convertendo YYYYMMDD string para tipo DATE)
    -- Usamos try_strptime para que, se houver '00000000' ou sujeira, ele retorne NULL em vez de quebrar
    try_strptime(data_inicio_atividade::VARCHAR, '%Y%m%d')::DATE as data_inicio_atividade

from source