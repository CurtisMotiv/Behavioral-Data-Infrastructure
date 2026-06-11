

with src as (
  select
    *,
    coalesce(peer_cohort_size, 0) as peer_cohort_size_num,
    lower(coalesce(health_center_type, 'unknown')) as health_center_type_norm
  from "postgres"."public_intermediate"."int_fqhc_profile"
),

components as (
  select
    *,

    -- Cohort size component: 0-60
    case
      when peer_cohort_size_num >= 50 then 60
      when peer_cohort_size_num >= 20 then 45
      when peer_cohort_size_num >= 10 then 30
      when peer_cohort_size_num >= coalesce(5, 5) then 20
      when peer_cohort_size_num > 0 then 10
      else 5
    end as cohort_size_score,

    -- Health center type component: 0-40
    case
      when health_center_type_norm like '%federally qualified%' then 40
      when health_center_type_norm like '%community health%' then 35
      when health_center_type_norm in ('rural health clinic','rhc') then 30
      when health_center_type_norm = 'unknown' then 20
      else 25
    end as health_center_type_score

  from src
),

scored as (
  select
    *,
    (cohort_size_score + health_center_type_score) as raw_score,
    greatest(0, least(100, (cohort_size_score + health_center_type_score))) as plan_health_grade_score,
    case
      when (cohort_size_score + health_center_type_score) >= 80 then 'A'
      when (cohort_size_score + health_center_type_score) >= 65 then 'B'
      when (cohort_size_score + health_center_type_score) >= 50 then 'C'
      else 'D'
    end as plan_health_grade
  from components
)

select *
from scored