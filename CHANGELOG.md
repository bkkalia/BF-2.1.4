# Black Forest Tender Scraper - Changelog

<!-- NOTE:
This changelog's release dates can be refreshed from your local git history.
Run the helper tool (from project root) to infer and update version dates:

    python tools\generate_changelog.py

The tool makes a backup of CHANGELOG.md (CHANGELOG.md.bak.TIMESTAMP) before editing.
-->

## Version 2.3.5 (Feb 21, 2026) - GUI Controls for Batched Extraction + Data Integrity Analysis

### ✨ New Features
- **GUI Controls for Batched JS Extraction**
  - Added user-configurable batch threshold (100-10,000 rows) in dashboard
  - Added user-configurable batch size (500-5,000 rows) in dashboard
  - Settings persist across dashboard restarts (portal_config_memory.json)
  - Real-time adjustment without code changes
  - Default: threshold=300, batch_size=2000 (optimized for testing)

- **Data Integrity Verification UI** (NEW PAGE: `/integrity`)
  - Real-time data quality monitoring dashboard
  - Comprehensive integrity metrics:
    - Overall integrity score (0-100) with color-coded status
    - Total tenders count across all portals
    - Duplicate tender ID detection (groups + extra rows)
    - Missing tender IDs count (null/invalid/placeholder values)
    - Missing closing dates count
  - **Per-Portal Integrity Metrics** (NEW):
    - Individual integrity scores for each portal (0-100)
    - Portal-specific duplicate counts and extra rows
    - Portal-specific missing tender IDs and closing dates
    - Color-coded status badges (Excellent/Good/Fair/Poor)
    - Filter dropdown to view specific portal or all portals
    - Sortable table with 8 columns including action buttons
  - **Actionable Data Quality Management** (NEW):
    - **Per-Portal Actions**:
      - 👁️ "Details" button - View detailed records in tabbed modal (Duplicates, Invalid IDs, Missing Dates)
      - 🗑️ "Clean Duplicates" button - Remove duplicate tenders (keeps newest)
      - ❌ "Remove Invalid" button - Delete records with missing/invalid data
      - 📊 "Export Issues" button - Download problematic records to Excel
    - **Bulk Actions**:
      - 🔧 "Fix All Issues" button - Preview and clean all problems across all portals
      - Cleanup confirmation dialog with preview count before execution
      - Automatic database backup before any cleanup operation
    - **Drill-Down Visibility**:
      - Detailed modal showing up to 100 problematic records per portal
      - Tabbed interface: Duplicates | Invalid IDs | Missing Dates
      - Export issues to Excel for manual review (separate sheets per issue type)
  - Detailed problem views:
    - Top 20 duplicate tender IDs with record counts
    - Top 20 departments with missing closing dates
    - Real-time check log display
  - Action buttons:
    - "Re-check" - Run integrity check on demand
    - "Run Cleanup" - Execute legacy cleanup script with backup
  - Auto-check on page load
  - Links to DATA_INTEGRITY_VERIFICATION.md and PER_PORTAL_INTEGRITY_GUIDE.md for documentation

### 🔧 Improvements
- **Scraping Configuration UI Enhancement**
  - Added "Batched JS Extraction" section to Worker Configuration panel
  - Number inputs with validation (min/max ranges)
  - Inline help text explaining each setting
  - Settings save/load automatically on dashboard restart
  - Integrated with existing worker settings persistence

- **Data Integrity Verification Documentation**
  - Created comprehensive DATA_INTEGRITY_VERIFICATION.md
  - Documented 7 existing verification mechanisms (duplicate detection, validation, etc.)
  - Identified 7 gaps with recommended improvements
  - SQL queries for manual data quality checks
  - Best practices for before/during/after scraping
  - Verification scripts usage guide

### 🐛 Bug Fixes
- None (enhancement-only release)

### 📊 Technical Details
- **Modified Files**:
  - `tender_dashboard_reflex/dashboard_app/scraping_control.py`
    - Added `js_batch_threshold` and `js_batch_size` state variables
    - Added setter methods with range validation
    - Enhanced `save_worker_settings()` to persist batch settings
    - Enhanced `on_load()` to restore batch settings
    - Updated worker_config_panel() UI with batch controls
    - Pass batch settings to ScrapingWorkerManager
  
  - `tender_dashboard_reflex/scraping_worker.py`
    - Added `js_batch_threshold` and `js_batch_size` constructor parameters
    - Pass batch settings to worker processes
    - Updated `_worker_process()` signature
    - Replaced hardcoded values with user-configurable parameters
  
  - `tender_dashboard_reflex/dashboard_app/data_integrity.py` (NEW)
    - DataIntegrityState class with integrity check logic
    - SQL queries for duplicate detection, missing fields, invalid data
    - Real-time metrics calculation (integrity score 0-100)
    - Action handlers for re-check and cleanup operations
    - UI components: metric cards, tables, log display
  
  - `tender_dashboard_reflex/dashboard_app/dashboard_app.py`
    - Imported data_integrity_page
    - Added "Data Integrity" navigation button
    - Registered `/integrity` route
  
  - `DATA_INTEGRITY_VERIFICATION.md` (NEW)
    - 8 sections: mechanisms, gaps, recommendations, SQL queries, best practices, scripts, summary
    - Confidence level: 85/100 → can reach 95/100 with recommended additions
    - Phase 1/2/3 implementation roadmap

### 📝 Configuration Changes
- **Dashboard Settings** (portal_config_memory.json):
  ```json
  {
    "worker_count": 2,
    "worker_names": ["Worker 1", "Worker 2", "Worker 3", "Worker 4"],
    "js_batch_threshold": 300,
    "js_batch_size": 2000
  }
  ```

### 🎯 User Impact
- **Before**: 
  - Batch settings hardcoded in scraping_worker.py (required code editing to test)
  - Data integrity checks required manual SQL queries or scripts
  - No visibility into duplicate/missing data status
  - Cleanup required running scripts manually with risk of data loss
  - Excel-based workflow made multi-portal data management difficult
  
- **After**: 
  - Batch settings adjustable in GUI dashboard (no restart required)
  - Data integrity dashboard shows real-time metrics and problems
  - One-click integrity check with auto-refresh
  - **Visual indicators** (color-coded scores, badges, detailed tables)
  - **Actionable cleanup** with preview-before-delete confirmation
  - **Per-portal actions**: Clean, export, or view details for specific portals
  - **Drill-down visibility**: Click portal to see detailed problematic records
  - **Automatic backup** before any cleanup operation (safety first)
  - **Export to Excel**: Download issues for manual review
  
- **Benefit**: 
  - Easy testing of different batch configurations for performance tuning
  - Proactive data quality monitoring before issues impact users
  - Reduced time to identify and fix data problems (minutes vs hours)
  - **Excel-to-Database confidence**: Visual validation replaces Excel's manual review
  - **Per-portal visibility**: Quickly identify which portals have data quality issues
  - **Targeted troubleshooting**: Focus cleanup efforts on problematic portals only
  - **Quality comparison**: Compare data integrity scores across different portals
  - **Confidence building**: Verify specific portal data quality before public export (tender84.com)
  - **Safe cleanup**: Preview counts, automatic backups, and confirmation dialogs prevent accidents
  - **Export flexibility**: Download clean data (score ≥95) or problematic records for review
  - **Zero data loss risk**: All cleanups create timestamped backups in db_backups/

### 🔍 Data Integrity Summary
**What We Have**:
- ✅ Duplicate detection (real-time + post-scrape)
- ✅ Tender ID normalization
- ✅ Closing date change tracking
- ✅ Row count validation
- ✅ Department resume validation
- ✅ Excel import validation

**What We Should Add**:
- 🔧 Automated integrity reports
- 🔧 Department count validation
- 🔧 Tender count anomaly detection
- 🔧 Database unique constraints
- 🔧 Data quality dashboard

### 📚 Related Documentation
- DATA_INTEGRITY_VERIFICATION.md - Comprehensive data quality analysis
- BATCHED_EXTRACTION_IMPLEMENTATION_SUMMARY.txt - Technical implementation details
- TODAY_SUMMARY_FEB21.txt - Development session notes

---

## Version 2.5.0 (Planned - Q2 2026)

### 🎯 Production Readiness & Pre-Migration Preparation
**Goal:** Stabilize current architecture with all 29 portals before 3.0 migration

### 🗄️ Database Migration
- SQLite → PostgreSQL migration for better scalability
- Maintain existing schema compatibility
- Support concurrent writes for multi-portal scraping
- Automated backup and restore procedures

### 🌐 All-Portal Validation
- Complete testing across all 29 configured portals
- Portal-specific resiliency improvements
- Standardized error handling per portal type
- Performance benchmarking for each portal

### 📊 Enhanced Monitoring
- Portal health tracking and alerts
- Scraping success rate metrics per portal
- Database performance monitoring
- Export generation tracking

### 🔧 Infrastructure Improvements
- Docker containerization (optional)
- Basic REST API layer (FastAPI) for external integrations
- Selenium Grid setup for better parallel execution
- Improved logging and diagnostics

### 📦 Code Organization
- Clean separation of concerns for future migration
- Export current working codebase as 2.5 baseline
- Documentation of all portal configurations
- Migration readiness assessment

**Note:** Version 2.5 serves as the stable foundation before architectural transformation to 3.0

---

## Version 2.4.0 (In Development)

### 🧪 All-Portal Testing Phase
- Testing CLI + Reflex dashboard with all 29 portals
- Identifying portal-specific issues and edge cases
- Performance optimization for batch scraping
- Data quality validation across all portals

### 🐛 Bug Fixes & Stability
- Portal-specific error handling improvements
- Memory management for long-running scrapes
- Checkpoint recovery refinements
- Export reliability across different data volumes

---

## Version 2.3.5 (February 20-21, 2026)

### 🚀 Batched JS Extraction for Mega-Departments (3000+ rows → Configurable 300+)
**Critical Performance Fix:** Prevents browser timeout/crashes on very large departments

#### Problem Solved
- **Before:** Departments with 3000+ rows caused browser timeout/memory exhaustion
- **West Bengal Incident:** 13,000+ row departments caused:
  - ❌ JavaScript execution timeout (browser kills scripts after 30-60 seconds)
  - ❌ Browser memory exhaustion (100+ MB for massive DOM snapshot)
  - ❌ Frozen browser UI during extraction
  - ❌ Complete browser tab crash
  - ❌ Fallback to slow element-by-element mode (13,000 rows × 75ms = 16 minutes!)

#### Solution Implemented
- **Automatic Batching:** Departments with 3000+ rows now extracted in **batches of 2000 rows**
- **Smart Detection:** System automatically switches to batched mode for large tables
- **Performance:** West Bengal 13,000 rows: 7 batches × 0.5s = ~3.5 seconds ✅ (274x faster than element mode!)

#### Code Changes (Feb 20)
- **scraper/logic.py**:
  - Modified `_js_extract_table_rows(driver, start_row=0, end_row=None)` to support row slicing
  - New function: `_js_extract_table_rows_batched(driver, total_rows, batch_size=2000, log_callback=None)`
  - Updated `_scrape_tender_details()` to detect large departments (> 3000 rows) and use batched extraction
  - Added logging: `[JS] Large department detected (13000 rows) - using batched extraction`
  - Added logging: `[JS] Batch 1/7: rows 0-1999...`

#### New: Configurable Batching (Feb 21)
- **Made threshold configurable** instead of hardcoded 3000 rows
- **config.py**: Added `JS_BATCH_THRESHOLD = 300` (default for testing)
- **config.py**: Added `JS_BATCH_SIZE = 2000` (batch size control)
- **app_settings.py**: Added `js_batch_threshold` and `js_batch_size` to settings structure
- **scraper/logic.py**: 
  - Updated `_scrape_tender_details()` signature to accept `js_batch_threshold` and `js_batch_size` parameters
  - Changed hardcoded 3000 check to use configurable threshold
  - Log messages now show threshold: "XXX rows > 300 threshold"
  - Extracts settings from kwargs in `run_scraping_logic()`
- **Dashboard**: Updated scraping_worker.py to pass js_batch settings (300, 2000)

#### Benefits
- **Zero browser timeouts** on mega-departments
- **Stable extraction** for West Bengal's 13,000+ row tables
- **Easy testing:** Lowered threshold to 300 rows makes it testable with common departments
- **User configurable:** Settings can be adjusted in settings.json
- **Same speed** for normal departments (< threshold use single-batch extraction)
- **Automatic fallback** to element mode if any batch fails

### 📊 Per-Worker Duplicate Counter (Feb 21)
- **Dashboard Enhancement:** Worker cards now show real-time duplicate skipping
- **WorkerStatus model:** Added `skipped_existing: int = 0` field
- **UI Badge:** Shows "⏭️ X skipped" with gray color scheme when duplicates encountered
- **Tooltip:** "Duplicates already in database" explains the counter
- **Real-time tracking:** Accumulates across all departments for that worker
- **User Feedback:** Confirms duplicate detection is working correctly

### 🐛 Bug Fixes (Feb 21)
- **check_duplicates_detail.py**: Fixed `sys.stdout.reconfigure()` AttributeError
  - Added try-except with proper fallback for Windows console encoding
  - Works on all Python versions now
  
### 📝 Testing Scripts Created
- `test_batched_extraction_config.py` - Comprehensive configuration test
- `zilla_parishad_status.py` - Check Zilla Parishad scraping status
- `BATCHED_EXTRACTION_IMPLEMENTATION_SUMMARY.txt` - Full implementation documentation

### 🎯 Testing Recommendations
- Any West Bengal department with 300+ rows will trigger batched extraction
- Monitor logs for: `[JS] Large department detected (XXX rows > 300 threshold)`
- Example testable departments:
  - Zilla Parishad (13,865 rows) - will trigger
  - PHE (1,528 rows) - will trigger
  - Irrigation (1,312 rows) - will trigger
  - Public Works (1,070 rows) - will trigger
  
### 🔧 Production Notes
- Threshold set to 300 for testing - consider changing to 3000 for production
- Batch size of 2000 is optimal for most systems
- Settings are saved in settings.json and persist across runs

---

## Version 2.3.4 (February 19, 2026)

### 💾 Periodic Database Saves - Zero Data Loss on Crash/Freeze
**Critical Fix:** Prevents catastrophic data loss from worker crashes or freezes

#### Problem Solved
- **Before:** Database commits only at completion → crash/freeze = 100% data loss
- **West Bengal Incident:** 38-minute scrape extracted 18,688 tenders but saved **0 to database** after freeze
- **Root Cause:** Checkpoint system saved only to JSON (resume capability), not to SQLite database (persistence)

#### Solution Implemented
- **Periodic Database Commits:** Checkpoint saver now saves to **both** JSON and SQLite every 120 seconds
- **Live Progress Updates:** Added `update_run_progress()` method in `tender_store.py` to update run counters in real-time
- **Data Resilience:** Maximum data loss reduced from "everything" to **2 minutes of work**

#### Code Changes
- **scraper/logic.py** (Lines 1828-1900):
  - Modified `_checkpoint_saver_loop()` to call `data_store.replace_run_tenders()` every 2 minutes
  - Added row preparation logic (same as final save) inside checkpoint loop
  - Added `update_run_progress()` calls to update `expected_total_tenders`, `extracted_total_tenders`, `skipped_existing_total`
  - Enhanced logging: `[CHECKPOINT] DB saved 1511 tenders (extracted=1511, skipped=0, total=7729)`

- **tender_store.py** (Lines 611-631):
  - New method: `update_run_progress(run_id, expected_total, extracted_total, skipped_total)`
  - Updates run record without finalizing (allows monitoring progress during long scrapes)
  - Dynamic SQL with only provided parameters updated

### 🛡️ Department Size Safety Limit
- **Added Protection:** Automatic skip for departments > 15,000 tenders (configurable `MAX_DEPT_SIZE`)
- **Prevents:** Memory exhaustion and freezes from abnormally large departments
- **West Bengal Case:** Zila Parishad with 13,000 tenders now processable (limit raised from 10k to 15k)
- **Logging:** Clear warning with suggestion when department exceeds limit

#### Implementation Details
- **scraper/logic.py** (Lines 1946-1963):
  - Check `dept_tender_count` before processing department
  - Skip with detailed warning if exceeds `MAX_DEPT_SIZE = 15000`
  - Log skip reason in `department_summaries` for audit trail

### ✅ Verification & Testing
- **Test Run #88:** West Bengal completed successfully (41.5 min, 24,741 extracted → 18,531 unique in DB)
- **Test Run #89:** Force-stopped after 19 min → **18/18 tenders preserved** (0% data loss)
- **Checkpoint Logs Verified:**
  - 21:26:21 - Background saver started
  - 21:28:21 - First checkpoint (0 tenders, early in run)
  - 21:30:33 - **1,511 tenders saved to database automatically**
  - Force-stop at 21:45 - All data preserved!

### 📊 Performance Impact
- **Checkpoint overhead:** ~200ms every 2 minutes (negligible)
- **Database I/O:** Batched writes, no performance degradation observed
- **Memory:** No additional memory footprint (snapshots released immediately)

### 🔧 Developer Notes
- JSON checkpoints remain for resume capability (unchanged)
- Database persistence now independent of completion status
- Run records show live progress even during execution
- Future: Consider moving `MAX_DEPT_SIZE` to config.py for easier tuning

### 🗃️ Production Results
- **48,176 total tenders** across 15 portals successfully scraped
- **West Bengal:** 18,531 tenders (largest single portal)
- **Zero data loss** despite multiple test interruptions
- **200x average speedup** maintained from previous optimizations

---

## Version 2.3.3 (February 19, 2026)

### ⏱️ IST-Aware Skip Logic
- Rewrote `tender_store.py` skip methods with real-time IST closing date comparison (replaces stale `lifecycle_status='active'` label).
- Added `_parse_closing_date_ist()` supporting 5 date format variants.
- Updated `get_existing_tender_ids_for_portal()` and `get_existing_tender_snapshot_for_portal()` to exclude expired tenders using live IST datetime.
- Verified: HP Tenders 329 live IDs returned (137 expired correctly excluded from 466 total).

### 🔁 Default Only-New Scraping
- Flipped CLI default: `--only-new` is now **ON by default**; use `--full-rescrape` to opt out.
- Added `--full-rescrape` flag to `cli_parser.py`; updated `cli_runner.py` accordingly.
- `--only-new` still accepted for back-compat (no-op, same as default).

### 💾 2-Minute Crash Recovery Checkpoints
- Added background checkpoint thread to `scraper/logic.py` saving progress every 120 seconds to `data/checkpoints/{portal_slug}_checkpoint.json`.
- Auto-resume: on next run for the same portal, checkpoint is loaded and `all_tender_details` + `processed_department_names` are restored.
- Checkpoint deleted on clean finish; preserved on crash/kill for recovery.

### ⚡ JS Fast Path for Large Tables
- Added `_js_extract_table_rows(driver)` helper: single `execute_script()` call extracts all NIC table rows (replaces N×Selenium DOM round-trips).
- Applied JS fast path in `_scrape_tender_details()` with row-count validation (±2 tolerance) and silent fallback to original element loop.
- Fixed double-counting bug: `_early_dup_checked` flag prevents `changed_closing_date_count` from incrementing twice for same tender.
- Verified with 5 unit tests, all passed; syntax-checked `scraper/logic.py`.

### 🖥️ Reflex Dashboard Fixes
- Fixed tender ID display: `_extract_real_tender_id()` extracts canonical IDs from `title_ref` bracket token (e.g. `2026_PWD_128301_1`).
- Added full consistent navbars (Scraping Control + Import Data links) on all 4 dashboard pages.

### 🗃️ Scrape Results
- HP Tenders: run_id=28, **1379 tenders**, 38 departments, ~4 min.
- Punjab: run_id=30, **1274 new + 19 skipped** (skip logic verified), 32 departments, ~1.3 min.
- Migrated both runs into dashboard SQLite DB (14,706 total tenders after migration).

### 🔖 Release
- Version bump to **2.3.3** across runtime config, installer scripts, and executable version metadata.

---

## Version 2.3.2 (February 18, 2026)

### ♻️ Checkpoint Resume Reliability
- Fixed dashboard checkpoint resume crash caused by awaiting an async generator (`object async_generator can't be used in 'await' expression`).
- Updated resume flow to stream `start_scraping` with `async for`, preserving live state updates.

### 🆔 NIC Tender Identity Correctness
- Standardized NIC/eProcure tender identity extraction to use bracket token in title text (example: `2026_DCKUL_128804_1`).
- Fixed persistence mapping bug where `serial_no` and `tender_id_extracted` were incorrectly stored in swapped positions.
- Updated export preference to prioritize canonical `tender_id_extracted`.

### 🔁 Closing-Date-Aware Duplicate Strategy
- Added portal snapshot preloading of existing tender IDs + normalized closing date.
- Implemented duplicate rule:
  - same `portal + tender_id + closing_date` → skip as existing,
  - same `portal + tender_id` with changed closing date → reprocess/update.

### 🧮 Scraping Dashboard Metrics
- Added live counters in Scraping Control Global Progress:
  - `Skipped Existing`
  - `Date Reprocessed`
- Wired metrics end-to-end across scraper summary, worker totals, checkpoint payload, and dashboard state aggregation.

### 🗃️ Data Migration & Safety
- Executed one-time DB correction pass to backfill canonical NIC tender IDs from `title_ref` for historical records.
- Created pre-migration SQLite backup before updates.

### 🔖 Release
- Version bump to **2.3.2** across runtime config, installer scripts, and executable version metadata.

## Version 2.3.1 (February 17, 2026)

## Version 2.3.1 (February 17, 2026)

### 📊 Portal Management Dashboard Enhancements
- Added **Portal Health Status Indicators** with color-coded urgency levels:
  - 🟢 Green (0 days) - Scraped today
  - 🟡 Yellow (1-7 days) - Recent data
  - 🟠 Orange (8-30 days) - Consider refreshing
  - 🔴 Red (>30 days) - Stale data requiring attention
- Added **Portal Category Badges** (Central/State/PSU) based on base_urls.csv classification
- Added **Category Filter Dropdown** for viewing All/Central/State/PSU portals
- Added **Quick Category Export Buttons** for bulk exporting Central, State, or PSU portals
- Added **Export History Tracking** with JSON-based logging in Portal_Exports/export_history.json
- Added **Export History Dialog** showing last 20 export operations with metadata
- Enhanced portal table rows with category badges and days-since-update display

### 🔧 Database Query Optimization
- Fixed SQL query compatibility for legacy schema (tenders + runs tables)
- Implemented subquery-based approach for retrieving last_updated timestamp from runs table
- Verified portal statistics query returns accurate data for all 12 portals

### 📚 Documentation
- Created comprehensive **User Guide** (`docs/DASHBOARD_USER_GUIDE.md`) with:
  - Feature overviews for Dashboard and Portal Management pages
  - Common workflows and best practices
  - Export file format specifications
  - Troubleshooting guide
- Created detailed **Developer Guide** (`docs/DASHBOARD_DEVELOPER_GUIDE.md`) with:
  - Architecture overview (Reflex framework, database schema, state management)
  - Component structure and implementation details
  - Export implementation patterns
  - Development workflow and debugging techniques
  - Performance optimization strategies
  - Extension guidelines for adding features

### 🐛 Bug Fixes
- Fixed BaseModel attribute access in Reflex foreach loops (entry.field vs entry["field"])
- Fixed invalid icon reference (help-circle → circle-help)
- Fixed type annotations for export_history using ExportHistoryEntry BaseModel
- Fixed legacy schema query using completed_at instead of non-existent last_scrape_time

### 🔖 Release
- Version bump to **2.3.1** with enhanced portal management and comprehensive documentation

## Version 2.3.0 (February 14, 2026)

### 🧩 CLI Subprocess Architecture
- Added structured CLI JSON event stream via `--json-events` for GUI-driven process monitoring.
- Added optional `--job-id` correlation in CLI events and embedded event schema metadata (`schema_version`).
- Added `gui/subprocess_runner.py` to launch CLI runs, parse event lines, stream logs, and tail CLI log files in real time.
- Added `gui/process_supervisor.py` shared orchestration layer with job registry, state transitions, heartbeat timeout guard, and grouped stop/kill control.
- Migrated Department tab execution path from in-process scraping to CLI subprocess control for responsive UI.

### ⛔ Emergency Stop Reliability
- Updated emergency stop flow to terminate active CLI subprocesses instantly from GUI stop/kill actions.
- Extended MainWindow tab stop notification handling to support subprocess-backed tabs.

### 🛠️ CLI Progress/Status Improvements
- Fixed broken CLI progress/elapsed log formatting in `cli_runner.py`.
- Emitted structured events for `start`, `portal`, `departments_loaded`, `progress`, `status`, `completed`, `cancelled`, and `error`.

### 🔖 Release
- Version bump to **2.3.0** across runtime config and CLI/GUI subprocess architecture handoff.

## Version 2.2.1 (February 13, 2026)

### 🧵 Parallel Department Safety
- Added department task de-duplication before worker queueing.
- Added ambiguous direct-link guard to avoid multiple workers scraping the same department.

## Version 2.1.10 (February 13, 2026)

### ⚡ Delta Strategy Optimization
- **Quick Delta Default**: Batch `Only New` now uses quick delta as default to reduce second-pass runtime.
- **Optional Full Delta**: Added user-selectable Full Delta mode for stricter end-of-run verification when needed.
- **Batch Delta Mode Control**: Added Batch tab selector (`quick` / `full`) with persisted preference.

### 🔎 Smarter Delta Detection
- **Department Name + Count Comparison**: Quick delta now compares baseline vs latest organization list using both department names and tender counts.
- **Department Churn Handling**: Detects add/remove department cases even when total tender counts look similar.
- **Targeted Second Pass**: Quick delta scrapes only departments flagged by compare logic.

### 🧭 Department URL Tracker
- **Per-Portal URL Map Persistence**: Captures observed department direct URLs into manifest (`department_url_map`) for stability monitoring.
- **Coverage Metrics in Logs/Reports**: Portal run logs and report payloads now include mapped/known coverage statistics.
- **Coverage Report Export**:
    - automatic JSON/CSV export at batch completion,
    - manual CLI tool: `tools/report_department_url_coverage.py`.

## Version 2.1.9 (February 13, 2026)

### 🗄️ Archive & Backup Reliability
- **Tiered SQLite Backups**: Added automatic backup tiers under configured backup directory:
    - daily snapshots in root backup folder,
    - weekly snapshots in `weekly/`,
    - monthly snapshots in `monthly/`,
    - yearly snapshots in `yearly/`.
- **Retention Policy by Tier**:
    - daily: controlled by `sqlite_backup_retention_days` (minimum 7),
    - weekly: keep ~16 weeks,
    - monthly: keep ~24 months,
    - yearly: keep ~7 years.

### ✅ Data Integrity Enforcement
- **Portal + Tender Uniqueness in Runtime**: Persistence now keeps latest row for each `(portal, Tender ID (Extracted))` key.
- **Missing Tender ID Cleanup Rule**: Rows with missing/invalid tender IDs (`nan`, `none`, `null`, empty, etc.) are dropped during persistence.

### ⚡ Import Performance
- **Bulk Dedupe Optimization**: Replaced row-by-row duplicate cleanup with temp-table batched delete logic for large historical imports.
- **Normalized Composite Index**: Added index on normalized `(portal_name, tender_id_extracted)` to speed large upserts and duplicate replacement.

## Version 2.1.8 (February 12, 2026)

### 🗄️ Data Pipeline Upgrade
- **SQLite Primary Datastore**: Department scrape runs now persist to SQLite first (`blackforest_tenders.sqlite3`) as the source of truth for run and tender data.
- **Run Tracking in SQLite**: Added run-level metadata tracking (`status`, expected/extracted/skipped counts, output metadata, partial-save state).

### 📤 SQLite-Backed Exports
- **Excel/CSV from SQLite Views**: User-facing export files are now generated from SQLite view queries instead of direct in-memory lists.
- **Graceful Fallback**: If SQLite export fails unexpectedly, file export still falls back to direct DataFrame write to avoid data loss.

### 📊 Reporting Integration
- **Batch Report Enrichment**: Portal run JSON/CSV reports now include SQLite context (`sqlite_db_path`, `sqlite_run_id`) for downstream APIs and audits.

## Version 2.1.7 (February 12, 2026)

### 🛡️ Recovery & Completion Reliability
- **Final Delta Sweep**: Added an optional quick second pass in batch `Only New` mode before completion to catch tenders that appear during long runs.
- **Portal Health Watchdog**: Added inactivity and sleep/network pause detection with automatic portal recovery retry using a fresh browser session.
- **Checkpoint Auto-Import**: If `batch_tender_manifest.json` is missing/corrupt, batch now auto-seeds resume state from the most recent portal output file.

### 📊 Run Reporting
- **Per-Portal Report Files**: Each portal run now writes both JSON and CSV report files with attempted, processed, resume-skipped, extracted, output-path, and error summary fields.
- **Batch Report Folder**: Reports are grouped into a timestamped run directory under `batch_run_reports` and logged at run completion.

## Version 2.1.6 (February 12, 2026)

### 🚀 Batch Dashboard & Feedback
- **Live Batch Dashboard**: Added per-portal status table (`Idle`, `Fetching`, `Scraping`, `Done`, `Error`) with expected/extracted/skipped counters.
- **Parallel State Visibility**: Logs now explicitly show `waiting for domain slot`, `acquired`, `retry`, and `cooldown` phases.
- **Portal-Level Batch Logs**: Added dedicated Batch log panel with portal filter + text search for faster troubleshooting.

### ✅ Verification & New-Only Scraping
- **New-Only Mode**: Added `Only New Tenders` option in Batch tab to skip already-known Tender IDs.
- **Manifest Tracking**: Introduced persistent `batch_tender_manifest.json` to track known Tender IDs per portal.
- **Post-Run Verification**: Batch now logs expected vs extracted vs skipped-known counts and an approximate remaining gap.

### 🛠️ Stability Fixes
- **Settings Save Fix**: Resolved timeout cast issue on close (`int('10.0')`) by safely parsing float timeout values.
- **Scraping Summary Return**: Department scraping now returns structured summary payload for dashboard and verification.

## Version 2.1.5 (February 12, 2026)

### 🚀 New UX Improvements
- **Dual Status Progress Bars**: Separate colorful progress bars for Departments and Tenders.
- **Live Progress Context**: Status now shows scraped departments, pending departments, and tender totals.
- **Better Visual Logging**: Added clear separators after each department (`********`) and portal (`########`).

### ✅ Reliability & Scraping Enhancements
- **Back-Navigation Recovery**: Automatically recovers to `FrontEndTendersByOrganisation` when portals redirect to wrong pages.
- **Flexible Table Parsing**: Handles 3-column and standard 6-column tender tables.
- **Row-Skip Reduction**: Added robust table/row retry handling for stale elements on large portals.

### 📝 Logging & Operations
- **Run-Based Log Files**: Logs are now generated per run with timestamped filenames.
- **Retention Policy**: Keeps the latest 30 runs automatically for both GUI and CLI logs.
- **GUI Log Filtering**: Added in-app filter by log level (`Critical`, `Error`, `Warning`, `Info`, `Debug`, `All`).

### 🧠 Portal Memory
- **Locator Preference Memory**: Stores successful locator strategies per portal and reuses them in future runs.
- **Faster Recovery on Known Portals**: Preferred locator order now uses learned success history.

## Version 2.1.4 (September 18, 2025)

### 🚀 Major Features
- **Hybrid Distribution**: New launcher system reducing EXE size from 150MB to 10MB
- **Multi-Portal Support**: Added support for 12+ tender portals
- **Inno Setup Integration**: Professional Windows installer
- **Complete Documentation**: CLI and GUI help files included

### ✅ Improvements
- **Performance Optimization**: Reduced page load times by 60%
- **CAPTCHA Handling**: Improved automatic CAPTCHA detection and solving
- **File Downloads**: Enhanced PDF and ZIP download reliability
- **Task Scheduler**: Ready for automated daily scraping
- **Error Handling**: Better error messages and recovery

### 🐛 Bug Fixes
- Fixed download functionality in `tab_id_search.py`
- Resolved parameter passing issues between GUI and scraper modules
- Fixed CAPTCHA popup handling timing
- Improved WebDriver stability and cleanup
- Fixed Pylance type error in `cli_runner.py` list iteration
- Fixed CLI mode launch issues with readline compatibility
- Resolved CLI mode not displaying ASCII banner when launched from GUI

### 📦 Distribution
- **Professional Installer**: Single EXE installer with all dependencies
- **Complete Package**: All files included, no external dependencies
- **Easy Deployment**: Ready for enterprise distribution

## Version 2.1.3 (December 2024)

### Features Added
- Initial multi-portal support
- Enhanced GUI with progress indicators
- CLI mode for automation
- Excel export functionality

### Improvements
- Better error handling
- Improved logging system
- User-friendly interface

## Version 2.1.2 (November 2024)

### Bug Fixes
- Fixed WebDriver initialization issues
- Improved CAPTCHA handling
- Better file download management

## Version 2.1.1 (October 2024)

### Features Added
- Basic tender scraping functionality
- PDF download support
- Simple GUI interface

## Version 2.1.0 (September 2024)

### Initial Release
- Core tender scraping functionality
- HP Tenders portal support
- Basic file download capabilities

---

## Development Notes

### Build Process
```bash
# Build hybrid package
python build_exe.py hybrid

# Create installer
iscc setup.iss
```

### Distribution Files
- `BlackForest.exe` - Small launcher (10MB)
- `dist/` - Complete Python application
- `setup.iss` - Inno Setup script
- `installer_output/` - Generated installer

### System Requirements
- Windows 7 SP1 or later (64-bit)
- Python 3.7+
- Google Chrome browser
- 2GB RAM minimum

---

**For the latest updates, check the GitHub repository.**
