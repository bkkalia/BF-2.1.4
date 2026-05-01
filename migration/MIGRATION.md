# Reflex Workflow Migration Guide

Generated on: 2026-04-30

## Purpose
This migration package is the Reflex-first project baseline extracted from the larger BF workspace.
It keeps the code paths required to continue development of the Reflex dashboard and scraper workflow,
while excluding desktop GUI app artifacts and local runtime/build noise.

## Final Deliverable Location
- Final package folder: `migration/reflex_workflow_final/reflex_workflow_core`
- Final archive: `migration/reflex_workflow_final.zip`

## What Was Migrated
### Core Reflex application
- `tender_dashboard_reflex/`
  - Reflex app pages, state, config, and scraping control integration.

### Scraper runtime used by Reflex
- `scraper/`
  - Includes runtime modules used by Reflex workers.
  - Includes `scraper/captcha_handler.py` because `scraper/logic.py` imports it.

### Shared runtime/core modules
- `app_settings.py`
- `config.py`
- `utils.py`
- `tender_store.py`
- `cleanup_service.py`
- `portal_config_memory.py`
- `batch_config_memory.py`
- `ui_message_queue.py`

### Config and data-entry files needed by workflow
- `base_urls.csv`
- `settings.json`
- `portal_config_memory.json`
- `batch_scrape_profiles.json`

### Scripts, tools, and selected docs
- `tools/`
- `scripts/`
- `docs/README.md`
- `docs/guides/`
- `docs/architecture/`
- `docs/planning/`
- Migration/reference docs:
  - `MIGRATION_AGENT_GUIDE.md`
  - `EXPORT_NOTES.md`
  - `SCRAPING_PIPELINE_STEPS.md`
  - `README.md`
  - `CHANGELOG.md`

### Launcher and dependency manifest
- `start_reflex_dashboard.bat`
- `requirements.txt`

## What Was Excluded
### Desktop GUI / legacy entry points
- `main.py` (Tkinter desktop app entry)
- `cli_main.py` (Tkinter dialogs)
- `gui/` package
- Desktop build launcher/installer-oriented files not required for Reflex workflow

### Local/runtime/build artifacts
- `.venv/`
- `.web/`
- `node_modules/`
- `__pycache__/`
- `.states/`
- `build/`, `dist/`
- Other transient cache/output artifacts

## Standardized Package Structure
The final archive contains this top-level shape:

- `reflex_workflow_final/`
  - `reflex_workflow_core/`
    - `tender_dashboard_reflex/`
    - `scraper/`
    - `tools/`
    - `scripts/`
    - `docs/`
    - root `.py` shared modules and config files

## Setup Instructions (New Machine or New Workspace)
Run these steps from inside `reflex_workflow_core`.

1. Install Python 3.11+ (recommended) and Google Chrome.
2. Create a virtual environment.
   - Windows PowerShell:
     - `python -m venv .venv`
     - `.\.venv\Scripts\Activate.ps1`
3. Install dependencies.
   - `pip install -r requirements.txt`
4. If Playwright is used by your workflow, install browser binaries once.
   - `python -m playwright install`
5. Verify required root files are present.
   - `base_urls.csv`
   - `settings.json`
6. Start the Reflex dashboard.
   - `start_reflex_dashboard.bat`
7. Open the printed URL (default host: `blackforest-dashboard.localhost`) in browser.

## Runtime Notes
- SQLite database is created automatically on first run when scraper/data-store initializes.
- Dashboard worker flow and CLI flow may use different default DB locations unless unified in config.
- For long-term maintenance, prefer a single configured SQLite path in settings.

## Recommended Next Step
Create a Phase-2 refactor branch in this migrated package and continue all new features there.
Keep this guide updated whenever modules are added/removed from the Reflex runtime chain.
