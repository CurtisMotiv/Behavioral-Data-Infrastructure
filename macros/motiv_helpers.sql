{# =========================================================================
   Motiv Alliance — dbt Macros v0.1
   =========================================================================
   These macros enforce architectural discipline across all models:
   - Multi-tenant platform_family filtering
   - Geography filtering for staged rollout
   - Peer cohort assignment with minimum cohort size enforcement
   - Civic engagement signal terminology helpers
   - Provenance-aware insert helpers

   IMPORTANT: Macros encode policy, not just convenience. Changing a macro
   changes behavior across many models — review and version accordingly.
   ========================================================================= #}


{# -------------------------------------------------------------------------
   filter_platform — Multi-tenant filter
   -------------------------------------------------------------------------
   Use in every model that touches shared.organizations or any cross-platform
   table when the model is platform-specific.

   Usage:
     SELECT * FROM {{ ref('stg_organizations') }}
     WHERE {{ filter_platform('HOSPITAL') }}
   ------------------------------------------------------------------------- #}

{% macro filter_platform(platform) %}
    platform_family = '{{ platform }}'
{% endmacro %}


{# -------------------------------------------------------------------------
   filter_geography — Phase 0 / Phase 1 geography scope
   -------------------------------------------------------------------------
   Phase 0: 'IL' only.
   Phase 1: 'IL', 'IN', 'IA', 'MI', 'MN', 'MO', 'NE', 'OH', 'WI'.
   Phase 2+: no filter (national).

   Reads var('current_geography_filter') from dbt_project.yml.
   ------------------------------------------------------------------------- #}

{% macro filter_geography(geography_field='geography') %}
    {%- set scope = var('current_geography_filter', 'IL') -%}
    {%- if scope == 'NATIONAL' -%}
        TRUE  -- No geography filter; national scope
    {%- elif scope == 'MIDWEST' -%}
        ({{ geography_field }}->>'state') IN ('IL', 'IN', 'IA', 'MI', 'MN', 'MO', 'NE', 'OH', 'WI')
    {%- else -%}
        ({{ geography_field }}->>'state') = '{{ scope }}'
    {%- endif -%}
{% endmacro %}


{# -------------------------------------------------------------------------
   assign_peer_cohort — Cohort assignment with size guard
   -------------------------------------------------------------------------
   Assigns each organization to a peer cohort based on platform-appropriate
   dimensions. Returns NULL for organizations whose cohort would be smaller
   than var('min_peer_cohort_size'), which prevents brittle small-cohort
   percentile calculations.

   Cohort composition:
     HOSPITAL:  state + revenue_band + facility_type
     FQHC:      hrsa_region + grant_type + size_band
     NONPROFIT: state + ntee_major + revenue_band
   ------------------------------------------------------------------------- #}

{% macro assign_peer_cohort(platform_family_field, geography_field, ntee_field=None, revenue_field=None) %}
    CASE
        WHEN {{ platform_family_field }} = 'HOSPITAL' THEN
            CONCAT(
                ({{ geography_field }}->>'state'), '_',
                {{ revenue_band(revenue_field) }}
            )
        WHEN {{ platform_family_field }} = 'FQHC' THEN
            CONCAT(
                ({{ geography_field }}->>'hrsa_region'), '_',
                {{ revenue_band(revenue_field) }}
            )
        WHEN {{ platform_family_field }} = 'NONPROFIT' THEN
            CONCAT(
                ({{ geography_field }}->>'state'), '_',
                COALESCE({{ ntee_field }}, 'UNK'), '_',
                {{ revenue_band(revenue_field) }}
            )
        ELSE NULL
    END
{% endmacro %}


{# -------------------------------------------------------------------------
   revenue_band — Categorize total_revenue into bands for peer comparison
   ------------------------------------------------------------------------- #}

{% macro revenue_band(revenue_field) %}
    CASE
        WHEN {{ revenue_field }} IS NULL THEN 'UNK'
        WHEN {{ revenue_field }} < 1000000 THEN 'sub_1m'
        WHEN {{ revenue_field }} < 10000000 THEN '1m_10m'
        WHEN {{ revenue_field }} < 50000000 THEN '10m_50m'
        WHEN {{ revenue_field }} < 100000000 THEN '50m_100m'
        WHEN {{ revenue_field }} < 500000000 THEN '100m_500m'
        WHEN {{ revenue_field }} < 1000000000 THEN '500m_1b'
        WHEN {{ revenue_field }} < 5000000000 THEN '1b_5b'
        ELSE 'over_5b'
    END
{% endmacro %}


{# -------------------------------------------------------------------------
   peer_percentile — Compute percentile within cohort
   -------------------------------------------------------------------------
   Standard pattern for any enrichment that benchmarks an organization
   against its peer cohort. Returns NULL if cohort is too small (caller
   should already have filtered, but this is a defense-in-depth check).
   ------------------------------------------------------------------------- #}

{% macro peer_percentile(value_field, cohort_field) %}
    CASE
        WHEN COUNT(*) OVER (PARTITION BY {{ cohort_field }}) < {{ var('min_peer_cohort_size') }} THEN NULL
        ELSE PERCENT_RANK() OVER (PARTITION BY {{ cohort_field }} ORDER BY {{ value_field }})
    END
{% endmacro %}


{# -------------------------------------------------------------------------
   civic_engagement_score — Per FQHC Schema Memo §8.4
   -------------------------------------------------------------------------
   This macro renders FEC contribution data as a civic engagement signal,
   never a behavioral profile. The output is intentionally aggregate and
   non-attributive.

   We do NOT compute partisan tilt, donor identity matching, or anything
   that could be construed as behavioral profiling. The 'What We Don't
   Mine' Charter §3 governs this macro.
   ------------------------------------------------------------------------- #}

{% macro civic_engagement_score(executive_id_field, lookback_years=10) %}
    {#- Returns a 0-100 engagement intensity score based on contribution
        frequency over the lookback window. Does NOT reveal recipient
        identity, party, or amount distribution. -#}
    LEAST(100, COALESCE(
        (
            SELECT COUNT(DISTINCT calendar_year)::numeric * 10
            FROM raw.fec_contributions
            WHERE executive_id = {{ executive_id_field }}
              AND calendar_year >= EXTRACT(YEAR FROM NOW()) - {{ lookback_years }}
        ),
        0
    ))
{% endmacro %}


{# -------------------------------------------------------------------------
   enrichment_metadata — Standard metadata columns for every enrichment
   -------------------------------------------------------------------------
   Every enrichment model includes these columns to support provenance,
   versioning, and the quarterly audit. Add to the SELECT list with:
     SELECT my_calc, {{ enrichment_metadata() }} FROM ...
   ------------------------------------------------------------------------- #}

{% macro enrichment_metadata() %}
    '{{ var("enrichment_version") }}'::text AS enrichment_version,
    '{{ this.name }}'::text AS enrichment_model,
    NOW() AS computed_at,
    '{{ var("dbt_actor") }}'::text AS computed_by
{% endmacro %}


{# -------------------------------------------------------------------------
   filter_active_thin — Depth-on-demand helper
   -------------------------------------------------------------------------
   Most enrichments run only on organizations with enrichment_tier='full'.
   This macro applies the standard filter.
   ------------------------------------------------------------------------- #}

{% macro filter_full_enrichment(enrichment_tier_field='enrichment_tier') %}
    {{ enrichment_tier_field }} = 'full' OR {{ enrichment_tier_field }} IS NULL
{% endmacro %}


{# -------------------------------------------------------------------------
   set_provenance_actor — Pre-hook for provenance attribution
   -------------------------------------------------------------------------
   Used in pre-hooks to ensure the database trigger writes the right actor
   to provenance_events. Each model can override the default actor.
   ------------------------------------------------------------------------- #}

{% macro set_provenance_actor(actor_name) %}
    SET LOCAL motiv.actor = '{{ actor_name }}'
{% endmacro %}
