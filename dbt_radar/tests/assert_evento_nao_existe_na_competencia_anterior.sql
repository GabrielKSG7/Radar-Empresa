-- Teste central do Event Store: nenhum evento NEW_COMPANY pode se referir a
-- um CNPJ que JÁ existia na competência anterior. Se falhar, o set difference
-- está errado e o produto inteiro perde credibilidade.
select e.event_id, e.cnpj
from {{ ref('evt_new_company') }} e
where exists (
    select 1
    from {{ ref('slv_estabelecimentos') }} s
    where s.cnpj = e.cnpj
      and s.competencia = '{{ var("competencia_anterior") }}'
)
