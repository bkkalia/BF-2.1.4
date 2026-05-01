# Reflex Scraper Migration Guide for AI Agents

## Purpose
This package is a clean starting point to build the next version of the Reflex-based scraper.
It intentionally excludes legacy desktop GUI code and local environment artifacts.

## Migration Goals
- Keep only Reflex dashboard and scraper automation logic.
- Remove Tkinter and other desktop-UI dependencies.
- Keep core scripts, docs, and configuration needed for further development.
- Provide clear ownership of files so AI agents can make safe edits.

## What Was Removed
- Legacy desktop app entry points: main.py, cli_main.py
- Desktop GUI package: gui/
- Captcha UI helper: scraper/captcha_handler.py
- Any Python file importing tkinter, PyQt, or PySide
- Runtime/build/cache artifacts, virtual environments, logs, and temp output folders

## High-Level Architecture
1. Reflex app layer
- Location: tender_dashboard_reflex/
- Responsibility: dashboard pages, state-driven UI, and orchestration hooks to scraping workers.

2. Scraper engine layer
- Location: scraper/
- Responsibility: browser setup, tender extraction flow, actions, tab/session handling, and download behavior.

3. Worker and orchestration layer
- Primary files: tender_dashboard_reflex/scraping_worker.py, cli_runner.py, cli_parser.py
- Responsibility: run jobs, connect UI/CLI inputs to scraper engine, stream progress.

4. Data/config utility layer
- Primary files: app_settings.py, config.py, batch_config_memory.py, portal_config_memory.py, tender_store.py, cleanup_service.py, utils.py, ui_message_queue.py
- Responsibility: settings, persistence helpers, cleanup, and shared utilities.

## File Responsibility Map
### Reflex dashboard core
- tender_dashboard_reflex/rxconfig.py
  - Reflex app configuration.
- tender_dashboard_reflex/tender_dashboard_reflex/state.py
  - Main state classes and event handlers used by dashboard pages.
- tender_dashboard_reflex/dashboard_app/dashboard_app.py
  - Main dashboard composition and routing.
- tender_dashboard_reflex/dashboard_app/scraping_control.py
  - Scraping control UI and actions that call worker logic.
- tender_dashboard_reflex/scraping_worker.py
  - Background worker manager linking dashboard actions to scraper engine.

### Scraper core
- scraper/logic.py
  - Core scraping workflows and extraction pipeline.
- scraper/playwright_logic.py
  - Playwright-based data collection helpers.
- scraper/driver_manager.py
  - Browser driver lifecycle and download directory setup.
- scraper/tab_manager.py
  - Multi-tab/browser-session handling.
- scraper/actions.py
  - Low-level page actions and safe extraction utilities.
- scraper/webdriver_manager.py
  - WebDriver helper abstractions.
- scraper/ocr_helper.py
  - OCR-related helper methods.
- scraper/sound_helper.py
  - Optional sound notifications (non-UI desktop GUI independent).

### CLI and shared runtime
- cli_parser.py
  - CLI argument definitions and parsing.
- cli_runner.py
  - CLI flow execution and scrape invocation.
- app_settings.py
  - App-level configuration constants and defaults.
- config.py
  - Runtime config loading and compatibility helpers.
- batch_config_memory.py
  - Batch scraping configuration persistence.
- portal_config_memory.py
  - Portal configuration persistence.
- tender_store.py
  - Tender data persistence and retrieval helpers.
- ui_message_queue.py
  - Message queue bridge used by orchestrators.
- cleanup_service.py
  - Cleanup routines for stale temp/runtime artifacts.
- utils.py
  - Shared utility functions across modules.

### Scripts and docs
- scripts/
  - Diagnostics and maintenance scripts for development support.
- docs/
  - Project documentation and references.
- README.md
  - Main project context and usage overview.
- CHANGELOG.md
  - Historical changes and release notes.

## Recommended Development Entry Points
1. Dashboard-first workflow
- Start from tender_dashboard_reflex/dashboard_app/scraping_control.py and tender_dashboard_reflex/scraping_worker.py.
- Trace into scraper/logic.py for extraction behavior.

2. Engine-first workflow
- Start from scraper/logic.py and scraper/playwright_logic.py.
- Validate driver/session behavior in scraper/driver_manager.py and scraper/tab_manager.py.

3. CLI-first workflow
- Start from cli_parser.py and cli_runner.py.
- Ensure parity with dashboard-triggered scraping behavior.

## AI Agent Guardrails for This Migration
- Do not reintroduce tkinter, PyQt, or PySide imports.
- Keep GUI-desktop assumptions out of scraper and worker code.
- Prefer extending worker APIs and state events rather than adding hidden side effects.
- Keep config changes centralized in config.py, app_settings.py, and memory helper modules.
- Maintain backward-safe interfaces for scraper/logic.py unless intentional refactor is planned.

## First Tasks for New Version
1. Define target architecture for scraping modes (Selenium only, Playwright only, or hybrid).
2. Normalize worker events and progress payload schema.
3. Add focused tests around scraper/logic.py and scraping_worker.py integration.
4. Introduce explicit interfaces for portal adapters if multi-portal support is expanding.

## Verification Checklist
- No desktop GUI imports present.
- Dashboard controls can trigger scraping worker.
- Worker can execute scraping flow with current config modules.
- Scripts and docs are available for debugging and migration support.
