
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "postgres"."public_dbt_test_failures"."not_null_mart_fqhc_intelligence_state"
    
      
    ) dbt_internal_test