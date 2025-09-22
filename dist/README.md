# Black Forest Tender Scraper

## Installation
1. Extract all files to a folder (e.g., C:\Program Files\Black Forest)
2. Ensure Python 3.7+ is installed on your system
3. Install required packages: pip install -r requirements.txt

## Usage

### GUI Mode (Default)
Double-click `BlackForest.exe` or run:
```
BlackForest.exe
```

### CLI Mode
```
# Scrape all departments from HP Tenders
BlackForest.exe department --all

# List available portals
BlackForest.exe urls

# Scrape from specific portal
BlackForest.exe --url "etenders" department --all

# With custom output
BlackForest.exe department --all --output "C:\Tenders"

# With logging
BlackForest.exe department --all --log "C:\Logs\tenders.log"
```

### Windows Task Scheduler
Create a batch file with:
```
@echo off
cd /d "C:\Path\To\BlackForest"
BlackForest.exe department --all --output "C:\Tenders\HP" --log "C:\Logs\tenders.log"
```

## Requirements
- Python 3.7 or higher
- Google Chrome browser
- Internet connection

## File Structure
```
BlackForest/
├── BlackForest.exe          # Launcher executable
├── main.py                  # Main application
├── cli_parser.py           # CLI argument parser
├── cli_runner.py           # CLI execution logic
├── base_urls.csv           # Portal configurations
├── settings.json           # Application settings
├── scraper/                # Scraping modules
├── gui/                    # GUI modules
├── CLI_HELP.md            # Detailed help
└── run_hp_tenders.bat     # Windows batch file
```

## Support
Run `BlackForest.exe --help` for command-line options
See `CLI_HELP.md` for detailed usage instructions
