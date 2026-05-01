# Documentation Index

All documentation for the Black Forest Tender Scraper project.

## Structure

### `architecture/`
Technical design documents — how components are built and why.

| Document | Topic |
|----------|-------|
| `NIC_PORTAL_ARCHITECTURE.md` | NIC portal DOM structure, scraping strategy |
| `DB_FOUNDATION_PLAN.md` | SQLite schema design and migration strategy |
| `CLI_REFLEX_INTEGRATION_REVIEW.md` | CLI ↔ Reflex dashboard integration design |
| `MIGRATION_GUIDE_FASTAPI_REFLEX.md` | FastAPI → Reflex migration notes |
| `REFACTORING_ANALYSIS.md` | Code refactoring analysis and decisions |
| `TAB_WORKERS_IMPLEMENTATION.md` | Tab-based parallel scraper implementation |
| `UI_QUEUE_IMPLEMENTATION.md` | UI message queue implementation detail |
| `USER_MANAGEMENT_ARCHITECTURE.md` | User/settings management design |

### `guides/`
How-to guides for users and developers.

| Document | Audience |
|----------|----------|
| `DASHBOARD_USER_GUIDE.md` | End users — using the Reflex dashboard |
| `DASHBOARD_DEVELOPER_GUIDE.md` | Developers — extending the dashboard |
| `CLI_HELP.md` | Operators — CLI commands reference |
| `GUI_HELP.md` | Operators — GUI walkthrough |
| `EXCEL_IMPORT_USER_GUIDE.md` | Operators — importing Excel/CSV into DB |
| `DATA_INTEGRITY_ACTIONS_GUIDE.md` | Operators — fixing data quality issues |
| `PER_PORTAL_INTEGRITY_GUIDE.md` | Operators — per-portal integrity checks |
| `AUTO_CLEANUP_GUIDE.md` | Operators — automatic cleanup configuration |
| `INNO_SETUP_GUIDE.md` | Developers — building the installer |
| `TESTING_GUIDE.md` | Developers — running the test suite |
| `SCRAPING_CONTROL_IMPLEMENTATION.md` | Developers — scraping control flow |

### `planning/`
Roadmaps, feature blueprints, and project direction.

| Document | Topic |
|----------|-------|
| `ROADMAP.md` | Short-term feature roadmap |
| `ROADMAP_TO_2.5.md` | Path to v2.5 — major milestones |
| `ENHANCED_PROJECT_BLUEPRINT.md` | Long-term project blueprint |
| `LLM_INTEGRATION_POSSIBILITIES.md` | AI/LLM feature ideas |
| `PROJECT_CONTEXT.md` | Project overview for AI assistants / onboarding |
| `IMPLEMENTATION_SUMMARY.md` | High-level implemented feature summary |

### `reports/`
Analysis reports, test results, and historical notes.

| Document | Topic |
|----------|-------|
| `CRITICAL_FIXES_SUMMARY.md` | Summary of critical bug fixes |
| `DATA_INTEGRITY_VERIFICATION.md` | Data integrity audit results |
| `DATA_QUALITY_ANALYSIS.md` | Data quality metrics analysis |
| `EXPERT_FEEDBACK_ANALYSIS.md` | External expert code review notes |
| `JS_FAST_PATH_ANALYSIS.md` | JS fast path performance analysis |
| `PORTAL_TESTING_PROGRESS.md` | Portal-by-portal testing status |
| `cppp_performance_report.md` | CPPP portal performance report |
| `FINAL_DASHBOARD_TEST_REPORT.md` | Dashboard acceptance test results |
| `EXCEL_DATABASE_COMPATIBILITY_REPORT.md` | Excel import compatibility report |
