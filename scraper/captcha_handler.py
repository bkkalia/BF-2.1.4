# scraper/captcha_handler.py v2.1.4
# Logic for detecting and handling CAPTCHA prompts

# Add project root to sys.path
import os, sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Standard library imports
import tkinter as tk
from tkinter import messagebox
import threading
import time
import logging

# Third-party imports - with error checking
try:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        NoSuchElementException, TimeoutException, WebDriverException
    )
    SELENIUM_IMPORTED = True
except ImportError as e:
    print(f"Error importing selenium components: {e}")
    SELENIUM_IMPORTED = False
    
    # Define fallback classes to prevent NameError
    class By:
        XPATH = "xpath"
        ID = "id"
        CSS_SELECTOR = "css selector"
    
    class WebDriverWait:
        def __init__(self, driver, timeout):
            pass
        def until(self, condition):
            return None
    
    class EC:
        @staticmethod
        def presence_of_element_located(locator):
            return None
    
    NoSuchElementException = Exception
    TimeoutException = Exception
    WebDriverException = Exception

logger = logging.getLogger(__name__)

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

def handle_captcha(driver, identifier, log_callback, status_callback, stop_event):
    """
    Enhanced CAPTCHA handling with GUI dialog and user interaction.
    Removed unused target_subfolder parameter.
    """
    if not SELENIUM_IMPORTED:
        log_callback("CAPTCHA handling skipped - Selenium not available")
        return True
        
    try:
        # Check for CAPTCHA elements on the page
        captcha_detected = False
        
        # Import CAPTCHA detection constants
        from config import CAPTCHA_IMAGE_LOCATOR, CAPTCHA_INPUT_LOCATOR, CAPTCHA_PROMPT_LOCATOR
        
        try:
            # Look for various CAPTCHA indicators
            captcha_image = driver.find_element(*CAPTCHA_IMAGE_LOCATOR)
            if captcha_image and captcha_image.is_displayed():
                captcha_detected = True
                log_callback(f"CAPTCHA image detected for {identifier}")
        except (NoSuchElementException, WebDriverException):
            pass
            
        try:
            captcha_input = driver.find_element(*CAPTCHA_INPUT_LOCATOR)
            if captcha_input and captcha_input.is_displayed():
                captcha_detected = True
                log_callback(f"CAPTCHA input field detected for {identifier}")
        except (NoSuchElementException, WebDriverException):
            pass
            
        try:
            captcha_prompt = driver.find_element(*CAPTCHA_PROMPT_LOCATOR)
            if captcha_prompt and captcha_prompt.is_displayed():
                captcha_detected = True
                log_callback(f"CAPTCHA prompt detected for {identifier}")
        except (NoSuchElementException, WebDriverException):
            pass
        
        if not captcha_detected:
            log_callback(f"No CAPTCHA detected for {identifier}")
            return True
            
        # CAPTCHA detected - show user dialog
        log_callback(f"CAPTCHA detected for {identifier} - showing user dialog")
        status_callback(f"CAPTCHA required for {identifier}")
        
        # Create and show CAPTCHA dialog
        captcha_dialog = CaptchaDialog(identifier, stop_event)
        result = captcha_dialog.show()
        
        if stop_event.is_set():
            log_callback(f"User cancelled via CAPTCHA dialog for {identifier}")
            return False
            
        if result == "solved":
            log_callback(f"User reported CAPTCHA solved for {identifier}")
            return True
        elif result == "skip":
            log_callback(f"User chose to skip {identifier}")
            return False
        else:
            log_callback(f"CAPTCHA dialog cancelled for {identifier}")
            return False
            
    except Exception as e:
        log_callback(f"Error in CAPTCHA handling for {identifier}: {e}")
        logger.error(f"CAPTCHA handling error: {e}", exc_info=True)
        return True  # Continue on error

class CaptchaDialog:
    """Dialog for CAPTCHA handling with user interaction."""
    
    def __init__(self, identifier, stop_event):
        self.identifier = identifier
        self.stop_event = stop_event
        self.result = None
        self.dialog = None
        
    def show(self):
        """Show the CAPTCHA dialog and return user choice."""
        # Create dialog in main thread
        self.dialog = tk.Toplevel()
        self.dialog.title("CAPTCHA Required")
        self.dialog.geometry("400x250")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()  # Make modal
        
        # Center the dialog
        self.dialog.transient()
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (250 // 2)
        self.dialog.geometry(f"400x250+{x}+{y}")
        
        # Dialog content
        tk.Label(
            self.dialog,
            text=f"CAPTCHA Detected",
            font=("Arial", 14, "bold")
        ).pack(pady=10)
        
        tk.Label(
            self.dialog,
            text=f"Tender: {self.identifier[:50]}...",
            wraplength=350
        ).pack(pady=5)
        
        tk.Label(
            self.dialog,
            text="Please solve the CAPTCHA in your browser,\nthen choose an option below:",
            justify=tk.CENTER
        ).pack(pady=10)
        
        # Buttons frame
        button_frame = tk.Frame(self.dialog)
        button_frame.pack(pady=20)
        
        tk.Button(
            button_frame,
            text="CAPTCHA Solved - Continue",
            command=lambda: self._set_result("solved"),
            bg="green",
            fg="white",
            width=20
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="Skip This Item",
            command=lambda: self._set_result("skip"),
            bg="orange",
            fg="white",
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="Cancel All",
            command=lambda: self._set_result("cancel"),
            bg="red",
            fg="white",
            width=15
        ).pack(side=tk.LEFT, padx=5)
        
        # Handle window close
        self.dialog.protocol("WM_DELETE_WINDOW", lambda: self._set_result("cancel"))
        
        # Wait for user response
        self.dialog.wait_window()
        return self.result
        
    def _set_result(self, result):
        """Set the result and close dialog."""
        self.result = result
        if result == "cancel":
            self.stop_event.set()
        self.dialog.destroy()