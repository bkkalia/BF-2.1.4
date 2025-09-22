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
Black Forest Tender Scraper - Developer Documentation
=================================================

1. Project Structure
-------------------
/BF 2.1.4/
├── gui/                 # GUI components
│   ├── main_window.py  # Main application window
│   ├── tab_*.py        # Individual tab implementations
│   └── gui_utils.py    # Shared GUI utilities
├── scraper/            # Core scraping logic
│   ├── logic.py        # Main scraping implementation
│   ├── actions.py      # Low-level Selenium actions
│   └── driver_manager.py # WebDriver management
├── config.py           # Configuration constants
├── main.py            # Application entry point
└── requirements.txt   # Dependencies

2. Dependencies
--------------
Core:
- selenium: Web automation
- undetected-chromedriver: Browser automation
- PyPDF2: PDF processing
- pytesseract: OCR capability
- Pillow: Image processing

Development:
- debugpy: Debugging support
- black: Code formatting
- pylint: Code analysis

3. Module Overview
-----------------
main.py:
- Application entry point
- Dependency checks
- Error handling
- GUI initialization

gui/main_window.py:
- Main window management
- Tab coordination
- Settings management
- Progress tracking

scraper/logic.py:
- Core scraping implementation
- Data extraction
- File downloads
- Error handling

scraper/actions.py:
- Selenium action wrappers
- Reliable element interaction
- Download management
- Safety checks

4. Key Classes
-------------
MainWindow:
- Main application window
- Settings management
- Background task handling
- Progress updates

DepartmentTab:
- Department list management
- Scraping initiation
- Progress tracking

IdSearchTab:
- ID input management
- Multiple import methods
- Search coordination

5. Function Interactions
-----------------------
start_background_task:
- Called by tabs to initiate scraping
- Creates WebDriver instance
- Manages threading
- Handles callbacks

search_and_download_tenders:
- Core scraping function
- Called by background tasks
- Manages downloads
- Reports progress

update_progress:
- Thread-safe progress updates
- Called by scraping functions
- Updates UI elements
- Handles time estimates

6. Development Guidelines
------------------------
- Use thread-safe operations for UI updates
- Implement proper error handling
- Follow existing naming conventions
- Document new features
- Test thoroughly with different inputs
"""
