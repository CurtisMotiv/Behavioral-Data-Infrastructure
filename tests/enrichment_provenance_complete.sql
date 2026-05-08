-- =============================================================================
-- TEST: Every enrichment row has provenance metadata populated
-- =============================================================================
-- Per the 'What We Don't Mine' Charter §7 (quarterly self-audit) and the
-- Phase 0 Charter §6 gate criterion on provenance audit pass rate.
--
-- This test fails (returns rows) if any enrichment is missing version,
-- model, or computed_at metadata. The dbt test runs as part of the
-- standard `dbt test` invocation.
-- =============================================================================

{% set enrichment_models = [
    'e01_plan_health_grade',
    'e02_retirement_readiness_gap',
    'e03_compensation_anomaly',
    'e04_motiv_opportunity_score'
] %}

{% for model_name in enrichment_models %}
    SELECT
        '{{ model_name }}' AS failing_model,
        COUNT(*) AS rows_missing_provenance
    FROM {{ ref(model_name) }}
    WHERE enrichment_version IS NULL
       OR enrichment_model IS NULL
       OR computed_at IS NULL
       OR computed_by IS NULL
    HAVING COUNT(*) > 0

    {% if not loop.last %}UNION ALL{% endif %}
{% endfor %}
