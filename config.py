# config.py v2.1.6
# Stores configuration constants, defaults, and locators

import logging

# Try to import selenium, provide fallback values if not available
try:
    from selenium.webdriver.common.by import By  # type: ignore
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support.ui import WebDriverWait
    SELENIUM_AVAILABLE = True
except ImportError:
    print("WARNING: Selenium not installed. Using string values for locators.")
    SELENIUM_AVAILABLE = False

    # Define fallback By class when Selenium is not available
    class By:
        ID = "id"
        CSS_SELECTOR = "css selector"
        XPATH = "xpath"
        LINK_TEXT = "link text"
        TAG_NAME = "tag name"

    # Define fallback types
    WebDriver = object  # Use object instead of None for type compatibility
    WebDriverWait = object

# By is already set in try/except
ByType = By

# --- Application ---
APP_VERSION = "2.1.6"
APP_AUTHOR = "Cloud84, Una, HP, India (Refactored)"
DEFAULT_APP_NAME = "Cloud84 Black Forest Project - Tender Search Utility"

# --- New Setting Defaults ---
DEEP_SCRAPE_DEPARTMENTS_DEFAULT = False
USE_UNDETECTED_DRIVER_DEFAULT = True
HEADLESS_MODE_DEFAULT = False
DEFAULT_THEME = "clam"

# --- Configurable Timeouts List ---
CONFIGURABLE_TIMEOUTS = [
    "PAGE_LOAD_TIMEOUT", "ELEMENT_WAIT_TIMEOUT", "STABILIZE_WAIT", "POST_ACTION_WAIT",
    "POST_CAPTCHA_WAIT", "CAPTCHA_CHECK_TIMEOUT", "DOWNLOAD_WAIT_TIMEOUT", "POPUP_WAIT_TIMEOUT",
    "POST_DOWNLOAD_CLICK_WAIT"
]

# --- Available Themes ---
AVAILABLE_THEMES = ["clam", "alt", "default", "classic", "vista", "xpnative"]

# --- Default URLs (Fallback if base_urls.csv is missing/invalid) ---
FALLBACK_BASE_URL = "https://hptenders.gov.in/nicgep/app"
# FALLBACK_ORG_LIST_URL removed - will be generated from FALLBACK_BASE_URL if needed
FALLBACK_URL_KEY = "hptenders"

# --- Timeouts (seconds) ---
# These are default values. User settings might override them in the future.
PAGE_LOAD_TIMEOUT = 75
ELEMENT_WAIT_TIMEOUT = 45
STABILIZE_WAIT = 1.5
POST_ACTION_WAIT = 0.6
POST_CAPTCHA_WAIT = 3
CAPTCHA_CHECK_TIMEOUT = 5
DOWNLOAD_WAIT_TIMEOUT = 180
POPUP_WAIT_TIMEOUT = 20
POST_DOWNLOAD_CLICK_WAIT = 4.5

# --- File Paths & Naming (Relative Names/Dirs) ---
# Absolute paths will be constructed in main.py based on script location
DEFAULT_DOWNLOAD_DIR_NAME = "Tender_Downloads"
EXCEL_FILENAME_FORMAT = "{website_keyword}_tenders_{timestamp}.xlsx"
EXCEL_ID_SEARCH_FILENAME_FORMAT = "{website_keyword}_id_search_summary_{timestamp}.xlsx" # New format for ID search
SETTINGS_FILENAME = "settings.json"
BASE_URLS_FILENAME = "base_urls.csv"
LOG_DIR_NAME = "logs"

# --- Selenium Locators (Verify!) ---
# Locators for "Scrape by Department" Tab (Organisation List Page)

# Fallback locator strategies for "Tenders by Organisation" link
TENDERS_BY_ORG_LOCATORS = [
    # Primary locator (current failing one)
    (By.XPATH, "//a[@id='PageLink_0'][@title='Tenders by Organisation']"),
    # Most specific - correct href pattern for NIC websites
    (By.XPATH, "//a[contains(@href, 'FrontEndTendersByOrganisation')]"),
    # Fallback by text content (exact match)
    (By.XPATH, "//a[normalize-space(text())='Tenders by Organisation']"),
    # Fallback by partial text but more specific
    (By.XPATH, "//a[contains(text(), 'Tenders by Organisation')]"),
    # Fallback by partial text with case insensitive
    (By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'tenders by organisation')]"),
    # Backup - any link with "organisation" in href
    (By.XPATH, "//a[contains(@href, 'Organisation')]"),
    # Last resort - link text contains "organisation"
    (By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'organisation')]")
]

MAIN_TABLE_LOCATOR = (By.ID, "table")
MAIN_TABLE_BODY_LOCATOR = (By.CSS_SELECTOR, f"#{MAIN_TABLE_LOCATOR[1]} tbody")
DEPT_LIST_SNO_COLUMN_INDEX = 0
DEPT_LIST_NAME_COLUMN_INDEX = 1
DEPT_LIST_LINK_COLUMN_INDEX = 2

# Locators for Tender Details List Page (After clicking a department link)
DETAILS_TABLE_LOCATOR = (By.ID, "table")
DETAILS_TABLE_BODY_LOCATOR = (By.CSS_SELECTOR, f"#{DETAILS_TABLE_LOCATOR[1]} tbody")
DETAILS_COL_SNO = 0
DETAILS_COL_PUB_DATE = 1
DETAILS_COL_CLOSE_DATE = 2
DETAILS_COL_OPEN_DATE = 3
DETAILS_COL_TITLE_REF = 4
DETAILS_COL_ORG_CHAIN = 5
DETAILS_TITLE_LINK_XPATH = ".//a"
BACK_BUTTON_FROM_DEPT_LIST_LOCATOR = (By.ID, "PageLink_13")
DETAILS_TABLE_HEADER_FRAGMENTS = ["S.No", "Published Date", "Closing Date", "Opening Date", "Title"]

# Locators for "Search by Tender ID" Tab (Using Base Page Search)
BASE_PAGE_TENDER_ID_INPUT_LOCATOR = (By.XPATH, "/html/body/table/tbody/tr[2]/td/table/tbody/tr/td[3]/table/tbody/tr[3]/td/form/table/tbody/tr[3]/td/table/tbody/tr/td/table/tbody/tr[2]/td[1]/input")
BASE_PAGE_SEARCH_BUTTON_LOCATOR = (By.ID, "Go")

# Locators for Search Results Page
SEARCH_RESULTS_TABLE_LOCATOR = (By.ID, "table")
SEARCH_RESULTS_TABLE_BODY_LOCATOR = (By.CSS_SELECTOR, f"#{SEARCH_RESULTS_TABLE_LOCATOR[1]} tbody")
SEARCH_RESULT_TITLE_COLUMN_INDEX = 4
SEARCH_RESULT_TARGET_LINK_TEXT_FRAGMENT = "app?component=%24DirectLink"
SEARCH_RESULT_TITLE_LINK_XPATH = f".//a[contains(@href, '{SEARCH_RESULT_TARGET_LINK_TEXT_FRAGMENT}')]"

# --- Locators on Tender Details Page (Used by Search ID & Direct URL tabs) ---
TENDER_ID_ON_PAGE_LOCATOR = (By.XPATH, "//td[normalize-space(.)='Tender ID']/following-sibling::td[1]/b")
TENDER_TITLE_LOCATOR = (By.XPATH, "//td[normalize-space(.)='Tender Title']/following-sibling::td[1]")

# Locators for "View More Details" PDF functionality
VIEW_MORE_DETAILS_LINK_LOCATOR = (By.XPATH, "/html/body/div/table/tbody/tr[2]/td/table/tbody/tr/td[2]/table/tbody/tr[1]/td/a")
WORK_DESCRIPTION_LOCATOR = (By.XPATH, "//td[normalize-space(.)='Work Description:']/following-sibling::td[1]")
POPUP_CONTENT_INDICATOR_LOCATOR = (By.XPATH, "//td[contains(text(), 'Basic Details')]")

# Locators for Additional Tender Details on the main details page
TENDER_VALUE_LOCATOR = (By.XPATH, "//td[normalize-space(.)='Tender Value in ₹']/following-sibling::td[1]|//td[normalize-space(.)='Tender Value']/following-sibling::td[1]")
PRODUCT_CATEGORY_LOCATOR = (By.XPATH, "//td[normalize-space(.)='Product Category']/following-sibling::td[1]")
CONTRACT_TYPE_LOCATOR = (By.XPATH, "//td[normalize-space(.)='Contract Type']/following-sibling::td[1]")
TENDER_FEE_LOCATOR = (By.XPATH, "//td[normalize-space(.)='Tender Fee in ₹']/following-sibling::td[1]|//td[normalize-space(.)='Tender Fee']/following-sibling::td[1]")
EMD_AMOUNT_LOCATOR = (By.XPATH, "//td[normalize-space(.)='EMD Amount in ₹']/following-sibling::td[1]|//td[normalize-space(.)='EMD Amount']/following-sibling::td[1]")
INVITING_OFFICER_LOCATOR = (By.XPATH, "//td[normalize-space(.)='Inviting Officer']/following-sibling::td[1]")
INVITING_OFFICER_ADDRESS_LOCATOR = (By.XPATH, "//td[normalize-space(.)='Inviting Officer Address']/following-sibling::td[1]")
# Note: Location and Pincode might be part of "Work/Item Details" section or similar.
# These are examples; adjust if the label is different (e.g., "Location", "Site Location")
WORK_LOCATION_LOCATOR = (By.XPATH, "//td[normalize-space(.)='Location']/following-sibling::td[1]|//td[normalize-space(.)='Work/Item Site Location']/following-sibling::td[1]")
PINCODE_LOCATOR = (By.XPATH, "//td[normalize-space(.)='Pincode']/following-sibling::td[1]")

# Locators for Document Downloads section on the *main* details page
TENDER_DOCUMENTS_PARENT_TABLE_LOCATOR = (By.XPATH, "//td[contains(text(), 'Tender Documents')]/ancestor::table[contains(@class, 'tablebg')]")
NIT_DOC_TABLE_LOCATOR = (By.ID, "table")
WORK_ITEM_DOC_TABLE_LOCATOR = (By.ID, "workItemDocumenttable")
TENDER_NOTICE_LINK_XPATH = ".//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'tendernotice') and contains(normalize-space(.), '.pdf')]"
DOCUMENT_NAME_COLUMN_INDEX = 2
DOWNLOAD_AS_ZIP_LINK_LOCATOR = (By.LINK_TEXT, "Download as zip file")
CERTIFICATE_IMAGE_LOCATOR = (By.XPATH, ".//img[contains(@src, 'images/certificate.png')]")

# Locators for CAPTCHA Page Detection
CAPTCHA_IMAGE_LOCATOR = (By.CSS_SELECTOR, 'img[src*="captcha"]')
CAPTCHA_INPUT_LOCATOR = (By.CSS_SELECTOR, 'input[name*="captcha"]')
CAPTCHA_PROMPT_LOCATOR = (By.XPATH, '//*[contains(text(), "captcha")]')

# Locator for Session Timeout Restart (Used in Direct URL processing)
SESSION_TIMEOUT_RESTART_LINK_LOCATOR = (By.CSS_SELECTOR, "a#restart") # Assuming 'a' tag with id 'restart'

# --- UI Styling ---
PRIMARY_COLOR = "#800000"        # changed to maroon
SECONDARY_COLOR = "#A00000"      # slightly lighter maroon for accents
TEXT_COLOR = "#FFFFFF"
HOVER_COLOR = "#00796B"          # teal for hover/active states
STOP_BUTTON_COLOR = "#C62828"
STOP_BUTTON_ACTIVE_COLOR = "#E53935"

# --- Sound Defaults (can be overridden via env vars or settings.json) ---
# Default Windows system sound file paths - these will be used if no custom files are specified
SOUND_DING_FILE = r"C:\Windows\Media\ding.wav"
SOUND_SUCCESS_FILE = r"C:\Windows\Media\tada.wav"
SOUND_ERROR_FILE = r"C:\Windows\Media\Windows Error.wav"

# Allow disabling sounds centrally if needed
ENABLE_SOUNDS = True

# --- Logging ---
LOG_FORMAT = '%(asctime)s - %(levelname)s - [%(threadName)s:%(funcName)s] %(message)s'
LOG_LEVEL = logging.INFO

# URL patterns for validation
SITE_COMPATIBILITY_URL_PATTERN = "page=SiteComp"
TENDERS_BY_ORG_URL_PATTERN = "page=FrontEndTendersByOrganisation"
