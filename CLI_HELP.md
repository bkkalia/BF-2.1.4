# Black Forest Tender Scraper - CLI Help

## Overview

The Black Forest Tender Scraper supports both **GUI** and **CLI** modes for maximum flexibility. The CLI mode is perfect for:

- **Scheduled tasks** (Windows Task Scheduler, cron jobs)
- **Batch processing** of multiple operations
- **Integration** with other scripts and automation tools
- **Headless environments** (servers, containers)
- **Automated workflows**

## 🚀 Quick Start

### Most Common Use Case (90% of users)
```bash
# Scrape all departments from HP Tenders
python main.py department --all

# With custom output directory
python main.py department --all --output "C:\Tenders\HP"

# With logging
python main.py department --all --log "C:\Logs\tenders.log" --verbose
```

### Multi-Portal Support
```bash
# List all available portals
python main.py urls

# Scrape from different portals
python main.py --url "etenders" department --all
python main.py --url "MP Tenders" department --all
python main.py --url "iocletenders" department --all
```

### Distribution Package (Recommended)
```bash
# After installing the distribution package
cd "C:\Program Files\Black Forest Tender Scraper"
BlackForest.exe department --all
BlackForest.exe urls
BlackForest.exe --url "etenders" department --all
```

### Windows Task Scheduler
1. Create a new task
2. Action: Start a program
3. Program: `C:\Path\To\run_hp_tenders.bat`
4. Add arguments: (leave empty for defaults)
5. Set triggers for daily/weekly scheduling

## Command Reference

### Department Scraping

#### Basic Usage
```bash
python main.py department --all
```

#### Specific Departments
```bash
# Scrape specific departments by name
python main.py department "PWD" "Highways" "Irrigation"

# Note: Department names must match exactly as they appear on the website
```

#### Filtering Options
```bash
# Filter departments by pattern
python main.py department --all --filter "PWD"

# Limit number of departments
python main.py department --all --max-departments 5
```

#### Output Control
```bash
# Custom output directory
python main.py department --all --output "C:\Tenders\HP"

# Custom log file
python main.py department --all --log "C:\Logs\tenders.log"
```

#### Logging Options
```bash
# Verbose logging (detailed output)
python main.py department --all --verbose

# Quiet mode (minimal output)
python main.py department --all --quiet

# Combined
python main.py department --all --log "C:\Logs\tenders.log" --verbose
```

#### Dry Run
```bash
# Show what would be done without executing
python main.py department --all --dry-run
```

### Configuration Options

#### Custom Configuration File
```bash
python main.py --config "C:\MyConfig\settings.json" department --all
```

#### Custom Base URLs File
```bash
# The application automatically uses base_urls.csv in the project directory
# No manual specification needed - HP Tenders is detected automatically
```

## Windows Task Scheduler Setup

### Method 1: Using the Batch File (Recommended)

1. **Locate the batch file**: `run_hp_tenders.bat` in your project directory
2. **Open Task Scheduler**: Search for "Task Scheduler" in Windows
3. **Create new task**:
   - Name: "HP Tenders Daily Scraping"
   - Security options: Run whether user is logged on or not
4. **Triggers tab**:
   - New trigger
   - Daily at your preferred time (e.g., 2:00 AM)
   - Recur every 1 day
5. **Actions tab**:
   - Action: Start a program
   - Program: `C:\Path\To\Your\Project\run_hp_tenders.bat`
   - Add arguments: (leave empty)
   - Start in: `C:\Path\To\Your\Project`
6. **Conditions tab**:
   - Uncheck "Start the task only if the computer is on AC power"
   - Check "Wake the computer to run this task"
7. **Settings tab**:
   - Check "Run task as soon as possible after a scheduled start is missed"
   - Check "If the task fails, restart every: 1 hour, up to 3 times"

### Method 2: Direct Python Execution

1. **Create a new batch file** (e.g., `custom_scraping.bat`):
   ```batch
   @echo off
   cd /d "C:\Path\To\Your\Project"
   python main.py department --all --output "C:\Tenders\HP" --log "C:\Logs\tenders.log" --verbose
   ```

2. **Use this batch file in Task Scheduler** as described above

## Output and Logs

### Default Locations
- **Output Directory**: `Tender_Downloads\` (in project folder)
- **Log Files**: `logs\` directory with date-stamped files
- **Excel Files**: Generated in output directory with timestamps

### Custom Locations
```bash
# Custom output directory
python main.py department --all --output "D:\Tenders\HP"

# Custom log file
python main.py department --all --log "D:\Logs\hp_tenders.log"
```

### Log File Format
```
2025-01-15 14:30:15 - INFO - Starting HP Tenders department scraping...
2025-01-15 14:30:16 - INFO - Found 25 departments to process
2025-01-15 14:30:17 - INFO - Processing department: Public Works Department
2025-01-15 14:35:22 - INFO - Completed department: Public Works Department (45 tenders)
...
2025-01-15 15:15:30 - INFO - Scraping completed successfully in 45.25 minutes
```

## Troubleshooting

### Common Issues

#### 1. "HP Tenders configuration not found"
**Solution**: Ensure `base_urls.csv` exists and contains HP Tenders entry
```csv
Name,BaseURL,Keyword
HP Tenders,https://hptenders.gov.in/nicgep/app,HP Tenders
```

#### 2. "WebDriver setup failed"
**Solution**: Install Chrome browser and ensure chromedriver is available
```bash
pip install webdriver-manager
# or download chromedriver manually
```

#### 3. "Permission denied" errors
**Solution**: Run command prompt as Administrator or check folder permissions

#### 4. Task Scheduler not running
**Solution**:
- Check Task Scheduler logs
- Ensure batch file paths are correct
- Test batch file manually first
- Check Windows Event Viewer for errors

### Debug Mode
```bash
# Enable verbose logging for troubleshooting
python main.py department --all --verbose --log "debug.log"
```

## Advanced Usage

### Batch Processing
```bash
# Process multiple commands from file
echo "department --all --output C:\Tenders\HP" > commands.txt
echo "department --all --filter PWD --output C:\Tenders\PWD" >> commands.txt
python main.py batch commands.txt
```

### Environment Variables
```batch
# Set environment variables in batch file
set PYTHONPATH=C:\Path\To\Project
set TENDERS_OUTPUT=C:\Tenders
python main.py department --all --output "%TENDERS_OUTPUT%"
```

### Error Handling
```batch
# Check exit codes in batch files
python main.py department --all
if %ERRORLEVEL% NEQ 0 (
    echo "Scraping failed with error code %ERRORLEVEL%"
    exit /b 1
)
```

## File Structure

After running the scraper, your directory structure will look like:
```
Project_Directory/
├── Tender_Downloads/
│   ├── HP_Tenders_20250115_143000.xlsx    # Main Excel file
│   ├── Public_Works_Department/
│   │   ├── tender_001_more_details.pdf
│   │   ├── tender_001_documents.zip
│   │   └── ...
│   ├── Highways_Department/
│   │   └── ...
│   └── ...
├── logs/
│   ├── hp_tenders_20250115.log
│   └── app_20250115.log
├── run_hp_tenders.bat
└── main.py
```

## Performance Tips

1. **Schedule during off-peak hours** (2-4 AM) to avoid website congestion
2. **Use SSD storage** for output directories to improve performance
3. **Monitor disk space** - tender files can be several GB
4. **Enable verbose logging initially** to monitor progress
5. **Test with small batches** before full automation

## Support

### Getting Help
```bash
# Show general help
python main.py --help

# Show department-specific help
python main.py help department

# Show scheduling help
python main.py help scheduling

# Show usage examples
python main.py help examples
```

### Documentation Files
- **CLI_HELP.md**: Complete CLI documentation (included in distribution)
- **GUI_HELP.md**: Comprehensive GUI usage guide (included in distribution)
- **README.md**: Installation and setup instructions

### Log Analysis
- Check `logs/` directory for detailed execution logs
- Look for ERROR or WARNING messages
- Monitor file sizes and processing times
- Review generated Excel files for data completeness

### GUI Mode
For interactive usage with visual interface:
- Launch the GUI: `BlackForest.exe` (from distribution) or `python main.py`
- Access Help tab for built-in assistance
- See `GUI_HELP.md` for detailed GUI instructions

---

**Last Updated**: February 12, 2026
**Version**: 2.1.9
**CLI Mode**: Automated tender scraping with command-line interface
**GUI Mode**: Interactive tender scraping with visual progress monitoring
