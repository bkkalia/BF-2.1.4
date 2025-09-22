# Black Forest Tender Scraper

## Installation
1. Download and run the installer: `BlackForest_Tender_Scraper_2.1.4_Setup.exe`
2. Follow the installation wizard
3. The installer will automatically detect Python 3.7+ and install dependencies
4. Launch from Start Menu or desktop shortcut

## What's New in v2.1.4
- **Hybrid Distribution**: 10MB launcher with full functionality (down from 150MB)
- **Multi-Portal Support**: Scrape from 12+ government tender portals
- **Professional Installer**: One-click Windows installation with all dependencies
- **Performance Boost**: 60% faster page loading and scraping
- **Enhanced CAPTCHA**: Automatic detection and solving
- **Reliable Downloads**: Improved PDF and ZIP file handling
- **Task Scheduler Ready**: Automated daily scraping capabilities
- **Better Error Handling**: Clear messages and automatic recovery

## Usage

### GUI Mode (Recommended for beginners)
Double-click `BlackForest.exe` or run:
```
BlackForest.exe
```

### CLI Mode (For automation and advanced users)
```
# Scrape all departments from HP Tenders
BlackForest.exe department --all

# List all available portals
BlackForest.exe urls

# Scrape from specific portal
BlackForest.exe --url "etenders" department --all

# With custom output
BlackForest.exe department --all --output "C:\Tenders"

# With logging
BlackForest.exe department --all --log "C:\Logs\tenders.log"
```

### Multi-Portal Scraping
The application now supports 12+ tender portals including:
- HP Tenders (Himachal Pradesh)
- eTenders (Government eTenders)
- MPPKVCL (Madhya Pradesh)
- And many more...

## Windows Task Scheduler Setup
1. Open Task Scheduler
2. Create new task → Action: Start a program
3. Program: `C:\Path\To\BlackForest.exe`
4. Add arguments: `department --all --output "C:\Tenders\Daily"`
5. Set daily trigger at your preferred time

## Requirements
- Windows 7 SP1 or later (64-bit)
- Python 3.7+ (automatically installed by setup)
- Google Chrome browser
- Internet connection
- 2GB RAM minimum

## File Structure
```
BlackForest/
├── BlackForest.exe          # Hybrid launcher (10MB)
├── main.py                  # Main application
├── cli_parser.py           # CLI argument parser
├── cli_runner.py           # CLI execution logic
├── base_urls.csv           # Portal configurations (12+ portals)
├── settings.json           # Application settings
├── scraper/                # Enhanced scraping modules
├── gui/                    # Improved GUI modules
├── CLI_HELP.md            # Detailed CLI help
├── GUI_HELP.md            # Comprehensive GUI guide
└── run_hp_tenders.bat     # Task Scheduler batch file
```

## Key Features
- **Multi-Portal Scraping**: Support for 12+ government tender portals
- **Hybrid Distribution**: Small executable with full Python environment
- **Professional Installation**: Windows installer with automatic setup
- **Performance Optimized**: 60% faster scraping with improved CAPTCHA handling
- **Task Automation**: Ready for scheduled daily scraping
- **Enhanced Reliability**: Better error recovery and file download handling
- **Complete Documentation**: Built-in CLI and GUI help files

## Support
Run `BlackForest.exe --help` for command-line options
See `CLI_HELP.md` for detailed CLI usage
See `GUI_HELP.md` for comprehensive GUI guide

## Distribution
- **Installer**: `BlackForest_Tender_Scraper_2.1.4_Setup.exe` (Professional Windows installer)
- **Portable**: Extract all files for portable use
- **Enterprise Ready**: Suitable for organizational deployment

---

**Version**: 2.1.4
**Release Date**: September 18, 2025
**Compatibility**: Windows 7 SP1+
