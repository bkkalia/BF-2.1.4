# Black Forest Tender Scraper - Changelog

<!-- NOTE:
This changelog's release dates can be refreshed from your local git history.
Run the helper tool (from project root) to infer and update version dates:

    python tools\generate_changelog.py

The tool makes a backup of CHANGELOG.md (CHANGELOG.md.bak.TIMESTAMP) before editing.
-->

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
