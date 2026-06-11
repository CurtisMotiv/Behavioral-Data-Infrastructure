
  
    

  create  table "postgres"."public_marts_fqhc"."mart_fqhc_intelligence__dbt_tmp"
  
  
    as
  
  (
    

with profile as (
    select *
    from "postgres"."public_intermediate"."int_fqhc_profile"
),
retirement as (
    select *
    from "postgres"."public_intermediate"."int_fqhc_retirement_profile"
),
plan_health as (
    select site_name, state, plan_health_grade
    from "postgres"."public_enrichment"."e01_plan_health_grade"
)

select
    p.site_name,
    p.state,
    p.health_center_type,
    p.peer_cohort_assignment,
    p.peer_cohort_size_category,
    ph.plan_health_grade,
    
    r.tot_active_partcp_cnt
from profile p

left join plan_health ph
    on p.site_name = ph.site_name
    and p.state = ph.state

left join lateral (
    select rr.tot_active_partcp_cnt
    from retirement rr
    where upper(trim(coalesce(rr.sponsor_dfe_name, rr.plan_name, ''))) = upper(trim(coalesce(p.site_name, '')))
    limit 1
) r on true
  );
  