-- O score é uma soma ponderada; se estourar 100 ou for negativo, os pesos
-- do ICP estão inconsistentes.
select event_id, opportunity_score
from {{ ref('gld_opportunities') }}
where opportunity_score < 0 or opportunity_score > 100
