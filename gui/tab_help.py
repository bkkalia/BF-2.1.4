import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
import webbrowser
import os

class HelpTab(ttk.Frame):
    def __init__(self, parent, main_app_ref):
        super().__init__(parent)
        self.main_app = main_app_ref
        self._create_widgets()

    def _create_widgets(self):
        # Create notebook for multiple help tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Project Scope & Goal Tab
        self.project_scope = ttk.Frame(self.notebook)
        self.notebook.add(self.project_scope, text="Project Scope & Goal")
        self._create_project_scope()

        # Changelog Tab
        self.changelog = ttk.Frame(self.notebook)
        self.notebook.add(self.changelog, text="Changelog")
        self._create_changelog()

        # End User Help Tab
        self.end_user_help = ttk.Frame(self.notebook)
        self.notebook.add(self.end_user_help, text="End User Help")
        self._create_end_user_help()

        # Roadmap Tab
        self.roadmap = ttk.Frame(self.notebook)
        self.notebook.add(self.roadmap, text="Roadmap")
        self._create_roadmap()

        # Developer Help Tab
        self.dev_help = ttk.Frame(self.notebook)
        self.notebook.add(self.dev_help, text="Developer Help")
        self._create_developer_help()

    def _create_developer_help(self):
        """Create developer help content"""
        # Header
        header = ttk.Label(self.dev_help,
                          text="Developer Documentation",
                          font=self.main_app.heading_font)
        header.pack(pady=10)

        # Create scrolled text widget for developer documentation
        self.dev_text = ScrolledText(self.dev_help,
                                   wrap=tk.WORD,
                                   font=("Consolas", 10),
                                   padx=10, pady=10)
        self.dev_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.dev_text.insert(tk.END, self._get_developer_help_content())
        self.dev_text.config(state=tk.DISABLED)

    def _load_md_file(self, filename):
        """Load content from a markdown file."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error loading {filename}: {e}"

    def _create_project_scope(self):
        """Create project scope content from PROJECT_CONTEXT.md"""
        header = ttk.Label(self.project_scope,
                          text="Project Scope & Goal",
                          font=self.main_app.heading_font)
        header.pack(pady=10)

        text = ScrolledText(self.project_scope,
                           wrap=tk.WORD,
                           font=("Segoe UI", 10),
                           padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        content = self._load_md_file("PROJECT_CONTEXT.md")
        text.insert(tk.END, content)
        text.config(state=tk.DISABLED)

    def _create_changelog(self):
        """Create changelog content from CHANGELOG.md"""
        header = ttk.Label(self.changelog,
                          text="Changelog",
                          font=self.main_app.heading_font)
        header.pack(pady=10)

        text = ScrolledText(self.changelog,
                           wrap=tk.WORD,
                           font=("Segoe UI", 10),
                           padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        content = self._load_md_file("CHANGELOG.md")
        text.insert(tk.END, content)
        text.config(state=tk.DISABLED)

    def _create_end_user_help(self):
        """Create end user help content from GUI_HELP.md"""
        header = ttk.Label(self.end_user_help,
                          text="End User Help",
                          font=self.main_app.heading_font)
        header.pack(pady=10)

        text = ScrolledText(self.end_user_help,
                           wrap=tk.WORD,
                           font=("Segoe UI", 10),
                           padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        content = self._load_md_file("GUI_HELP.md")
        text.insert(tk.END, content)
        text.config(state=tk.DISABLED)

    def _create_roadmap(self):
        """Create roadmap content from ROADMAP.md"""
        header = ttk.Label(self.roadmap,
                          text="Roadmap",
                          font=self.main_app.heading_font)
        header.pack(pady=10)

        text = ScrolledText(self.roadmap,
                           wrap=tk.WORD,
                           font=("Segoe UI", 10),
                           padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        content = self._load_md_file("ROADMAP.md")
        text.insert(tk.END, content)
        text.config(state=tk.DISABLED)

    def _get_developer_help_content(self):
        return """
Black Forest Tender Scraper - Developer Documentation (v2.1.10)
===============================================================

1. Core Architecture
--------------------
Entry and shell:
- `main.py`            : app lifecycle, startup checks, logging bootstrap
- `gui/main_window.py` : tab host, background task orchestration, status/progress hub

GUI tabs:
- `gui/tab_department.py`    : department scraping flow
- `gui/tab_batch_scrape.py`  : batch multi-portal flow
- `gui/tab_refresh_watch.py` : watch rules + change-triggered batch execution
- `gui/tab_id_search.py`     : tender ID-based processing
- `gui/tab_url_process.py`   : direct URL processing
- `gui/tab_settings.py`      : settings and persistence controls

Scraper and persistence:
- `scraper/logic.py`   : extraction orchestration and persistence callbacks
- `tender_store.py`    : SQLite datastore, dedupe, export, backup policy

2. Persistence Model (Current)
------------------------------
SQLite is primary source of truth using:
- `runs` table for run metadata
- `tenders` table for tender rows

Runtime integrity rules:
- keep latest row per `(portal, Tender ID (Extracted))`
- remove missing/invalid tender IDs (`nan`, `none`, `null`, empty, etc.)

3. Backup Model (Current)
-------------------------
Backups are generated in tiers:
- daily in backup root
- weekly in `weekly/`
- monthly in `monthly/`
- yearly in `yearly/`

Retention windows:
- daily = `sqlite_backup_retention_days` (minimum 7)
- weekly ≈ 16 weeks
- monthly ≈ 24 months
- yearly ≈ 7 years

4. Development Workflow Guidelines
----------------------------------
- Keep UI updates thread-safe (use callback pattern from `main_window.py`).
- Preserve backward compatibility in scraper callbacks and summary payloads.
- Prefer root-cause fixes over one-off patches.
- Update Help-tab source docs (`PROJECT_CONTEXT.md`, `GUI_HELP.md`, `ROADMAP.md`, `CHANGELOG.md`) when behavior changes.
- Run `py_compile` checks for touched modules before release commits.

5. Diagnostic Data Notes
------------------------
- `.playwright-mcp/` logs are for portal-change debugging only.
- SQLite remains the business data source for analytics/history.
"""
