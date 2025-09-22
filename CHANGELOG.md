# Black Forest Tender Scraper - Changelog

<!-- NOTE:
This changelog's release dates can be refreshed from your local git history.
Run the helper tool (from project root) to infer and update version dates:

    python tools\generate_changelog.py

The tool makes a backup of CHANGELOG.md (CHANGELOG.md.bak.TIMESTAMP) before editing.
-->

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
