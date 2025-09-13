import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger(__name__)

class GlobalPanel(ttk.Frame):
    def __init__(self, parent, main_app_ref):
        super().__init__(parent)
        self.main_app = main_app_ref
        self._create_widgets()

    def _create_widgets(self):
        # Portal Selection
        url_frame = ttk.LabelFrame(self, text="Portal Selection", style='Section.TLabelframe')
        url_frame.pack(fill=tk.X, padx=5, pady=(5, 0))

        # URL dropdown
        urls = [url["Name"] for url in self.main_app.base_urls_data]
        self.url_dropdown = ttk.Combobox(
            url_frame, 
            values=urls,
            state="readonly",
            textvariable=self.main_app.selected_url_name_var,
            width=25
        )
        self.url_dropdown.pack(fill=tk.X, padx=5, pady=5)

        # Global Filters
        filter_frame = ttk.LabelFrame(self, text="Global Filters", style='Section.TLabelframe')
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        # Deep scrape option
        ttk.Checkbutton(
            filter_frame,
            text="Deep Scrape",
            variable=self.main_app.deep_scrape_departments_var
        ).pack(anchor=tk.W, padx=5, pady=2)

        # Download options
        ttk.Checkbutton(
            filter_frame,
            text="Download Details",
            variable=self.main_app.dl_more_details_var
        ).pack(anchor=tk.W, padx=5, pady=2)

        ttk.Checkbutton(
            filter_frame,
            text="Download ZIP",
            variable=self.main_app.dl_zip_var
        ).pack(anchor=tk.W, padx=5, pady=2)

        ttk.Checkbutton(
            filter_frame,
            text="Download PDFs",
            variable=self.main_app.dl_notice_pdfs_var
        ).pack(anchor=tk.W, padx=5, pady=2)
