import tkinter as tk
from tkinter import ttk, scrolledtext, font as tkFont, StringVar, BooleanVar, filedialog
import logging
import os
import sys
import threading
from datetime import datetime

# --- Ensure project root in sys.path ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if (PROJECT_ROOT not in sys.path):
    sys.path.insert(0, PROJECT_ROOT)

# --- Import application components ---
from gui import gui_utils
from gui.gui_utils import EmergencyStopDialog
from config import (
    APP_VERSION, APP_AUTHOR, DEFAULT_APP_NAME,
    CONFIGURABLE_TIMEOUTS, DEFAULT_THEME,
    USE_UNDETECTED_DRIVER_DEFAULT, HEADLESS_MODE_DEFAULT,
    DEEP_SCRAPE_DEPARTMENTS_DEFAULT,
    AVAILABLE_THEMES, PRIMARY_COLOR, SECONDARY_COLOR, TEXT_COLOR, HOVER_COLOR,  # added HOVER_COLOR
    LOG_DIR_NAME, BASE_URLS_FILENAME
)
from app_settings import FALLBACK_URL_CONFIG, save_settings, DEFAULT_SETTINGS_STRUCTURE
from gui.tab_department import DepartmentTab
from gui.tab_id_search import IdSearchTab
from gui.tab_url_process import UrlProcessTab
from gui.tab_settings import SettingsTab
from scraper.webdriver_manager import get_driver, quit_driver  # Add this import
from scraper.driver_manager import setup_driver, safe_quit_driver  # Add setup_driver import
from gui.tab_help import HelpTab


logger = logging.getLogger(__name__)

class MainWindow:
    """Main application window with sidebar navigation and persistent log/status."""
    def __init__(self, root, settings, base_urls_data, settings_filepath, abs_default_download_dir):
        print("MainWindow initialization started...")
        try:
            self.root = root
            print("Root assigned")
            
            self.settings = settings
            print("Settings assigned")
            
            self.base_urls_data = base_urls_data if isinstance(base_urls_data, list) and base_urls_data else [FALLBACK_URL_CONFIG.copy()]
            print("Base URLs processed")
            
            self.settings_filepath = settings_filepath
            self.abs_default_download_dir = abs_default_download_dir
            print("Paths assigned")

            self.app_version = APP_VERSION
            self.app_author = APP_AUTHOR
            self.app_name = DEFAULT_APP_NAME
            print("App info assigned")

            # Initialize state variables
            print("Initializing state variables...")
            self.scraping_in_progress = False
            self.stop_event = threading.Event()
            self.background_thread = None
            self.start_time = None
            self.timer_id = None
            self.total_estimated_tenders_for_run = 0
            print("State variables initialized")

            # Initialize Tkinter variables
            print("Initializing Tkinter variables...")
            self._init_tkinter_vars()
            print("Tkinter variables initialized")
            
            # Configure window
            print("Configuring window...")
            self._configure_window()
            print("Window configured")
            
            # Configure styles and build layout
            print("Configuring styles and building layout...")
            self._configure_styles_and_fonts()
            
            # Initialize logging
            print("Initializing logging methods...")
            self._init_logging_methods()
            
            # Build the layout (now that logging is ready)
            self._build_layout()
            print("Layout completed")
            
            # Add WebDriver state
            self.driver = None
            print("WebDriver state initialized")
            
            print("MainWindow initialization completed successfully")
            
        except Exception as e:
            print(f"Error in MainWindow initialization: {e}")
            logging.error(f"MainWindow initialization failed: {e}", exc_info=True)
            raise

    def _init_logging_methods(self):
        """Initialize logging-related methods early."""
        self.update_log = self._update_log_impl
        self.update_status = lambda message: gui_utils.update_status(self.status_label, message)
        
        # Simplified progress callback with correct parameter mapping
        self.update_progress = lambda current=0, total=0, details=None, *args: gui_utils.update_progress(
            self.progress_bar,
            self.progress_details_label, 
            self.est_rem_label,
            current,                  # Current count
            total,                    # Total items
            None,                     # Percent (calculated in gui_utils)
            details,                  # Details text
            None,                     # Est. remaining (calculated in gui_utils)
            self.scraping_in_progress # Scraping status
        )

    def _update_log_impl(self, message):
        """Implementation of the log update functionality."""
        try:
            if not message:
                return
            if not isinstance(message, str):
                message = str(message)
            if hasattr(self, 'log_text') and self.log_text and not self.stop_event.is_set():
                gui_utils.update_log(self.log_text, message)
                logger.debug(f"Log updated: {message[:100]}")
        except Exception as e:
            logger.error(f"Error updating log: {e}")

    def _init_tkinter_vars(self):
        """Initialize all Tkinter variables."""
        # Main settings variables
        self.download_dir_var = StringVar(value=self.settings.get("download_directory", self.abs_default_download_dir))
        self.dl_more_details_var = BooleanVar(value=self.settings.get("dl_more_details", True))
        self.dl_zip_var = BooleanVar(value=self.settings.get("dl_zip", True))
        self.dl_notice_pdfs_var = BooleanVar(value=self.settings.get("dl_notice_pdfs", True))
        
        # Advanced settings variables
        self.deep_scrape_departments_var = BooleanVar(value=self.settings.get("deep_scrape_departments", DEEP_SCRAPE_DEPARTMENTS_DEFAULT))
        self.selected_theme_var = StringVar(value=self.settings.get("selected_theme", DEFAULT_THEME))
        self.use_undetected_driver_var = BooleanVar(value=self.settings.get("use_undetected_driver", USE_UNDETECTED_DRIVER_DEFAULT))
        self.headless_mode_var = BooleanVar(value=self.settings.get("headless_mode", HEADLESS_MODE_DEFAULT))

        # Initialize timeout variables
        self.timeout_vars = {}
        for key in CONFIGURABLE_TIMEOUTS:
            self.timeout_vars[key] = StringVar(value=str(self.settings.get(key, 0)))

        # Selected URL initialization
        valid_url_names = [d.get("Name") for d in self.base_urls_data if d.get("Name")]
        initial_url_name = self.settings.get("selected_url_name")
        if not initial_url_name or initial_url_name not in valid_url_names:
            initial_url_name = valid_url_names[0] if valid_url_names else FALLBACK_URL_CONFIG["Name"]
        self.selected_url_name_var = StringVar(value=initial_url_name)

        # Sound settings variables
        self.enable_sounds_var = BooleanVar(value=self.settings.get("enable_sounds", True))
        self.sound_ding_var = StringVar(value=self.settings.get("sound_ding_file", ""))
        self.sound_success_var = StringVar(value=self.settings.get("sound_success_file", ""))
        self.sound_error_var = StringVar(value=self.settings.get("sound_error_file", ""))

        # Additional paths needed for settings tab
        self.abs_log_dir = os.path.join(os.path.dirname(self.settings_filepath), LOG_DIR_NAME)
        self.abs_base_urls_file = os.path.join(os.path.dirname(self.settings_filepath), BASE_URLS_FILENAME)

    def _configure_window(self):
        """Configure main window properties."""
        self.root.configure(bg="#f5f7fa")
        self.root.title(f"{self.app_name} v{self.app_version}")
        self.root.geometry(self.settings.get("window_geometry", "1150x780"))
        self.root.minsize(950, 650)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _configure_styles_and_fonts(self):
        """Configure ttk styles and fonts."""
        # Try to use Star Wars font for ASCII styling (assuming it's installed)
        try:
            # Check if Star Wars font is available
            available_fonts = tkFont.families()
            starwars_family = None
            for font_name in available_fonts:
                if 'star wars' in font_name.lower() or 'starwars' in font_name.lower():
                    starwars_family = font_name
                    break

            if starwars_family:
                self.starwars_font = tkFont.Font(family=starwars_family, size=24)
                logging.info(f"✓ Star Wars font '{starwars_family}' loaded successfully")
            else:
                # Try to register the font if not available
                starwars_font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "starwars.ttf")
                if os.path.exists(starwars_font_path):
                    # Note: tkinter doesn't support loading TTF files directly
                    # This would require additional libraries or system font installation
                    logging.warning("Star Wars font file found but tkinter cannot load TTF files directly")
                    self.starwars_font = tkFont.Font(family="Segoe UI", size=18, weight="bold")
                else:
                    logging.warning("Star Wars font file not found")
                    self.starwars_font = tkFont.Font(family="Segoe UI", size=18, weight="bold")
        except Exception as e:
            logging.warning(f"Could not load Star Wars font: {e}, falling back to default")
            self.starwars_font = tkFont.Font(family="Segoe UI", size=18, weight="bold")

        self.heading_font = self.starwars_font
        self.subheading_font = tkFont.Font(family="Segoe UI", size=12, weight="bold")
        self.label_font = tkFont.Font(family="Segoe UI", size=11)
        self.button_font = tkFont.Font(family="Segoe UI", size=11, weight="bold")
        self.status_font = tkFont.Font(family="Segoe UI", size=10)
        self.log_font = ("Consolas", 10)
        self.listbox_font = ("Consolas", 10)

        style = ttk.Style()
        current_theme = self.selected_theme_var.get()
        try:
            style.theme_use(current_theme)
            
            # Theme-specific color adjustments
            if current_theme in ['clam', 'alt']:
                bg_color = "#f5f7fa"
                button_bg = "#37474F"
                accent_bg = SECONDARY_COLOR   # use config secondary
            elif current_theme in ['default', 'classic']:
                bg_color = "#e1e1e1"
                button_bg = "#4a4a4a"
                accent_bg = PRIMARY_COLOR     # use config primary
            else:  # vista, xpnative, etc.
                bg_color = style.lookup('TFrame', 'background')
                button_bg = style.lookup('TButton', 'background')
                accent_bg = SECONDARY_COLOR

            # Apply theme colors
            self.root.configure(bg=bg_color)
            style.configure('TFrame', background=bg_color)
            style.configure('Content.TFrame', background=bg_color)
            style.configure('Section.TLabelframe', background=bg_color)
            style.configure('Section.TLabelframe.Label', background=bg_color)

        except tk.TclError:
            logger.warning(f"Theme '{current_theme}' not available, defaulting to '{DEFAULT_THEME}'")
            self.selected_theme_var.set(DEFAULT_THEME)
            style.theme_use(DEFAULT_THEME)

        # Sidebar style
        style.configure('Sidebar.TFrame', background="#263238")
        style.configure('Sidebar.TButton', font=self.button_font, foreground=TEXT_COLOR, background="#37474F", padding=10, width=15, anchor='w')
        style.map('Sidebar.TButton',
                  background=[('active', HOVER_COLOR), ('pressed', PRIMARY_COLOR), ('disabled', '#37474F')],
                  foreground=[('disabled', '#78909C')])

        # Header style — use PRIMARY_COLOR for header background
        style.configure('Header.TFrame', background=PRIMARY_COLOR)
        style.configure('Header.TLabel', background=PRIMARY_COLOR, foreground=TEXT_COLOR, font=self.heading_font)
        style.configure('Version.Header.TLabel', background=PRIMARY_COLOR, foreground=TEXT_COLOR, font=self.status_font)

        # Section Labelframe style
        style.configure('Section.TLabelframe', background="#f5f7fa", borderwidth=1, relief="groove")
        style.configure('Section.TLabelframe.Label', font=self.subheading_font, foreground=PRIMARY_COLOR, background="#f5f7fa")

        # Accent Button style (e.g., Start, Fetch) — use SECONDARY_COLOR
        style.configure('Accent.TButton', foreground=TEXT_COLOR, background=SECONDARY_COLOR, font=self.button_font)
        style.map('Accent.TButton', background=[("active", HOVER_COLOR), ('disabled', '#B0BEC5')])

        # Stop Button style
        self.stop_button_font = tkFont.Font(family="Segoe UI", size=9, weight="bold")
        style.configure("Danger.TButton", foreground="#FFFFFF", background="#C62828", font=self.stop_button_font)
        style.map("Danger.TButton", background=[("active", "#E53935"), ('disabled', '#EF9A9A')])

        # Progress bar and status area style
        style.configure('Status.TFrame', background="#ECEFF1")
        style.configure('Status.TLabel', background="#ECEFF1", font=self.status_font)
        style.configure('Content.TFrame', background="#f5f7fa")  # Set background for content area

    def _build_layout(self):
        """Build the main UI layout: Header, Sidebar, Content, Status Bar."""
        # --- Header ---
        header_frame = ttk.Frame(self.root, style='Header.TFrame', height=60)
        header_frame.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(header_frame, text=self.app_name, style='Header.TLabel').pack(side=tk.LEFT, padx=20, pady=10)
        ttk.Label(header_frame, text=f"v{self.app_version}", style='Version.Header.TLabel').pack(side=tk.RIGHT, padx=20, pady=10)

        # --- Main Area (Sidebar + Content) ---
        main_area = ttk.Frame(self.root)
        main_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # --- Sidebar ---
        sidebar_frame = ttk.Frame(main_area, style='Sidebar.TFrame', width=180)
        sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        sidebar_frame.pack_propagate(False)  # Prevent sidebar from shrinking to fit buttons

        self.sidebar_buttons = {}
        nav_items = [
            ("By Department", self._show_department),
            ("By Tender ID", self._show_id_search),
            ("By Direct URL", self._show_url_process),
            ("Settings", self._show_settings),
            ("Help", self._show_help),  # Add Help menu item
            ("Logs", self._show_logs),
        ]
        for idx, (label, cmd) in enumerate(nav_items):
            btn = ttk.Button(sidebar_frame, text=label, style='Sidebar.TButton', command=cmd)
            btn.pack(fill=tk.X, pady=(10 if idx == 0 else 2, 0), padx=10)
            self.sidebar_buttons[label] = btn

        # CLI Mode button below Logs
        cli_button = ttk.Button(sidebar_frame, text="CLI Mode", style='Sidebar.TButton', command=self.launch_cli_mode)
        cli_button.pack(fill=tk.X, pady=(10, 0), padx=10)
        self.sidebar_buttons["CLI Mode"] = cli_button

        # Exit button at the bottom of sidebar
        exit_button = ttk.Button(sidebar_frame, text="Exit", style='Sidebar.TButton', command=self.on_closing)
        exit_button.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(10, 20))

        # --- Content Area ---
        self.content_frame = ttk.Frame(main_area, style='Content.TFrame', padding=(10, 5))
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- Global Panel (above tabs, right side, same color as sidebar) ---
        self.global_panel = ttk.Frame(self.content_frame, style='Sidebar.TFrame', height=48)
        self.global_panel.pack(side=tk.TOP, fill=tk.X, padx=0, pady=(0, 5))
        self.global_panel.pack_propagate(False)

        # --- Global Panel Widgets: Filter Departments and Select URL ---
        self.filter_dept_label = ttk.Label(
            self.global_panel, text="Filter Departments:", font=self.label_font, background="#263238", foreground="#FFFFFF"
        )
        self.filter_dept_label.pack(side=tk.LEFT, padx=(10, 5), pady=8)
        self.filter_dept_entry = ttk.Entry(
            self.global_panel, textvariable=self.get_or_create_global_search_var(), width=32
        )
        self.filter_dept_entry.pack(side=tk.LEFT, padx=(0, 15), pady=8)

        self.select_url_label = ttk.Label(
            self.global_panel, text="Select URL:", font=self.label_font, background="#263238", foreground="#FFFFFF"
        )
        self.select_url_label.pack(side=tk.LEFT, padx=(0, 5), pady=8)
        self.select_url_combobox = ttk.Combobox(
            self.global_panel,
            textvariable=self.selected_url_name_var,
            values=[config.get("Name", "Unknown") for config in self.base_urls_data],
            state="readonly",
            width=32
        )
        self.select_url_combobox.pack(side=tk.LEFT, padx=(0, 10), pady=8)

        # --- Bind filter logic to update URL dropdown ---
        self.get_or_create_global_search_var().trace_add("write", self._filter_url_combobox)

        # --- Section Frames (Tabs) ---
        self.section_frames = {}
        self._init_sections()

        # --- Always keep global panel visible and tabs below it ---
        self.global_panel.lift()
        # Adjust tab frames to start below the global panel and above the status bar
        self.content_frame.update_idletasks()
        global_panel_height = self.global_panel.winfo_reqheight() + 5
        # Calculate status bar height after it's created
        # --- Status Bar ---
        status_frame = ttk.Frame(self.root, style='Status.TFrame', height=44)  # Increased by 10% from 40 to 44
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_frame.pack_propagate(False)  # Prevent shrinking

        self.progress_bar = ttk.Progressbar(status_frame, orient="horizontal", length=250, mode="determinate")
        self.progress_bar.pack(side=tk.LEFT, padx=(15, 5), pady=8)
        self.progress_details_label = ttk.Label(status_frame, text="Processed: 0 / ~0", style='Status.TLabel', width=25, anchor='w')
        self.progress_details_label.pack(side=tk.LEFT, padx=5, pady=8)
        self.est_rem_label = ttk.Label(status_frame, text="Est. Rem: --:--:--", style='Status.TLabel', width=20, anchor='w')
        self.est_rem_label.pack(side=tk.LEFT, padx=5, pady=8)
        self.timer_label = ttk.Label(status_frame, text="Elapsed: 00:00:00", style='Status.TLabel', width=18, anchor='w')
        self.timer_label.pack(side=tk.LEFT, padx=5, pady=8)
        self.stop_button = ttk.Button(
            status_frame,
            text="EMERGENCY STOP",
            command=self.request_stop_scraping,
            style="Danger.TButton",
            width=15
        )
        self.stop_button.pack(side=tk.RIGHT, padx=(2, 5), pady=4)

        self.content_frame.update_idletasks()
        status_bar_height = status_frame.winfo_reqheight()

        # Place tab frames below the global panel and above the status bar
        for frame in self.section_frames.values():
            frame.place_configure(
                relx=0, rely=0, relwidth=1, relheight=1,
                y=global_panel_height,
                height=f"-{global_panel_height + status_bar_height}"
            )

    def get_or_create_global_search_var(self):
        """Ensure a global search_var exists for department filtering."""
        if not hasattr(self, 'global_search_var'):
            self.global_search_var = tk.StringVar()
        return self.global_search_var

    def _init_sections(self):
        """Create and place the frames for each navigable section."""
        logger.debug("Initializing section frames...")
        sections_to_create = {
            "By Department": DepartmentTab,
            "By Tender ID": IdSearchTab,
            "By Direct URL": UrlProcessTab,
            "Settings": SettingsTab,
            "Help": HelpTab,  # Add Help tab
        }
        for name, TabClass in sections_to_create.items():
            container_frame = ttk.Frame(self.content_frame, padding=0)
            tab_instance = TabClass(container_frame, self)
            tab_instance.pack(fill=tk.BOTH, expand=True)
            self.section_frames[name] = container_frame
            # Do not set y/height here, handled in _build_layout after status bar is created
            container_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            container_frame.lower()
            logger.debug(f"Initialized section: {name}")

        # --- Logs Tab (Special Handling) ---
        logs_container = ttk.Frame(self.content_frame, padding=0)
        logs_frame = ttk.Frame(logs_container, padding=(5, 5))
        logs_frame.pack(fill=tk.BOTH, expand=True)
        log_labelframe = ttk.Labelframe(logs_frame, text="Log Output", style="Section.TLabelframe")
        log_labelframe.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.log_text = scrolledtext.ScrolledText(
            log_labelframe, height=15, wrap=tk.WORD, state=tk.DISABLED,
            borderwidth=1, relief="solid", font=self.log_font, bg="#FFFFFF"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.status_label = ttk.Label(logs_frame, text="Status: Initializing...", font=self.status_font, anchor="w")
        self.status_label.pack(fill=tk.X, padx=5, pady=(5, 0))

        self.section_frames["Logs"] = logs_container
        logs_container.place(relx=0, rely=0, relwidth=1, relheight=1)
        logs_container.lower()
        logger.debug("Initialized section: Logs")
        logger.debug(f"Section frames initialized: {list(self.section_frames.keys())}")

    def _filter_url_combobox(self, *args):
        """Filter the URL dropdown based on filter entry (matches Name, BaseURL, or Keyword)."""
        term = self.get_or_create_global_search_var().get().lower().strip()
        filtered = []
        for config in self.base_urls_data:
            name = str(config.get("Name", "")).lower()
            baseurl = str(config.get("BaseURL", "")).lower()
            keyword = str(config.get("Keyword", "")).lower()
            if not term or (term in name or term in baseurl or term in keyword):
                filtered.append(config.get("Name", "Unknown"))
        if not filtered:
            filtered = ["No matching URLs found."]
        self.select_url_combobox['values'] = filtered
        # If the current selection is not in filtered, reset to first
        current = self.selected_url_name_var.get()
        if current not in filtered:
            self.selected_url_name_var.set(filtered[0])

    def _show_section(self, section_name):
        """Bring the specified section frame to the top and update sidebar buttons."""
        logger.debug(f"Attempting to show section: {section_name}")
        if section_name not in self.section_frames:
            logger.error(f"Section '{section_name}' not found in section_frames.")
            return
        frame_to_show = self.section_frames[section_name]
        frame_to_show.lift()
        self.global_panel.lift()  # Always keep global panel visible
        logger.debug(f"Lifted frame for section: {section_name}")
        for label, button in self.sidebar_buttons.items():
            if label == section_name:
                button.state(['pressed', '!disabled'])
            else:
                button.state(['!pressed'])

        # --- Filter logic connection ---
        # Only connect filter callback when By Department tab is active
        if section_name == "By Department":
            # Attach filter callback if not already attached
            if not hasattr(self, '_filter_trace_id'):
                dept_tab = self.section_frames["By Department"].winfo_children()[0]
                self._filter_trace_id = self.global_search_var.trace_add("write", dept_tab._filter_departments)
        else:
            # Remove filter callback if attached
            if hasattr(self, '_filter_trace_id'):
                try:
                    self.global_search_var.trace_remove("write", self._filter_trace_id)
                except Exception:
                    pass
                del self._filter_trace_id

    def _show_department(self): self._show_section("By Department")
    def _show_id_search(self): self._show_section("By Tender ID")
    def _show_url_process(self): self._show_section("By Direct URL")
    def _show_settings(self): self._show_section("Settings")
    def _show_help(self): self._show_section("Help")  # Add help method
    def _show_logs(self): self._show_section("Logs")

    def get_available_themes(self):
        """Returns list of available themes for the settings dialog."""
        try:
            style = ttk.Style()
            # First try getting system themes
            available = style.theme_names()
            # Filter to known supported themes
            supported = [theme for theme in available if theme in AVAILABLE_THEMES]
            if not supported:
                # Fallback to default list if no supported themes found
                logger.warning("No supported themes found in system, using fallback list")
                return AVAILABLE_THEMES
            return supported
        except Exception as e:
            logger.error(f"Error getting available themes: {e}")
            return [DEFAULT_THEME]  # Absolute fallback

    def apply_selected_theme(self):
        """Applies the currently selected theme and reconfigures styles."""
        try:
            new_theme = self.selected_theme_var.get()
            if new_theme not in self.get_available_themes():
                raise ValueError(f"Theme '{new_theme}' is not available")
            
            style = ttk.Style()
            style.theme_use(new_theme)
            
            # Define theme colors based on selected theme
            if new_theme in ['clam', 'alt']:
                colors = {
                    'bg': "#f5f7fa",
                    'fg': "#000000",
                    'button_bg': "#37474F",
                    'button_fg': "#FFFFFF",
                    'accent_bg': SECONDARY_COLOR,   # use config
                    'accent_fg': TEXT_COLOR,
                    'header_bg': PRIMARY_COLOR,     # use config
                    'header_fg': TEXT_COLOR,
                    'sidebar_bg': "#263238",
                    'sidebar_fg': TEXT_COLOR
                }
            else:  # default, classic, vista, xpnative
                colors = {
                    'bg': "#e1e1e1",
                    'fg': "#000000",
                    'button_bg': "#4a4a4a",
                    'button_fg': "#FFFFFF",
                    'accent_bg': PRIMARY_COLOR,
                    'accent_fg': TEXT_COLOR,
                    'header_bg': PRIMARY_COLOR,
                    'header_fg': TEXT_COLOR,
                    'sidebar_bg': "#263238",
                    'sidebar_fg': TEXT_COLOR
                }

            # Apply colors to all widgets
            style.configure('TFrame', background=colors['bg'])
            style.configure('TLabel', background=colors['bg'], foreground=colors['fg'])
            style.configure('TButton', background=colors['button_bg'], foreground=colors['button_fg'])
            
            # Header style
            style.configure('Header.TFrame', background=colors['header_bg'])
            style.configure('Header.TLabel', background=colors['header_bg'], foreground=colors['header_fg'])
            
            # Sidebar style
            style.configure('Sidebar.TFrame', background=colors['sidebar_bg'])
            style.configure('Sidebar.TButton', 
                          background=colors['button_bg'], 
                          foreground=colors['sidebar_fg'])
            
            # Update root and all frames
            self.root.configure(bg=colors['bg'])
            self.content_frame.configure(style='Content.TFrame')
            
            # Force update all widgets
            for frame in self.section_frames.values():
                frame.configure(style='Content.TFrame')
                for child in frame.winfo_children():
                    if isinstance(child, (ttk.Frame, ttk.LabelFrame)):
                        child.configure(style='Content.TFrame')
            
            # Save the setting
            self.settings["selected_theme"] = new_theme
            success = self._save_current_settings()
            
            if success:
                logger.info(f"Theme '{new_theme}' applied and saved successfully")
                self.update_log(f"Theme changed to: {new_theme}")
            else:
                logger.warning(f"Theme '{new_theme}' applied but settings save failed")
                self.update_log("Theme changed but settings save failed")
            
        except Exception as e:
            logger.error(f"Error applying theme: {e}")
            self.update_log(f"Failed to apply theme: {e}")
            self.selected_theme_var.set(DEFAULT_THEME)
            self._configure_styles_and_fonts()

    def _save_current_settings(self):
        """Gathers current settings from UI variables and saves them to the file."""
        logger.info("Saving current settings...")
        self.settings["download_directory"] = self.download_dir_var.get()
        self.settings["dl_more_details"] = self.dl_more_details_var.get()
        self.settings["dl_zip"] = self.dl_zip_var.get()
        self.settings["dl_notice_pdfs"] = self.dl_notice_pdfs_var.get()
        self.settings["selected_url_name"] = self.selected_url_name_var.get()
        self.settings["deep_scrape_departments"] = self.deep_scrape_departments_var.get()
        self.settings["selected_theme"] = self.selected_theme_var.get()
        self.settings["use_undetected_driver"] = self.use_undetected_driver_var.get()
        self.settings["headless_mode"] = self.headless_mode_var.get()

        # Sound settings
        self.settings["enable_sounds"] = self.enable_sounds_var.get()
        self.settings["sound_ding_file"] = self.sound_ding_var.get()
        self.settings["sound_success_file"] = self.sound_success_var.get()
        self.settings["sound_error_file"] = self.sound_error_var.get()

        # Handle timeout values - properly preserve float values
        for key, var in self.timeout_vars.items():
            try:
                # Convert to float first to preserve decimal values
                value = float(var.get())
                # Store as float to preserve decimal points
                self.settings[key] = value
            except ValueError:
                logger.warning(f"Invalid timeout value for {key}: {var.get()}, using 0")
                self.settings[key] = 0.0

        try:
            if self.root.winfo_exists():
                self.settings["window_geometry"] = self.root.geometry()
        except tk.TclError:
            logger.warning("Could not get window geometry, possibly already be closed.")

        save_settings(self.settings, self.settings_filepath)
        self.update_log("Settings saved.")

    def start_background_task(self, func, args=None, kwargs=None, task_name="Task"):
        """Start a background task with proper error handling and UI updates."""
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}

        # Set scraping in progress and disable controls before starting the task
        self.scraping_in_progress = True
        self.set_controls_state(tk.DISABLED)

        def task_wrapper():
            driver = None
            try:
                # Create WebDriver instance for this task
                driver = setup_driver(initial_download_dir=self.download_dir_var.get())

                # Start timer for task
                self.root.after(0, self.start_timer_updates)

                # Add common args
                full_kwargs = {
                    'driver': driver,
                    'log_callback': self.update_log,
                    'progress_callback': self.update_progress,
                    'timer_callback': self.update_timer,
                    'status_callback': self.update_status,
                    'stop_event': self.stop_event,
                    'deep_scrape': self.deep_scrape_departments_var.get(),
                    'dl_more_details': self.dl_more_details_var.get(),
                    'dl_zip': self.dl_zip_var.get(),
                    'dl_notice_pdfs': self.dl_notice_pdfs_var.get(),
                    **kwargs
                }

                # Run the task
                func(*args, **full_kwargs)

            except Exception as e:
                self.update_log(f"Error in {task_name}: {e}")
                logger.error(f"Error in {task_name}", exc_info=True)
            finally:
                if driver:
                    safe_quit_driver(driver, self.update_log)
                self.scraping_in_progress = False
                self.root.after(0, self.stop_timer_updates)
                self.root.after(0, lambda: self.set_controls_state(tk.NORMAL))

        # Start the background thread
        task_thread = threading.Thread(
            target=task_wrapper,
            name=task_name,
            daemon=True
        )
        task_thread.start()
        self.background_thread = task_thread

    def stop_timer_updates(self):
        """Stop the timer updates."""
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
            self.start_time = None

    def start_timer_updates(self):
        """Start periodic timer updates."""
        self.start_time = datetime.now()
        self._update_timer()

    def _update_timer(self):
        """Update the timer display and schedule next update."""
        if self.start_time and self.scraping_in_progress:
            self.update_timer(self.start_time)
            self.timer_id = self.root.after(1000, self._update_timer)

    def _background_worker_wrapper(self, worker_func, args, kwargs, task_name):
        """Wraps the actual worker function to handle completion and errors."""
        # Initialize status and log messages with defaults
        status_message = "Task Failed"
        log_message = f"{task_name} failed with an unknown error"

        try:
            logger.info(f"Background task '{task_name}' executing.")

            # Initialize WebDriver if needed
            if not self.driver:
                self.driver = get_driver(
                    use_undetected=self.use_undetected_driver_var.get(),
                    headless=self.headless_mode_var.get(),
                    download_dir=self.download_dir_var.get()
                )
                logger.info("Created new WebDriver instance")
                kwargs['driver'] = self.driver  # Update driver in kwargs
            else:
                logger.info("Reusing existing WebDriver instance")
                kwargs['driver'] = self.driver  # Ensure driver is in kwargs

            # Execute worker function with combined args and kwargs
            worker_func(*args, **kwargs)
            
            logger.info(f"Background task '{task_name}' completed normally.")
            status_message = "Idle - Task Completed"
            log_message = f"{task_name} finished successfully."

        except Exception as e:
            logger.error(f"Exception in background task '{task_name}': {e}", exc_info=True)
            status_message = f"Error - {task_name} Failed"
            log_message = f"ERROR during {task_name}: {e}"
            # Schedule error dialog in main thread
            self.root.after(0, lambda e=e, task_name=task_name: 
                          gui_utils.show_message("Task Error", 
                                              f"An error occurred during {task_name}:\n\n{e}", 
                                              type="error", parent=self.root))
        finally:
            if self.root.winfo_exists():
                self.root.after(0, self._task_finished, status_message, log_message)

    def _task_finished(self, status_message, log_message):
        """Called via root.after() when a background task finishes or errors."""
        logger.debug(f"Task finished callback. Status: '{status_message}', Log: '{log_message}'")
        self.scraping_in_progress = False
        self.stop_timer_updates()
        self.update_status(status_message)
        self.update_log(log_message)
        self.set_controls_state(tk.NORMAL)
        self.progress_bar['value'] = 0
        self.root.lift()
        self.root.focus_force()

    def request_stop_scraping(self):
        """Shows emergency stop dialog with options for the current running process."""
        if not self.scraping_in_progress:
            self.update_log("Stop requested but no task is running.")
            return

        # Show the emergency stop dialog
        dialog = EmergencyStopDialog(self.root, self)
        result = dialog.show()

        if result == "kill":
            # Force kill the process
            self._kill_current_process()
        elif result == "pause":
            # Pause the process (for now, treat as stop)
            self._pause_current_process()
        elif result == "cancel":
            # Cancel - do nothing
            self.update_log("Emergency stop cancelled by user.")
        else:
            # Dialog was closed without selection
            self.update_log("Emergency stop dialog closed without action.")

    def _kill_current_process(self):
        """Force kill the current running process."""
        if self.background_thread and self.background_thread.is_alive():
            try:
                # Note: In Python, we can't forcefully terminate threads easily
                # This will set the stop event and log the kill request
                self.stop_event.set()
                self.update_status("Kill requested...")
                self.update_log("Kill request sent to background task - attempting forceful termination.")
                # For more forceful termination, we could use process-based approach
                # but for now, we'll rely on the stop event
                self.stop_button.config(state=tk.DISABLED)
                self.root.after(2000, lambda: self.stop_button.config(state=tk.NORMAL) if not self.scraping_in_progress else None)
            except Exception as e:
                self.update_log(f"Error during kill operation: {e}")
                logger.error(f"Kill operation error: {e}")
        else:
            self.update_log("Kill requested but no task is running.")

    def _pause_current_process(self):
        """Pause the current running process."""
        # For now, implement pause as a graceful stop
        # TODO: Implement actual pause functionality if needed
        if self.background_thread and self.background_thread.is_alive():
            self.stop_event.set()
            self.update_status("Pause requested...")
            self.update_log("Pause request sent to background task - stopping gracefully.")
            self.stop_button.config(state=tk.DISABLED)
            self.root.after(2000, lambda: self.stop_button.config(state=tk.NORMAL) if not self.scraping_in_progress else None)
        else:
            self.update_log("Pause requested but no task is running.")

    def set_controls_state(self, state):
        """Enable or disable main interaction controls based on state (tk.NORMAL or tk.DISABLED)."""
        logger.debug(f"Setting controls state to: {state}")
        for label, button in self.sidebar_buttons.items():
            # Keep Logs tab clickable during scraping
            if label == "Logs":
                continue
            is_pressed = 'pressed' in button.state()
            button.config(state=state)
            if state == tk.DISABLED and is_pressed:
                button.state(['pressed', 'disabled'])
        self.stop_button.config(state=tk.NORMAL if self.scraping_in_progress and state == tk.DISABLED else tk.DISABLED)
        for name, frame in self.section_frames.items():
            if frame.winfo_children():
                tab_instance = frame.winfo_children()[0]
                if hasattr(tab_instance, 'set_controls_state'):
                    try:
                        tab_instance.set_controls_state(state)
                    except Exception as e:
                        logger.warning(f"Could not set state for tab '{name}': {e}")
                else:
                    logger.debug(f"Tab '{name}' does not have a 'set_controls_state' method.")
            else:
                logger.debug(f"No children found in frame for tab '{name}'")
        logger.debug("Controls state updated.")

    # --- Settings and Configuration ---
    def get_current_url_config(self):
        """Retrieves the configuration dict for the currently selected URL name."""
        selected_name = self.selected_url_name_var.get()
        for config in self.base_urls_data:
            if config.get("Name") == selected_name:
                return config.copy()
        logger.warning(f"Selected URL name '{selected_name}' not found in data. Returning first available or fallback.")
        return self.base_urls_data[0].copy() if self.base_urls_data else FALLBACK_URL_CONFIG.copy()

    def browse_download_dir(self):
        """Opens a directory selection dialog and updates the download_dir_var."""
        logger.debug("Browse download directory triggered.")
        current_dir = self.download_dir_var.get()
        initial = current_dir if os.path.isdir(current_dir) else os.path.expanduser("~")
        directory = filedialog.askdirectory(parent=self.root, initialdir=initial, title="Select Download Folder")
        if (directory):
            norm_dir = os.path.normpath(directory)
            self.download_dir_var.set(norm_dir)
            self.update_log(f"Download folder selected: {norm_dir}")
            logger.info(f"Download directory set to: {norm_dir}")
        else:
            logger.debug("Directory selection cancelled.")

    def validate_download_dir(self, directory):
        """Checks if the download directory exists and is writable."""
        if not directory:
            gui_utils.show_message("Error", "Download directory is not set.", type="error", parent=self.root)
            return False
        if not os.path.isdir(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                self.update_log(f"Created download directory: {directory}")
                logger.info(f"Created download directory: {directory}")
                return True
            except OSError as e:
                gui_utils.show_message("Error", f"Could not create download directory:\n{directory}\n\nError: {e}", type="error", parent=self.root)
                logger.error(f"Failed to create download directory '{directory}': {e}")
                return False
        elif not os.access(directory, os.W_OK):
            gui_utils.show_message("Error", f"Download directory is not writable:\n{directory}", type="error", parent=self.root)
            logger.error(f"Download directory '{directory}' is not writable.")
            return False
        return True

    def _save_current_settings_and_show_message(self):
        """Gathers current settings from UI variables, saves them, and shows a confirmation message."""
        logger.info("Saving current settings...")
        self.settings["download_directory"] = self.download_dir_var.get()
        self.settings["dl_more_details"] = self.dl_more_details_var.get()
        self.settings["dl_zip"] = self.dl_zip_var.get()
        self.settings["dl_notice_pdfs"] = self.dl_notice_pdfs_var.get()
        self.settings["selected_url_name"] = self.selected_url_name_var.get()
        self.settings["deep_scrape_departments"] = self.deep_scrape_departments_var.get()
        self.settings["selected_theme"] = self.selected_theme_var.get()
        self.settings["use_undetected_driver"] = self.use_undetected_driver_var.get()
        self.settings["headless_mode"] = self.headless_mode_var.get()
        for key, var in self.timeout_vars.items():
            self.settings[key] = int(var.get())
        try:
            if self.root.winfo_exists():
                self.settings["window_geometry"] = self.root.geometry()
        except tk.TclError:
            logger.warning("Could not get window geometry, possibly already closed.")
        save_settings(self.settings, self.settings_filepath)
        self.update_log("Settings saved.")
        gui_utils.show_message("Settings Saved", "Current settings have been saved.", type="info", parent=self.root)

    def reset_to_defaults(self):
        """Resets UI settings to default values and saves."""
        logger.info("Resetting settings to defaults.")
        if not gui_utils.show_message("Confirm Reset", "Reset all settings to their default values?", type="askyesno", parent=self.root):
            self.update_log("Settings reset cancelled.")
            return
        self.download_dir_var.set(self.abs_default_download_dir)
        self.dl_more_details_var.set(DEFAULT_SETTINGS_STRUCTURE["dl_more_details"])
        self.dl_zip_var.set(DEFAULT_SETTINGS_STRUCTURE["dl_zip"])
        self.dl_notice_pdfs_var.set(DEFAULT_SETTINGS_STRUCTURE["dl_notice_pdfs"])
        self.deep_scrape_departments_var.set(DEFAULT_SETTINGS_STRUCTURE["deep_scrape_departments"])
        self.selected_theme_var.set(DEFAULT_SETTINGS_STRUCTURE["selected_theme"])
        self.use_undetected_driver_var.set(DEFAULT_SETTINGS_STRUCTURE["use_undetected_driver"])
        self.headless_mode_var.set(DEFAULT_SETTINGS_STRUCTURE["headless_mode"])
        for key in CONFIGURABLE_TIMEOUTS:
            self.timeout_vars[key].set(str(DEFAULT_SETTINGS_STRUCTURE[key]))
        default_url_name = self.base_urls_data[0]["Name"] if self.base_urls_data else FALLBACK_URL_CONFIG["Name"]
        self.selected_url_name_var.set(default_url_name)
        self._save_current_settings_and_show_message()
        gui_utils.show_message("Settings Reset", "Settings have been reset to defaults.", type="info", parent=self.root)

    # --- Application Closing ---
    def on_closing(self, force_quit=False):
        """Handles application close event."""
        logger.info("Close requested.")
        try:
            # Save settings before checking for running tasks
            self._save_current_settings_and_show_message()
        except Exception as e:
            logger.error(f"Failed to save settings on exit: {e}")

        if self.scraping_in_progress and not force_quit:
            if gui_utils.show_message("Confirm Exit", "A task is currently running. Are you sure you want to exit?", type="askyesno", parent=self.root):
                logger.warning("Exiting while task is running.")
                self.request_stop_scraping()
            else:
                logger.info("Exit cancelled by user.")
                return

        self.stop_event.set()
        # Quit WebDriver if it exists
        if self.driver:
            try:
                quit_driver(self.driver)
                self.driver = None
                logger.info("WebDriver closed successfully")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
        if self.root:
            try:
                self.root.destroy()
                logger.info("Tkinter root window destroyed.")
            except tk.TclError as e:
                logger.warning(f"Error destroying Tkinter root (might already be destroyed): {e}")
            except Exception as e:
                logger.error(f"Unexpected error destroying Tkinter root: {e}", exc_info=True)
        logger.info("--- Application Shutdown Sequence Complete ---")

    def log_message(self, message):
        """Log a message to the GUI log area."""
        if hasattr(self, 'update_log'):
            self.update_log(message)

    def update_timer(self, start_time):
        """Update the timer display."""
        if not start_time:
            self.timer_label.config(text="Elapsed: 00:00:00")
            return

        elapsed = datetime.now() - start_time
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.timer_label.config(text=f"Elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def reset_progress_and_timer(self):
        """Reset progress bars and timer for new operation"""
        # Reset progress for the "By Direct URL" tab if it exists and has reset_progress
        url_process_frame = self.section_frames.get("By Direct URL")
        if url_process_frame and url_process_frame.winfo_children():
            tab_instance = url_process_frame.winfo_children()[0]
            if hasattr(tab_instance, "reset_progress"):
                tab_instance.reset_progress()
        self.timer_label.config(text="00:00:00")
        self.processed_count = 0
        self.total_count = 0
        self.start_time = None
        self.processed_count = 0
        self.total_count = 0
        self.start_time = None

    def launch_cli_mode(self):
        """Launch CLI mode in a new console window with interactive prompt."""
        import subprocess
        import sys
        import os
        try:
            # Get the project directory (where main.py is located)
            project_dir = os.path.dirname(os.path.dirname(__file__))  # Go up from gui/ to project root

            # Use cmd.exe to open console in project directory with custom title
            cmd = [
                'cmd.exe', '/k',
                f'title "BlackForest CLI v{self.app_version}" && python main.py'
            ]

            # Set environment variable to indicate interactive CLI mode
            env = os.environ.copy()
            env['BLACKFOREST_CLI_MODE'] = 'interactive'

            # Launch in new console window on Windows, starting in project directory
            subprocess.Popen(cmd, cwd=project_dir, creationflags=subprocess.CREATE_NEW_CONSOLE, env=env)
            self.update_log("CLI mode launched in project directory with ASCII banner - type commands in the console window")
        except Exception as e:
            self.update_log(f"Failed to launch CLI: {e}")
            logger.error(f"CLI launch error: {e}")
