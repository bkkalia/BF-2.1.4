"""
Cloud84 Tender Scraper v2.1.4
DESKTOP APPLICATION - Python Tkinter GUI
Purpose: Web scraping tender/bid data from government portals
Tech Stack: Python, Tkinter, Selenium, pandas
NOT a web application - NO JavaScript/HTML/CSS
"""

# main.py v2.1.4
# Main entry point for the Cloud84 Tender Scraper application.

import tkinter as tk
import tkinter.messagebox
import sys
import logging
import os
import datetime
import platform
import traceback


# Add a fallback URL in case base_urls.csv is not readable or empty
FALLBACK_URL = "https://hptenders.gov.in"  # Just the base URL, no additional paths

# --- Calculate Absolute Paths Early ---
try:
    # Get the directory where main.py resides
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # Fallback for environments where __file__ might not be defined (e.g., interactive)
    SCRIPT_DIR = os.getcwd()

# --- Add Project Root to sys.path ---
# This allows absolute imports from the project root (e.g., 'import config')
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# --- Configuration and Utility Imports ---
try:
    from config import (
        LOG_FORMAT, LOG_LEVEL, DEFAULT_APP_NAME, APP_VERSION,
        LOG_DIR_NAME, SETTINGS_FILENAME, BASE_URLS_FILENAME, DEFAULT_DOWNLOAD_DIR_NAME
    )
except ImportError as e:
    print(f"FATAL ERROR: Could not import required constants from config.py: {e}")
    # Define fallbacks for path calculation if config fails
    LOG_DIR_NAME = "logs"
    LOG_FORMAT = '%(asctime)s - %(levelname)s - [%(threadName)s:%(funcName)s] %(message)s'
    LOG_LEVEL = logging.INFO
    DEFAULT_APP_NAME = "Tender Scraper (Config Error)"
    APP_VERSION = "ERR"
    SETTINGS_FILENAME = "settings.json"
    BASE_URLS_FILENAME = "base_urls.csv"
    DEFAULT_DOWNLOAD_DIR_NAME = "Tender_Downloads"

# --- Set Absolute Paths based on Script Location ---
ABS_LOG_DIR = os.path.join(SCRIPT_DIR, LOG_DIR_NAME)
ABS_SETTINGS_FILE = os.path.join(SCRIPT_DIR, SETTINGS_FILENAME)
ABS_BASE_URLS_FILE = os.path.join(SCRIPT_DIR, BASE_URLS_FILENAME)
ABS_DEFAULT_DOWNLOAD_DIR = os.path.join(SCRIPT_DIR, DEFAULT_DOWNLOAD_DIR_NAME)

# --- Early Logging Setup (Console Only) ---
def setup_logging():
    """Setup enhanced logging with better formatting and error handling."""
    try:
        # Create logs directory if it doesn't exist
        os.makedirs(ABS_LOG_DIR, exist_ok=True)
        
        # Configure logging with both console and file output
        logging.basicConfig(
            level=LOG_LEVEL,
            format=LOG_FORMAT,
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(
                    os.path.join(ABS_LOG_DIR, f"app_{datetime.datetime.now().strftime('%Y%m%d')}.log"),
                    encoding='utf-8'
                )
            ],
            force=True
        )
        
        # Log system information
        logging.info(f"--- {DEFAULT_APP_NAME} v{APP_VERSION} Starting ---")
        logging.info(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
        logging.info(f"Python: {sys.version}")
        logging.info(f"Script Directory: {SCRIPT_DIR}")
        logging.info(f"Working Directory: {os.getcwd()}")
        
        return True
    except Exception as log_setup_err:
        print(f"FATAL ERROR setting up logging: {log_setup_err}")
        # Fallback to basic console logging
        logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT, stream=sys.stdout)
        return False

setup_logging()

# --- Enhanced Package Availability Checks ---
REQUIRED_PACKAGES = {
    'selenium': 'selenium>=4.0.0',
    'pandas': 'pandas>=1.3.0',
    'openpyxl': 'openpyxl>=3.0.0',
    'requests': 'requests>=2.25.0',
    'pytesseract': 'pytesseract>=0.3.10',  # Added pytesseract to required packages
}

OPTIONAL_PACKAGES = {
    'undetected_chromedriver': 'undetected-chromedriver',
    'webdriver_manager': 'webdriver-manager'
}

def check_package_versions():
    """Check package availability and versions with detailed reporting."""
    missing_packages = []
    outdated_packages = []
    
    for package, requirement in REQUIRED_PACKAGES.items():
        try:
            imported_module = __import__(package)
            version = getattr(imported_module, '__version__', 'unknown')
            logging.info(f"✓ {package} {version} is available")
        except ImportError:
            missing_packages.append((package, requirement))
            logging.error(f"✗ {package} is not installed")
    
    # Check optional packages
    for package, requirement in OPTIONAL_PACKAGES.items():
        try:
            imported_module = __import__(package)
            version = getattr(imported_module, '__version__', 'unknown')
            logging.info(f"✓ {package} {version} (optional) is available")
        except ImportError:
            logging.warning(f"⚠ {package} (optional) is not installed")
    
    return missing_packages, outdated_packages

missing_packages, outdated_packages = check_package_versions()

if missing_packages:
    error_msg = "Missing required packages:\n\n"
    for package, requirement in missing_packages:
        error_msg += f"pip install {requirement}\n"
    
    if outdated_packages:
        error_msg += "\nOutdated packages (recommended to upgrade):\n"
        for package, requirement in outdated_packages:
            error_msg += f"pip install --upgrade {requirement}\n"
    
    logging.error(error_msg)
    print(error_msg)
    
    try:
        root_err = tk.Tk()
        root_err.withdraw()
        tkinter.messagebox.showerror(
            "Missing Dependencies",
            "Required packages are missing. Check console for details.\n\n" +
            "Install missing packages and restart the application."
        )
        root_err.destroy()
    except Exception as gui_err:
        logging.error(f"Could not show GUI error: {gui_err}")
    sys.exit(1)

# --- System Requirements Check ---
def check_system_requirements():
    """Check system requirements and display warnings if needed."""
    warnings = []
    
    # Check Python version
    if sys.version_info < (3, 7):
        warnings.append(f"Python {sys.version_info.major}.{sys.version_info.minor} detected. Python 3.7+ recommended.")
    
    # Check available memory (basic check) - make psutil truly optional
    try:
        # Import locally to avoid module resolution warnings
        import psutil  # type: ignore
        memory_gb = psutil.virtual_memory().total / (1024**3)
        if memory_gb < 4:
            warnings.append(f"Low system memory detected: {memory_gb:.1f}GB. 4GB+ recommended.")
        logging.debug(f"System memory: {memory_gb:.1f}GB")
    except ImportError:
        logging.debug("psutil not available, skipping memory check")
    except Exception as e:
        logging.debug(f"Error checking memory: {e}")
    
    # Check disk space in script directory
    try:
        import shutil
        free_space_gb = shutil.disk_usage(SCRIPT_DIR).free / (1024**3)
        if free_space_gb < 1:
            warnings.append(f"Low disk space: {free_space_gb:.1f}GB free. 1GB+ recommended.")
        logging.debug(f"Disk space: {free_space_gb:.1f}GB free")
    except Exception as e:
        logging.debug(f"Error checking disk space: {e}")
    
    for warning in warnings:
        logging.warning(f"System Check: {warning}")
    
    return warnings

system_warnings = check_system_requirements()

# --- Import Core Application Components ---
def import_application_components():
    """Import application components with detailed error reporting."""
    try:
        logging.info("Importing application components...")
        
        # Import in order of dependency
        from app_settings import load_settings, save_settings, load_base_urls
        logging.debug("✓ app_settings imported")
        
        from gui.main_window import MainWindow
        logging.debug("✓ MainWindow imported")
        
        # Test import scraper components early
        try:
            import scraper.logic
            logging.debug("✓ scraper.logic imported")
        except ImportError as e:
            logging.warning(f"⚠ scraper.logic import failed: {e}")
        
        logging.info("Application components imported successfully")
        return load_settings, save_settings, load_base_urls, MainWindow
        
    except ImportError as e:
        logging.error(f"Import error: {e}", exc_info=True)
        error_message = f"Failed to import required components.\n\nError: {str(e)}\n\nCheck that all files are present and Python path is correct."
        raise ImportError(error_message)
    except Exception as e:
        logging.error(f"Unexpected import error: {e}", exc_info=True)
        error_message = f"Unexpected error during import.\n\nError: {str(e)}\n\nCheck console output for details."
        raise Exception(error_message)

try:
    load_settings, save_settings, load_base_urls, MainWindow = import_application_components()
except (ImportError, Exception) as e:
    error_message = str(e)
    print(f"FATAL ERROR: {error_message}")
    try:
        root_err = tk.Tk()
        root_err.withdraw()
        tkinter.messagebox.showerror("Import Error", error_message)
        root_err.destroy()
    except Exception as msg_err:
        logging.error(f"Could not display GUI error message: {msg_err}")
    sys.exit(1)

# --- Configuration Loading with Validation ---
def load_and_validate_configurations():
    """Load and validate all configuration files with comprehensive error handling."""
    # Load base URLs
    try:
        logging.info(f"Loading base URL configurations from {ABS_BASE_URLS_FILE}...")
        base_urls_data = load_base_urls(ABS_BASE_URLS_FILE)
        
        if not base_urls_data or not isinstance(base_urls_data, list):
            logging.warning("No valid base URLs found, using fallback")
            base_urls_data = [{
                'Name': 'Fallback HP Tenders',
                'BaseURL': FALLBACK_URL,
                'OrgListURL': f"{FALLBACK_URL}/nicgep/app",
                'Keyword': 'hptenders'
            }]
        
        # Validate and enhance URL configurations
        for config in base_urls_data:
            required_keys = ['Name', 'BaseURL', 'Keyword']
            missing_keys = [k for k in required_keys if k not in config]
            if missing_keys:
                raise ValueError(f"URL config missing keys: {missing_keys}")
            
            # Auto-generate OrgListURL if missing
            if 'OrgListURL' not in config:
                config['OrgListURL'] = f"{config['BaseURL']}/nicgep/app"
                logging.debug(f"Auto-generated OrgListURL for {config['Name']}")
        
        logging.info(f"✓ Loaded {len(base_urls_data)} URL configurations")
        
    except Exception as url_err:
        logging.error(f"Error loading base URLs: {url_err}", exc_info=True)
        base_urls_data = [{
            'Name': 'Fallback HP Tenders',
            'BaseURL': FALLBACK_URL,
            'OrgListURL': f"{FALLBACK_URL}/nicgep/app",
            'Keyword': 'hptenders'
        }]
        logging.warning("Using fallback URL configuration")
    
    # Load settings
    try:
        logging.info("Loading application settings...")
        settings = load_settings(ABS_SETTINGS_FILE, ABS_DEFAULT_DOWNLOAD_DIR)
        
        if not settings:
            settings = {}
            logging.info("No existing settings found, using defaults")
        
        # Ensure required settings exist
        default_settings = {
            'download_directory': ABS_DEFAULT_DOWNLOAD_DIR,
            'window_geometry': '1200x800+100+100',
            'dl_more_details': True,
            'dl_zip': True,
            'dl_notice_pdfs': True,
            'deep_scrape_departments': False,
            'use_undetected_driver': True,
            'headless_mode': False
        }
        
        for key, default_value in default_settings.items():
            if key not in settings:
                settings[key] = default_value
                logging.debug(f"Set default setting: {key} = {default_value}")
        
        # Validate download directory
        download_dir = settings['download_directory']
        if not os.path.exists(download_dir):
            try:
                os.makedirs(download_dir, exist_ok=True)
                logging.info(f"Created download directory: {download_dir}")
            except Exception as e:
                logging.warning(f"Could not create download directory: {e}")
                settings['download_directory'] = ABS_DEFAULT_DOWNLOAD_DIR
        
        logging.info("✓ Settings loaded and validated")
        
    except Exception as settings_err:
        logging.error(f"Error loading settings: {settings_err}", exc_info=True)
        settings = {
            'download_directory': ABS_DEFAULT_DOWNLOAD_DIR,
            'window_geometry': '1200x800+100+100'
        }
        logging.warning("Using minimal default settings")
    
    return base_urls_data, settings

# --- Main Execution Block ---
if __name__ == "__main__":
    root = None
    app = None
    
    try:
        logging.info("🚀 Starting application initialization...")
        
        # Show system warnings if any
        if system_warnings:
            logging.warning("System warnings detected - application may run with reduced performance")
        
        # Load configurations
        base_urls_data, settings = load_and_validate_configurations()
        
        # Initialize Tkinter with better error handling
        logging.info("Creating main application window...")
        root = tk.Tk()
        
        # Verify Tkinter is working
        if not root.winfo_exists():
            raise RuntimeError("Failed to create Tkinter root window")
        
        # Hide window during initialization for smoother startup
        root.withdraw()
        
        # Set basic window properties early
        root.title(f"{DEFAULT_APP_NAME} v{APP_VERSION}")
        try:
            # Try to set window icon if available
            icon_path = os.path.join(SCRIPT_DIR, "icon.ico")
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
        except Exception:
            pass  # Icon setting is optional
        
        logging.info("Creating MainWindow instance...")
        app = MainWindow(
            root=root,
            settings=settings,
            base_urls_data=base_urls_data,
            settings_filepath=ABS_SETTINGS_FILE,
            abs_default_download_dir=ABS_DEFAULT_DOWNLOAD_DIR
        )
        
        # Open search tab by default (MAIN FEATURE) - with safe attribute checking
        try:
            # Safe notebook access with multiple fallback strategies
            notebook_widget = None
            
            # Strategy 1: Check common notebook attribute names
            possible_notebook_attrs = ['notebook', 'tab_notebook', 'main_notebook', 'tabs']
            for attr_name in possible_notebook_attrs:
                if hasattr(app, attr_name):
                    candidate = getattr(app, attr_name)
                    # Verify it has notebook-like methods
                    if (hasattr(candidate, 'index') and 
                        hasattr(candidate, 'tab') and 
                        hasattr(candidate, 'select')):
                        notebook_widget = candidate
                        logging.debug(f"Found notebook widget: {attr_name}")
                        break
            
            # Strategy 2: Search in widget hierarchy if direct access failed
            if notebook_widget is None and hasattr(app, 'winfo_children'):
                def find_notebook_widget(parent):
                    """Recursively find notebook widget in widget tree."""
                    try:
                        for child in parent.winfo_children():
                            widget_class = child.__class__.__name__
                            if ('notebook' in widget_class.lower() or 'tab' in widget_class.lower()):
                                if (hasattr(child, 'index') and 
                                    hasattr(child, 'tab') and 
                                    hasattr(child, 'select')):
                                    return child
                            
                            # Recursively search children
                            found = find_notebook_widget(child)
                            if found:
                                return found
                    except Exception:
                        pass
                    return None
                
                notebook_widget = find_notebook_widget(app)
                if notebook_widget:
                    logging.debug("Found notebook widget in widget hierarchy")
            
            # Strategy 3: Try to select search tab if notebook widget found
            if notebook_widget:
                try:
                    num_tabs = notebook_widget.index('end')
                    search_tab_found = False
                    
                    # Look for search tab
                    for i in range(num_tabs):
                        try:
                            tab_text = notebook_widget.tab(i, 'text')
                            if 'search' in tab_text.lower():
                                notebook_widget.select(i)
                                logging.info("✓ Search tab opened by default - PRIMARY DASHBOARD")
                                search_tab_found = True
                                break
                        except Exception as tab_err:
                            logging.debug(f"Error checking tab {i}: {tab_err}")
                            continue
                    
                    # Fallback to first tab if search tab not found
                    if not search_tab_found and num_tabs > 0:
                        notebook_widget.select(0)
                        logging.info("✓ First tab selected as default (search tab not found)")
                        
                except Exception as notebook_err:
                    logging.warning(f"Error working with notebook widget: {notebook_err}")
            else:
                logging.debug("No notebook widget found - application may use different UI structure")
                
        except Exception as tab_err:
            logging.warning(f"Could not select search tab: {tab_err}")
        
        # Show window after initialization
        root.deiconify()
        root.lift()
        root.focus_force()
        
        logging.info("✓ Application initialization completed successfully")
        logging.info("🎯 Starting main event loop...")
        
        # Start the main event loop
        root.mainloop()
        
        logging.info("Main event loop ended normally")

    except Exception as main_err:
        error_message = str(main_err)
        logging.exception("🔥 Fatal error in main execution")
        print(f"\nFATAL ERROR: {error_message}")
        
        # Show error dialog if possible
        try:
            if root and root.winfo_exists():
                tkinter.messagebox.showerror(
                    "Fatal Application Error",
                    f"A critical error occurred:\n\n{error_message}\n\n"
                    f"Check the log file for detailed information.\n"
                    f"Log location: {ABS_LOG_DIR}",
                    parent=root
                )
        except Exception as gui_err:
            logging.error(f"Could not show error dialog: {gui_err}")
        
        sys.exit(1)

    finally:
        # Cleanup and shutdown
        try:
            logging.info("🛑 Application shutdown initiated...")
            
            # Save any pending settings
            if app and hasattr(app, '_save_current_settings'):
                try:
                    app._save_current_settings()
                    logging.debug("Final settings save completed")
                except Exception as save_err:
                    logging.warning(f"Could not save final settings: {save_err}")
            
            # Destroy Tkinter root
            if root and root.winfo_exists():
                logging.debug("Destroying main window...")
                root.destroy()
            
            logging.info("✅ Application shutdown completed successfully")
            
        except Exception as cleanup_err:
            print(f"Cleanup error: {cleanup_err}")
            # Force exit if cleanup fails
            if root:
                try:
                    root.quit()
                except Exception:
                    pass
            sys.exit(1)
