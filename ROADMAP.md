# Motiv Alliance Intelligence Platform — Development Roadmap

## Overview

The Motiv Alliance Intelligence Platform is a multi-phase initiative to build an integrated data infrastructure connecting behavioral science, financial wellness, and organizational leadership intelligence. The platform combines public data sources (HRSA, IRS 990, Form 5500) with news feeds, policy monitoring, and proprietary research to enable evidence-based decision-making for FQHCs, hospitals, and nonprofits.

---

## Phase 0: Illinois FQHC Focus ✅ COMPLETED

**Timeline:** May–June 2026

### Completed Deliverables

#### Data Ingestion
- **HRSA National FQHC Database:** 18,904 sites across all 50 states
  - Extracted via HRSA Data Explorer API
  - Loaded into `raw_hrsa_sites` table
- **Form 5500 Retirement Plan Data:** 1,570 unique plans
  - Downloaded from DOL bulk archives and open-data CSV
  - Filtered to healthcare NAICS codes
  - Loaded into `raw_form_5500` table
- **990 Bulk Extraction (In Progress):** ProPublica 990 lookup by site name
  - Script: `Extraction/extract_990_bulk.py`
  - Connection resilience with progress persistence
  - Keepalive pings and EIN normalization

#### dbt Transformation Pipeline
- **Staging Layer:**
  - `stg_hrsa_sites` (source: public_staging)
  - `stg_form_5500` (raw Form 5500 data with column mappings)
  
- **Intermediate Layer:**
  - `int_fqhc_profile`: Peer cohort assignments by state and health center type
  - `int_fqhc_retirement_profile`: Join retirement data to FQHC profiles by normalized org name
  
- **Enrichment Layer:**
  - `e01_plan_health_grade`: Dual-component scoring (cohort size + health center type)
    - Cohort Size Score: 5–60 points
    - Health Center Type Score: 20–40 points
    - Final Grade: A (80+), B (65–79), C (50–64), D (<50)
  
- **Marts Layer:**
  - `mart_fqhc_intelligence`: Denormalized mart combining profile, retirement, and health grade
    - **27,232 rows** (Illinois FQHC sites with profiles and enrichment)
    - Columns: site_name, state, health_center_type, peer_cohort_assignment, peer_cohort_size_category, plan_health_grade, tot_active_partcp_cnt

#### Quality & Testing
- **dbt Compile:** PASS
- **Tests:** 10 not_null tests across profile, retirement, and mart models
- **Test Pass Rate:** 100% (Phase 0 Sprint A gate criteria met per Charter §6)

#### Infrastructure
- **Database:** Supabase PostgreSQL (db.bnrmplilxdkfdtlscmnb.supabase.co)
- **Extraction Scripts:** Python 3.x with psycopg2 and requests
- **Version Control:** Git with .gitignore (excludes *.csv, *.xlsx, dbt/target, dbt/logs, __pycache__, .env, profiles.yml)

---

## Phase 1: Historical Data & Intelligence Feed 🔄 PENDING

**Timeline:** Q3 2026

### Data Ingestion Enhancements
- **Historical 990 & Form 5500:** 3-year lookback (2023–2025)
- **Schedule J Extraction:** Executive compensation detail
  - Parse and normalize salary, bonus, deferred comp, severance
  - Load into `raw_schedule_j` table
  
- **News & Intelligence Feeds:**
  - Google News RSS integration (leadership changes, new projects)
  - Federal Register API monitoring (HRSA policy, CMS rules)
  - HRSA news feed subscription
  - State health department RSS feeds (regulatory updates)

### Transformation & Enrichment
- **Executive Profiles Layer:**
  - Staging: `stg_schedule_j` (raw compensation detail)
  - Intermediate: `int_executive_profiles` (normalize roles: CEO, CFO, CMO, CNO, Chief Compliance Officer, Chief Data Officer)
  - Enrichment: `e02_executive_compensation` (deferred comp tracking, retirement balances, peer comparison)
  
- **Differentiated Health Grades:**
  - `e02_plan_health_grade_v2`: Enhanced scoring incorporating compensation benchmarks
  
- **News & Policy Intelligence:**
  - Staging: `stg_news_events` (parsed and categorized from feeds)
  - Enrichment: `e03_news_intelligence` (AI-assisted summarization and categorization)
  - Link: correlate with organizational changes and regulatory timelines

### Application Features
- Intelligence Dashboard (read-only for Phase 1)
- Executive compensation benchmarking view
- News timeline and policy monitoring
- Alerts for peer organizations

---

## Phase 2: Midwest Expansion 📍 PENDING

**Timeline:** Q4 2026

### Geographic & Segment Expansion
- **9-State Midwest Rollout:** IL, IN, IA, MI, MN, MO, WI, OH, KY
- **Hospital System Data Layer:**
  - CMS Hospital Compare data integration
  - American Hospital Association (AHA) Annual Survey
  - Hospital financial performance metrics
  
- **Nonprofit Organization Data Layer:**
  - Expanded 990 coverage (all form types)
  - Foundation and funder networks
  - Grant and funding source tracking
  
- **Cross-Segment Benchmarking:**
  - FQHC vs. hospital vs. nonprofit comparisons
  - Cohort analysis across vertical boundaries

### Data Infrastructure
- Schema expansion: `hospitals/`, `nonprofits/` alongside `fqhc/`
- Multi-tenant filtering via `platform_family` column

---

## Phase 3: National Coverage & Product Layer 🌐 PENDING

**Timeline:** 2027

### Geographic Expansion
- **National Coverage:** All 50 states + US territories
- **Segment Coverage:** FQHCs, hospitals, nonprofits, health plans

### Application Layer
- **Dashboard & Visualization:**
  - Peer cohort performance cards
  - Executive compensation trends
  - News and policy timeline
  - Health grade evolution
  
- **Client-Facing Portal:**
  - Organization profile page
  - Competitive benchmarking dashboard
  - Custom alert configuration
  - Export and reporting tools
  
- **Behavioral Diagnostic Tools:**
  - Executive Financial Wellness Clinic integration
  - Behavioral Retirement Lab integration
  - Behavioral Cash Flow Intelligence integration
  - Personalized insights and recommendations

### Intelligence Enhancement
- Real-time policy monitoring alerts
- Predictive modeling for organizational changes
- Peer-led best practice sharing

---

## Dissertation Research Layer 🎓 PENDING

**Timeline:** Ongoing (parallel track)

### Research Objectives
- **Behavioral Pattern Analysis:**
  - Executive compensation decision-making
  - Correlation with organizational outcomes
  - Peer influence and benchmarking effects
  
- **Deferred Compensation Gap Analysis:**
  - Prevalence and trends across segments
  - Leadership risk profiles
  - Financial wellness implications
  
- **Academic Validation:**
  - Diagnostic tool efficacy studies
  - Peer-reviewed publication pipeline
  - Conference presentations

### Data Pipeline for Research
- Separate research schema with privacy-compliant anonymization
- Longitudinal tracking tables for behavior analysis
- Integration with Behavioral Science division research protocols

---

## Success Metrics

| Phase | Metric | Target |
|-------|--------|--------|
| 0 | Rows in mart_fqhc_intelligence | 27,232 ✅ |
| 0 | dbt Test Pass Rate | 100% ✅ |
| 0 | FQHC Coverage (IL) | 100% ✅ |
| 1 | 990 Historical Coverage | 3 years |
| 1 | News Feed Ingestion | 4+ sources |
| 1 | Executive Profile Coverage | 80%+ of CEOs/CFOs |
| 2 | State Coverage | 9 states |
| 3 | National Coverage | 50 states |
| 3 | Dashboard Daily Active Users | TBD |

---

## Known Constraints & Assumptions

1. **Data Availability:** ProPublica 990 search may have rate limits and gaps; fallback to IRS direct download planned.
2. **Executive Compensation Privacy:** Schedule J data is public but requires careful compliance review.
3. **API Dependencies:** HRSA, IRS, Google News, and Federal Register APIs subject to changes; monitoring and fallback strategies required.
4. **dbt Performance:** Current intermediate/mart materialization as tables; incremental strategies to be evaluated for Phase 2+.
5. **Multi-Tenant Architecture:** All models default to view materialization in staging for fresh data; table materialization in intermediate/marts for performance.

---

## References

- **Charter §6:** Phase 0 gate criteria require dbt test pass rate ≥95% and complete FQHC peer cohort coverage.
- **Pre-Launch Memo (May 2):** Multi-tenant architecture design and FQHC schema specification.
- **Behavioral Science Protocols:** Executive Financial Wellness Clinic, Behavioral Retirement Lab, Behavioral Cash Flow Intelligence integration specifications.
