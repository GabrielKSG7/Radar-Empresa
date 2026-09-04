{{ config(materialized='table') }}

with icp_matches as (
    select * from {{ ref('gld_icp_matches') }}
)

select
    event_id,
    cnpj,
    event_type,
    event_date,
    municipio_nome,
    cnae_descricao,
    
    -- 1. Calculando o Score (Determinístico)
    (
        50 -- Pontuação base garantida por ser um Match de ICP
        + case 
            -- Bônus de Recência
            when event_date >= current_date - interval 7 day then 35
            when event_date >= current_date - interval 15 day then 15
            else 0 
          end
        -- No futuro, podemos somar pontos por Porte da Empresa, Capital Social, etc.
    ) as opportunity_score,
    
    -- 2. Princípio 8: O Score deve ser explicável (White-box)
    match_reason || ' | Motivo do Score: Base ICP (+50), ' ||
    case 
        when event_date >= current_date - interval 7 day then 'Altíssima Recência (+35)'
        when event_date >= current_date - interval 15 day then 'Média Recência (+15)'
        else 'Baixa Recência (+0)'
    end as score_explanation,
    
    current_timestamp as scored_at

from icp_matches

-- Garantimos que só passa quem tem um score mínimo de relevância
where opportunity_score >= 50