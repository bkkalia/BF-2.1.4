# Cloud84 Tender Scraper v2.1.4
## PROJECT OVERVIEW
This is a **Python desktop application** for web scraping tender/bid data from government websites like hptenders.gov.in and other government portals.

## TECHNOLOGY STACK
- **Language**: Python 3.7+
- **GUI Framework**: Tkinter (NO web technologies)
- **Web Scraping**: Selenium WebDriver, requests
- **Data Processing**: pandas, openpyxl
- **Architecture**: Desktop application (NOT web-based)
- **Storage**: Local files (Excel, JSON, CSV)

## CORE FUNCTIONALITY
1. **Web Scraping Engine**: Extract tender data from government portals using Selenium
2. **Search & Filter Dashboard**: Advanced filtering by date, department, keywords in `gui/tab_search.py`
3. **Data Management**: Load, filter, and display scraped tender data
4. **Export Features**: Export filtered results to Excel files
5. **URL Configuration**: Manage multiple tender portal URLs
6. **Persistent Storage**: Save user preferences and folder paths

## PROJECT STRUCTURE
```
d:\Dev84\BF 2.1.4\
├── main.py                           # Application entry point
├── config.py                         # Configuration constants
├── app_settings.py                   # Settings management
├── cli_parser.py                     # Command-line interface parser
├── cli_runner.py                     # CLI execution logic
├── utils.py                          # Utility functions
├── test.py                           # Test scripts
├── build_exe.py                      # Executable build script
├── blackforest_launcher.py           # Launcher script
├── rebuild_installer.bat             # Installer rebuild script
├── run_hp_tenders.bat                # HP tenders batch script
├── requirements.txt                  # Python dependencies
├── settings.json                     # User settings
├── base_urls.csv                     # Portal configurations
├── search_folders.json               # Search folder configurations
├── version_info.txt                  # Version information for builds
├── AI_INSTRUCTIONS.md                # AI assistant guidelines
├── CHANGELOG.md                      # Version changelog
├── CLI_HELP.md                       # CLI help documentation
├── GUI_HELP.md                       # GUI help documentation
├── PROJECT_CONTEXT.md                # This file - project overview
├── ROADMAP.md                        # Development roadmap
├── LICENSE.txt                       # License information
├── INSTRUCTIONS.md                   # General instructions
├── GPT_Analysis.md                   # GPT analysis notes
├── Cline Style AI Coding Assistant Instructions.md  # AI coding guidelines
├── New Structure.txt                 # Structure documentation
├── search Himachal Pradesh.pdf       # Sample search document
├── BlackForest.spec                  # PyInstaller spec file
├── BlackForest_Launcher.spec         # Launcher PyInstaller spec
├── setup.iss                         # Inno Setup script
├── setup_simple.iss                  # Simplified installer script
├── BF 2.1.4.code-workspace           # VSCode workspace file
├── build/                            # Build artifacts
│   └── build/BlackForest_Launcher/
├── gui/                              # GUI components
│   ├── __init__.py
│   ├── main_window.py                # Main GUI window with tabs
│   ├── tab_department.py             # Department-based scraping tab
│   ├── tab_help.py                   # Help and documentation tab
│   ├── tab_id_search.py              # ID-based search tab
│   ├── tab_settings.py               # Application settings tab
│   ├── tab_url_process.py            # URL processing tab
│   ├── global_panel.py               # Global control panel
│   └── gui_utils.py                  # GUI utility functions
├── installer_output/                 # Generated installers
│   └── BlackForest_Tender_Scraper_2.1.4_Portable.zip
├── logs/                             # Application logs
│   ├── app_20250914.log
│   ├── app_20250915.log
│   ├── app_20250917.log
│   ├── app_20250918.log
│   ├── app_20250919.log
│   └── app_20250920.log
├── resources/                        # Application resources
│   └── app_icon.ico                  # Application icon
├── sample Excels/                    # Sample Excel files
│   └── hptenders_gov_in_tenders_20250524_163439.xlsx
├── scraper/                          # Core scraping logic
│   ├── __init__.py
│   ├── logic.py                      # Main scraping logic
│   ├── actions.py                    # Selenium action wrappers
│   ├── captcha_handler.py            # CAPTCHA handling
│   ├── driver_manager.py             # WebDriver management
│   ├── ocr_helper.py                 # OCR functionality
│   ├── sound_helper.py               # Sound notification system
│   └── webdriver_manager.py          # WebDriver setup
├── Tender_Downloads/                 # Downloaded tender files
│   └── hptenders_gov_in_tenders_20250919_182152.xlsx
└── tools/                            # Development tools
    └── generate_changelog.py         # Changelog generation tool
```

## PRIMARY FOCUS AREAS
1. **Search Dashboard** (`gui/tab_search.py`): Advanced data filtering and display
2. **Data Processing**: pandas DataFrame operations for filtering
3. **User Experience**: Tkinter GUI improvements
4. **Export Functionality**: Excel data export features

## STRICT TECHNOLOGY RULES
- ❌ NO JavaScript, HTML, CSS (this is NOT a web app)
- ❌ NO React, Node.js, Angular, or web frameworks
- ❌ NO game development code or brain training apps
- ❌ NO web servers or API endpoints
- ✅ ONLY Python Tkinter desktop application
- ✅ Focus on data scraping, filtering, and management
- ✅ pandas for data manipulation
- ✅ Selenium for web scraping

## CURRENT STATE
- Application successfully loads and displays tender data
- Search dashboard with department and keyword filtering
- Date-based filtering (today, tomorrow, 7 days, etc.)
- Data export to Excel functionality
- Persistent folder management for data sources

## IMMEDIATE PRIORITIES
1. Enhance search and filtering in `tab_search.py`
2. Improve data sorting and display features
3. Add custom date range filtering
4. Optimize data loading and performance
5. Better error handling and user feedback
