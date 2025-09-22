# Black Forest Tender Scraper - GUI Help

## Overview

The Black Forest Tender Scraper provides a user-friendly **Graphical User Interface (GUI)** for interactive tender scraping operations. The GUI is perfect for:

- **Interactive exploration** of tender data
- **One-time scraping tasks** without automation
- **Visual monitoring** of scraping progress
- **Easy configuration** through settings
- **Beginner-friendly** operation

## 🚀 Getting Started

### Launching the Application

#### Method 1: From Distribution Package
```bash
# Navigate to installation directory
cd "C:\Program Files\Black Forest Tender Scraper"

# Double-click BlackForest.exe or run:
BlackForest.exe
```

#### Method 2: From Source Code
```bash
# Ensure Python and dependencies are installed
pip install -r requirements.txt

# Run the application
python main.py
```

### Main Interface Overview

```
┌─────────────────────────────────────────────────────────────┐
│ Black Forest Tender Scraper v2.1.4                    [_][□][X] │
├─────────────────────────────────────────────────────────────┤
│ [By Department] [By Tender ID] [By Direct URL] [Settings] [Help] │
├─────────────────────────────────────────────────────────────┤
│ Filter Departments: [____________________] Select URL: [▼]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                  [TAB CONTENT AREA]                         │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Progress: [████████████████████████░░░░░] 75%               │
│ Processed: 15 / 20                    Est. Rem: 00:05:30    │
│ Elapsed: 00:12:15                     Status: Processing... │
│                                                             │
│ [STOP]                                                      │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Main Tabs

### 1. By Department (Most Common Use Case)

#### Overview
This tab allows you to scrape tenders from all departments of a selected portal. This is the **90% use case** for most users.

#### How to Use:
1. **Select Portal**: Use the dropdown in the global panel to choose your target portal
2. **Filter Departments** (Optional): Type to filter departments by name
3. **Configure Options**:
   - ✅ **Download More Details PDFs**: Get detailed tender information
   - ✅ **Download ZIP Files**: Download tender documents
   - ✅ **Download Notice PDFs**: Download tender notices
4. **Choose Departments**:
   - **All Departments**: Click "Fetch All Departments" then "Start Scraping"
   - **Specific Departments**: Select individual departments from the list
5. **Set Output Directory**: Choose where to save downloaded files
6. **Start Scraping**: Click the "Start Scraping" button

#### Example Workflow:
```
1. Select "HP Tenders" from dropdown
2. Click "Fetch All Departments"
3. Check all download options
4. Set output to "C:\Tenders\HP"
5. Click "Start Scraping"
6. Monitor progress in the status bar
```

### 2. By Tender ID

#### Overview
Search for specific tenders using their unique Tender ID numbers.

#### How to Use:
1. **Select Portal**: Choose target portal from dropdown
2. **Enter Tender IDs**:
   - **Single ID**: Enter one tender ID
   - **Multiple IDs**: Enter comma-separated IDs
   - **From File**: Load IDs from a text file
3. **Configure Download Options**: Same as Department tab
4. **Set Output Directory**: Choose save location
5. **Start Search**: Click "Search & Download"

#### Example:
```
Tender IDs: 2024_HP_001, 2024_HP_002, 2024_HP_003
Output: C:\Tenders\Specific
```

### 3. By Direct URL

#### Overview
Process tenders using direct URLs from tender portals.

#### How to Use:
1. **Select Portal**: Choose target portal from dropdown
2. **Enter URLs**:
   - **Single URL**: Paste one tender URL
   - **Multiple URLs**: Enter multiple URLs (one per line)
   - **From File**: Load URLs from a text file
3. **Configure Download Options**: Same as other tabs
4. **Set Output Directory**: Choose save location
5. **Start Processing**: Click "Process URLs"

#### URL Format Examples:
```
HP Tenders: https://hptenders.gov.in/nicgep/app?page=FrontEndTendersByOrganisation&service=page&TenderID=12345
etenders: https://etenders.gov.in/eprocure/app?page=FrontEndTendersByOrganisation&service=page&TenderID=67890
```

### 4. Settings

#### Overview
Configure application behavior, appearance, and advanced options.

#### Main Settings:
- **Download Directory**: Default location for saved files
- **Download Options**: Default PDF/ZIP download preferences
- **Theme Selection**: Choose GUI appearance theme
- **Driver Settings**: Configure Selenium WebDriver options
- **Timeout Settings**: Adjust waiting times for web operations

#### Advanced Settings:
- **Deep Scraping**: Enable detailed tender information extraction
- **Headless Mode**: Run browser invisibly (for automation)
- **Verbose Logging**: Enable detailed logging
- **Proxy Settings**: Configure proxy servers if needed

### 5. Help

#### Overview
Access built-in help and documentation.

#### Available Help Topics:
- **Quick Start Guide**: Basic usage instructions
- **CLI Mode**: Command-line interface documentation
- **Troubleshooting**: Common issues and solutions
- **About**: Application information and version details

## 🎛️ Global Controls

### Department Filter
- **Location**: Top panel, left side
- **Function**: Filter department list by typing department names
- **Usage**: Type "PWD" to show only Public Works departments

### Portal Selection
- **Location**: Top panel, right side
- **Function**: Choose which tender portal to scrape
- **Available Portals**: All portals listed in `base_urls.csv`

### Progress Monitoring
- **Location**: Bottom status bar
- **Information**:
  - **Progress Bar**: Visual progress indicator
  - **Processed Count**: Items completed vs total
  - **Estimated Time**: Time remaining for current operation
  - **Elapsed Time**: Total time since operation started
  - **Status Messages**: Current operation status

### Stop Button
- **Location**: Bottom right of status bar
- **Function**: Immediately stop current scraping operation
- **Usage**: Click when you need to cancel a long-running operation

## ⚙️ Configuration

### Application Settings
1. **Navigate to Settings tab**
2. **Modify preferences**:
   - Download directory
   - Default download options
   - UI theme
   - Timeout values
3. **Click "Save Settings"**
4. **Settings persist** between application sessions

### Portal Management
- **Add New Portals**: Edit `base_urls.csv` file
- **Format Required**:
  ```csv
  Name,BaseURL,Keyword
  NewPortal,https://newportal.gov.in/nicgep/app,NewPortal
  ```
- **Automatic Detection**: New portals appear in dropdown after restart

## 📊 Output and Results

### File Organization
```
Output_Directory/
├── PortalName_Tenders_YYYYMMDD_HHMMSS.xlsx    # Main Excel file
├── Department1_Name/
│   ├── tender_001_more_details.pdf
│   ├── tender_001_documents.zip
│   └── tender_001_notice.pdf
├── Department2_Name/
│   └── ...
└── Scraping_Log_YYYYMMDD_HHMMSS.log
```

### Excel File Contents
- **Tender ID**: Unique identifier
- **Title**: Tender title/description
- **Department**: Issuing department
- **Publish Date**: When tender was published
- **Closing Date**: Tender submission deadline
- **Opening Date**: Technical bid opening date
- **Value**: Tender value (if available)
- **Status**: Current tender status
- **Direct URL**: Link to tender details

### Log Files
- **Location**: `logs/` directory
- **Naming**: `app_YYYYMMDD.log`
- **Content**: Detailed operation logs, errors, and progress

## 🔧 Troubleshooting

### Common GUI Issues

#### 1. Application Won't Start
**Symptoms**: Error messages on startup
**Solutions**:
- Ensure Python 3.7+ is installed
- Install required packages: `pip install -r requirements.txt`
- Check for missing dependencies in error messages

#### 2. WebDriver Errors
**Symptoms**: "ChromeDriver not found" or similar
**Solutions**:
- Install Google Chrome browser
- Ensure stable internet connection
- Try updating WebDriver: `pip install --upgrade webdriver-manager`

#### 3. Portal Connection Issues
**Symptoms**: "Cannot connect to portal" errors
**Solutions**:
- Check internet connection
- Verify portal URL is accessible
- Try different portal if one is down
- Check firewall/antivirus settings

#### 4. Slow Performance
**Symptoms**: Scraping takes very long time
**Solutions**:
- Reduce number of departments to scrape
- Disable unnecessary download options
- Check system resources (CPU, memory)
- Close other applications during scraping

#### 5. Memory Issues
**Symptoms**: Application crashes with memory errors
**Solutions**:
- Reduce concurrent operations
- Close other memory-intensive applications
- Increase system virtual memory
- Use smaller batches for processing

### Getting Help
1. **Check Logs**: Look in `logs/` directory for detailed error information
2. **Built-in Help**: Use the Help tab in the application
3. **CLI Help**: Run `python main.py --help` for command-line options
4. **Verbose Mode**: Enable verbose logging in Settings for more details

## 🎯 Best Practices

### For Optimal Performance
1. **Schedule during off-peak hours** (2-4 AM) to avoid website congestion
2. **Start with small batches** to test system performance
3. **Use SSD storage** for output directories to improve speed
4. **Monitor system resources** during large scraping operations
5. **Keep output directories organized** with descriptive names

### Data Management
1. **Regular backups** of important tender data
2. **Organize by date/project** for easy retrieval
3. **Monitor disk space** - tender files can be several GB
4. **Use descriptive filenames** for output directories
5. **Archive old data** to prevent disk space issues

### Security Considerations
1. **Use strong passwords** if portal requires authentication
2. **Avoid scraping sensitive/confidential tenders**
3. **Respect website terms of service**
4. **Don't overload target websites** with too many requests
5. **Use appropriate delays** between requests

## 🚀 Advanced Features

### Batch Processing
- Use CLI mode for batch processing: `python main.py department --all`
- Create batch files for repetitive tasks
- Schedule automated scraping with Windows Task Scheduler

### Custom Scripts
- Use the CLI in custom scripts and automation
- Integrate with other business processes
- Create custom reporting and analysis tools

### Multi-Portal Operations
- Switch between different portals using the dropdown
- Compare data across different tender portals
- Monitor tenders from multiple sources simultaneously

## 📞 Support and Resources

### Built-in Resources
- **Help Tab**: Comprehensive in-application help
- **CLI Help**: `python main.py --help`
- **Log Files**: Detailed operation logs in `logs/` directory
- **Configuration Files**: Editable settings in `settings.json`

### External Resources
- **Python Documentation**: For custom script development
- **Selenium Documentation**: For WebDriver troubleshooting
- **Pandas Documentation**: For Excel file manipulation

---

**Last Updated**: September 22, 2025
**Version**: 2.1.4
**GUI Mode**: Interactive tender scraping with visual progress monitoring
