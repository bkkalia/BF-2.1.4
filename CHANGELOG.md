# Black Forest Tender Scraper - Changelog

<!-- NOTE:
This changelog's release dates can be refreshed from your local git history.
Run the helper tool (from project root) to infer and update version dates:

    python tools\generate_changelog.py

The tool makes a backup of CHANGELOG.md (CHANGELOG.md.bak.TIMESTAMP) before editing.
-->

## Version 2.1.6 (February 12, 2026)

### 🚀 Batch Dashboard & Feedback
- **Live Batch Dashboard**: Added per-portal status table (`Idle`, `Fetching`, `Scraping`, `Done`, `Error`) with expected/extracted/skipped counters.
- **Parallel State Visibility**: Logs now explicitly show `waiting for domain slot`, `acquired`, `retry`, and `cooldown` phases.
- **Portal-Level Batch Logs**: Added dedicated Batch log panel with portal filter + text search for faster troubleshooting.

### ✅ Verification & New-Only Scraping
- **New-Only Mode**: Added `Only New Tenders` option in Batch tab to skip already-known Tender IDs.
- **Manifest Tracking**: Introduced persistent `batch_tender_manifest.json` to track known Tender IDs per portal.
- **Post-Run Verification**: Batch now logs expected vs extracted vs skipped-known counts and an approximate remaining gap.

### 🛠️ Stability Fixes
- **Settings Save Fix**: Resolved timeout cast issue on close (`int('10.0')`) by safely parsing float timeout values.
- **Scraping Summary Return**: Department scraping now returns structured summary payload for dashboard and verification.

## Version 2.1.5 (February 12, 2026)

### 🚀 New UX Improvements
- **Dual Status Progress Bars**: Separate colorful progress bars for Departments and Tenders.
- **Live Progress Context**: Status now shows scraped departments, pending departments, and tender totals.
- **Better Visual Logging**: Added clear separators after each department (`********`) and portal (`########`).

### ✅ Reliability & Scraping Enhancements
- **Back-Navigation Recovery**: Automatically recovers to `FrontEndTendersByOrganisation` when portals redirect to wrong pages.
- **Flexible Table Parsing**: Handles 3-column and standard 6-column tender tables.
- **Row-Skip Reduction**: Added robust table/row retry handling for stale elements on large portals.

### 📝 Logging & Operations
- **Run-Based Log Files**: Logs are now generated per run with timestamped filenames.
- **Retention Policy**: Keeps the latest 30 runs automatically for both GUI and CLI logs.
- **GUI Log Filtering**: Added in-app filter by log level (`Critical`, `Error`, `Warning`, `Info`, `Debug`, `All`).

### 🧠 Portal Memory
- **Locator Preference Memory**: Stores successful locator strategies per portal and reuses them in future runs.
- **Faster Recovery on Known Portals**: Preferred locator order now uses learned success history.

## Version 2.1.4 (September 18, 2025)

### 🚀 Major Features
- **Hybrid Distribution**: New launcher system reducing EXE size from 150MB to 10MB
- **Multi-Portal Support**: Added support for 12+ tender portals
- **Inno Setup Integration**: Professional Windows installer
- **Complete Documentation**: CLI and GUI help files included

### ✅ Improvements
- **Performance Optimization**: Reduced page load times by 60%
- **CAPTCHA Handling**: Improved automatic CAPTCHA detection and solving
- **File Downloads**: Enhanced PDF and ZIP download reliability
- **Task Scheduler**: Ready for automated daily scraping
- **Error Handling**: Better error messages and recovery

### 🐛 Bug Fixes
- Fixed download functionality in `tab_id_search.py`
- Resolved parameter passing issues between GUI and scraper modules
- Fixed CAPTCHA popup handling timing
- Improved WebDriver stability and cleanup
- Fixed Pylance type error in `cli_runner.py` list iteration
- Fixed CLI mode launch issues with readline compatibility
- Resolved CLI mode not displaying ASCII banner when launched from GUI

### 📦 Distribution
- **Professional Installer**: Single EXE installer with all dependencies
- **Complete Package**: All files included, no external dependencies
- **Easy Deployment**: Ready for enterprise distribution

## Version 2.1.3 (December 2024)

### Features Added
- Initial multi-portal support
- Enhanced GUI with progress indicators
- CLI mode for automation
- Excel export functionality

### Improvements
- Better error handling
- Improved logging system
- User-friendly interface

## Version 2.1.2 (November 2024)

### Bug Fixes
- Fixed WebDriver initialization issues
- Improved CAPTCHA handling
- Better file download management

## Version 2.1.1 (October 2024)

### Features Added
- Basic tender scraping functionality
- PDF download support
- Simple GUI interface

## Version 2.1.0 (September 2024)

### Initial Release
- Core tender scraping functionality
- HP Tenders portal support
- Basic file download capabilities

---

## Development Notes

### Build Process
```bash
# Build hybrid package
python build_exe.py hybrid

# Create installer
iscc setup.iss
```

### Distribution Files
- `BlackForest.exe` - Small launcher (10MB)
- `dist/` - Complete Python application
- `setup.iss` - Inno Setup script
- `installer_output/` - Generated installer

### System Requirements
- Windows 7 SP1 or later (64-bit)
- Python 3.7+
- Google Chrome browser
- 2GB RAM minimum

---

**For the latest updates, check the GitHub repository.**
