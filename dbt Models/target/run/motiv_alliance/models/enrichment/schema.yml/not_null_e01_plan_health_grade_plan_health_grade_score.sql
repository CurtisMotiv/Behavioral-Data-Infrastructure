
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "postgres"."public_dbt_test_failures"."not_null_e01_plan_health_grade_plan_health_grade_score"
    
      
    ) dbt_internal_test