# scraper/captcha_handler.py v2.2.1
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

# New: cross-platform, simple sound helper (Windows winsound preferred)
winsound = None
try:
    import winsound
    _WINSOUND_AVAILABLE = True
except Exception:
    _WINSOUND_AVAILABLE = False

# Import selenium exceptions
try:
    from selenium.common.exceptions import NoSuchElementException, WebDriverException
    SELENIUM_IMPORTED = True
except ImportError:
    NoSuchElementException = Exception
    WebDriverException = Exception
    SELENIUM_IMPORTED = False

# Sound constants
SOUND_DING = "ding"
SOUND_SUCCESS = "success"
SOUND_ERROR = "error"

def play_sound(kind: str) -> None:
    """Play a short sound for UI feedback. Uses winsound on Windows, fallback to ASCII bell."""
    try:
        if _WINSOUND_AVAILABLE:
            if kind == SOUND_DING:
                winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)  # type: ignore
            elif kind == SOUND_SUCCESS:
                winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)  # type: ignore
            elif kind == SOUND_ERROR:
                winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC)  # type: ignore
            else:
                winsound.Beep(1000, 120)  # type: ignore
        else:
            # Fallback: ASCII bell (may be suppressed by environment)
            print("\a", end="", flush=True)
    except Exception:
        # Best-effort only; do not raise from sound helper
        pass

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

def _detect_captcha_elements(driver, identifier, log_callback):
    """Detect various CAPTCHA elements on the page."""
    from config import CAPTCHA_IMAGE_LOCATOR, CAPTCHA_INPUT_LOCATOR, CAPTCHA_PROMPT_LOCATOR

    captcha_indicators = [
        (CAPTCHA_IMAGE_LOCATOR, "CAPTCHA image"),
        (CAPTCHA_INPUT_LOCATOR, "CAPTCHA input field"),
        (CAPTCHA_PROMPT_LOCATOR, "CAPTCHA prompt")
    ]

    for locator, description in captcha_indicators:
        try:
            element = driver.find_element(*locator)
            if element and element.is_displayed():
                log_callback(f"{description} detected for {identifier}")
                return True
        except (NoSuchElementException, WebDriverException):
            continue

    return False

def _handle_captcha_dialog(identifier, log_callback, status_callback, stop_event):
    """Show CAPTCHA dialog and handle user response."""
    log_callback(f"CAPTCHA detected for {identifier} - showing user dialog")
    status_callback(f"CAPTCHA required for {identifier}")

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

def handle_captcha(driver, identifier, log_callback, status_callback, stop_event):
    """
    Enhanced CAPTCHA handling with GUI dialog and user interaction.
    """
    if not SELENIUM_IMPORTED:
        log_callback("CAPTCHA handling skipped - Selenium not available")
        return True

    try:
        # Check for CAPTCHA elements
        if not _detect_captcha_elements(driver, identifier, log_callback):
            log_callback(f"No CAPTCHA detected for {identifier}")
            return True

        # Handle CAPTCHA dialog
        return _handle_captcha_dialog(identifier, log_callback, status_callback, stop_event)

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
        self.dialog.resizable(False, False)
        self.dialog.grab_set()  # Make modal

        # Keep on top
        try:
            self.dialog.attributes("-topmost", True)
        except Exception:
            pass

        # Center the dialog and add padding
        width, height = 520, 220
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")

        # Outer frame with padding to give nicer spacing
        outer = tk.Frame(self.dialog, padx=14, pady=10)
        outer.pack(fill=tk.BOTH, expand=True)

        # Dialog content
        tk.Label(
            outer,
            text="CAPTCHA Detected",
            font=("Arial", 14, "bold")
        ).pack(pady=(2, 6))

        tk.Label(
            outer,
            text=f"Tender: {self.identifier[:60]}...",
            wraplength=480
        ).pack(pady=4)

        tk.Label(
            outer,
            text="Please solve the CAPTCHA in your browser,\nthen choose an option below:",
            justify=tk.CENTER
        ).pack(pady=(6, 8))

        # Buttons frame
        button_frame = tk.Frame(outer)
        button_frame.pack(pady=6)

        tk.Button(
            button_frame,
            text="CAPTCHA Solved - Continue",
            command=lambda: self._set_result("solved"),
            bg="green",
            fg="white",
            width=22
        ).pack(side=tk.LEFT, padx=6)

        tk.Button(
            button_frame,
            text="Skip This Item",
            command=lambda: self._set_result("skip"),
            bg="orange",
            fg="white",
            width=15
        ).pack(side=tk.LEFT, padx=6)

        tk.Button(
            button_frame,
            text="Cancel All",
            command=lambda: self._set_result("cancel"),
            bg="red",
            fg="white",
            width=15
        ).pack(side=tk.LEFT, padx=6)

        # Handle window close
        self.dialog.protocol("WM_DELETE_WINDOW", lambda: self._set_result("cancel"))

        # Ensure focus and play ding
        try:
            self.dialog.lift()
            self.dialog.focus_force()
            self.dialog.after(50, lambda: self.dialog.focus_set())  # type: ignore
            play_sound(SOUND_DING)  # Play ding when CAPTCHA dialog appears
        except Exception:
            pass

        # Wait for user response
        self.dialog.wait_window()
        return self.result
        
    def _set_result(self, result):
        """Set the result and close dialog."""
        self.result = result
        if result == "cancel":
            # inform caller to stop work
            self.stop_event.set()
        if self.dialog:
            try:
                self.dialog.destroy()
            except Exception:
                pass
