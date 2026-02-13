# Black Forest Tender Scraper - Roadmap

## Baseline (Current)
- Version: **2.2.1**
- SQLite-first persistence active
- Tiered backup policy active (daily/weekly/monthly/yearly)
- Tender integrity rules active (latest per portal+tender ID, missing IDs removed)
- Quick Delta default + optional Full Delta active
- Department URL coverage tracker active (manifest + report export)

## Phase 2 (Near-term)
### 1) Archive Lifecycle
- Introduce explicit live/archive status on persisted tenders.
- Mark/archive tenders older than threshold (for example, closed > 90 days).
- Keep archive queryable without slowing live searches.

### 2) Portal Normalization
- Normalize portal aliases (example: human label vs slug form).
- Standardize stored portal key for stronger dedupe/search consistency.

### 3) Date Normalization
- Parse and store canonical date formats for published/open/closing fields.
- Improve date-range filtering and archive automation reliability.

### 4) Operational Hardening
- Extend portal diagnostics capture (DOM/config snapshots).
- Improve automated recovery paths for changed portal layouts.

## Phase 3 (Mid-term)
### 1) Foundation Schema Parallel Write
- Begin parallel writes to foundation entities:
  - `portals`
  - `scrape_runs`
  - `tender_items`
- Maintain compatibility with current `runs`/`tenders` reads.

### 2) History Tracking
- Add immutable snapshot/status history for tender changes.
- Prepare for future corrigendum-aware monitoring.

### 3) Search Enhancements
- Add high-performance live filters on normalized fields.
- Optional FTS for title/organization keyword search.

## Phase 4 (Future)
### 1) Alerting & Accounts
- User-defined saved filters and alerts.
- Event-driven notifications (new/changed tenders).

### 2) Deep Tender Expansion
- Capture deeper tender details and files metadata.
- Link deep details to canonical portal+tender identity.

### 3) Integration Surface
- Stable export/report interfaces for downstream systems.

## Guiding Principles
- Reliability first over feature volume.
- Backward-compatible migrations.
- Clear observability in logs and reports.
- Centralized data model with predictable retention.

---
Last updated: February 13, 2026
