-- Camada Bronze: espelho fiel do dado cru, sem transformação de negócio.
-- A coluna `competencia` vem do particionamento Hive dos Parquet.
select * from {{ source('rfb', 'estabelecimentos') }}
