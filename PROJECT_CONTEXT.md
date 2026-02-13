# Cloud84 Black Forest Project v2.1.10

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

## Current Architecture (v2.1.10)
- `main.py`: app startup, dependency checks, lifecycle handling.
- `gui/main_window.py`: top-level shell, tabs, status/progress orchestration.
- `gui/tab_department.py`: department-based scraping.
- `gui/tab_batch_scrape.py`: multi-portal batch runs with dashboard.
- `gui/tab_refresh_watch.py`: refresh watch automation with change detection.
- `gui/tab_id_search.py`: tender ID-based lookup flow.
- `gui/tab_url_process.py`: direct URL processing.
- `gui/tab_help.py`: in-app help views from markdown sources.
- `scraper/logic.py`: scraping execution and persistence callbacks.
- `tender_store.py`: SQLite run/tender persistence, dedupe, export, backup policy.

## Data Model and Integrity
Primary SQLite tables:
- `runs`: run metadata and output references.
- `tenders`: persisted tender rows.

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

## Current Status
- Version: 2.1.10
- Branch: `main`
- Central datastore and backup system are active.
- Documentation and website are aligned with latest release.
