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
        # Create notebook for User/Developer tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # User Help Tab
        self.user_help = ttk.Frame(self.notebook)
        self.notebook.add(self.user_help, text="User Guide")
        self._create_user_help()

        # Developer Help Tab
        self.dev_help = ttk.Frame(self.notebook)
        self.notebook.add(self.dev_help, text="Developer Guide")
        self._create_developer_help()

    def _create_user_help(self):
        """Create user help content"""
        # Header
        header = ttk.Label(self.user_help, 
                          text="Black Forest Tender Scraper - User Guide",
                          font=self.main_app.heading_font)
        header.pack(pady=10)

        # Create scrolled text widget for user documentation
        self.user_text = ScrolledText(self.user_help, 
                                    wrap=tk.WORD, 
                                    font=("Segoe UI", 10),
                                    padx=10, pady=10)
        self.user_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.user_text.insert(tk.END, self._get_user_help_content())
        self.user_text.config(state=tk.DISABLED)

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

    def _get_user_help_content(self):
        return """
Black Forest Tender Scraper - User Guide
======================================

1. Getting Started
-----------------
- Install required dependencies using requirements.txt
- Launch the application
- Configure download directory in Settings tab

2. Scraping Methods
------------------
a) By Department:
   - Select departments from the list
   - Click "Fetch Departments" to update
   - Select desired departments
   - Click "Start Scraping" to begin

b) By Tender ID:
   - Enter or paste tender IDs
   - Import IDs from:
     * Image (screenshot)
     * Excel file
     * Text file
     * PDF file
   - Click "Start Search by ID"

c) By Direct URL:
   - Enter tender URLs directly
   - Click "Process URLs"

3. Settings
----------
- Download Directory: Where files are saved
- Portal Selection: Choose tender portal
- Advanced Options:
  * Deep Scrape
  * Download Options
  * Theme Selection
  * Browser Options

4. Features
----------
- Multi-threaded scraping
- Progress tracking
- Error handling
- File format support:
  * Excel exports
  * PDF downloads
  * ZIP archives

5. Troubleshooting
-----------------
- Check console output for errors
- Verify internet connection
- Ensure Chrome browser is installed
- Check download directory permissions
"""

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
