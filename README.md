# Cloud84 Black Forest Project - Tender Search Utility

Desktop utility for multi-portal government tender scraping, tracking, and export with a centralized SQLite datastore.

## Current Version
- **v2.1.10**

## What This Tool Does
- Scrapes tender listings by department/organization across supported portals.
- Supports GUI and CLI workflows for operators and automation.
- Persists runs and tenders in SQLite as the primary source of truth.
- Exports user-facing Excel/CSV outputs from persisted data.

## Core Features
- **Batch Multi-Portal Runs** with run dashboard and per-portal reporting.
- **Refresh Watch Automation** to trigger scraping on detected change.
- **Only-New / Resume Logic** with persistent manifest tracking.
- **Tender Integrity Rules**:
  - keep latest row per `(portal, Tender ID (Extracted))`
  - drop missing/invalid tender IDs (`nan`, `none`, `null`, empty, etc.)
- **Large Historical Import Tools** for Excel/CSV consolidation into SQLite.

## Innovations (Recent)
- **SQLite-first pipeline** with run metadata and DB-backed exports.
- **High-volume dedupe optimization** using normalized composite indexing.
- **Tiered backup policy** (daily/weekly/monthly/yearly) with retention windows.
- **Operational resilience** via portal recovery, checkpoint continuity, and mode-based delta strategy.
- **Quick Delta by default** with optional Full Delta for stricter verification.
- **Department URL coverage tracking** with automatic and manual coverage reports.

## Backup & Retention
Configured backup directory receives:
- Daily snapshots in root
- Weekly snapshots in `weekly/`
- Monthly snapshots in `monthly/`
- Yearly snapshots in `yearly/`

Retention policy:
- Daily: `sqlite_backup_retention_days` (min 7)
- Weekly: ~16 weeks
- Monthly: ~24 months
- Yearly: ~7 years

## Version Highlights
- **v2.1.10 (Feb 13, 2026):** Quick Delta default, optional Full Delta, department name+count delta detection, and department URL coverage tracker/reports.
- **v2.1.9 (Feb 13, 2026):** Tiered backups, stronger tender ID integrity, import performance upgrades.
- **v2.1.8 (Feb 12, 2026):** SQLite-first persistence and DB-backed exports.
- **v2.1.7 (Feb 12, 2026):** Delta sweep + health watchdog + checkpoint auto-import.
- **v2.1.6 (Feb 12, 2026):** Batch dashboard, only-new mode, manifest tracking.
- **v2.1.5 (Feb 12, 2026):** UX progress improvements and portal memory enhancements.

See full history in [CHANGELOG.md](CHANGELOG.md).

## Project Page
- Product webpage: [blackforest_website.html](blackforest_website.html)
- Repository: https://github.com/bkkalia/BF-2.1.4
