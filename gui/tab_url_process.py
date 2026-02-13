# gui/tab_url_process.py v2.2.1
# Widgets and logic for the "Process by Direct URL" tab

import tkinter as tk
from tkinter import ttk, scrolledtext, Frame, Label, Button
import logging
import os

# Absolute imports from project root
from scraper.logic import process_direct_urls
from gui import gui_utils # Absolute import

logger = logging.getLogger(__name__)

class UrlProcessTab(ttk.Frame):
    """Frame containing widgets and logic for processing by Direct URL."""

    def __init__(self, parent, main_app_ref, **kwargs):
        super().__init__(parent, **kwargs)
        self.main_app = main_app_ref
        self.log_callback = self.main_app.update_log
        self._create_widgets()

    def _create_widgets(self):
        section = ttk.Labelframe(self, text="Process by Direct URLs", style="Section.TLabelframe")
        section.grid(row=0, column=0, sticky='nsew', padx=20, pady=15)

        # Input label
        input_label = ttk.Label(section, text="Enter URLs (one per line):", font=self.main_app.label_font)
        input_label.grid(row=0, column=0, columnspan=2, sticky='w', padx=5, pady=(10, 2))

        # Create frame for text area and line numbers
        text_frame = ttk.Frame(section)
        text_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=5, pady=(0, 10))

        # Line numbers text widget
        self.line_numbers = tk.Text(
            text_frame,
            width=4,
            padx=3,
            takefocus=0,
            border=0,
            background='lightgray',
            state='disabled',
            wrap=tk.NONE,
            font=self.main_app.log_font
        )
        self.line_numbers.grid(row=0, column=0, sticky='ns')

        # URL input area
        self.url_text = scrolledtext.ScrolledText(
            text_frame,
            height=20,
            width=40,
            wrap=tk.WORD,
            font=self.main_app.log_font,
            borderwidth=1,
            relief="solid"
        )
        self.url_text.grid(row=0, column=1, sticky='nsew')

        # Configure text frame grid
        text_frame.grid_columnconfigure(1, weight=1)
        text_frame.grid_rowconfigure(0, weight=1)

        # Button frame
        button_frame = ttk.Frame(section)
        button_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=5, pady=(0, 5))

        # Start button
        self.start_button = ttk.Button(
            button_frame,
            text="Start Processing URLs",
            command=self.start_process_urls,
            style="Accent.TButton",
            width=22
        )
        self.start_button.grid(row=0, column=0, padx=(0, 10))

        # Clear button
        self.clear_button = ttk.Button(
            button_frame,
            text="Clear Input",
            command=lambda: self.url_text.delete("1.0", tk.END),
            width=12
        )
        self.clear_button.grid(row=0, column=1)

        # Configure grid weights
        section.grid_columnconfigure(0, weight=1)
        section.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Bind events for line numbers
        self.url_text.bind('<KeyPress>', self._on_text_change)
        self.url_text.bind('<KeyRelease>', self._on_text_change)
        self.url_text.bind('<MouseWheel>', self._on_text_scroll)

        # Initial line numbers
        self._update_line_numbers()

    def _enable_text_scrolling(self, widget):
        def _on_mousewheel(event):
            if event.delta:
                widget.yview_scroll(int(-1*(event.delta/120)), "units")
            elif event.num == 4:
                widget.yview_scroll(-1, "units")
            elif event.num == 5:
                widget.yview_scroll(1, "units")
            return "break"
        widget.bind("<MouseWheel>", _on_mousewheel)
        widget.bind("<Button-4>", _on_mousewheel)
        widget.bind("<Button-5>", _on_mousewheel)

    def _on_text_change(self, event=None):
        self._update_line_numbers()

    def _on_text_scroll(self, event=None):
        self.line_numbers.yview_moveto(self.url_text.yview()[0])
        return "break"

    def _update_line_numbers(self):
        if not hasattr(self, 'line_numbers'):
            return
        final_index = self.url_text.index("end-1c")
        num_of_lines = int(final_index.split('.')[0])
        line_numbers_text = '\n'.join(str(i).rjust(3) for i in range(1, num_of_lines + 1))
        self.line_numbers.configure(state='normal')
        self.line_numbers.delete(1.0, tk.END)
        self.line_numbers.insert(1.0, line_numbers_text)
        self.line_numbers.configure(state='disabled')
        self.line_numbers.yview_moveto(self.url_text.yview()[0])

    def get_direct_urls_from_input(self):
        """Extracts and validates URLs from the text area."""
        urls_text = self.url_text.get("1.0", tk.END).strip()
        if not urls_text: return []
        direct_urls = []
        for line in urls_text.splitlines():
            url = line.strip()
            if url.startswith(('http://', 'https://')): direct_urls.append(url)
            elif url: logger.warning(f"Skipping invalid URL input line: {url[:100]}...")
        if not direct_urls: logger.warning("No valid http/https URLs found after parsing input.")
        else: logger.info(f"Parsed {len(direct_urls)} potential Direct URLs from input.")
        return direct_urls

    def start_process_urls(self):
        """Starts the background thread for processing direct URLs."""
        logger.info("Start Processing URLs button clicked.")
        if self.main_app.scraping_in_progress:
            gui_utils.show_message("Busy", "Another process is currently running.", type="warning", parent=self.main_app.root)
            return

        download_dir = self.main_app.download_dir_var.get()
        if not self.main_app.validate_download_dir(download_dir): return

        direct_urls = self.get_direct_urls_from_input()
        if not direct_urls:
            gui_utils.show_message("Input Missing", "Please enter one or more valid Tender Detail URLs (starting with http:// or https://).", type="warning", parent=self.main_app.root)
            return

        dl_more = self.main_app.dl_more_details_var.get()
        dl_zip = self.main_app.dl_zip_var.get()
        dl_notice = self.main_app.dl_notice_pdfs_var.get()
        url_config = self.main_app.get_current_url_config()

        confirm_msg = (f"Start processing {len(direct_urls)} Direct URL(s).\n"
                       f"(Context site: '{url_config['Name']}')\n\n"
                       f"Files saved in subfolders within:\n{download_dir}\n\n"
                       f"Download Options:\n"
                       f" - More Details PDF: {'Yes' if dl_more else 'No'}\n"
                       f" - ZIP File: {'Yes' if dl_zip else 'No'}\n"
                       f" - TenderNotice PDFs: {'Yes' if dl_notice else 'No'}\n\n"
                       f"NOTE: Requires manual CAPTCHA solving in the console if prompted.\n\nProceed?")
        if not gui_utils.show_message("Confirm Direct URL Processing", confirm_msg, type="askyesno", parent=self.main_app.root):
            self.log_callback("Direct URL processing cancelled by user.")
            return

        self.log_callback(f"Starting Direct URL processing for {len(direct_urls)} URL(s). Base download folder: {download_dir}")
        self.main_app.total_estimated_tenders_for_run = len(direct_urls)
        self.main_app.reset_progress_and_timer()
        self.main_app.update_status("Starting Direct URL Processing...")

        # Fix: Pass only the required arguments
        self.main_app.start_background_task(
            process_direct_urls,
            args=(direct_urls, download_dir),
            kwargs={
                'dl_more_details': dl_more,
                'dl_zip': dl_zip,
                'dl_notice_pdfs': dl_notice
            },
            task_name="Direct URL Processing"
        )

    def reset_progress(self):
        """Reset progress indicators."""
        if hasattr(self.main_app, 'progress_bar'):
            self.main_app.progress_bar['value'] = 0
        if hasattr(self.main_app, 'progress_details_label'):
            self.main_app.progress_details_label.config(text="Processed: 0 / ~0")
        if hasattr(self.main_app, 'est_rem_label'):
            self.main_app.est_rem_label.config(text="Est. Rem: --:--:--")