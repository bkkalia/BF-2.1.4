# gui/gui_utils.py v2.1.4
# Utility functions specifically for the GUI components

import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
import datetime
import logging
import threading
import time
import webbrowser
import os
import sys # For platform checks

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
            log_text_widget.insert(tk.END, formatted_message + "\n")
            log_text_widget.see(tk.END)
            log_text_widget.config(state=current_state)
    except Exception as e:
        if log_text_widget.winfo_exists():
             logger.warning(f"Error appending log message: {e}")

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

def update_progress(progress_bar, details_label, rem_label,
                   current, total, percent, details, est_rem, scraping_in_progress):
    """Thread-safe update for progress indicators."""
    if progress_bar and progress_bar.winfo_exists():
        try:
            progress_bar.after(0, _set_progress, progress_bar, details_label, rem_label,
                             current, total, details, scraping_in_progress)
        except Exception as e:
            if progress_bar.winfo_exists():
                logger.warning(f"Error scheduling progress update: {e}")

def _set_progress(progress_bar, details_label, rem_label,
                  current, total, details, scraping_in_progress):
    """Internal function to set progress, called via after()"""
    try:
        if not all(w.winfo_exists() for w in (progress_bar, details_label, rem_label)):
            return

        # Calculate percentage
        percentage = int((current / max(1, total)) * 100) if total else 0
        progress_bar['value'] = min(percentage, 100)
        
        # Update details label
        details_text = details if details else f"Processed: {current} / {total}"
        details_label.config(text=details_text)
        
        # Update remaining time label
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
    if type == "info":          messagebox.showinfo(title, message, parent=parent)
    elif type == "warning":     messagebox.showwarning(title, message, parent=parent)
    elif type == "error":       messagebox.showerror(title, message, parent=parent)
    elif type == "askyesno":    return messagebox.askyesno(title, message, parent=parent)
    elif type == "askokcancel": return messagebox.askokcancel(title, message, parent=parent)
    else:
        logger.warning(f"Unknown message type: {type}")
        messagebox.showinfo(title, message, parent=parent) # Default to info