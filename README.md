# Cloud84 Black Forest Project - Tender Search Utility

Desktop utility for multi-portal government tender scraping, tracking, and export with a centralized SQLite datastore.

## Current Version
- **v2.3.4**

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
- **v2.3.4 (Feb 19, 2026):** Periodic database saves every 2 minutes (zero data loss on crash/freeze), department size safety limits, live progress updates in database.
- **v2.3.3 (Feb 19, 2026):** IST-aware skip logic, default only-new scraping, 2-minute crash recovery checkpoints, JS fast path for large tables, Reflex dashboard fixes.
- **v2.3.2 (Feb 18, 2026):** Checkpoint resume stability fix for async generator flow, NIC tender-ID canonical extraction and DB correction, closing-date-aware duplicate reprocessing, and new live dashboard counters (`Skipped Existing`, `Date Reprocessed`).
- **v2.3.1 (Feb 17, 2026):** Portal management dashboard enhancements with health status indicators, category filters, bulk exports, export history tracking, and comprehensive documentation.
- **v2.3.0 (Feb 14, 2026):** CLI subprocess architecture, emergency stop reliability, structured event streaming.
- **v2.2.1 (Feb 13, 2026):** Parallel department de-duplication and ambiguous direct-link safety guard.
- **v2.1.10 (Feb 13, 2026):** Quick Delta default, optional Full Delta, department name+count delta detection.
- **v2.1.9 (Feb 13, 2026):** Tiered backups, stronger tender ID integrity, import performance upgrades.
- **v2.1.8 (Feb 12, 2026):** SQLite-first persistence and DB-backed exports.
- **v2.1.5 (Feb 12, 2026):** UX progress improvements and portal memory enhancements.

See full history in [CHANGELOG.md](CHANGELOG.md).

## Project Page
- Product webpage: [blackforest_website.html](blackforest_website.html)
- Repository: https://github.com/bkkalia/BF-2.1.4
