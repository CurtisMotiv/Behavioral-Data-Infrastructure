# Motiv Alliance — dbt Project (`dbt_motiv`)

**Version:** v0.1 (Phase 0 Sprint A skeleton)
**Owner:** Chief, Innovation, Data Infrastructure & R&D
**Status:** Skeleton — runs end-to-end against an empty database; populates as upstream pipelines deliver data through Sprints A–C.

---

## What This Is

`dbt_motiv` is the transformation layer of the Motiv Alliance Intelligence Platform. It transforms raw ingested data (IRS 990 XML, Schedule J extractions, CMS Hospital Compare, EMMA bond filings, FEC contributions, HRSA UDS, and the rest) into the analytic surfaces the application consumes. Every enrichment, every peer cohort, every prospect prioritization score is defined here as versioned SQL.

The project is multi-tenant from day one: a single dbt run produces analytic surfaces for the Hospitals, FQHC, and Nonprofits platforms, partitioned by `platform_family`. The architecture honors the Pre-Launch Memo §4.1 directive without compromise.

## Architecture

```
sources (raw tables in shared/hospital/fqhc/nonprofit schemas)
    │
    ▼
staging/  ──── 1:1 with source, light typing, derived geography columns
    │
    ▼
intermediate/  ──── joins, derived ratios, peer cohort assignment
    │
    ▼
enrichment/  ──── the 22+ enrichments (Phase 0 Sprint A delivers e01-e04)
    │
    ▼
marts/  ──── application-facing denormalized surfaces
```

Materialization defaults: `view` in staging (cheap, always fresh), `table` in intermediate, `table` in marts. Move to `incremental` selectively in Phase 1 when refresh times demand it.

## Project Structure

```
dbt_motiv/
├── dbt_project.yml              # Project config; vars; materialization defaults
├── profiles.template.yml        # Connection template; copy to ~/.dbt/profiles.yml
├── packages.yml                 # dbt-utils dependency
├── models/
│   ├── sources.yml              # Source registry (shared/hospital/fqhc/nonprofit)
│   ├── staging/
│   │   └── shared/              # stg_organizations, stg_executives, stg_form_990_filings, stg_bd_outcomes
│   ├── intermediate/
│   │   └── shared/              # int_org_financial_profile, int_executive_compensation
│   ├── enrichment/              # e01 - e04 (the 22+ enrichments live here)
│   └── marts/
│       └── shared/              # mart_prospect_prioritization
├── macros/
│   └── motiv_helpers.sql        # filter_platform, assign_peer_cohort, civic_engagement_score, etc.
├── tests/
│   └── enrichment_provenance_complete.sql   # Custom singular test
├── seeds/                       # CSV reference data (populated as needed)
├── snapshots/                   # SCD2 snapshots (deferred to Phase 1)
└── analyses/                    # Ad-hoc analytical queries (not promoted to models)
```

## Phase 0 Sprint A Deliverables — What's In This Skeleton

| Layer | Models | Status |
|---|---|---|
| Staging | `stg_organizations`, `stg_executives`, `stg_form_990_filings`, `stg_bd_outcomes` | Complete |
| Intermediate | `int_org_financial_profile`, `int_executive_compensation` | Complete |
| Enrichment | `e01_plan_health_grade`, `e02_retirement_readiness_gap`, `e03_compensation_anomaly`, `e04_motiv_opportunity_score` | Complete; pattern established |
| Marts | `mart_prospect_prioritization` | Complete |
| Macros | Multi-tenant filter, peer cohort assignment, civic engagement score, provenance helpers | Complete |
| Tests | dbt-native tests on every model + custom provenance test | Complete |

## What's Deferred

- Enrichments e05–e22 (18 enrichments) — Sprint C, Days 49–63 per Charter §3.3.
- Hospital-specific intermediate models pulling from `cms_hospital_data` and `emma_bond_filings` — Sprint B Days 28–42.
- FQHC schema staging models — Phase 1 per FQHC Schema Memo.
- Nonprofit schema staging models — Phase 2.
- Incremental materialization — Phase 1 when refresh time becomes a constraint.
- Snapshots for slowly-changing dimensions (executive tenure changes) — Phase 1.

## Setup

```bash
# 1. Install dbt-core and the Postgres adapter
pip install --break-system-packages dbt-core dbt-postgres

# 2. Copy the profiles template and fill in real credentials
cp profiles.template.yml ~/.dbt/profiles.yml
# Edit ~/.dbt/profiles.yml — replace env_var references with your secrets manager

# 3. Set environment variables for Supabase or Neon connection
export MOTIV_PG_HOST=...
export MOTIV_PG_USER=...
export MOTIV_PG_PASSWORD=...
export MOTIV_PG_DB=postgres

# 4. Install dbt packages
dbt deps

# 5. Verify connection
dbt debug

# 6. Run end-to-end (will run against empty source tables in Sprint A)
dbt run

# 7. Run tests
dbt test
```

## Running

```bash
# Build everything
dbt build

# Build only enrichments
dbt run --select tag:enrichment

# Build only the Hospital platform
dbt run --select tag:hospital

# Build only the prospect prioritization mart
dbt run --select mart_prospect_prioritization

# Test only the headline mart
dbt test --select mart_prospect_prioritization
```

## Geography Scoping

The variable `current_geography_filter` in `dbt_project.yml` controls scope:

- Phase 0: `'IL'` (default; Illinois only)
- Phase 1: `'MIDWEST'` (9-state Midwest)
- Phase 2+: `'NATIONAL'` (no filter)

To run a Phase 1 build during Phase 0 development:
```bash
dbt run --vars '{current_geography_filter: MIDWEST}'
```

## Methodology Versioning

Every enrichment writes its `enrichment_version` (read from `dbt_project.yml` var `enrichment_version`) into output rows via the `enrichment_metadata()` macro. When methodology changes:

1. Increment `enrichment_version` in `dbt_project.yml` (e.g., `v1.0` → `v1.1`).
2. Document the change in `/docs/enrichment_methodology/<enrichment>/CHANGELOG.md`.
3. Run `dbt build` — old rows are overwritten with the new version.
4. The full provenance trail of past versions remains queryable via `shared.provenance_events`.
5. Methodology change is logged in the Journal (Phase 0 Charter §9 template).

## Provenance Integration

Every dbt-driven write is attributed to the dbt actor via the `pre-hook` configured in `profiles.yml`:

```yaml
pre-hook:
  - "SET LOCAL motiv.actor = 'pipeline:dbt:dev'"
```

The Postgres triggers defined in `migrations_phase0_sprint_a.sql` then write the actor into `shared.provenance_events`. This makes lineage from raw source through enrichment to mart fully reconstructable.

## Charter Discipline

The macros in `macros/motiv_helpers.sql` encode the 'What We Don't Mine' Charter directly:

- `civic_engagement_score()` — never reveals partisan tilt, donor identity, or amount distribution. The macro is intentionally aggregate and non-attributive (per FQHC Schema Memo §8.4).
- `assign_peer_cohort()` — uses revenue band, not protected-class proxies (per Charter §2).
- `filter_full_enrichment()` — enforces depth-on-demand, which limits compute and surface area.

Changing any of these macros requires Chief sign-off and a Decisions Log entry.

## Quarterly Audit Hook

The custom test at `tests/enrichment_provenance_complete.sql` runs as part of standard `dbt test` and verifies that every enrichment row carries complete provenance metadata. The quarterly provenance audit (Phase 0 Charter §6 gate criterion) extends this with a sample-based replay test that should be added in Sprint D.

## Open Questions (Sprint A → Sprint B)

1. **Schedule J source table location.** This skeleton assumes a `raw.schedule_j_extractions` table populated by the Claude API extraction pipeline. The actual table name and schema location should be confirmed when the extraction pipeline is built in Sprint B.
2. **Enrichment refresh cadence.** Phase 0 runs full-rebuild nightly. Move to incremental in Phase 1 when full rebuild exceeds 30 minutes.
3. **Cross-platform calibration.** `bd_outcomes` is shared shape across platforms, but model calibration logic is not yet defined. Schedule for Phase 2 once outcomes table has volume.

---

*Last updated: Phase 0 Sprint A activation.*
*Maintained by: Chief, Innovation, Data Infrastructure & R&D.*
