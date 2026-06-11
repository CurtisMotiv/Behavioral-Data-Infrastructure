{{ config(
    materialized='table',
    tags=['intermediate', 'fqhc']
) }}

with hrsa_sites as (
    select *
    from public_staging.stg_hrsa_sites
),

peer_cohort_assignments as (
    select
        *,
        state as peer_cohort_state,
        health_center_type as peer_cohort_health_center_type,
        concat(state, ' | ', health_center_type) as peer_cohort_assignment,
        dense_rank() over(order by state, health_center_type) as peer_cohort_id,
        count(*) over(partition by state, health_center_type) as peer_cohort_size,
        case
            when count(*) over(partition by state, health_center_type) >= coalesce({{ var('min_peer_cohort_size') }}, 5)
                then 'sufficient'
            else 'undersized'
        end as peer_cohort_size_category
    from hrsa_sites
)

select *
from peer_cohort_assignments
