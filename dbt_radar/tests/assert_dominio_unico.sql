-- Após a deduplicação por competência, dominio+codigo deve ser único.
select dominio, codigo, count(*) as ocorrencias
from {{ ref('slv_dominios') }}
group by dominio, codigo
having count(*) > 1
