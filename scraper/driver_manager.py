# scraper/driver_manager.py v2.3.2
# Manages Selenium WebDriver setup and configuration

import os
import logging
import time
import threading
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

_CHROMEDRIVER_PATH = None
_CHROMEDRIVER_LOCK = threading.Lock()

# --- Configuration ---
USE_UNDETECTED = UNDETECTED_AVAILABLE # Default: use UC if available
HEADLESS_MODE = False # Default: run with browser window visible

def setup_driver(initial_download_dir=None):
    """Setup and return a configured ChromeDriver instance."""
    try:
        logger.info("Setting up Chrome WebDriver...")

        # Force use of standard ChromeDriver for better compatibility
        logger.info("Using standard ChromeDriver for better compatibility")
        options = ChromeOptions()

        # Essential Chrome options to prevent conflicts
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-features=TranslateUI')
        options.add_argument('--disable-ipc-flooding-protection')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-web-security')
        options.add_argument('--allow-running-insecure-content')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')
        options.add_argument('--ignore-certificate-errors-spki-list')
        options.add_argument('--ignore-ssl-errors-ignore-untrusted')

        # Set window size
        options.add_argument('--window-size=1920,1080')

        # Set user agent to avoid detection
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # Download preferences
        if initial_download_dir:
            logger.info(f"Setting download directory to: {initial_download_dir}")
            prefs = {
                "download.default_directory": initial_download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
                "profile.default_content_settings.popups": 0,
                "profile.default_content_setting_values.automatic_downloads": 1
            }
            options.add_experimental_option("prefs", prefs)

        # Additional experimental options
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Create service with compatible ChromeDriver version
        if WDM_AVAILABLE:
            global _CHROMEDRIVER_PATH
            with _CHROMEDRIVER_LOCK:
                if _CHROMEDRIVER_PATH:
                    logger.info("Using cached ChromeDriver path")
                    service = Service(_CHROMEDRIVER_PATH)
                else:
                    logger.info("Installing ChromeDriver using webdriver-manager...")
                    from webdriver_manager.chrome import ChromeDriverManager
                    try:
                        _CHROMEDRIVER_PATH = ChromeDriverManager().install()
                        service = Service(_CHROMEDRIVER_PATH)
                        logger.info("ChromeDriver installed successfully")
                    except Exception as version_error:
                        logger.warning(f"Could not install ChromeDriver: {version_error}")
                        _CHROMEDRIVER_PATH = None
                        service = Service()
        else:
            logger.warning("webdriver-manager not available, using default service")
            service = Service()

        logger.info("Creating Chrome WebDriver instance...")
        driver_instance = webdriver.Chrome(service=service, options=options)

        # Execute script to remove webdriver property
        driver_instance.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        logger.info("Chrome WebDriver setup completed successfully")
        return driver_instance

    except SessionNotCreatedException as snce:
        logger.error(f"Session creation failed: {snce}")
        logger.error("This usually means ChromeDriver version doesn't match Chrome version")
        logger.error("Please check Chrome version and ensure ChromeDriver is compatible")
        raise
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
