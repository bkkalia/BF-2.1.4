# gui/tab_department.py v2.1.4
# Widgets and logic for the "Scrape by Department" tab

import tkinter as tk
from tkinter import ttk, Listbox, Scrollbar, StringVar, IntVar, END, EXTENDED
import threading
import logging
import os
import sys

# Add the project root to sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Absolute imports from project root
from scraper.logic import fetch_department_list_from_site, run_scraping_logic
from gui import gui_utils

logger = logging.getLogger(__name__)

class DepartmentTab(ttk.Frame):
    """Frame containing widgets and logic for scraping by department."""

    def __init__(self, parent, main_app_ref, **kwargs):
        super().__init__(parent, **kwargs)
        self.main_app = main_app_ref
        self.log_callback = self.main_app.update_log
        self.all_departments_data = []
        self.filtered_departments = []
        self.total_estimated_tenders = 0
        self.scrape_mode_var = IntVar(value=1)  

        # Use global search_var and selected_url_name_var from MainWindow
        self.search_var = self.main_app.get_or_create_global_search_var()
        # Do NOT trace_add here; handled by MainWindow._show_section
        self.selected_url_name_var = self.main_app.selected_url_name_var

        self._create_widgets()
        self._update_listbox()  # Initialize listbox state

    def _create_widgets(self):
        section = ttk.Labelframe(self, text="Scrape by Department", style="Section.TLabelframe")
        section.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # --- Top Controls --- (Removed Filter Departments and Select URL, now in global panel)
        top_controls_frame = ttk.Frame(section)
        top_controls_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 10))

        # Fetch Departments Button
        self.fetch_button = ttk.Button(
            top_controls_frame,
            text="Fetch Departments",
            command=self._start_fetch_departments_thread,
            width=18,
            style="Accent.TButton"
        )
        self.fetch_button.pack(side=tk.LEFT, padx=(0, 10))

        # Start Scraping Button
        self.start_scrape_button = ttk.Button(
            top_controls_frame,
            text="Start Scraping",
            command=self._start_scraping,
            width=18,
            state=tk.DISABLED  # Initially disabled
        )
        self.start_scrape_button.pack(side=tk.LEFT)

        # --- Radio Buttons for Scrape Mode ---
        radio_frame = ttk.Frame(section)
        radio_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 10))
        ttk.Radiobutton(radio_frame, text="Scrape All Departments", variable=self.scrape_mode_var, value=1).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(radio_frame, text="Scrape Selected Departments", variable=self.scrape_mode_var, value=2).pack(side=tk.LEFT, padx=10)

        # --- Listbox Frame ---
        listbox_frame = ttk.Frame(section)
        listbox_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=5, pady=(0, 5))
        listbox_frame.rowconfigure(0, weight=1)
        listbox_frame.columnconfigure(0, weight=1)

        self.dept_listbox = Listbox(
            listbox_frame,
            selectmode=EXTENDED,
            font=("Consolas", 10),  # Use monospace font for alignment
            borderwidth=1,
            relief="solid",
            height=15,
            width=50
        )
        self.dept_listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.dept_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.dept_listbox.config(yscrollcommand=scrollbar.set)

        # --- Download Folder Selection ---
        folder_frame = ttk.Frame(section)
        folder_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 10))
        ttk.Label(folder_frame, text="Download Folder:", font=self.main_app.label_font).pack(side=tk.LEFT, padx=(0, 5))
        self.folder_dropdown = ttk.Combobox(
            folder_frame,
            textvariable=self.main_app.download_dir_var,
            values=[config.get("Name", "Unknown") for config in self.main_app.base_urls_data],  # Populate from CSV
            state="readonly",
            width=40
        )
        self.folder_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Button(folder_frame, text="Browse", command=self.main_app.browse_download_dir, width=10).pack(side=tk.LEFT)

        # --- Bottom Info Label ---
        self.total_tenders_label = ttk.Label(section, text="Est. Total Tenders: 0", font=self.main_app.label_font)
        self.total_tenders_label.grid(row=4, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 10))

        # Configure grid weights for resizing
        section.columnconfigure(0, weight=1)
        section.rowconfigure(2, weight=1)

    def _filter_departments(self, *args):
        """Filters the department list based on the search term."""
        term = self.search_var.get().lower().strip()
        if not term:
            self.filtered_departments = self.all_departments_data
        else:
            self.filtered_departments = [
                dept for dept in self.all_departments_data
                if term in dept.get('name', '').lower()
            ]
        self._update_listbox()

    def _update_listbox(self):
        """Updates the listbox with the current filtered departments."""
        self.dept_listbox.delete(0, END)
        if not self.filtered_departments:
            self.dept_listbox.insert(END, "No departments available.")
        else:
            # Define column widths for alignment
            sr_no_width = 5
            name_width = 50
            count_width = 10

            # Add a header row for better readability
            header = f"{'Sr No':<{sr_no_width}} | {'Department Name':<{name_width}} | {'Tender Count':>{count_width}}"
            self.dept_listbox.insert(END, header)
            self.dept_listbox.insert(END, "-" * (sr_no_width + name_width + count_width + 6))  # Separator line

            for dept in self.filtered_departments:
                s_no = dept.get('s_no', 'N/A')
                name = dept.get('name', 'Unknown')
                count = dept.get('count_text', '?')

                # Format each row with proper alignment
                row = f"{s_no:<{sr_no_width}} | {name:<{name_width}} | {count:>{count_width}}"
                self.dept_listbox.insert(END, row)

    def _start_fetch_departments_thread(self):
        """Starts the background thread to fetch the department list."""
        logger.info("Fetch Departments button clicked.")
        if self.main_app.scraping_in_progress:
            gui_utils.show_message("Busy", "Another process is currently running.", type="warning", parent=self.main_app.root)
            return

        url_config = self.main_app.get_current_url_config()
        fetch_url = url_config.get('OrgListURL')
        if not fetch_url or not fetch_url.startswith(('http://', 'https://')):
            gui_utils.show_message("Invalid URL", f"No valid Organisation List URL configured for '{url_config.get('Name', 'Selected Site')}'.", type="error", parent=self.main_app.root)
            return

        self.log_callback(f"Fetching departments from: {fetch_url}")
        self.main_app.update_status(f"Fetching department list from '{url_config.get('Name')}'...")
        self.main_app.set_controls_state(tk.DISABLED)

        thread = threading.Thread(target=self._fetch_departments_worker, args=(fetch_url,), name="DeptFetchThread", daemon=True)
        thread.start()

    def _fetch_departments_worker(self, target_url):
        """Worker thread function to fetch the department list."""
        departments = None
        total_tenders = 0
        try:
            departments, total_tenders = fetch_department_list_from_site(target_url, self.log_callback)
        except Exception as e:
            logger.error(f"Error fetching departments: {e}", exc_info=True)
        finally:
            self.main_app.root.after(0, self._fetch_departments_finished, departments, total_tenders)

    def _fetch_departments_finished(self, departments, total_tenders):
        """Callback executed after fetching departments."""
        if departments:
            self.all_departments_data = departments
            self.filtered_departments = departments
            self.total_estimated_tenders = total_tenders
            self._update_listbox()
            self.total_tenders_label.config(text=f"Est. Total Tenders: {self.total_estimated_tenders}")
            self.start_scrape_button.config(state=tk.NORMAL)
            self.main_app.update_status("Idle - Department list loaded")
            self.log_callback(f"Fetched {len(departments)} departments. Estimated tenders: {total_tenders}")
        else:
            self.all_departments_data = []
            self.filtered_departments = []
            self.total_estimated_tenders = 0
            self._update_listbox()
            self.total_tenders_label.config(text="Est. Total Tenders: Error")
            self.main_app.update_status("Error - Failed to fetch departments")
            self.log_callback("Failed to fetch department list. Check URL/Log.")
            gui_utils.show_message("Fetch Error", "Failed to fetch department list. Check the log for details.", type="error", parent=self.main_app.root)

        self.main_app.set_controls_state(tk.NORMAL)

    def _is_valid_department(self, dept):
        """Check if a department is valid for scraping (not a header row)."""
        s_no = dept.get('s_no', '').strip().lower()
        name = dept.get('name', '').strip().lower()
        
        # Skip header-like rows
        if s_no in ['s.no', 'sr.no', 'serial', '#']:
            return False
        if name in ['organisation name', 'department name', 'organization', 'organization name']:
            return False
        
        # Skip rows without proper S.No
        if not s_no or not s_no.isdigit():
            return False
            
        return True

    def _get_all_valid_departments(self):
        """Get all valid departments for scraping, filtering out headers."""
        if not self.filtered_departments:
            return None, "No departments available to scrape. Please fetch departments first."
        
        valid_depts = []
        for dept in self.filtered_departments:
            if self._is_valid_department(dept):
                valid_depts.append(dept)
            else:
                self.log_callback(f"Skipping header-like department: {dept.get('name', 'Unknown')}")
        
        if not valid_depts:
            return None, "No valid departments found to scrape after filtering."
            
        logger.info(f"Starting scraping for ALL {len(valid_depts)} valid departments (filtered from {len(self.filtered_departments)} total).")
        return valid_depts, None

    def _get_selected_valid_departments(self):
        """Get selected valid departments for scraping."""
        selected_indices = self.dept_listbox.curselection()
        if not selected_indices:
            return None, "Please select at least one department."
        
        selected_depts = []
        for i in selected_indices:
            if i < 2:  # Skip header rows (first 2 rows are header and separator)
                continue
                
            dept = self.filtered_departments[i-2]
            if self._is_valid_department(dept):
                selected_depts.append(dept)
            else:
                self.log_callback(f"Skipping selected header-like department: {dept.get('name', 'Unknown')}")
        
        if not selected_depts:
            return None, "Please select valid department rows (not header rows)."
            
        logger.info(f"Starting scraping for {len(selected_depts)} selected valid departments.")
        return selected_depts, None

    def _start_scraping(self):
        """Start the scraping process for selected departments."""
        try:
            # Determine which departments to scrape based on mode
            scrape_mode = self.scrape_mode_var.get()
            
            if scrape_mode == 1:  # Scrape All Departments
                selected_depts, error_msg = self._get_all_valid_departments()
            else:  # Scrape Selected Departments
                selected_depts, error_msg = self._get_selected_valid_departments()
            
            if error_msg:
                gui_utils.show_message("Validation Error", error_msg, type="warning", parent=self.main_app.root)
                return
            
            # Get current URL config and download directory
            url_config = self.main_app.get_current_url_config()
            download_dir = self.main_app.download_dir_var.get()

            # Validate download directory before starting
            if not self.main_app.validate_download_dir(download_dir):
                return

            # Start background task
            self.main_app.start_background_task(
                run_scraping_logic,
                args=(selected_depts, url_config, download_dir),
                task_name="Department Scrape"
            )

        except Exception as e:
            logger.error(f"Error starting scraping: {e}", exc_info=True)
            gui_utils.show_message("Error", f"Failed to start scraping:\n\n{e}", type="error", parent=self.main_app.root)
