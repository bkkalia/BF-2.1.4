# Database Foundation Plan (Tender84 / BlackForest)

## 1) Design Goals

- Portal-first query performance for live tenders.
- Minimal disruption to current scraper flow (department-list level scraping + URLs).
- Future-safe model for:
  - detailed tender attributes,
  - accounts and alert rules,
  - historical status tracking,
  - adsupported read-heavy traffic.
- Clear archive handling without slowing live search.
- Centralized single DB with daily backup to secondary location.

## 2) Recommended Core Model

Use one central SQLite database with normalized tables and strong indexing:

- `portals`: master portal metadata (`portal_slug`, `portal_code`, active flag, source file).
- `scrape_runs`: ingestion audit trail per portal run.
- `tender_items`: canonical latest record per portal tender (`UNIQUE(portal_id, portal_tender_uid)`).
- `tender_snapshots`: immutable snapshots per run (history and audit).
- `tender_status_history`: explicit status transitions.
- `tender_files`: future file metadata (NIT/BOQ/etc).
- `user_alert_rules`: future alert-ready structure.
- `backup_log`: daily backup run tracking.

Views:
- `v_live_tenders` for hot-path search.
- `v_archive_tenders` for low-frequency archive/expired lookups.

Search:
- FTS5 table (`tender_search_fts`) with triggers for keyword queries.

## 3) Why This Fits Your Use Case

### Current stage
You currently store list-level tender information and URLs, not full downstream detail extraction. The schema keeps those fields first-class while leaving nullable placeholders for future details.

### Live-heavy queries
Most searches are portal-specific and live-only. Indexes are centered on:
- `(portal_id, is_live, closing_at)`
- `(portal_id, tender_status, closing_at)`
- amount range (`estimated_cost_value`, `emd_amount_value`)
- geography (`state_code`, `district`, `city`, `pincode`)
- work segmentation (`work_type`, `tender_type`, `payment_type`)

### Archive strategy
Expired tenders are not deleted. Mark as `is_live=0`, set `closed_at` and optional `archived_at`. This keeps history accessible while live queries stay fast.

## 4) Central DB + Backup Policy

### Central DB path (recommended)
Use one fixed database path across all runs, for example:
- `%APPDATA%/BlackForest/blackforest_tenders.sqlite3`
or
- project-defined absolute path in settings.

Do **not** derive DB path from download folder.

### Tiered backup (implemented)
Current runtime now writes backups to the configured backup directory in four tiers:

- Daily snapshots in the backup root:
  - `blackforest_tenders_YYYYMMDD.sqlite3`
- Weekly snapshots in `weekly/`:
  - `blackforest_tenders_YYYYWww.sqlite3`
- Monthly snapshots in `monthly/`:
  - `blackforest_tenders_YYYYMM.sqlite3`
- Yearly snapshots in `yearly/`:
  - `blackforest_tenders_YYYY.sqlite3`

Retention now follows:
- daily: `sqlite_backup_retention_days` (minimum 7),
- weekly: ~16 weeks,
- monthly: ~24 months,
- yearly: ~7 years.

This tiered policy improves recovery points while keeping long-term archive protection.

## 5) Migration Path from Current `runs/tenders`

### Phase 1 (safe, no feature break)
- Keep existing scraper outputs unchanged.
- Add new schema (`database/schema_foundation_v1.sql`).
- Start writing `portals`, `scrape_runs`, and `tender_items` in parallel with current tables.

### Phase 2
- Upsert into `tender_items` by `(portal_id, portal_tender_uid)`.
- Insert per-run immutable rows into `tender_snapshots`.
- Add status change entries into `tender_status_history`.

### Phase 3
- Switch exports/search reads to `v_live_tenders` and optional FTS search.
- Gradually deprecate legacy `tenders` table usage.

## 6) Portal Code Notes

Your portal codes are not strictly ISO-only; they are mixed:
- state-like (`HP`, `PB`, `RJ`, etc.)
- domain-like (`DEFENCE`, `EPROCURE`, `ETENDERS`, `HSL`)

Hence store both:
- `portal_slug` (route key, e.g. `hp`, `defence`)
- `portal_code` (from frontend config `stateCode`)

This prevents future mismatches and supports routing + analytics cleanly.

## 7) Query Examples (Target Patterns)

### Live tenders, single portal, date range
```sql
SELECT *
FROM v_live_tenders
WHERE portal_slug = 'hp'
  AND closing_at >= '2026-02-01'
  AND closing_at < '2026-03-01'
ORDER BY closing_at ASC;
```

### Amount + location + work keyword
```sql
SELECT *
FROM v_live_tenders
WHERE state_code = 'HP'
  AND district = 'Una'
  AND estimated_cost_value BETWEEN 500000 AND 2000000
  AND work_type LIKE '%road%'
ORDER BY closing_at ASC;
```

### Global keyword search via FTS
```sql
SELECT ti.*
FROM tender_search_fts f
JOIN tender_items ti ON ti.id = f.rowid
WHERE tender_search_fts MATCH 'digital signature'
  AND ti.is_live = 1
ORDER BY ti.closing_at ASC;
```

## 8) Capacity Expectation

For your forecast (50 portals * ~5000 live records = ~250k live rows), SQLite with WAL and the included indexes is suitable.

10M+ total historical rows is possible in SQLite, but monitor:
- index growth,
- backup duration,
- VACUUM/maintenance windows,
- read latency on global searches.

If/when multi-user writes + account alerts become highly concurrent, migrate to PostgreSQL with the same logical schema.

## 9) Deliverables Added

- SQL foundation schema: `database/schema_foundation_v1.sql`
- This design plan: `docs/DB_FOUNDATION_PLAN.md`

