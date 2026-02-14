# BlackForest v3.0 - Enhanced Project Blueprint

**Vision:** Skill-based general scraping platform for government tender portals  
**Goal:** 95%+ automated scraping of 100+ Indian tender portals  
**Timeline:** 6-9 months migration to FastAPI + Reflex architecture

---

## Executive Architecture

### System Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                             │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐       │
│  │  Web Dashboard │  │  Mobile App    │  │  REST API      │       │
│  │  (Reflex)      │  │  (Future)      │  │  (External)    │       │
│  └────────┬───────┘  └────────┬───────┘  └────────┬───────┘       │
└───────────┼──────────────────────┼──────────────────┼──────────────┘
            │                      │                  │
            └──────────────────────┴──────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────┐
│                         API GATEWAY LAYER                           │
│  ┌────────────────────────────────────────────────────────┐        │
│  │             FastAPI Backend (main.py)                  │        │
│  │  - Authentication & Authorization                      │        │
│  │  - Request Routing                                     │        │
│  │  - Rate Limiting                                       │        │
│  │  - WebSocket Management (Real-time Logs)              │        │
│  └────────────────────────────────────────────────────────┘        │
└─────────────────┬───────────────────────┬────────────────────────────┘
                  │                       │
                  ▼                       ▼
┌─────────────────────────────┐  ┌──────────────────────────────────┐
│    CORE SERVICE LAYER       │  │    DATA PERSISTENCE LAYER        │
│                             │  │                                  │
│  ┌──────────────────────┐  │  │  ┌────────────────────────────┐ │
│  │  Portal Manager      │  │  │  │  PostgreSQL Database       │ │
│  │  - CRUD operations   │  │  │  │  - Portals                 │ │
│  │  - Skill assignment  │  │  │  │  - Scraping Runs           │ │
│  └──────────────────────┘  │  │  │  - Tenders                 │ │
│                             │  │  │  - Skills                  │ │
│  ┌──────────────────────┐  │  │  │  - Metrics                 │ │
│  │  Skill Manager       │  │  │  └────────────────────────────┘ │
│  │  - Registry          │  │  │                                  │
│  │  - Hot-loading       │  │  │  ┌────────────────────────────┐ │
│  │  - Testing           │  │  │  │  Redis Cache & Queue       │ │
│  └──────────────────────┘  │  │  │  - Session data            │ │
│                             │  │  │  - Task queue (Celery)     │ │
│  ┌──────────────────────┐  │  │  │  - Rate limit state        │ │
│  │  Schedule Manager    │  │  │  └────────────────────────────┘ │
│  │  - Auto-scheduling   │  │  │                                  │
│  │  - Priority-based    │  │  └──────────────────────────────────┘
│  │  - ML optimization   │  │
│  └──────────────────────┘  │
│                             │
│  ┌──────────────────────┐  │
│  │  Analytics Engine    │  │
│  │  - Tender trends     │  │
│  │  - Performance       │  │
│  └──────────────────────┘  │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    TASK PROCESSING LAYER                            │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │              Celery Distributed Workers                   │    │
│  │                                                             │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │    │
│  │  │ Worker 1 │  │ Worker 2 │  │ Worker 3 │  │ Worker N │ │    │
│  │  │ (High    │  │ (Medium  │  │ (Low     │  │ (...)    │ │    │
│  │  │ Priority)│  │ Priority)│  │ Priority)│  │          │ │    │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │    │
│  │       │             │             │             │         │    │
│  │       └─────────────┴─────────────┴─────────────┘         │    │
│  │                            │                               │    │
│  └────────────────────────────┼───────────────────────────────┘    │
│                               ▼                                    │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │              Task Orchestrator                            │    │
│  │  - Task routing (by priority)                             │    │
│  │  - Retry management                                       │    │
│  │  - Error recovery                                         │    │
│  │  - Progress tracking                                      │    │
│  └───────────────────────────────────────────────────────────┘    │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   SCRAPING EXECUTION LAYER                          │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │              Skill-Based Scraper Engine                   │    │
│  │                                                             │    │
│  │  ┌────────────────────────────────────────────────────┐   │    │
│  │  │         Portal Skill Factory                       │   │    │
│  │  │  - Load skill for target portal                    │   │    │
│  │  │  - Configure rate limits                           │   │    │
│  │  │  - Initialize session                              │   │    │
│  │  └────────────────────────────────────────────────────┘   │    │
│  │                                                             │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │    │
│  │  │ NIC Skill    │ │ Railway Skill│ │ GEM Skill    │      │    │
│  │  │ (Standard)   │ │ (Custom)     │ │ (Custom)     │  ... │    │
│  │  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘      │    │
│  │         │                │                │               │    │
│  │         └────────────────┴────────────────┘               │    │
│  │                          │                                 │    │
│  │                          ▼                                 │    │
│  │  ┌────────────────────────────────────────────────────┐   │    │
│  │  │     Base Portal Skill Interface                    │   │    │
│  │  │  - get_department_list()                           │   │    │
│  │  │  - navigate_to_department()                        │   │    │
│  │  │  - extract_tender_ids()                            │   │    │
│  │  │  - extract_tender_details()                        │   │    │
│  │  │  - detect_changes_fast()                           │   │    │
│  │  └────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────┬─────────────────────────────────┘    │
│                            │                                       │
│                            ▼                                       │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │           Anti-Detection & Rate Limit Layer              │    │
│  │  - Request throttling (portal-specific)                  │    │
│  │  - User-agent rotation                                   │    │
│  │  - Adaptive backoff                                      │    │
│  │  - Circuit breaker                                       │    │
│  │  - Off-peak scheduling                                   │    │
│  └───────────────────────────────────────────────────────────┘    │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    BROWSER AUTOMATION LAYER                         │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │              Selenium Grid (Distributed)                  │    │
│  │                                                             │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │    │
│  │  │ Chrome 1 │  │ Chrome 2 │  │ Chrome 3 │  │ Chrome N │ │    │
│  │  │ (Headless)│ │ (Headless)│ │ (Headless)│ │ (...)    │ │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │    │
│  └───────────────────────────────────────────────────────────┘    │
│                                                                     │
│  Optional: HTTP Client Pool (for simple list pages)               │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │  requests + BeautifulSoup (10-50x faster than Selenium)  │    │
│  └───────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   TARGET: GOVERNMENT PORTALS                        │
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │ NIC      │ │ Railway  │ │   GEM    │ │  State   │   ...       │
│  │ Portals  │ │ Portal   │ │  Portal  │ │ Portals  │   (100+)    │
│  │ (70%)    │ │          │ │          │ │          │             │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘             │
└─────────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MONITORING & OBSERVABILITY                       │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │  Prometheus      │  │  Grafana         │  │  Sentry          │ │
│  │  (Metrics)       │  │  (Dashboards)    │  │  (Error Track)   │ │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Architecture

### 1. Automated Scraping Workflow

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AUTOMATED TRIGGER                                 │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │
│  │  Celery Beat   │  │  Change        │  │  Manual        │        │
│  │  (Schedule)    │  │  Detection     │  │  Trigger       │        │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘        │
└───────────┼───────────────────┼───────────────────┼──────────────────┘
            └───────────────────┴───────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      1. PRE-FLIGHT CHECKS                            │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  • Check portal enabled status                             │     │
│  │  • Verify last scrape time (avoid duplication)             │     │
│  │  • Check rate limit budget                                 │     │
│  │  • Validate circuit breaker open/closed                    │     │
│  │  • Fast change detection (HTTP HEAD request)               │     │
│  └────────────────────────────────────────────────────────────┘     │
│                               │                                      │
│              ┌────────────────┴────────────────┐                    │
│              ▼                                 ▼                     │
│     ┌────────────────┐                ┌────────────────┐            │
│     │  No Changes    │                │  Changes       │            │
│     │  Skip Scrape   │                │  Proceed       │            │
│     └────────────────┘                └───────┬────────┘            │
└───────────────────────────────────────────────┼──────────────────────┘
                                                │
                                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   2. SKILL LOADING & INITIALIZATION                  │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  • Load portal configuration from database                 │     │
│  │  • Get assigned skill (e.g., NIC_STANDARD)                 │     │
│  │  • Initialize skill instance with portal config            │     │
│  │  • Acquire scraping resources (driver from pool)           │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────┬────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   3. DEPARTMENT LIST EXTRACTION                      │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Strategy: Try HTTP first (fast), fallback to Selenium     │     │
│  │                                                              │     │
│  │  HTTP Method (10-50x faster):                               │     │
│  │    • requests.get(org_list_url)                             │     │
│  │    • BeautifulSoup parse table                              │     │
│  │    • Extract dept names, counts, links                      │     │
│  │                                                              │     │
│  │  Selenium Fallback (JS-heavy pages):                        │     │
│  │    • driver.get(org_list_url)                               │     │
│  │    • Wait for table load                                    │     │
│  │    • Extract via DOM queries                                │     │
│  └────────────────────────────────────────────────────────────┘     │
│                               │                                      │
│                               ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Result: List[DepartmentInfo]                              │     │
│  │    - s_no, name, count_text, direct_url                    │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────┬────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   4. SMART DELTA FILTERING                           │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  • Load last scrape department snapshot (from manifest)    │     │
│  │  • Compare department names + counts                       │     │
│  │  • Identify changed departments:                           │     │
│  │    - New departments (not in previous snapshot)            │     │
│  │    - Count changed (more/fewer tenders)                    │     │
│  │    - Removed departments (log only)                        │     │
│  │  • Result: Targeted department list (30-70% reduction)     │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────┬────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│              5. PARALLEL DEPARTMENT PROCESSING                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  For each department (in parallel pool):                   │     │
│  │                                                              │     │
│  │  5.1 Navigate to Department                                 │     │
│  │      • Try direct_url if available                          │     │
│  │      • Fallback: Click department link                      │     │
│  │                                                              │     │
│  │  5.2 Extract Tender IDs (with pagination)                   │     │
│  │      • Loop through all pages                               │     │
│  │      • Collect tender_ids                                   │     │
│  │                                                              │     │
│  │  5.3 Filter Known IDs (if only_new mode)                    │     │
│  │      • Query existing tender_ids from DB                    │     │
│  │      • Skip already-scraped tenders                         │     │
│  │                                                              │     │
│  │  5.4 Extract Tender Details                                 │     │
│  │      For each new tender_id:                                │     │
│  │        • Navigate to tender detail page                     │     │
│  │        • Extract: title, dates, EMD, org chain, etc.        │     │
│  │        • Rate limiting (wait cooldown_seconds)              │     │
│  │        • Save to database (bulk insert)                     │     │
│  │        • Broadcast progress via WebSocket                   │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────┬────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    6. POST-PROCESSING                                │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  • Update scraping run record (status = completed)         │     │
│  │  • Update portal last_scraped_at timestamp                 │     │
│  │  • Save department snapshot for next delta                 │     │
│  │  • Update portal metrics (success/failure counters)        │     │
│  │  • Trigger data quality checks                             │     │
│  │  • Release scraping resources (return driver to pool)      │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────┬────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    7. ALERTING & NOTIFICATIONS                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  • Send summary to monitoring system                       │     │
│  │  • Alert on failures (circuit breaker opened)              │     │
│  │  • Notify on significant tender count changes              │     │
│  │  • Update dashboard metrics                                │     │
│  └────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema Design

### Core Tables

```sql
-- ============================================================================
-- PORTAL & SKILL MANAGEMENT
-- ============================================================================

CREATE TABLE portal_skills (
    id SERIAL PRIMARY KEY,
    skill_name VARCHAR(100) UNIQUE NOT NULL,
    skill_class VARCHAR(200) NOT NULL,  -- Python import path
    skill_file_path TEXT,  -- For hot-loaded custom skills
    version VARCHAR(20),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE portals (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) UNIQUE NOT NULL,
    base_url TEXT NOT NULL,
    org_list_url TEXT NOT NULL,
    skill_id INTEGER REFERENCES portal_skills(id) ON DELETE SET NULL,
    
    -- Classification
    portal_type VARCHAR(50),  -- 'NIC', 'STATE', 'CENTRAL', 'CUSTOM'
    state VARCHAR(100),
    priority VARCHAR(20) DEFAULT 'medium',  -- 'high', 'medium', 'low'
    
    -- Configuration
    rate_limit_rpm INTEGER DEFAULT 30,
    cooldown_seconds INTEGER DEFAULT 2,
    requires_captcha BOOLEAN DEFAULT FALSE,
    requires_login BOOLEAN DEFAULT FALSE,
    enabled BOOLEAN DEFAULT TRUE,
    
    -- Tracking
    last_scraped_at TIMESTAMP,
    last_modified_check TIMESTAMP,
    last_change_detected TIMESTAMP,
    total_scrapes INTEGER DEFAULT 0,
    total_failures INTEGER DEFAULT 0,
    
    -- Flexible config storage
    metadata JSONB,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_portals_enabled ON portals(enabled);
CREATE INDEX idx_portals_priority ON portals(priority) WHERE enabled = TRUE;
CREATE INDEX idx_portals_last_scraped ON portals(last_scraped_at);

-- ============================================================================
-- SCRAPING EXECUTION
-- ============================================================================

CREATE TABLE scraping_runs (
    id SERIAL PRIMARY KEY,
    portal_id INTEGER NOT NULL REFERENCES portals(id) ON DELETE CASCADE,
    
    -- Run metadata
    run_type VARCHAR(50),  -- 'scheduled', 'manual', 'triggered'
    delta_mode VARCHAR(20),  -- 'quick', 'full'
    scope_mode VARCHAR(50),  -- 'all_departments', 'only_new', etc.
    
    -- Timing
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    
    -- Status & Progress
    status VARCHAR(50),  -- 'running', 'completed', 'failed', 'stopped'
    current_department VARCHAR(200),
    progress_percentage REAL DEFAULT 0,
    
    -- Statistics
    total_departments INTEGER DEFAULT 0,
    processed_departments INTEGER DEFAULT 0,
    expected_total_tenders INTEGER DEFAULT 0,
    extracted_total_tenders INTEGER DEFAULT 0,
    skipped_existing_tenders INTEGER DEFAULT 0,
    new_tenders_discovered INTEGER DEFAULT 0,
    
    -- Output
    output_file_path TEXT,
    output_file_type VARCHAR(20),
    
    -- Error tracking
    error_message TEXT,
    error_details JSONB,
    
    -- Metadata
    triggered_by VARCHAR(100),  -- User/system identifier
    worker_id VARCHAR(100),  -- Celery worker ID
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_runs_portal ON scraping_runs(portal_id);
CREATE INDEX idx_runs_status ON scraping_runs(status);
CREATE INDEX idx_runs_started ON scraping_runs(started_at DESC);

-- ============================================================================
-- TENDER DATA
-- ============================================================================

CREATE TABLE tenders (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES scraping_runs(id) ON DELETE CASCADE,
    portal_id INTEGER NOT NULL REFERENCES portals(id) ON DELETE CASCADE,
    
    -- Core identification
    tender_id_extracted VARCHAR(200) NOT NULL,
    department_name VARCHAR(500),
    
    -- Lifecycle
    lifecycle_status VARCHAR(50) DEFAULT 'active',  -- 'active', 'archived', 'cancelled'
    cancelled_detected_at TIMESTAMP,
    cancelled_source VARCHAR(100),
    
    -- Key dates
    published_date VARCHAR(100),  -- Store as text, normalize separately
    closing_date VARCHAR(100),
    opening_date VARCHAR(100),
    
    -- Parsed dates (for querying)
    published_date_parsed DATE,
    closing_date_parsed DATE,
    opening_date_parsed DATE,
    
    -- Tender information
    title_ref TEXT,
    organisation_chain TEXT,
    work_description TEXT,
    location VARCHAR(500),
    
    -- Financial
    emd_amount VARCHAR(100),
    emd_amount_numeric NUMERIC(15, 2),
    tender_value VARCHAR(100),
    tender_value_numeric NUMERIC(15, 2),
    tender_fee VARCHAR(100),
    
    -- Additional fields
    contract_type VARCHAR(100),
    inviting_officer VARCHAR(500),
    inviting_officer_address TEXT,
    
    -- Raw data storage
    tender_json JSONB,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_tenders_run ON tenders(run_id);
CREATE INDEX idx_tenders_portal ON tenders(portal_id);
CREATE INDEX idx_tenders_id_extracted ON tenders(tender_id_extracted);
CREATE INDEX idx_tenders_lifecycle ON tenders(lifecycle_status);
CREATE INDEX idx_tenders_closing_date ON tenders(closing_date_parsed) WHERE closing_date_parsed IS NOT NULL;

-- Composite index for deduplication
CREATE UNIQUE INDEX idx_tenders_portal_id_unique 
ON tenders(portal_id, trim(lower(tender_id_extracted)));

-- Full-text search index (optional)
CREATE INDEX idx_tenders_title_fts ON tenders USING gin(to_tsvector('english', title_ref));

-- ============================================================================
-- DEPARTMENT TRACKING (for delta detection)
-- ============================================================================

CREATE TABLE department_snapshots (
    id SERIAL PRIMARY KEY,
    portal_id INTEGER NOT NULL REFERENCES portals(id) ON DELETE CASCADE,
    run_id INTEGER REFERENCES scraping_runs(id) ON DELETE SET NULL,
    
    department_name VARCHAR(500) NOT NULL,
    department_key VARCHAR(500),  -- Normalized key for matching
    tender_count INTEGER,
    direct_url TEXT,
    
    snapshot_date TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(portal_id, department_key, snapshot_date)
);

CREATE INDEX idx_dept_snapshots_portal ON department_snapshots(portal_id, snapshot_date DESC);

-- ============================================================================
-- METRICS & MONITORING
-- ============================================================================

CREATE TABLE portal_metrics (
    id SERIAL PRIMARY KEY,
    portal_id INTEGER NOT NULL REFERENCES portals(id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,
    
    -- Scraping performance
    scrape_attempts INTEGER DEFAULT 0,
    scrape_success INTEGER DEFAULT 0,
    scrape_failures INTEGER DEFAULT 0,
    avg_duration_seconds REAL,
    
    -- Data metrics
    tenders_discovered INTEGER DEFAULT 0,
    new_tenders INTEGER DEFAULT 0,
    duplicate_tenders INTEGER DEFAULT 0,
    
    -- Health indicators
    captcha_encountered INTEGER DEFAULT 0,
    rate_limit_hits INTEGER DEFAULT 0,
    timeout_errors INTEGER DEFAULT 0,
    
    UNIQUE(portal_id, metric_date)
);

CREATE INDEX idx_portal_metrics_date ON portal_metrics(metric_date DESC);

-- ============================================================================
-- AUDIT & CHANGE TRACKING
-- ============================================================================

CREATE TABLE tender_change_log (
    id SERIAL PRIMARY KEY,
    tender_id INTEGER REFERENCES tenders(id) ON DELETE CASCADE,
    portal_id INTEGER NOT NULL,
    tender_id_extracted VARCHAR(200) NOT NULL,
    
    change_type VARCHAR(50),  -- 'created', 'updated', 'cancelled'
    field_name VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    
    detected_at TIMESTAMP DEFAULT NOW(),
    run_id INTEGER REFERENCES scraping_runs(id)
);

CREATE INDEX idx_change_log_tender ON tender_change_log(tender_id);
CREATE INDEX idx_change_log_date ON tender_change_log(detected_at DESC);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Active tenders view (most common query)
CREATE VIEW v_active_tenders AS
SELECT 
    t.id,
    t.tender_id_extracted,
    t.title_ref,
    t.department_name,
    p.name AS portal_name,
    t.published_date_parsed,
    t.closing_date_parsed,
    t.emd_amount_numeric,
    t.lifecycle_status
FROM tenders t
JOIN portals p ON p.id = t.portal_id
WHERE t.lifecycle_status = 'active'
  AND (t.closing_date_parsed IS NULL OR t.closing_date_parsed >= CURRENT_DATE);

-- Portal health summary
CREATE VIEW v_portal_health AS
SELECT 
    p.id,
    p.name,
    p.priority,
    p.last_scraped_at,
    p.enabled,
    ROUND(
        (p.total_scrapes - p.total_failures)::NUMERIC / NULLIF(p.total_scrapes, 0) * 100,
        2
    ) AS success_rate_percentage,
    COUNT(t.id) AS total_tenders,
    COUNT(t.id) FILTER (WHERE t.lifecycle_status = 'active') AS active_tenders
FROM portals p
LEFT JOIN tenders t ON t.portal_id = p.id
GROUP BY p.id;
```

---

## Technology Stack Details

### Backend Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Web Framework** | FastAPI | 0.109+ | RESTful API, WebSockets, async support |
| **Database** | PostgreSQL | 15+ | Primary data store |
| **ORM** | SQLAlchemy | 2.0+ | Database abstraction |
| **Task Queue** | Celery | 5.3+ | Distributed async tasks |
| **Message Broker** | Redis | 7.0+ | Celery broker + caching |
| **Web Server** | Uvicorn | 0.27+ | ASGI server |
| **Browser Automation** | Selenium | 4.15+ | Portal scraping |
| **HTTP Client** | httpx | 0.26+ | Async HTTP requests |
| **HTML Parsing** | BeautifulSoup4 | 4.12+ | Fast HTML parsing |

### Frontend Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **UI Framework** | Reflex | Python-based reactive web UI |
| **Real-time Updates** | WebSocket | Live log streaming, progress |
| **Charts** | Recharts (via Reflex) | Dashboard visualizations |

### Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Container Platform** | Docker | Application containerization |
| **Orchestration** | Docker Compose | Local multi-container setup |
| **Metrics** | Prometheus | Performance monitoring |
| **Dashboards** | Grafana | Metrics visualization |
| **Error Tracking** | Sentry (optional) | Exception monitoring |

---

## Skill Development Guide

### Creating a New Portal Skill

**Step 1: Analyze Portal Structure**

```python
# tools/portal_analyzer.py
"""
Quick tool to analyze a portal and identify patterns.
"""
import requests
from bs4 import BeautifulSoup

def analyze_portal(url: str):
    """Generate skeleton skill code from portal URL"""
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    print("=== Portal Analysis ===")
    print(f"Title: {soup.title.string if soup.title else 'N/A'}")
    
    # Detect NIC portal
    if "NIC" in str(soup) or "National Informatics Centre" in str(soup):
        print("Portal Type: NIC Standard")
        print("Recommended Skill: NIC_STANDARD")
    
    # Find tables
    tables = soup.find_all('table')
    print(f"Tables found: {len(tables)}")
    for i, table in enumerate(tables[:3]):
        print(f"  Table {i}: id='{table.get('id')}' class='{table.get('class')}'")
    
    # Find forms
    forms = soup.find_all('form')
    print(f"Forms found: {len(forms)}")
    
    # Find links
    links = soup.find_all('a', href=True)
    org_links = [l for l in links if 'organisation' in l.get('href', '').lower() or 'organisation' in l.text.lower()]
    print(f"Organisation links: {len(org_links)}")
    if org_links:
        print(f"  Sample: {org_links[0].get('href')}")
```

**Step 2: Create Skill Class**

```python
# skills/custom_portal_skill.py
from skills.base_skill import BasePortalSkill, PortalConfig, DepartmentInfo, TenderInfo
from selenium.webdriver.common.by import By
import requests
from bs4 import BeautifulSoup

class CustomPortalSkill(BasePortalSkill):
    """
    Skill for [Portal Name]
    Portal URL: [base URL]
    Notes: [Any special handling needed]
    """
    
    # Define portal-specific locators
    DEPT_TABLE_LOCATOR = (By.ID, "custom_table_id")
    TENDER_ID_LOCATOR = (By.XPATH, "//span[@class='tender-id']")
    # ... more locators
    
    def get_department_list(self, driver) -> List[DepartmentInfo]:
        """
        Extract department list.
        Try HTTP first if portal is simple HTML table.
        """
        # Your implementation here
        pass
    
    def navigate_to_department(self, driver, dept: DepartmentInfo) -> bool:
        """Navigate to department tender list"""
        # Your implementation here
        pass
    
    def extract_tender_ids_from_page(self, driver) -> List[str]:
        """Extract tender IDs with pagination"""
        # Your implementation here
        pass
    
    def extract_tender_details(self, driver, tender_id: str) -> Optional[TenderInfo]:
        """Extract tender detail fields"""
        # Your implementation here
        pass
```

**Step 3: Test Skill**

```python
# tests/test_custom_skill.py
import pytest
from skills.custom_portal_skill import CustomPortalSkill
from skills.base_skill import PortalConfig
from selenium import webdriver

@pytest.fixture
def portal_config():
    return PortalConfig(
        name="Custom Portal",
        base_url="https://example.gov.in/app",
        org_list_url="https://example.gov.in/app?page=OrganisationList",
        portal_type="CUSTOM"
    )

@pytest.fixture
def skill(portal_config):
    return CustomPortalSkill(portal_config)

@pytest.fixture
def driver():
    driver = webdriver.Chrome()
    yield driver
    driver.quit()

def test_get_department_list(skill, driver):
    """Test department list extraction"""
    departments = skill.get_department_list(driver)
    assert len(departments) > 0
    assert departments[0].name
    assert departments[0].count_text

def test_extract_tender_ids(skill, driver):
    """Test tender ID extraction"""
    departments = skill.get_department_list(driver)
    if departments:
        skill.navigate_to_department(driver, departments[0])
        tender_ids = skill.extract_tender_ids_from_page(driver)
        assert len(tender_ids) > 0

# Run tests:
# pytest tests/test_custom_skill.py -v
```

**Step 4: Register Skill**

```python
# Via API (hot-load)
curl -X POST http://localhost:8000/api/skills/upload \
  -F "file=@skills/custom_portal_skill.py"

# Or add to registry manually
# skills/registry.py
from skills.custom_portal_skill import CustomPortalSkill

SkillRegistry._skills["CUSTOM_PORTAL"] = CustomPortalSkill
```

**Step 5: Assign to Portal**

```python
# Via API
curl -X PATCH http://localhost:8000/api/portals/123 \
  -H "Content-Type: application/json" \
  -d '{"skill_name": "CUSTOM_PORTAL"}'

# Or via database
UPDATE portals 
SET skill_id = (SELECT id FROM portal_skills WHERE skill_name = 'CUSTOM_PORTAL')
WHERE id = 123;
```

---

## Performance Benchmarks

### Current System (v2.2.1 - Tkinter/SQLite)

| Metric | Value |
|--------|-------|
| Portals supported | ~20-25 |
| Scraping mode | Sequential portals, parallel departments (5 max) |
| Department list fetch | 5-15 seconds (Selenium) |
| Tender detail extraction | 3-5 seconds/tender |
| Throughput | ~500-800 tenders/hour |
| Database | SQLite (single-writer bottleneck) |
| **Portal freshness** | **Manual, 2-4 days** |

### Target System (v3.0 - FastAPI/Reflex/PostgreSQL)

| Metric | Value | Improvement |
|--------|-------|-------------|
| Portals supported | 100+ | **4-5x** |
| Scraping mode | Parallel portals (10+), parallel departments (5/portal) | **10x concurrency** |
| Department list fetch | 0.5-2 seconds (HTTP) / 5-10 sec (Selenium fallback) | **5-10x faster** |
| Tender detail extraction | 2-4 seconds/tender (optimized) | **1.5x faster** |
| Throughput | ~3,000-5,000 tenders/hour | **5-6x faster** |
| Database | PostgreSQL (concurrent writes, partitioning) | **No bottleneck** |
| **Portal freshness** | **Automated, 4-24 hours** | **10x better** |

### Scalability Projections

| Workers | Portals/Day | Tenders/Day | Infrastructure Cost |
|---------|-------------|-------------|---------------------|
| 3 | ~30 | ~50,000 | $50-100/month |
| 10 | ~100 | ~200,000 | $150-250/month |
| 30 | ~300 | ~600,000 | $400-600/month |

---

## Security Considerations

### 1. API Security

```python
# backend/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token for API access"""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Protected endpoints
@app.get("/api/portals", dependencies=[Depends(verify_token)])
def list_portals():
    # Implementation
    pass
```

### 2. Database Security

```python
# Use environment variables for credentials
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str
    
    class Config:
        env_file = ".env"

settings = Settings()

# Never commit .env file
# .gitignore:
# .env
# *.env
```

### 3. Rate Limiting (API Level)

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/runs/start")
@limiter.limit("10/minute")  # Max 10 scraping requests per minute
async def start_scraping_run(request: Request, portal_id: int):
    # Implementation
    pass
```

---

## Monitoring Dashboard Example

### Grafana Dashboard Panels

**Panel 1: Portal Health Overview**
```
Metric: portal_scrape_success_rate{portal="*"}
Visualization: Gauge (0-100%)
Alert: < 80% success rate
```

**Panel 2: Scraping Throughput**
```
Metric: rate(tenders_scraped_total[1h])
Visualization: Graph (tenders/hour over time)
```

**Panel 3: Active Workers**
```
Metric: celery_active_workers
Visualization: Single stat
```

**Panel 4: Queue Depth**
```
Metric: celery_queue_length{queue="scraping"}
Visualization: Graph
Alert: > 100 tasks queued
```

**Panel 5: Error Rate**
```
Metric: rate(scraping_errors_total[5m])
Visualization: Graph with threshold
Alert: > 10 errors/5min
```

---

## Migration Checklist

### Pre-Migration (Weeks 1-2)
- [ ] Review migration guide with team
- [ ] Set up development environment (PostgreSQL, Redis, Docker)
- [ ] Install dependencies (FastAPI, Celery, Reflex)
- [ ] Create SQLAlchemy models from existing schema
- [ ] Write SQLite → PostgreSQL migration script
- [ ] Test migration with sample data

### Phase 1: Backend API (Weeks 3-6)
- [ ] Implement FastAPI basic structure
- [ ] Create portal CRUD endpoints
- [ ] Create tender query endpoints
- [ ] Implement WebSocket log streaming
- [ ] Add authentication/authorization
- [ ] Write API integration tests

### Phase 2: Skill System (Weeks 7-10)
- [ ] Create BasePortalSkill abstract class
- [ ] Implement NICPortalSkill
- [ ] Build SkillRegistry with hot-loading
- [ ] Migrate existing scraping logic to skills
- [ ] Create skill upload API
- [ ] Write skill testing framework

### Phase 3: Task Queue (Weeks 11-14)
- [ ] Configure Celery + Redis
- [ ] Implement scraping tasks
- [ ] Set up Celery Beat scheduling
- [ ] Add retry logic and error handling
- [ ] Implement rate limiting
- [ ] Configure monitoring

### Phase 4: Frontend (Weeks 15-18)
- [ ] Build Reflex dashboard
- [ ] Implement portal management UI
- [ ] Create skill upload interface
- [ ] Add real-time log viewer
- [ ] Build tender search/export UI
- [ ] Implement scheduler configuration

### Phase 5: Migration & Parallel Run (Weeks 19-22)
- [ ] Migrate production database
- [ ] Import all portal configurations
- [ ] Run both systems in parallel
- [ ] Data consistency validation
- [ ] Performance benchmarking
- [ ] Fix discrepancies

### Phase 6: Cutover (Weeks 23-26)
- [ ] Gradual portal migration
- [ ] Monitoring dashboard live
- [ ] Alert rules configured
- [ ] Performance optimization
- [ ] Decommission old system
- [ ] Team training on new system

---

## Success Criteria

### Technical Metrics
- ✅ 100+ portals actively scraping
- ✅ <24 hour data freshness for high-priority portals
- ✅ 95%+ automation (minimal manual intervention)
- ✅ 90%+ scraping success rate
- ✅ <5 minute incident response time
- ✅ Zero data loss during migration

### Business Metrics
- ✅ 500,000+ tenders/year tracked
- ✅ 70%+ NIC portal coverage (India-wide)
- ✅ New portal onboarding <1 day (with existing skill)
- ✅ Custom skill development <1 week
- ✅ System uptime >99.5%

### Operational Metrics
- ✅ Infrastructure cost <$500/month for 100 portals
- ✅ 95% reduction in manual scraping runs
- ✅ 80% reduction in maintenance time
- ✅ Real-time visibility into all scraping operations

---

## Conclusion

This blueprint transforms BlackForest from a **desktop scraping tool** into a **production-grade scraping platform** capable of:

🎯 **Scaling horizontally** to handle 100+ portals  
🎯 **Automating 95%+** of scraping operations  
🎯 **Maintaining freshness** of 500k+ tenders annually  
🎯 **Skill-based architecture** for rapid portal addition  
🎯 **Anti-detection strategies** to avoid bans  
🎯 **Modern tech stack** (FastAPI, Reflex, PostgreSQL, Celery)  
🎯 **Production monitoring** with alerts and dashboards  

**Timeline:** 6-9 months  
**Investment:** ~$100-500/month infrastructure  
**ROI:** 10x capacity, 95% automation, zero manual runs  

Ready to build the future of government tender intelligence! 🚀
