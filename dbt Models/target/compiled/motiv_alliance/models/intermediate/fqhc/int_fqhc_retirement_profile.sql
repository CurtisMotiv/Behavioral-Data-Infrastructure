

with retirement_data as (
  select *
  from "postgres"."public_staging"."stg_form_5500"
),

fqhc_profiles as (
  select
    *,
    upper(trim(coalesce(site_name, ''))) as profile_name_norm
  from "postgres"."public_intermediate"."int_fqhc_profile"
)

select
  r.*,
  p.peer_cohort_state,
  p.peer_cohort_health_center_type,
  p.peer_cohort_assignment,
  p.peer_cohort_id,
  p.peer_cohort_size,
  p.peer_cohort_size_category
from retirement_data r
left join fqhc_profiles p
  on upper(trim(coalesce(r.sponsor_dfe_name, r.plan_name, ''))) = p.profile_name_norm