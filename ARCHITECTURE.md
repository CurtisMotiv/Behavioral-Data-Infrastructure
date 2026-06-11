# Motiv Alliance Intelligence Platform — Architecture

## System Overview

The Motiv Alliance Intelligence Platform is a multi-layered data architecture designed to ingest, transform, and surface organizational intelligence for FQHCs, hospitals, and nonprofits. The architecture follows a classic data lakehouse pattern with three primary flows:

1. **Extraction**: Source system APIs and feeds → raw data tables
2. **Transformation**: Raw data → cleansed, modeled, enriched business views via dbt
3. **Intelligence**: Analytics, research, and application-facing marts

---

## Layer 1: Data Sources

### Public Data Feeds

#### HRSA National FQHC Registry
- **Endpoint:** HRSA Data Explorer API
- **Update Frequency:** Quarterly
- **Records:** 18,904 federally qualified health centers (all 50 states)
- **Key Fields:** site_name, state, health_center_type, service_area_population
- **Purpose:** Foundational organization directory and peer cohort basis

#### IRS Form 990 (Tax-Exempt Organizations)
- **Source:** ProPublica Nonprofit Explorer API + IRS bulk downloads
- **Extraction Method:** Site name matching + historical lookup
- **Update Frequency:** Annual (with 6-month lag)
- **Records:** 1.5M+ organizations; filtered to healthcare nonprofits
- **Key Fields:** ein, organization_name, asset_amount, income_amount, ntee_code, raw_json (full form)
- **Purpose:** Organizational financial health, asset base, executive compensation (on Schedule J)

#### Form 5500 (Employee Benefit Plans)
- **Source:** DOL ERISA filing database + open-data CSV
- **Extraction Method:** NAICS filter (healthcare codes 621xxx)
- **Update Frequency:** Annual
- **Records:** 1,570 plans in healthcare sector
- **Key Fields:** plan_name, sponsor_dfe_name, tot_active_partcp_cnt, assets, contributions
- **Purpose:** Retirement plan coverage, employee benefit trends, workforce engagement

#### Schedule J (Executive Compensation)
- **Source:** IRS 990-N, 990-EZ, 990 filings
- **Extraction Method:** Form parsing and normalization
- **Update Frequency:** Annual (with delay)
- **Key Fields:** executive_name, title, compensation_type (salary/bonus/deferred), amount
- **Purpose:** Leadership financial profiles, peer compensation benchmarking

### News & Intelligence Feeds

#### Google News RSS
- **Query:** Organization name + keywords (leadership, merger, clinical trial)
- **Update Frequency:** Real-time (polled hourly)
- **Key Fields:** title, link, publish_date, summary
- **Purpose:** Leadership changes, new projects, organizational announcements

#### Federal Register API
- **Query:** HRSA, CMS, OPM rules and notices
- **Update Frequency:** Daily
- **Key Fields:** document_type, agency, publication_date, summary, effective_date
- **Purpose:** Regulatory monitoring, policy impact assessment

#### HRSA News Feed
- **Endpoint:** HRSA public news and program updates
- **Update Frequency:** Weekly
- **Key Fields:** title, category (funding, policy, clinical), publish_date
- **Purpose:** FQHC-specific program updates and policy guidance

#### State Health Department RSS Feeds
- **Scope:** 50 state health departments + DC
- **Update Frequency:** Weekly
- **Key Fields:** title, state, category (regulation, funding, emergency), publish_date
- **Purpose:** State-level regulatory and policy monitoring

---

## Layer 2: Extraction & Ingestion

### Python Extraction Scripts

Located in `Extraction/` folder:

#### `extract_hrsa.py`
- **Purpose:** Fetch HRSA FQHC registry
- **Input:** HRSA Data Explorer API
- **Output:** Supabase `raw_hrsa_sites` table
- **Logic:** Paginated API calls, duplicate deduplication by site_name, rate limiting (2s between requests)
- **Error Handling:** Connection retry with exponential backoff, progress logging

#### `extract_5500.py`
- **Purpose:** Bulk download Form 5500 filings from DOL
- **Input:** DOL ERISA filing database ZIP archives
- **Output:** CSV file `f_5500_2025_latest.csv`
- **Logic:** Direct DOL bulk ZIP download with fallback to open-data CSV
- **Error Handling:** Retry on network failure, checksum validation

#### `load_5500.py`
- **Purpose:** Parse and load Form 5500 CSV into database
- **Input:** `f_5500_2025_latest.csv`
- **Output:** Supabase `raw_form_5500` table
- **Logic:** Filter rows to healthcare NAICS (621xxx), normalize column names, type casting
- **Error Handling:** Row-level error logging, partial success mode (skip bad rows, log to file)

#### `extract_990.py`
- **Purpose:** Single-org 990 lookup
- **Input:** Organization name, state
- **Output:** ProPublica API JSON response
- **Logic:** API search by name+state, rank by score, return top match

#### `extract_990_bulk.py`
- **Purpose:** Bulk site-based 990 lookup for all HRSA sites
- **Input:** Supabase `raw_hrsa_sites` table
- **Output:** Supabase `raw_990_organizations` table
- **Logic:**
  - Fetch distinct HRSA sites (site_name, state)
  - Normalize site names (whitespace trim, parent org detection for satellites)
  - Call ProPublica API for each site
  - Deduplicate by EIN, check existing records
  - Insert unique rows with raw_json backup
- **Resilience:**
  - `ensure_connection()`: Detect stale DB connections, ping with `SELECT 1`, reconnect on failure
  - `load_progress()` / `save_progress()`: Resume from last site if interrupted
  - Keepalive pings every 50 inserted rows
  - Progress logging every 10 sites processed

### Database Connection

**Supabase PostgreSQL (Phase 0–1)**
- **Host:** db.bnrmplilxdkfdtlscmnb.supabase.co
- **Database:** postgres
- **Schema:** public (all raw tables)
- **Authentication:** User/password credentials in `.env` (never committed)

---

## Layer 3: Data Storage

### Raw Data Schema (Supabase PostgreSQL)

#### raw_hrsa_sites
- **Records:** 18,904
- **Columns:** site_name, state, health_center_type, service_area_pop, loaded_at
- **Indexes:** (site_name, state)

#### raw_form_5500
- **Records:** ~1,570
- **Columns:** plan_name, sponsor_dfe_name, tot_active_partcp_cnt, assets, contributions, loaded_at
- **Indexes:** (sponsor_dfe_name)

#### raw_990_organizations
- **Records:** ~1,500 (in progress)
- **Columns:** ein (PK), name, asset_amount, income_amount, revenue_amount, ntee_code, raw_json, loaded_at
- **Indexes:** (ein), (name)

### Schemas (dbt Multi-Schema Model)

- **staging:** Public staging schema (views for freshness, 1:1 with source)
- **intermediate:** Business layer tables (cleaned, joined, derived columns)
- **enrichment:** Scoring and enrichment tables (health grades, compensation analysis)
- **marts:** Final analytics surfaces (denormalized for dashboards)

---

## Layer 4: Transformation (dbt)

### Project Structure

```
dbt Models/
├── models/
│   ├── staging/
│   │   ├── fqhc/
│   │   │   ├── stg_hrsa_sites.sql (source: raw_hrsa_sites)
│   │   │   └── schema.yml
│   │   └── ...
│   ├── intermediate/
│   │   ├── fqhc/
│   │   │   ├── int_fqhc_profile.sql (peer cohorts)
│   │   │   ├── int_fqhc_retirement_profile.sql (5500 join)
│   │   │   └── schema.yml
│   │   └── ...
│   ├── enrichment/
│   │   ├── e01_plan_health_grade.sql (health score: A–D)
│   │   ├── e02_executive_compensation.sql (Phase 1+)
│   │   ├── e03_news_intelligence.sql (Phase 1+)
│   │   └── schema.yml
│   ├── marts/
│   │   ├── fqhc/
│   │   │   ├── mart_fqhc_intelligence.sql (27,232 rows, dashboard source)
│   │   │   └── schema.yml
│   │   └── ...
│   ├── sources.yml (source definitions)
│   └── ...
├── dbt_project.yml (model config, materializations, tags)
├── packages.yml (dbt dependencies)
└── macros/ (motiv_helpers.sql for org normalization)
```

### Staging Layer

**Purpose:** 1:1 mapping of raw tables; light transformations (type casting, source documentation)

**Example:** `stg_hrsa_sites.sql`
```sql
select
  site_name,
  state,
  health_center_type
from public.raw_hrsa_sites
where state is not null
```

### Intermediate Layer

**Purpose:** Business logic, joins, derived columns

**Key Models:**

1. **int_fqhc_profile**
   - Source: `stg_hrsa_sites` (select * pulls all columns)
   - Derivations:
     - `peer_cohort_state`: state from HRSA
     - `peer_cohort_health_center_type`: health_center_type
     - `peer_cohort_assignment`: concat(state, ' | ', health_center_type)
     - `peer_cohort_id`: dense_rank() over (order by state, health_center_type)
     - `peer_cohort_size`: count(*) over (partition by state, health_center_type)
     - `peer_cohort_size_category`: 'sufficient' if size ≥ var('min_peer_cohort_size', default=5), else 'undersized'
   - Materialization: table
   - Tests: not_null on peer_cohort_state, peer_cohort_health_center_type, peer_cohort_size

2. **int_fqhc_retirement_profile**
   - Sources: `stg_form_5500` (retirement data) + `int_fqhc_profile` (FQHC profiles)
   - Join Logic: Match sponsor_dfe_name or plan_name (normalized via `upper(trim(...))`) to site_name
   - Columns: all from stg_form_5500 + peer cohort columns from int_fqhc_profile
   - Materialization: table

### Enrichment Layer

**Purpose:** Business scoring, derived metrics, behavioral intelligence

**Key Models:**

1. **e01_plan_health_grade**
   - Source: `int_fqhc_profile`
   - Scoring Components:
     - **Cohort Size Score (0–60 points):**
       - ≥50 sites: 60 points
       - ≥20 sites: 45 points
       - ≥10 sites: 30 points
       - ≥min_peer_cohort_size (default 5): 20 points
       - 1–4 sites (undersized): 10 points
       - 0 sites: 5 points
     - **Health Center Type Score (20–40 points):**
       - "Federally Qualified Health Center": 40 points
       - "Community Health Center": 35 points
       - "Rural Health Clinic" or "RHC": 30 points
       - Unknown: 20 points
       - Other: 25 points
   - Composite Score:
     - `raw_score`: sum of both components (max 100)
     - `plan_health_grade_score`: clamp(raw_score, 0–100)
     - `plan_health_grade`: 'A' (≥80), 'B' (65–79), 'C' (50–64), 'D' (<50)
   - Materialization: table
   - Tests: not_null on plan_health_grade

2. **e02_executive_compensation** (Phase 1+)
   - Source: `stg_schedule_j` (parsed from 990 filings)
   - Roles Normalized: CEO, CFO, CMO, CNO, Chief Compliance Officer, Chief Data Officer
   - Derivations:
     - Total compensation by role
     - Peer benchmarking (vs. peer cohort, vs. state, vs. national)
     - Deferred compensation percentage
     - Severance and benefits analysis
   - Materialization: table

3. **e03_news_intelligence** (Phase 1+)
   - Source: `stg_news_events` (parsed from news feeds and Federal Register)
   - AI-Assisted Processing:
     - Categorization: leadership_change, regulatory_update, clinical_milestone, fundraising, merger
     - Sentiment: positive, neutral, negative
     - Relevance scoring (impact on org or industry)
   - Materialization: table

### Marts Layer

**Purpose:** Final denormalized analytics surfaces

**Key Model:**

**mart_fqhc_intelligence**
- **Sources:**
  - `int_fqhc_profile` (profiles and cohort assignments)
  - `int_fqhc_retirement_profile` (retirement plan data, via lateral join)
  - `e01_plan_health_grade` (health score)
  
- **Columns:**
  - site_name
  - state
  - health_center_type
  - peer_cohort_assignment
  - peer_cohort_size_category
  - plan_health_grade
  - tot_active_partcp_cnt (from retirement data)
  
- **Row Count:** 27,232 (Phase 0 Illinois + national sites with profiles)
- **Materialization:** table
- **Indexes:** (site_name, state)
- **Tests:** not_null on site_name, state; unique on (site_name, state)

---

## Layer 5: Intelligence & Analytics

### Peer Cohort Intelligence
- **Definition:** Organizations grouped by state and health center type
- **Metrics:** cohort size, size category (sufficient/undersized), peer member list
- **Application:** Benchmarking, peer comparison, trend analysis

### Health Grade Scoring
- **Input Signals:** Peer cohort size, health center type classification
- **Output:** Single A–D letter grade per organization
- **Use Case:** Quick health assessment for orgs (dashboards, alerts, research)

### Executive Compensation Intelligence (Phase 1+)
- **Input Signals:** Form 990 Schedule J compensation detail, role normalization
- **Output Metrics:** Compensation by role, peer percentile, deferred comp analysis
- **Use Case:** Executive financial wellness, benchmarking, risk profiling

### News & Policy Intelligence (Phase 1+)
- **Input Signals:** News feeds, Federal Register, state health departments
- **Output Metrics:** Event timeline, regulatory impact, peer trends
- **Use Case:** Alerts, policy monitoring, organizational change tracking

---

## Layer 6: Application Layer

### Phase 0 Status
- **Current:** Extraction and transformation pipeline only
- **Database:** Supabase PostgreSQL with raw and modeled tables

### Phase 1 (Planned)
- **Dashboard:** Read-only analytics UI
  - Org profile cards (site_name, state, peer cohort, health grade)
  - Peer comparison charts
  - Health grade distribution
  - News timeline
  
- **Alerts & Monitoring:**
  - Grade changes
  - Peer organization updates
  - Regulatory announcements
  - News mentions

### Phase 3 (Planned)
- **Client-Facing Portal:**
  - Organization profile page
  - Benchmarking dashboard
  - Custom alert configuration
  - Export and reporting
  
- **Behavioral Diagnostic Tools:**
  - Executive Financial Wellness Clinic integration
  - Behavioral Retirement Lab integration
  - Behavioral Cash Flow Intelligence integration
  - Personalized insights and recommendations

---

## Layer 7: Behavioral Science Integration

The platform is architected to feed organizational and leadership data into three proprietary behavioral science programs:

### Executive Financial Wellness Clinic
- **Input:** Executive compensation, retirement readiness, personal financial metrics
- **Process:** Behavioral diagnostic assessment + personalized guidance
- **Output:** Financial wellness recommendations, behavioral change coaching

### Behavioral Retirement Lab
- **Input:** Retirement plan characteristics, deferred compensation profiles, industry trends
- **Process:** Behavioral analysis of retirement decision-making
- **Output:** Organizational retirement strategy recommendations, member engagement tools

### Behavioral Cash Flow Intelligence
- **Input:** Organization cash flow trends, operational patterns, peer benchmarks
- **Process:** Behavioral patterns in financial decision-making
- **Output:** Insights and recommendations for cash flow optimization

### Research Applications
- **Dissertation Layer:** Peer-reviewed research on executive behavior, compensation decisions, organizational outcomes
- **Academic Validation:** Efficacy studies of diagnostic tools
- **Publication Pipeline:** Conference presentations and peer-reviewed journals

---

## Deployment & Operations

### Infrastructure (Phase 0–1)
- **Database:** Supabase PostgreSQL (managed service)
- **Extraction:** Python scripts (local execution via Windows Task Scheduler or VM)
- **Transformation:** dbt Cloud or local CLI
- **Version Control:** GitHub (private repo)

### Phase 2–3 (Planned)
- **Scalability:** Migrate to managed Postgres or BigQuery
- **Orchestration:** dbt Cloud or Apache Airflow
- **CI/CD:** GitHub Actions for dbt compile + test on PR
- **Application Server:** TBD (Flask, FastAPI, or cloud-native)

---

## Data Governance & Security

### Access Control
- Raw tables: dbt service account only
- Staging/intermediate tables: Read access for analysts (dbt cloud)
- Marts & dashboards: Application user role with encryption

### Privacy & Compliance
- Public data only (HRSA, IRS 990, Form 5500, public news)
- No PII retention beyond necessary keys (site_name, ein, executive name on public forms)
- Research layer: Separate schema with privacy-compliant anonymization

### Version Control
- `.gitignore` excludes:
  - `*.csv`, `*.xlsx` (large data files)
  - `dbt Models/target/`, `dbt Models/logs/` (build artifacts)
  - `__pycache__/` (Python cache)
  - `.env` (credentials)
  - `profiles.yml` (dbt config with credentials)

---

## Performance Considerations

### Materialization Strategy
- **Staging:** Views (cheap, always fresh, 1:1 with source)
- **Intermediate:** Tables (enables faster downstream joins)
- **Enrichment:** Tables (scoring computed once)
- **Marts:** Tables (optimized for dashboard queries)

### Indexes
- Primary keys on (ein, site_name, state) in raw/staging tables
- Composite indexes on join keys (site_name, state) in intermediate/marts

### Query Optimization
- Lateral join in mart to avoid full retirement table scan
- Peer cohort window functions computed in intermediate layer (not repeated in enrichment)

---

## References

- **Charter §6:** "Multi-tenant architecture from day one; three-layer model architecture (staging/intermediate/marts); enrichment models versioned and documented."
- **Pre-Launch Memo (May 2):** "FQHC Schema specification; peer cohort assignment methodology; health grade scoring logic."
- **dbt Best Practices:** https://docs.getdbt.com/docs/building-a-dbt-project
- **Supabase PostgreSQL:** https://supabase.com/docs
