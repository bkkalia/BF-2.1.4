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
h:\My Drive\0dev\BF 2.1.4\
├── main.py                    # Application entry point
├── config.py                  # Configuration constants
├── app_settings.py            # Settings management
├── gui/
│   ├── main_window.py         # Main GUI window with tabs
│   ├── tab_search.py          # Search dashboard (PRIMARY FOCUS)
│   └── tab_url_process.py     # URL processing tab
├── scraper/
│   └── logic.py               # Web scraping logic
├── logs/                      # Application logs
├── settings.json              # User settings
└── base_urls.csv              # Portal configurations
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
