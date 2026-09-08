-- Um CNPJ não pode aparecer duas vezes na mesma competência.
-- Falha aqui indica fatia duplicada na ingestão (ZIP baixado duas vezes).
select cnpj, competencia, count(*) as ocorrencias
from {{ ref('slv_estabelecimentos') }}
group by cnpj, competencia
having count(*) > 1
