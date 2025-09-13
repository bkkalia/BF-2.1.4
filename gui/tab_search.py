import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
import threading
import logging
import re
import warnings

# Suppress pandas warnings about date parsing
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')

logger = logging.getLogger(__name__)

class SearchTab(ttk.Frame):
    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.main_window = main_window
        self.df = None
        self.filtered_df = None
        self.original_df = None  # Store original unfiltered data
        self.folder_paths = []
        self.current_search_terms = []  # Store current search terms for highlighting
        self.persistent_folders_file = os.path.join(
            os.path.dirname(main_window.settings_filepath), 
            "search_folders.json"
        )
        
        # Load persistent folder paths
        self.load_persistent_folders()
        
        self.create_widgets()
        
        # Auto-populate data if folders exist
        if self.folder_paths:
            self.main_window.root.after(100, self.load_and_display_data)

    def load_persistent_folders(self):
        """Load previously saved folder paths."""
        try:
            if os.path.exists(self.persistent_folders_file):
                with open(self.persistent_folders_file, 'r', encoding='utf-8') as f:
                    self.folder_paths = json.load(f)
                logger.info(f"Loaded {len(self.folder_paths)} persistent folders")
        except Exception as e:
            logger.warning(f"Could not load persistent folders: {e}")
            self.folder_paths = []

    def save_persistent_folders(self):
        """Save current folder paths for future sessions."""
        try:
            os.makedirs(os.path.dirname(self.persistent_folders_file), exist_ok=True)
            with open(self.persistent_folders_file, 'w', encoding='utf-8') as f:
                json.dump(self.folder_paths, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(self.folder_paths)} persistent folders")
        except Exception as e:
            logger.warning(f"Could not save persistent folders: {e}")

    def create_widgets(self):
        # Stats Dashboard at the top
        self.create_stats_dashboard()
        
        # Main content area: Folders and Search sections
        content_row = ttk.Frame(self)
        content_row.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Folders Section
        folders_frame = ttk.LabelFrame(content_row, text="📁 Data Folders", padding=8)
        folders_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Folders controls in one row
        folders_controls = ttk.Frame(folders_frame)
        folders_controls.pack(fill=tk.X)
        
        # Left side: buttons
        folders_btn_frame = ttk.Frame(folders_controls)
        folders_btn_frame.pack(side=tk.LEFT)
        
        button_font = ("Segoe UI", 9, "bold")
        ttk.Button(
            folders_btn_frame, text="Add Folder", 
            command=self.add_folder, width=12, 
            style="Large.TButton"
        ).pack(side=tk.LEFT, padx=(0, 3))
        
        ttk.Button(
            folders_btn_frame, text="Remove", 
            command=self.remove_folder, width=10,
            style="Large.TButton"
        ).pack(side=tk.LEFT, padx=(0, 3))
        
        ttk.Button(
            folders_btn_frame, text="Clear All", 
            command=self.clear_folders, width=10,
            style="Large.TButton"
        ).pack(side=tk.LEFT)
        
        # Configure button style
        style = ttk.Style()
        style.configure("Large.TButton", font=button_font)
        
        # Right side: folder list (compact)
        folder_list_frame = ttk.Frame(folders_controls)
        folder_list_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
        
        self.folder_listbox = tk.Listbox(
            folder_list_frame, height=2,  # Very compact
            selectmode=tk.SINGLE,
            font=("Segoe UI", 9)
        )
        self.folder_listbox.pack(fill=tk.BOTH, expand=True)
        
        # Populate existing folders
        self.update_folder_list()
        
        # Search & Filter Section
        search_frame = ttk.LabelFrame(content_row, text="🔍 Search & Filter", padding=10)
        search_frame.pack(fill=tk.X, pady=(5, 0))
        
        # First row: Department Filter and Global Search
        filter_row1 = ttk.Frame(search_frame)
        filter_row1.pack(fill=tk.X, pady=(0, 8))
        
        # Department Filter (left side)
        dept_frame = ttk.Frame(filter_row1)
        dept_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(dept_frame, text="Department:", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        
        self.dept_filter_var = tk.StringVar()
        self.dept_filter_var.trace_add("write", self.on_filter_change)
        
        dept_entry = ttk.Entry(
            dept_frame, textvariable=self.dept_filter_var, 
            width=25, font=("Segoe UI", 10)
        )
        dept_entry.pack(side=tk.LEFT, padx=(0, 15))
        
        # Global Search (center)
        search_frame_inner = ttk.Frame(filter_row1)
        search_frame_inner.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(search_frame_inner, text="Global Search:", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_filter_change)
        
        search_entry = ttk.Entry(
            search_frame_inner, textvariable=self.search_var, 
            width=30, font=("Segoe UI", 10)  # Bigger search box
        )
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 15))
        
        # Action buttons (right side)
        actions_frame = ttk.Frame(filter_row1)
        actions_frame.pack(side=tk.RIGHT)
        
        reset_btn = tk.Button(
            actions_frame, text="🔄 Reset", 
            command=self.reset_all_filters,
            bg="#E74C3C", fg="white", font=("Segoe UI", 9, "bold"),
            relief=tk.RAISED, bd=1, padx=8, pady=2,
            cursor="hand2"
        )
        reset_btn.pack(side=tk.RIGHT, padx=(3, 0))
        
        ttk.Button(
            actions_frame, text="Export", 
            command=self.export_filtered_data, width=8,
            style="Large.TButton"
        ).pack(side=tk.RIGHT, padx=(0, 3))
        
        # Second row: Date Filters
        filter_row2 = ttk.Frame(search_frame)
        filter_row2.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(filter_row2, text="Closing Date Filters:", 
                 font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        
        # Date filter buttons in same row
        filter_buttons = [
            ("Today", "today", "#E74C3C"),
            ("Tomorrow", "tomorrow", "#F39C12"),
            ("3 Days", "3days", "#3498DB"),
            ("7 Days", "7days", "#2ECC71"),
            ("15 Days", "15days", "#9B59B6"),
            ("Month", "month", "#1ABC9C"),
        ]
        
        self.filter_buttons = {}
        for text, filter_type, color in filter_buttons:
            btn = tk.Button(
                filter_row2, text=text, 
                command=lambda ft=filter_type: self.apply_date_filter(ft),
                bg=color, fg="white", font=("Segoe UI", 8, "bold"),
                relief=tk.RAISED, bd=1, padx=6, pady=2,
                cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.filter_buttons[filter_type] = btn
        
        # Data Table
        self.create_data_table()

    def create_stats_dashboard(self):
        """Create a redesigned stats dashboard with large cards in one row."""
        dashboard_frame = ttk.LabelFrame(self, text="📊 Search Dashboard", padding=10)
        dashboard_frame.pack(fill=tk.X, pady=(0, 8))
        
        # Main stats row with large cards
        stats_row = ttk.Frame(dashboard_frame)
        stats_row.pack(fill=tk.X, pady=(0, 8))
        
        self.stats_dashboard = ttk.Frame(stats_row)
        self.stats_dashboard.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # DateTime on the right
        self.datetime_label = tk.Label(
            stats_row, text="", font=("Segoe UI", 10, "bold"),
            bg="#2C3E50", fg="white", padx=12, pady=6, relief=tk.RAISED, bd=1
        )
        self.datetime_label.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Active filters section
        self.active_filters_frame = ttk.Frame(dashboard_frame)
        self.active_filters_frame.pack(fill=tk.X, pady=(5, 0))
        
        # Start datetime updates
        self.update_datetime()

    def update_dashboard_stats(self):
        """Update the redesigned dashboard with large cards and enhanced active filters."""
        # Clear existing stats
        for widget in self.stats_dashboard.winfo_children():
            widget.destroy()
        
        for widget in self.active_filters_frame.winfo_children():
            widget.destroy()
        
        if self.df is None or self.df.empty:
            no_data_label = tk.Label(
                self.stats_dashboard, text="📂 No data loaded - Add folders to begin",
                font=("Segoe UI", 12, "bold"), fg="gray"
            )
            no_data_label.pack(pady=10)
            return
        
        # Calculate stats
        total_records = len(self.df)
        filtered_records = len(self.filtered_df) if self.filtered_df is not None else total_records
        filter_percentage = (filtered_records / total_records * 100) if total_records > 0 else 0
        
        # Get current filter info
        dept_filter = self.dept_filter_var.get().strip()
        search_filter = self.search_var.get().strip()
        
        # Determine active date filter
        active_date_filter = None
        for filter_type, btn in self.filter_buttons.items():
            if btn.cget('relief') == tk.SUNKEN:
                active_date_filter = filter_type
                break
        
        # Large cards data with enhanced stats
        large_cards_data = [
            ("Total Records", total_records, "#3498DB", "📋"),
            ("Filtered Results", filtered_records, "#2ECC71", "👁️"),
            ("Match Rate", f"{filter_percentage:.0f}%", "#E67E22", "🎯"),
            ("Data Sources", len(self.folder_paths), "#9B59B6", "📁"),
        ]
        
        # Add filter-specific stats
        working_df = self.filtered_df if self.filtered_df is not None else self.df
        
        # Department-specific stats
        if 'Department Name' in working_df.columns:
            unique_depts = working_df['Department Name'].nunique()
            large_cards_data.append(("Departments", unique_depts, "#8E44AD", "🏢"))
        
        # Search-specific stats
        if search_filter and self.current_search_terms:
            search_matches = len(self.current_search_terms)
            large_cards_data.append(("Search Terms", search_matches, "#E74C3C", "🔍"))
        
        # Add date-based cards if available
        if 'Closing Date' in working_df.columns:
            today = datetime.now().date()
            try:
                closing_dates_series = self._safe_parse_dates(working_df['Closing Date'])
                
                if closing_dates_series is not None and not closing_dates_series.empty:
                    closing_dates = closing_dates_series.dt.date
                    valid_dates = closing_dates.dropna()
                    
                    if len(valid_dates) > 0:
                        closing_today = sum(valid_dates == today)
                        closing_week = sum((valid_dates >= today) & (valid_dates <= today + timedelta(days=7)))
                        closing_15days = sum((valid_dates >= today) & (valid_dates <= today + timedelta(days=15)))
                        closing_month = sum((valid_dates >= today) & (valid_dates <= today + timedelta(days=30)))
                        
                        # Highlight active date filter or show all
                        date_cards = [
                            ("Today", closing_today, "#E74C3C", "🚨"),
                            ("7 Days", closing_week, "#F39C12", "⏰"),
                            ("15 Days", closing_15days, "#8E44AD", "📅"),
                            ("30 Days", closing_month, "#16A085", "📆"),
                        ]
                        
                        # If a date filter is active, highlight that card
                        if active_date_filter:
                            filter_name_map = {
                                'today': 'Today',
                                'tomorrow': 'Tomorrow',
                                '3days': '3 Days',
                                '7days': '7 Days', 
                                '15days': '15 Days',
                                'month': '30 Days'
                            }
                            
                            # Add the active filter card with special highlighting
                            if active_date_filter == 'tomorrow':
                                tomorrow_count = sum(valid_dates == today + timedelta(days=1))
                                large_cards_data.append(("🔥 Tomorrow", tomorrow_count, "#C0392B", "⚡"))
                            elif active_date_filter == '3days':
                                three_days_count = sum((valid_dates >= today) & (valid_dates <= today + timedelta(days=3)))
                                large_cards_data.append(("🔥 3 Days", three_days_count, "#C0392B", "⚡"))
                            else:
                                # Find matching card and highlight it
                                for card_name, count, color, icon in date_cards:
                                    if filter_name_map.get(active_date_filter) == card_name:
                                        large_cards_data.append((f"🔥 {card_name}", count, "#C0392B", "⚡"))
                                        break
                        else:
                            # Add regular date cards
                            large_cards_data.extend(date_cards[:3])  # Show first 3 to fit in row
                        
            except Exception as e:
                logger.warning(f"Error calculating date stats: {e}")
        
        # Create large cards with improved styling
        cards_per_row = min(8, len(large_cards_data))  # Max 8 cards to fit in one row
        for i, (name, value, color, icon) in enumerate(large_cards_data[:cards_per_row]):
            card_frame = tk.Frame(self.stats_dashboard, bg=color, relief=tk.RAISED, bd=2)
            card_frame.pack(side=tk.LEFT, padx=3, pady=2, fill=tk.BOTH, expand=True)
            
            # Enhanced card layout
            content_frame = tk.Frame(card_frame, bg=color)
            content_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
            
            # Icon at top
            icon_label = tk.Label(
                content_frame, text=icon, font=("Segoe UI", 16),
                bg=color, fg="white"
            )
            icon_label.pack(pady=(0, 2))
            
            # Value in center (larger)
            value_label = tk.Label(
                content_frame, text=str(value), font=("Segoe UI", 14, "bold"),
                bg=color, fg="white"
            )
            value_label.pack(pady=1)
            
            # Name at bottom
            name_label = tk.Label(
                content_frame, text=name, font=("Segoe UI", 8, "bold"),
                bg=color, fg="white"
            )
            name_label.pack()
        
        # Enhanced Active Filters Section
        self.create_active_filters_display(dept_filter, search_filter, active_date_filter)

    def create_active_filters_display(self, dept_filter, search_filter, active_date_filter=None):
        """Create an enhanced active filters display with date filter info."""
        has_filters = dept_filter or search_filter or active_date_filter
        
        if not has_filters:
            # Show "No filters active" message
            no_filters_frame = tk.Frame(self.active_filters_frame, bg="#ECF0F1", relief=tk.RIDGE, bd=1)
            no_filters_frame.pack(fill=tk.X, pady=(5, 0))
            
            no_filters_label = tk.Label(
                no_filters_frame, 
                text="🔓 No active filters - Showing all data",
                font=("Segoe UI", 10), fg="#7F8C8D", bg="#ECF0F1"
            )
            no_filters_label.pack(pady=6)
            return
        
        # Active filters header
        filters_header_frame = tk.Frame(self.active_filters_frame, bg="#34495E", relief=tk.RAISED, bd=1)
        filters_header_frame.pack(fill=tk.X, pady=(5, 0))
        
        filters_header = tk.Label(
            filters_header_frame,
            text="🔍 ACTIVE FILTERS",
            font=("Segoe UI", 10, "bold"),
            bg="#34495E", fg="#ECF0F1"
        )
        filters_header.pack(pady=4)
        
        # Filters content frame
        filters_content_frame = tk.Frame(self.active_filters_frame)
        filters_content_frame.pack(fill=tk.X)
        
        # Date filter display (show first if active)
        if active_date_filter:
            date_frame = tk.Frame(filters_content_frame, bg="#C0392B", relief=tk.RAISED, bd=1)
            date_frame.pack(side=tk.LEFT, padx=(0, 5), pady=2, fill=tk.Y)
            
            date_header = tk.Label(
                date_frame,
                text="📅 Date Filter",
                font=("Segoe UI", 9, "bold"),
                bg="#C0392B", fg="white"
            )
            date_header.pack(padx=8, pady=(4, 2))
            
            # Date filter details
            filter_display_names = {
                'today': 'Today Only',
                'tomorrow': 'Tomorrow Only', 
                '3days': 'Next 3 Days',
                '7days': 'Next 7 Days',
                '15days': 'Next 15 Days',
                'month': 'Next 30 Days'
            }
            
            date_name = filter_display_names.get(active_date_filter, active_date_filter.title())
            date_label = tk.Label(
                date_frame,
                text=str(date_name),  # Fix: Convert to string to handle None
                font=("Segoe UI", 8, "bold"),
                bg="#C0392B", fg="#FADBD8"
            )
            date_label.pack(padx=8, pady=(0, 4))
        
        # Department filter display
        if dept_filter:
            # Fix: Safe handling of dept_names splitting and type checking
            try:
                dept_names = [name.strip() for name in dept_filter.split(',') if name.strip()]
                if not isinstance(dept_names, list):
                    dept_names = []
            except Exception:
                dept_names = []  # Fallback to empty list
            
            dept_frame = tk.Frame(filters_content_frame, bg="#3498DB", relief=tk.RAISED, bd=1)
            dept_frame.pack(side=tk.LEFT, padx=(0, 5), pady=2, fill=tk.Y)
            
            # Department filter header
            dept_header = tk.Label(
                dept_frame,
                text="🏢 Department",
                font=("Segoe UI", 9, "bold"),
                bg="#3498DB", fg="white"
            )
            dept_header.pack(padx=8, pady=(4, 2))
            
            # Department count - Fix: Simplified safe len() call
            dept_count = len(dept_names) if isinstance(dept_names, list) else 0
            dept_count_label = tk.Label(
                dept_frame,
                text=f"{dept_count} department(s)",
                font=("Segoe UI", 8, "bold"),
                bg="#3498DB", fg="#E8F6F3"
            )
            dept_count_label.pack(padx=8)
            
            # Show department names (limited) - Fix: Safe iteration with type check
            display_depts = dept_names[:3] if isinstance(dept_names, list) else []
            for dept in display_depts:
                if dept and isinstance(dept, str):
                    dept_name_label = tk.Label(
                        dept_frame,
                        text=f"• {dept[:20]}{'...' if len(dept) > 20 else ''}",
                        font=("Segoe UI", 7),
                        bg="#3498DB", fg="white",
                        anchor="w"
                    )
                    dept_name_label.pack(padx=8, fill=tk.X)
            if isinstance(dept_names, list) and len(dept_names) > 3:
                more_label = tk.Label(
                    dept_frame,
                    text=f"... and {len(dept_names) - 3} more",
                    font=("Segoe UI", 7, "italic"),
                    bg="#3498DB", fg="#E8F6F3"
                )
                more_label.pack(padx=8, pady=(0, 4))
            else:
                tk.Label(dept_frame, text="", bg="#3498DB").pack(pady=2)
        
        # Search filter display
        if search_filter:
            search_frame = tk.Frame(filters_content_frame, bg="#E74C3C", relief=tk.RAISED, bd=1)
            search_frame.pack(side=tk.LEFT, padx=(0, 5), pady=2, fill=tk.Y)
            
            # Search filter header
            search_header = tk.Label(
                search_frame,
                text="🔍 Global Search",
                font=("Segoe UI", 9, "bold"),
                bg="#E74C3C", fg="white"
            )
            search_header.pack(padx=8, pady=(4, 2))
            
            # Search terms count - Fix: Safe len() with None check
            terms_count = len(self.current_search_terms) if self.current_search_terms is not None else 0
            search_count_label = tk.Label(
                search_frame,
                text=f"{terms_count} search term(s)",
                font=("Segoe UI", 8, "bold"),
                bg="#E74C3C", fg="#FADBD8"
            )
            search_count_label.pack(padx=8)
            
            # Search string (truncated)
            search_display = search_filter[:30] + "..." if len(search_filter) > 30 else search_filter
            search_text_label = tk.Label(
                search_frame,
                text=f'"{search_display}"',
                font=("Segoe UI", 8),
                bg="#E74C3C", fg="white",
                wraplength=150
            )
            search_text_label.pack(padx=8, pady=(0, 2))
            
            # Search analysis
            analysis_parts = []
            if any(char.isdigit() for char in search_filter):
                analysis_parts.append("Contains numbers")
            if len(search_filter.split()) > 1:
                analysis_parts.append("Multi-word search")
            if len(search_filter) > 20:
                analysis_parts.append("Long query")
            
            if analysis_parts:
                analysis_text = " • ".join(analysis_parts[:2])  # Show max 2 analysis points
                analysis_label = tk.Label(
                    search_frame,
                    text=analysis_text,
                    font=("Segoe UI", 6, "italic"),
                    bg="#E74C3C", fg="#FADBD8"
                )
                analysis_label.pack(padx=8, pady=(0, 4))
            else:
                # Add bottom padding
                tk.Label(search_frame, text="", bg="#E74C3C").pack(pady=2)
        
        # Filter statistics
        if self.filtered_df is not None:
            total_records = len(self.df)
            filtered_records = len(self.filtered_df)
            reduction = ((total_records - filtered_records) / total_records * 100) if total_records > 0 else 0
            
            stats_frame = tk.Frame(filters_content_frame, bg="#16A085", relief=tk.RAISED, bd=1)
            stats_frame.pack(side=tk.LEFT, padx=(0, 5), pady=2, fill=tk.Y)
            
            stats_header = tk.Label(
                stats_frame,
                text="📊 Filter Impact",
                font=("Segoe UI", 9, "bold"),
                bg="#16A085", fg="white"
            )
            stats_header.pack(padx=8, pady=(4, 2))
            
            reduction_label = tk.Label(
                stats_frame,
                text=f"{reduction:.1f}% reduced",
                font=("Segoe UI", 8, "bold"),
                bg="#16A085", fg="#A3F2E6"
            )
            reduction_label.pack(padx=8)
            
            records_label = tk.Label(
                stats_frame,
                text=f"{filtered_records:,} of {total_records:,}",
                font=("Segoe UI", 7),
                bg="#16A085", fg="white"
            )
            records_label.pack(padx=8, pady=(0, 4))
        
        # Clear filters button
        clear_frame = tk.Frame(filters_content_frame)
        clear_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        clear_button = tk.Button(
            clear_frame,
            text="🔄\nClear\nAll",
            command=self.reset_all_filters,
            bg="#95A5A6", fg="white", font=("Segoe UI", 8, "bold"),
            relief=tk.RAISED, bd=2, cursor="hand2",
            width=6
        )
        clear_button.pack(fill=tk.BOTH, expand=True, pady=2)

    def update_datetime(self):
        """Update the datetime display with Indian time."""
        try:
            import pytz
            ist = pytz.timezone('Asia/Kolkata')
            now = datetime.now(ist)
            datetime_str = now.strftime("%d %b %Y\n%I:%M:%S %p IST")
        except ImportError:
            # Fallback if pytz not available
            now = datetime.now()
            datetime_str = now.strftime("%d %b %Y\n%I:%M:%S %p")
        
        self.datetime_label.config(text=datetime_str)
        self.main_window.root.after(1000, self.update_datetime)

    def add_folder(self):
        """Add a folder and remember it for future sessions."""
        folder_path = filedialog.askdirectory(title="Select Tender Data Folder")
        if folder_path and folder_path not in self.folder_paths:
            self.folder_paths.append(folder_path)
            self.update_folder_list()
            self.save_persistent_folders()
            self.load_and_display_data()  # Auto-populate data

    def remove_folder(self):
        """Remove selected folder from the list."""
        selection = self.folder_listbox.curselection()
        if selection:
            index = selection[0]
            removed_path = self.folder_paths.pop(index)
            self.update_folder_list()
            self.save_persistent_folders()
            self.main_window.update_log(f"Removed folder: {os.path.basename(removed_path)}")
            self.load_and_display_data()  # Refresh data

    def clear_folders(self):
        """Clear all folders after confirmation."""
        if self.folder_paths and messagebox.askyesno(
            "Clear Folders", 
            f"Remove all {len(self.folder_paths)} folders from the list?"
        ):
            self.folder_paths.clear()
            self.update_folder_list()
            self.save_persistent_folders()
            self.clear_data()

    def update_folder_list(self):
        """Update the folder listbox display."""
        self.folder_listbox.delete(0, tk.END)
        for path in self.folder_paths:
            display_name = f"{os.path.basename(path)} ({len(os.path.basename(path))} chars)"
            self.folder_listbox.insert(tk.END, display_name)

    def load_and_display_data(self):
        """Load data from all folders and display automatically."""
        if not self.folder_paths:
            # Safe status update with None check
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.config(text="No folders selected")
            return
        
        # Safe status update with None check
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.config(text="Loading data...")
        self.main_window.root.update()
        
        # Load data in background thread
        def load_data_thread():
            try:
                all_dataframes = []
                total_files = 0
                
                for folder_path in self.folder_paths:
                    if os.path.exists(folder_path):
                        # Get all Excel files, but skip temporary files
                        excel_files = [f for f in os.listdir(folder_path) 
                                     if f.endswith(('.xlsx', '.xls')) and not f.startswith('~$')]
                        total_files += len(excel_files)
                        
                        for file in excel_files:
                            file_path = os.path.join(folder_path, file)
                            try:
                                # Try to read with different engines and handle errors
                                df = None
                                try:
                                    df = pd.read_excel(file_path, engine='openpyxl')
                                except Exception:
                                    try:
                                        df = pd.read_excel(file_path, engine='xlrd')
                                    except Exception:
                                        try:
                                            df = pd.read_excel(file_path)
                                        except Exception as e:
                                            logger.warning(f"Error reading {file}: {e}")
                                            continue
                                
                                if df is not None and not df.empty:
                                    df['Source_File'] = file
                                    df['Source_Folder'] = os.path.basename(folder_path)
                                    all_dataframes.append(df)
                                    
                            except Exception as e:
                                logger.warning(f"Error reading {file}: {e}")
                
                if all_dataframes:
                    self.df = pd.concat(all_dataframes, ignore_index=True)
                    # Store original data
                    self.original_df = self.df.copy()
                    # Call display_data method correctly
                    self.main_window.root.after(0, self.display_data)
                    # Safe status update
                    def update_status():
                        if hasattr(self, 'status_label') and self.status_label:
                            record_count = len(self.df) if self.df is not None else 0
                            self.status_label.config(text=f"Loaded {record_count} records from {total_files} files")
                    self.main_window.root.after(0, update_status)
                else:
                    # Safe status update
                    def update_status_no_files():
                        if hasattr(self, 'status_label') and self.status_label:
                            self.status_label.config(text="No Excel files found in selected folders")
                    self.main_window.root.after(0, update_status_no_files)
                    
            except Exception as e:
                logger.error(f"Error loading data: {e}")
                # Safe status update
                def update_status_error():
                    if hasattr(self, 'status_label') and self.status_label:
                        self.status_label.config(text=f"Error loading data: {str(e)}")
                self.main_window.root.after(0, update_status_error)
        
        threading.Thread(target=load_data_thread, daemon=True).start()

    def display_data(self):
        """Display data in the table with proper filtering and highlighting."""
        if not hasattr(self, 'tree') or self.tree is None:
            logger.warning("Tree widget not initialized")
            return
        
        # Apply current filters first
        self.apply_filters()
        
        # Clear existing data
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Get data to display (filtered or all)
        display_df = self.filtered_df if self.filtered_df is not None else self.df
        
        if display_df is None or display_df.empty:
            # Update status and dashboard
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.config(text="No data to display")
            self.update_dashboard_stats()
            return
        
        # Configure columns
        columns_to_show = [
            'Department Name', 'Title and Ref.No./Tender ID', 'Organisation Chain',
            'Closing Date', 'Value in Lakhs', 'State', 'Source_File'
        ]
        
        # Add URL columns if they exist
        url_columns = []
        for col in display_df.columns:
            if any(url_indicator in col.lower() for url_indicator in ['url', 'link', 'direct']):
                url_columns.append(col)
        
        # Filter columns to only show those that exist in the dataframe
        available_columns = [col for col in columns_to_show if col in display_df.columns]
        available_columns.extend(url_columns)
        
        # Configure tree columns
        self.tree["columns"] = available_columns
        self.tree["show"] = "headings"
        
        # Configure column headings and widths
        for col in available_columns:
            self.tree.heading(col, text=col, anchor="w")
            
            # Set appropriate column widths
            if col == 'Title and Ref.No./Tender ID':
                width = 400
            elif col == 'Department Name':
                width = 250
            elif col == 'Organisation Chain':
                width = 200
            elif 'URL' in col or 'Link' in col:
                width = 80
            else:
                width = 120
            
            self.tree.column(col, width=width, minwidth=50, anchor="w")
        
        # Insert data with highlighting
        for idx, row in display_df.iterrows():
            values = []
            tags = []
            
            for col in available_columns:
                cell_value = row.get(col, "")
                
                # Handle URL columns
                if any(url_indicator in col.lower() for url_indicator in ['url', 'link', 'direct']):
                    if pd.notna(cell_value) and str(cell_value).strip():
                        values.append("🔗 View")
                        tags.append("url")
                    else:
                        values.append("")
                else:
                    # Regular data handling
                    if pd.isna(cell_value):
                        values.append("")
                    else:
                        cell_str = str(cell_value)
                        # Truncate long values
                        if len(cell_str) > 100:
                            cell_str = cell_str[:97] + "..."
                        values.append(cell_str)
                
                # Check for search term highlighting
                if (self.current_search_terms and cell_value and 
                    any(term.lower() in str(cell_value).lower() for term in self.current_search_terms)):
                    if "highlighted" not in tags:
                        tags.append("highlighted")
            
            # Use appropriate tag
            tag = tags[0] if tags else "normal"
            self.tree.insert("", "end", values=values, tags=(tag,))
        
        # Update stats and status
        record_count = len(display_df)
        filter_info = ""
        if self.filtered_df is not None:
            total_count = len(self.df) if self.df is not None else 0
            filter_info = f" (filtered from {total_count:,})"
        
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.config(text=f"Displaying {record_count:,} records{filter_info}")
        
        # Update dashboard stats
        self.update_dashboard_stats()

    def update_stats(self):
        """Update the statistics panel with colorful stats and query information."""
        # Clear existing stats
        for widget in self.stats_dashboard.winfo_children():
            widget.destroy()
        
        if self.df is None or self.df.empty:
            no_data_label = tk.Label(
                self.stats_dashboard, text="No data loaded",
                font=("Segoe UI", 11), fg="gray"
            )
            no_data_label.pack(pady=25)
            return
        
        # Calculate basic stats
        total_records = len(self.df)
        filtered_records = len(self.filtered_df) if self.filtered_df is not None else total_records
        filter_percentage = (filtered_records / total_records * 100) if total_records > 0 else 0
        
        # Get current filter info
        dept_filter = self.dept_filter_var.get().strip()
        search_filter = self.search_var.get().strip()
        
        # Basic stats
        stats_data = [
            ("Total Records", total_records, "#3498DB"),
            ("Filtered Records", filtered_records, "#2ECC71"),
            ("Filter Match %", f"{filter_percentage:.1f}%", "#E67E22"),
            ("Data Folders", len(self.folder_paths), "#9B59B6"),
        ]
        
        # Query-specific stats
        if dept_filter or search_filter:
            query_stats = []
            
            if dept_filter:
                # Fix: Safe handling of dept_names with proper type checking
                try:
                    dept_names = [name.strip() for name in dept_filter.split(',') if name.strip()]
                    dept_count = len(dept_names) if isinstance(dept_names, list) else 0
                    query_stats.append(("Dept Filters", dept_count, "#8E44AD"))
                except Exception:
                    query_stats.append(("Dept Filters", 0, "#8E44AD"))
            
            if search_filter:
                search_terms = len(self.current_search_terms) if self.current_search_terms is not None else 0
                query_stats.append(("Search Terms", search_terms, "#E74C3C"))
            
            # Add department breakdown if filtering by department
            if dept_filter and self.filtered_df is not None and 'Department Name' in self.filtered_df.columns:
                unique_depts = self.filtered_df['Department Name'].nunique()
                query_stats.append(("Matched Depts", unique_depts, "#F39C12"))
            
            stats_data.extend(query_stats)
        else:
            # Show general department info
            if 'Department Name' in self.df.columns:
                unique_depts = self.df['Department Name'].nunique()
                stats_data.append(("Unique Departments", unique_depts, "#E67E22"))
        
        # Date-related stats
        if 'Closing Date' in self.df.columns:
            today = datetime.now().date()
            try:
                # Use filtered data if available, otherwise use full dataset
                working_df = self.filtered_df if self.filtered_df is not None else self.df
                closing_dates_series = self._safe_parse_dates(working_df['Closing Date'])
                
                if closing_dates_series is not None and not closing_dates_series.empty:
                    closing_dates = closing_dates_series.dt.date
                    valid_dates = closing_dates.dropna()
                    
                    if len(valid_dates) > 0:
                        # Calculate date-based stats
                        closing_today = sum(valid_dates == today)
                        closing_week = sum((valid_dates >= today) & (valid_dates <= today + timedelta(days=7)))
                        closing_month = sum((valid_dates >= today) & (valid_dates <= today + timedelta(days=30)))
                        expired = sum(valid_dates < today)
                        
                        stats_data.extend([
                            ("Closing Today", closing_today, "#E74C3C"),
                            ("Next 7 Days", closing_week, "#F39C12"),
                            ("Next 30 Days", closing_month, "#3498DB"),
                            ("Expired", expired, "#95A5A6"),
                        ])
            except Exception as e:
                logger.warning(f"Error calculating date stats: {e}")
        
        # Performance stats
        if self.filtered_df is not None:
            reduction_percent = ((total_records - filtered_records) / total_records * 100) if total_records > 0 else 0
            stats_data.append(("Performance Gain", f"{reduction_percent:.1f}%", "#2ECC71"))
        
        # Display stats with improved layout
        for i, (name, value, color) in enumerate(stats_data):
            stat_frame = tk.Frame(self.stats_dashboard, bg=color, relief=tk.RAISED, bd=2)
            stat_frame.pack(side=tk.LEFT, padx=3, pady=2, fill=tk.BOTH, expand=True)
            
            # Enhanced stat layout
            content_frame = tk.Frame(stat_frame, bg=color)
            content_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
            
            # Icon at top
            icon_label = tk.Label(
                content_frame, text="📊", font=("Segoe UI", 16),
                bg=color, fg="white"
            )
            icon_label.pack(pady=(0, 2))
            
            # Value in center (larger)
            value_label = tk.Label(
                content_frame, text=str(value), font=("Segoe UI", 14, "bold"),
                bg=color, fg="white"
            )
            value_label.pack(pady=1)
            
            # Name at bottom
            name_label = tk.Label(
                content_frame, text=name, font=("Segoe UI", 8, "bold"),
                bg=color, fg="white"
            )
            name_label.pack()

    def on_filter_change(self, *args):
        """Handle changes to filter inputs with debouncing."""
        # Cancel any existing delayed update
        if hasattr(self, '_filter_update_job'):
            self.main_window.root.after_cancel(self._filter_update_job)
        
        # Schedule a new update after a short delay (debouncing)
        self._filter_update_job = self.main_window.root.after(300, self._apply_filter_update)

    def _apply_filter_update(self):
        """Apply filter updates after debouncing delay."""
        try:
            self.apply_filters()
            self.display_data()
        except Exception as e:
            logger.warning(f"Error applying filter update: {e}")

    def reset_all_filters(self):
        """Reset all active filters to their default state."""
        try:
            # Clear text filters
            self.dept_filter_var.set("")
            self.search_var.set("")
            
            # Reset date filter buttons
            for btn in self.filter_buttons.values():
                btn.config(relief=tk.RAISED)
            
            # Clear filtered data
            self.filtered_df = None
            self.current_search_terms = []
            
            # Refresh display
            self.display_data()
            
            logger.info("All filters reset")
            
        except Exception as e:
            logger.error(f"Error resetting filters: {e}")

    def export_filtered_data(self):
        """Export the currently filtered data to Excel."""
        try:
            # Get data to export
            export_df = self.filtered_df if self.filtered_df is not None else self.df
            
            if export_df is None or export_df.empty:
                messagebox.showwarning("No Data", "No data available to export.")
                return
            
            # Ask user for save location
            filename = filedialog.asksaveasfilename(
                title="Export Filtered Data",
                defaultextension=".xlsx",
                filetypes=[
                    ("Excel files", "*.xlsx"),
                    ("CSV files", "*.csv"),
                    ("All files", "*.*")
                ]
            )
            
            if filename:
                # Export based on file extension
                if filename.lower().endswith('.csv'):
                    export_df.to_csv(filename, index=False, encoding='utf-8')
                else:
                    export_df.to_excel(filename, index=False, engine='openpyxl')
                
                messagebox.showinfo(
                    "Export Complete", 
                    f"Data exported successfully!\n\n"
                    f"Records: {len(export_df):,}\n"
                    f"File: {os.path.basename(filename)}"
                )
                logger.info(f"Exported {len(export_df)} records to {filename}")
                
        except Exception as e:
            error_msg = f"Error exporting data: {str(e)}"
            logger.error(error_msg)
            messagebox.showerror("Export Error", error_msg)

    def apply_filters(self):
        """Apply all active filters to the data with improved multi-filter support."""
        if self.df is None:
            return
        
        # Start with original dataset and reset index to avoid alignment issues
        working_df = self.df.copy().reset_index(drop=True)
        
        # Apply department filter (supporting multiple departments)
        dept_filter = self.dept_filter_var.get().strip()
        if dept_filter and 'Department Name' in working_df.columns:
            # Split by comma and clean up department names
            dept_names = [name.strip().lower() for name in dept_filter.split(',') if name.strip()]
            
            if dept_names:
                # Create mask for any of the specified departments
                dept_mask = pd.Series([False] * len(working_df), index=working_df.index)
                for dept_name in dept_names:
                    # Use safe string operations
                    dept_column = working_df['Department Name'].fillna('')
                    dept_mask |= dept_column.str.lower().str.contains(
                        dept_name, na=False, regex=False
                    )
                working_df = working_df[dept_mask].reset_index(drop=True)
                logger.debug(f"Applied department filter for: {dept_names}")
        
        # Apply general search filter and prepare highlighting
        search_term = self.search_var.get().strip().lower()
        self.current_search_terms = []
        
        if search_term:
            # Store search terms for highlighting
            self.current_search_terms = [term.strip() for term in search_term.split() if term.strip()]
            
            # Search across multiple columns
            search_columns = ['Department Name', 'Title and Ref.No./Tender ID', 'Organisation Chain']
            search_mask = pd.Series([False] * len(working_df), index=working_df.index)
            
            for col in search_columns:
                if col in working_df.columns:
                    # Use safe string operations
                    col_data = working_df[col].fillna('')
                    search_mask |= col_data.str.lower().str.contains(
                        search_term, na=False, regex=False
                    )
            
            working_df = working_df[search_mask].reset_index(drop=True)
            logger.debug(f"Applied search filter: '{search_term}'")
        
        # Check if any date filter is active and apply it
        active_date_filter = None
        for filter_type, btn in self.filter_buttons.items():
            if btn.cget('relief') == tk.SUNKEN:
                active_date_filter = filter_type
                break
        
        if active_date_filter and 'Closing Date' in working_df.columns:
            today = datetime.now().date()
            
            # Calculate date range based on filter type
            if active_date_filter == "today":
                start_date = today
                end_date = today
            elif active_date_filter == "tomorrow":
                start_date = today + timedelta(days=1)
                end_date = today + timedelta(days=1)
            elif active_date_filter == "3days":
                start_date = today
                end_date = today + timedelta(days=3)
            elif active_date_filter == "7days":
                start_date = today
                end_date = today + timedelta(days=7)
            elif active_date_filter == "15days":
                start_date = today
                end_date = today + timedelta(days=15)
            elif active_date_filter == "month":
                start_date = today
                end_date = today + timedelta(days=30)
            else:
                start_date = end_date = None
            
            if start_date and end_date:
                try:
                    closing_dates_series = self._safe_parse_dates(working_df['Closing Date'])
                    
                    if closing_dates_series is not None and not closing_dates_series.empty:
                        closing_dates = closing_dates_series.dt.date
                        date_mask = (closing_dates >= start_date) & (closing_dates <= end_date)
                        date_mask = date_mask.fillna(False)
                        working_df = working_df[date_mask].reset_index(drop=True)
                        logger.debug(f"Applied date filter '{active_date_filter}': {start_date} to {end_date}")
                    
                except Exception as e:
                    logger.warning(f"Error applying date filter in combined filters: {e}")
        
        # Update the filtered dataframe
        if len(working_df) != len(self.df):
            self.filtered_df = working_df
        else:
            self.filtered_df = None  # No filtering applied

    def _safe_parse_dates(self, date_series):
        """Safely parse dates with multiple fallback methods."""
        if date_series is None or date_series.empty:
            return None
            
        # Suppress specific pandas warnings for this method
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='Could not infer format')
            
            try:
                # Method 1: Try with specific format
                result = pd.to_datetime(date_series, format='%d-%m-%Y', errors='coerce')
                if not result.isna().all():
                    return result
            except:
                pass
            
            try:
                # Method 2: Try with dayfirst=True
                result = pd.to_datetime(date_series, dayfirst=True, errors='coerce')
                if not result.isna().all():
                    return result
            except:
                pass
            
            try:
                # Method 3: Let pandas infer
                result = pd.to_datetime(date_series, errors='coerce')
                return result
            except:
                return None

    def apply_date_filter(self, filter_type):
        """Apply date-based filters to the data with improved error handling."""
        if self.df is None or 'Closing Date' not in self.df.columns:
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.config(text="No closing date data available for filtering")
            return
        
        # Reset button styles
        for btn_type, btn in self.filter_buttons.items():
            btn.config(relief=tk.RAISED)
        
        if filter_type == "reset":
            self.filtered_df = None
            self.current_search_terms = []
            logger.info("Date filters reset")
        else:
            today = datetime.now().date()
            
            # Calculate date range based on filter type
            if filter_type == "today":
                start_date = today
                end_date = today
            elif filter_type == "tomorrow":
                start_date = today + timedelta(days=1)
                end_date = today + timedelta(days=1)
            elif filter_type == "3days":
                start_date = today
                end_date = today + timedelta(days=3)
            elif filter_type == "7days":
                start_date = today
                end_date = today + timedelta(days=7)
            elif filter_type == "15days":
                start_date = today
                end_date = today + timedelta(days=15)
            elif filter_type == "month":
                start_date = today
                end_date = today + timedelta(days=30)
            else:
                logger.warning(f"Unknown filter type: {filter_type}")
                return
            
            # Apply date filter with improved error handling
            try:
                # Start with original data and apply all filters
                working_df = self.df.copy().reset_index(drop=True)
                
                # First apply other filters (dept and search)
                dept_filter = self.dept_filter_var.get().strip()
                search_filter = self.search_var.get().strip()
                
                # Apply department filter
                if dept_filter and 'Department Name' in working_df.columns:
                    dept_names = [name.strip().lower() for name in dept_filter.split(',') if name.strip()]
                    if dept_names:
                        dept_mask = pd.Series([False] * len(working_df), index=working_df.index)
                        for dept_name in dept_names:
                            dept_column = working_df['Department Name'].fillna('')
                            dept_mask |= dept_column.str.lower().str.contains(
                                dept_name, na=False, regex=False
                            )
                        working_df = working_df[dept_mask].reset_index(drop=True)
                
                # Apply search filter
                if search_filter:
                    self.current_search_terms = [term.strip() for term in search_filter.lower().split() if term.strip()]
                    search_columns = ['Department Name', 'Title and Ref.No./Tender ID', 'Organisation Chain']
                    search_mask = pd.Series([False] * len(working_df), index=working_df.index)
                    
                    for col in search_columns:
                        if col in working_df.columns:
                            col_data = working_df[col].fillna('')
                            search_mask |= col_data.str.lower().str.contains(
                                search_filter.lower(), na=False, regex=False
                            )
                    
                    working_df = working_df[search_mask].reset_index(drop=True)
                
                # Now apply date filter
                closing_dates_series = self._safe_parse_dates(working_df['Closing Date'])
                
                if closing_dates_series is not None and not closing_dates_series.empty:
                    closing_dates = closing_dates_series.dt.date
                    
                    # Create date mask
                    date_mask = (closing_dates >= start_date) & (closing_dates <= end_date)
                    date_mask = date_mask.fillna(False)
                    
                    # Apply date filter
                    self.filtered_df = working_df[date_mask].reset_index(drop=True)
                    
                    # Highlight active filter button
                    if filter_type in self.filter_buttons:
                        self.filter_buttons[filter_type].config(relief=tk.SUNKEN)
                    
                    # Log filter results
                    logger.info(f"Date filter '{filter_type}' applied: {len(self.filtered_df)} records from {start_date} to {end_date}")
                    
                else:
                    logger.warning("Could not parse any closing dates for filtering")
                    if hasattr(self, 'status_label') and self.status_label:
                        self.status_label.config(text="Error: Could not parse closing dates")
                    return
                
            except Exception as e:
                logger.error(f"Error applying date filter '{filter_type}': {e}")
                if hasattr(self, 'status_label') and self.status_label:
                    self.status_label.config(text=f"Error applying date filter: {str(e)}")
                return
        
        # Refresh display
        self.display_data()

    def create_data_table(self):
        """Create the data display table with search highlighting."""
        table_frame = ttk.LabelFrame(self, text="📋 Tender Data", padding=5)
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create Treeview with scrollbars
        tree_frame = ttk.Frame(table_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tree = ttk.Treeview(tree_frame, show="headings", height=18)
        
        # Configure treeview with larger font
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        
        # Configure highlighting tags
        self.tree.tag_configure("highlighted", background="#E8F5E8", foreground="#2E7D32")
        self.tree.tag_configure("normal", background="white", foreground="black")
        self.tree.tag_configure("url", background="#E3F2FD", foreground="#1976D2")
        
        # Bind events for copy and URL functionality
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack scrollbars and tree
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Status bar
        status_frame = ttk.Frame(table_frame)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.status_label = ttk.Label(
            status_frame, text="Ready - Load folders to view tender data",
            font=("Segoe UI", 10)
        )
        self.status_label.pack(side=tk.LEFT)

    def on_double_click(self, event):
        """Handle double-click on table cells with improved URL handling."""
        item = self.tree.selection()[0] if self.tree.selection() else None
        if not item:
            return
        
        # Get clicked column
        column = self.tree.identify_column(event.x)
        if not column:
            return
        
        col_index = int(column.replace('#', '')) - 1
        
        # Safe column access with bounds checking
        tree_columns = self.tree.cget("columns")
        if tree_columns and col_index < len(tree_columns):
            col_name = tree_columns[col_index]
        else:
            return
        
        displayed_value = self.tree.item(item, "values")[col_index]
        
        # For URL columns, get the actual URL from the dataframe
        if 'URL' in col_name and displayed_value == "🔗 View":
            # Get row index and actual URL value
            children = self.tree.get_children()
            row_index = children.index(item)
            
            display_df = self.filtered_df if self.filtered_df is not None else self.df
            if display_df is not None and row_index < len(display_df):
                # Find actual column name
                actual_col = col_name
                column_alternatives = {
                    'Status/Opening URL': ['StatusURL', 'Status_URL', 'Opening_URL', 'Status Link', 'Opening Link', 'Status URL'],
                    'Direct URL': ['DirectURL', 'Direct_URL', 'URL', 'Link', 'Tender_URL', 'Tender URL'],
                }
                
                if hasattr(display_df, 'columns') and col_name not in display_df.columns:
                    for alt_col in column_alternatives.get(col_name, []):
                        if alt_col in display_df.columns:
                            actual_col = alt_col
                            break
                
                if hasattr(display_df, 'columns') and actual_col in display_df.columns:
                    actual_url = display_df.iloc[row_index][actual_col]
                    self.open_url(actual_url)
                else:
                    self.copy_to_clipboard(displayed_value, f"Copied {col_name}")
        else:
            self.copy_to_clipboard(displayed_value, f"Copied {col_name}")

    def on_right_click(self, event):
        """Handle right-click context menu."""
        # Implementation for context menu
        pass

    def open_url(self, url):
        """Open URL in default browser."""
        if url and pd.notna(url):
            import webbrowser
            try:
                webbrowser.open(str(url))
                logger.info(f"Opened URL: {url}")
            except Exception as e:
                logger.error(f"Error opening URL {url}: {e}")

    def copy_to_clipboard(self, text, message="Copied to clipboard"):
        """Copy text to clipboard."""
        try:
            self.main_window.root.clipboard_clear()
            self.main_window.root.clipboard_append(str(text))
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.config(text=message)
            logger.debug(f"Copied to clipboard: {text[:50]}...")
        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")

    def clear_data(self):
        """Clear all loaded data."""
        self.df = None
        self.filtered_df = None
        self.original_df = None
        self.current_search_terms = []
        
        # Clear the tree widget
        if hasattr(self, 'tree'):
            for item in self.tree.get_children():
                self.tree.delete(item)
        
        # Update dashboard
        self.update_dashboard_stats()
        
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.config(text="Data cleared")

