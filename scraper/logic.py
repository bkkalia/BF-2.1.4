print("scraper.logic module imported")  # DEBUG

# Add project root to sys.path
import os, sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Standard library imports
import time
import threading
import concurrent.futures
import socket
import json
import tempfile
import pandas as pd
import logging
from datetime import datetime
import re
from queue import Queue, Empty
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse

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
    from scraper.tab_manager import TabManager, setup_driver_with_tabs
    from ui_message_queue import (
        send_log, send_progress, send_complete, send_error,
        register_worker
    )
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
    from tender_store import TenderDataStore
    from scraper.driver_manager import setup_driver, set_download_directory, safe_quit_driver
    from scraper.actions import safe_extract_text, click_element, wait_for_downloads, save_page_as_pdf
    from scraper.captcha_handler import handle_captcha
    from portal_config_memory import get_portal_memory
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

PORTAL_SKILL_NIC = "NIC_SCRAPING_SKILL"
PORTAL_SKILL_GENERIC = "GENERIC_SCRAPING_SKILL"


def _sleep_with_stop(seconds, stop_event=None, step=0.2):
    remaining = max(0.0, float(seconds or 0.0))
    while remaining > 0:
        if stop_event and stop_event.is_set():
            return False
        chunk = min(step, remaining)
        time.sleep(chunk)
        remaining -= chunk
    return True


def _wait_for_presence_with_stop(driver, locator, timeout, stop_event=None, poll=0.3):
    timeout = max(0.1, float(timeout or 0.1))
    deadline = time.monotonic() + timeout
    last_error = None

    while time.monotonic() < deadline:
        if stop_event and stop_event.is_set():
            raise TimeoutException("Stop requested")
        remaining = max(0.05, deadline - time.monotonic())
        try:
            return WebDriverWait(driver, min(poll, remaining)).until(
                EC.presence_of_element_located(locator)
            )
        except TimeoutException as err:
            last_error = err

    if last_error:
        raise last_error
    raise TimeoutException(f"Timeout waiting for locator: {locator}")


def normalize_tender_id(value):
    """Normalize tender IDs for reliable matching when portal formatting varies."""
    text = str(value or "").strip()
    if not text:
        return ""

    text = re.sub(r'(?i)^\s*(tender\s*id|tenderid|id)\s*[:#\-]?\s*', '', text)
    if text.startswith('[') and text.endswith(']') and len(text) > 2:
        text = text[1:-1]

    text = text.upper().strip()
    text = re.sub(r'[\s\-\./]+', '_', text)
    text = re.sub(r'_+', '_', text).strip('_')
    return text


def normalize_closing_date(value):
    """Normalize closing-date text for stable comparisons."""
    text = str(value or "").strip().upper()
    if not text:
        return ""
    text = text.replace("-", "/").replace(".", "/")
    text = re.sub(r"\s+", " ", text)
    return text


def extract_tender_id_from_title(title_text):
    """
    Canonical tender-id extraction.

    Rule for NIC portals:
    - Prefer bracketed NIC token like [2026_DCKUL_128804_1]
    - Ignore local refs/S.No tokens when NIC token is present
    - If NIC token is not present, fallback to strongest bracket token
    """
    text = str(title_text or "").strip()
    if not text:
        return ""

    nic_match = re.search(r'\[(\d{4}_[A-Z0-9_]+(?:_\d+)?)\]', text, flags=re.IGNORECASE)
    if nic_match:
        return normalize_tender_id(nic_match.group(1))

    bracket_tokens = re.findall(r'\[([^\]]+)\]', text)
    for token in reversed(bracket_tokens):
        candidate = normalize_tender_id(token)
        if candidate and re.fullmatch(r'[A-Z0-9_]{5,}', candidate):
            return candidate

    fallback = re.search(r'(\d{4}_[A-Z0-9_]+(?:_\d+)?)', text, flags=re.IGNORECASE)
    if fallback:
        return normalize_tender_id(fallback.group(1))

    return ""


def resolve_portal_skill(base_url_config):
    """Resolve scraping skill by portal metadata/URL. Extensible for future skills."""
    portal_name = str((base_url_config or {}).get("Name", "")).strip().lower()
    base_url = str((base_url_config or {}).get("BaseURL", "")).strip().lower()
    org_list_url = str((base_url_config or {}).get("OrgListURL", "")).strip().lower()
    combined = f"{portal_name} {base_url} {org_list_url}"

    nic_indicators = [
        "eprocure",
        "tenders.gov.in",
        "nic.in",
        "tendershimachal",
        "etenders",
    ]
    if any(token in combined for token in nic_indicators):
        return PORTAL_SKILL_NIC
    return PORTAL_SKILL_GENERIC


def extract_tender_id_by_skill(title_text, portal_skill):
    """Skill-aware tender ID extraction entrypoint."""
    if portal_skill == PORTAL_SKILL_NIC:
        return extract_tender_id_from_title(title_text)
    return extract_tender_id_from_title(title_text)


def sanitize_department_direct_url(url):
    """Strip volatile session parameters from department direct URLs."""
    raw = str(url or "").strip()
    if not raw:
        return ""

    try:
        parsed = urlparse(raw)
        if not parsed.query:
            return raw

        blocked_keys = {"session", "sp", "jsessionid", "sid", "phpsessid"}
        filtered_params = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            key_norm = str(key or "").strip().lower()
            if key_norm in blocked_keys or "session" in key_norm:
                continue
            filtered_params.append((key, value))

        filtered_query = urlencode(filtered_params, doseq=True)
        cleaned = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            filtered_query,
            "",
        ))
        return cleaned or raw
    except Exception:
        return raw

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

# New: import sound helper (safe fallback)
try:
    from scraper.sound_helper import play_sound, SOUND_SUCCESS, SOUND_ERROR, SOUND_DING  # type: ignore
except Exception:
    def play_sound(kind): pass
    SOUND_SUCCESS = "success"
    SOUND_ERROR = "error"
    SOUND_DING = "ding"

# ==============================================================================
# ==                           UTILITY FUNCTIONS                              ==
# ==============================================================================

def find_element_with_fallbacks(driver, locators, description="element", timeout=ELEMENT_WAIT_TIMEOUT, log_callback=None, preferred_index=None):
    """
    Try multiple locators in order until one succeeds.
    If preferred_index is provided, tries that locator first.
    Returns (element, successful_locator) or (None, None) if all fail.
    """
    log_callback = log_callback or (lambda x: None)
    
    # Create ordered list - try preferred first if specified
    indices = list(range(len(locators)))
    if preferred_index is not None and 0 <= preferred_index < len(locators):
        log_callback(f"  Using preferred locator index {preferred_index} based on portal history")
        indices.remove(preferred_index)
        indices.insert(0, preferred_index)
    
    for i in indices:
        locator = locators[i]
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
        if not navigate_to_org_list(driver, log_callback, org_list_url=target_url):
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
                dept_info = {'s_no': s_no, 'name': dept_name, 'count_text': count_text, 'has_link': False, 'processed': False, 'tenders_found': 0, 'direct_url': ''}
                has_link = False
                direct_url = ''
                try:
                    link_candidates = count_cell.find_elements(By.TAG_NAME, "a")
                    if link_candidates:
                        direct_url = str(link_candidates[0].get_attribute('href') or '').strip()
                except Exception:
                    direct_url = ''

                if direct_url:
                    direct_url = sanitize_department_direct_url(direct_url)
                    has_link = True
                    dept_info['direct_url'] = direct_url

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
    quick_wait = min(ELEMENT_WAIT_TIMEOUT, 6 + (attempt * 2))
    try:
        table_body = WebDriverWait(driver, quick_wait).until(
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
        log_callback(f"    WARN: Table body ({MAIN_TABLE_BODY_LOCATOR}) not ready in {quick_wait}s (att {attempt+1}); trying main table fallback.")
        try:
            main_table = WebDriverWait(driver, min(quick_wait, 5)).until(
                EC.presence_of_element_located(MAIN_TABLE_LOCATOR)
            )
            rows = main_table.find_elements(By.TAG_NAME, "tr")
            log_callback(f"    Fallback: Check {len(rows)} table rows for S.No '{s_no}'...")
            for idx, row in enumerate(rows):
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) > DEPT_LIST_SNO_COLUMN_INDEX:
                        cell_text = cells[DEPT_LIST_SNO_COLUMN_INDEX].text.strip()
                        if _is_header_row(cell_text):
                            continue
                        if cell_text == s_no:
                            log_callback(f"    Found match row index {idx} (fallback).")
                            return row
                except StaleElementReferenceException:
                    return None
        except (TimeoutException, NoSuchElementException):
            pass
        log_callback(f"    ERROR: Department table not found for S.No '{s_no}' att {attempt+1}.")
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


def _navigate_department_direct_url(driver, dept_info, log_callback, base_reference_url=None):
    """Navigate directly to department tenders page using captured direct URL."""
    direct_url_raw = sanitize_department_direct_url(dept_info.get('direct_url', ''))
    if not direct_url_raw:
        return False

    try:
        current_url = driver.current_url
    except Exception as session_err:
        log_callback(f"    Direct URL skipped (session invalid): {session_err}")
        return False

    parsed_direct = urlparse(direct_url_raw)
    if parsed_direct.scheme in ("http", "https"):
        target_url = direct_url_raw
    else:
        base_url = str(base_reference_url or "").strip() or str(current_url or "").strip()
        if not base_url or base_url.lower().startswith("data:"):
            log_callback(
                f"    Direct URL skipped: invalid base URL '{base_url}' for relative direct link '{direct_url_raw}'"
            )
            return False
        target_url = urljoin(base_url, direct_url_raw)

    log_callback(f"    Direct URL attempt: {target_url}")

    try:
        driver.get(target_url)
        time.sleep(STABILIZE_WAIT)

        try:
            WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT).until(
                EC.presence_of_element_located(BACK_BUTTON_FROM_DEPT_LIST_LOCATOR)
            )
            log_callback("    ✓ Direct URL opened department page")
            return True
        except TimeoutException:
            WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT / 2).until(
                EC.presence_of_element_located(DETAILS_TABLE_LOCATOR)
            )

            landed_url = driver.current_url
            if TENDERS_BY_ORG_URL_PATTERN in landed_url and "DirectLink" not in landed_url:
                log_callback(f"    ✗ Direct URL returned to organization page: {landed_url}")
                return False

            log_callback("    ✓ Direct URL appears valid (details table detected)")
            return True
    except Exception as direct_err:
        log_callback(f"    ✗ Direct URL navigation failed: {direct_err}")
        return False


def _open_department_page(driver, dept_info, log_callback, base_reference_url=None):
    """Open department page using direct URL first, then row-click fallback."""
    has_direct = bool(str(dept_info.get('direct_url', '')).strip())
    if has_direct and _navigate_department_direct_url(driver, dept_info, log_callback, base_reference_url=base_reference_url):
        return True, "direct"

    try:
        current_url = driver.current_url
    except Exception:
        current_url = ""

    # Click flow requires the organization table context.
    if TENDERS_BY_ORG_URL_PATTERN not in str(current_url):
        if has_direct:
            log_callback("    Direct URL fallback: restoring organization list before click flow")
        else:
            log_callback("    No direct URL: ensuring organization list page before click flow")
        navigate_to_org_list(driver, log_callback, org_list_url=base_reference_url)
        time.sleep(STABILIZE_WAIT)

    if _find_and_click_dept_link(driver, dept_info, log_callback):
        return True, "click"

    return False, "failed"

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


def _js_extract_table_rows(driver):
    """Batch-extract all table rows via a single JS call.
    Returns list of {c: [cell_texts...], h: href_or_None} dicts, or None on any failure.
    Automatically skips <th>-only header rows (querySelectorAll('td') returns empty for them).
    """
    try:
        result = driver.execute_script("""
            (function() {
                var table = document.getElementById('table');
                if (!table) return null;
                var tbody = table.querySelector('tbody') || table;
                var trs = Array.from(tbody.querySelectorAll('tr'));
                var out = [];
                for (var i = 0; i < trs.length; i++) {
                    var tds = Array.from(trs[i].querySelectorAll('td'));
                    if (tds.length === 0) continue;  // skip header <th> rows
                    var texts = tds.map(function(td) {
                        return (td.innerText || td.textContent || '').replace(/\\s+/g, ' ').trim();
                    });
                    var href = null;
                    var link = trs[i].querySelector('td a');
                    if (link) href = link.href || link.getAttribute('href') || null;
                    out.push({c: texts, h: href});
                }
                return out;
            })()
        """)
        if isinstance(result, list):
            return result
        return None
    except Exception:
        return None


def _scrape_tender_details(
    driver,
    department_name,
    base_url,
    log_callback,
    existing_tender_ids=None,
    existing_tender_ids_normalized=None,
    existing_tender_snapshot=None,
    portal_skill=PORTAL_SKILL_NIC,
    stop_event=None,
):
    """ Scrapes tender details from the department's tender list page with enhanced retry logic for large tables."""
    tender_data = []
    existing_tender_ids = existing_tender_ids or set()
    if existing_tender_ids_normalized is None:
        existing_tender_ids_normalized = {
            normalize_tender_id(item)
            for item in existing_tender_ids
            if normalize_tender_id(item)
        }
    skipped_existing_count = 0
    changed_closing_date_count = 0
    existing_tender_snapshot = existing_tender_snapshot or {}
    log_callback(f"  Scraping details for: {department_name}...")

    if stop_event and stop_event.is_set():
        log_callback(f"  Stop requested before scraping rows for {department_name}.")
        return [], 0, 0
    
    # Check session before starting
    try:
        driver.current_url
    except Exception as session_err:
        log_callback(f"  ERROR: Driver session invalid before scraping {department_name}: {session_err}")
        return [], 0, 0
    
    # Maximum retries for stale element issues
    MAX_TABLE_REFETCH_RETRIES = 3
    
    for table_attempt in range(MAX_TABLE_REFETCH_RETRIES):
        if stop_event and stop_event.is_set():
            log_callback(f"  Stop requested while preparing table for {department_name}.")
            return tender_data, skipped_existing_count, changed_closing_date_count
        try:
            # Add extra stabilization wait for large tables
            if table_attempt > 0:
                log_callback(f"    Retry {table_attempt}/{MAX_TABLE_REFETCH_RETRIES-1} for table fetch...")
                if not _sleep_with_stop(STABILIZE_WAIT * 2, stop_event=stop_event):
                    return tender_data, skipped_existing_count, changed_closing_date_count
            
            table = _wait_for_presence_with_stop(driver, DETAILS_TABLE_LOCATOR, ELEMENT_WAIT_TIMEOUT, stop_event=stop_event)
            log_callback("    Details table located.")
            if not _sleep_with_stop(STABILIZE_WAIT, stop_event=stop_event):
                return tender_data, skipped_existing_count, changed_closing_date_count
            
            try: 
                body = table.find_element(*DETAILS_TABLE_BODY_LOCATOR)
            except NoSuchElementException: 
                log_callback("    Details tbody not found, use table.")
                body = table
                
            rows = body.find_elements(By.TAG_NAME, "tr")
            if not rows: 
                log_callback(f"    No rows found in details table for {department_name}.")
                return [], 0

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
                return [], 0
                
            total_rows = len(rows)
            log_callback(f"    Found {total_rows} data rows for {department_name}.")
            
            # For large tables, add progress logging every N rows
            progress_interval = 100 if total_rows > 1000 else 500

            processed_count = 0
            skipped_count = 0
            req_cols = max(DETAILS_COL_SNO, DETAILS_COL_PUB_DATE, DETAILS_COL_CLOSE_DATE, DETAILS_COL_OPEN_DATE, DETAILS_COL_TITLE_REF, DETAILS_COL_ORG_CHAIN) + 1

            # Detect actual column count from first data row for flexible handling
            actual_cols = 0
            if len(rows) > 0:
                first_data_row_cells = rows[0].find_elements(By.TAG_NAME, "td")
                actual_cols = len(first_data_row_cells)
                if actual_cols < req_cols:
                    log_callback(f"    INFO: Table has {actual_cols} columns (expected {req_cols}). Using flexible column detection.")
                    req_cols = min(req_cols, actual_cols)

            # ================================================================
            # JS FAST PATH — batch-extract all row data in ONE browser call.
            # Falls back to element-by-element mode automatically on any failure.
            # ================================================================
            _js_rows = _js_extract_table_rows(driver)
            _use_js = False
            if _js_rows is not None:
                if abs(len(_js_rows) - total_rows) <= 2:   # ≤2 tolerance for edge header rows
                    _use_js = True
                    if total_rows >= 200:
                        log_callback(f"    [JS] Fast mode: {len(_js_rows)} rows batch-extracted ({total_rows} DOM rows)")
                else:
                    log_callback(
                        f"    [JS] Row count mismatch (JS={len(_js_rows)}, DOM={total_rows}) "
                        f"\u2014 using element mode"
                    )

            if _use_js:
                for i, js_row in enumerate(_js_rows, 1):
                    if stop_event and stop_event.is_set():
                        log_callback(f"  Stop requested at JS row {i}/{len(_js_rows)}.")
                        return tender_data, skipped_existing_count, changed_closing_date_count

                    if total_rows > 1000 and i % progress_interval == 0:
                        log_callback(f"    [JS] Row {i}/{len(_js_rows)} ({int(i/len(_js_rows)*100)}%)...")

                    cells_text = js_row.get('c', []) if isinstance(js_row, dict) else []
                    href       = js_row.get('h')       if isinstance(js_row, dict) else None
                    num_cells  = len(cells_text)

                    if num_cells < 3:
                        if any(str(t).strip() for t in cells_text):
                            skipped_count += 1
                        continue

                    # Early duplicate check (title col only — fast path)
                    title_col_index    = 1 if num_cells == 3 else DETAILS_COL_TITLE_REF
                    title_text         = cells_text[title_col_index] if title_col_index < num_cells else ""
                    quick_tid          = extract_tender_id_by_skill(title_text, portal_skill) if title_text else None
                    _early_dup_checked = False  # track so final check doesn't double-count

                    if quick_tid:
                        quick_tid_norm = normalize_tender_id(quick_tid)
                        if quick_tid_norm and quick_tid_norm in existing_tender_ids_normalized:
                            _early_dup_checked = True  # this tender was handled here
                            q_close  = normalize_closing_date(cells_text[2]) if num_cells > 2 else ""
                            prev_rec = existing_tender_snapshot.get(quick_tid_norm, {})
                            p_close  = normalize_closing_date(prev_rec.get("closing_date", ""))
                            if q_close and p_close and q_close != p_close:
                                changed_closing_date_count += 1
                                # fall through — closing date changed, re-process
                            else:
                                skipped_existing_count += 1
                                continue   # exact duplicate — skip

                    # Build full data dict
                    data = {DEPARTMENT_NAME_KEY: department_name}
                    data["S.No"]             = cells_text[0] if num_cells > 0 else "N/A"
                    data["e-Published Date"] = cells_text[1] if num_cells > 1 else "N/A"
                    data["Closing Date"]     = cells_text[2] if num_cells > 2 else "N/A"
                    data["Opening Date"]     = cells_text[3] if num_cells > 3 else "N/A"

                    if num_cells == 3:
                        c1, c2 = cells_text[1], cells_text[2]
                        if re.search(r'\[.*?\]', c1):
                            data[TITLE_REF_KEY]  = c1
                            data["Closing Date"] = c2
                        else:
                            data["Closing Date"] = c1
                            data[TITLE_REF_KEY]  = c2
                        data["Opening Date"]       = "N/A"
                        data["Organisation Chain"] = "N/A"
                    else:
                        data[TITLE_REF_KEY]        = cells_text[DETAILS_COL_TITLE_REF]  if DETAILS_COL_TITLE_REF  < num_cells else "N/A"
                        data["Organisation Chain"] = cells_text[DETAILS_COL_ORG_CHAIN] if DETAILS_COL_ORG_CHAIN < num_cells else "N/A"

                    direct_url = status_url = None
                    if href:
                        urls       = generate_tender_urls(href, base_url)
                        direct_url = urls.get('direct_url')
                        status_url = urls.get('status_url')

                    final_title = data.get(TITLE_REF_KEY, "") or ""
                    t_id = extract_tender_id_by_skill(final_title, portal_skill) if final_title else None

                    # Final dup check — only runs when early check found no match in existing IDs
                    # (guards against double-counting tenders already handled above)
                    if not _early_dup_checked:
                        t_id_norm = normalize_tender_id(t_id)
                        if t_id_norm and t_id_norm in existing_tender_ids_normalized:
                            r_close  = normalize_closing_date(data.get("Closing Date", ""))
                            prev_rec = existing_tender_snapshot.get(t_id_norm, {})
                            p_close  = normalize_closing_date(prev_rec.get("closing_date", ""))
                            if r_close and p_close and r_close != p_close:
                                changed_closing_date_count += 1
                            else:
                                skipped_existing_count += 1
                                continue

                    data["Tender ID (Extracted)"] = t_id
                    data["Direct URL"]            = direct_url
                    data["Status URL"]            = status_url
                    tender_data.append(data)
                    processed_count += 1

            # ================================================================
            # ELEMENT FALLBACK — original row-by-row Selenium extraction.
            # Runs only when JS fast path was not used.
            # ================================================================
            _rows_for_element_loop = [] if _use_js else rows
            for i, row in enumerate(_rows_for_element_loop, 1):
                if stop_event and stop_event.is_set():
                    log_callback(f"  Stop requested during row scan for {department_name} at row {i}/{total_rows}.")
                    return tender_data, skipped_existing_count, changed_closing_date_count

                # Progress logging for large tables
                if total_rows > 1000 and i % progress_interval == 0:
                    log_callback(f"    Processing row {i}/{total_rows} ({int(i/total_rows*100)}%)...")
                
                data = {DEPARTMENT_NAME_KEY: department_name}
                prefix = f"    Row {i}:"
                
                # Retry logic for individual rows that experience stale element issues
                MAX_ROW_RETRIES = 2
                row_processed = False
                
                for row_attempt in range(MAX_ROW_RETRIES):
                    if stop_event and stop_event.is_set():
                        log_callback(f"{prefix} Stop requested during row retry loop.")
                        return tender_data, skipped_existing_count, changed_closing_date_count
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        
                        # Flexible column handling - extract what we can
                        num_cells = len(cells)
                        
                        # Skip rows with truly insufficient data
                        if num_cells < 3:
                            if any(c.text.strip() for c in cells):
                                if row_attempt == 0:
                                    log_callback(f"{prefix} WARN - Skip: Only {num_cells} cells, need at least 3.")
                                skipped_count += 1
                            break
                        
                        # EARLY DUPLICATE CHECK: Extract just tender ID first to skip duplicates quickly
                        # before doing expensive operations like extracting all data
                        quick_tender_id = None
                        title_col_index = 1 if num_cells == 3 else DETAILS_COL_TITLE_REF
                        if title_col_index < num_cells:
                            try:
                                title_cell = cells[title_col_index]
                                title_text = title_cell.text.strip()
                                quick_tender_id = extract_tender_id_by_skill(title_text, portal_skill)
                            except Exception:
                                pass  # Will extract properly later if not duplicate
                        
                        # Check if duplicate BEFORE extracting all data
                        if quick_tender_id:
                            quick_id_normalized = normalize_tender_id(quick_tender_id)
                            if quick_id_normalized and quick_id_normalized in existing_tender_ids_normalized:
                                quick_closing_date = ""
                                if num_cells > 2:
                                    try:
                                        quick_closing_date = normalize_closing_date(cells[2].text.strip())
                                    except Exception:
                                        quick_closing_date = ""
                                existing_record = existing_tender_snapshot.get(quick_id_normalized, {})
                                existing_closing_date = normalize_closing_date(existing_record.get("closing_date", ""))
                                if quick_closing_date and existing_closing_date and quick_closing_date != existing_closing_date:
                                    changed_closing_date_count += 1
                                else:
                                    skipped_existing_count += 1
                                    row_processed = True
                                    break  # Skip this duplicate row early, saving time
                        
                        # Not a duplicate or no tender ID found yet - proceed with full extraction
                        # Proceed with flexible extraction
                        if num_cells < req_cols and row_attempt == 0:
                            log_callback(f"{prefix} INFO - Processing with {num_cells}/{req_cols} columns (flexible mode)")
                            
                        # Extract data with bounds checking
                        data["S.No"] = cells[0].text.strip() if num_cells > 0 else "N/A"
                        data["e-Published Date"] = cells[1].text.strip() if num_cells > 1 else "N/A"
                        data["Closing Date"] = cells[2].text.strip() if num_cells > 2 else "N/A"
                        data["Opening Date"] = cells[3].text.strip() if num_cells > 3 else "N/A"
                        
                        # For 3-column tables, try different mappings
                        if num_cells == 3:
                            # Likely: S.No, Title, Date or S.No, Date, Title
                            # Check if column 1 or 2 contains tender ID pattern
                            col1_text = cells[1].text.strip()
                            col2_text = cells[2].text.strip()
                            if re.search(r'\[.*?\]', col1_text):  # Has tender ID markers
                                data[TITLE_REF_KEY] = col1_text
                                data["Closing Date"] = col2_text
                            else:
                                data["Closing Date"] = col1_text
                                data[TITLE_REF_KEY] = col2_text
                            data["Opening Date"] = "N/A"
                            data["Organisation Chain"] = "N/A"
                        else:
                            # Standard 6+ column layout
                            data[TITLE_REF_KEY] = cells[DETAILS_COL_TITLE_REF].text.strip() if DETAILS_COL_TITLE_REF < num_cells else "N/A"
                            data["Organisation Chain"] = cells[DETAILS_COL_ORG_CHAIN].text.strip() if DETAILS_COL_ORG_CHAIN < num_cells else "N/A"

                        t_id, direct_url, status_url = None, None, None
                        title_text = data.get(TITLE_REF_KEY, "N/A")
                        
                        # Try to extract link from title column
                        title_col_index = 1 if num_cells == 3 else DETAILS_COL_TITLE_REF
                        if title_col_index < num_cells:
                            try:
                                title_cell = cells[title_col_index]
                                if title_text == "N/A":  # If not set above, get it now
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
                                    
                                t_id = extract_tender_id_by_skill(title_text, portal_skill)
                                if t_id:
                                    logger.debug(f"{prefix} Extracted ID: {t_id}")
                                else: 
                                    logger.debug(f"{prefix} No ID pattern in title: '{title_text[:50]}...'")
                                    
                            except Exception as title_err: 
                                log_callback(f"{prefix} WARN - Error processing title cell: {title_err}")
                                if TITLE_REF_KEY not in data:
                                    data[TITLE_REF_KEY] = "Error"

                        # Final duplicate check (in case tender ID wasn't extractable earlier)
                        t_id_normalized = normalize_tender_id(t_id)
                        if t_id_normalized and t_id_normalized in existing_tender_ids_normalized:
                            row_closing_date = normalize_closing_date(data.get("Closing Date", ""))
                            existing_record = existing_tender_snapshot.get(t_id_normalized, {})
                            existing_closing_date = normalize_closing_date(existing_record.get("closing_date", ""))
                            if row_closing_date and existing_closing_date and row_closing_date != existing_closing_date:
                                changed_closing_date_count += 1
                            else:
                                skipped_existing_count += 1
                                row_processed = True
                                break

                        data["Tender ID (Extracted)"] = t_id
                        data["Direct URL"] = direct_url
                        data["Status URL"] = status_url
                        tender_data.append(data)
                        processed_count += 1
                        row_processed = True
                        break  # Success, exit retry loop
                        
                    except StaleElementReferenceException:
                        if row_attempt < MAX_ROW_RETRIES - 1:
                            if stop_event and stop_event.is_set():
                                return tender_data, skipped_existing_count, changed_closing_date_count
                            log_callback(f"{prefix} WARN - Stale element, retrying ({row_attempt + 1}/{MAX_ROW_RETRIES})...")
                            if not _sleep_with_stop(0.3, stop_event=stop_event):
                                return tender_data, skipped_existing_count, changed_closing_date_count
                            # Re-fetch the row from the table
                            try:
                                table = driver.find_element(*DETAILS_TABLE_LOCATOR)
                                body = table.find_element(*DETAILS_TABLE_BODY_LOCATOR) if table.find_elements(*DETAILS_TABLE_BODY_LOCATOR) else table
                                rows = body.find_elements(By.TAG_NAME, "tr")
                                if i <= len(rows):
                                    row = rows[i-1]  # Re-get the row
                                else:
                                    log_callback(f"{prefix} ERROR - Row index out of range after refetch")
                                    break
                            except Exception as refetch_err:
                                log_callback(f"{prefix} ERROR - Failed to refetch table: {refetch_err}")
                                break
                        else:
                            log_callback(f"{prefix} ERROR - Stale element persists after {MAX_ROW_RETRIES} retries. Skipping row.")
                            skipped_count += 1
                            break
                    except Exception as row_err:
                        log_callback(f"{prefix} WARN - Unexpected row error: {row_err}")
                        logger.warning(f"Error tender detail row {i}", exc_info=True)
                        skipped_count += 1
                        break
            
            log_callback(f"  Successfully extracted {processed_count} tenders from {department_name}.")
            if skipped_existing_count > 0:
                log_callback(f"  ✓ SKIPPED {skipped_existing_count} DUPLICATE tenders (already in database) from {department_name}")
            if changed_closing_date_count > 0:
                log_callback(f"  ↻ PROCESSED {changed_closing_date_count} tender(s) due to closing date change in {department_name}")
            if skipped_count > 0:
                log_callback(f"  ⚠ Skipped {skipped_count} rows due to errors or insufficient data.")
            log_callback("")  # Blank line for readability
            log_callback("*" * 80)  # Department completion separator
            log_callback("")  # Blank line
            
            return tender_data, skipped_existing_count, changed_closing_date_count
            
        except (TimeoutException, NoSuchElementException) as table_err:
            if stop_event and stop_event.is_set():
                return tender_data, skipped_existing_count, changed_closing_date_count
            if table_attempt < MAX_TABLE_REFETCH_RETRIES - 1:
                log_callback(f"  WARN: Table fetch error (attempt {table_attempt + 1}/{MAX_TABLE_REFETCH_RETRIES}): {table_err}")
                if not _sleep_with_stop(STABILIZE_WAIT * 2, stop_event=stop_event):
                    return tender_data, skipped_existing_count, changed_closing_date_count
                continue
            else:
                log_callback(f"  ERROR: Details table ({DETAILS_TABLE_LOCATOR}) not found after {MAX_TABLE_REFETCH_RETRIES} attempts for {department_name}: {table_err}")
                return [], 0, 0
        except WebDriverException as wde: 
            # Check if it's a session error
            if "invalid session id" in str(wde).lower() or "session deleted" in str(wde).lower():
                log_callback(f"  ERROR: WebDriver session lost while scraping {department_name}: {wde}")
            else:
                log_callback(f"  ERROR: WebDriverException scraping {department_name}: {wde}")
            logger.error(f"WebDriverException scraping details {department_name}", exc_info=True)
            return [], 0
        except Exception as e: 
            log_callback(f"  ERROR: Unexpected error scraping {department_name}: {e}")
            logger.error(f"Unexpected error scraping details {department_name}", exc_info=True)
            return [], 0


def _click_on_page_back_button(driver, log_callback, org_list_url=None, stop_event=None):
    """Return to organization list page.

    Strategy order:
    1) Direct navigation to OrgListURL (preferred)
    2) Site back button
    3) navigate_to_org_list fallback
    """
    log_callback("  Attempting return to organization page...")
    
    # Check session before clicking
    try:
        current_url_before = driver.current_url
    except Exception as session_err:
        log_callback(f"  ERROR: Driver session invalid before back button click: {session_err}")
        return False
    
    # Preferred: direct navigation to organization list URL
    try:
        base_url = current_url_before.split('?')[0]
        org_url = org_list_url or f"{base_url}?page=FrontEndTendersByOrganisation&service=page"
        log_callback(f"    Direct navigation first: {org_url}")
        
        if stop_event and stop_event.is_set():
            return False
        driver.get(org_url)
        if not _sleep_with_stop(STABILIZE_WAIT * 2, stop_event=stop_event):
            return False
        
        # Verify we're on the correct page
        final_url = driver.current_url
        if TENDERS_BY_ORG_URL_PATTERN in final_url:
            log_callback("    ✓ Direct navigation successful")
            
            # Verify table is present
            try:
                _wait_for_presence_with_stop(driver, MAIN_TABLE_LOCATOR, ELEMENT_WAIT_TIMEOUT, stop_event=stop_event)
                log_callback("    ✓ Direct navigation successful and organization table confirmed")
                return True
            except TimeoutException:
                log_callback("    ⚠ Table not found but URL correct")
                return True  # Give benefit of doubt
        else:
            log_callback(f"    ⚠ Direct navigation did not land on org page: {final_url}")
            
    except Exception as direct_err:
        log_callback(f"    ⚠ Direct navigation error: {direct_err}")

    # Fallback 1: try site back button
    back_button_clicked = click_element(
        driver,
        BACK_BUTTON_FROM_DEPT_LIST_LOCATOR,
        "Dept List Back Button",
        max_wait=15
    )

    if back_button_clicked:
        log_callback("    Site 'Back' button clicked.")
        if not _sleep_with_stop(STABILIZE_WAIT * 1.5, stop_event=stop_event):
            return False

        try:
            current_url = driver.current_url
        except Exception as session_err:
            log_callback(f"  ERROR: Driver session lost after back button click: {session_err}")
            return False

        if TENDERS_BY_ORG_URL_PATTERN in current_url:
            log_callback("    ✓ Back button navigation successful to Tenders by Organisation")
            return True

        try:
            table = driver.find_element(*MAIN_TABLE_LOCATOR)
            if table:
                log_callback("    ✓ Organization table found after back click")
                return True
        except NoSuchElementException:
            pass
        log_callback(f"    ⚠ Back button landed on unexpected page: {current_url}")
    else:
        log_callback("    WARN: Back button click failed.")

    # Fallback 2: robust generic navigation helper
    try:
        if navigate_to_org_list(driver, log_callback, org_list_url=org_list_url):
            log_callback("    ✓ Fallback navigate_to_org_list successful")
            return True
    except Exception as nav_err:
        log_callback(f"    ⚠ Fallback navigate_to_org_list error: {nav_err}")

    return False


def _normalize_department_task_key(dept_info):
    s_no = str((dept_info or {}).get("s_no", "")).strip().lower()
    name = str((dept_info or {}).get("name", "")).strip().lower()
    direct_url = sanitize_department_direct_url((dept_info or {}).get("direct_url", ""))

    if s_no and s_no not in HEADER_SNO_KEYWORDS:
        return f"sno::{s_no}"
    if name:
        return f"name::{name}"
    if direct_url:
        return f"url::{direct_url}"
    return ""


def _prepare_department_tasks(departments, log_callback, base_reference_url=None):
    prepared = []
    seen_task_keys = set()
    duplicate_rows = 0
    base_reference_url = str(base_reference_url or "").strip()

    for raw in departments or []:
        dept = dict(raw or {})

        direct_url = sanitize_department_direct_url(dept.get("direct_url", ""))
        if direct_url:
            parsed_direct = urlparse(direct_url)
            if parsed_direct.scheme in ("http", "https"):
                dept["direct_url"] = direct_url
            elif base_reference_url and not base_reference_url.lower().startswith("data:"):
                dept["direct_url"] = urljoin(base_reference_url, direct_url)
            else:
                dept["direct_url"] = ""

        task_key = _normalize_department_task_key(dept)
        if task_key and task_key in seen_task_keys:
            duplicate_rows += 1
            continue
        if task_key:
            seen_task_keys.add(task_key)
        prepared.append(dept)

    direct_url_buckets = {}
    for index, dept in enumerate(prepared):
        direct_url = sanitize_department_direct_url(dept.get("direct_url", ""))
        if not direct_url:
            continue
        direct_url_buckets.setdefault(direct_url, []).append(index)

    ambiguous_direct_count = 0
    for _url, indices in direct_url_buckets.items():
        if len(indices) <= 1:
            continue
        for idx in indices:
            prepared[idx]["direct_url"] = ""
        ambiguous_direct_count += len(indices)

    if duplicate_rows > 0:
        log_callback(f"De-dup task filter removed {duplicate_rows} duplicate department row(s).")
    if ambiguous_direct_count > 0:
        log_callback(
            f"Direct URL safety: disabled ambiguous direct-link navigation for {ambiguous_direct_count} department row(s); using row-click fallback."
        )

    return prepared


def _build_worker_assignments(departments, worker_count):
    """
    Distribute departments across workers using smart load balancing.
    
    CRITICAL: Time is dominated by per-department overhead (navigation, page load)
    NOT by tender count. Use a hybrid formula that heavily weights department count.
    
    Formula: estimated_time = (dept_count * FIXED_OVERHEAD) + (tender_count * PER_TENDER_TIME)
    Where FIXED_OVERHEAD (~30s) >> PER_TENDER_TIME (~0.5s)
    
    Args:
        departments: List of department dictionaries with 'count_text' field
        worker_count: Number of workers to distribute across
        
    Returns:
        List of department lists, one per worker
    """
    worker_count = max(1, int(worker_count or 1))
    if worker_count == 1:
        return [departments or []]
    
    # Empirical constants based on actual performance data
    # Per-department overhead: navigation (15s) + page load (10s) + parsing (5s) = 30s
    DEPT_OVERHEAD_SECONDS = 30.0
    # Per-tender scraping time: ~0.5s average
    PER_TENDER_SECONDS = 0.5
    
    # Calculate realistic estimated time for each department
    departments_with_estimates = []
    for dept in (departments or []):
        count_text = str(dept.get('count_text', '0')).strip()
        tender_count = int(count_text) if count_text.isdigit() else 0
        
        # Hybrid formula: department overhead dominates
        estimated_time = DEPT_OVERHEAD_SECONDS + (tender_count * PER_TENDER_SECONDS)
        departments_with_estimates.append((dept, tender_count, estimated_time))
    
    # Sort by estimated time descending (largest jobs first for better balancing)
    departments_with_estimates.sort(key=lambda x: x[2], reverse=True)
    
    # Initialize workers with empty lists and track their total estimated time
    worker_times = [0.0] * worker_count
    worker_dept_counts = [0] * worker_count
    worker_tender_counts = [0] * worker_count
    assignments = [[] for _ in range(worker_count)]
    
    # Greedy assignment: Always assign next department to least-loaded worker (by time)
    for dept, tender_count, estimated_time in departments_with_estimates:
        # Find worker with minimum estimated time
        min_time_idx = worker_times.index(min(worker_times))
        assignments[min_time_idx].append(dept)
        worker_times[min_time_idx] += estimated_time
        worker_dept_counts[min_time_idx] += 1
        worker_tender_counts[min_time_idx] += tender_count
    
    # Log the load distribution for verification
    logger.debug(f"Smart load balancing (time-based): Worker times = {[f'{t:.0f}s' for t in worker_times]}")
    logger.debug(f"  Dept counts: {worker_dept_counts}, Tender counts: {worker_tender_counts}")
    
    return assignments


def _write_department_links_snapshot(portal_name, departments, assignments, log_callback):
    try:
        safe_portal = sanitise_filename(str(portal_name or "portal")) or "portal"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_dir = os.path.join(tempfile.gettempdir(), "blackforest_department_links")
        os.makedirs(target_dir, exist_ok=True)
        path = os.path.join(target_dir, f"{safe_portal}_dept_links_{stamp}.json")

        payload = {
            "portal": portal_name,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "department_count": len(departments or []),
            "departments": [
                {
                    "s_no": str(item.get("s_no", "")).strip(),
                    "name": str(item.get("name", "")).strip(),
                    "direct_url": str(item.get("direct_url", "")).strip(),
                    "count_text": str(item.get("count_text", "")).strip(),
                }
                for item in (departments or [])
            ],
            "worker_assignments": {
                f"W{idx + 1}": [
                    {
                        "s_no": str(item.get("s_no", "")).strip(),
                        "name": str(item.get("name", "")).strip(),
                        "direct_url": str(item.get("direct_url", "")).strip(),
                    }
                    for item in bucket
                ]
                for idx, bucket in enumerate(assignments or [])
            },
        }

        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

        log_callback(f"Department links snapshot saved: {path}")
        return path
    except Exception as snapshot_err:
        log_callback(f"WARNING: Could not save department links snapshot: {snapshot_err}")
        return None


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
    total_tenders = 0
    all_tender_details = []
    processed_depts = 0
    existing_tender_ids = set(kwargs.get("existing_tender_ids") or [])
    existing_tender_ids_normalized = {
        normalize_tender_id(item)
        for item in existing_tender_ids
        if normalize_tender_id(item)
    }
    existing_tender_snapshot_raw = kwargs.get("existing_tender_snapshot") or {}
    existing_tender_snapshot = {}
    if isinstance(existing_tender_snapshot_raw, dict):
        for key, value in existing_tender_snapshot_raw.items():
            normalized_id = normalize_tender_id(key)
            if not normalized_id:
                continue
            value_dict = value if isinstance(value, dict) else {}
            existing_tender_snapshot[normalized_id] = {
                "closing_date": normalize_closing_date(value_dict.get("closing_date", ""))
            }
    existing_department_names = {
        str(name).strip().lower()
        for name in (kwargs.get("existing_department_names") or [])
        if str(name).strip()
    }
    skipped_existing_total = 0
    closing_date_reprocessed_total = 0
    skipped_resume_departments = 0
    expected_total_tenders = 0
    department_summaries = []
    processed_department_names = set()
    direct_nav_attempted = 0
    direct_nav_success = 0
    direct_nav_fallback_click = 0
    click_only_success = 0
    
    # Timing statistics for comprehensive summary
    total_nav_time = 0.0
    total_scrape_time = 0.0
    total_dept_processing_time = 0.0
    browser_init_time_total = 0.0
    portal_name = str(base_url_config.get('Name', 'Unknown')).strip() or "Unknown"
    portal_base_url = str(base_url_config.get('BaseURL', '')).strip()
    portal_skill = resolve_portal_skill(base_url_config)
    scope_mode = "only_new" if existing_tender_ids or existing_department_names else "all"
    departments_to_scrape = _prepare_department_tasks(
        departments_to_scrape,
        log_callback,
        base_reference_url=base_url_config.get('OrgListURL') or base_url_config.get('BaseURL')
    )
    log_callback(f"[SKILL] Using {portal_skill} for portal '{portal_name}'")

    try:
        portal_host = (urlparse(portal_base_url).hostname or "").strip().lower()
        if portal_host:
            try:
                portal_ip = socket.gethostbyname(portal_host)
                log_callback(f"[NETWORK] Portal host: {portal_host} | IP: {portal_ip}")
            except Exception as dns_err:
                log_callback(f"[NETWORK] Portal host: {portal_host} | IP lookup failed: {dns_err}")
    except Exception:
        pass

    sqlite_db_path = kwargs.get("sqlite_db_path") or os.path.join(download_dir, "blackforest_tenders.sqlite3")
    sqlite_backup_dir = kwargs.get("sqlite_backup_dir")
    sqlite_backup_retention_days = kwargs.get("sqlite_backup_retention_days", 30)
    raw_export_policy = str(kwargs.get("export_policy", "on_demand") or "on_demand").strip().lower()
    export_policy = raw_export_policy if raw_export_policy in {"on_demand", "always", "alternate_days"} else "on_demand"
    try:
        export_interval_days = max(1, int(kwargs.get("export_interval_days", 2) or 2))
    except Exception:
        export_interval_days = 2
    force_excel_export = bool(kwargs.get("force_excel_export", False))

    # --- Checkpoint setup (resume on kill/crash) ---
    _portal_slug = re.sub(r'[^\w]+', '_', portal_name.lower()).strip('_') or 'portal'
    _checkpoint_dir = os.path.join(os.path.dirname(os.path.abspath(sqlite_db_path or 'data')), 'checkpoints')
    _checkpoint_path = os.path.join(_checkpoint_dir, f'{_portal_slug}_checkpoint.json')
    _ckpt_stop_event = threading.Event()
    _ckpt_thread = None
    try:
        os.makedirs(_checkpoint_dir, exist_ok=True)
    except Exception:
        _checkpoint_path = None

    # Load existing checkpoint if it exists (auto-resume after kill)
    if _checkpoint_path and os.path.exists(_checkpoint_path):
        try:
            with open(_checkpoint_path, 'r', encoding='utf-8') as _f:
                _ckpt = json.load(_f)
            if _ckpt.get('portal_name', '').lower() == portal_name.lower():
                _ckpt_tenders = _ckpt.get('tenders', [])
                _ckpt_depts = set(_ckpt.get('processed_departments', []))
                if _ckpt_tenders:
                    all_tender_details.extend(_ckpt_tenders)
                    total_tenders = len(all_tender_details)
                    existing_department_names.update(_ckpt_depts)
                    for _t in _ckpt_tenders:
                        _tid = str(_t.get('Tender ID (Extracted)', '')).strip()
                        if _tid:
                            existing_tender_ids.add(_tid)
                            _norm = normalize_tender_id(_tid)
                            if _norm:
                                existing_tender_ids_normalized.add(_norm)
                    log_callback(
                        f"[CHECKPOINT] Resumed: loaded {len(_ckpt_tenders)} tenders, "
                        f"{len(_ckpt_depts)} departments already done from previous run"
                    )
            else:
                log_callback(f"[CHECKPOINT] Stale checkpoint (portal mismatch) — ignored")
        except Exception as _ckpt_load_err:
            log_callback(f"[CHECKPOINT] Could not load checkpoint: {_ckpt_load_err}")

    data_store = None
    sqlite_run_id = None

    try:
        data_store = TenderDataStore(sqlite_db_path)
        try:
            backup_path = data_store.backup_if_due(
                backup_dir=sqlite_backup_dir,
                retention_days=int(sqlite_backup_retention_days or 30)
            )
            if backup_path:
                log_callback(f"[PERSIST] SQLite backup created: {backup_path}")
        except Exception as backup_err:
            log_callback(f"[PERSIST][WARN] SQLite backup skipped: {backup_err}")
        sqlite_run_id = data_store.start_run(
            portal_name=portal_name,
            base_url=base_url_config.get('BaseURL', ''),
            scope_mode=scope_mode
        )
        log_callback("[PERSIST] SQLite datastore active")
        log_callback(f"[PERSIST] SQLite DB path: {sqlite_db_path}")
        log_callback(f"[PERSIST] SQLite run id: {sqlite_run_id}")
    except Exception as ds_err:
        log_callback(f"WARNING: SQLite datastore unavailable ({ds_err}). Falling back to direct file export.")
        log_callback(f"[PERSIST] SQLite DB path (unavailable): {sqlite_db_path}")
        data_store = None
        sqlite_run_id = None

    def _should_export_snapshot(mark_partial=False):
        if force_excel_export:
            return True, "forced"
        if data_store is None:
            return True, "sqlite_unavailable"
        if mark_partial:
            return False, "partial_skip_by_policy"
        if export_policy == "always":
            return True, "policy_always"
        if export_policy == "on_demand":
            return False, "policy_on_demand"

        snapshot = data_store.get_portal_status_snapshot(portal_name=portal_name)
        last_export_at_text = str(snapshot.get("last_excel_export_at") or "").strip()
        if not last_export_at_text:
            return True, "alternate_days_first_export"

        try:
            last_export_at = datetime.fromisoformat(last_export_at_text)
            days_since = (datetime.now() - last_export_at).total_seconds() / 86400.0
            if days_since >= float(export_interval_days):
                return True, f"alternate_days_due_{export_interval_days}"
            return False, f"alternate_days_not_due_{days_since:.1f}"
        except Exception:
            return True, "alternate_days_invalid_last_export"

    def _save_tender_data_snapshot(data_to_save, mark_partial=False):
        """Save extracted tenders to Excel (or CSV fallback) and return save metadata."""
        if not data_to_save:
            return None, None
        try:
            should_export, export_reason = _should_export_snapshot(mark_partial=mark_partial)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            website_keyword = get_website_keyword_from_url(base_url_config['BaseURL'])
            suffix = "_partial" if mark_partial else ""
            excel_filename = EXCEL_FILENAME_FORMAT.format(
                website_keyword=f"{website_keyword}{suffix}",
                timestamp=timestamp
            )
            target_dir = download_dir
            excel_path = os.path.join(target_dir, excel_filename)

            try:
                os.makedirs(target_dir, exist_ok=True)
            except Exception as dir_err:
                log_callback(f"ERROR: Cannot create download directory: {dir_err}")
                fallback_dir = os.path.join(os.path.expanduser("~"), "Downloads", "Tender_Downloads")
                log_callback(f"Using fallback directory: {fallback_dir}")
                os.makedirs(fallback_dir, exist_ok=True)
                target_dir = fallback_dir
                excel_path = os.path.join(target_dir, excel_filename)

            try:
                test_file = os.path.join(target_dir, '.write_test')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except PermissionError:
                log_callback(f"ERROR: No write permission for {target_dir}")
                import tempfile
                fallback_dir = os.path.join(tempfile.gettempdir(), "Tender_Downloads")
                os.makedirs(fallback_dir, exist_ok=True)
                log_callback(f"Using temp directory: {fallback_dir}")
                target_dir = fallback_dir
                excel_path = os.path.join(target_dir, excel_filename)

            prepared_rows = []
            for tender in data_to_save:
                row = dict(tender)
                row.setdefault("Portal", portal_name)
                published_value = row.get("Published Date")
                if not published_value:
                    published_value = row.get("e-Published Date")
                if published_value is None:
                    published_value = ""
                published_text = str(published_value).strip()
                row["Published Date"] = published_text
                row["e-Published Date"] = published_text

                row["Direct URL"] = str(row.get("Direct URL") or "").strip()
                row["Status URL"] = str(row.get("Status URL") or "").strip()
                row["S.No"] = str(row.get("S.No") or "").strip()
                try:
                    if EMD_AMOUNT_KEY in row:
                        row['EMD Amount (Numeric)'] = float(
                            re.sub(r'[^\\d.]', '', row[EMD_AMOUNT_KEY]) or 0
                        )
                except Exception:
                    pass
                prepared_rows.append(row)

            if data_store is not None and sqlite_run_id is not None:
                try:
                    saved_rows = data_store.replace_run_tenders(sqlite_run_id, prepared_rows)
                    log_callback(f"[PERSIST] SQLite save: SUCCESS | run_id={sqlite_run_id} | rows={saved_rows}")
                    log_callback(f"[PERSIST] SQLite DB path: {sqlite_db_path}")
                    if not should_export:
                        log_callback(f"[PERSIST] File export skipped ({export_reason})")
                        return None, None
                    exported_path, exported_type = data_store.export_run(
                        run_id=sqlite_run_id,
                        output_dir=target_dir,
                        website_keyword=f"{website_keyword}{suffix}",
                        mark_partial=mark_partial
                    )
                    if exported_path:
                        label = "PARTIAL" if mark_partial else "FINAL"
                        log_callback(f"\n[{label}] File export: SUCCESS | format={str(exported_type or '').upper()}")
                        log_callback(f"[{label}] Export path: {exported_path}")
                        return exported_path, exported_type
                except Exception as sqlite_export_err:
                    log_callback(f"WARNING: SQLite export failed, using direct file export: {sqlite_export_err}")
                    log_callback(f"[PERSIST] SQLite save may exist, but file export from SQLite failed. DB path: {sqlite_db_path}")

            if not should_export:
                log_callback(f"[PERSIST] File export skipped ({export_reason})")
                return None, None

            df = pd.DataFrame(prepared_rows)
            if DEPARTMENT_NAME_KEY in df.columns:
                df = df.sort_values(DEPARTMENT_NAME_KEY)

            try:
                df.to_excel(excel_path, index=False, engine='openpyxl')
                label = "PARTIAL" if mark_partial else "FINAL"
                log_callback(f"\n[{label}] File export: SUCCESS | format=EXCEL")
                log_callback(f"[{label}] Export path: {excel_path}")
                return excel_path, "excel"
            except PermissionError:
                timestamp_ms = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                excel_filename_alt = EXCEL_FILENAME_FORMAT.format(
                    website_keyword=f"{website_keyword}{suffix}",
                    timestamp=timestamp_ms
                )
                excel_path_alt = os.path.join(target_dir, excel_filename_alt)
                log_callback(f"File locked or permission denied. Trying alternate name: {excel_filename_alt}")
                df.to_excel(excel_path_alt, index=False, engine='openpyxl')
                label = "PARTIAL" if mark_partial else "FINAL"
                log_callback(f"\n[{label}] File export: SUCCESS | format=EXCEL")
                log_callback(f"[{label}] Export path: {excel_path_alt}")
                return excel_path_alt, "excel"
            except Exception as save_err:
                log_callback(f"ERROR saving Excel file: {save_err}")
                csv_filename = excel_filename.replace('.xlsx', '.csv')
                csv_path = os.path.join(target_dir, csv_filename)
                log_callback(f"Attempting to save as CSV instead: {csv_filename}")
                df.to_csv(csv_path, index=False, encoding='utf-8-sig')
                label = "PARTIAL" if mark_partial else "FINAL"
                log_callback(f"\n[{label}] File export: SUCCESS | format=CSV")
                log_callback(f"[{label}] Export path: {csv_path}")
                return csv_path, "csv"
        except Exception as save_outer_err:
            log_callback(f"CRITICAL ERROR in snapshot save: {save_outer_err}")
            logger.error(f"Snapshot save error: {save_outer_err}", exc_info=True)
            return None, None

    def _log_persistence_summary(file_path, file_type, sqlite_saved=False, sqlite_note=None):
        log_callback("[PERSIST] ---------- Persistence Summary ----------")
        if sqlite_saved and sqlite_run_id is not None:
            note = f" | {sqlite_note}" if sqlite_note else ""
            log_callback(f"[PERSIST] SQLite: SAVED | run_id={sqlite_run_id} | path={sqlite_db_path}{note}")
        else:
            note = f" | {sqlite_note}" if sqlite_note else ""
            log_callback(f"[PERSIST] SQLite: NOT SAVED | path={sqlite_db_path}{note}")

        if file_path:
            export_fmt = str(file_type or "unknown").upper()
            log_callback(f"[PERSIST] File: SAVED | format={export_fmt} | path={file_path}")
        else:
            log_callback("[PERSIST] File: NOT GENERATED")
        log_callback("[PERSIST] -----------------------------------------")

    saved_output_path = None
    saved_output_type = None

    try:

        for dept in departments_to_scrape:
            count_text = str(dept.get("count_text", "")).strip()
            if count_text.isdigit():
                expected_total_tenders += int(count_text)

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
        if not navigate_to_org_list(driver, log_callback, org_list_url=base_url_config.get('OrgListURL')):
            log_callback("WARNING: Could not verify organization list page navigation")
        
        _wait_for_presence_with_stop(driver, MAIN_TABLE_LOCATOR, PAGE_LOAD_TIMEOUT, stop_event=stop_event)
        if not _sleep_with_stop(STABILIZE_WAIT, stop_event=stop_event):
            status_callback("Scraping stopped by user")
            timer_callback(start_time)
            return {
                "status": "Scraping stopped by user",
                "processed_departments": 0,
                "expected_total_tenders": expected_total_tenders,
                "extracted_total_tenders": 0,
                "skipped_existing_total": 0,
                "skipped_resume_departments": 0,
                "department_summaries": [],
                "direct_nav_attempted": 0,
                "direct_nav_success": 0,
                "direct_nav_fallback_click": 0,
                "click_only_success": 0,
                "extracted_tender_ids": [],
                "processed_department_names": [],
                "output_file_path": None,
                "output_file_type": None,
                "sqlite_db_path": sqlite_db_path,
                "sqlite_run_id": sqlite_run_id,
                "partial_saved": False,
            }

        total_depts = len(departments_to_scrape)
        log_callback(f"Starting to process {total_depts} departments...")
        state_lock = threading.Lock()
        dept_queue = Queue()

        # Start background checkpoint saver — writes every 2 minutes
        def _checkpoint_saver_loop():
            while not _ckpt_stop_event.wait(120):  # wake every 120s or on stop
                if not _checkpoint_path:
                    continue
                try:
                    with state_lock:
                        _snap_tenders = list(all_tender_details)
                        _snap_depts = list(processed_department_names)
                    with open(_checkpoint_path, 'w', encoding='utf-8') as _cf:
                        json.dump({
                            'portal_name': portal_name,
                            'run_started_at': start_time.isoformat(),
                            'tenders': _snap_tenders,
                            'processed_departments': _snap_depts,
                        }, _cf)
                    log_callback(
                        f"[CHECKPOINT] Auto-saved {len(_snap_tenders)} tenders "
                        f"({len(_snap_depts)} depts) → {os.path.basename(_checkpoint_path)}"
                    )
                except Exception as _ce:
                    log_callback(f"[CHECKPOINT] Save failed: {_ce}")

        if _checkpoint_path:
            _ckpt_thread = threading.Thread(target=_checkpoint_saver_loop, name="ckpt-saver", daemon=True)
            _ckpt_thread.start()
            log_callback(f"[CHECKPOINT] Background saver started (every 2 min) → {os.path.basename(_checkpoint_path)}")

        def _process_department_with_driver(active_driver, dept_info, worker_label="W1"):
            nonlocal processed_depts, total_tenders, skipped_existing_total, closing_date_reprocessed_total
            nonlocal skipped_resume_departments, direct_nav_attempted, direct_nav_success
            nonlocal direct_nav_fallback_click, click_only_success
            nonlocal total_nav_time, total_scrape_time, total_dept_processing_time

            if stop_event and stop_event.is_set():
                return

            dept_name = dept_info.get('name', 'Unknown')
            dept_sno = str(dept_info.get('s_no', 'Unknown')).strip()
            dept_name_norm = str(dept_name).strip().lower()

            if dept_name_norm and dept_name_norm in existing_department_names:
                expected_for_dept = int(str(dept_info.get('count_text', '0')).strip()) if str(dept_info.get('count_text', '')).strip().isdigit() else None
                with state_lock:
                    skipped_resume_departments += 1
                    department_summaries.append({
                        "department": dept_name,
                        "expected": expected_for_dept,
                        "scraped": 0,
                        "resume_skipped": True
                    })
                log_callback(f"[{worker_label}] RESUME: Skipping already-processed department: {dept_name}")
                return

            if dept_sno.lower() in HEADER_SNO_KEYWORDS:
                log_callback(f"[{worker_label}] SKIP: Department S.No '{dept_sno}' appears to be a header row")
                return
            if dept_name.lower() in HEADER_NAME_KEYWORDS:
                log_callback(f"[{worker_label}] SKIP: Department name '{dept_name}' appears to be a header")
                return

            with state_lock:
                processed_depts += 1
                current_processed = processed_depts
                pending_depts = max(0, total_depts - processed_depts)
                current_total_tenders = total_tenders

            dept_start_time = time.time()
            log_callback("")
            log_callback("**************")
            log_callback(f"[{worker_label}] Processing department {current_processed}/{total_depts}: {dept_name}")
            log_callback("**************")
            
            # Send non-blocking log message
            send_log(worker_label, f"Processing department {current_processed}/{total_depts}: {dept_name}")
            
            if progress_callback:
                progress_details = (
                    f"Dept {current_processed}/{total_depts}: {dept_name[:30]}... "
                    f"| Scraped: {current_total_tenders} | Pending: {pending_depts}"
                )
                progress_callback(current_processed, total_depts, progress_details, dept_name, 0, current_total_tenders, pending_depts)
                
                # Send non-blocking progress update
                send_progress(
                    worker_label,
                    current=current_processed,
                    total=total_depts,
                    status=f"Dept: {dept_name[:30]}...",
                    extra_data={
                        "dept_name": dept_name,
                        "scraped_tenders": current_total_tenders,
                        "total_tenders": current_total_tenders,
                        "pending_depts": pending_depts,
                        "skipped_duplicates": 0  # Will be updated after scraping
                    }
                )

            try:
                current_url = active_driver.current_url
                log_callback(f"[{worker_label}] Current URL before processing: {current_url}")
            except Exception as session_err:
                log_callback(f"[{worker_label}] Driver session lost before dept {dept_name}: {session_err}")
                return

            has_direct_url = bool(str(dept_info.get('direct_url', '')).strip())
            if has_direct_url:
                with state_lock:
                    direct_nav_attempted += 1

            nav_start_time = time.time()
            opened_dept, nav_mode = _open_department_page(
                active_driver,
                dept_info,
                log_callback,
                base_reference_url=base_url_config.get('OrgListURL') or base_url_config.get('BaseURL')
            )
            nav_time = time.time() - nav_start_time
            if not opened_dept:
                log_callback(f"[{worker_label}] ⏱️ Navigation time: {nav_time:.2f}s (failed)")
                return

            log_callback(f"[{worker_label}] ⏱️ Navigation time: {nav_time:.2f}s")
            
            with state_lock:
                if nav_mode == "direct":
                    direct_nav_success += 1
                elif nav_mode == "click":
                    if has_direct_url:
                        direct_nav_fallback_click += 1
                    else:
                        click_only_success += 1

            if not _sleep_with_stop(STABILIZE_WAIT * 2, stop_event=stop_event):
                return

            try:
                active_driver.current_url
            except Exception as session_err:
                log_callback(f"[{worker_label}] Driver session lost after opening dept {dept_name}: {session_err}")
                return

            scrape_start_time = time.time()
            tender_data, skipped_existing, changed_closing_date_count = _scrape_tender_details(
                driver=active_driver,
                department_name=dept_name,
                base_url=base_url_config['BaseURL'],
                log_callback=log_callback,
                existing_tender_ids=existing_tender_ids,
                existing_tender_ids_normalized=existing_tender_ids_normalized,
                existing_tender_snapshot=existing_tender_snapshot,
                portal_skill=portal_skill,
                stop_event=stop_event
            )
            scrape_time = time.time() - scrape_start_time
            log_callback(f"[{worker_label}] ⏱️ Table scraping time: {scrape_time:.2f}s")

            expected_for_dept = int(str(dept_info.get('count_text', '0')).strip()) if str(dept_info.get('count_text', '')).strip().isdigit() else None
            with state_lock:
                skipped_existing_total += skipped_existing
                closing_date_reprocessed_total += changed_closing_date_count
                if dept_name_norm:
                    processed_department_names.add(dept_name_norm)

            if tender_data:
                dept_tender_count = len(tender_data)
                new_ids = {
                    str(item.get("Tender ID (Extracted)")).strip()
                    for item in tender_data
                    if str(item.get("Tender ID (Extracted)", "")).strip()
                }
                new_normalized_ids = {
                    normalize_tender_id(item)
                    for item in new_ids
                    if normalize_tender_id(item)
                }
                with state_lock:
                    total_tenders += dept_tender_count
                    current_total = total_tenders
                    all_tender_details.extend(tender_data)
                    existing_tender_ids.update(new_ids)
                    existing_tender_ids_normalized.update(new_normalized_ids)
                    for item in tender_data:
                        fresh_id = normalize_tender_id(item.get("Tender ID (Extracted)"))
                        if not fresh_id:
                            continue
                        existing_tender_snapshot[fresh_id] = {
                            "closing_date": normalize_closing_date(item.get("Closing Date", ""))
                        }
                    department_summaries.append({
                        "department": dept_name,
                        "expected": expected_for_dept,
                        "scraped": dept_tender_count,
                        "resume_skipped": False
                    })
                dept_info['processed'] = True
                dept_info['tenders_found'] = dept_tender_count
                dept_total_time = time.time() - dept_start_time
                
                # Accumulate timing statistics
                with state_lock:
                    total_nav_time += nav_time
                    total_scrape_time += scrape_time
                    total_dept_processing_time += dept_total_time
                
                log_callback(f"[{worker_label}] Found {dept_tender_count} tenders in department {dept_name}")
                log_callback(f"[{worker_label}] ⏱️ Total department time: {dept_total_time:.2f}s (Nav: {nav_time:.2f}s, Scrape: {scrape_time:.2f}s)")
                if skipped_existing > 0:
                    log_callback(f"[{worker_label}] ⏭️  Skipped {skipped_existing} duplicates in {dept_name}")
                if changed_closing_date_count > 0:
                    log_callback(f"[{worker_label}] ↻ Reprocessed {changed_closing_date_count} due to closing date changes in {dept_name}")

                if progress_callback:
                    progress_details = (
                        f"Dept {current_processed}/{total_depts}: {dept_name[:28]}... "
                        f"| Scraped: {current_total} | Pending: {pending_depts}"
                    )
                    extra_info = {
                        "dept_name": dept_name,
                        "scraped_tenders": dept_tender_count,
                        "total_tenders": current_total,
                        "pending_depts": pending_depts,
                        "skipped_duplicates": skipped_existing,
                        "closing_date_reprocessed": changed_closing_date_count
                    }
                    progress_callback(current_processed, total_depts, progress_details, extra_info)
                    
                # Send via message queue with skip info
                send_progress(
                    worker_label,
                    current=current_processed,
                    total=total_depts,
                    status=f"Dept: {dept_name[:28]}...",
                    extra_data={
                        "dept_name": dept_name,
                        "scraped_tenders": dept_tender_count,
                        "total_tenders": current_total,
                        "pending_depts": pending_depts,
                        "skipped_duplicates": skipped_existing,
                        "closing_date_reprocessed": changed_closing_date_count
                    }
                )
            else:
                with state_lock:
                    department_summaries.append({
                        "department": dept_name,
                        "expected": expected_for_dept,
                        "scraped": 0,
                        "resume_skipped": False
                    })
                dept_info['processed'] = True
                dept_info['tenders_found'] = 0
                dept_total_time = time.time() - dept_start_time
                log_callback(f"[{worker_label}] No tenders found/extracted from department {dept_name}")
                log_callback(f"[{worker_label}] ⏱️ Department processing time: {dept_total_time:.2f}s")

            if nav_mode == "direct":
                log_callback(f"[{worker_label}] Direct navigation mode: skipping return-to-org and proceeding to next department")
                return

            try:
                active_driver.current_url
            except Exception as session_err:
                log_callback(f"[{worker_label}] Driver session lost before back navigation for {dept_name}: {session_err}")
                return

            back_clicked = _click_on_page_back_button(active_driver, log_callback, base_url_config.get('OrgListURL'), stop_event=stop_event)
            if not back_clicked:
                log_callback(f"[{worker_label}] WARNING: Back button click failed, returning to org list URL")
                try:
                    active_driver.current_url
                    active_driver.get(base_url_config['OrgListURL'])
                    if not navigate_to_org_list(active_driver, log_callback, org_list_url=base_url_config.get('OrgListURL')):
                        log_callback(f"[{worker_label}] ERROR: Could not navigate back to organization list")
                    _wait_for_presence_with_stop(active_driver, MAIN_TABLE_LOCATOR, PAGE_LOAD_TIMEOUT, stop_event=stop_event)
                    if not _sleep_with_stop(STABILIZE_WAIT * 2, stop_event=stop_event):
                        return
                except Exception as nav_err:
                    log_callback(f"[{worker_label}] ERROR: Failed to navigate back (session may be lost): {nav_err}")

        department_parallel_workers = 1
        active_workers = 1
        try:
            department_parallel_workers = max(1, min(5, int(kwargs.get("department_parallel_workers") or 1)))
        except (TypeError, ValueError):
            department_parallel_workers = 1

        if department_parallel_workers > 1 and total_depts > 1:
            active_workers = min(department_parallel_workers, total_depts)
            if active_workers < department_parallel_workers:
                log_callback(
                    f"Department worker cap applied: requested={department_parallel_workers}, active={active_workers}, departments={total_depts}"
                )
            log_callback(f"Department parallel mode enabled: workers={active_workers} (instance-based for true parallelism)")

            worker_assignments = _build_worker_assignments(departments_to_scrape, active_workers)
            _write_department_links_snapshot(portal_name, departments_to_scrape, worker_assignments, log_callback)
            
            # Show load balancing distribution with time estimates
            log_callback("📊 Smart Load Balancing - Worker Assignments (Time-Based):")
            DEPT_OVERHEAD = 30.0  # seconds per department
            PER_TENDER = 0.5      # seconds per tender
            for idx, bucket in enumerate(worker_assignments, 1):
                total_tenders = sum(int(dept.get('count_text', '0') or '0') for dept in bucket)
                estimated_time = (len(bucket) * DEPT_OVERHEAD) + (total_tenders * PER_TENDER)
                log_callback(f"   W{idx}: {len(bucket)} depts, ~{total_tenders} tenders, est. {estimated_time/60:.1f} min")

            # Close the initial driver since we'll create separate instances for each worker
            log_callback("Closing initial browser instance (will create separate instances per worker)...")
            try:
                driver.quit()
                driver = None  # Mark as closed so finally block doesn't try to close it again
            except Exception as close_err:
                log_callback(f"Warning: Error closing initial driver: {close_err}")
                driver = None

            # Create separate browser instances for each worker (true parallelism)
            # Use parallel initialization to speed up browser startup
            worker_drivers = []
            browser_init_start = time.time()
            try:
                log_callback(f"⚡ Initializing {active_workers} browser instances IN PARALLEL...")
                from scraper.driver_manager import setup_driver
                
                def _init_worker_browser(worker_idx):
                    """Initialize a single browser instance for a worker."""
                    worker_label = f"W{worker_idx + 1}"
                    try:
                        log_callback(f"  [{worker_label}] Starting browser...")
                        worker_driver = None
                        worker_org_url = str(base_url_config.get('OrgListURL') or base_url_config.get('BaseURL') or '').strip()
                        for prime_attempt in range(2):
                            if worker_driver is None:
                                worker_driver = setup_driver(initial_download_dir=download_dir)

                            if not worker_org_url:
                                break

                            log_callback(f"  [{worker_label}] Priming browser to org list page...")
                            try:
                                prime_ok = navigate_to_org_list(worker_driver, lambda msg: log_callback(f"  [{worker_label}] {msg}"), org_list_url=worker_org_url)
                                primed_url = str(worker_driver.current_url or '')
                                invalid_primed = (
                                    primed_url.startswith('data:')
                                    or primed_url.startswith('about:blank')
                                    or primed_url.startswith('chrome-error://')
                                    or primed_url.startswith('edge-error://')
                                )
                                if prime_ok and not invalid_primed:
                                    break

                                log_callback(f"  [{worker_label}] Priming failed ({primed_url[:60]}), recreating browser and retrying...")
                            except Exception as warmup_err:
                                log_callback(f"  [{worker_label}] ⚠ Browser priming warning: {warmup_err}")

                            safe_quit_driver(worker_driver, lambda _msg: None)
                            worker_driver = None
                        
                        if worker_driver is None:
                            raise Exception("Worker browser could not be primed to organization page")

                        log_callback(f"  ✓ [{worker_label}] Browser ready")
                        return (worker_idx, worker_driver, None)
                    except Exception as init_err:
                        log_callback(f"  ✗ [{worker_label}] Browser initialization failed: {init_err}")
                        return (worker_idx, None, init_err)
                
                # Start all browser instances in parallel
                with concurrent.futures.ThreadPoolExecutor(max_workers=active_workers) as init_executor:
                    init_futures = [
                        init_executor.submit(_init_worker_browser, idx)
                        for idx in range(active_workers)
                    ]
                    
                    # Collect results in order
                    worker_drivers = [None] * active_workers
                    failed_count = 0
                    for future in concurrent.futures.as_completed(init_futures):
                        worker_idx, driver_instance, error = future.result()
                        if driver_instance:
                            worker_drivers[worker_idx] = driver_instance
                        else:
                            failed_count += 1
                
                # Remove None entries (failed initializations)
                worker_drivers = [wd for wd in worker_drivers if wd is not None]
                
                browser_init_time = time.time() - browser_init_start
                browser_init_time_total = browser_init_time  # Store for summary statistics
                
                if failed_count > 0:
                    log_callback(f"⚠️  {failed_count} browser(s) failed to initialize")
                
                if len(worker_drivers) == 0:
                    raise Exception(f"All {active_workers} browser instances failed to initialize")
                
                actual_workers = len(worker_drivers)
                log_callback(f"✓ {actual_workers} browser instances initialized in {browser_init_time:.2f}s (parallel startup)")
                
                # Adjust active_workers if some browsers failed
                if actual_workers < active_workers:
                    log_callback(f"⚠️  Reduced worker count from {active_workers} to {actual_workers} due to initialization failures")
                    active_workers = actual_workers
                    # Re-balance work assignments
                    worker_assignments = _build_worker_assignments(departments_to_scrape, active_workers)
                
            except Exception as driver_err:
                log_callback(f"ERROR: Could not create worker browser instances: {driver_err}")
                # Clean up any drivers that were created
                for wd in worker_drivers:
                    try:
                        wd.quit()
                    except:
                        pass
                log_callback("Falling back to single worker mode - creating new browser instance...")
                # Recreate driver for fallback single worker mode
                try:
                    driver = setup_driver(initial_download_dir=download_dir)
                except Exception as fallback_err:
                    log_callback(f"ERROR: Could not create fallback driver: {fallback_err}")
                    return _prepare_summary()
                
                # Fallback to single worker
                for dept_info in departments_to_scrape:
                    if stop_event and stop_event.is_set():
                        break
                    _process_department_with_driver(driver, dept_info, "W1")
                return _prepare_summary()

            def _worker_loop(worker_index, label, assigned_departments, worker_driver):
                """Worker loop with dedicated browser instance for true parallelism."""
                # Register this worker with message queue
                register_worker(label)
                log_callback(f"[{label}] Worker registered with dedicated browser instance")
                
                worker_success = True
                departments_completed = 0
                
                try:
                    for dept_task in assigned_departments or []:
                        if stop_event and stop_event.is_set():
                            break
                        
                        # Process with dedicated driver (no locks, true parallel execution)
                        try:
                            _process_department_with_driver(worker_driver, dept_task, label)
                            departments_completed += 1
                            
                        except Exception as dept_err:
                            error_msg = f"ERROR processing department: {dept_err}"
                            log_callback(f"[{label}] {error_msg}")
                            send_error(label, str(dept_err))
                            # Continue with next department even if one fails
                    
                    # Worker completed all departments
                    log_callback(f"[{label}] Worker completed {departments_completed}/{len(assigned_departments or [])} departments")
                    send_complete(label, {"departments": departments_completed})
                    
                except Exception as worker_critical_err:
                    # Critical worker failure (e.g., browser crash)
                    worker_success = False
                    error_details = f"Critical worker error: {worker_critical_err}"
                    log_callback(f"[{label}] ❌ {error_details}")
                    send_error(label, error_details)
                    
                finally:
                    # Each worker closes its own browser instance
                    try:
                        log_callback(f"[{label}] Closing browser instance...")
                        worker_driver.quit()
                        log_callback(f"[{label}] ✓ Browser closed")
                    except Exception as close_err:
                        log_callback(f"[{label}] WARNING: Error closing browser: {close_err}")
                    
                    return {
                        "worker_id": label,
                        "success": worker_success,
                        "departments_completed": departments_completed,
                        "departments_assigned": len(assigned_departments or [])
                    }

            # Track worker results for error isolation
            worker_results = []
            
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=active_workers) as executor:
                    futures = [
                        executor.submit(_worker_loop, idx, f"W{idx + 1}", worker_assignments[idx], worker_drivers[idx])
                        for idx in range(active_workers)
                    ]
                    for fut in concurrent.futures.as_completed(futures):
                        try:
                            result = fut.result()
                            if result:
                                worker_results.append(result)
                        except Exception as fut_err:
                            log_callback(f"❌ WARNING: Worker thread failed critically: {fut_err}")
                            worker_results.append({
                                "worker_id": "Unknown",
                                "success": False,
                                "departments_completed": 0,
                                "departments_assigned": 0,
                                "error": str(fut_err)
                            })
            finally:
                # Ensure all worker browsers are closed (safety cleanup)
                log_callback("Cleaning up worker browser instances...")
                for idx, wd in enumerate(worker_drivers):
                    try:
                        wd.quit()
                        log_callback(f"  ✓ W{idx + 1} browser cleaned up")
                    except Exception as cleanup_err:
                        log_callback(f"  WARNING: W{idx + 1} cleanup error: {cleanup_err}")
                log_callback("✓ All worker browsers cleaned up")
        else:
            for dept_info in departments_to_scrape:
                if stop_event and stop_event.is_set():
                    break
                _process_department_with_driver(driver, dept_info, "W1")

        # Generate output file if we have data
        was_stopped = stop_event and stop_event.is_set()
        if all_tender_details:
            # Mark as partial if scraping was stopped before completion
            saved_output_path, saved_output_type = _save_tender_data_snapshot(
                all_tender_details, 
                mark_partial=was_stopped
            )
            
            if was_stopped and saved_output_path:
                log_callback("")
                log_callback("=" * 80)
                log_callback("⚠️  GRACEFUL SHUTDOWN - PARTIAL SAVE COMPLETED")
                log_callback("=" * 80)
                log_callback(f"✓ Saved {len(all_tender_details)} tenders to: {saved_output_type}")
                log_callback(f"   File: {saved_output_path}")
                log_callback("")
                
                # Calculate what was missed
                pending_depts = len(departments_to_scrape) - processed_depts
                if pending_depts > 0:
                    log_callback(f"⏸️  Departments Not Processed: {pending_depts}")
                    estimated_missed_tenders = sum(
                        int(dept.get('count_text', '0') or '0')
                        for dept in departments_to_scrape[processed_depts:]
                    )
                    if estimated_missed_tenders > 0:
                        log_callback(f"   Estimated Missed Tenders: ~{estimated_missed_tenders}")
                log_callback("=" * 80)
                log_callback("")
        
        status_msg = "Scraping completed"
        if was_stopped:
            status_msg = "Scraping stopped by user (partial results saved)"
        
        # Calculate total elapsed time
        total_elapsed_time = (datetime.now() - start_time).total_seconds()
        
        log_callback("")
        log_callback("#" * 80)  # Portal completion separator
        log_callback("#" * 80)
        log_callback(f"\n=== {status_msg} ===")
        log_callback(f"Processed {processed_depts} departments")
        if skipped_resume_departments > 0:
            log_callback(f"Resume skipped departments: {skipped_resume_departments}")
        log_callback(f"Total tenders found: {total_tenders}")
        
        # Show completion status for partial runs
        if was_stopped:
            total_depts_to_process = len(departments_to_scrape)
            completion_percentage = (processed_depts / total_depts_to_process * 100) if total_depts_to_process > 0 else 0
            log_callback("")
            log_callback("⚠️  PARTIAL RUN STATUS:")
            log_callback(f"   Completion: {completion_percentage:.1f}% ({processed_depts}/{total_depts_to_process} departments)")
            log_callback(f"   Tenders Saved: {total_tenders}")
            if skipped_existing_total > 0:
                log_callback(f"   Duplicates Skipped: {skipped_existing_total}")
        
        # Comprehensive Summary Statistics
        log_callback("")
        log_callback("=" * 80)
        log_callback("📊 COMPREHENSIVE PERFORMANCE SUMMARY")
        log_callback("=" * 80)
        
        # Timing Breakdown
        log_callback("")
        log_callback("⏱️  TIMING BREAKDOWN:")
        log_callback(f"   Total Elapsed Time: {total_elapsed_time:.2f}s ({total_elapsed_time/60:.2f} min)")
        
        if browser_init_time_total > 0:
            log_callback(f"   Browser Initialization: {browser_init_time_total:.2f}s (parallel startup)")
        
        if processed_depts > 0:
            log_callback(f"   Total Navigation Time: {total_nav_time:.2f}s")
            log_callback(f"   Total Scraping Time: {total_scrape_time:.2f}s")
            log_callback(f"   Total Dept Processing: {total_dept_processing_time:.2f}s")
            
            overhead_time = total_elapsed_time - total_dept_processing_time - browser_init_time_total
            if overhead_time > 0:
                log_callback(f"   System Overhead: {overhead_time:.2f}s")
        
        # Average Times
        log_callback("")
        log_callback("📈 AVERAGE TIMES:")
        if processed_depts > 0:
            avg_nav = total_nav_time / processed_depts
            avg_scrape = total_scrape_time / processed_depts
            avg_dept = total_dept_processing_time / processed_depts
            log_callback(f"   Per Department: {avg_dept:.2f}s (Nav: {avg_nav:.2f}s, Scrape: {avg_scrape:.2f}s)")
        
        if total_tenders > 0:
            avg_per_tender = total_scrape_time / total_tenders
            log_callback(f"   Per New Tender: {avg_per_tender:.2f}s")
        
        # Duplicate Detection Performance
        if skipped_existing_total > 0:
            log_callback("")
            log_callback("🔍 DUPLICATE DETECTION PERFORMANCE:")
            log_callback(f"   Total Duplicates Skipped: {skipped_existing_total} tenders")
            total_processed = total_tenders + skipped_existing_total
            duplicate_percentage = (skipped_existing_total / total_processed * 100) if total_processed > 0 else 0
            log_callback(f"   Duplicate Rate: {duplicate_percentage:.1f}% ({skipped_existing_total}/{total_processed})")
            
            # Estimate time saved (assuming 0.7s per tender if we didn't have early detection)
            time_saved_estimate = skipped_existing_total * 0.7
            log_callback(f"   Estimated Time Saved: {time_saved_estimate:.2f}s ({time_saved_estimate/60:.2f} min)")
            log_callback(f"   (Based on early duplicate detection vs full extraction)")
        
        # Worker Efficiency
        if active_workers > 1:
            log_callback("")
            log_callback("⚡ MULTI-WORKER EFFICIENCY:")
            log_callback(f"   Workers Used: {active_workers} (instance-based parallelism)")
            
            # Worker status from error isolation
            if worker_results:
                successful_workers = [w for w in worker_results if w.get("success", True)]
                failed_workers = [w for w in worker_results if not w.get("success", True)]
                
                log_callback(f"   Workers Successful: {len(successful_workers)}/{len(worker_results)}")
                if failed_workers:
                    log_callback(f"   ⚠️  Workers Failed: {len(failed_workers)}")
                    for fw in failed_workers:
                        worker_id = fw.get("worker_id", "Unknown")
                        error_info = fw.get("error", "Unknown error")
                        log_callback(f"      - {worker_id}: {error_info}")
                
                # Department completion by worker
                log_callback("")
                log_callback("   Department Completion by Worker:")
                for wr in worker_results:
                    worker_id = wr.get("worker_id", "Unknown")
                    completed = wr.get("departments_completed", 0)
                    assigned = wr.get("departments_assigned", 0)
                    status_icon = "✓" if wr.get("success", True) else "❌"
                    log_callback(f"      {status_icon} {worker_id}: {completed}/{assigned} departments")
            
            if processed_depts > 0:
                theoretical_sequential_time = total_dept_processing_time
                actual_time = total_elapsed_time
                if actual_time > 0:
                    log_callback("")
                    speedup_factor = theoretical_sequential_time / actual_time
                    efficiency = (speedup_factor / active_workers) * 100
                    log_callback(f"   Parallelism Speedup: {speedup_factor:.2f}x")
                    log_callback(f"   Worker Efficiency: {efficiency:.1f}% (ideal: 100%)")
        
        # Throughput
        log_callback("")
        log_callback("🚀 THROUGHPUT:")
        if total_elapsed_time > 0:
            tenders_per_minute = (total_tenders / total_elapsed_time) * 60
            log_callback(f"   New Tenders: {tenders_per_minute:.1f} per minute")
            
            if skipped_existing_total > 0:
                total_processed = total_tenders + skipped_existing_total
                total_per_minute = (total_processed / total_elapsed_time) * 60
                log_callback(f"   Total Processed: {total_per_minute:.1f} per minute (incl. duplicates)")
        
        log_callback("")
        log_callback("=" * 80)
        log_callback("")
        
        # Original summary for compatibility
        if skipped_existing_total > 0:
            log_callback(f"📊 DUPLICATE SKIPPING SUMMARY:")
            log_callback(f"   Total duplicates skipped: {skipped_existing_total} tenders")
            log_callback(f"   (These tenders already exist in database with same closing date)")
            log_callback("")
        if closing_date_reprocessed_total > 0:
            log_callback(f"📊 CLOSING DATE CHANGE SUMMARY:")
            log_callback(f"   Reprocessed due to closing date change: {closing_date_reprocessed_total} tenders")
            log_callback("")
        log_callback(
            f"Department navigation summary: "
            f"direct_success={direct_nav_success}/{direct_nav_attempted}, "
            f"fallback_click={direct_nav_fallback_click}, click_only={click_only_success}"
        )
        if expected_total_tenders > 0:
            log_callback(f"Verification: expected approx {expected_total_tenders}, extracted {total_tenders}")
            if total_tenders < expected_total_tenders:
                log_callback(f"Verification gap: {expected_total_tenders - total_tenders} (portal filters/status differences possible)")
        log_callback("#" * 80)  # Portal completion separator
        log_callback("#" * 80)
        log_callback("")  # Blank line
        status_callback(status_msg)
        timer_callback(start_time)

        extracted_tender_ids = sorted({
            str(item.get("Tender ID (Extracted)")).strip()
            for item in all_tender_details
            if str(item.get("Tender ID (Extracted)", "")).strip()
        })

        # Stop checkpoint thread and delete checkpoint on clean completion
        _ckpt_stop_event.set()
        if _ckpt_thread and _ckpt_thread.is_alive():
            _ckpt_thread.join(timeout=5)
        if _checkpoint_path and os.path.exists(_checkpoint_path):
            try:
                os.remove(_checkpoint_path)
                log_callback(f"[CHECKPOINT] Deleted on successful completion")
            except Exception:
                pass

        if data_store is not None and sqlite_run_id is not None:
            try:
                data_store.finalize_run(
                    run_id=sqlite_run_id,
                    status=status_msg,
                    expected_total=expected_total_tenders,
                    extracted_total=total_tenders,
                    skipped_total=skipped_existing_total,
                    partial_saved=False,
                    output_file_path=saved_output_path,
                    output_file_type=saved_output_type
                )
                log_callback(f"[PERSIST] SQLite finalize: SUCCESS | run_id={sqlite_run_id}")
                log_callback(f"[PERSIST] SQLite DB path: {sqlite_db_path}")
            except Exception as finalize_err:
                log_callback(f"WARNING: Failed to finalize SQLite run metadata: {finalize_err}")

        _log_persistence_summary(
            file_path=saved_output_path,
            file_type=saved_output_type,
            sqlite_saved=(data_store is not None and sqlite_run_id is not None),
            sqlite_note=status_msg,
        )

        return {
            "status": status_msg,
            "processed_departments": processed_depts,
            "expected_total_tenders": expected_total_tenders,
            "extracted_total_tenders": total_tenders,
            "skipped_existing_total": skipped_existing_total,
            "closing_date_reprocessed_total": closing_date_reprocessed_total,
            "skipped_resume_departments": skipped_resume_departments,
            "department_summaries": department_summaries,
            "direct_nav_attempted": direct_nav_attempted,
            "direct_nav_success": direct_nav_success,
            "direct_nav_fallback_click": direct_nav_fallback_click,
            "click_only_success": click_only_success,
            "extracted_tender_ids": extracted_tender_ids,
            "processed_department_names": sorted(processed_department_names),
            "output_file_path": saved_output_path,
            "output_file_type": saved_output_type,
            "partial_saved": False,
            "sqlite_db_path": sqlite_db_path,
            "sqlite_run_id": sqlite_run_id
        }

        # Play success sound only if not cancelled
        try:
            if not (stop_event and stop_event.is_set()):
                play_sound(SOUND_SUCCESS)
        except Exception:
            pass

    except Exception as e:
        log_callback(f"Error in run_scraping_logic: {e}")
        logger.error(f"Error in run_scraping_logic: {e}", exc_info=True)

        # Stop checkpoint thread (keep checkpoint file so next run can resume)
        _ckpt_stop_event.set()
        if _ckpt_thread and _ckpt_thread.is_alive():
            _ckpt_thread.join(timeout=3)
        if _checkpoint_path and all_tender_details:
            try:
                with open(_checkpoint_path, 'w', encoding='utf-8') as _cf:
                    json.dump({
                        'portal_name': portal_name,
                        'run_started_at': start_time.isoformat(),
                        'tenders': list(all_tender_details),
                        'processed_departments': list(processed_department_names),
                    }, _cf)
                log_callback(f"[CHECKPOINT] Final save on error: {len(all_tender_details)} tenders kept for resume")
            except Exception:
                pass

        partial_saved = False
        if all_tender_details:
            log_callback("Attempting partial save of extracted tenders after error...")
            saved_output_path, saved_output_type = _save_tender_data_snapshot(all_tender_details, mark_partial=True)
            partial_saved = bool(saved_output_path)

        status_callback("Error during scraping")
        timer_callback(start_time)
        # Play error sound
        try:
            play_sound(SOUND_ERROR)
        except Exception:
            pass
        extracted_tender_ids = sorted({
            str(item.get("Tender ID (Extracted)")).strip()
            for item in all_tender_details
            if str(item.get("Tender ID (Extracted)", "")).strip()
        })

        if data_store is not None and sqlite_run_id is not None:
            try:
                data_store.finalize_run(
                    run_id=sqlite_run_id,
                    status="Error during scraping",
                    expected_total=expected_total_tenders,
                    extracted_total=len(all_tender_details),
                    skipped_total=skipped_existing_total,
                    partial_saved=partial_saved,
                    output_file_path=saved_output_path,
                    output_file_type=saved_output_type
                )
                log_callback(f"[PERSIST] SQLite finalize: SUCCESS | run_id={sqlite_run_id}")
                log_callback(f"[PERSIST] SQLite DB path: {sqlite_db_path}")
            except Exception as finalize_err:
                log_callback(f"WARNING: Failed to finalize SQLite run metadata: {finalize_err}")

        _log_persistence_summary(
            file_path=saved_output_path,
            file_type=saved_output_type,
            sqlite_saved=(data_store is not None and sqlite_run_id is not None),
            sqlite_note="Error during scraping",
        )

        return {
            "status": "Error during scraping",
            "processed_departments": processed_depts,
            "expected_total_tenders": expected_total_tenders,
            "extracted_total_tenders": len(all_tender_details),
            "skipped_existing_total": skipped_existing_total,
            "closing_date_reprocessed_total": closing_date_reprocessed_total,
            "skipped_resume_departments": skipped_resume_departments,
            "department_summaries": department_summaries,
            "direct_nav_attempted": direct_nav_attempted,
            "direct_nav_success": direct_nav_success,
            "direct_nav_fallback_click": direct_nav_fallback_click,
            "click_only_success": click_only_success,
            "extracted_tender_ids": extracted_tender_ids,
            "processed_department_names": sorted(processed_department_names),
            "output_file_path": saved_output_path,
            "output_file_type": saved_output_type,
            "partial_saved": partial_saved,
            "sqlite_db_path": sqlite_db_path,
            "sqlite_run_id": sqlite_run_id
        }

def process_department(dept_info, base_url_config, download_dir, driver,
                      log_callback=None, progress_callback=None, stop_event=None):
    """Process a single department and return tender data."""
    # Create no-op callbacks if None provided
    log_callback = log_callback or (lambda x: None)
    progress_callback = progress_callback or (lambda *args: None)
    portal_skill = resolve_portal_skill(base_url_config)

    try:
        if not dept_info['has_link'] or dept_info['processed']:
            log_callback(f"Skipping department {dept_info['name']}: already processed or no link")
            return None

        # Open department page (direct URL first, click fallback)
        opened_dept, _nav_mode = _open_department_page(
            driver,
            dept_info,
            log_callback,
            base_reference_url=base_url_config.get('OrgListURL') or base_url_config.get('BaseURL')
        )
        if not opened_dept:
            log_callback(f"Failed to open department page: {dept_info['name']}")
            return None

        log_callback(f"Processing department {dept_info['name']}...")
        if not _sleep_with_stop(STABILIZE_WAIT, stop_event=stop_event):
            return None

        # Extract tender details
        tender_data, _skipped_existing, _changed_closing_date_count = _scrape_tender_details(
            driver=driver,
            department_name=dept_info['name'],
            base_url=base_url_config['BaseURL'],
            log_callback=log_callback,
            portal_skill=portal_skill,
            stop_event=stop_event
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
        back_clicked = _click_on_page_back_button(driver, log_callback, base_url_config.get('OrgListURL'), stop_event=stop_event)
        if not back_clicked:
            log_callback("Warning: Back button click failed, returning to org list URL")
            try:
                driver.get(base_url_config['OrgListURL'])
                _sleep_with_stop(STABILIZE_WAIT, stop_event=stop_event)
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


def _perform_tender_processing(driver, identifier, base_download_dir, log_callback, status_callback, stop_event, dl_more_details=True, dl_zip=True, dl_notice_pdfs=True, portal_skill=PORTAL_SKILL_NIC):
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
            tender_id = extract_tender_id_by_skill(title, portal_skill)
            if tender_id:
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
        portal_skill = resolve_portal_skill(base_url_config)
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
                        dl_notice_pdfs=True,
                        portal_skill=portal_skill
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
    portal_skill = kwargs.get('portal_skill', PORTAL_SKILL_NIC)
    
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
                    dl_notice_pdfs=dl_notice_pdfs,
                    portal_skill=portal_skill
                )

                processed += 1
                if progress_callback:
                    progress_callback(processed, total_urls, total_urls, None)

            except Exception as e:
                log_callback(f"Error processing URL {url}: {e}")
                continue

        log_callback(f"\nCompleted processing {processed} of {total_urls} URLs")

        # Success sound when completed (not cancelled)
        try:
            if not (stop_event and stop_event.is_set()):
                play_sound(SOUND_SUCCESS)
        except Exception:
            pass

    except Exception as e:
        log_callback(f"Error in direct URL processing: {e}")
        # Play error sound
        try:
            play_sound(SOUND_ERROR)
        except Exception:
            pass
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

def navigate_to_org_list(driver, log_callback=None, org_list_url=None):
    """Navigate to the organization list page using resilient locator strategies with portal config memory."""
    log_callback = log_callback or (lambda x: None)
    org_list_url = str(org_list_url or '').strip()
    
    # Get portal memory
    portal_memory = get_portal_memory()
    
    try:
        current_url = str(driver.current_url or '')
        portal_seed_url = org_list_url or current_url
        portal_name = get_website_keyword_from_url(portal_seed_url)
        log_callback(f"Worker: Current URL: {current_url}")

        invalid_current = current_url.startswith('data:') or current_url.startswith('about:blank') or current_url.startswith('chrome-error://') or current_url.startswith('edge-error://')
        if invalid_current and org_list_url:
            log_callback(f"⚠ Invalid worker page detected ({current_url[:80]}), recovering via OrgListURL")
            driver.get(org_list_url)
            time.sleep(STABILIZE_WAIT * 2)
            current_url = str(driver.current_url or '')
            log_callback(f"Worker: Recovery URL: {current_url}")
            if TENDERS_BY_ORG_URL_PATTERN in current_url:
                log_callback("✓ Recovery landed on 'Tenders by Organisation' page")
                return True
        
        # Check if we're already on the correct page
        if TENDERS_BY_ORG_URL_PATTERN in current_url:
            log_callback("✓ Already on 'Tenders by Organisation' page")
            portal_memory.record_successful_config(portal_name, "navigation", "already_on_page")
            return True
        
        # Check if we're on the wrong page (Site Compatibility)
        if SITE_COMPATIBILITY_URL_PATTERN in current_url:
            log_callback("⚠ Detected Site Compatibility page - navigating back to home")
            base_url = org_list_url or current_url.split('?')[0]  # Get base URL without parameters
            log_callback(f"Navigating to base URL: {base_url}")
            driver.get(base_url)
            time.sleep(STABILIZE_WAIT * 2)
        
        log_callback("Worker: Finding 'Tenders by Organisation' link with fallback strategies...")
        
        # Check if we have a preferred locator from history
        preferred_locator_index = portal_memory.get_preferred_locator(portal_name, "tenders_by_org")
        
        # Try to find the link using multiple fallback strategies
        org_link, successful_locator = find_element_with_fallbacks(
            driver, 
            TENDERS_BY_ORG_LOCATORS, 
            "'Tenders by Organisation' link",
            timeout=8,  # Shorter timeout per attempt
            log_callback=log_callback,
            preferred_index=preferred_locator_index
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
                    
                    # Record successful locator
                    locator_index = TENDERS_BY_ORG_LOCATORS.index(successful_locator) if successful_locator in TENDERS_BY_ORG_LOCATORS else None
                    if locator_index is not None:
                        portal_memory.record_successful_config(
                            portal_name, 
                            "locator_tenders_by_org", 
                            locator_index,
                            {"locator": str(successful_locator), "url": final_url}
                        )
                    
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
                    portal_memory.record_failure(portal_name, "navigation_site_compatibility", {"url": final_url})
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
            current_base = str(driver.current_url or '').split('?')[0]
            if org_list_url:
                direct_org_url = org_list_url
            elif current_base.startswith("http://") or current_base.startswith("https://"):
                direct_org_url = f"{current_base}?page=FrontEndTendersByOrganisation&service=page"
            else:
                direct_org_url = None
                log_callback(f"✗ Cannot construct direct org URL from current page: {current_base}")

            if not direct_org_url:
                return False
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
        if not navigate_to_org_list(driver, log_callback, org_list_url=target_url):
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
                dept_info = {'s_no': s_no, 'name': dept_name, 'count_text': count_text, 'has_link': False, 'processed': False, 'tenders_found': 0, 'direct_url': ''}
                has_link = False
                direct_url = ''
                try:
                    link_candidates = count_cell.find_elements(By.TAG_NAME, "a")
                    if link_candidates:
                        direct_url = str(link_candidates[0].get_attribute('href') or '').strip()
                except Exception:
                    direct_url = ''

                if direct_url:
                    direct_url = sanitize_department_direct_url(direct_url)
                    has_link = True
                    dept_info['direct_url'] = direct_url

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
