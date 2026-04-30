# Black Forest — Government Tender Scraper & Dashboard

> Desktop utility for multi-portal government tender scraping, tracking, and search with a centralized SQLite datastore and real-time Reflex web dashboard.

**Current Version: v2.3.14** | [CHANGELOG](CHANGELOG.md) | [Repository](https://github.com/bkkalia/BF-2.1.4)

---

## What This Does

- Scrapes tender listings across supported NIC government portals (HP Tenders, CPPP, GePNIC, etc.)
- GUI and CLI workflows for operators and automation
- Persists runs and tenders in SQLite — single source of truth
- Real-time search dashboard with live/expired/recent filtering
- Exports to Excel/CSV from persisted data

---

## Project Structure

```
BF 2.1.4/
├── README.md                  ← this file
├── CHANGELOG.md               ← full version history
├── requirements.txt           ← Python dependencies
├── config.py                  ← global configuration
├── main.py                    ← CLI / GUI entry point
├── settings.json              ← user settings
│
├── tender_dashboard_reflex/   ← Reflex web dashboard (port 3000)
│   ├── tender_dashboard_reflex/   ← backend: state.py, db.py
│   └── dashboard_app/             ← UI components
│
├── scraper/                   ← portal scraping engine
├── gui/                       ← desktop GUI (Tkinter)
├── tools/                     ← developer utilities (generate_changelog, etc.)
│
├── docs/                      ← all project documentation
│   ├── README.md              ← documentation index
│   ├── architecture/          ← technical design docs
│   ├── guides/                ← user & developer how-to guides
│   ├── planning/              ← roadmaps & blueprints
│   └── reports/               ← test results & analysis reports
│
├── tests/                     ← automated test suite
├── scripts/                   ← utility scripts (not part of the app)
│   ├── diagnostics/           ← performance benchmarks & DB inspection
│   └── maintenance/           ← cleanup, integrity checks, verification
│
├── database/                  ← SQLite database (gitignored)
├── db_backups/                ← tiered automated DB backups
├── logs/                      ← application logs
└── resources/                 ← images & static assets
```

---

## Core Features

| Feature | Details |
|---------|---------|
| **Batch Multi-Portal Scraping** | Parallel scraping with per-portal run reports and resume logic |
| **Only-New / Resume Logic** | Persistent manifest tracking; skips already-scraped tenders |
| **Tender Integrity** | Deduped by `(portal, Tender ID Extracted)`; drops null/invalid IDs |
| **Reflex Search Dashboard** | Real-time live search with 550ms debounce; full page refresh ~15ms |
| **Live + Recent Filter** | Live tenders + expired within last 30 days (compound-indexed) |
| **Closing Date Index** | Pre-computed `closing_date_iso` TEXT column (ISO format) + compound index `(portal_name, closing_date_iso)` for sub-5ms date-range queries |
| **Excel/CSV Import & Export** | Full round-trip with column mapping and deduplication |
| **Tiered Backups** | Daily / weekly / monthly / yearly with configurable retention policy |
| **Data Integrity Dashboard** | Per-portal integrity scores, duplicate detection, actionable fixes |

---

## Reflex Dashboard

```bash
cd tender_dashboard_reflex
python -m reflex run
# Open http://localhost:3000
```

### Search Performance (v2.3.12)

| Operation | Time |
|-----------|------|
| Full page refresh with keyword search | ~15 ms |
| Portal + date range query (indexed) | ~3–5 ms |
| Global live/expired counts | ~0 ms (120 s cache) |

---

## Running Tests

```bash
# From project root with venv active
python -m pytest tests/ -v
```

See [tests/README.md](tests/README.md) for details.

---

## Utility Scripts

```bash
# Benchmark search performance
python scripts/diagnostics/_bench_search.py

# Check database schema and indexes
python scripts/maintenance/check_db_schema.py

# Remove duplicate rows
python scripts/maintenance/fix_database_duplicates.py
```

See [scripts/README.md](scripts/README.md) for the full list.

---

## Backup & Retention

DB backups go to `db_backups/`:

| Tier | Location | Retention |
|------|----------|-----------|
| Daily | `db_backups/` | 7 days |
| Weekly | `db_backups/weekly/` | 16 weeks |
| Monthly | `db_backups/monthly/` | 24 months |
| Yearly | `db_backups/yearly/` | 7 years |

---

## Version History (Recent)

- **v2.3.14 (Apr 30, 2026):** Reflex Telegram completion message and `#BF_DONE` now use a safe fallback for `new` count: when tenders are scraped and computed unique-new is zero, `new` is reported as total tenders so downstream pipeline AI does not skip execution.
- **v2.3.12 (Apr 23, 2026):** Selenium driver startup reliability fix on Windows — serialized `webdriver.Chrome()` creation to prevent `WinError 32` when multiple workers initialize ChromeDriver concurrently.
- **v2.3.11 (Apr 12, 2026):** Reflex dashboard enhancements — V3 schema portal status fix, settings persistence via on_load wiring, real worker process stop/terminate, portal IP display in worker cards, completion notifications (Telegram bot, cPanel webhook with secret token), post-scrape local script runner with CLI args, all notification features toggle-able with cloud migration guidance.
- **v2.3.10 (Apr 12, 2026):** Portal catalog expansion in `base_urls.csv` including ePublish, BEL, Meghalaya, Mizoram, Nagaland, and Puducherry; CSV keyword field consistency updates.
- **v2.3.9 (Mar 3, 2026):** V3-only database runtime enforcement, portal-scoped KPI summaries, live skipped/extended counter updates, and extended-deadline overcount reduction.
- **v2.3.8 (Mar 2, 2026):** Dashboard scraping control updates — live skipped-tender aggregation fix, milestone notifications/status strip improvements, resume checkpoint robustness, and visuals module isolation under `dashboard_app/visuals/`.
- **v2.3.7 (Feb 26, 2026):** Search performance overhaul — `closing_date_iso` indexed column, merged aggregation query (52ms → 15ms), thread-local DB connections, Live+Recent 30-day filter, project reorganization.
- **v2.3.6 (Feb 22, 2026):** Reflex runtime & type fixes, `rx.select` crash fix, pyrightconfig.
- **v2.3.5 (Feb 21, 2026):** GUI controls for batched JS extraction, data integrity verification UI.
- **v2.3.4 (Feb 19, 2026):** Periodic DB saves every 2 minutes, department size safety limits.
- **v2.3.3 (Feb 19, 2026):** IST-aware skip logic, JS fast path for large portal tables.
- **v2.3.2 (Feb 18, 2026):** Checkpoint resume stability, NIC tender-ID canonical extraction.
- **v2.3.1 (Feb 17, 2026):** Portal management dashboard with health indicators.
- **v2.3.0 (Feb 14, 2026):** CLI subprocess architecture, emergency-stop reliability.

See [CHANGELOG.md](CHANGELOG.md) for full history.

---

## Documentation

See [docs/README.md](docs/README.md) for the complete documentation index.

**Quick links:**
- [Dashboard User Guide](docs/guides/DASHBOARD_USER_GUIDE.md)
- [Dashboard Developer Guide](docs/guides/DASHBOARD_DEVELOPER_GUIDE.md)
- [CLI Reference](docs/guides/CLI_HELP.md)
- [NIC Portal Architecture](docs/architecture/NIC_PORTAL_ARCHITECTURE.md)
- [Roadmap to v2.5](docs/planning/ROADMAP_TO_2.5.md)
- [Testing Guide](docs/guides/TESTING_GUIDE.md)
