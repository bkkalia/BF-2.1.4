# gui/gui_utils.py v2.1.4
# Utility functions specifically for the GUI components

import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
from tkinter import font as tkFont
import datetime
import logging
import threading
import time
import webbrowser
import os
import sys # For platform checks
import re

logger = logging.getLogger(__name__)

# --- UI Update Functions (Thread-safe using .after()) ---

def update_status(status_label_widget, message):
    """Thread-safe update for the status label."""
    if status_label_widget and status_label_widget.winfo_exists():
        try:
            status_label_widget.after(0, lambda: status_label_widget.config(text=f"Status: {message}"))
        except Exception as e:
            if status_label_widget.winfo_exists():
                 logger.debug(f"Minor error updating status label (likely during shutdown): {e}")

def update_log(log_text_widget, message):
    """Thread-safe update for the log ScrolledText widget."""
    if log_text_widget and log_text_widget.winfo_exists():
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        thread_name = threading.current_thread().name
        formatted_message = f"[{timestamp}][{thread_name}] {str(message)}"
        try:
            log_text_widget.after(0, _append_log_message, log_text_widget, formatted_message)
        except Exception as e:
            if log_text_widget.winfo_exists():
                logger.warning(f"Error scheduling log update: {e}")

def _append_log_message(log_text_widget, formatted_message):
    """Internal function to append message, called by update_log via .after()"""
    try:
        if log_text_widget.winfo_exists():
            current_state = log_text_widget['state']
            log_text_widget.config(state=tk.NORMAL)
            _insert_styled_log_line(log_text_widget, formatted_message)
            log_text_widget.see(tk.END)
            log_text_widget.config(state=current_state)
    except Exception as e:
        if log_text_widget.winfo_exists():
             logger.warning(f"Error appending log message: {e}")

def _ensure_log_style_tags(log_text_widget):
    if getattr(log_text_widget, "_bf_log_tags_ready", False):
        return

    base_font_name = log_text_widget.cget("font")
    try:
        base_font = tkFont.nametofont(base_font_name)
        portal_font = tkFont.Font(
            family=base_font.actual("family"),
            size=base_font.actual("size"),
            weight="bold"
        )
        level_font = tkFont.Font(
            family=base_font.actual("family"),
            size=base_font.actual("size"),
            weight="bold"
        )
    except Exception:
        portal_font = ("Consolas", 10, "bold")
        level_font = ("Consolas", 10, "bold")

    log_text_widget._bf_portal_font = portal_font
    log_text_widget._bf_level_font = level_font

    log_text_widget.tag_configure("portal_name", foreground="#4169E1", font=portal_font)
    log_text_widget.tag_configure("department_name", foreground="#C2185B", font=portal_font)
    log_text_widget.tag_configure("level_critical", foreground="#8E24AA", font=level_font)
    log_text_widget.tag_configure("level_error", foreground="#C62828", font=level_font)
    log_text_widget.tag_configure("level_warning", foreground="#EF6C00", font=level_font)
    log_text_widget.tag_configure("level_info", foreground="#2E7D32", font=level_font)
    log_text_widget.tag_configure("level_debug", foreground="#546E7A", font=level_font)
    log_text_widget.tag_configure("number_token", foreground="#8B0000", font=level_font)

    log_text_widget.tag_configure("icon_success", foreground="#2E7D32")
    log_text_widget.tag_configure("icon_warn", foreground="#EF6C00")
    log_text_widget.tag_configure("icon_error", foreground="#C62828")
    log_text_widget.tag_configure("icon_info", foreground="#1565C0")

    log_text_widget._bf_log_tags_ready = True

def _apply_tag_by_span(log_text_widget, line_start_index, match_obj, tag_name, group_index=0):
    try:
        start_pos = match_obj.start(group_index)
        end_pos = match_obj.end(group_index)
        if end_pos <= start_pos:
            return
        log_text_widget.tag_add(
            tag_name,
            f"{line_start_index}+{start_pos}c",
            f"{line_start_index}+{end_pos}c"
        )
    except Exception:
        return

def _insert_styled_log_line(log_text_widget, formatted_message):
    _ensure_log_style_tags(log_text_widget)

    text = str(formatted_message)
    line_start = log_text_widget.index(tk.END + "-1c")
    log_text_widget.insert(tk.END, text + "\n")

    main_portal = re.search(r"^\[[^\]]+\]\[[^\]]+\]\s(\[[^\]]+\])", text)
    if main_portal:
        _apply_tag_by_span(log_text_widget, line_start, main_portal, "portal_name", group_index=1)
    else:
        batch_portal = re.search(r"^\[[^\]]+\](\[[^\]]+\])", text)
        if batch_portal:
            _apply_tag_by_span(log_text_widget, line_start, batch_portal, "portal_name", group_index=1)

    for level_match in re.finditer(r"\b(CRITICAL|ERROR|WARNING|INFO|DEBUG)\b", text, flags=re.IGNORECASE):
        level_token = level_match.group(1).upper()
        tag_name = {
            "CRITICAL": "level_critical",
            "ERROR": "level_error",
            "WARNING": "level_warning",
            "INFO": "level_info",
            "DEBUG": "level_debug"
        }.get(level_token)
        if tag_name:
            _apply_tag_by_span(log_text_widget, line_start, level_match, tag_name)

    department_patterns = [
        r"processing department\s+\d+\s*/\s*\d+\s*:\s*(.+)",
        r"processing department\s+(.+?)\.\.\.",
        r"found\s+\d+\s+tenders?\s+in department\s+(.+)",
        r"no tenders found/extracted from department\s+(.+)",
        r"resume:\s+skipping already-processed department:\s+(.+)",
    ]
    for pattern in department_patterns:
        for dept_match in re.finditer(pattern, text, flags=re.IGNORECASE):
            _apply_tag_by_span(log_text_widget, line_start, dept_match, "department_name", group_index=1)

    icon_tag_map = {
        "✅": "icon_success",
        "✓": "icon_success",
        "❌": "icon_error",
        "⚠": "icon_warn",
        "🚀": "icon_info",
        "🎯": "icon_info",
        "ℹ": "icon_info",
    }
    for icon, tag_name in icon_tag_map.items():
        for icon_match in re.finditer(re.escape(icon), text):
            _apply_tag_by_span(log_text_widget, line_start, icon_match, tag_name)

    for number_match in re.finditer(r"\d+(?:[\.,:/-]\d+)*", text):
        _apply_tag_by_span(log_text_widget, line_start, number_match, "number_token")

def append_styled_log_line(log_text_widget, formatted_message):
    if not (log_text_widget and log_text_widget.winfo_exists()):
        return
    try:
        current_state = log_text_widget['state']
        if current_state != tk.NORMAL:
            log_text_widget.config(state=tk.NORMAL)
        _insert_styled_log_line(log_text_widget, formatted_message)
        log_text_widget.see(tk.END)
        if current_state != tk.NORMAL:
            log_text_widget.config(state=current_state)
    except Exception as e:
        if log_text_widget.winfo_exists():
            logger.warning(f"Error appending styled log line: {e}")

def clear_log(log_text_widget, log_callback):
    """Clears the log ScrolledText widget."""
    logger.info("Clear log button clicked.")
    try:
        if log_text_widget and log_text_widget.winfo_exists():
            log_text_widget.config(state=tk.NORMAL)
            log_text_widget.delete('1.0', tk.END)
            log_text_widget.config(state=tk.DISABLED)
            if log_callback:
                log_callback("Log cleared by user.")
    except Exception as e:
        logger.warning(f"Error clearing log: {e}")

def update_dept_progress(dept_progress_bar, dept_progress_label, current, total):
    """Thread-safe update for department progress indicators."""
    if dept_progress_bar and dept_progress_bar.winfo_exists():
        try:
            dept_progress_bar.after(0, _set_dept_progress, dept_progress_bar, dept_progress_label, current, total)
        except Exception as e:
            if dept_progress_bar.winfo_exists():
                logger.warning(f"Error scheduling dept progress update: {e}")

def _set_dept_progress(dept_progress_bar, dept_progress_label, current, total):
    """Internal function to set department progress, called via after()"""
    try:
        if not dept_progress_bar.winfo_exists() or not dept_progress_label.winfo_exists():
            return

        # Calculate percentage
        percentage = int((current / max(1, total)) * 100) if total else 0
        dept_progress_bar['value'] = min(percentage, 100)
        
        # Update label
        dept_progress_label.config(text=f"{current}/{total} ({percentage}%)")

    except Exception as e:
        if dept_progress_bar.winfo_exists():
            logger.warning(f"Error setting dept progress: {e}")

def update_progress(progress_bar, details_label, rem_label,
                   current, total, percent, details, est_rem, scraping_in_progress, *extra_args):
    """Thread-safe update for progress indicators with enhanced details."""
    if progress_bar and progress_bar.winfo_exists():
        try:
            # Extract additional info if provided
            dept_name = extra_args[0] if len(extra_args) > 0 else None
            dept_tender_count = extra_args[1] if len(extra_args) > 1 else None
            total_tenders = extra_args[2] if len(extra_args) > 2 else None
            pending_depts = extra_args[3] if len(extra_args) > 3 else None
            
            progress_bar.after(0, _set_progress, progress_bar, details_label, rem_label,
                             current, total, details, scraping_in_progress, dept_name, dept_tender_count, total_tenders, pending_depts)
        except Exception as e:
            if progress_bar.winfo_exists():
                logger.warning(f"Error scheduling progress update: {e}")

def _set_progress(progress_bar, details_label, rem_label,
                  current, total, details, scraping_in_progress, dept_name=None, dept_tender_count=None, total_tenders=None, pending_depts=None):
    """Internal function to set progress with enhanced details, called via after()"""
    try:
        if not all(w.winfo_exists() for w in (progress_bar, details_label, rem_label)):
            return

        # Calculate percentage
        percentage = int((current / max(1, total)) * 100) if total else 0
        progress_bar['value'] = min(percentage, 100)
        
        # Build enhanced details text
        if details:
            details_text = details
        elif dept_name:
            # Enhanced format with department name and counts
            dept_display = dept_name[:40] + "..." if len(dept_name) > 40 else dept_name
            details_text = f"Dept {current}/{total}: {dept_display}"
            if total_tenders is not None:
                details_text += f" | Scraped Tenders: {total_tenders}"
            if pending_depts is not None:
                details_text += f" | Pending Depts: {pending_depts}"
            if dept_tender_count is not None:
                details_text += f" | This Dept: {dept_tender_count}"
        else:
            details_text = f"Processed: {current} / {total}"
        
        details_label.config(text=details_text)
        
        # Simple remaining time estimate (can be enhanced with actual timing data)
        if scraping_in_progress and current > 0 and total > current:
            rem_label.config(text="Est. Rem: Calculating...")
        else:
            rem_label.config(text="Est. Rem: --:--:--")

    except Exception as e:
        if progress_bar.winfo_exists():
            logger.warning(f"Error setting progress: {e}")

# --- Timer Functions ---

def start_timer_updates(timer_label, start_time_dt, main_window_ref):
    """Initiates the timer update loop. Needs main_window_ref to store timer_id."""
    if timer_label and timer_label.winfo_exists() and main_window_ref:
        try:
            timer_label.after(0, _init_timer, timer_label, start_time_dt, main_window_ref)
        except Exception as e:
            if timer_label.winfo_exists():
                logger.warning(f"Error scheduling timer init: {e}")

def _init_timer(timer_label, start_time_dt, main_window_ref):
    """Internal: Sets start time and begins the update loop."""
    main_window_ref.start_time = start_time_dt
    try:
        if timer_label.winfo_exists():
            timer_label.config(text="Elapsed: 00:00:00")
    except Exception as e:
        if timer_label.winfo_exists(): logger.warning(f"Error resetting timer label: {e}")

    stop_timer_updates(main_window_ref)
    _update_timer_label(timer_label, main_window_ref)

def stop_timer_updates(main_window_ref):
    """Stops the timer update loop."""
    if hasattr(main_window_ref, 'timer_id') and main_window_ref.timer_id:
        try:
            if main_window_ref.root and main_window_ref.root.winfo_exists():
                main_window_ref.root.after_cancel(main_window_ref.timer_id)
        except Exception as e: logger.warning(f"Error cancelling timer: {e}")
        main_window_ref.timer_id = None

def _update_timer_label(timer_label, main_window_ref):
    """Internal: Recursively updates the timer label every second."""
    if not (main_window_ref.scraping_in_progress and main_window_ref.start_time and
            main_window_ref.root and main_window_ref.root.winfo_exists() and
            timer_label and timer_label.winfo_exists()):
        main_window_ref.timer_id = None
        return

    try:
        elapsed = datetime.datetime.now() - main_window_ref.start_time
        elapsed_str = str(elapsed).split('.')[0]
        timer_label.config(text=f"Elapsed: {elapsed_str}")
        main_window_ref.timer_id = timer_label.after(1000, _update_timer_label, timer_label, main_window_ref)
    except Exception as e:
        logger.warning(f"Error updating timer label: {e}")
        main_window_ref.timer_id = None

# --- Dialog and File/Folder Operations ---

def browse_directory(parent_widget, initial_dir_var, title="Select Folder"):
    """Opens a directory selection dialog and updates the initial_dir_var."""
    logger.debug("Browse directory triggered.")
    current_dir = initial_dir_var.get()
    initial = current_dir if os.path.isdir(current_dir) else os.path.expanduser("~")
    directory = filedialog.askdirectory(parent=parent_widget, initialdir=initial, title=title)
    if directory:
        norm_dir = os.path.normpath(directory)
        initial_dir_var.set(norm_dir)
        logger.info(f"Directory selected: {norm_dir}")
        return norm_dir
    logger.debug("Directory selection cancelled.")
    return None

def open_folder(folder_path, log_callback):
    """Opens the specified folder in the default file explorer."""
    logger.info(f"Attempting to open folder: {folder_path}")
    if not folder_path:
        show_message("No Folder", "No folder path specified.", type="warning")
        return
    norm_path = os.path.normpath(folder_path)
    if os.path.isdir(norm_path):
        try:
            abs_path = os.path.realpath(norm_path) # Get absolute path for reliability
            if os.name == 'nt':       os.startfile(abs_path)
            elif sys.platform == 'darwin': webbrowser.open(f"file://{abs_path}")
            else:                          webbrowser.open(f"file://{abs_path}", new=2) # Try forcing new tab/window
            if log_callback: log_callback(f"Opened folder: {norm_path}")
        except Exception as e:
            logger.error(f"Could not open folder '{norm_path}': {e}", exc_info=True)
            if log_callback: log_callback(f"Error opening folder '{norm_path}': {e}")
            show_message("Error Opening Folder", f"Could not open folder:\n{norm_path}\n\nError: {e}", type="error")
    else:
        logger.warning(f"Cannot open folder: '{norm_path}' is not a valid directory.")
        if log_callback: log_callback(f"Cannot open folder: '{norm_path}' not valid.")
        show_message("Invalid Path", f"Folder does not exist or is not a directory:\n{norm_path}", type="warning")

def show_message(title, message, type="info", parent=None):
    """Wrapper for messagebox functions."""
    kwargs = {}
    if parent is not None:
        kwargs['parent'] = parent
    if type == "info":
        messagebox.showinfo(title, message, **kwargs)
    elif type == "warning":
        messagebox.showwarning(title, message, **kwargs)
    elif type == "error":
        messagebox.showerror(title, message, **kwargs)
    elif type == "askyesno":
        return messagebox.askyesno(title, message, **kwargs)
    elif type == "askokcancel":
        return messagebox.askokcancel(title, message, **kwargs)
    else:
        logger.warning(f"Unknown message type: {type}")
        messagebox.showinfo(title, message, **kwargs) # Default to info

class EmergencyStopDialog:
    """Dialog for emergency stop options with user interaction."""

    def __init__(self, parent, main_window):
        self.parent = parent
        self.main_window = main_window
        self.result = None
        self.dialog = None

    def show(self):
        """Show the emergency stop dialog and return user choice."""
        # Create dialog in main thread
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Emergency Stop Options")
        self.dialog.resizable(False, False)
        self.dialog.grab_set()  # Make modal

        # Keep on top
        try:
            self.dialog.attributes("-topmost", True)
        except Exception:
            pass

        # Center the dialog and add padding
        width, height = 400, 180
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (height // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")

        # Outer frame with padding
        outer = tk.Frame(self.dialog, padx=14, pady=10)
        outer.pack(fill=tk.BOTH, expand=True)

        # Dialog content
        tk.Label(
            outer,
            text="Emergency Stop",
            font=("Arial", 14, "bold")
        ).pack(pady=(2, 6))

        tk.Label(
            outer,
            text="Choose an action for the current running process:",
            justify=tk.CENTER
        ).pack(pady=(6, 8))

        # Buttons frame
        button_frame = tk.Frame(outer)
        button_frame.pack(pady=6)

        tk.Button(
            button_frame,
            text="Kill Process",
            command=lambda: self._set_result("kill"),
            bg="red",
            fg="white",
            width=12
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            button_frame,
            text="Pause Process",
            command=lambda: self._set_result("pause"),
            bg="orange",
            fg="white",
            width=12
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            button_frame,
            text="Cancel",
            command=lambda: self._set_result("cancel"),
            bg="gray",
            fg="white",
            width=12
        ).pack(side=tk.LEFT, padx=4)

        # Handle window close (same as cancel)
        self.dialog.protocol("WM_DELETE_WINDOW", lambda: self._set_result("cancel"))

        # Ensure focus
        local_dialog = self.dialog
        try:
            local_dialog.lift()
            local_dialog.focus_force()
            local_dialog.after(50, lambda: local_dialog.focus_set())
        except Exception:
            pass

        # Wait for user response
        self.dialog.wait_window()
        return self.result

    def _set_result(self, result):
        """Set the result and close dialog."""
        self.result = result
        if self.dialog:
            try:
                self.dialog.destroy()
            except Exception:
                pass
