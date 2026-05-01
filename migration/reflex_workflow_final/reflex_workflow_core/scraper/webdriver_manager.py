import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

def get_driver(use_undetected=True, headless=False, download_dir=None):
    """Creates or returns a WebDriver instance with the specified configuration."""
    try:
        options = webdriver.ChromeOptions()
        
        if headless:
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
        
        # Add common arguments for stability
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-notifications')
        
        if use_undetected:
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
        
        # Add download directory preference if specified
        if download_dir:
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            }
            options.add_experimental_option("prefs", prefs)

        # Create service and driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Configure common settings
        driver.maximize_window()
        driver.implicitly_wait(10)
        
        logger.info(f"WebDriver initialized (Undetected mode: {use_undetected}, Headless: {headless})")
        return driver

    except Exception as e:
        logger.error(f"Error initializing WebDriver: {e}")
        raise

def quit_driver(driver):
    """Safely quits the WebDriver instance."""
    if driver:
        try:
            driver.quit()
            logger.info("WebDriver quit successfully")
        except Exception as e:
            logger.error(f"Error quitting WebDriver: {e}")
            try:
                driver.close()
                logger.info("WebDriver closed via fallback method")
            except:
                pass
