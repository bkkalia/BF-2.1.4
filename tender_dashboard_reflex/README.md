# Tender Dashboard (Reflex)

Standalone dashboard app for tender data analysis using the existing SQLite database:

- Database: `../data/blackforest_tenders.sqlite3`
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
