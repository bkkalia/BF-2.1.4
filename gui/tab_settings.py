# gui/tab_settings.py v2.1.4
# Widgets and logic for the Settings tab

import tkinter as tk
from tkinter import ttk, Frame, Label, Button, filedialog
import logging
import os
import webbrowser
import datetime

# Absolute imports from project root
from config import (
    BASE_URLS_FILENAME, LOG_DIR_NAME, DEFAULT_DOWNLOAD_DIR_NAME,
    PAGE_LOAD_TIMEOUT, ELEMENT_WAIT_TIMEOUT, STABILIZE_WAIT, POST_ACTION_WAIT,
    POST_CAPTCHA_WAIT, CAPTCHA_CHECK_TIMEOUT, DOWNLOAD_WAIT_TIMEOUT, POPUP_WAIT_TIMEOUT, POST_DOWNLOAD_CLICK_WAIT,
    APP_VERSION, DEFAULT_APP_NAME
)
from app_settings import save_settings, DEFAULT_SETTINGS_STRUCTURE
from gui import gui_utils

logger = logging.getLogger(__name__)

class SettingsTab(ttk.Frame):
    """Frame containing application settings and configuration options."""

    def __init__(self, parent, main_app_ref, **kwargs):
        super().__init__(parent, **kwargs)
        self.main_app = main_app_ref
        self._create_widgets()

    def _create_widgets(self):
        section = ttk.Labelframe(self, text="Application Settings", style="Section.TLabelframe")
        section.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
        row = 0

        # Download Settings
        ttk.Label(section, text="Download Folder:", font=self.main_app.label_font).grid(row=row, column=0, sticky="w", padx=5, pady=3)
        ttk.Entry(section, textvariable=self.main_app.download_dir_var, width=50).grid(row=row, column=1, sticky="ew", padx=5, pady=3)
        ttk.Button(section, text="Browse...", command=self.main_app.browse_download_dir, width=10).grid(row=row, column=2, padx=5, pady=3)
        
        # Download Options
        row += 1
        ttk.Label(section, text="Download Options:", font=self.main_app.label_font).grid(row=row, column=0, sticky="w", padx=5, pady=3)
        dl_frame = ttk.Frame(section)
        dl_frame.grid(row=row, column=1, columnspan=2, sticky="w", padx=5, pady=3)
        ttk.Checkbutton(dl_frame, text="More Details PDF", variable=self.main_app.dl_more_details_var).pack(side=tk.LEFT, padx=(0,10))
        ttk.Checkbutton(dl_frame, text="ZIP File", variable=self.main_app.dl_zip_var).pack(side=tk.LEFT, padx=(0,10))
        ttk.Checkbutton(dl_frame, text="Notice PDFs", variable=self.main_app.dl_notice_pdfs_var).pack(side=tk.LEFT)

        # Deep Scrape Option
        row += 1
        ttk.Label(section, text="Scrape Mode:", font=self.main_app.label_font).grid(row=row, column=0, sticky="w", padx=5, pady=3)
        ttk.Checkbutton(section, text="Deep Scrape by Department (slower, more details)", 
                       variable=self.main_app.deep_scrape_departments_var).grid(row=row, column=1, columnspan=2, sticky="w", padx=5, pady=3)

        # Driver Settings
        row += 1
        ttk.Label(section, text="Driver Settings:", font=self.main_app.label_font).grid(row=row, column=0, sticky="w", padx=5, pady=3)
        driver_frame = ttk.Frame(section)
        driver_frame.grid(row=row, column=1, columnspan=2, sticky="w", padx=5, pady=3)
        ttk.Checkbutton(driver_frame, text="Use Undetected Driver", 
                       variable=self.main_app.use_undetected_driver_var).pack(side=tk.LEFT, padx=(0,10))
        ttk.Checkbutton(driver_frame, text="Headless Mode", 
                       variable=self.main_app.headless_mode_var).pack(side=tk.LEFT)

        # Theme Selection
        row += 1
        ttk.Label(section, text="Application Theme:", font=self.main_app.label_font).grid(row=row, column=0, sticky="w", padx=5, pady=3)
        theme_frame = ttk.Frame(section)
        theme_frame.grid(row=row, column=1, columnspan=2, sticky="w", padx=5, pady=3)
        self.theme_combo = ttk.Combobox(theme_frame, textvariable=self.main_app.selected_theme_var,
                                      values=self.main_app.get_available_themes(), state="readonly", width=20)
        self.theme_combo.pack(side=tk.LEFT, padx=(0,10))
        ttk.Button(theme_frame, text="Apply Theme", 
                  command=self.main_app.apply_selected_theme).pack(side=tk.LEFT)

        # Timeout Settings
        row += 1
        timeout_frame = ttk.LabelFrame(section, text="Timeout Settings (seconds)", padding=5)
        timeout_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=5, pady=(10,5))
        
        for i, (key) in enumerate(self.main_app.timeout_vars.keys()):
            r, c = divmod(i, 2)
            ttk.Label(timeout_frame, text=f"{key.replace('_', ' ').title()}:").grid(
                row=r, column=c*2, sticky="w", padx=5, pady=2)
            ttk.Entry(timeout_frame, textvariable=self.main_app.timeout_vars[key], 
                     width=8).grid(row=r, column=c*2+1, sticky="w", padx=5, pady=2)

        # Buttons
        row += 1
        button_frame = ttk.Frame(section)
        button_frame.grid(row=row, column=0, columnspan=3, sticky="w", padx=5, pady=(15,5))
        ttk.Button(button_frame, text="Save Settings", command=self.main_app._save_current_settings,
                  style="Accent.TButton", width=15).pack(side=tk.LEFT, padx=(0,10))
        ttk.Button(button_frame, text="Reset to Defaults", 
                  command=self.main_app.reset_to_defaults, width=15).pack(side=tk.LEFT)

        section.columnconfigure(1, weight=1)

    def _init_default_download_dir(self):
        # Default: Downloads/DEFAULT_DOWNLOAD_DIR_NAME_YYYYMMDD_HHMMSS
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        dt_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_dir = os.path.join(downloads, f"{DEFAULT_DOWNLOAD_DIR_NAME}_{dt_str}")
        self.download_dir_var.set(default_dir)

    def _browse_download_dir(self):
        folder = filedialog.askdirectory(
            title="Select Download Folder",
            initialdir=os.path.expanduser("~")
        )
        if folder:
            self.download_dir_var.set(folder)
            self.log_callback(f"Download folder set to: {folder}")

    def _save_timeouts(self):
        # Save timeouts to main_app and optionally to settings
        for key, var in self.timeout_vars.items():
            value = var.get()
            setattr(self.main_app, key, value)
            # Optionally, save to settings file:
            # self.main_app.settings[key] = value
        self.log_callback("Timeouts updated in memory (restart may be required for all changes).")
        gui_utils.show_message("Timeouts Updated", "Timeout values have been updated for this session.", type="info", parent=self.main_app.root)

    def _quit_app(self):
        self.main_app.on_closing(force_quit=True)

    def open_log_folder(self):
        gui_utils.open_folder(self.abs_log_dir, self.log_callback)

    def open_base_urls_csv(self):
        csv_path = self.abs_base_urls_file
        self.log_callback(f"Attempting to open configuration file: {csv_path}")
        if os.path.exists(csv_path):
            try:
                os.startfile(csv_path)
            except AttributeError:
                try:
                    webbrowser.open(f"file://{csv_path}")
                except Exception as e:
                    logger.error(f"Could not open {csv_path}: {e}", exc_info=True)
                    self.log_callback(f"Error opening {csv_path}: {e}")
                    gui_utils.show_message("Error", f"Could not automatically open '{BASE_URLS_FILENAME}'.\nPlease open it manually.\n\nPath: {csv_path}", type="error", parent=self.main_app.root)
            except Exception as e:
                logger.error(f"Could not open {csv_path}: {e}", exc_info=True)
                self.log_callback(f"Error opening {csv_path}: {e}")
                gui_utils.show_message("Error", f"Could not automatically open '{BASE_URLS_FILENAME}'.\nPlease open it manually.\n\nPath: {csv_path}", type="error", parent=self.main_app.root)
        else:
            self.log_callback(f"Configuration file not found: {csv_path}")
            gui_utils.show_message("File Not Found", f"The configuration file '{BASE_URLS_FILENAME}' was not found.\nIt should be in the same directory as the application.\n\nExpected Path: {csv_path}", type="error", parent=self.main_app.root)
