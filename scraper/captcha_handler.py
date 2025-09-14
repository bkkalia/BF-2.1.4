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

import tkinter as tk
from tkinter import messagebox

logger = logging.getLogger(__name__)

def handle_captcha(driver, identifier, target_subfolder, log_callback, status_callback, stop_event):
    """Enhanced CAPTCHA handler with GUI popup dialog."""
    
    def show_captcha_dialog():
        """Show CAPTCHA dialog asking if user has filled the CAPTCHA."""
        try:
            # Get browser information
            browser_url = driver.current_url if driver else "Unknown"
            
            # Extract portal name from URL
            portal_name = "Unknown Portal"
            if "hptenders" in browser_url.lower():
                portal_name = "HP Tenders"
            elif "arunachaltenders" in browser_url.lower():
                portal_name = "Arunachal Tenders"
            elif "nagalandtenders" in browser_url.lower():
                portal_name = "Nagaland Tenders"
            
            # Create custom dialog
            dialog_result = {'choice': None, 'completed': False}
            
            def create_dialog():
                # Create dialog window
                dialog = tk.Toplevel()
                dialog.title("CAPTCHA Verification")
                dialog.geometry("480x300")
                dialog.resizable(False, False)
                dialog.grab_set()  # Make dialog modal
                dialog.attributes('-topmost', True)  # Keep on top
                
                # Center the dialog
                dialog.update_idletasks()
                x = (dialog.winfo_screenwidth() // 2) - (480 // 2)
                y = (dialog.winfo_screenheight() // 2) - (300 // 2)
                dialog.geometry(f"480x300+{x}+{y}")
                
                # Configure dialog background
                dialog.configure(bg='white')
                
                # Main frame with padding
                main_frame = tk.Frame(dialog, bg='white', padx=20, pady=20)
                main_frame.pack(fill=tk.BOTH, expand=True)
                
                # Title with icon
                title_frame = tk.Frame(main_frame, bg='white')
                title_frame.pack(fill=tk.X, pady=(0, 20))
                
                title_label = tk.Label(
                    title_frame, 
                    text="🔐 CAPTCHA Required",
                    font=("Arial", 18, "bold"),
                    fg="#d32f2f",
                    bg='white'
                )
                title_label.pack()
                
                # Tender information
                info_frame = tk.Frame(main_frame, bg='white')
                info_frame.pack(fill=tk.X, pady=(0, 20))
                
                tk.Label(
                    info_frame, 
                    text=f"Portal: {portal_name}",
                    font=("Arial", 11, "bold"),
                    fg="#1976d2",
                    bg='white'
                ).pack()
                
                tk.Label(
                    info_frame, 
                    text=f"Tender ID: {identifier}",
                    font=("Arial", 11),
                    fg="#388e3c",
                    bg='white'
                ).pack()
                
                # Main question
                question_frame = tk.Frame(main_frame, bg='white')
                question_frame.pack(fill=tk.X, pady=(0, 25))
                
                question_label = tk.Label(
                    question_frame,
                    text="Did you fill the CAPTCHA in the browser?",
                    font=("Arial", 14, "bold"),
                    fg="#424242",
                    bg='white'
                )
                question_label.pack()
                
                # Instruction
                instruction_label = tk.Label(
                    question_frame,
                    text="(Switch to browser, solve CAPTCHA, then answer below)",
                    font=("Arial", 10),
                    fg="#757575",
                    bg='white'
                )
                instruction_label.pack(pady=(5, 0))
                
                # Button frame
                button_frame = tk.Frame(main_frame, bg='white')
                button_frame.pack(fill=tk.X, pady=(10, 0))
                
                # Center the buttons
                button_container = tk.Frame(button_frame, bg='white')
                button_container.pack(expand=True)
                
                def on_yes():
                    dialog_result['choice'] = 'yes'
                    dialog_result['completed'] = True
                    dialog.destroy()
                
                def on_no():
                    # Show confirmation dialog
                    confirm_result = tk.messagebox.askyesno(
                        "Confirm Cancellation",
                        "Do you really want to cancel scraping this tender?\n\n"
                        f"Tender: {identifier}\n"
                        f"Portal: {portal_name}",
                        icon='warning',
                        parent=dialog
                    )
                    
                    if confirm_result:  # User confirmed cancellation
                        dialog_result['choice'] = 'no'
                        dialog_result['completed'] = True
                        dialog.destroy()
                    # If user said no to confirmation, dialog stays open
                
                def on_close():
                    # Treat window close as "No" with confirmation
                    on_no()
                
                # Yes Button (Continue)
                yes_btn = tk.Button(
                    button_container,
                    text="✓ Yes, Continue",
                    command=on_yes,
                    bg="#4caf50",
                    fg="white",
                    font=("Arial", 14, "bold"),
                    padx=30,
                    pady=10,
                    relief="raised",
                    bd=3,
                    cursor="hand2",
                    activebackground="#45a049"
                )
                yes_btn.pack(side=tk.LEFT, padx=(0, 20))
                
                # No Button (Cancel)
                no_btn = tk.Button(
                    button_container,
                    text="✗ No, Cancel",
                    command=on_no,
                    bg="#f44336",
                    fg="white",
                    font=("Arial", 14, "bold"),
                    padx=30,
                    pady=10,
                    relief="raised",
                    bd=3,
                    cursor="hand2",
                    activebackground="#e53935"
                )
                no_btn.pack(side=tk.LEFT)
                
                # Keyboard shortcuts info
                shortcuts_frame = tk.Frame(main_frame, bg='white')
                shortcuts_frame.pack(fill=tk.X, pady=(15, 0))
                
                shortcuts_label = tk.Label(
                    shortcuts_frame,
                    text="⌨️ Y or Space = Yes  •  N or Esc = No  •  Alt+Tab = Switch Window",
                    font=("Arial", 9),
                    fg="#9e9e9e",
                    bg='white'
                )
                shortcuts_label.pack()
                
                # Handle window close
                dialog.protocol("WM_DELETE_WINDOW", on_close)
                
                # Bind keyboard shortcuts
                dialog.bind('<Return>', lambda e: on_yes())
                dialog.bind('<KP_Enter>', lambda e: on_yes())
                dialog.bind('<space>', lambda e: on_yes())
                dialog.bind('<y>', lambda e: on_yes())
                dialog.bind('<Y>', lambda e: on_yes())
                
                dialog.bind('<Escape>', lambda e: on_no())
                dialog.bind('<n>', lambda e: on_no())
                dialog.bind('<N>', lambda e: on_no())
                
                # Additional shortcuts
                dialog.bind('<Control-w>', lambda e: on_no())
                dialog.bind('<Alt-F4>', lambda e: on_no())
                
                # Tab navigation between buttons
                def focus_next_button(event):
                    if yes_btn == dialog.focus_get():
                        no_btn.focus_set()
                    else:
                        yes_btn.focus_set()
                
                def focus_prev_button(event):
                    if no_btn == dialog.focus_get():
                        yes_btn.focus_set()
                    else:
                        no_btn.focus_set()
                
                dialog.bind('<Tab>', focus_next_button)
                dialog.bind('<Shift-Tab>', focus_prev_button)
                dialog.bind('<Left>', focus_prev_button)
                dialog.bind('<Right>', focus_next_button)
                
                # Visual feedback on focus
                def on_button_focus_in(event, button):
                    button.configure(relief="solid", bd=4)
                
                def on_button_focus_out(event, button):
                    button.configure(relief="raised", bd=3)
                
                yes_btn.bind('<FocusIn>', lambda e: on_button_focus_in(e, yes_btn))
                yes_btn.bind('<FocusOut>', lambda e: on_button_focus_out(e, yes_btn))
                no_btn.bind('<FocusIn>', lambda e: on_button_focus_in(e, no_btn))
                no_btn.bind('<FocusOut>', lambda e: on_button_focus_out(e, no_btn))
                
                # Set initial focus to Yes button
                yes_btn.focus_set()
                
                # Ensure dialog is visible and focused
                dialog.update()
                dialog.lift()
                dialog.focus_force()
                
                # Wait for dialog completion
                dialog.wait_window()
                
                return dialog_result
            
            # Run dialog in main thread
            return create_dialog()
            
        except Exception as e:
            logger.error(f"Error creating CAPTCHA dialog: {e}")
            # Fallback to simple messagebox
            result = messagebox.askyesno(
                "CAPTCHA Required",
                f"CAPTCHA verification required for tender: {identifier}\n\n"
                f"Did you fill the CAPTCHA in the browser?\n\n"
                f"Yes = Continue scraping\n"
                f"No = Cancel scraping",
                icon='question'
            )
            return {'choice': 'yes' if result else 'no', 'completed': True}
    
    try:
        # Check if CAPTCHA elements are present
        captcha_detected = False
        
        try:
            # Check for common CAPTCHA indicators
            from config import CAPTCHA_IMAGE_LOCATOR, CAPTCHA_INPUT_LOCATOR, CAPTCHA_PROMPT_LOCATOR
            
            captcha_image = driver.find_elements(*CAPTCHA_IMAGE_LOCATOR)
            captcha_input = driver.find_elements(*CAPTCHA_INPUT_LOCATOR)
            captcha_prompt = driver.find_elements(*CAPTCHA_PROMPT_LOCATOR)
            
            if captcha_image or captcha_input or captcha_prompt:
                captcha_detected = True
                log_callback(f"CAPTCHA detected for '{identifier}' - showing GUI dialog")
                
        except Exception as detection_err:
            # Check for CAPTCHA in page source as fallback
            page_source = driver.page_source.lower()
            captcha_keywords = ['captcha', 'verification', 'security code', 'human verification']
            
            if any(keyword in page_source for keyword in captcha_keywords):
                captcha_detected = True
                log_callback(f"CAPTCHA likely detected for '{identifier}' (page source analysis)")
        
        if not captcha_detected:
            log_callback(f"No CAPTCHA detected for '{identifier}'")
            return True
        
        # Update status
        status_callback(f"CAPTCHA verification required: {identifier[:25]}...")
        
        # Show GUI dialog (this will block until user responds)
        dialog_result = show_captcha_dialog()
        
        if not dialog_result or not dialog_result.get('completed'):
            log_callback("CAPTCHA dialog error or timeout")
            return False
        
        user_choice = dialog_result.get('choice')
        
        if user_choice == 'yes':
            log_callback(f"User confirmed CAPTCHA filled for '{identifier}' - continuing")
            status_callback(f"Continuing scraping: {identifier[:25]}...")
            time.sleep(1)  # Brief pause before continuing
            return True
            
        elif user_choice == 'no':
            log_callback(f"User cancelled scraping for '{identifier}'")
            status_callback(f"Cancelled by user: {identifier[:25]}")
            
            # Set stop event to cancel current operation
            if stop_event:
                stop_event.set()
            return False
        
        else:
            log_callback(f"Unknown user choice: {user_choice}")
            return False
            
    except Exception as e:
        log_callback(f"Error in CAPTCHA handler: {e}")
        logger.error(f"CAPTCHA handler error: {e}", exc_info=True)
        
        # Fallback to simple dialog
        try:
            result = messagebox.askyesno(
                "CAPTCHA Error",
                f"Error handling CAPTCHA for tender: {identifier}\n\n"
                f"Did you fill the CAPTCHA?\n"
                f"Yes = Continue anyway\n"
                f"No = Cancel",
                icon='warning'
            )
            return result
        except Exception:
            return False