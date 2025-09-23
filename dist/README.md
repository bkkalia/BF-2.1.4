# Black Forest Tender Scraper v2.1.5

## 🚀 High-Performance Tender Scraping Solution

**Black Forest Tender Scraper** is a professional-grade web scraping application designed for automated extraction of government tender data from multiple portals. Built with enterprise-grade reliability and performance.

## ⚡ Performance Highlights

- **⚡ Lightning Fast**: Scrapes 1000+ records in under 10 minutes (tested: 1316 records in 8 min 28 sec)
- **🌐 Multi-Portal Support**: Supports 40+ government tender portals (12 currently configured)
- **🎯 High Reliability**: Advanced CAPTCHA handling and error recovery
- **📊 Smart Processing**: Intelligent data extraction and validation

## 🎯 Key Features

### Core Capabilities
- **Multi-Portal Scraping**: HP Tenders, eTenders, and 10+ other government portals
- **Advanced CAPTCHA Handling**: Automatic detection and solving
- **File Downloads**: PDF, ZIP, and document downloads with integrity checks
- **Excel Export**: Structured data export with customizable formats
- **Progress Tracking**: Real-time progress monitoring and status updates

### User Interface
- **Modern GUI**: Clean, intuitive interface with tabbed navigation
- **CLI Mode**: Powerful command-line interface with ASCII banner
- **Interactive Prompts**: Guided scraping with real-time feedback
- **Task Scheduling**: Ready for automated daily/weekly scraping

### Enterprise Features
- **Professional Installer**: Smart upgrade system with automatic uninstall
- **Registry Integration**: Proper Windows Add/Remove Programs support
- **Silent Operations**: Background processing and dependency management
- **Comprehensive Logging**: Detailed operation logs for troubleshooting

## 📦 Installation

### Windows Installer (Recommended)
1. Download `BlackForest_Tender_Scraper_2.1.5_Setup.exe`
2. Run the installer - it will automatically detect and upgrade previous versions
3. Follow the installation wizard
4. Launch from Start Menu or desktop shortcut

### Manual Installation
1. Extract all files to a folder (e.g., `C:\Program Files\Black Forest`)
2. Ensure Python 3.7+ is installed
3. Install dependencies: `pip install -r requirements.txt`
4. Run `BlackForest.exe`

## 🚀 Usage

### GUI Mode (Default)
```bash
BlackForest.exe
```
- User-friendly interface for interactive scraping
- Real-time progress monitoring
- Visual feedback and error handling

### CLI Mode
```bash
# Interactive mode with ASCII banner
BlackForest.exe

# Scrape all departments from HP Tenders
BlackForest.exe department --all

# Scrape from specific portal
BlackForest.exe --url "etenders" department --all

# List available portals
BlackForest.exe urls
```

### Windows Task Scheduler
Create automated daily scraping:
```
BlackForest.exe department --all --output "C:\Tenders\Daily" --log "C:\Logs\tenders.log"
```

## 🏗️ Architecture

### Hybrid Distribution
- **Small Launcher**: 10MB executable launcher
- **Complete Application**: Full Python environment included
- **No External Dependencies**: Self-contained installation

### Multi-Mode Operation
- **GUI Mode**: Console-free graphical interface
- **CLI Mode**: Dedicated command-line interface with banner
- **Independent Operation**: No interference between modes

### Smart Upgrade System
- **Version Detection**: Automatic registry-based version checking
- **Upgrade Options**: New install, upgrade, repair, or reinstall
- **Silent Uninstall**: Background removal of previous versions

## 🔧 System Requirements

- **OS**: Windows 7 SP1 or later (64-bit)
- **Python**: 3.7 or higher (included in installer)
- **Browser**: Google Chrome (latest version recommended)
- **RAM**: 2GB minimum, 4GB recommended
- **Storage**: 500MB free space
- **Network**: Stable internet connection

## 📋 Supported Portals

Currently configured portals (12 of 40+ supported):
- HP Tenders (hptenders.gov.in)
- Indian Oil Corporation (iocletenders.nic.in)
- Central Government eTenders (etenders.gov.in)
- Arunachal Pradesh Tenders
- Assam Tenders
- Goa eProcure
- Haryana eTenders
- Jammu & Kashmir Tenders
- Jharkhand Tenders
- Kerala eTenders
- Madhya Pradesh Tenders
- Maharashtra Tenders

## 🛠️ Development & Build

### Build Commands
```bash
# Create hybrid distribution
python build_exe.py hybrid

# Build professional installer
iscc setup.iss
```

### Project Structure
```
BlackForest/
├── BlackForest.exe          # Launcher executable
├── main.py                  # GUI application
├── cli_main.py              # CLI application
├── cli_parser.py           # CLI argument parser
├── cli_runner.py           # CLI execution logic
├── base_urls.csv           # Portal configurations
├── settings.json           # Application settings
├── scraper/                # Scraping modules
├── gui/                    # GUI components
├── resources/              # Icons and assets
├── CLI_HELP.md            # CLI documentation
└── GUI_HELP.md            # GUI documentation
```

## 📞 Support & Licensing

**License**: Commercial software - contact for licensing details
**Email**: [license@blackforest-scraper.com](mailto:license@blackforest-scraper.com)
**Documentation**: See `CLI_HELP.md` and `GUI_HELP.md` for detailed usage

## 🔄 Version History

### v2.1.5 (Current)
- Smart upgrade system with automatic version detection
- Console-free GUI operation
- Enhanced CLI architecture with dedicated entry point
- Professional installer with repair/uninstall options
- High-performance scraping (1000+ records in 10 minutes)

### v2.1.4
- Hybrid distribution system
- Multi-portal support (12 portals)
- Inno Setup integration
- Performance optimizations

---

**Black Forest Tender Scraper** - Enterprise-grade tender data extraction solution.
