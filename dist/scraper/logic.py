print("scraper.logic module imported")  # DEBUG

# Add project root to sys.path
import os, sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Standard library imports
import time
import pandas as pd
import logging
from datetime import datetime
import re
from urllib.parse import urljoin, urlparse

# Third-party imports - with error checking
try:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.common.exceptions import (
        NoSuchElementException, TimeoutException, WebDriverException,
        StaleElementReferenceException
    )
    SELENIUM_IMPORTED = True
except ImportError as e:
    print(f"Error importing selenium components: {e}")
    SELENIUM_IMPORTED = False
    raise

# Local imports - using absolute paths
try:
    from config import (
        APP_VERSION, PAGE_LOAD_TIMEOUT, ELEMENT_WAIT_TIMEOUT, STABILIZE_WAIT, POST_ACTION_WAIT,
        POST_CAPTCHA_WAIT, CAPTCHA_CHECK_TIMEOUT, DOWNLOAD_WAIT_TIMEOUT, POPUP_WAIT_TIMEOUT,
        POST_DOWNLOAD_CLICK_WAIT, EXCEL_FILENAME_FORMAT,
        MAIN_TABLE_LOCATOR, MAIN_TABLE_BODY_LOCATOR,
        DEPT_LIST_SNO_COLUMN_INDEX, DEPT_LIST_NAME_COLUMN_INDEX, DEPT_LIST_LINK_COLUMN_INDEX,
        DETAILS_TABLE_LOCATOR, DETAILS_TABLE_BODY_LOCATOR,
        DETAILS_COL_SNO, DETAILS_COL_PUB_DATE, DETAILS_COL_CLOSE_DATE, DETAILS_COL_OPEN_DATE,
        DETAILS_COL_TITLE_REF, DETAILS_COL_ORG_CHAIN, DETAILS_TITLE_LINK_XPATH,
        BACK_BUTTON_FROM_DEPT_LIST_LOCATOR, DETAILS_TABLE_HEADER_FRAGMENTS,
        BASE_PAGE_TENDER_ID_INPUT_LOCATOR, BASE_PAGE_SEARCH_BUTTON_LOCATOR,
        SEARCH_RESULTS_TABLE_LOCATOR, SEARCH_RESULTS_TABLE_BODY_LOCATOR,
        SEARCH_RESULT_TITLE_COLUMN_INDEX, SEARCH_RESULT_TITLE_LINK_XPATH,
        TENDER_ID_ON_PAGE_LOCATOR, TENDER_TITLE_LOCATOR,
        VIEW_MORE_DETAILS_LINK_LOCATOR, WORK_DESCRIPTION_LOCATOR, POPUP_CONTENT_INDICATOR_LOCATOR,
        TENDER_DOCUMENTS_PARENT_TABLE_LOCATOR,
        NIT_DOC_TABLE_LOCATOR, WORK_ITEM_DOC_TABLE_LOCATOR,
        TENDER_NOTICE_LINK_XPATH,
        DOCUMENT_NAME_COLUMN_INDEX, DOWNLOAD_AS_ZIP_LINK_LOCATOR,
        CERTIFICATE_IMAGE_LOCATOR,
        SESSION_TIMEOUT_RESTART_LINK_LOCATOR,
        CONTRACT_TYPE_LOCATOR, TENDER_FEE_LOCATOR, EMD_AMOUNT_LOCATOR, TENDER_VALUE_LOCATOR, WORK_LOCATION_LOCATOR, INVITING_OFFICER_LOCATOR, INVITING_OFFICER_ADDRESS_LOCATOR,
        TENDERS_BY_ORG_LOCATORS, SITE_COMPATIBILITY_URL_PATTERN, TENDERS_BY_ORG_URL_PATTERN  # Add the new constants
    )
    from utils import sanitise_filename, get_website_keyword_from_url, generate_tender_urls
    from scraper.driver_manager import setup_driver, set_download_directory, safe_quit_driver
    from scraper.actions import safe_extract_text, click_element, wait_for_downloads, save_page_as_pdf
    from scraper.captcha_handler import handle_captcha
except ImportError as e:
    print(f"Error importing local modules: {e}")
    raise

# Initialize logger before it might be used in except blocks below
logger = logging.getLogger(__name__)

# Constants for repeated strings
DEPARTMENT_NAME_KEY = 'Department Name'
TITLE_REF_KEY = "Title and Ref.No./Tender ID"
EMD_AMOUNT_KEY = 'EMD Amount'
WEBDRIVER_REQUIRED_MSG = "WebDriver instance required"
SNO_LITERAL = 'sr.no'
DEPARTMENT_NAME_LITERAL = 'department name'
ORGANISATION_NAME_LITERAL = 'organisation name'

# Header keywords to identify and skip
HEADER_SNO_KEYWORDS = ['s.no', 'sr.no', 'serial', '#']
HEADER_NAME_KEYWORDS = ['organisation name', 'department name', 'organization']

# Constants for search processing
SEARCH_ID_KEY = 'Search ID'
SEARCH_INDEX_KEY = 'Search Index'
TENDER_ID_KEY = 'Tender ID'

# Additional constants for commonly used strings
SNO_KEY = 'sr.no'
DEPARTMENT_NAME_LITERAL = 'department name'
ORGANISATION_NAME_LITERAL = 'organisation name'

# Additional constants for error messages and status
SESSION_TIMEOUT_ERROR = "session deleted"
INVALID_SESSION_ERROR = "invalid session id"
WEBDRIVER_EXCEPTION_MSG = "WebDriverException"
UNEXPECTED_ERROR_MSG = "Unexpected error"
CRITICAL_ERROR_MSG = "CRITICAL"

# --- GUI Import Check ---
# Use absolute import based on sys.path modification in main.py
try:
    from gui import gui_utils # Absolute import
    GUI_UTILS_IMPORTED = True
    logger.debug("Successfully imported gui_utils.") # logger is now defined
except ImportError:
    gui_utils = None # Define gui_utils as None if import fails
    GUI_UTILS_IMPORTED = False
    logger.warning("gui_utils could not be imported. GUI messages will be disabled in scraper logic.") # logger is now defined
except Exception as import_err:
    gui_utils = None
    GUI_UTILS_IMPORTED = False
    logger.error(f"Unexpected error importing gui_utils: {import_err}", exc_info=True) # logger is now defined

# ==============================================================================
# ==                           UTILITY FUNCTIONS                              ==
# ==============================================================================

def find_element_with_fallbacks(driver, locators, description="element", timeout=ELEMENT_WAIT_TIMEOUT, log_callback=None):
    """
    Try multiple locators in order until one succeeds.
    Returns (element, successful_locator) or (None, None) if all fail.
    """
    log_callback = log_callback or (lambda x: None)
    
    for i, locator in enumerate(locators):
        try:
            log_callback(f"  Trying locator {i+1}/{len(locators)} for {description}: {locator}")
            if hasattr(driver, 'find_element') and hasattr(WebDriverWait, '__call__'):
                element = WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable(locator)
                )
                if element:
                    log_callback(f"  ✓ Found {description} using locator {i+1}: {locator}")
                    return element, locator
        except (TimeoutException, NoSuchElementException) as e:
            log_callback(f"  ✗ Locator {i+1} failed for {description}: {e}")
            continue
        except Exception as e:
            log_callback(f"  ⚠ Unexpected error with locator {i+1} for {description}: {e}")
            continue
    
    log_callback(f"  ✗ All {len(locators)} locators failed for {description}")
    return None, None

# ==============================================================================
# ==                           DEPARTMENT SCRAPING                           ==
# ==============================================================================

def fetch_department_list_from_site(target_url, log_callback):
    """Fetches department list and estimates total tenders from the org list page."""
    driver = None; departments = []; total_tenders = 0
    log_callback(f"Worker: Fetching departments from base URL: {target_url}")
    
    try:
        log_callback("Worker: Setting up WebDriver...")
        driver = setup_driver(initial_download_dir=os.getcwd())
        
        log_callback(f"Worker: Navigating to {target_url}")
        driver.get(target_url)
        time.sleep(STABILIZE_WAIT)
        
        # Navigate to organization list page using resilient method
        log_callback("Worker: Finding Tenders by Organisation link...")
        if not navigate_to_org_list(driver, log_callback):
            raise Exception("Failed to navigate to organization list page")
            
        log_callback("Worker: Waiting for main department table...");
        try: WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(EC.presence_of_element_located(MAIN_TABLE_LOCATOR)); log_callback("Worker: Main table container located."); time.sleep(STABILIZE_WAIT / 2)
        except TimeoutException: log_callback(f"Worker: ERROR - Timeout waiting for department table at {target_url}. Check URL/locators."); raise

        log_callback("Worker: Extracting department data..."); time.sleep(STABILIZE_WAIT)
        table_body = None; rows = []
        try: table_body = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT / 2).until(EC.presence_of_element_located(MAIN_TABLE_BODY_LOCATOR)); rows = table_body.find_elements(By.TAG_NAME, "tr"); log_callback(f"Worker: Found {len(rows)} rows using tbody.")
        except (NoSuchElementException, TimeoutException):
            log_callback(f"Worker: WARN - tbody locator ({MAIN_TABLE_BODY_LOCATOR}) not found/timed out. Checking table ({MAIN_TABLE_LOCATOR}).")
            try: main_table = driver.find_element(*MAIN_TABLE_LOCATOR); rows = main_table.find_elements(By.TAG_NAME, "tr"); log_callback(f"Worker: Found {len(rows)} rows in table (fallback).")
            except Exception as fb_err: log_callback(f"Worker: ERROR - Fallback failed: {fb_err}"); raise
            if rows and rows[0].find_elements(By.TAG_NAME, "th"): log_callback("Worker: Skipped header row (<th>) in fallback."); rows = rows[1:]

        processed_rows = 0; required_cols = max(DEPT_LIST_SNO_COLUMN_INDEX, DEPT_LIST_NAME_COLUMN_INDEX, DEPT_LIST_LINK_COLUMN_INDEX) + 1
        for i, row in enumerate(rows):
            try:
                cells = row.find_elements(By.TAG_NAME, "td");
                if len(cells) < required_cols: continue
                s_no = cells[DEPT_LIST_SNO_COLUMN_INDEX].text.strip(); dept_name = cells[DEPT_LIST_NAME_COLUMN_INDEX].text.strip(); count_cell = cells[DEPT_LIST_LINK_COLUMN_INDEX]; count_text = count_cell.text.strip()
                
                # Skip header rows
                if s_no.lower() in ['s.no', 'sr.no', 'serial', '#'] or dept_name.lower() in ['organisation name', 'department name', 'organization']:
                    log_callback(f"Worker: Skipping header row: S.No='{s_no}', Name='{dept_name[:30]}'")
                    continue
                    
                if not s_no and not dept_name: continue
                dept_info = {'s_no': s_no, 'name': dept_name, 'count_text': count_text, 'has_link': False, 'processed': False, 'tenders_found': 0}
                has_link = False
                if count_text.isdigit():
                    tender_count_int = int(count_text)
                    if tender_count_int > 0:
                        total_tenders += tender_count_int
                        try: link = WebDriverWait(count_cell, 0.5).until(EC.element_to_be_clickable((By.TAG_NAME, "a"))); has_link = bool(link.is_displayed() and link.get_attribute('href'))
                        except Exception: pass # Ignore if no link
                dept_info['has_link'] = has_link; departments.append(dept_info); processed_rows += 1
            except StaleElementReferenceException: log_callback(f"Worker: WARN - Row {i+1} stale. Skipping."); continue
            except Exception as e: log_callback(f"Worker: ERROR processing row {i+1}: {e}"); logger.error(f"Error processing dept row {i+1}", exc_info=True); continue
        log_callback(f"Worker: Processed {processed_rows} rows. Found {len(departments)} depts. Est tenders: {total_tenders}")
        return departments, total_tenders
    except (TimeoutException, NoSuchElementException) as nav_err:
        log_callback(f"Worker: CRITICAL NAVIGATION ERROR: {nav_err}")
        logger.critical("Navigation error fetch_dept_list", exc_info=True)
        return None, 0
    except WebDriverException as wde:
        log_callback(f"Worker: CRITICAL WebDriver ERROR: {wde}")
        logger.critical("WebDriverException fetch_dept_list", exc_info=True)
        return None, 0
    except Exception as e:
        log_callback(f"Worker: CRITICAL UNEXPECTED ERROR: {e}")
        logger.critical("Unexpected error fetch_dept_list", exc_info=True)
        return None, 0
    finally:
        safe_quit_driver(driver, log_callback)


def _is_header_row(s_no):
    """Check if S.No indicates a header row."""
    return s_no.lower() in HEADER_SNO_KEYWORDS

def _find_target_row(driver, s_no, attempt, log_callback):
    """Find the target row for the given S.No."""
    try:
        table_body = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
            EC.presence_of_element_located(MAIN_TABLE_BODY_LOCATOR)
        )
        rows = table_body.find_elements(By.TAG_NAME, "tr")
        log_callback(f"    Attempt {attempt+1}: Check {len(rows)} rows for S.No '{s_no}'...")

        for idx, row in enumerate(rows):
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) > DEPT_LIST_SNO_COLUMN_INDEX:
                    cell_text = cells[DEPT_LIST_SNO_COLUMN_INDEX].text.strip()
                    if _is_header_row(cell_text):
                        log_callback(f"    Skip header-like row {idx}: '{cell_text}'")
                        continue
                    if cell_text == s_no:
                        log_callback(f"    Found match row index {idx}.")
                        return row
            except StaleElementReferenceException:
                log_callback(f"    WARN: Stale row {idx} (Attempt {attempt+1}). Retrying find.")
                return None
        return None
    except (TimeoutException, NoSuchElementException):
        log_callback(f"    ERROR: Table body ({MAIN_TABLE_BODY_LOCATOR}) not found att {attempt+1}.")
        return None

def _click_department_link(driver, target_row, s_no, name, log_callback):
    """Click the department link in the target row."""
    try:
        cells = target_row.find_elements(By.TAG_NAME, "td")
        if len(cells) <= DEPT_LIST_LINK_COLUMN_INDEX:
            log_callback(f"    ERROR: Row S.No {s_no} has only {len(cells)} cells.")
            return False

        link_cell = cells[DEPT_LIST_LINK_COLUMN_INDEX]
        link_element = WebDriverWait(link_cell, 5).until(
            EC.element_to_be_clickable((By.TAG_NAME, "a"))
        )
        log_callback(f"    Link found S.No '{s_no}'. Clicking...")
        return click_element(driver, link_element, f"Dept Link '{name[:20]}' (SNo:{s_no})")
    except (TimeoutException, NoSuchElementException):
        log_callback(f"    ERROR: Link not found/clickable S.No '{s_no}'.")
        return False
    except StaleElementReferenceException:
        log_callback(f"    WARN: Link cell/element stale S.No '{s_no}'. Retrying.")
        return False

def _find_and_click_dept_link(driver, dept_info, log_callback):
    """Finds and clicks the specific department link by S.No with retries."""
    s_no = dept_info['s_no']
    name = dept_info['name']
    log_callback(f"  Finding link for Dept S.No: {s_no} - {name[:30]}...")

    # Skip if this looks like a header row
    if _is_header_row(s_no):
        log_callback(f"  SKIP: S.No '{s_no}' appears to be a header row")
        return False

    attempts = 3
    for attempt in range(attempts):
        if attempt > 0:
            log_callback(f"  Retry {attempt}/{attempts-1} find link {s_no}...")
            time.sleep(STABILIZE_WAIT * attempt)

        try:
            target_row = _find_target_row(driver, s_no, attempt, log_callback)
            if target_row is None:
                if attempt == attempts - 1:
                    log_callback(f"    Final attempt failed for S.No '{s_no}'.")
                continue

            if _click_department_link(driver, target_row, s_no, name, log_callback):
                return True
            else:
                log_callback(f"    ERROR: click_element failed S.No '{s_no}' (Attempt {attempt+1}).")

        except Exception as e:
            log_callback(f"    UNEXPECTED ERROR finding/click S.No {s_no} (Att {attempt+1}): {e}")
            logger.error(f"Unexpected error find/click S.No {s_no}", exc_info=True)
            if attempt == attempts - 1:
                return False

    log_callback(f"  ERROR: Failed find/click S.No {s_no} after {attempts} attempts.")
    return False


def _scrape_tender_details(driver, department_name, base_url, log_callback):
    """ Scrapes tender details from the department's tender list page with session validation."""
    tender_data = []
    log_callback(f"  Scraping details for: {department_name}...")
    
    # Check session before starting
    try:
        driver.current_url
    except Exception as session_err:
        log_callback(f"  ERROR: Driver session invalid before scraping {department_name}: {session_err}")
        return []
    
    try:
        table = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(EC.presence_of_element_located(DETAILS_TABLE_LOCATOR))
        log_callback("    Details table located.")
        time.sleep(STABILIZE_WAIT / 2)
        
        try: 
            body = table.find_element(*DETAILS_TABLE_BODY_LOCATOR)
        except NoSuchElementException: 
            log_callback("    Details tbody not found, use table.")
            body = table
            
        rows = body.find_elements(By.TAG_NAME, "tr")
        if not rows: 
            log_callback(f"    No rows found in details table for {department_name}.")
            return []

        first_row_cells = rows[0].find_elements(By.XPATH, ".//th|.//td")
        if first_row_cells:
            if rows[0].find_elements(By.TAG_NAME, "th"): 
                log_callback("    Skipping header row (<th>).")
                rows = rows[1:]
            elif DETAILS_TABLE_HEADER_FRAGMENTS:
                first_row_text = " ".join(c.text.strip().lower() for c in first_row_cells)
                matches = [f.lower() for f in DETAILS_TABLE_HEADER_FRAGMENTS if f.lower() in first_row_text]
                if len(matches) >= 2: 
                    log_callback(f"    Skipping header row (content match: {matches}).")
                    rows = rows[1:]
                else: 
                    log_callback("    First row not matching header content.")
                    
        if not rows: 
            log_callback(f"    No data rows after header check for {department_name}.")
            return []
            
        log_callback(f"    Found {len(rows)} data rows for {department_name}.")

        processed_count = 0
        req_cols = max(DETAILS_COL_SNO, DETAILS_COL_PUB_DATE, DETAILS_COL_CLOSE_DATE, DETAILS_COL_OPEN_DATE, DETAILS_COL_TITLE_REF, DETAILS_COL_ORG_CHAIN) + 1
        
        for i, row in enumerate(rows, 1):
            data = {DEPARTMENT_NAME_KEY: department_name}
            prefix = f"    Row {i}:"
            
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < req_cols:
                    if any(c.text for c in cells): 
                        log_callback(f"{prefix} WARN - Skip: {len(cells)} cells < {req_cols}.")
                    continue
                    
                data["S.No"] = cells[DETAILS_COL_SNO].text.strip() if DETAILS_COL_SNO < len(cells) else "N/A"
                data["e-Published Date"] = cells[DETAILS_COL_PUB_DATE].text.strip() if DETAILS_COL_PUB_DATE < len(cells) else "N/A"
                data["Closing Date"] = cells[DETAILS_COL_CLOSE_DATE].text.strip() if DETAILS_COL_CLOSE_DATE < len(cells) else "N/A"
                data["Opening Date"] = cells[DETAILS_COL_OPEN_DATE].text.strip() if DETAILS_COL_OPEN_DATE < len(cells) else "N/A"
                data["Organisation Chain"] = cells[DETAILS_COL_ORG_CHAIN].text.strip() if DETAILS_COL_ORG_CHAIN < len(cells) else "N/A"

                t_id, direct_url, status_url = None, None, None
                title_text = "N/A"
                
                if DETAILS_COL_TITLE_REF < len(cells):
                    try:
                        title_cell = cells[DETAILS_COL_TITLE_REF]
                        title_text = title_cell.text.strip()
                        data[TITLE_REF_KEY] = title_text
                        
                        try: 
                            a = title_cell.find_element(By.XPATH, DETAILS_TITLE_LINK_XPATH)
                            href = a.get_attribute('href')
                        except NoSuchElementException: 
                            href = None
                            
                        if href: 
                            urls = generate_tender_urls(href, base_url)
                            direct_url = urls.get('direct_url')
                            status_url = urls.get('status_url')
                            logger.debug(f"{prefix} Processed link: {direct_url}")
                        else: 
                            logger.debug(f"{prefix} No link in title cell.")
                            
                        match = re.search(r'\[(\d{4}_[A-Z0-9_]+(?:_\d+)?)\]', title_text) or re.search(r'\[([A-Z0-9_]{5,})\]', title_text)
                        if match: 
                            t_id = match.group(1)
                            logger.debug(f"{prefix} Extracted ID: {t_id}")
                        else: 
                            logger.debug(f"{prefix} No ID pattern in title: '{title_text[:50]}...'")
                            
                    except Exception as title_err: 
                        log_callback(f"{prefix} WARN - Error processing title cell: {title_err}")
                        data[TITLE_REF_KEY] = "Error"
                else: 
                    data[TITLE_REF_KEY] = "N/A (Col Idx OOR)"

                data["Tender ID (Extracted)"] = t_id
                data["Direct URL"] = direct_url
                data["Status URL"] = status_url
                tender_data.append(data)
                processed_count += 1
                
            except StaleElementReferenceException: 
                log_callback(f"{prefix} WARN - Stale element. Skipping.")
                continue
            except Exception as row_err: 
                log_callback(f"{prefix} WARN - Unexpected row error: {row_err}")
                logger.warning(f"Error tender detail row {i}", exc_info=True)
                continue
                
        log_callback(f"  Successfully extracted details for {processed_count} tenders from {department_name}.")
        return tender_data
        
    except (TimeoutException, NoSuchElementException) as table_err: 
        log_callback(f"  ERROR: Details table ({DETAILS_TABLE_LOCATOR}) not found/timeout for {department_name}: {table_err}")
        return []
    except WebDriverException as wde: 
        # Check if it's a session error
        if "invalid session id" in str(wde).lower() or "session deleted" in str(wde).lower():
            log_callback(f"  ERROR: WebDriver session lost while scraping {department_name}: {wde}")
        else:
            log_callback(f"  ERROR: WebDriverException scraping {department_name}: {wde}")
        logger.error(f"WebDriverException scraping details {department_name}", exc_info=True)
        return []
    except Exception as e: 
        log_callback(f"  ERROR: Unexpected error scraping {department_name}: {e}")
        logger.error(f"Unexpected error scraping details {department_name}", exc_info=True)
        return []


def _click_on_page_back_button(driver, log_callback):
    """Clicks the website's 'Back' button from dept tender list with session validation."""
    log_callback("  Attempting site 'Back' button click...")
    
    # Check session before clicking
    try:
        driver.current_url
    except Exception as session_err:
        log_callback(f"  ERROR: Driver session invalid before back button click: {session_err}")
        return False
    
    if click_element(driver, BACK_BUTTON_FROM_DEPT_LIST_LOCATOR, "Dept List Back Button"):
        log_callback("    Site 'Back' button clicked.")
        time.sleep(STABILIZE_WAIT * 1.5)
        
        # Check session after clicking
        try:
            current_url = driver.current_url
        except Exception as session_err:
            log_callback(f"  ERROR: Driver session lost after back button click: {session_err}")
            return False
        
        # Check if we ended up on Site Compatibility page
        if SITE_COMPATIBILITY_URL_PATTERN in current_url:
            log_callback("    ⚠ Back button led to Site Compatibility page - recovering...")
            
            # Try to navigate directly to organization list
            base_url = current_url.split('?')[0]
            org_url = f"{base_url}?page=FrontEndTendersByOrganisation&service=page"
            log_callback(f"    Navigating directly to: {org_url}")
            
            try:
                driver.get(org_url)
                time.sleep(STABILIZE_WAIT * 2)
                
                # Verify we're on the correct page
                final_url = driver.current_url
                if TENDERS_BY_ORG_URL_PATTERN in final_url:
                    log_callback("    ✓ Successfully recovered to organization list page")
                    return True
                else:
                    log_callback(f"    ✗ Recovery failed, ended up at: {final_url}")
                    return False
                    
            except Exception as recovery_err:
                log_callback(f"    ✗ Recovery navigation failed: {recovery_err}")
                return False
        else:
            log_callback(f"    ✓ Back navigation successful, URL: {current_url}")
            return True
    else:
        log_callback("  WARN: Failed site 'Back' button click.")
        return False


def run_scraping_logic(departments_to_scrape, base_url_config, download_dir,
                      log_callback=None, progress_callback=None, timer_callback=None, 
                      status_callback=None, stop_event=None, driver=None,
                      deep_scrape=False, **kwargs):
    """Main scraping function with improved session management."""
    if not driver:
        raise ValueError("WebDriver instance required")

    # Create no-op callbacks if None provided
    log_callback = log_callback or (lambda x: None)
    progress_callback = progress_callback or (lambda *args: None) 
    timer_callback = timer_callback or (lambda x: None)
    status_callback = status_callback or (lambda x: None)
        
    start_time = datetime.now()
    try:
        total_tenders = 0
        all_tender_details = []
        processed_depts = 0

        # Navigate to org list and ensure initial page load
        log_callback("Navigating to organization list...")
        
        # Check driver session before starting
        try:
            driver.current_url  # Test if session is valid
        except Exception as session_err:
            log_callback(f"Driver session invalid at start: {session_err}")
            raise ValueError("WebDriver session is not valid")
        
        driver.get(base_url_config['OrgListURL'])
        
        # Make sure we're on the right page before starting
        if not navigate_to_org_list(driver, log_callback):
            log_callback("WARNING: Could not verify organization list page navigation")
        
        WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
            EC.presence_of_element_located(MAIN_TABLE_LOCATOR)
        )
        time.sleep(STABILIZE_WAIT)

        total_depts = len(departments_to_scrape)
        log_callback(f"Starting to process {total_depts} departments...")

        for dept_info in departments_to_scrape:
            if stop_event and stop_event.is_set():
                break

            processed_depts += 1
            dept_name = dept_info.get('name', 'Unknown')
            dept_sno = dept_info.get('s_no', 'Unknown')
            
            log_callback(f"\nProcessing department {processed_depts}/{total_depts}: {dept_name}")
            
            # Validate department info before processing
            if dept_sno.lower() in ['s.no', 'sr.no', 'serial', '#']:
                log_callback(f"SKIP: Department S.No '{dept_sno}' appears to be a header row")
                continue
                
            if dept_name.lower() in ['organisation name', 'department name', 'organization']:
                log_callback(f"SKIP: Department name '{dept_name}' appears to be a header")
                continue
            
            # Check driver session before each department
            try:
                current_url = driver.current_url
                log_callback(f"Current URL before processing: {current_url}")
            except Exception as session_err:
                log_callback(f"Driver session lost before dept {dept_name}: {session_err}")
                break  # Stop processing if session is lost
            
            # Click department link and get tender data
            if not _find_and_click_dept_link(driver, dept_info, log_callback):
                continue
                 
            time.sleep(STABILIZE_WAIT * 2)
            
            # Check session again after clicking
            try:
                driver.current_url
            except Exception as session_err:
                log_callback(f"Driver session lost after clicking dept {dept_name}: {session_err}")
                break
            
            tender_data = _scrape_tender_details(
                driver=driver,
                department_name=dept_name,
                base_url=base_url_config['BaseURL'],
                log_callback=log_callback
            )
            
            if tender_data:
                dept_tender_count = len(tender_data)
                total_tenders += dept_tender_count
                all_tender_details.extend(tender_data)
                dept_info['processed'] = True
                dept_info['tenders_found'] = dept_tender_count
                log_callback(f"Found {dept_tender_count} tenders in department {dept_name}")
                
                if progress_callback:
                    progress_callback(total_tenders, processed_depts, total_depts, None)
            else:
                log_callback(f"No tenders found/extracted from department {dept_name}")
                dept_info['processed'] = True
                dept_info['tenders_found'] = 0
            
            # Check session before navigation
            try:
                driver.current_url
            except Exception as session_err:
                log_callback(f"Driver session lost before back navigation for {dept_name}: {session_err}")
                break
            
            # Navigate back after each department with Site Compatibility recovery
            back_clicked = _click_on_page_back_button(driver, log_callback)
            if not back_clicked:
                log_callback("WARNING: Back button click failed, returning to org list URL")
                try:
                    # Check session before recovery navigation
                    driver.current_url
                    
                    driver.get(base_url_config['OrgListURL'])
                    # Ensure we navigate to the correct page
                    if not navigate_to_org_list(driver, log_callback):
                        log_callback("ERROR: Could not navigate back to organization list")
                    WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                        EC.presence_of_element_located(MAIN_TABLE_LOCATOR)
                    )
                    time.sleep(STABILIZE_WAIT * 2)
                except Exception as nav_err:
                    log_callback(f"ERROR: Failed to navigate back (session may be lost): {nav_err}")
                    break

        # Generate Excel file if we have data
        if all_tender_details:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                website_keyword = get_website_keyword_from_url(base_url_config['BaseURL'])
                excel_filename = EXCEL_FILENAME_FORMAT.format(
                    website_keyword=website_keyword,
                    timestamp=timestamp
                )
                excel_path = os.path.join(download_dir, excel_filename)
                
                # Add some derived/calculated fields
                for tender in all_tender_details:
                    try:
                        if EMD_AMOUNT_KEY in tender:
                            tender['EMD Amount (Numeric)'] = float(
                                re.sub(r'[^\d.]', '', tender[EMD_AMOUNT_KEY]) or 0
                            )
                    except: pass
                    
                # Create DataFrame and sort by department name
                df = pd.DataFrame(all_tender_details)
                if DEPARTMENT_NAME_KEY in df.columns:
                    df = df.sort_values(DEPARTMENT_NAME_KEY)
                
                # Save Excel with index=False
                df.to_excel(excel_path, index=False, engine='openpyxl')
                log_callback(f"\nSaved {len(all_tender_details)} tender details to: {excel_filename}")
                
            except Exception as excel_err:
                log_callback(f"Error saving Excel file: {excel_err}")
                logger.error(f"Excel creation error: {excel_err}", exc_info=True)
        
        status_msg = "Scraping completed"
        if stop_event and stop_event.is_set():
            status_msg = "Scraping stopped by user"
            
        log_callback(f"\n=== {status_msg} ===")
        log_callback(f"Processed {processed_depts} departments")
        log_callback(f"Total tenders found: {total_tenders}")
        status_callback(status_msg)
        timer_callback(start_time)

    except Exception as e:
        log_callback(f"Error in run_scraping_logic: {e}")
        logger.error(f"Error in run_scraping_logic: {e}", exc_info=True)
        status_callback("Error during scraping")
        timer_callback(start_time)


def process_department(dept_info, base_url_config, download_dir, driver,
                      log_callback=None, progress_callback=None, stop_event=None):
    """Process a single department and return tender data."""
    # Create no-op callbacks if None provided
    log_callback = log_callback or (lambda x: None)
    progress_callback = progress_callback or (lambda *args: None)

    try:
        if not dept_info['has_link'] or dept_info['processed']:
            log_callback(f"Skipping department {dept_info['name']}: already processed or no link")
            return None

        # Click department link
        if not _find_and_click_dept_link(driver, dept_info, log_callback):
            log_callback(f"Failed to click link for department: {dept_info['name']}")
            return None

        log_callback(f"Processing department {dept_info['name']}...")
        time.sleep(STABILIZE_WAIT)

        # Extract tender details
        tender_data = _scrape_tender_details(
            driver=driver,
            department_name=dept_info['name'],
            base_url=base_url_config['BaseURL'],
            log_callback=log_callback
        )

        if not tender_data:
            log_callback(f"No tenders found in department {dept_info['name']}")
            dept_info['processed'] = True
            dept_info['tenders_found'] = 0
            return None

        # Update department info
        dept_info['processed'] = True
        dept_info['tenders_found'] = len(tender_data)
        log_callback(f"Found {len(tender_data)} tenders in department {dept_info['name']}")

        # Click back to department list
        back_clicked = _click_on_page_back_button(driver, log_callback)
        if not back_clicked:
            log_callback("Warning: Back button click failed, returning to org list URL")
            try:
                driver.get(base_url_config['OrgListURL'])
                time.sleep(STABILIZE_WAIT)
            except Exception as nav_err:
                log_callback(f"Error navigating back: {nav_err}")
                return tender_data  # Still return data even if navigation fails

        if progress_callback:
            progress_callback(len(tender_data))

        return tender_data

    except Exception as e:
        log_callback(f"Error processing department {dept_info['name']}: {e}")
        dept_info['processed'] = False  # Mark as not processed on error
        dept_info['tenders_found'] = 0
        return None


# ==============================================================================
# ==                      TENDER ID / DIRECT URL PROCESSING                  ==
# ==============================================================================

def _find_download_links(driver, log_callback, include_zip=True, include_notice_pdfs=True):
    """Finds potential download links based on options, filters certificates."""
    doc_section = driver
    if TENDER_DOCUMENTS_PARENT_TABLE_LOCATOR:
        try: 
            doc_section = WebDriverWait(driver, 5).until(EC.presence_of_element_located(TENDER_DOCUMENTS_PARENT_TABLE_LOCATOR))
            log_callback("      Search in Tender Docs parent table.")
        except Exception: 
            log_callback(f"      WARN: Tender Docs parent ({TENDER_DOCUMENTS_PARENT_TABLE_LOCATOR}) not found. Search whole page.")
            doc_section = driver
    else: 
        log_callback("      TENDER_DOCUMENTS_PARENT_TABLE_LOCATOR not defined. Search whole page.")

    potential_links = []
    if include_zip:
        try: 
            zip_link = WebDriverWait(doc_section, 3).until(EC.element_to_be_clickable(DOWNLOAD_AS_ZIP_LINK_LOCATOR))
            log_callback("        Found 'Download as zip'.")
            potential_links.append(zip_link)
        except Exception: 
            log_callback("        'Download as zip' not found/clickable/requested.")
            
    if include_notice_pdfs:
        if NIT_DOC_TABLE_LOCATOR:
             try: 
                 nit_table = WebDriverWait(doc_section, 3).until(EC.presence_of_element_located(NIT_DOC_TABLE_LOCATOR))
                 pdf_links = nit_table.find_elements(By.XPATH, TENDER_NOTICE_LINK_XPATH)
             except Exception: 
                 pdf_links = []
             if pdf_links: 
                 log_callback(f"        Found {len(pdf_links)} TenderNotice PDFs in NIT table.")
                 potential_links.extend(pdf_links)
                 
        if WORK_ITEM_DOC_TABLE_LOCATOR:
             try: 
                 work_table = WebDriverWait(doc_section, 3).until(EC.presence_of_element_located(WORK_ITEM_DOC_TABLE_LOCATOR))
                 pdf_links = work_table.find_elements(By.XPATH, TENDER_NOTICE_LINK_XPATH)
             except Exception: 
                 pdf_links = []
             if pdf_links: 
                 log_callback(f"        Found {len(pdf_links)} TenderNotice PDFs in Work Item table.")
                 potential_links.extend(pdf_links)
                 
        if not potential_links and (not NIT_DOC_TABLE_LOCATOR or not WORK_ITEM_DOC_TABLE_LOCATOR):  
             log_callback("       Broad search for TenderNotice PDFs...")
             try: 
                 pdf_links = doc_section.find_elements(By.XPATH, TENDER_NOTICE_LINK_XPATH)
                 log_callback(f"        Found {len(pdf_links)} via broad search.")
                 potential_links.extend(pdf_links)
             except Exception as e: 
                 log_callback(f"      WARN: Broad PDF search error: {e}")

    final_links = []
    skipped_cert = 0
    log_callback(f"      Filtering {len(potential_links)} links for certificates...")
    seen = set()
    unique_potential = [x for x in potential_links if x not in seen and not seen.add(x)]  # Preserve order, make unique
    
    for link in unique_potential:
        try:
            if link.find_elements(*CERTIFICATE_IMAGE_LOCATOR): 
                logger.debug(f"        Skip cert link: '{link.text[:30]}...'")
                skipped_cert += 1
                continue
            final_links.append(link)
            logger.debug(f"        Keep link: '{link.text[:30]}...'")
        except StaleElementReferenceException: 
            log_callback("        WARN: Link stale during cert filter. Skip.")
            skipped_cert += 1
        except Exception as filter_err: 
            log_callback(f"       WARN: Error filtering cert link: {filter_err}. Include.")
            final_links.append(link)
            
    log_callback(f"      Found {len(final_links)} download links ({skipped_cert} cert links skipped).")
    return final_links


def _find_and_trigger_downloads(driver, identifier, target_subfolder, log_callback, status_callback, stop_event, download_zip, download_notice_pdfs):
    """Finds, handles CAPTCHA, clicks download links based on options, waits - optimized timing."""
    if stop_event and stop_event.is_set():
        return

    log_callback(f"  🚀 Starting downloads for '{identifier}' -> Target: {os.path.basename(target_subfolder)}")
    if not set_download_directory(driver, target_subfolder, log_callback):
        log_callback(f"    ⚠️ Failed set download dir '{os.path.basename(target_subfolder)}'. Downloads may go elsewhere.")

    initial_links = _find_download_links(driver, log_callback, include_zip=download_zip, include_notice_pdfs=download_notice_pdfs)
    if not initial_links:
        log_callback(f"    ℹ️ No download links found matching options for '{identifier}'.")
        return

    first_link = initial_links[0]
    first_desc = f"'{first_link.text.strip()[:30]}...'" if first_link.text else "first link"
    log_callback(f"    🔍 Attempt initial click {first_desc} for CAPTCHA check...")
    first_click_ok = click_element(driver, first_link, f"Initial Download Link ({first_desc})")

    if first_click_ok:
        log_callback(f"    ✅ Clicked {first_desc}. Quick CAPTCHA check...")
        # Reduced CAPTCHA wait time from CAPTCHA_CHECK_TIMEOUT to 3 seconds
        time.sleep(3)
    else:
        log_callback(f"    ⚠️ Failed initial click {first_desc}. CAPTCHA check might be skipped.")

    # Optimized CAPTCHA handling - skip for first-time "View More Details" PDFs
    captcha_handled = False
    if not stop_event.is_set():
        # Check if this is a "View More Details" PDF (doesn't need CAPTCHA on first access)
        is_more_details_pdf = "_more_details" in identifier.lower()

        if is_more_details_pdf:
            log_callback(f"    ℹ️ Skipping CAPTCHA for 'More Details' PDF (first-time access)")
            captcha_handled = True  # Mark as handled to proceed
        else:
            log_callback(f"    🔐 Checking for CAPTCHA requirements for '{identifier}'...")
            captcha_handled = handle_captcha(driver, identifier, log_callback, status_callback, stop_event)

        # Check if user cancelled via stop_event
        if stop_event.is_set():
            log_callback(f"    🛑 User cancelled scraping for '{identifier}' via CAPTCHA dialog")
            return

        if captcha_handled is False:
            log_callback(f"    ❌ CAPTCHA handling failed or cancelled for '{identifier}'")
            return

    log_callback(f"    🔄 Re-finding download links for '{identifier}' post-CAPTCHA check...")
    final_links = _find_download_links(driver, log_callback, include_zip=download_zip, include_notice_pdfs=download_notice_pdfs)
    if not final_links:
        log_callback(f"    ℹ️ No links found after re-scan for '{identifier}'.")
        if first_click_ok and not captcha_handled:
            log_callback(f"    ⏳ Wait for potential download from initial click...")
            wait_for_downloads(target_subfolder, timeout=30)  # Reduced from 60s to 30s
        return

    if not set_download_directory(driver, target_subfolder, log_callback):
        log_callback(f"    ⚠️ Failed re-set download dir before loop for '{identifier}'.")

    status_callback(f"📥 Attempt {len(final_links)} downloads: {identifier[:25]}...")
    download_count = 0
    for idx, link in enumerate(final_links):
        if stop_event.is_set():
            log_callback("    🛑 Stop requested during download loop.")
            break
        link_name = f"link_{idx+1}"
        try:
            lname = link.text.strip()
            if lname:
                link_name=lname
        except Exception as e:
            pass # Keep default name
        log_callback(f"    📄 Attempt download {idx+1}/{len(final_links)}: '{link_name[:50]}...'")
        try:
            if click_element(driver, link, f"Download Link '{link_name[:30]}'"):
                download_count += 1
                # Reduced post-download wait from POST_DOWNLOAD_CLICK_WAIT to 1 second
                time.sleep(1)
            else:
                log_callback(f"    ⚠️ Failed click download link '{link_name[:50]}...'. Skip.")
        except StaleElementReferenceException:
            log_callback(f"    ⚠️ Link '{link_name[:50]}...' stale before click. Skip.")
            continue
        except Exception as click_err:
            log_callback(f"    ❌ ERROR click download '{link_name[:50]}...': {click_err}")
            logger.error(f"Error click download '{link_name}'", exc_info=True)

    if download_count > 0 or first_click_ok:
        log_callback(f"    ✅ Finished attempts (initiated {download_count} in loop + pot. first). Wait downloads complete...")
        wait_for_downloads(target_subfolder, timeout=30)  # Reduced from default to 30s
        log_callback(f"    🎉 Download wait finished for '{identifier}'.")
    elif len(final_links) > 0:
        log_callback(f"    ℹ️ No downloads initiated despite {len(final_links)} links found.")


def _perform_tender_processing(driver, identifier, base_download_dir, log_callback, status_callback, stop_event, dl_more_details=True, dl_zip=True, dl_notice_pdfs=True):
    """Core logic for processing a single tender page - IMMEDIATE DOWNLOAD START."""
    if stop_event.is_set(): return False
    log_callback(f"  ⚡ Processing details page for: {identifier}")

    try:
        # Wait for key elements to confirm page load - reduced timeout
        WebDriverWait(driver, 5).until(EC.any_of(
            EC.presence_of_element_located(TENDER_ID_ON_PAGE_LOCATOR),
            EC.presence_of_element_located(TENDER_TITLE_LOCATOR),
            EC.presence_of_element_located(NIT_DOC_TABLE_LOCATOR),
            EC.presence_of_element_located(WORK_ITEM_DOC_TABLE_LOCATOR)
        ))
        log_callback(f"    ✅ Page loaded for {identifier}")

        # IMMEDIATE DOWNLOAD START - just 1 second wait as requested
        time.sleep(1)
        log_callback(f"    🚀 Starting downloads immediately...")

    except TimeoutException:
        log_callback(f"  ❌ Timeout waiting for page elements for {identifier}")
        try:
            fname=f"error_page_load_{sanitise_filename(identifier)}.html"
            fpath=os.path.join(base_download_dir, fname)
            with open(fpath,'w',encoding='utf-8') as f:
                f.write(driver.page_source)
            log_callback(f"    💾 Saved error page: {fname}")
        except Exception as save_err:
            log_callback(f"    ⚠️ Could not save error page: {save_err}")
        return False

    # Quick tender ID extraction
    tender_id = safe_extract_text(driver, TENDER_ID_ON_PAGE_LOCATOR, "Tender ID", quick_mode=True)
    if not tender_id:
        title = safe_extract_text(driver, TENDER_TITLE_LOCATOR, "Tender Title", quick_mode=True)
        if title:
            match = re.search(r'(\d{4}_[A-Z0-9_]+(?:_\d+)?)', title) or re.search(r'([A-Z0-9_]{6,})', title)
            if match:
                tender_id = match.group(1)
                log_callback(f"    🆔 Extracted ID: {tender_id}")

    folder_base = tender_id if tender_id else identifier
    folder_name = sanitise_filename(folder_base)
    tender_subfolder = os.path.join(base_download_dir, folder_name)
    try:
        os.makedirs(tender_subfolder, exist_ok=True)
    except OSError as fe:
        log_callback(f"    ❌ Cannot create subfolder '{tender_subfolder}': {fe}. Using base dir.")
        tender_subfolder = base_download_dir

    # Handle 'View More Details' PDF download - ULTRA FAST
    if dl_more_details:
        try:
            log_callback("    🔍 Finding 'View More Details' link...")
            # IMMEDIATE link detection - 1 second timeout
            more_details_link = WebDriverWait(driver, 1).until(
                EC.element_to_be_clickable(VIEW_MORE_DETAILS_LINK_LOCATOR)
            )
            if more_details_link:
                log_callback("    ✅ Found 'View More Details' link. Clicking...")
                if click_element(driver, more_details_link, "View More Details Link"):
                    try:
                        # Wait for popup content - reduced to 3 seconds
                        WebDriverWait(driver, 3).until(
                            EC.presence_of_element_located(POPUP_CONTENT_INDICATOR_LOCATOR)
                        )
                        log_callback("    ✅ Popup ready")

                        # Quick document ready check - 3 seconds
                        WebDriverWait(driver, 3).until(
                            lambda d: d.execute_script("return document.readyState") == "complete"
                        )
                        log_callback("    ✅ Page ready, saving PDF...")

                        pdf_filename = f"{folder_name}_more_details.pdf"
                        pdf_filepath = os.path.join(tender_subfolder, pdf_filename)
                        log_callback(f"    💾 Saving PDF: {pdf_filename}")
                        if save_page_as_pdf(driver, pdf_filepath):
                            log_callback(f"    🎉 PDF saved: {pdf_filename}")
                        else:
                            log_callback("    ❌ PDF save failed")
                    except TimeoutException:
                        log_callback("    ❌ Popup timeout")
                    except Exception as popup_err:
                        log_callback(f"    ❌ Popup error: {type(popup_err).__name__}")
                else:
                    log_callback("    ❌ Link click failed")
            else:
                log_callback("    ℹ️ 'View More Details' link not found")
        except TimeoutException:
            log_callback("    ℹ️ 'View More Details' link not found/clickable")
        except Exception as more_err:
            log_callback(f"    ❌ 'More Details' error: {type(more_err).__name__}")
    else:
        log_callback("    ⏭️ Skip 'More Details' PDF")

    if stop_event.is_set(): return True

    # Handle document downloads if enabled - START IMMEDIATELY
    if dl_zip or dl_notice_pdfs:
        try:
            _find_and_trigger_downloads(
                driver=driver,
                identifier=identifier,
                target_subfolder=tender_subfolder,
                log_callback=log_callback,
                status_callback=status_callback,
                stop_event=stop_event,
                download_zip=dl_zip,
                download_notice_pdfs=dl_notice_pdfs
            )
        except Exception as download_err:
            log_callback(f"    ❌ Download error: {type(download_err).__name__}")
    else:
        log_callback("    ⏭️ Skip document downloads")

    log_callback(f"  ✅ Finished processing: {identifier}")
    return True


def search_and_download_tenders(tender_ids, base_url_config, download_dir, driver,
                              log_callback=None, progress_callback=None,
                              timer_callback=None, status_callback=None,
                              stop_event=None, deep_scrape=False, **kwargs):
    """Search and process tenders by ID."""
    from config import EXCEL_ID_SEARCH_FILENAME_FORMAT
    
    all_tender_details = []  # List to store all tender details
    if not driver:
        raise ValueError("WebDriver instance required")

    # Create no-op callbacks if None provided
    log_callback = log_callback or (lambda x: None)
    progress_callback = progress_callback or (lambda *args: None)
    timer_callback = timer_callback or (lambda x: None)
    status_callback = status_callback or (lambda x: None)
    
    start_time = datetime.now()

    try:
        total_tenders = len(tender_ids)
        log_callback(f"Processing {total_tenders} tender IDs...")

        for idx, tender_id in enumerate(tender_ids, 1):
            if stop_event and stop_event.is_set():
                break

            try:
                log_callback(f"Searching for tender ID: {tender_id} ({idx}/{total_tenders})")
                
                # Check driver session
                try:
                    driver.current_url
                except Exception as session_err:
                    log_callback(f"Driver session lost for {tender_id}: {session_err}")
                    continue

                # Navigate to base URL
                driver.get(base_url_config['BaseURL'])
                time.sleep(STABILIZE_WAIT)

                # Find and fill tender ID input
                id_input = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
                    EC.presence_of_element_located(BASE_PAGE_TENDER_ID_INPUT_LOCATOR)
                )
                id_input.clear()
                id_input.send_keys(tender_id)

                # Click search button
                search_button = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
                    EC.element_to_be_clickable(BASE_PAGE_SEARCH_BUTTON_LOCATOR)
                )
                search_button.click()
                time.sleep(STABILIZE_WAIT)

                # Handle search results
                try:
                    results_table = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
                        EC.presence_of_element_located(SEARCH_RESULTS_TABLE_LOCATOR)
                    )
                    # Find and click tender link
                    tender_link = results_table.find_element(By.XPATH, SEARCH_RESULT_TITLE_LINK_XPATH)
                    tender_link.click()
                    time.sleep(STABILIZE_WAIT)

                    # Process the tender details page and collect details
                    details = extract_tender_details(driver, deep_scrape=deep_scrape)
                    details[SEARCH_ID_KEY] = tender_id  # Add search ID to details
                    details[SEARCH_INDEX_KEY] = idx
                    details['Portal'] = base_url_config.get('Name', 'Unknown')
                    all_tender_details.append(details)
                    
                    _perform_tender_processing(
                        driver=driver,
                        identifier=tender_id,
                        base_download_dir=download_dir,
                        log_callback=log_callback,
                        status_callback=status_callback,
                        stop_event=stop_event,
                        dl_more_details=True,
                        dl_zip=True,
                        dl_notice_pdfs=True
                    )

                except TimeoutException:
                    log_callback(f"No results found for tender ID: {tender_id}")
                    all_tender_details.append({
                        SEARCH_ID_KEY: tender_id,
                        SEARCH_INDEX_KEY: idx,
                        'Portal': base_url_config.get('Name', 'Unknown'),
                        TENDER_ID_KEY: 'N/A',
                        'Title': 'No results found',
                        'Status': 'Not Found'
                    })
                    continue

                if progress_callback:
                    progress_callback(idx, idx, total_tenders, None)

            except Exception as e:
                log_callback(f"Error processing tender ID {tender_id}: {e}")
                all_tender_details.append({
                    SEARCH_ID_KEY: tender_id,
                    SEARCH_INDEX_KEY: idx,
                    'Portal': base_url_config.get('Name', 'Unknown'),
                    TENDER_ID_KEY: 'N/A',
                    'Title': 'Processing error',
                    'Error': str(e)
                })
                continue

        # Generate Excel file after all tenders are processed
        if all_tender_details:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                website_keyword = get_website_keyword_from_url(base_url_config['BaseURL'])
                excel_filename = f"{website_keyword}_tender_ids_{timestamp}.xlsx"
                excel_path = os.path.join(download_dir, excel_filename)
                
                # Convert details to DataFrame and save
                df = pd.DataFrame(all_tender_details)
                df = df.sort_values('Search Index')
                df.to_excel(excel_path, index=False, engine='openpyxl')
                
                log_callback(f"Saved tender details to Excel: {excel_filename}")
            except Exception as excel_err:
                log_callback(f"Error saving Excel file: {excel_err}")
        else:
            log_callback("No tender details collected to save to Excel.")

    except Exception as e:
        log_callback(f"Error in search and download process: {e}")
        raise
    finally:
        if timer_callback:
            timer_callback(start_time)

def process_direct_urls(urls, base_dir, *args, **kwargs):
    """Process a list of direct tender URLs."""
    driver = kwargs.get('driver')
    if driver is None:
        raise ValueError("WebDriver instance required")

    log_callback = kwargs.get('log_callback', lambda x: None)
    stop_event = kwargs.get('stop_event')
    status_callback = kwargs.get('status_callback', lambda x: None)
    progress_callback = kwargs.get('progress_callback', lambda *args: None)
    dl_more_details = kwargs.get('dl_more_details', True)
    dl_zip = kwargs.get('dl_zip', True)
    dl_notice_pdfs = kwargs.get('dl_notice_pdfs', True)
    
    def _handle_session_timeout(url, max_retries=3):
        """Handle session timeout by finding and clicking restart link."""
        for attempt in range(max_retries):
            try:
                restart_link = driver.find_element(By.XPATH, "//a[@id='restart']")
                if restart_link:
                    log_callback("Found session timeout. Clicking restart...")
                    restart_link.click()
                    time.sleep(STABILIZE_WAIT)
                    driver.get(url)  # Retry the original URL
                    return True
            except NoSuchElementException:
                return False  # No timeout page, continue normally
            except Exception as e:
                log_callback(f"Error during session restart (attempt {attempt+1}): {e}")
                if attempt == max_retries - 1:
                    return False
                time.sleep(STABILIZE_WAIT)
        return False

    try:
        total_urls = len(urls)
        processed = 0
        log_callback(f"Processing {total_urls} direct URLs...")

        for url in urls:
            if stop_event and stop_event.is_set():
                break

            try:
                log_callback(f"\nProcessing URL: {url}")
                driver.get(url)
                
                # Check for session timeout and handle if needed
                if _handle_session_timeout(url):
                    log_callback("Session restarted successfully.")
                
                _perform_tender_processing(
                    driver=driver,
                    identifier=url,
                    base_download_dir=base_dir,
                    log_callback=log_callback,
                    status_callback=status_callback,
                    stop_event=stop_event,
                    dl_more_details=dl_more_details,
                    dl_zip=dl_zip,
                    dl_notice_pdfs=dl_notice_pdfs
                )

                processed += 1
                if progress_callback:
                    progress_callback(processed, total_urls, total_urls, None)

            except Exception as e:
                log_callback(f"Error processing URL {url}: {e}")
                continue

        log_callback(f"\nCompleted processing {processed} of {total_urls} URLs")
        
    except Exception as e:
        log_callback(f"Error in direct URL processing: {e}")
        raise


def extract_tender_details(driver, deep_scrape=False):
    """Extracts tender details from the details page."""
    if not driver:
        raise ValueError(WEBDRIVER_REQUIRED_MSG)
        
    details = {}
    try:
        # Basic details always collected
        details.update({
            'Tender ID': safe_extract_text(driver, TENDER_ID_ON_PAGE_LOCATOR, "Tender ID"),
            'Title': safe_extract_text(driver, TENDER_TITLE_LOCATOR, "Tender Title")
        })
        
        # Additional details when deep_scrape is enabled
        if deep_scrape:
            details.update({
                'Contract Type': safe_extract_text(driver, CONTRACT_TYPE_LOCATOR, "Contract Type", quick_mode=True),
                'Payment Mode': "Online",  # Usually fixed for e-tenders
                'Tender Fee': safe_extract_text(driver, TENDER_FEE_LOCATOR, "Tender Fee", quick_mode=True),
                EMD_AMOUNT_KEY: safe_extract_text(driver, EMD_AMOUNT_LOCATOR, EMD_AMOUNT_KEY, quick_mode=True),
                'Tender Value': safe_extract_text(driver, TENDER_VALUE_LOCATOR, "Tender Value", quick_mode=True),
                'Work Description': safe_extract_text(driver, WORK_DESCRIPTION_LOCATOR, "Work Description", quick_mode=True),
                'Location': safe_extract_text(driver, WORK_LOCATION_LOCATOR, "Location", quick_mode=True),
                'Inviting Officer': safe_extract_text(driver, INVITING_OFFICER_LOCATOR, "Inviting Officer", quick_mode=True),
                'Inviting Officer Address': safe_extract_text(driver, INVITING_OFFICER_ADDRESS_LOCATOR, "Inviting Officer Address", quick_mode=True)
            })
            
            # Clean up monetary values
            for key in ['Tender Fee', EMD_AMOUNT_KEY, 'Tender Value']:
                if details.get(key):
                    details[key] = details[key].replace('₹', '').strip()
                    
    except Exception as e:
        logger.error(f"Error extracting tender details: {e}")
        
    return details

def process_tender_page(driver, tender_info, deep_scrape=False):
    """Process a single tender details page."""
    try:
        # Extract basic and additional details based on deep_scrape flag
        details = extract_tender_details(driver, deep_scrape)
        tender_info.update(details)
        # Rest of the processing will be implemented here
        return True
    except Exception as e:
        logger.error(f"Error processing tender page: {e}")
        return False

def navigate_to_org_list(driver, log_callback=None):
    """Navigate to the organization list page using resilient locator strategies with wrong page detection."""
    log_callback = log_callback or (lambda x: None)
    
    try:
        current_url = driver.current_url
        log_callback(f"Worker: Current URL: {current_url}")
        
        # Check if we're already on the correct page
        if TENDERS_BY_ORG_URL_PATTERN in current_url:
            log_callback("✓ Already on 'Tenders by Organisation' page")
            return True
        
        # Check if we're on the wrong page (Site Compatibility)
        if SITE_COMPATIBILITY_URL_PATTERN in current_url:
            log_callback("⚠ Detected Site Compatibility page - navigating back to home")
            base_url = current_url.split('?')[0]  # Get base URL without parameters
            log_callback(f"Navigating to base URL: {base_url}")
            driver.get(base_url)
            time.sleep(STABILIZE_WAIT * 2)
        
        log_callback("Worker: Finding 'Tenders by Organisation' link with fallback strategies...")
        
        # Try to find the link using multiple fallback strategies
        org_link, successful_locator = find_element_with_fallbacks(
            driver, 
            TENDERS_BY_ORG_LOCATORS, 
            "'Tenders by Organisation' link",
            timeout=8,  # Shorter timeout per attempt
            log_callback=log_callback
        )
        
        if org_link:
            # Validate the link before clicking
            href = org_link.get_attribute('href')
            if href and TENDERS_BY_ORG_URL_PATTERN in href:
                log_callback(f"✓ Found correct 'Tenders by Organisation' link: {href}")
            elif href and SITE_COMPATIBILITY_URL_PATTERN in href:
                log_callback(f"✗ Link leads to Site Compatibility page, skipping: {href}")
                org_link = None
            else:
                log_callback(f"? Found link with uncertain destination: {href}")
            
            if org_link:
                log_callback(f"Found 'Tenders by Organisation' link using: {successful_locator}")
                log_callback("Clicking 'Tenders by Organisation' link...")
                org_link.click()
                time.sleep(STABILIZE_WAIT * 2)
                
                # Verify we're on the correct page after clicking
                final_url = driver.current_url
                if TENDERS_BY_ORG_URL_PATTERN in final_url:
                    log_callback("✓ Successfully navigated to 'Tenders by Organisation' page")
                    
                    # Double-check for the main table
                    try:
                        WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
                            EC.presence_of_element_located(MAIN_TABLE_LOCATOR)
                        )
                        log_callback("✓ Organization table confirmed on page")
                        return True
                    except TimeoutException:
                        log_callback("⚠ Link clicked and URL correct, but organization table not found")
                        return True  # URL is correct, give benefit of doubt
                
                elif SITE_COMPATIBILITY_URL_PATTERN in final_url:
                    log_callback("✗ Link led to Site Compatibility page instead")
                    return False
                else:
                    log_callback(f"? Link led to unexpected page: {final_url}")
                    # Try to find table anyway
                    try:
                        table = driver.find_element(*MAIN_TABLE_LOCATOR)
                        if table:
                            log_callback("✓ Found organization table on unexpected page")
                            return True
                    except NoSuchElementException:
                        pass
                    return False
                    
        else:
            log_callback("✗ Could not find 'Tenders by Organisation' link with any fallback strategy")
            
            # Last resort: check if we're already on the organization list page
            try:
                table = driver.find_element(*MAIN_TABLE_LOCATOR)
                if table:
                    log_callback("ℹ Found organization table - may already be on correct page")
                    return True
            except NoSuchElementException:
                pass
            
            # Try direct URL navigation as final fallback
            current_base = driver.current_url.split('?')[0]
            direct_org_url = f"{current_base}?page=FrontEndTendersByOrganisation&service=page"
            log_callback(f"Last resort: Direct navigation to {direct_org_url}")
            try:
                driver.get(direct_org_url)
                time.sleep(STABILIZE_WAIT * 2)
                
                # Check if this worked
                table = driver.find_element(*MAIN_TABLE_LOCATOR)
                if table:
                    log_callback("✓ Direct URL navigation successful")
                    return True
            except Exception as direct_err:
                log_callback(f"✗ Direct URL navigation failed: {direct_err}")
                
            return False
            
    except Exception as e:
        log_callback(f"Error navigating to organization list: {e}")
        logger.error(f"Error in navigate_to_org_list: {e}", exc_info=True)
        return False

def fetch_department_list_from_site_v2(target_url, log_callback=None):
    """Enhanced version: Fetches department list and estimates total tenders from the org list page."""
    driver = None
    departments = []
    total_tenders = 0
    # Use no-op function if log_callback is None
    log_callback = log_callback if log_callback is not None else lambda x: None
    log_callback(f"Worker: Fetching departments from base URL: {target_url}")

    try:
        log_callback("Worker: Setting up WebDriver...")
        driver = setup_driver(initial_download_dir=os.getcwd())

        log_callback(f"Worker: Navigating to {target_url}")
        driver.get(target_url)
        time.sleep(STABILIZE_WAIT)

        # Use the new resilient navigation method
        log_callback("Worker: Finding Tenders by Organisation link...")
        if not navigate_to_org_list(driver, log_callback):
            log_callback("Could not navigate to organization list, trying to locate department table directly...")

        log_callback("Worker: Waiting for main department table...");
        try: WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(EC.presence_of_element_located(MAIN_TABLE_LOCATOR)); log_callback("Worker: Main table container located."); time.sleep(STABILIZE_WAIT / 2)
        except TimeoutException: log_callback(f"Worker: ERROR - Timeout waiting for department table at {target_url}. Check URL/locators."); raise

        log_callback("Worker: Extracting department data..."); time.sleep(STABILIZE_WAIT)
        table_body = None; rows = []
        try: table_body = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT / 2).until(EC.presence_of_element_located(MAIN_TABLE_BODY_LOCATOR)); rows = table_body.find_elements(By.TAG_NAME, "tr"); log_callback(f"Worker: Found {len(rows)} rows using tbody.")
        except (NoSuchElementException, TimeoutException):
            log_callback(f"Worker: WARN - tbody locator ({MAIN_TABLE_BODY_LOCATOR}) not found/timed out. Checking table ({MAIN_TABLE_LOCATOR}).")
            try: main_table = driver.find_element(*MAIN_TABLE_LOCATOR); rows = main_table.find_elements(By.TAG_NAME, "tr"); log_callback(f"Worker: Found {len(rows)} rows in table (fallback).")
            except Exception as fb_err: log_callback(f"Worker: ERROR - Fallback failed: {fb_err}"); raise
            if rows and rows[0].find_elements(By.TAG_NAME, "th"): log_callback("Worker: Skipped header row (<th>) in fallback."); rows = rows[1:]

        processed_rows = 0; required_cols = max(DEPT_LIST_SNO_COLUMN_INDEX, DEPT_LIST_NAME_COLUMN_INDEX, DEPT_LIST_LINK_COLUMN_INDEX) + 1
        for i, row in enumerate(rows):
            try:
                cells = row.find_elements(By.TAG_NAME, "td");
                if len(cells) < required_cols: continue
                s_no = cells[DEPT_LIST_SNO_COLUMN_INDEX].text.strip(); dept_name = cells[DEPT_LIST_NAME_COLUMN_INDEX].text.strip(); count_cell = cells[DEPT_LIST_LINK_COLUMN_INDEX]; count_text = count_cell.text.strip()
                
                # Skip header rows
                if s_no.lower() in ['s.no', 'sr.no', 'serial', '#'] or dept_name.lower() in ['organisation name', 'department name', 'organization']:
                    log_callback(f"Worker: Skipping header row: S.No='{s_no}', Name='{dept_name[:30]}'")
                    continue
                    
                if not s_no and not dept_name: continue
                dept_info = {'s_no': s_no, 'name': dept_name, 'count_text': count_text, 'has_link': False, 'processed': False, 'tenders_found': 0}
                has_link = False
                if count_text.isdigit():
                    tender_count_int = int(count_text)
                    if tender_count_int > 0:
                        total_tenders += tender_count_int
                        try: link = WebDriverWait(count_cell, 0.5).until(EC.element_to_be_clickable((By.TAG_NAME, "a"))); has_link = bool(link.is_displayed() and link.get_attribute('href'))
                        except Exception: pass # Ignore if no link
                dept_info['has_link'] = has_link; departments.append(dept_info); processed_rows += 1
            except StaleElementReferenceException: log_callback(f"Worker: WARN - Row {i+1} stale. Skipping."); continue
            except Exception as e: log_callback(f"Worker: ERROR processing row {i+1}: {e}"); logger.error(f"Error processing dept row {i+1}", exc_info=True); continue
        log_callback(f"Worker: Processed {processed_rows} rows. Found {len(departments)} depts. Est tenders: {total_tenders}")
        return departments, total_tenders
    except WebDriverException as wde:
        log_callback(f"Worker: CRITICAL WebDriver ERROR: {wde}")
        logger.critical("WebDriverException fetch_dept_list", exc_info=True)
        return None, 0
    except Exception as e:
        log_callback(f"Worker: CRITICAL UNEXPECTED ERROR: {e}")
        logger.critical("Unexpected error fetch_dept_list", exc_info=True)
        return None, 0
    finally:
        safe_quit_driver(driver, log_callback)
