
  create view "postgres"."public_staging"."stg_hrsa_sites__dbt_tmp"
    
    
  as (
    with source as (
    select * from public.raw_hrsa_sites
),

staged as (
    select
        site_name,
        services,
        health_center_type,
        location_type,
        location_setting,
        county,
        state,
        grant_number,
        case
            when state = 'IL' then 'ILLINOIS'
            when state in ('IN','MI','OH','WI','MN','IA','MO','ND','SD') 
            then 'MIDWEST'
            else 'NATIONAL'
        end as geography_region
    from source
)

select * from staged
  );