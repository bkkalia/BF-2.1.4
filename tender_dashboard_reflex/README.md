# Tender Dashboard (Reflex)

Standalone dashboard app for tender data analysis using the existing SQLite database:

- Database (default): `../database/blackforest_tenders.sqlite3`
- Database fallback: `../data/blackforest_tenders.sqlite3`
- Override via env var: `TENDER_DB_PATH=/absolute/path/to/blackforest_tenders.sqlite3`
- UI Framework: Reflex
- Scope: filtering + KPI view + recommendations
- Separate from scraping project/runtime

## Features

- Portal filter + status filter
- State → district → city dependent filters
- Tender type + work type filters
- Date range + amount range + global search
- KPI cards (live/expired/total/filtered/match/dept/due today/due 3-day/due 7-day/data sources)
- Recommendation cards (top portal/state/work type + urgent closures)
- Paginated results

## Run

From workspace root:

1. Install deps:
   - `pip install -r requirements.txt`
2. Start Reflex app:
   - `cd tender_dashboard_reflex`
   - `reflex run`

Default app page is the dashboard in `dashboard_app/dashboard_app.py`.

## Notes

- This app intentionally keeps dashboard analysis separate from scraping workflows.
- Existing Tkinter-based interfaces can remain for scraping until full migration is complete.

## Database Access

- Engine: SQLite (single file DB)
- Login credentials: none (SQLite file-based access)
- Main file in this workspace: `database/blackforest_tenders.sqlite3`

### Connect from another frontend

1. Point your app to the SQLite file path (recommended via `TENDER_DB_PATH`).
2. Use a SQLite driver for your stack:
   - Node.js: `better-sqlite3` / `sqlite3`
   - Python: built-in `sqlite3`
   - Go: `mattn/go-sqlite3`
3. Query table `tenders` (primary dashboard data) and `runs` (run metadata).
4. Keep DB in read-only mode for external analytics UIs when possible.

### Log History

- Scraping Control log history: `logs/reflex_scraping_control.log`
- Import history (success/error events): `logs/reflex_import_history.log`

### Scraping Hero Visuals Module

- Decorative scraping hero visuals are isolated at: `dashboard_app/visuals/scraping_hero_visuals.py`
- Scraping page integration point: `dashboard_app/scraping_control.py`
- Purpose: keep decorative UI effects separate from core scraping state and worker orchestration logic
