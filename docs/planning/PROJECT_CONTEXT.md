# Cloud84 Black Forest Project v2.3.3

## Project Overview
Black Forest is a Python desktop application for scraping and managing government tender listings across multiple portals.

It focuses on:
- reliable multi-portal extraction,
- operator-friendly GUI + CLI workflows,
- centralized SQLite persistence,
- robust backups and historical usability.

## Technology Stack
- Language: Python 3.10+
- GUI: Tkinter
- Scraping: Selenium WebDriver
- Data processing: pandas, openpyxl
- Datastore: SQLite (primary source of truth)
- Packaging: PyInstaller + Inno Setup

## Current Architecture (v2.3.3)
- `main.py`: app startup, dependency checks, lifecycle handling.
- `gui/main_window.py`: top-level shell, tabs, status/progress orchestration.
- `gui/tab_department.py`: department-based scraping.
- `gui/tab_batch_scrape.py`: multi-portal batch runs with dashboard.
- `gui/tab_refresh_watch.py`: refresh watch automation with change detection.
- `gui/tab_id_search.py`: tender ID-based lookup flow.
- `gui/tab_url_process.py`: direct URL processing.
- `gui/tab_help.py`: in-app help views from markdown sources.
- `scraper/logic.py`: scraping execution, persistence callbacks, 2-min checkpoint system, JS fast path for large NIC tables.
- `tender_store.py`: SQLite run/tender persistence, IST-aware dedupe, export, backup policy.

## Data Model and Integrity
Primary SQLite tables:
- `runs`: run metadata and output references.
- `tenders`: persisted tender rows.

### NIC Portal Tender ID Canonical Rule
- On NIC/eProcure "Tenders By Organisation" pages, Tender ID is the bracket token embedded in title text (example: `2026_DCKUL_128804_1`).
- Per NIC portal, Tender ID is unique at portal scope.
- Canonical identity key is `(portal_name, tender_id_extracted)`.
- Closing date can be extended/changed for the same tender ID; this should trigger reprocessing/update, not new identity creation.

Current integrity behavior:
- keeps latest row per `(portal, Tender ID (Extracted))`.
- removes missing/invalid tender IDs (`nan`, `none`, `null`, empty, etc.).
- allows same tender ID across different portals.

## Backup Strategy (Implemented)
Backups are generated under configured backup directory in tiers:
- Daily: root backup folder
- Weekly: `weekly/`
- Monthly: `monthly/`
- Yearly: `yearly/`

Retention:
- daily = `sqlite_backup_retention_days` (min 7),
- weekly ≈ 16 weeks,
- monthly ≈ 24 months,
- yearly ≈ 7 years.

## User-Facing Capabilities
- Department scraping with progress visibility.
- Batch mode (sequential/parallel) with only-new and resume behavior.
- Delta mode control with **Quick** (default) and **Full** options.
- Quick delta compare using department names + counts for targeted second pass.
- Refresh watch with event history and export.
- Explicit persistence logging (SQLite path + output path).
- Excel/CSV outputs generated from persisted run data.
- Department URL coverage tracking and report export (auto + manual).

## Skip / Duplicate Logic (v2.3.3)
- `--only-new` is **ON by default** in CLI; use `--full-rescrape` to disable.
- `tender_store.py` performs IST-aware closing date comparison: a tender is considered "live" only if its closing date > `now(IST)`.
- Same `portal + tender_id + closing_date` → skipped; same `portal + tender_id` with changed closing date → reprocessed.

## Crash Recovery (v2.3.3)
- `scraper/logic.py` runs a background thread saving checkpoint JSON every 120 seconds to `data/checkpoints/{portal_slug}_checkpoint.json`.
- On next run for same portal, checkpoint is auto-loaded; scraping resumes from saved `all_tender_details` + `processed_department_names`.
- Checkpoint deleted on clean finish; preserved on crash/kill.

## Performance (v2.3.3)
- `_js_extract_table_rows(driver)`: single `execute_script()` extracts all rows from NIC `#table` — replaces N×Selenium DOM round-trips for large departments.
- Falls back to original element-loop on any JS failure.

## Current Status
- Version: 2.3.3
- Branch: `main`
- Central datastore and backup system are active.
- Documentation and website are aligned with latest release.
