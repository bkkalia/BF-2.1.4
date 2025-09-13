# scraper/captcha_handler.py v2.1.4
# Logic for detecting and handling CAPTCHA prompts

import time
import logging
import threading
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Use absolute import instead of relative
from config import (
    CAPTCHA_IMAGE_LOCATOR, CAPTCHA_INPUT_LOCATOR, CAPTCHA_PROMPT_LOCATOR,
    POST_CAPTCHA_WAIT, CAPTCHA_CHECK_TIMEOUT
)
# Import gui_utils carefully for potential error messages
try:
    from gui import gui_utils
    GUI_UTILS_AVAILABLE = True
    gui_utils_module = gui_utils  # Store reference to avoid unbound issues
except ImportError:
    GUI_UTILS_AVAILABLE = False # Handle case where GUI isn't available/import fails
    gui_utils_module = None

logger = logging.getLogger(__name__)

def _get_console_input_thread(result_dict):
    """Target function for input thread to handle blocking input()."""
    try: result_dict['value'] = input() # Blocks here
    except EOFError: logger.warning("EOFError waiting for console input."); result_dict['value'] = 'eof_error'
    except Exception as e: logger.warning(f"Exception waiting for console input: {e}"); result_dict['value'] = 'input_error'

def handle_captcha(driver, identifier, target_download_dir, log_callback, status_callback, stop_event):
    """Checks for CAPTCHA elements and prompts user for manual solving via console."""
    captcha_detected = False
    try: # Check for presence of any CAPTCHA element
        wait_time = max(1, CAPTCHA_CHECK_TIMEOUT / 2)
        WebDriverWait(driver, wait_time).until(EC.any_of(
            EC.presence_of_element_located(CAPTCHA_IMAGE_LOCATOR),
            EC.presence_of_element_located(CAPTCHA_PROMPT_LOCATOR),
            EC.presence_of_element_located(CAPTCHA_INPUT_LOCATOR)
        ))
        captcha_detected = True
        log_callback("    CAPTCHA element detected!")
    except TimeoutException: log_callback("    No CAPTCHA elements detected within initial check."); return False
    except Exception as e: log_callback(f"    Error checking for CAPTCHA elements: {e}. Assuming no CAPTCHA."); logger.warning(f"Error during CAPTCHA check: {e}", exc_info=True); return False

    if captcha_detected:
        status_callback(f"CAPTCHA Required for {identifier}...")
        log_callback(f"  !!! ACTION REQUIRED for '{identifier}' !!!"); log_callback(f"    Current URL: {driver.current_url}"); log_callback(f"    Downloads Target: {os.path.basename(target_download_dir)}")
        log_callback("    Please check the browser window, solve the CAPTCHA, then press Enter in THIS CONSOLE window.")
        print("\n" + "="*60 + f"\n  ACTION REQUIRED: Solve CAPTCHA for '{identifier}'\n  Browser Title: {driver.title[:60]}...\n  Browser URL: {driver.current_url}\n  Downloads Target: {os.path.basename(target_download_dir)}\n\n  >>> Solve CAPTCHA in browser, then press Enter HERE <<<\n" + "="*60 + "\n")

        user_input = {'value': None}; input_thread = threading.Thread(target=_get_console_input_thread, args=(user_input,), name=f"CaptchaInput-{identifier[:10]}", daemon=True); input_thread.start()
        while input_thread.is_alive():
            if stop_event.is_set(): log_callback("    Stop requested during CAPTCHA wait."); print("\nStop requested."); input_thread.join(timeout=0.5); return False
            time.sleep(0.5)
        if stop_event.is_set(): log_callback("    Stop confirmed after CAPTCHA input."); return False

        input_val = user_input.get('value')
        if input_val == 'eof_error':
            if GUI_UTILS_AVAILABLE and gui_utils_module is not None:
                gui_utils_module.show_message("CAPTCHA Error", "Console input (EOFError) - cannot handle CAPTCHA.", type="error")
            log_callback("    ERROR: Console input unavailable (EOFError). Cannot handle CAPTCHA.")
            if GUI_UTILS_AVAILABLE and gui_utils_module is not None:
                gui_utils_module.show_message("CAPTCHA Error", "Console input (EOFError) - cannot handle CAPTCHA.", type="error")
            return False
        elif input_val == 'input_error':
            log_callback("    ERROR: Failed to get console input for CAPTCHA confirmation.")
            if GUI_UTILS_AVAILABLE and gui_utils_module is not None: gui_utils_module.show_message("CAPTCHA Error", "Failed to get console input.", type="error")
            return False

        log_callback("    User pressed Enter. Assuming CAPTCHA handled. Waiting..."); status_callback(f"Proceeding after CAPTCHA {identifier}..."); time.sleep(POST_CAPTCHA_WAIT)
        try: # Optional: Check if still on CAPTCHA page
            if driver.find_elements(*CAPTCHA_PROMPT_LOCATOR) or driver.find_elements(*CAPTCHA_IMAGE_LOCATOR): log_callback("    WARN: CAPTCHA elements still detected after waiting.")
            else: log_callback("    Navigated away from CAPTCHA page (elements no longer detected).")
        except Exception as check_err: log_callback(f"    Notice: Error checking if still on CAPTCHA page: {check_err}")
        return True # CAPTCHA detected and interaction occurred
    return False # Fallback