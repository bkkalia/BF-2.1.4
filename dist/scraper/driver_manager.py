# scraper/driver_manager.py v2.1.4
# Manages Selenium WebDriver setup and configuration

import os
import logging
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions # Alias for clarity
from selenium.common.exceptions import WebDriverException, SessionNotCreatedException

try:
    import undetected_chromedriver as uc # type: ignore
    UNDETECTED_AVAILABLE = True
except ImportError: uc = None; UNDETECTED_AVAILABLE = False; logging.info("undetected-chromedriver not found, using standard ChromeDriver.")

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WDM_AVAILABLE = True
except ImportError: WDM_AVAILABLE = False; logging.warning("webdriver-manager not found. ChromeDriver must be in system PATH or specified.")

# Absolute imports from project root
from config import PAGE_LOAD_TIMEOUT, DEFAULT_DOWNLOAD_DIR_NAME # Import relative name

logger = logging.getLogger(__name__)

# --- Configuration ---
USE_UNDETECTED = UNDETECTED_AVAILABLE # Default: use UC if available
HEADLESS_MODE = False # Default: run with browser window visible

def setup_driver(initial_download_dir=None):
    """Setup and return a configured ChromeDriver instance."""
    try:
        # Check if undetected_chromedriver is available
        if not UNDETECTED_AVAILABLE:
            logger.warning("Using standard ChromeDriver - undetected_chromedriver not available")
            options = ChromeOptions()
            # Common options setup
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--disable-notifications')
            if initial_download_dir:
                prefs = {
                    "download.default_directory": initial_download_dir,
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "safebrowsing.enabled": True
                }
                options.add_experimental_option("prefs", prefs)
        else:
            if uc is not None:
                options = uc.ChromeOptions()
                # Common options setup
                options.add_argument('--disable-popup-blocking')
                options.add_argument('--disable-notifications')
                if initial_download_dir:
                    prefs = {
                        "download.default_directory": initial_download_dir,
                        "download.prompt_for_download": False,
                        "download.directory_upgrade": True,
                        "safebrowsing.enabled": True
                    }
                    options.add_experimental_option("prefs", prefs)
            else:
                raise ImportError("undetected-chromedriver is not available, cannot use uc.ChromeOptions()")
        
        # Create driver instance based on availability
        if UNDETECTED_AVAILABLE and uc is not None:
            driver_instance = uc.Chrome(options=options)
        else:
            if WDM_AVAILABLE:
                from webdriver_manager.chrome import ChromeDriverManager  # Ensure it's imported here
                service = Service(ChromeDriverManager().install())
            else:
                service = Service()
            # Always pass ChromeOptions to webdriver.Chrome
            # Ensure options is always ChromeOptions for webdriver.Chrome
            if not isinstance(options, ChromeOptions):
                chrome_options = ChromeOptions()
                # Copy arguments and experimental options from options (uc.ChromeOptions) if needed
                for arg in getattr(options, 'arguments', []):
                    chrome_options.add_argument(arg)
                for key, value in getattr(options, 'experimental_options', {}).items():
                    chrome_options.add_experimental_option(key, value)
                options = chrome_options
            driver_instance = webdriver.Chrome(service=service, options=options)
        
        return driver_instance
        
    except Exception as e:
        logger.error(f"Failed driver setup: {e}", exc_info=True)
        raise

def set_download_directory(driver, new_download_path, log_callback):
    """Uses Chrome DevTools Protocol (CDP) to change download directory."""
    if not driver: log_callback("ERROR: WebDriver not initialized for set_download_directory."); return False
    abs_path = os.path.abspath(new_download_path)
    log_callback(f"    Attempting CDP: Set download dir to: {abs_path}")
    try:
        os.makedirs(abs_path, exist_ok=True)
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": abs_path})
        log_callback(f"    CDP: Set download directory successful.")
        return True
    except WebDriverException as wde:
         if "execute_cdp_cmd" in str(wde) or "Command is not supported" in str(wde): log_callback("    ERROR: WebDriver does not support CDP command 'Page.setDownloadBehavior'."); logger.error("CDP command 'Page.setDownloadBehavior' not supported.")
         else: log_callback(f"    ERROR: Failed CDP set download dir (WebDriverException): {wde}"); logger.error("CDP setDownloadBehavior failed", exc_info=True)
         return False
    except Exception as e: log_callback(f"    ERROR: Failed CDP set download dir (Unexpected): {e}"); logger.error("Unexpected error setting download directory via CDP", exc_info=True); return False

def safe_quit_driver(driver, log_callback):
    """Safely quits the WebDriver instance if it exists."""
    if driver:
        log_callback("Closing WebDriver instance..."); logger.info("Closing WebDriver instance...")
        try: driver.quit(); logger.info("WebDriver quit successfully.")
        except Exception as e: logger.error(f"Error quitting WebDriver: {e}", exc_info=True); log_callback(f"Error closing WebDriver: {e}")
    else: logger.debug("No active WebDriver instance to quit.")

# Removed duplicate safe_quit_driver definition

# --- Example Usage (for testing this module directly) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    test_download_dir = os.path.join(os.path.dirname(__file__), '..', DEFAULT_DOWNLOAD_DIR_NAME, "driver_test") # Go up one level from scraper
    driver_instance = None # Initialize driver_instance
    try:
        logging.info("Starting driver manager test...")
        driver_instance = setup_driver(initial_download_dir=test_download_dir)
        if driver_instance:
            logging.info("Driver setup successful. Navigating to example.com...")
            driver_instance.get("https://example.com")
            logging.info(f"Page title: {driver_instance.title}")
            time.sleep(2) # Keep browser open briefly
            logging.info("Test navigation complete.")
        else:
            logging.error("Driver setup failed.")
    except Exception as e:
        logging.error(f"Error during driver manager test: {e}", exc_info=True)
    finally:
        # Ensure the driver is always quit, even if errors occur during setup/use
        if driver_instance:
            try:
                driver_instance.quit()
            except Exception: # Corrected syntax
                pass # Correctly indented
        logging.info("Driver manager test finished.")