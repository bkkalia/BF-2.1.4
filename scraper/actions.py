# scraper/actions.py v2.1.4
# Low-level Selenium actions and file operations

import time
import logging
import os
import base64
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, ElementNotInteractableException,
    StaleElementReferenceException, WebDriverException, UnexpectedAlertPresentException,
    NoAlertPresentException
)
from selenium.webdriver.remote.webelement import WebElement

# Absolute imports from project root
from config import (
    ELEMENT_WAIT_TIMEOUT, STABILIZE_WAIT, POST_ACTION_WAIT, DOWNLOAD_WAIT_TIMEOUT
)

logger = logging.getLogger(__name__)

def safe_extract_text(driver, locator, description, timeout_multiplier=1.0, default="", quick_mode=False):
    """Safely extracts text using a locator, waiting briefly for visibility."""
    if quick_mode:
        # For download operations, use very short timeout (2-3 seconds max)
        wait_time = 2
        presence_timeout = 3
    else:
        wait_time = max(3, int((ELEMENT_WAIT_TIMEOUT / 3) * timeout_multiplier))
        presence_timeout = wait_time + 2

    try:
        element_present = WebDriverWait(driver, presence_timeout).until(EC.presence_of_element_located(locator))
        element_visible = WebDriverWait(driver, wait_time).until(EC.visibility_of(element_present))
        text = element_visible.text.strip()
        if quick_mode:
            logger.debug(f"Quick extract {description}: '{text[:50]}...'") if text else logger.debug(f"{description} found but empty.")
        else:
            logger.debug(f"Extracted {description}: '{text[:70]}...'") if text else logger.debug(f"{description} found but text empty.")
        return text
    except TimeoutException:
        if quick_mode:
            logger.debug(f"{description} not found in {presence_timeout}s (quick mode).")
        else:
            logger.warning(f"{description} ({locator}) not found/visible in {wait_time}s.")
    except StaleElementReferenceException:
        if quick_mode:
            logger.debug(f"{description} became stale (quick mode).")
        else:
            logger.warning(f"{description} ({locator}) became stale during text extraction.")
    except WebDriverException as e:
        if quick_mode:
            logger.debug(f"WebDriver error extracting {description}: {type(e).__name__}")
        else:
            logger.error(f"WebDriver error extracting text for {description} ({locator}): {e}")
    except Exception as e:
        if quick_mode:
            logger.debug(f"Error extracting {description}: {type(e).__name__}")
        else:
            logger.error(f"Unexpected error extracting text for {description} ({locator}): {e}", exc_info=True)
    return default

def click_element(driver, locator, description, scroll=True, timeout_multiplier=1.0, wait_condition=EC.element_to_be_clickable, max_wait=None):
    """Finds, optionally scrolls to, and clicks an element with retries (standard and JS click).
    
    Args:
        max_wait: Maximum wait time in seconds. If specified, overrides timeout_multiplier.
    """
    element = None
    wait_time = max_wait if max_wait is not None else max(5, int(ELEMENT_WAIT_TIMEOUT * timeout_multiplier))
    last_exception = None
    for attempt in range(2):
        action_type = "standard" if attempt == 0 else "JavaScript"; current_wait_condition = wait_condition if attempt == 0 else EC.presence_of_element_located
        if attempt > 0: logger.warning(f"Std click failed for '{description}'. Retrying with {action_type}..."); time.sleep(0.5)
        try:
            logger.debug(f"Attempt {attempt+1}: Wait {wait_time}s for '{description}' ({current_wait_condition.__name__}). Loc: {locator}")
            if isinstance(locator, tuple): element = WebDriverWait(driver, wait_time).until(current_wait_condition(locator)); logger.debug(f"'{description}' found via locator.")
            elif isinstance(locator, WebElement):
                 if not locator.is_displayed(): element = WebDriverWait(driver, wait_time).until(EC.visibility_of(locator)) # Check visibility if passed element
                 else: element = locator # Assume usable if displayed
                 logger.debug(f"'{description}' passed directly, confirmed state.") # Re-wait for condition
            else: logger.error(f"Invalid locator type for '{description}': {type(locator)}"); return False

            if scroll:
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element); time.sleep(POST_ACTION_WAIT / 2)
                    logger.debug(f"Scrolled '{description}' into view.")
                    element = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(element)) # Re-check after scroll
                except StaleElementReferenceException: logger.warning(f"'{description}' stale after scroll.")
                except Exception as scroll_err: logger.warning(f"Scroll error for '{description}': {scroll_err}. Clicking anyway.")

            logger.debug(f"Attempting {action_type} click on '{description}'...")
            if attempt == 0: element.click()
            else: driver.execute_script("arguments[0].click();", element)
            logger.info(f"{action_type.capitalize()} click successful for '{description}'."); time.sleep(POST_ACTION_WAIT if attempt == 0 else STABILIZE_WAIT); return True
        except (TimeoutException, ElementNotInteractableException, StaleElementReferenceException) as e: last_exception = e; logger.warning(f"Attempt {attempt+1} ({action_type}) click failed for '{description}': {type(e).__name__}")
        except WebDriverException as e: last_exception = e; logger.error(f"WebDriver error during {action_type} click {attempt+1} for '{description}': {e}"); break
        except Exception as e: last_exception = e; logger.error(f"Unexpected error during {action_type} click {attempt+1} for '{description}': {e}", exc_info=True); break

    error_msg = f"All click attempts failed for '{description}'."
    if last_exception: error_msg += f" Last error: {type(last_exception).__name__}: {str(last_exception).splitlines()[0]}"
    logger.error(error_msg); return False

def wait_for_downloads(download_dir, timeout=DOWNLOAD_WAIT_TIMEOUT):
    """Waits for downloads by checking for temporary files."""
    start_time = time.monotonic(); logger.info(f"Waiting up to {timeout}s for downloads in '{os.path.basename(download_dir)}'...")
    last_check_files_str = None
    while True:
        elapsed = time.monotonic() - start_time
        if elapsed > timeout:
            logger.warning(f"Download wait timeout ({timeout}s) for '{os.path.basename(download_dir)}'.")
            try: files = [f for f in os.listdir(download_dir) if f.lower().endswith(('.crdownload', '.tmp', '.part'))]
            except Exception as e: files = []; logger.warning(f"Could not list files at timeout check: {e}")
            if files: logger.warning(f"Timeout reached, files potentially still downloading: {files}")
            return False # Timeout

        try:
            if not os.path.isdir(download_dir): logger.error(f"Download directory '{download_dir}' disappeared."); return False
            files_in_dir = os.listdir(download_dir)
            downloading_files = [f for f in files_in_dir if f.lower().endswith(('.crdownload', '.tmp', '.part'))]
            current_files_str = ", ".join(sorted(downloading_files))

            if not downloading_files:
                time.sleep(2); files_in_dir = os.listdir(download_dir) # Re-check after wait
                downloading_files = [f for f in files_in_dir if f.lower().endswith(('.crdownload', '.tmp', '.part'))]
                if not downloading_files: logger.info(f"No active downloads detected in '{os.path.basename(download_dir)}' after {elapsed:.1f}s."); return True
                else: logger.info(f"Downloads still in progress (found on double-check): {downloading_files}"); last_check_files_str = ", ".join(sorted(downloading_files))
            else:
                if current_files_str != last_check_files_str: logger.info(f"Downloads in progress after {elapsed:.1f}s: {downloading_files}"); last_check_files_str = current_files_str
            time.sleep(1)
        except FileNotFoundError: logger.error(f"Download directory '{download_dir}' not found."); return False
        except PermissionError: logger.error(f"Permission denied accessing '{download_dir}'."); return False
        except Exception as e: logger.warning(f"Error checking download dir '{download_dir}': {e}. Retrying..."); time.sleep(3)

    logger.debug("Exited download wait loop unexpectedly."); return False # Fallback

def save_page_as_pdf(driver, pdf_filepath, scale=0.75):
    """Saves the current page as a PDF file using Chrome DevTools Protocol (CDP)."""
    pdf_dir, pdf_filename = os.path.split(pdf_filepath)
    try: os.makedirs(pdf_dir, exist_ok=True)
    except OSError as e: logger.error(f"Failed create directory for PDF '{pdf_filepath}': {e}."); return False
    logger.info(f"Attempting to save current page as PDF: {pdf_filename}")
    result = None
    try:
        print_options = {'landscape': False, 'displayHeaderFooter': False, 'printBackground': True, 'preferCSSPageSize': True, 'marginTop': 0.4, 'marginBottom': 0.4, 'marginLeft': 0.4, 'marginRight': 0.4, 'scale': scale}
        result = driver.execute_cdp_cmd("Page.printToPDF", print_options)
        pdf_data = base64.b64decode(result['data'])
        with open(pdf_filepath, "wb") as f: f.write(pdf_data)
        if os.path.exists(pdf_filepath) and os.path.getsize(pdf_filepath) > 0: logger.info(f"Successfully saved PDF: {pdf_filename} (Size: {len(pdf_data)} bytes)"); return True
        else: logger.error(f"Failed to save PDF: {pdf_filename}. File missing or empty."); return False
    except UnexpectedAlertPresentException:
        try: alert = driver.switch_to.alert; alert_text = alert.text; logger.error(f"Cannot save PDF '{pdf_filename}' due to alert: '{alert_text}'. Dismissing."); alert.accept()
        except NoAlertPresentException: logger.warning("UnexpectedAlertPresentException but no alert found.")
        except Exception as dismiss_err: logger.warning(f"Failed to handle alert saving PDF: {dismiss_err}")
        return False
    except KeyError as ke:
        result_desc = f"Result: {result}" if result else "No result available"
        logger.error(f"Error saving PDF '{pdf_filename}': CDP result missing 'data' key. {result_desc}. Error: {ke}", exc_info=True)
        return False
    except WebDriverException as wde:
         if "execute_cdp_cmd" in str(wde) or "Command is not supported" in str(wde): logger.error(f"Error saving PDF '{pdf_filename}': WebDriver does not support CDP 'Page.printToPDF'.")
         else: logger.error(f"WebDriverException saving PDF '{pdf_filename}': {wde}", exc_info=True)
         return False
    except Exception as pdf_err: logger.error(f"Unexpected error saving PDF '{pdf_filename}': {pdf_err}", exc_info=True); return False
