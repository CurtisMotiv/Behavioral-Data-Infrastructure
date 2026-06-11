

with source_data as (
  select *
  from public.raw_form_5500
),

cleaned as (
  select
    ack_id,
    plan_name,
    sponsor_dfe_name,
    spons_dfe_ein,
    spons_dfe_mail_us_state,
    business_code,
    type_pension_bnft_code,
    tot_active_partcp_cnt,
    tot_partcp_boy_cnt,
    form_plan_year_begin_date,
    filing_status,
    upper(trim(coalesce(sponsor_dfe_name, plan_name, ''))) as sponsor_name_norm,
    upper(trim(coalesce(plan_name, sponsor_dfe_name, ''))) as plan_name_norm
  from source_data
)

select *
from cleaned