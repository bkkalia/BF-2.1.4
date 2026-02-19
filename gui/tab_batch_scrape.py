import concurrent.futures
import csv
import glob
import json
import os
import random
import re
import sqlite3
import sys
import threading
import time
import tkinter as tk
from datetime import datetime, timedelta
import tempfile
from tkinter import ttk, scrolledtext, Listbox, Scrollbar, END, EXTENDED, StringVar, IntVar, BooleanVar, filedialog
from urllib.parse import urlparse

from batch_config_memory import get_batch_memory
from gui import gui_utils
from scraper.driver_manager import setup_driver, safe_quit_driver
from scraper.logic import fetch_department_list_from_site_v2, run_scraping_logic
from scraper.playwright_logic import fetch_department_list_from_site_playwright
from tender_store import TenderDataStore
from utils import get_website_keyword_from_url, sanitise_filename

try:
    import pandas as pd
except Exception:
    pd = None


class _CompositeStopEvent:
    def __init__(self, primary_event=None, secondary_event=None):
        self.primary_event = primary_event
        self.secondary_event = secondary_event

    def is_set(self):
        primary = bool(self.primary_event and self.primary_event.is_set())
        secondary = bool(self.secondary_event and self.secondary_event.is_set())
        return primary or secondary

    def set(self):
        if self.secondary_event:
            self.secondary_event.set()


class BatchScrapeTab(ttk.Frame):
    """Batch scrape orchestration tab with dashboard, verification and script export."""

    def __init__(self, parent, main_app_ref, **kwargs):
        super().__init__(parent, **kwargs)
        self.main_app = main_app_ref
        self.log_callback = self.main_app.update_log
        self.batch_memory = get_batch_memory()
        self._active_drivers = set()
        self._active_drivers_lock = threading.Lock()

        self.mode_var = StringVar(value="sequential")
        self.max_parallel_var = IntVar(value=2)
        self.department_workers_var = IntVar(value=1)
        self.department_workers_var.trace_add("write", lambda *_args: self._sync_department_workers_setting())
        self.delta_mode_var = StringVar(value="quick")
        self.only_new_var = BooleanVar(value=True)
        self.scrape_scope_var = StringVar(value="only_new")

        self.group_name_var = StringVar(value="")
        self.group_selector_var = StringVar(value="")

        self.per_domain_max_var = IntVar(value=1)
        self.min_delay_var = StringVar(value="1.0")
        self.max_delay_var = StringVar(value="3.0")
        self.cooldown_var = IntVar(value=10)
        self.max_retries_var = IntVar(value=2)

        self.batch_log_filter_portal_var = StringVar(value="All")
        self.batch_log_search_var = StringVar(value="")

        self.batch_log_messages = []
        self.portal_dashboard_rows = {}
        self.portal_live_stats = {}
        self._dashboard_lock = threading.Lock()

        self.manifest_path = os.path.join(os.getcwd(), "batch_tender_manifest.json")
        self.download_manifest = self._load_manifest()

        self.enable_delta_sweep = True
        self.current_batch_delta_mode = "quick"
        self.portal_watchdog_inactivity_sec = 120
        self.portal_watchdog_sleep_jump_sec = 180
        self.current_batch_report_dir = None
        self._batch_job_ids = set()
        self._batch_use_subprocess = False
        self._batch_pending_portals = []
        self._batch_active_jobs = {}
        self._batch_completed_count = 0
        self._batch_total_count = 0
        self._batch_max_parallel = 1
        self._batch_lock = threading.Lock()
        self._batch_only_new = False
        self._batch_delta_mode = "quick"
        self._portal_launch_locks = {}
        self._portal_lock_dir = os.path.join(tempfile.gettempdir(), "blackforest_portal_locks")
        os.makedirs(self._portal_lock_dir, exist_ok=True)

        self.data_status_portal_var = StringVar(value="-")
        self.data_last_full_var = StringVar(value="-")
        self.data_last_export_var = StringVar(value="-")
        self.data_next_due_var = StringVar(value="-")
        self.data_policy_var = StringVar(value="on_demand")

        self._create_widgets()
        self._load_initial_data()

    def _selected_automation_engine(self):
        engine = str((self.main_app.settings or {}).get("automation_engine", "playwright") or "playwright").strip().lower()
        if engine not in {"selenium", "playwright"}:
            return "playwright"
        return engine

    def _fetch_departments_for_portal(self, portal_config, portal_log):
        engine = self._selected_automation_engine()
        org_list_url = portal_config.get("OrgListURL")
        portal_log(f"Automation engine: {engine}")

        if engine == "playwright":
            departments, estimated = fetch_department_list_from_site_playwright(org_list_url, portal_log)
            if departments:
                return departments, estimated
            portal_log("Playwright department fetch returned no rows; falling back to Selenium")

        return fetch_department_list_from_site_v2(org_list_url, portal_log)

    def _interruptible_sleep(self, seconds, stop_event=None, step=0.2):
        remaining = max(0.0, float(seconds or 0.0))
        while remaining > 0:
            if stop_event and stop_event.is_set():
                return False
            wait_for = min(step, remaining)
            time.sleep(wait_for)
            remaining -= wait_for
        return True

    def _register_active_driver(self, driver):
        if not driver:
            return
        with self._active_drivers_lock:
            self._active_drivers.add(driver)

    def _unregister_active_driver(self, driver):
        if not driver:
            return
        with self._active_drivers_lock:
            self._active_drivers.discard(driver)

    def request_emergency_stop(self, stop_event=None):
        handled = False
        if stop_event is not None:
            try:
                stop_event.set()
                handled = True
            except Exception:
                pass

        if hasattr(self.main_app, "stop_supervised_group"):
            try:
                stopped_group = self.main_app.stop_supervised_group("batch", force=True)
                handled = bool(stopped_group) or handled
            except Exception:
                pass

        with self._active_drivers_lock:
            active_drivers = list(self._active_drivers)
            self._active_drivers.clear()

        for driver in active_drivers:
            try:
                safe_quit_driver(driver, self.log_callback)
                handled = True
            except Exception:
                pass

        return handled

    def _build_portal_cli_command(self, portal_name, download_dir, dept_workers=1, only_new=False, delta_mode="quick", manifest_path=None):
        command = [
            sys.executable,
            os.path.join(os.getcwd(), "cli_main.py"),
            "--json-events",
            "--url", str(portal_name),
            "--output", str(download_dir),
            "department",
            "--all",
            "--dept-workers", str(max(1, int(dept_workers or 1))),
        ]
        if only_new:
            command.append("--only-new")
            mode = str(delta_mode or "quick").strip().lower()
            if mode not in ("quick", "full"):
                mode = "quick"
            command.extend(["--delta-mode", mode])
            if manifest_path:
                command.extend(["--manifest-path", str(manifest_path)])
        return command

    def _build_portal_cli_log_path(self, portal_name):
        logs_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        safe_portal = sanitise_filename(str(portal_name or "portal")) or "portal"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(logs_dir, f"batch_cli_{safe_portal}_{stamp}.log")

    def _build_portal_job_command(self, portal_name, download_dir, dept_workers, job_id, log_path=None, only_new=False, delta_mode="quick"):
        command = self._build_portal_cli_command(
            portal_name,
            download_dir,
            dept_workers=max(1, min(3, int(dept_workers or 1))),
            only_new=only_new,
            delta_mode=delta_mode,
            manifest_path=self.manifest_path,
        )
        if "--job-id" not in command:
            command.insert(3, "--job-id")
            command.insert(4, str(job_id))
        if log_path:
            command.insert(5, "--log")
            command.insert(6, str(log_path))
        return command

    def _create_widgets(self):
        section = ttk.Labelframe(self, text="Batch Scrape", style="Section.TLabelframe")
        section.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        top_controls = ttk.Frame(section)
        top_controls.pack(fill=tk.X, padx=5, pady=(8, 8))

        ttk.Label(top_controls, text="Mode:", font=self.main_app.label_font).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Radiobutton(top_controls, text="Sequential", variable=self.mode_var, value="sequential").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(top_controls, text="Parallel", variable=self.mode_var, value="parallel").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(top_controls, text="Max Parallel:", font=self.main_app.label_font).pack(side=tk.LEFT, padx=(6, 4))
        self.max_parallel_spin = ttk.Spinbox(top_controls, from_=1, to=4, width=5, textvariable=self.max_parallel_var)
        self.max_parallel_spin.pack(side=tk.LEFT)

        ttk.Label(top_controls, text="Dept Workers:", font=self.main_app.label_font).pack(side=tk.LEFT, padx=(12, 4))
        self.dept_workers_spin = ttk.Spinbox(top_controls, from_=1, to=3, width=5, textvariable=self.department_workers_var)
        self.dept_workers_spin.pack(side=tk.LEFT)

        ttk.Label(top_controls, text="Scrape:", font=self.main_app.label_font).pack(side=tk.LEFT, padx=(12, 4))
        self.scope_new_radio = ttk.Radiobutton(top_controls, text="Only New", variable=self.scrape_scope_var, value="only_new")
        self.scope_new_radio.pack(side=tk.LEFT, padx=(0, 6))
        self.scope_all_radio = ttk.Radiobutton(top_controls, text="All", variable=self.scrape_scope_var, value="all")
        self.scope_all_radio.pack(side=tk.LEFT, padx=(0, 0))

        ttk.Label(top_controls, text="Delta:", font=self.main_app.label_font).pack(side=tk.LEFT, padx=(12, 4))
        self.delta_mode_combo = ttk.Combobox(top_controls, textvariable=self.delta_mode_var, values=["quick", "full"], state="readonly", width=8)
        self.delta_mode_combo.pack(side=tk.LEFT)

        safety_frame = ttk.Frame(section)
        safety_frame.pack(fill=tk.X, padx=5, pady=(0, 8))

        ttk.Label(safety_frame, text="IP Safety:", font=self.main_app.label_font).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Label(safety_frame, text="Per Domain:").pack(side=tk.LEFT, padx=(0, 4))
        self.per_domain_spin = ttk.Spinbox(safety_frame, from_=1, to=4, width=4, textvariable=self.per_domain_max_var)
        self.per_domain_spin.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(safety_frame, text="Delay(s):").pack(side=tk.LEFT, padx=(0, 4))
        self.min_delay_entry = ttk.Entry(safety_frame, width=5, textvariable=self.min_delay_var)
        self.min_delay_entry.pack(side=tk.LEFT)
        ttk.Label(safety_frame, text="to").pack(side=tk.LEFT, padx=3)
        self.max_delay_entry = ttk.Entry(safety_frame, width=5, textvariable=self.max_delay_var)
        self.max_delay_entry.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(safety_frame, text="Cooldown(s):").pack(side=tk.LEFT, padx=(0, 4))
        self.cooldown_spin = ttk.Spinbox(safety_frame, from_=0, to=300, width=5, textvariable=self.cooldown_var)
        self.cooldown_spin.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(safety_frame, text="Retries:").pack(side=tk.LEFT, padx=(0, 4))
        self.retries_spin = ttk.Spinbox(safety_frame, from_=0, to=5, width=4, textvariable=self.max_retries_var)
        self.retries_spin.pack(side=tk.LEFT)

        top_split = ttk.Frame(section)
        top_split.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 8))

        select_frame = ttk.Frame(top_split)
        select_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(select_frame, text="Select portals (multi-select)", font=self.main_app.label_font).pack(anchor="w", pady=(0, 4))
        listbox_frame = ttk.Frame(select_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)

        self.portal_listbox = Listbox(listbox_frame, selectmode=EXTENDED, font=("Consolas", 10), borderwidth=1, relief="solid", height=10)
        self.portal_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.portal_listbox.bind("<<ListboxSelect>>", lambda _e: self._refresh_data_status())
        scrollbar = Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.portal_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.portal_listbox.config(yscrollcommand=scrollbar.set)

        actions_frame = ttk.Frame(top_split)
        actions_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))

        ttk.Button(actions_frame, text="Select All", width=16, command=self._select_all).pack(pady=(0, 6))
        ttk.Button(actions_frame, text="Clear Selection", width=16, command=self._clear_selection).pack(pady=(0, 16))

        ttk.Label(actions_frame, text="Saved Groups", font=self.main_app.label_font).pack(anchor="w", pady=(0, 4))
        self.group_combo = ttk.Combobox(actions_frame, textvariable=self.group_selector_var, state="readonly", width=22)
        self.group_combo.pack(pady=(0, 6))
        ttk.Button(actions_frame, text="Load Group", width=16, command=self._load_selected_group).pack(pady=(0, 6))
        ttk.Button(actions_frame, text="Delete Group", width=16, command=self._delete_selected_group).pack(pady=(0, 10))

        ttk.Entry(actions_frame, textvariable=self.group_name_var, width=24).pack(pady=(0, 6))
        ttk.Button(actions_frame, text="Save Current Group", width=16, command=self._save_current_group).pack(pady=(0, 6))

        control_bar = ttk.Frame(section)
        control_bar.pack(fill=tk.X, padx=5, pady=(0, 8))
        self.start_batch_button = ttk.Button(control_bar, text="Start Batch", style="Accent.TButton", width=16, command=self.start_batch)
        self.start_batch_button.pack(side=tk.LEFT, padx=(0, 8))
        self.export_bat_button = ttk.Button(control_bar, text="Export CLI .bat", width=16, command=self.export_bat_script)
        self.export_bat_button.pack(side=tk.LEFT, padx=(0, 8))
        self.export_ps1_button = ttk.Button(control_bar, text="Export CLI .ps1", width=16, command=self.export_ps1_script)
        self.export_ps1_button.pack(side=tk.LEFT)

        data_status_lab = ttk.Labelframe(section, text="Data Status", style="Section.TLabelframe")
        data_status_lab.pack(fill=tk.X, padx=0, pady=(0, 8))

        status_row_1 = ttk.Frame(data_status_lab)
        status_row_1.pack(fill=tk.X, padx=8, pady=(6, 2))
        ttk.Label(status_row_1, text="Portal:", font=self.main_app.label_font).pack(side=tk.LEFT)
        ttk.Label(status_row_1, textvariable=self.data_status_portal_var).pack(side=tk.LEFT, padx=(4, 16))
        ttk.Label(status_row_1, text="Policy:", font=self.main_app.label_font).pack(side=tk.LEFT)
        ttk.Label(status_row_1, textvariable=self.data_policy_var).pack(side=tk.LEFT, padx=(4, 16))
        ttk.Label(status_row_1, text="Next Due:", font=self.main_app.label_font).pack(side=tk.LEFT)
        ttk.Label(status_row_1, textvariable=self.data_next_due_var).pack(side=tk.LEFT, padx=(4, 8))

        status_row_2 = ttk.Frame(data_status_lab)
        status_row_2.pack(fill=tk.X, padx=8, pady=(2, 6))
        ttk.Label(status_row_2, text="Last Full Scrape:", font=self.main_app.label_font).pack(side=tk.LEFT)
        ttk.Label(status_row_2, textvariable=self.data_last_full_var).pack(side=tk.LEFT, padx=(4, 16))
        ttk.Label(status_row_2, text="Last Excel Export:", font=self.main_app.label_font).pack(side=tk.LEFT)
        ttk.Label(status_row_2, textvariable=self.data_last_export_var).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Button(status_row_2, text="Refresh Status", width=14, command=self._refresh_data_status).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(status_row_2, text="Export Now", width=12, command=self._manual_export_now).pack(side=tk.RIGHT)

        dash_lab = ttk.Labelframe(section, text="Batch Dashboard", style="Section.TLabelframe")
        dash_lab.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0, 0))

        self.dashboard_tree = ttk.Treeview(
            dash_lab,
            columns=("portal", "state", "expected", "extracted", "skipped", "known", "current", "updated"),
            show="headings",
            height=7
        )
        for col, txt, width in [
            ("portal", "Portal", 180),
            ("state", "State", 120),
            ("expected", "Expected", 80),
            ("extracted", "Extracted", 80),
            ("skipped", "SkippedKnown", 95),
            ("known", "KnownTotal", 90),
            ("current", "Current Activity", 350),
            ("updated", "Updated", 90),
        ]:
            self.dashboard_tree.heading(col, text=txt)
            self.dashboard_tree.column(col, width=width, anchor="center")
        self.dashboard_tree.column("portal", anchor="w")
        self.dashboard_tree.column("current", anchor="w")
        self.dashboard_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 5))

        log_lab = ttk.Labelframe(section, text="Batch Logs", style="Section.TLabelframe")
        log_lab.pack(fill=tk.BOTH, expand=True, padx=0, pady=(8, 0))

        log_controls = ttk.Frame(log_lab)
        log_controls.pack(fill=tk.X, padx=5, pady=(5, 2))

        ttk.Label(log_controls, text="Portal:").pack(side=tk.LEFT, padx=(0, 4))
        self.batch_portal_filter_combo = ttk.Combobox(log_controls, textvariable=self.batch_log_filter_portal_var, state="readonly", width=24)
        self.batch_portal_filter_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.batch_portal_filter_combo.bind("<<ComboboxSelected>>", lambda _e: self._render_batch_logs())

        ttk.Label(log_controls, text="Search:").pack(side=tk.LEFT, padx=(0, 4))
        self.batch_log_search_entry = ttk.Entry(log_controls, textvariable=self.batch_log_search_var, width=30)
        self.batch_log_search_entry.pack(side=tk.LEFT, padx=(0, 8))
        self.batch_log_search_entry.bind("<KeyRelease>", lambda _e: self._render_batch_logs())

        ttk.Button(log_controls, text="Clear", width=10, command=self._clear_batch_logs).pack(side=tk.LEFT)

        self.batch_log_text = scrolledtext.ScrolledText(log_lab, height=8, wrap=tk.WORD, state=tk.DISABLED, font=self.main_app.log_font)
        self.batch_log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=(2, 5))

    def _get_all_portal_names(self):
        names = []
        for config in self.main_app.base_urls_data:
            name = str(config.get("Name", "")).strip()
            if name:
                names.append(name)
        return sorted(set(names))

    def _load_initial_data(self):
        self.portal_listbox.delete(0, END)
        for name in self._get_all_portal_names():
            self.portal_listbox.insert(END, name)

        settings = self.batch_memory.get_last_settings()
        self.mode_var.set(settings.get("mode", "sequential"))
        self.max_parallel_var.set(settings.get("max_parallel", 2))
        self.only_new_var.set(bool(settings.get("only_new", True)))
        self.scrape_scope_var.set("only_new" if self.only_new_var.get() else "all")

        raw_delta_mode = str(settings.get("delta_mode") or self.main_app.settings.get("batch_delta_mode", "quick") or "quick").strip().lower()
        if raw_delta_mode not in ("quick", "full"):
            raw_delta_mode = "quick"
        self.delta_mode_var.set(raw_delta_mode)
        try:
            self.main_app.settings["batch_delta_mode"] = raw_delta_mode
        except Exception:
            pass

        dept_workers = 1
        try:
            if hasattr(self.main_app, "department_parallel_workers_var"):
                dept_workers = max(1, min(3, int(self.main_app.department_parallel_workers_var.get() or 1)))
            else:
                dept_workers = max(1, min(3, int(self.main_app.settings.get("department_parallel_workers", 1) or 1)))
        except Exception:
            dept_workers = 1
        self.department_workers_var.set(dept_workers)
        self._sync_department_workers_setting()

        ip_safety = settings.get("ip_safety", {})
        self.per_domain_max_var.set(ip_safety.get("per_domain_max", 1))
        self.min_delay_var.set(str(ip_safety.get("min_delay_sec", 1.0)))
        self.max_delay_var.set(str(ip_safety.get("max_delay_sec", 3.0)))
        self.cooldown_var.set(ip_safety.get("cooldown_sec", 10))
        self.max_retries_var.set(ip_safety.get("max_retries", 2))

        self._restore_selection(settings.get("last_selection", []))
        self._refresh_group_combo()
        self._refresh_portal_filter_values()
        self._init_dashboard_rows(self._get_selected_portals())
        self._refresh_data_status()

    def _resolve_status_portal_name(self):
        selected = self._get_selected_portals()
        if selected:
            return str(selected[0]).strip()
        configured = str(self.main_app.settings.get("selected_url_name") or "").strip()
        if configured:
            return configured
        names = self._get_all_portal_names()
        return names[0] if names else "HP Tenders"

    def _resolve_sqlite_db_path(self):
        path = str(self.main_app.settings.get("central_sqlite_db_path") or "").strip()
        if path and not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        if not path:
            path = os.path.join(os.getcwd(), "data", "blackforest_tenders.sqlite3")
        return path

    def _get_export_policy(self):
        policy = str(self.main_app.settings.get("excel_export_policy", "on_demand") or "on_demand").strip().lower()
        if policy not in ("on_demand", "always", "alternate_days"):
            policy = "on_demand"
        try:
            interval_days = max(1, int(self.main_app.settings.get("excel_export_interval_days", 2) or 2))
        except Exception:
            interval_days = 2
        return policy, interval_days

    def _refresh_data_status(self):
        portal_name = self._resolve_status_portal_name()
        self.data_status_portal_var.set(portal_name)
        policy, interval_days = self._get_export_policy()
        policy_text = policy if policy != "alternate_days" else f"alternate_days ({interval_days}d)"
        self.data_policy_var.set(policy_text)

        try:
            db_path = self._resolve_sqlite_db_path()
            data_store = TenderDataStore(db_path)
            snapshot = data_store.get_portal_status_snapshot(portal_name=portal_name)

            last_full = str(snapshot.get("last_full_scrape_at") or "").strip()
            last_export_at = str(snapshot.get("last_excel_export_at") or "").strip()
            last_export_path = str(snapshot.get("last_excel_export_path") or "").strip()

            self.data_last_full_var.set(last_full or "-")

            if last_export_at:
                export_text = last_export_at
                if last_export_path:
                    export_text = f"{last_export_at} ({os.path.basename(last_export_path)})"
                self.data_last_export_var.set(export_text)
            else:
                self.data_last_export_var.set("-")

            if policy == "alternate_days":
                if last_export_at:
                    try:
                        next_due = datetime.fromisoformat(last_export_at) + timedelta(days=interval_days)
                        self.data_next_due_var.set(next_due.isoformat(timespec="seconds"))
                    except Exception:
                        self.data_next_due_var.set("-")
                else:
                    self.data_next_due_var.set("Now (first export)")
            else:
                self.data_next_due_var.set("On demand" if policy == "on_demand" else "Every run")
        except Exception as err:
            self.data_last_full_var.set("-")
            self.data_last_export_var.set("-")
            self.data_next_due_var.set("-")
            self.log_callback(f"Data status refresh failed: {err}")

    def _manual_export_now(self):
        portal_name = self._resolve_status_portal_name()
        portal_config = self._portal_config_by_name(portal_name)
        if not portal_config:
            gui_utils.show_message("Export Error", f"Portal config not found for '{portal_name}'.", type="error", parent=self.main_app.root)
            return

        try:
            db_path = self._resolve_sqlite_db_path()
            data_store = TenderDataStore(db_path)
            run_id = data_store.get_latest_completed_run_id(portal_name=portal_name, full_only=True)
            if not run_id:
                gui_utils.show_message("No Data", f"No completed full scrape found for '{portal_name}'.", type="warning", parent=self.main_app.root)
                return

            keyword = get_website_keyword_from_url(str(portal_config.get("BaseURL") or ""))
            output_dir = self.main_app.download_dir_var.get()
            export_path, export_type = data_store.export_run(
                run_id=run_id,
                output_dir=output_dir,
                website_keyword=keyword,
                mark_partial=False,
            )

            if not export_path:
                gui_utils.show_message("No Rows", f"No rows found to export for run {run_id}.", type="warning", parent=self.main_app.root)
                return

            self.log_callback(f"Manual export completed for '{portal_name}' | Run ID={run_id} | {str(export_type or '').upper()} | {export_path}")
            self._refresh_data_status()
            gui_utils.show_message("Export Complete", f"Exported {str(export_type or '').upper()}\n{export_path}", type="info", parent=self.main_app.root)
        except Exception as err:
            gui_utils.show_message("Export Failed", str(err), type="error", parent=self.main_app.root)

    def _sync_department_workers_setting(self):
        if getattr(self, "_syncing_dept_workers", False):
            return
        self._syncing_dept_workers = True
        try:
            value = max(1, min(3, int(self.department_workers_var.get() or 1)))
        except Exception:
            value = 1
        try:
            current = int(self.department_workers_var.get() or 1)
        except Exception:
            current = value
        if current != value:
            self.department_workers_var.set(value)

        if hasattr(self.main_app, "department_parallel_workers_var"):
            try:
                self.main_app.department_parallel_workers_var.set(str(value))
            except Exception:
                pass
        try:
            self.main_app.settings["department_parallel_workers"] = value
        except Exception:
            pass
        finally:
            self._syncing_dept_workers = False

    def _get_selected_delta_mode(self):
        mode = str(self.delta_mode_var.get() or "quick").strip().lower()
        if mode not in ("quick", "full"):
            mode = "quick"
        if str(self.delta_mode_var.get() or "").strip().lower() != mode:
            self.delta_mode_var.set(mode)
        try:
            self.main_app.settings["batch_delta_mode"] = mode
        except Exception:
            pass
        return mode

    def _portal_lock_path(self, portal_name):
        safe = sanitise_filename(str(portal_name or "").strip()) or "portal"
        return os.path.join(self._portal_lock_dir, f"{safe}.lock")

    def _is_pid_running(self, pid):
        try:
            os.kill(int(pid), 0)
            return True
        except Exception:
            return False

    def _acquire_portal_launch_lock(self, portal_name, job_id):
        lock_path = self._portal_lock_path(portal_name)
        current_pid = os.getpid()
        payload = f"pid={current_pid}\njob_id={job_id}\nportal={portal_name}\nstarted_at={datetime.now().isoformat(timespec='seconds')}\n"

        for _ in range(2):
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, payload.encode("utf-8", errors="replace"))
                finally:
                    os.close(fd)
                self._portal_launch_locks[portal_name] = lock_path
                return True
            except FileExistsError:
                try:
                    with open(lock_path, "r", encoding="utf-8", errors="replace") as handle:
                        raw = handle.read()
                    lock_pid = None
                    for line in raw.splitlines():
                        if line.startswith("pid="):
                            lock_pid = int(str(line.split("=", 1)[1]).strip())
                            break
                    if lock_pid and self._is_pid_running(lock_pid):
                        return False
                except Exception:
                    pass
                try:
                    os.remove(lock_path)
                except Exception:
                    return False
            except Exception:
                return False
        return False

    def _release_portal_launch_lock(self, portal_name):
        lock_path = self._portal_launch_locks.pop(portal_name, None) or self._portal_lock_path(portal_name)
        try:
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except Exception:
            pass

    def _load_manifest(self):
        if not os.path.exists(self.manifest_path):
            return self._bootstrap_manifest_from_outputs("missing")
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                return self._bootstrap_manifest_from_outputs("invalid-structure")
            data.setdefault("portals", {})
            if not isinstance(data.get("portals"), dict):
                return self._bootstrap_manifest_from_outputs("invalid-portals")
            return data
        except Exception:
            return self._bootstrap_manifest_from_outputs("corrupt")

    def _bootstrap_manifest_from_outputs(self, reason):
        fallback = {"portals": {}}
        imported = 0

        for config in getattr(self.main_app, "base_urls_data", []):
            portal_name = str(config.get("Name", "")).strip()
            base_url = str(config.get("BaseURL", "")).strip()
            if not portal_name or not base_url:
                continue

            latest_file = self._find_latest_output_for_portal(base_url)
            if not latest_file:
                continue

            ids, departments = self._extract_checkpoint_from_output(latest_file)
            if not ids and not departments:
                continue

            fallback["portals"][portal_name] = {
                "tender_ids": sorted(ids),
                "processed_departments": sorted(departments),
                "last_run": datetime.now().isoformat(timespec="seconds"),
                "last_expected": None,
                "last_extracted": len(ids),
                "seeded_from": latest_file,
                "seed_reason": reason
            }
            imported += 1

        if imported > 0:
            self.download_manifest = fallback
            self._save_manifest()
            self.log_callback(f"Manifest {reason}; auto-imported checkpoint for {imported} portal(s).")
        return fallback

    def _find_latest_output_for_portal(self, base_url):
        keyword = get_website_keyword_from_url(base_url)
        if not keyword:
            return None

        search_dirs = [
            os.path.join(os.getcwd(), "Tender_Downloads"),
            os.path.join(os.path.expanduser("~"), "Downloads"),
            os.getcwd(),
        ]

        candidates = []
        for base_dir in search_dirs:
            if not os.path.isdir(base_dir):
                continue
            for pattern in [f"{keyword}_tenders_*.xlsx", f"{keyword}_tenders_*.csv"]:
                candidates.extend(glob.glob(os.path.join(base_dir, pattern)))

        if not candidates:
            return None

        candidates.sort(key=lambda path: os.path.getmtime(path), reverse=True)
        return candidates[0]

    def _extract_checkpoint_from_output(self, file_path):
        tender_ids = set()
        departments = set()
        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext == ".xlsx" and pd is not None:
                df = pd.read_excel(file_path)
                columns = set(df.columns)
                id_col = "Tender ID (Extracted)" if "Tender ID (Extracted)" in columns else ("Tender ID" if "Tender ID" in columns else None)
                dept_col = "Department Name" if "Department Name" in columns else ("Department" if "Department" in columns else None)

                if id_col:
                    tender_ids.update(
                        str(value).strip()
                        for value in df[id_col].dropna().tolist()
                        if str(value).strip()
                    )
                if dept_col:
                    departments.update(
                        str(value).strip().lower()
                        for value in df[dept_col].dropna().tolist()
                        if str(value).strip()
                    )
            elif ext == ".csv":
                with open(file_path, "r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        tender_id = str(row.get("Tender ID (Extracted)") or row.get("Tender ID") or "").strip()
                        dept_name = str(row.get("Department Name") or row.get("Department") or "").strip().lower()
                        if tender_id:
                            tender_ids.add(tender_id)
                        if dept_name:
                            departments.add(dept_name)
        except Exception as error:
            self.log_callback(f"Checkpoint import failed for '{os.path.basename(file_path)}': {error}")

        return tender_ids, departments

    def _save_manifest(self):
        try:
            with open(self.manifest_path, "w", encoding="utf-8") as handle:
                json.dump(self.download_manifest, handle, indent=2, ensure_ascii=False)
        except Exception as error:
            self.log_callback(f"Failed to save batch manifest: {error}")

    def _ensure_portal_checkpoint(self, portal_name):
        portals = self.download_manifest.setdefault("portals", {})
        if portal_name in portals:
            return

        portal_config = self._portal_config_by_name(portal_name)
        if not portal_config:
            return

        base_url = str(portal_config.get("BaseURL", "")).strip()
        if not base_url:
            return

        latest_file = self._find_latest_output_for_portal(base_url)
        if not latest_file:
            return

        ids, departments = self._extract_checkpoint_from_output(latest_file)
        if not ids and not departments:
            return

        portals[portal_name] = {
            "tender_ids": sorted(ids),
            "processed_departments": sorted(departments),
            "last_run": datetime.now().isoformat(timespec="seconds"),
            "last_expected": None,
            "last_extracted": len(ids),
            "seeded_from": latest_file,
            "seed_reason": "portal-missing"
        }
        self._save_manifest()
        self.log_callback(
            f"Resume checkpoint auto-imported for '{portal_name}' from {os.path.basename(latest_file)} "
            f"(ids={len(ids)}, depts={len(departments)})."
        )

    def _get_known_ids_for_portal(self, portal_name):
        self._ensure_portal_checkpoint(portal_name)
        portal_data = self.download_manifest.get("portals", {}).get(portal_name, {})
        known_ids = set(portal_data.get("tender_ids", []))

        sqlite_known_ids = self._get_sqlite_known_ids_for_portal(portal_name)
        if sqlite_known_ids:
            added = len(sqlite_known_ids - known_ids)
            if added > 0:
                known_ids.update(sqlite_known_ids)
                portal_data["tender_ids"] = sorted(known_ids)
                portal_data["last_db_seed"] = datetime.now().isoformat(timespec="seconds")
                self._save_manifest()
                self.log_callback(
                    f"Loaded {len(sqlite_known_ids)} known IDs from SQLite for '{portal_name}' (added {added} to manifest)."
                )

        return known_ids

    def _get_sqlite_known_ids_for_portal(self, portal_name):
        db_path = None
        if hasattr(self.main_app, "_get_sqlite_runtime_settings"):
            try:
                runtime = self.main_app._get_sqlite_runtime_settings() or {}
                db_path = str(runtime.get("sqlite_db_path") or "").strip()
            except Exception:
                db_path = None

        if not db_path:
            db_path = str(getattr(self.main_app, "settings", {}).get("central_sqlite_db_path") or "").strip()

        if not db_path or not os.path.exists(db_path):
            return set()

        portal_config = self._portal_config_by_name(portal_name) or {}
        base_url = str(portal_config.get("BaseURL") or "").strip()
        keyword = str(portal_config.get("Keyword") or "").strip()

        keyword_from_url = ""
        try:
            if base_url:
                keyword_from_url = str(get_website_keyword_from_url(base_url) or "").strip()
        except Exception:
            keyword_from_url = ""

        candidates_raw = {
            str(portal_name or "").strip(),
            keyword,
            keyword_from_url,
            keyword.replace(".", "_").replace("-", "_"),
            keyword_from_url.replace(".", "_").replace("-", "_"),
        }
        portal_candidates = sorted({item.lower() for item in candidates_raw if item})
        if not portal_candidates:
            return set()

        placeholders = ",".join(["?"] * len(portal_candidates))
        query = (
            "SELECT DISTINCT trim(tender_id_extracted) "
            "FROM tenders "
            "WHERE trim(coalesce(tender_id_extracted, '')) <> '' "
            f"AND lower(trim(coalesce(portal_name, ''))) IN ({placeholders})"
        )

        try:
            conn = sqlite3.connect(db_path)
            try:
                rows = conn.execute(query, portal_candidates).fetchall()
            finally:
                conn.close()
        except Exception as error:
            self.log_callback(f"SQLite known-ID seed failed for '{portal_name}': {error}")
            return set()

        return {
            str(row[0]).strip()
            for row in rows
            if row and str(row[0]).strip()
        }

    def _get_known_departments_for_portal(self, portal_name):
        self._ensure_portal_checkpoint(portal_name)
        portal_data = self.download_manifest.get("portals", {}).get(portal_name, {})
        return {
            str(name).strip().lower()
            for name in portal_data.get("processed_departments", [])
            if str(name).strip()
        }

    def _update_manifest_for_portal(self, portal_name, summary):
        portals = self.download_manifest.setdefault("portals", {})
        portal_data = portals.setdefault(portal_name, {})
        known = set(portal_data.get("tender_ids", []))
        known.update(summary.get("extracted_tender_ids", []))
        known_departments = {
            str(name).strip().lower()
            for name in portal_data.get("processed_departments", [])
            if str(name).strip()
        }
        known_departments.update(summary.get("processed_department_names", []))

        dept_url_map = portal_data.setdefault("department_url_map", {})
        if not isinstance(dept_url_map, dict):
            dept_url_map = {}
            portal_data["department_url_map"] = dept_url_map
        for dept in summary.get("source_departments", []) or []:
            dept_name = str(dept.get("name", "")).strip()
            direct_url = str(dept.get("direct_url", "") or "").strip()
            if not dept_name or not direct_url:
                continue
            dept_key = self._normalize_department_key(dept_name)
            if not dept_key:
                continue
            dept_url_map[dept_key] = {
                "name": dept_name,
                "direct_url": direct_url,
                "last_seen": datetime.now().isoformat(timespec="seconds")
            }

        portal_data["tender_ids"] = sorted(known)
        portal_data["processed_departments"] = sorted(known_departments)
        portal_data["last_run"] = datetime.now().isoformat(timespec="seconds")
        portal_data["last_expected"] = summary.get("expected_total_tenders", 0)
        portal_data["last_extracted"] = summary.get("extracted_total_tenders", 0)
        self._save_manifest()
        return len(known)

    def _get_department_url_stats(self, portal_name):
        portal_data = self.download_manifest.get("portals", {}).get(portal_name, {})
        known_departments = {
            str(name).strip().lower()
            for name in portal_data.get("processed_departments", [])
            if str(name).strip()
        }
        known_department_keys = {
            self._normalize_department_key(name)
            for name in known_departments
            if self._normalize_department_key(name)
        }
        dept_url_map = portal_data.get("department_url_map", {})
        if not isinstance(dept_url_map, dict):
            dept_url_map = {}

        mapped_total = 0
        mapped_known = 0
        for key, row in dept_url_map.items():
            if not isinstance(row, dict):
                continue
            if str(row.get("direct_url", "") or "").strip():
                mapped_total += 1
                dept_key = self._normalize_department_key(key)
                if dept_key and dept_key in known_department_keys:
                    mapped_known += 1

        known_total = len(known_department_keys)
        coverage = int(round((mapped_known / max(1, known_total)) * 100)) if known_total > 0 else 0
        coverage = max(0, min(100, coverage))
        return {
            "known_departments": known_total,
            "mapped_departments": mapped_known,
            "mapped_total": mapped_total,
            "coverage_percent": coverage,
        }

    def _append_batch_log(self, portal_name, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        message_text = str(message)
        entry = {
            "timestamp": timestamp,
            "portal": portal_name,
            "message": message_text
        }
        self.batch_log_messages.append(entry)

        live_updates, progress_note = self._update_live_stats_from_message(portal_name, message_text)
        combined_message = message_text
        if progress_note:
            combined_message = f"{progress_note} | {message_text}"

        self._update_dashboard(
            portal_name,
            state=self._derive_state_from_message(message_text),
            extracted=live_updates.get("extracted") if live_updates else None,
            message=combined_message
        )
        self._render_batch_logs()

    def _update_live_stats_from_message(self, portal_name, message_text):
        stats = self.portal_live_stats.setdefault(
            portal_name,
            {
                "dept_total": 0,
                "dept_done": 0,
                "extracted": 0,
                "completed_departments": set(),
            }
        )

        text = str(message_text)

        processing_match = re.search(r"processing department\s+(\d+)\s*/\s*(\d+)\s*:\s*(.+)", text, flags=re.IGNORECASE)
        if processing_match:
            current_idx = int(processing_match.group(1))
            stats["dept_total"] = max(stats["dept_total"], int(processing_match.group(2)))
            stats["dept_done"] = max(stats["dept_done"], max(0, current_idx - 1))

        found_match = re.search(r"found\s+(\d+)\s+tenders?\s+in\s+department\s+(.+)", text, flags=re.IGNORECASE)
        if found_match:
            dept_name = found_match.group(2).strip().lower()
            if dept_name and dept_name not in stats["completed_departments"]:
                stats["completed_departments"].add(dept_name)
                stats["dept_done"] += 1
                stats["extracted"] += int(found_match.group(1))

        no_tenders_match = re.search(r"no tenders found/extracted from department\s+(.+)", text, flags=re.IGNORECASE)
        if no_tenders_match:
            dept_name = no_tenders_match.group(1).strip().lower()
            if dept_name and dept_name not in stats["completed_departments"]:
                stats["completed_departments"].add(dept_name)
                stats["dept_done"] += 1

        resume_skip_match = re.search(r"resume:\s+skipping already-processed department:\s+(.+)", text, flags=re.IGNORECASE)
        if resume_skip_match:
            dept_name = resume_skip_match.group(1).strip().lower()
            if dept_name and dept_name not in stats["completed_departments"]:
                stats["completed_departments"].add(dept_name)
                stats["dept_done"] += 1

        progress_note = None
        if stats["dept_total"] > 0:
            done = min(stats["dept_done"], stats["dept_total"])
            progress_note = f"Dept {done}/{stats['dept_total']} | Scraped {stats['extracted']}"

        return {"extracted": stats["extracted"]}, progress_note

    def _derive_state_from_message(self, message):
        text = str(message).lower()
        if "delta sweep" in text or "delta sweeping" in text:
            return "DeltaSweeping"
        if "error" in text or "failed" in text:
            return "Error"
        if "verification summary" in text or "output saved" in text or "completed" in text:
            return "Done"
        if "processing department" in text or "scraping details" in text or "found " in text:
            return "Scraping"
        if "fetching departments" in text or "navigating" in text:
            return "Fetching"
        if "waiting for domain slot" in text or "cooldown" in text or "ip safety delay" in text:
            return "Waiting"
        return None

    def _append_batch_log_threadsafe(self, portal_name, message):
        self.main_app.root.after(0, self._append_batch_log, portal_name, message)

    def _clear_batch_logs(self):
        self.batch_log_messages = []
        self._render_batch_logs()

    def _render_batch_logs(self):
        portal_filter = self.batch_log_filter_portal_var.get().strip()
        search_term = self.batch_log_search_var.get().strip().lower()

        self.batch_log_text.config(state=tk.NORMAL)
        self.batch_log_text.delete("1.0", tk.END)

        for entry in self.batch_log_messages:
            if portal_filter and portal_filter != "All" and entry["portal"] != portal_filter:
                continue
            line = f"[{entry['timestamp']}][{entry['portal']}] {entry['message']}"
            if search_term and search_term not in line.lower():
                continue
            gui_utils.append_styled_log_line(self.batch_log_text, line)

        self.batch_log_text.see(tk.END)
        self.batch_log_text.config(state=tk.DISABLED)

    def _refresh_portal_filter_values(self):
        values = ["All"] + self._get_all_portal_names()
        self.batch_portal_filter_combo["values"] = values
        if self.batch_log_filter_portal_var.get() not in values:
            self.batch_log_filter_portal_var.set("All")

    def _init_dashboard_rows(self, selected_portals):
        existing_items = self.dashboard_tree.get_children()
        for item in existing_items:
            self.dashboard_tree.delete(item)
        self.portal_dashboard_rows = {}
        self.portal_live_stats = {}

        if hasattr(self.main_app, "reset_logs_portal_monitor"):
            try:
                self.main_app.reset_logs_portal_monitor(selected_portals)
            except Exception:
                pass

        for portal in selected_portals:
            known_total = len(self._get_known_ids_for_portal(portal))
            item_id = self.dashboard_tree.insert(
                "", tk.END,
                values=(portal, "Idle", 0, 0, 0, known_total, "Waiting to start...", "--:--:--")
            )
            self.portal_dashboard_rows[portal] = item_id

        self._push_global_progress(state="Starting" if selected_portals else "Ready")

    def _update_dashboard(self, portal, state=None, expected=None, extracted=None, skipped=None, known=None, message=None):
        with self._dashboard_lock:
            item_id = self.portal_dashboard_rows.get(portal)
            if not item_id:
                known_total = len(self._get_known_ids_for_portal(portal))
                item_id = self.dashboard_tree.insert("", tk.END, values=(portal, "Idle", 0, 0, 0, known_total, "Waiting to start...", "--:--:--"))
                self.portal_dashboard_rows[portal] = item_id

            current = list(self.dashboard_tree.item(item_id, "values"))
            if not current:
                current = [portal, "Idle", 0, 0, 0, 0, "Waiting to start...", "--:--:--"]

            if state is not None:
                current[1] = state
            if expected is not None:
                current[2] = expected
            if extracted is not None:
                current[3] = extracted
            if skipped is not None:
                current[4] = skipped
            if known is not None:
                current[5] = known
            if message is not None:
                condensed = str(message).replace("\n", " ").strip()
                current[6] = condensed[:340]

            current[7] = datetime.now().strftime("%H:%M:%S")
            self.dashboard_tree.item(item_id, values=current)

            if hasattr(self.main_app, "update_logs_portal_monitor"):
                try:
                    self.main_app.update_logs_portal_monitor(
                        portal=portal,
                        state=current[1],
                        expected=current[2],
                        extracted=current[3],
                        skipped=current[4],
                        known=current[5],
                        current=current[6],
                        updated=current[7]
                    )
                except Exception:
                    pass

            self._push_global_progress(active_portal=portal)

    def _update_dashboard_threadsafe(self, portal, **kwargs):
        self.main_app.root.after(
            0,
            self._update_dashboard,
            portal,
            kwargs.get("state"),
            kwargs.get("expected"),
            kwargs.get("extracted"),
            kwargs.get("skipped"),
            kwargs.get("known"),
            kwargs.get("message")
        )

    def _safe_int(self, value):
        try:
            return int(value)
        except Exception:
            try:
                return int(float(value))
            except Exception:
                return 0

    def _collect_global_metrics(self):
        total_portals = len(self.portal_dashboard_rows)
        completed_portals = 0
        active_portals = 0
        total_tenders = 0
        scraped_tenders = 0
        skipped_tenders = 0
        active_names = []

        terminal_states = {"done", "error", "nodata"}
        active_states = {"scraping", "fetching", "waiting", "starting"}

        for portal_name, item_id in self.portal_dashboard_rows.items():
            values = list(self.dashboard_tree.item(item_id, "values"))
            if not values:
                continue

            state = str(values[1]).strip().lower()
            expected = self._safe_int(values[2])
            extracted = self._safe_int(values[3])
            skipped = self._safe_int(values[4])

            total_tenders += max(0, expected)
            scraped_tenders += max(0, extracted)
            skipped_tenders += max(0, skipped)

            if state in terminal_states:
                completed_portals += 1
            if state in active_states:
                active_portals += 1
                active_names.append(portal_name)

        total_departments = 0
        scraped_departments = 0
        for stats in self.portal_live_stats.values():
            dept_total = max(0, self._safe_int(stats.get("dept_total", 0)))
            dept_done = max(0, self._safe_int(stats.get("dept_done", 0)))
            total_departments += dept_total
            scraped_departments += min(dept_done, dept_total) if dept_total > 0 else dept_done

        if active_names:
            active_portal_text = ", ".join(active_names[:2]) + (" ..." if len(active_names) > 2 else "")
        else:
            active_portal_text = "-"

        return {
            "total_portals": total_portals,
            "completed_portals": completed_portals,
            "active_portals": active_portals,
            "total_tenders": total_tenders,
            "scraped_tenders": scraped_tenders,
            "skipped_tenders": skipped_tenders,
            "total_departments": total_departments,
            "scraped_departments": scraped_departments,
            "active_portal_text": active_portal_text,
        }

    def _push_global_progress(self, state=None, active_portal=None):
        if not hasattr(self.main_app, "update_global_progress"):
            return

        metrics = self._collect_global_metrics()
        total_portals = metrics["total_portals"]
        completed_portals = metrics["completed_portals"]
        active_portals = metrics["active_portals"]

        if state is None:
            if total_portals == 0:
                state = "Ready"
            elif completed_portals >= total_portals:
                state = "Completed"
            elif active_portals > 0:
                state = "Running"
            else:
                state = "Starting"

        active_portal_value = active_portal or metrics["active_portal_text"]
        self.main_app.update_global_progress(
            active_portals=active_portals,
            completed_portals=completed_portals,
            total_portals=total_portals,
            total_tenders=metrics["total_tenders"],
            scraped_tenders=metrics["scraped_tenders"],
            skipped_tenders=metrics["skipped_tenders"],
            total_departments=metrics["total_departments"],
            scraped_departments=metrics["scraped_departments"],
            active_portal=active_portal_value,
            state=state,
        )

    def _get_ip_safety_settings(self):
        try:
            per_domain_max = max(1, int(self.per_domain_max_var.get() or 1))
        except Exception:
            per_domain_max = 1

        try:
            min_delay = max(0.0, float(self.min_delay_var.get() or 0.0))
        except Exception:
            min_delay = 1.0

        try:
            max_delay = max(min_delay, float(self.max_delay_var.get() or min_delay))
        except Exception:
            max_delay = max(min_delay, 3.0)

        try:
            cooldown = max(0, int(self.cooldown_var.get() or 0))
        except Exception:
            cooldown = 10

        try:
            retries = max(0, int(self.max_retries_var.get() or 0))
        except Exception:
            retries = 2

        return {
            "per_domain_max": per_domain_max,
            "min_delay_sec": min_delay,
            "max_delay_sec": max_delay,
            "cooldown_sec": cooldown,
            "max_retries": retries,
        }

    def _is_probable_block(self, error):
        text = str(error).lower()
        patterns = ["429", "503", "too many requests", "rate limit", "temporarily blocked", "captcha"]
        return any(pattern in text for pattern in patterns)

    def _domain_from_config(self, portal_config):
        base_url = str(portal_config.get("BaseURL", "")).strip()
        if not base_url:
            return "unknown"
        parsed = urlparse(base_url)
        return parsed.netloc.lower() or "unknown"

    def _restore_selection(self, portal_names):
        wanted = set(portal_names or [])
        self.portal_listbox.selection_clear(0, END)
        for idx in range(self.portal_listbox.size()):
            if self.portal_listbox.get(idx) in wanted:
                self.portal_listbox.selection_set(idx)

    def _refresh_group_combo(self):
        groups = sorted(self.batch_memory.get_groups().keys())
        self.group_combo["values"] = groups
        if groups and self.group_selector_var.get() not in groups:
            self.group_selector_var.set(groups[0])
        if not groups:
            self.group_selector_var.set("")

    def _select_all(self):
        self.portal_listbox.selection_set(0, END)
        self._init_dashboard_rows(self._get_selected_portals())

    def _clear_selection(self):
        self.portal_listbox.selection_clear(0, END)
        self._init_dashboard_rows([])

    def _get_selected_portals(self):
        return [self.portal_listbox.get(index) for index in self.portal_listbox.curselection()]

    def _save_current_group(self):
        group_name = self.group_name_var.get().strip()
        selected = self._get_selected_portals()
        if not group_name:
            gui_utils.show_message("Missing Name", "Enter a group name first.", type="warning", parent=self.main_app.root)
            return
        if not selected:
            gui_utils.show_message("No Selection", "Select one or more portals to save as a group.", type="warning", parent=self.main_app.root)
            return
        if self.batch_memory.save_group(group_name, selected):
            self._refresh_group_combo()
            self.group_selector_var.set(group_name)
            self.log_callback(f"Saved group '{group_name}' with {len(selected)} portal(s).")
        else:
            gui_utils.show_message("Save Error", "Failed to save group.", type="error", parent=self.main_app.root)

    def _load_selected_group(self):
        group_name = self.group_selector_var.get().strip()
        if not group_name:
            gui_utils.show_message("No Group", "Select a saved group first.", type="warning", parent=self.main_app.root)
            return
        groups = self.batch_memory.get_groups()
        selected = groups.get(group_name, [])
        self._restore_selection(selected)
        self._init_dashboard_rows(selected)
        self.log_callback(f"Loaded group '{group_name}'.")

    def _delete_selected_group(self):
        group_name = self.group_selector_var.get().strip()
        if not group_name:
            gui_utils.show_message("No Group", "Select a saved group first.", type="warning", parent=self.main_app.root)
            return
        if not gui_utils.show_message("Confirm Delete", f"Delete group '{group_name}'?", type="askyesno", parent=self.main_app.root):
            return
        if self.batch_memory.delete_group(group_name):
            self._refresh_group_combo()
            self.log_callback(f"Deleted group '{group_name}'.")
        else:
            gui_utils.show_message("Delete Error", "Failed to delete group.", type="error", parent=self.main_app.root)

    def _portal_config_by_name(self, portal_name):
        for config in self.main_app.base_urls_data:
            if str(config.get("Name", "")).strip() == portal_name:
                selected = config.copy()
                base_url = selected.get("BaseURL", "")
                if not selected.get("OrgListURL") and base_url:
                    selected["OrgListURL"] = f"{base_url}?page=FrontEndTendersByOrganisation&service=page"
                return selected
        return None

    def _build_cli_commands(self, selected_portals):
        return [f'python cli_main.py --url "{portal_name}" department --all' for portal_name in selected_portals]

    def _build_bat_content(self, selected_portals):
        commands = self._build_cli_commands(selected_portals)
        mode = self.mode_var.get()

        lines = ["@echo off", "setlocal", "cd /d %~dp0", ""]
        if mode == "parallel":
            lines.append("echo Starting batch in parallel mode...")
            for command in commands:
                lines.append(f"start \"BlackForest CLI\" cmd /c \"{command}\"")
            lines.append("echo Parallel jobs launched.")
        else:
            lines.append("echo Starting batch in sequential mode...")
            for command in commands:
                lines.append(command)
                lines.append("if %ERRORLEVEL% NEQ 0 echo Command failed with exit code %ERRORLEVEL%")
            lines.append("echo Sequential batch completed.")

        lines.extend(["", "endlocal", "pause"])
        return "\n".join(lines)

    def _build_ps1_content(self, selected_portals):
        commands = self._build_cli_commands(selected_portals)
        mode = self.mode_var.get()

        lines = [
            "$ErrorActionPreference = 'Continue'",
            "$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path",
            "Set-Location $scriptRoot",
            ""
        ]

        if mode == "parallel":
            lines.append("Write-Host 'Starting batch in parallel mode...' -ForegroundColor Cyan")
            lines.append("$jobs = @()")
            for command in commands:
                escaped = command.replace("'", "''")
                lines.append(f"$jobs += Start-Job -ScriptBlock {{ cmd /c '{escaped}' }}")
            lines.append("if ($jobs.Count -gt 0) { $jobs | Wait-Job | Out-Null; $jobs | Receive-Job; $jobs | Remove-Job }")
            lines.append("Write-Host 'Parallel batch completed.' -ForegroundColor Green")
        else:
            lines.append("Write-Host 'Starting batch in sequential mode...' -ForegroundColor Cyan")
            for command in commands:
                escaped = command.replace("`", "``")
                lines.append(f"Write-Host 'Running: {command}'")
                lines.append(f"cmd /c \"{escaped}\"")
                lines.append("if ($LASTEXITCODE -ne 0) { Write-Warning \"Command failed with exit code $LASTEXITCODE\" }")
            lines.append("Write-Host 'Sequential batch completed.' -ForegroundColor Green")

        return "\n".join(lines)

    def export_bat_script(self):
        selected_portals = self._get_selected_portals()
        if not selected_portals:
            gui_utils.show_message("No Selection", "Select one or more portals before exporting.", type="warning", parent=self.main_app.root)
            return

        default_name = "batch_scrape_parallel.bat" if self.mode_var.get() == "parallel" else "batch_scrape_sequential.bat"
        save_path = filedialog.asksaveasfilename(parent=self.main_app.root, title="Save CLI Batch Script", initialfile=default_name, defaultextension=".bat", filetypes=[("Batch Files", "*.bat"), ("All Files", "*.*")])
        if not save_path:
            return

        with open(save_path, "w", encoding="utf-8") as script_handle:
            script_handle.write(self._build_bat_content(selected_portals))
        self.log_callback(f"Exported CLI batch script: {save_path}")

    def export_ps1_script(self):
        selected_portals = self._get_selected_portals()
        if not selected_portals:
            gui_utils.show_message("No Selection", "Select one or more portals before exporting.", type="warning", parent=self.main_app.root)
            return

        default_name = "batch_scrape_parallel.ps1" if self.mode_var.get() == "parallel" else "batch_scrape_sequential.ps1"
        save_path = filedialog.asksaveasfilename(parent=self.main_app.root, title="Save PowerShell Script", initialfile=default_name, defaultextension=".ps1", filetypes=[("PowerShell", "*.ps1"), ("All Files", "*.*")])
        if not save_path:
            return

        with open(save_path, "w", encoding="utf-8") as script_handle:
            script_handle.write(self._build_ps1_content(selected_portals))
        self.log_callback(f"Exported PowerShell batch script: {save_path}")

    def start_batch(self):
        selected_portals = self._get_selected_portals()
        mode = self.mode_var.get()
        only_new = self.scrape_scope_var.get() == "only_new"
        max_parallel = max(1, int(self.max_parallel_var.get() or 1))
        self._start_batch_execution(
            selected_portals=selected_portals,
            mode=mode,
            only_new=only_new,
            max_parallel=max_parallel,
            confirm=True,
            reason="manual"
        )

    def start_batch_for_portals(self, portal_names, only_new=False, mode="sequential", max_parallel=1, reason="auto-watch"):
        selected_portals = [str(name).strip() for name in (portal_names or []) if str(name).strip()]
        return self._start_batch_execution(
            selected_portals=selected_portals,
            mode=mode,
            only_new=bool(only_new),
            max_parallel=max_parallel,
            confirm=False,
            reason=reason
        )

    def _start_batch_execution(self, selected_portals, mode, only_new, max_parallel, confirm=True, reason="manual"):
        if self.main_app.scraping_in_progress:
            if confirm:
                gui_utils.show_message("Busy", "Another process is currently running.", type="warning", parent=self.main_app.root)
            else:
                self.log_callback("Auto-run skipped: another process is currently running.")
            return False

        if not selected_portals:
            if confirm:
                gui_utils.show_message("No Selection", "Select one or more portals first.", type="warning", parent=self.main_app.root)
            else:
                self.log_callback("Auto-run skipped: no portals selected.")
            return False

        self._init_dashboard_rows(selected_portals)
        self._refresh_portal_filter_values()

        download_dir = self.main_app.download_dir_var.get()
        if not self.main_app.validate_download_dir(download_dir):
            return False

        mode = "parallel" if str(mode).lower() == "parallel" else "sequential"
        max_parallel = max(1, int(max_parallel or 1))
        if mode == "parallel":
            max_parallel = min(max_parallel, len(selected_portals), 4)

        ip_safety = self._get_ip_safety_settings()

        delta_mode = self._get_selected_delta_mode()

        if confirm:
            if not gui_utils.show_message(
                "Confirm Batch",
                f"Start batch scrape for {len(selected_portals)} portal(s)?\n"
                f"Mode: {mode.title()}\n"
                f"Scope: {'Only New' if only_new else 'All'}\n"
            f"Delta Mode: {delta_mode.title()}\n"
                f"Max Parallel: {max_parallel}\n"
                f"Per-Domain: {ip_safety['per_domain_max']}\n"
                f"Delay: {ip_safety['min_delay_sec']}s to {ip_safety['max_delay_sec']}s\n"
                f"Cooldown: {ip_safety['cooldown_sec']}s\n"
                f"Retries: {ip_safety['max_retries']}",
                type="askyesno",
                parent=self.main_app.root
            ):
                return False

        self.only_new_var.set(bool(only_new))
        self.current_batch_delta_mode = delta_mode
        self.batch_memory.save_last_settings(selected_portals, mode, max_parallel, ip_safety, only_new, delta_mode=delta_mode)

        self.main_app.total_estimated_tenders_for_run = len(selected_portals)
        self.main_app.reset_progress_and_timer()
        self.main_app.update_status(f"Starting batch ({mode})...")
        if hasattr(self.main_app, "set_status_context"):
            try:
                self.main_app.set_status_context(
                    run_type="Batch",
                    mode=mode.title(),
                    scope="Only New" if only_new else "All",
                    active_portal="-",
                    completed_portals=0,
                    total_portals=len(selected_portals),
                    state="Starting"
                )
            except Exception:
                pass
        self._push_global_progress(state="Starting", active_portal="-")
        self.log_callback(
            f"Starting batch scrape for {len(selected_portals)} portal(s) in {mode} mode "
            f"(scope={'Only New' if only_new else 'All'}, delta={delta_mode.title()}, reason={reason})."
        )

        use_subprocess = bool(hasattr(self.main_app, "start_supervised_cli_job"))
        if use_subprocess:
            self._start_batch_subprocess_execution(
                selected_portals=selected_portals,
                download_dir=download_dir,
                mode=mode,
                max_parallel=max_parallel,
                only_new=only_new,
                delta_mode=delta_mode,
            )
        else:
            self.main_app.start_background_task(
                self._run_batch_worker,
                args=(selected_portals, download_dir, mode, max_parallel, ip_safety, only_new),
                task_name="Batch Scrape"
            )
        return True

    def _start_batch_subprocess_execution(self, selected_portals, download_dir, mode, max_parallel, only_new=False, delta_mode="quick"):
        self._prepare_batch_report_dir()
        self._batch_use_subprocess = True
        ordered_unique = list(dict.fromkeys([str(portal).strip() for portal in (selected_portals or []) if str(portal).strip()]))
        self._batch_pending_portals = ordered_unique
        self._batch_active_jobs = {}
        self._batch_completed_count = 0
        self._batch_total_count = len(ordered_unique)
        self._batch_max_parallel = 1 if str(mode).lower() != "parallel" else max(1, int(max_parallel or 1))
        self._batch_only_new = bool(only_new)
        self._batch_delta_mode = str(delta_mode or "quick").strip().lower()

        self.main_app.stop_event.clear()
        self.main_app.scraping_in_progress = True
        self.main_app.set_controls_state(tk.DISABLED)
        self.main_app.start_timer_updates()

        self.main_app.update_status(f"Starting batch subprocesses ({mode})...")
        self.main_app.update_log(
            f"Batch subprocess supervisor active: portals={self._batch_total_count}, max_parallel={self._batch_max_parallel}"
        )

        self._launch_next_batch_jobs(download_dir, only_new=self._batch_only_new, delta_mode=self._batch_delta_mode)

    def _launch_next_batch_jobs(self, download_dir, only_new=False, delta_mode="quick"):
        with self._batch_lock:
            while (
                len(self._batch_active_jobs) < self._batch_max_parallel
                and self._batch_pending_portals
                and not self.main_app.stop_event.is_set()
            ):
                portal_name = self._batch_pending_portals.pop(0)
                try:
                    dept_workers = max(1, min(3, int(self.department_workers_var.get() or 1)))
                except Exception:
                    dept_workers = 1

                job_id = self.main_app.process_supervisor.create_job_id(prefix="batch")
                if not self._acquire_portal_launch_lock(portal_name, job_id):
                    self._append_batch_log_threadsafe(portal_name, "[GUARD] Skipped duplicate launch: portal already active in another app/job")
                    self._update_dashboard_threadsafe(portal_name, state="Skipped", message="Duplicate launch blocked")
                    self._batch_completed_count += 1
                    continue

                cli_log_path = self._build_portal_cli_log_path(portal_name)
                command = self._build_portal_job_command(
                    portal_name=portal_name,
                    download_dir=download_dir,
                    dept_workers=dept_workers,
                    job_id=job_id,
                    log_path=cli_log_path,
                    only_new=only_new,
                    delta_mode=delta_mode,
                )

                self._batch_active_jobs[portal_name] = {
                    "job_id": job_id,
                    "download_dir": download_dir,
                    "log_path": cli_log_path,
                    "started_at": datetime.now().isoformat(timespec="seconds"),
                }
                self._batch_job_ids.add(job_id)
                self._update_dashboard_threadsafe(portal_name, state="Starting", message="Launching CLI subprocess...")

                try:
                    self.main_app.start_supervised_cli_job(
                        job_id=job_id,
                        command=command,
                        cwd=os.getcwd(),
                        group="batch",
                        tail_log_file=cli_log_path,
                        on_log=lambda message, portal=portal_name: self._on_batch_job_log(portal, message),
                        on_event=lambda event, portal=portal_name: self._on_batch_job_event(portal, event),
                        on_state_change=lambda jid, state, reason=None, portal=portal_name: self._on_batch_job_state_change(portal, jid, state, reason),
                        on_exit=lambda exit_code, portal=portal_name, jid=job_id: self._on_batch_job_exit(portal, jid, exit_code),
                        on_error=lambda message, portal=portal_name: self._on_batch_job_stderr(portal, message),
                    )
                except Exception as launch_err:
                    self._release_portal_launch_lock(portal_name)
                    self._batch_active_jobs.pop(portal_name, None)
                    self._append_batch_log_threadsafe(portal_name, f"[GUARD] Launch failed: {launch_err}")
                    self._update_dashboard_threadsafe(portal_name, state="Error", message="Launch failed")
                    self._batch_completed_count += 1

    def _on_batch_job_log(self, portal_name, message):
        self._append_batch_log_threadsafe(portal_name, str(message))

    def _on_batch_job_stderr(self, portal_name, message):
        self._append_batch_log_threadsafe(portal_name, f"[STDERR] {message}")

    def _on_batch_job_state_change(self, portal_name, job_id, state, reason=None):
        def _apply():
            state_text = str(state or "").lower()
            if state_text == "running":
                self._update_dashboard_threadsafe(portal_name, state="Running")
            elif state_text == "stopping":
                self._update_dashboard_threadsafe(portal_name, state="Stopping", message="Stop requested")
            elif state_text == "cancelled":
                self._update_dashboard_threadsafe(portal_name, state="Stopped", message="Cancelled")
            elif state_text == "failed":
                self._update_dashboard_threadsafe(portal_name, state="Error", message=f"Failed ({reason or 'unknown'})")
        self.main_app.root.after(0, _apply)

    def _on_batch_job_event(self, portal_name, event):
        def _apply():
            event_type = str((event or {}).get("type", "")).strip().lower()
            if not event_type:
                return

            if event_type == "status":
                message = str(event.get("message", "")).strip()
                if message:
                    derived = self._derive_state_from_message(message) or "Running"
                    self._append_batch_log_threadsafe(portal_name, f"[STATUS] {message}")
                    self._update_dashboard_threadsafe(portal_name, state=derived, message=message)
                return

            if event_type == "departments_loaded":
                expected_total = int(event.get("estimated_total_tenders", 0) or 0)
                total_depts = int(event.get("total_departments", 0) or 0)
                portal_stats = self.portal_live_stats.setdefault(portal_name, {
                    "dept_total": 0,
                    "dept_done": 0,
                    "extracted": 0,
                    "completed_departments": set(),
                })
                portal_stats["dept_total"] = max(0, total_depts)
                self._update_dashboard_threadsafe(
                    portal_name,
                    state="Fetching",
                    expected=max(0, expected_total),
                    message=f"Departments loaded: {total_depts}",
                )
                self._push_global_progress(state="Running", active_portal=portal_name)
                return

            if event_type == "progress":
                current = int(event.get("current", 0) or 0)
                total = int(event.get("total", 0) or 0)
                scraped_tenders = int(event.get("scraped_tenders", 0) or 0)
                details = str(event.get("details", "") or "").strip()

                portal_stats = self.portal_live_stats.setdefault(portal_name, {
                    "dept_total": 0,
                    "dept_done": 0,
                    "extracted": 0,
                    "completed_departments": set(),
                })
                portal_stats["dept_total"] = max(portal_stats.get("dept_total", 0), total)
                portal_stats["dept_done"] = max(portal_stats.get("dept_done", 0), current)
                portal_stats["extracted"] = max(portal_stats.get("extracted", 0), scraped_tenders)

                self._update_dashboard_threadsafe(
                    portal_name,
                    state="Scraping",
                    extracted=scraped_tenders,
                    message=details or f"Dept {current}/{total}",
                )
                self._push_global_progress(state="Running", active_portal=portal_name)
                return

            if event_type == "completed":
                elapsed = event.get("elapsed_seconds", 0)
                expected = int(event.get("expected_total_tenders", 0) or 0)
                extracted = int(event.get("extracted_total_tenders", 0) or 0)
                skipped = int(event.get("skipped_existing_total", 0) or 0)
                known_total = int(event.get("known_total", 0) or 0)
                output_file = str(event.get("output_file_path", "") or "").strip()
                output_type = str(event.get("output_file_type", "") or "").strip()
                sqlite_path = str(event.get("sqlite_db_path", "") or "").strip()
                sqlite_run_id = event.get("sqlite_run_id")
                status_msg = f"Completed in {elapsed}s"
                if output_file:
                    status_msg = f"{status_msg} | Output: {os.path.basename(output_file)}"
                self._update_dashboard_threadsafe(
                    portal_name,
                    state="Done",
                    expected=expected,
                    extracted=extracted,
                    skipped=skipped,
                    known=known_total if known_total > 0 else None,
                    message=status_msg,
                )
                report = {
                    "portal": portal_name,
                    "started_at": datetime.now().isoformat(timespec="seconds"),
                    "completed_at": datetime.now().isoformat(timespec="seconds"),
                    "duration_sec": float(elapsed or 0),
                    "status": "Scraping completed",
                    "attempted_departments": int(event.get("total_departments", 0) or 0),
                    "processed_departments": int(event.get("processed_departments", 0) or 0),
                    "resume_skipped_departments": 0,
                    "expected_tenders": expected,
                    "extracted_tenders": extracted,
                    "skipped_known_tenders": skipped,
                    "output_file_path": output_file,
                    "output_file_type": output_type,
                    "sqlite_db_path": sqlite_path,
                    "sqlite_run_id": sqlite_run_id,
                    "partial_saved": bool(event.get("partial_saved", False)),
                    "delta_sweep_enabled": bool(event.get("only_new", False)),
                    "delta_mode": str(event.get("delta_mode", "") or ""),
                    "delta_sweep_extracted": 0,
                    "delta_quick_stats": {},
                    "department_url_tracker": self._get_department_url_stats(portal_name),
                    "error_count": 0,
                    "errors": [],
                }
                try:
                    json_report_path, csv_report_path = self._write_portal_report(portal_name, report)
                    self._append_batch_log_threadsafe(portal_name, f"Run report saved (JSON): {json_report_path}")
                    self._append_batch_log_threadsafe(portal_name, f"Run report saved (CSV): {csv_report_path}")
                except Exception as report_err:
                    self._append_batch_log_threadsafe(portal_name, f"Report write failed: {report_err}")
                self._push_global_progress(state="Running", active_portal=portal_name)
                return

            if event_type == "error":
                message = str(event.get("message", "Unknown error"))
                self._update_dashboard_threadsafe(portal_name, state="Error", message=message)
                self._append_batch_log_threadsafe(portal_name, f"[ERROR] {message}")

        self.main_app.root.after(0, _apply)

    def _on_batch_job_exit(self, portal_name, job_id, exit_code):
        def _finish_one():
            self._release_portal_launch_lock(portal_name)
            with self._batch_lock:
                self._batch_active_jobs.pop(portal_name, None)
                self._batch_completed_count += 1

            if int(exit_code) == 0:
                self._update_dashboard_threadsafe(portal_name, state="Done")
            else:
                if self.main_app.stop_event.is_set():
                    self._update_dashboard_threadsafe(portal_name, state="Stopped")
                else:
                    self._update_dashboard_threadsafe(portal_name, state="Error", message=f"CLI exit {exit_code}")

            try:
                self.main_app.set_status_context(
                    completed_portals=self._batch_completed_count,
                    total_portals=self._batch_total_count,
                    active_portal=portal_name,
                    state="Running" if self._batch_completed_count < self._batch_total_count else "Completed"
                )
            except Exception:
                pass

            if not self.main_app.stop_event.is_set():
                download_dir = self.main_app.download_dir_var.get()
                self._launch_next_batch_jobs(
                    download_dir,
                    only_new=getattr(self, "_batch_only_new", False),
                    delta_mode=getattr(self, "_batch_delta_mode", "quick"),
                )

            with self._batch_lock:
                has_pending = bool(self._batch_pending_portals)
                has_active = bool(self._batch_active_jobs)

            if not has_pending and not has_active:
                self._finish_batch_subprocess_execution()

        self.main_app.root.after(0, _finish_one)

    def _finish_batch_subprocess_execution(self):
        stopped = bool(self.main_app.stop_event.is_set())
        self._push_global_progress(state="Stopped" if stopped else "Completed", active_portal="-")

        self.main_app.scraping_in_progress = False
        self.main_app.stop_timer_updates()
        self.main_app.set_controls_state(tk.NORMAL)
        self.main_app.update_status("Batch scraping stopped by user" if stopped else "Batch scraping completed")

        try:
            self.main_app.set_status_context(
                state="Stopped" if stopped else "Completed",
                completed_portals=self._batch_completed_count,
                total_portals=self._batch_total_count,
                active_portal="-",
            )
        except Exception:
            pass

        self._batch_use_subprocess = False
        self._batch_pending_portals = []
        self._batch_active_jobs = {}
        self._batch_job_ids.clear()
        for portal_name in list(self._portal_launch_locks.keys()):
            self._release_portal_launch_lock(portal_name)

        try:
            self._export_department_url_coverage_report(log_callback=self.log_callback)
        except Exception:
            pass
        if self.current_batch_report_dir:
            self.log_callback(f"Batch run reports saved in: {self.current_batch_report_dir}")

        self._refresh_data_status()

    def _build_portal_logger(self, portal_name, log_callback):
        def _portal_log(message):
            msg = str(message)
            log_callback(f"[{portal_name}] {msg}")
            self._append_batch_log_threadsafe(portal_name, msg)
        return _portal_log

    def _attach_sink_to_logger(self, base_logger, sink, touch_callback=None):

        def _portal_log(message):
            msg = str(message)
            sink.append(msg)
            if touch_callback:
                touch_callback()
            base_logger(msg)

        return _portal_log

    def _start_portal_watchdog(self, portal_name, portal_log, stop_event, inactivity_state, watchdog_trigger):
        done_event = threading.Event()

        def _watchdog_loop():
            while not done_event.is_set():
                if stop_event and stop_event.is_set():
                    return
                now_mono = time.monotonic()
                now_wall = time.time()

                last_mono = inactivity_state.get("last_mono", now_mono)
                last_wall = inactivity_state.get("last_wall", now_wall)

                if (now_wall - last_wall) >= self.portal_watchdog_sleep_jump_sec:
                    portal_log(f"Watchdog: sleep/network pause detected for {portal_name}; requesting auto-recovery.")
                    watchdog_trigger.set()
                    return

                if (now_mono - last_mono) >= self.portal_watchdog_inactivity_sec:
                    portal_log(f"Watchdog: no activity for {self.portal_watchdog_inactivity_sec}s; requesting auto-recovery.")
                    watchdog_trigger.set()
                    return

                self._interruptible_sleep(10, stop_event=stop_event)

        thread = threading.Thread(target=_watchdog_loop, daemon=True)
        thread.start()
        return done_event, thread

    def _is_recoverable_portal_error(self, text):
        payload = str(text or "").lower()
        patterns = [
            "session",
            "invalid session",
            "timeout",
            "connection",
            "disconnected",
            "net::",
            "chrome not reachable",
            "target window already closed",
            "unable to discover open pages",
        ]
        return any(pattern in payload for pattern in patterns)

    def _normalize_department_key(self, value):
        text = str(value or "").strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text

    def _build_valid_departments(self, departments):
        valid_departments = []
        expected_total = 0
        for dept in departments or []:
            s_no = str(dept.get("s_no", "")).strip().lower()
            dept_name = str(dept.get("name", "")).strip().lower()
            count_text = str(dept.get("count_text", "")).strip()
            if s_no.isdigit() and dept_name not in ["organisation name", "department name", "organization", "organization name"]:
                valid_departments.append(dept)
                if count_text.isdigit():
                    expected_total += int(count_text)
        return valid_departments, expected_total

    def _build_department_snapshot(self, departments):
        snapshot = {}
        for dept in departments or []:
            name = str(dept.get("name", "")).strip()
            key = self._normalize_department_key(name)
            if not key:
                continue
            count_text = str(dept.get("count_text", "")).strip()
            try:
                count_val = int(count_text) if count_text.isdigit() else 0
            except Exception:
                count_val = 0
            snapshot[key] = {
                "name": name,
                "count": max(0, count_val),
                "department": dept,
            }
        return snapshot

    def _plan_quick_delta_departments(self, baseline_departments, latest_departments, portal_log):
        baseline_snapshot = self._build_department_snapshot(baseline_departments)
        latest_snapshot = self._build_department_snapshot(latest_departments)

        baseline_keys = set(baseline_snapshot.keys())
        latest_keys = set(latest_snapshot.keys())

        added_keys = sorted(latest_keys - baseline_keys)
        removed_keys = sorted(baseline_keys - latest_keys)
        common_keys = sorted(latest_keys.intersection(baseline_keys))

        changed_keys = []
        unchanged_count = 0
        count_changed = 0

        for key in common_keys:
            old_count = int(baseline_snapshot[key].get("count", 0))
            new_count = int(latest_snapshot[key].get("count", 0))
            if old_count != new_count:
                changed_keys.append(key)
                count_changed += 1
                portal_log(
                    f"Quick delta candidate: {latest_snapshot[key].get('name', key)} count changed {old_count}->{new_count}"
                )
            else:
                unchanged_count += 1

        for key in added_keys:
            changed_keys.append(key)
            portal_log(
                f"Quick delta candidate: NEW department {latest_snapshot[key].get('name', key)} count={latest_snapshot[key].get('count', 0)}"
            )

        for key in removed_keys:
            portal_log(
                f"Quick delta notice: Department missing now {baseline_snapshot[key].get('name', key)} "
                f"(previous count={baseline_snapshot[key].get('count', 0)})"
            )

        seen = set()
        delta_departments = []
        for key in changed_keys:
            if key in seen:
                continue
            seen.add(key)
            dept = latest_snapshot.get(key, {}).get("department")
            if dept:
                delta_departments.append(dept)

        stats = {
            "baseline_departments": len(baseline_snapshot),
            "latest_departments": len(latest_snapshot),
            "added_departments": len(added_keys),
            "removed_departments": len(removed_keys),
            "count_changed_departments": count_changed,
            "unchanged_departments": unchanged_count,
            "targeted_departments": len(delta_departments),
        }
        return delta_departments, stats

    def _run_portal_pass(
        self,
        portal_name,
        portal_config,
        download_dir,
        stop_event,
        deep_scrape,
        only_new,
        shared_driver,
        portal_log,
        status_callback,
        resume_departments=True,
        pre_fetched_departments=None,
        phase_label="PASS-1",
        known_ids_seed=None,
    ):
        if pre_fetched_departments is None:
            self._update_dashboard_threadsafe(portal_name, state="Fetching", message="Fetching departments...")
            departments, _estimated = self._fetch_departments_for_portal(portal_config, portal_log)
        else:
            departments = list(pre_fetched_departments)
            _estimated = 0
        if not departments:
            portal_log("No departments found.")
            self._update_dashboard_threadsafe(portal_name, state="NoData", expected=0, extracted=0, skipped=0)
            return {
                "status": "No departments found",
                "expected_total_tenders": 0,
                "extracted_total_tenders": 0,
                "processed_departments": 0,
                "skipped_resume_departments": 0,
                "skipped_existing_total": 0,
                "extracted_tender_ids": [],
                "processed_department_names": [],
                "output_file_path": None,
                "output_file_type": None,
                "sqlite_db_path": None,
                "sqlite_run_id": None,
                "partial_saved": False,
                "department_summaries": [],
                "source_departments": []
            }

        valid_departments, expected_total = self._build_valid_departments(departments)

        known_ids = self._get_known_ids_for_portal(portal_name) if only_new else set()
        known_ids.update({str(item).strip() for item in (known_ids_seed or set()) if str(item).strip()})
        known_departments = self._get_known_departments_for_portal(portal_name) if (only_new and resume_departments) else set()
        if only_new:
            portal_log(f"Known tender IDs for resume/new-only: {len(known_ids)}")
            if resume_departments:
                portal_log(f"Known processed departments for resume: {len(known_departments)}")
            else:
                portal_log(f"{phase_label}: tender-ID de-duplication active; resume department skip disabled.")

        self._update_dashboard_threadsafe(portal_name, state="Scraping", expected=expected_total)
        if hasattr(self.main_app, "set_status_context"):
            try:
                self.main_app.set_status_context(active_portal=portal_name, state="Scraping")
            except Exception:
                pass
        status_callback(f"Batch: {portal_name}")

        sqlite_runtime_kwargs = {}
        if hasattr(self.main_app, "_get_sqlite_runtime_settings"):
            try:
                sqlite_runtime_kwargs = self.main_app._get_sqlite_runtime_settings()
            except Exception:
                sqlite_runtime_kwargs = {}

        dept_workers = 1
        try:
            dept_workers = max(1, min(3, int(self.department_workers_var.get() or 1)))
        except Exception:
            dept_workers = 1
        self._sync_department_workers_setting()
        if dept_workers > 1:
            portal_log(f"Department parallel workers enabled: {dept_workers}")

        summary = run_scraping_logic(
            departments_to_scrape=valid_departments,
            base_url_config=portal_config,
            download_dir=download_dir,
            log_callback=portal_log,
            progress_callback=lambda *_args: None,
            timer_callback=lambda *_args: None,
            status_callback=lambda *_args: None,
            stop_event=stop_event,
            driver=shared_driver,
            deep_scrape=deep_scrape,
            existing_tender_ids=known_ids,
            existing_department_names=known_departments,
            department_parallel_workers=dept_workers,
            **sqlite_runtime_kwargs
        )
        summary.setdefault("expected_total_tenders", expected_total)
        summary.setdefault("extracted_total_tenders", 0)
        summary.setdefault("skipped_existing_total", 0)
        summary.setdefault("processed_departments", 0)
        summary.setdefault("skipped_resume_departments", 0)
        summary.setdefault("extracted_tender_ids", [])
        summary.setdefault("processed_department_names", [])
        summary.setdefault("department_summaries", [])
        summary.setdefault("output_file_path", None)
        summary.setdefault("output_file_type", None)
        summary.setdefault("sqlite_db_path", None)
        summary.setdefault("sqlite_run_id", None)
        summary.setdefault("partial_saved", False)
        summary.setdefault("source_departments", list(valid_departments))
        return summary

    def _merge_pass_summaries(self, first_summary, delta_summary):
        combined_ids = sorted(set(first_summary.get("extracted_tender_ids", [])).union(delta_summary.get("extracted_tender_ids", [])))
        combined_departments = sorted(set(first_summary.get("processed_department_names", [])).union(delta_summary.get("processed_department_names", [])))
        combined_source_departments = []
        seen_dept_keys = set()
        for dept in list(first_summary.get("source_departments", []) or []) + list(delta_summary.get("source_departments", []) or []):
            if not isinstance(dept, dict):
                continue
            dept_name = str(dept.get("name", "")).strip()
            dept_key = self._normalize_department_key(dept_name)
            if not dept_key or dept_key in seen_dept_keys:
                continue
            seen_dept_keys.add(dept_key)
            combined_source_departments.append(dept)
        merged = {
            "status": first_summary.get("status", "Scraping completed"),
            "processed_departments": int(first_summary.get("processed_departments", 0)) + int(delta_summary.get("processed_departments", 0)),
            "expected_total_tenders": int(first_summary.get("expected_total_tenders", 0)),
            "extracted_total_tenders": int(first_summary.get("extracted_total_tenders", 0)) + int(delta_summary.get("extracted_total_tenders", 0)),
            "skipped_existing_total": int(first_summary.get("skipped_existing_total", 0)) + int(delta_summary.get("skipped_existing_total", 0)),
            "skipped_resume_departments": int(first_summary.get("skipped_resume_departments", 0)) + int(delta_summary.get("skipped_resume_departments", 0)),
            "department_summaries": list(first_summary.get("department_summaries", [])) + list(delta_summary.get("department_summaries", [])),
            "extracted_tender_ids": combined_ids,
            "processed_department_names": combined_departments,
            "output_file_path": delta_summary.get("output_file_path") or first_summary.get("output_file_path"),
            "output_file_type": delta_summary.get("output_file_type") or first_summary.get("output_file_type"),
            "sqlite_db_path": delta_summary.get("sqlite_db_path") or first_summary.get("sqlite_db_path"),
            "sqlite_run_id": delta_summary.get("sqlite_run_id") or first_summary.get("sqlite_run_id"),
            "partial_saved": bool(first_summary.get("partial_saved") or delta_summary.get("partial_saved")),
            "delta_sweep_extracted": int(delta_summary.get("extracted_total_tenders", 0)),
            "delta_mode": delta_summary.get("delta_mode") or first_summary.get("delta_mode") or "quick",
            "delta_quick_stats": delta_summary.get("delta_quick_stats", {}),
            "source_departments": combined_source_departments
        }
        if "error" in str(first_summary.get("status", "")).lower() or "error" in str(delta_summary.get("status", "")).lower():
            merged["status"] = "Error during scraping"
        return merged

    def _prepare_batch_report_dir(self):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_root = os.path.join(os.getcwd(), "batch_run_reports")
        report_dir = os.path.join(report_root, f"run_{stamp}")
        os.makedirs(report_dir, exist_ok=True)
        self.current_batch_report_dir = report_dir
        return report_dir

    def _write_portal_report(self, portal_name, report):
        if not self.current_batch_report_dir:
            self._prepare_batch_report_dir()
        report_dir = self.current_batch_report_dir or os.path.join(os.getcwd(), "batch_run_reports")
        os.makedirs(report_dir, exist_ok=True)

        safe_name = sanitise_filename(portal_name) or "portal"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_path = os.path.join(report_dir, f"{safe_name}_{ts}")
        json_path = f"{base_path}.json"
        csv_path = f"{base_path}.csv"

        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)

        csv_row = dict(report)
        csv_row["errors"] = " | ".join(report.get("errors", []))
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(csv_row.keys()))
            writer.writeheader()
            writer.writerow(csv_row)

        return json_path, csv_path

    def _export_department_url_coverage_report(self, log_callback=None):
        logger = log_callback or self.log_callback or (lambda _msg: None)

        if not self.current_batch_report_dir:
            self._prepare_batch_report_dir()
        report_dir = self.current_batch_report_dir or os.path.join(os.getcwd(), "batch_run_reports")
        os.makedirs(report_dir, exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = os.path.join(report_dir, f"department_url_coverage_{stamp}.json")
        csv_path = os.path.join(report_dir, f"department_url_coverage_{stamp}.csv")

        portals = self.download_manifest.get("portals", {})
        rows = []
        mapped_total = 0
        known_total = 0

        for portal_name in sorted(portals.keys()):
            stats = self._get_department_url_stats(portal_name)
            portal_data = portals.get(portal_name, {}) if isinstance(portals.get(portal_name, {}), dict) else {}
            row = {
                "portal": portal_name,
                "mapped_departments": int(stats.get("mapped_departments", 0)),
                "known_departments": int(stats.get("known_departments", 0)),
                "coverage_percent": int(stats.get("coverage_percent", 0)),
                "last_run": str(portal_data.get("last_run") or ""),
            }
            rows.append(row)
            mapped_total += row["mapped_departments"]
            known_total += row["known_departments"]

        overall_coverage = int(round((mapped_total / max(1, known_total)) * 100)) if known_total > 0 else 0
        summary = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "portal_count": len(rows),
            "mapped_departments_total": mapped_total,
            "known_departments_total": known_total,
            "overall_coverage_percent": overall_coverage,
            "portals": rows,
        }

        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, ensure_ascii=False)

        with open(csv_path, "w", encoding="utf-8-sig", newline="") as handle:
            fieldnames = ["portal", "mapped_departments", "known_departments", "coverage_percent", "last_run"]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        logger(
            "Department URL coverage report saved: "
            f"overall={overall_coverage}% ({mapped_total}/{known_total}), portals={len(rows)}, "
            f"json={json_path}, csv={csv_path}"
        )
        return json_path, csv_path

    def _run_single_portal(self, portal_name, portal_config, download_dir, stop_event, deep_scrape, only_new, shared_driver, portal_log, status_callback):
        started_at = datetime.now()
        portal_messages = []
        first_pass_summary = {}
        delta_mode = str(getattr(self, "current_batch_delta_mode", "quick") or "quick").strip().lower()
        if delta_mode not in ("quick", "full"):
            delta_mode = "quick"
        inactivity_state = {
            "last_mono": time.monotonic(),
            "last_wall": time.time()
        }

        def _touch_activity():
            inactivity_state["last_mono"] = time.monotonic()
            inactivity_state["last_wall"] = time.time()

        portal_log = self._attach_sink_to_logger(portal_log, portal_messages, _touch_activity)
        watchdog_trigger = threading.Event()
        composite_stop = _CompositeStopEvent(stop_event, watchdog_trigger)
        watchdog_done, watchdog_thread = self._start_portal_watchdog(
            portal_name=portal_name,
            portal_log=portal_log,
            stop_event=stop_event,
            inactivity_state=inactivity_state,
            watchdog_trigger=watchdog_trigger
        )

        summary = None
        self._register_active_driver(shared_driver)
        try:
            for attempt in range(2):
                if composite_stop.is_set() and attempt == 0:
                    break

                summary = self._run_portal_pass(
                    portal_name=portal_name,
                    portal_config=portal_config,
                    download_dir=download_dir,
                    stop_event=composite_stop,
                    deep_scrape=deep_scrape,
                    only_new=only_new,
                    shared_driver=shared_driver,
                    portal_log=portal_log,
                    status_callback=status_callback,
                    resume_departments=True,
                    phase_label="PASS-1"
                )

                if not watchdog_trigger.is_set() and "error" not in str(summary.get("status", "")).lower():
                    break

                if attempt == 0 and (watchdog_trigger.is_set() or self._is_recoverable_portal_error(summary.get("status"))):
                    portal_log("Watchdog/session recovery: retrying portal with fresh browser session.")
                    try:
                        if shared_driver:
                            safe_quit_driver(shared_driver, portal_log)
                            self._unregister_active_driver(shared_driver)
                    except Exception:
                        pass
                    shared_driver = setup_driver(initial_download_dir=download_dir)
                    self._register_active_driver(shared_driver)
                    watchdog_trigger.clear()
                    _touch_activity()
                    continue
                break

            if summary is None:
                summary = {
                    "status": "Error during scraping",
                    "processed_departments": 0,
                    "expected_total_tenders": 0,
                    "extracted_total_tenders": 0,
                    "skipped_existing_total": 0,
                    "skipped_resume_departments": 0,
                    "department_summaries": [],
                    "extracted_tender_ids": [],
                    "processed_department_names": [],
                    "output_file_path": None,
                    "output_file_type": None,
                    "sqlite_db_path": None,
                    "sqlite_run_id": None,
                    "partial_saved": False
                }

            first_pass_summary = dict(summary)
            first_extracted = int(first_pass_summary.get("extracted_total_tenders", 0))
            first_skipped = int(first_pass_summary.get("skipped_existing_total", 0))
            first_expected = int(first_pass_summary.get("expected_total_tenders", 0))
            first_processed = int(first_pass_summary.get("processed_departments", 0))
            first_resolved = first_extracted + first_skipped
            portal_log(
                f"MajorStep[PASS-1] expected={first_expected}, processed_depts={first_processed}, "
                f"extracted={first_extracted}, skipped_known={first_skipped}, resolved={first_resolved}"
            )

            if only_new and not composite_stop.is_set() and "error" not in str(summary.get("status", "")).lower():
                first_pass_ids = {
                    str(item).strip()
                    for item in first_pass_summary.get("extracted_tender_ids", [])
                    if str(item).strip()
                }
                portal_log(
                    f"MajorStep[DELTA-START] baseline_resolved={first_resolved}, "
                    f"baseline_extracted={first_extracted}, baseline_skipped={first_skipped}"
                )
                self._update_dashboard_threadsafe(
                    portal_name,
                    state="DeltaSweeping",
                    message="DELTA SWEEPING (final pass)"
                )
                self._push_global_progress(state="DeltaSweeping", active_portal=portal_name)
                if hasattr(self.main_app, "set_status_context"):
                    try:
                        self.main_app.set_status_context(active_portal=portal_name, state="DeltaSweeping")
                    except Exception:
                        pass
                status_callback(f"Delta sweeping: {portal_name}")
                portal_log(f"Delta strategy selected: {delta_mode.upper()}")

                delta_summary = None
                if delta_mode == "full":
                    portal_log("Starting FULL delta sweep (re-checking all listed departments)...")
                    delta_summary = self._run_portal_pass(
                        portal_name=portal_name,
                        portal_config=portal_config,
                        download_dir=download_dir,
                        stop_event=composite_stop,
                        deep_scrape=False,
                        only_new=True,
                        shared_driver=shared_driver,
                        portal_log=portal_log,
                        status_callback=status_callback,
                        resume_departments=False,
                        phase_label="DELTA-FULL",
                        known_ids_seed=first_pass_ids
                    )
                else:
                    portal_log("Starting QUICK delta sweep (org list count/name compare)...")
                    latest_departments, _latest_estimated = self._fetch_departments_for_portal(portal_config, portal_log)
                    baseline_departments = list(first_pass_summary.get("source_departments", []))
                    latest_valid, _latest_expected = self._build_valid_departments(latest_departments or [])
                    delta_departments, quick_stats = self._plan_quick_delta_departments(baseline_departments, latest_valid, portal_log)

                    portal_log(
                        "MajorStep[DELTA-QUICK-COMPARE] "
                        f"baseline_depts={quick_stats.get('baseline_departments', 0)}, "
                        f"latest_depts={quick_stats.get('latest_departments', 0)}, "
                        f"added={quick_stats.get('added_departments', 0)}, "
                        f"removed={quick_stats.get('removed_departments', 0)}, "
                        f"count_changed={quick_stats.get('count_changed_departments', 0)}, "
                        f"targeted={quick_stats.get('targeted_departments', 0)}"
                    )

                    if delta_departments:
                        names_preview = ", ".join([str(d.get("name", "")).strip() for d in delta_departments[:6] if str(d.get("name", "")).strip()])
                        if len(delta_departments) > 6:
                            names_preview += " ..."
                        if names_preview:
                            portal_log(f"Quick delta targeted departments: {names_preview}")

                        delta_summary = self._run_portal_pass(
                            portal_name=portal_name,
                            portal_config=portal_config,
                            download_dir=download_dir,
                            stop_event=composite_stop,
                            deep_scrape=False,
                            only_new=True,
                            shared_driver=shared_driver,
                            portal_log=portal_log,
                            status_callback=status_callback,
                            resume_departments=False,
                            pre_fetched_departments=delta_departments,
                            phase_label="DELTA-QUICK",
                            known_ids_seed=first_pass_ids
                        )
                    else:
                        portal_log("Quick delta compare found no changed departments; skipping second pass scraping.")
                        delta_summary = {
                            "status": "Quick delta: no changed departments",
                            "processed_departments": 0,
                            "expected_total_tenders": int(first_pass_summary.get("expected_total_tenders", 0)),
                            "extracted_total_tenders": 0,
                            "skipped_existing_total": 0,
                            "skipped_resume_departments": 0,
                            "department_summaries": [],
                            "extracted_tender_ids": [],
                            "processed_department_names": [],
                            "output_file_path": first_pass_summary.get("output_file_path"),
                            "output_file_type": first_pass_summary.get("output_file_type"),
                            "sqlite_db_path": first_pass_summary.get("sqlite_db_path"),
                            "sqlite_run_id": first_pass_summary.get("sqlite_run_id"),
                            "partial_saved": bool(first_pass_summary.get("partial_saved", False)),
                            "source_departments": [],
                        }
                    delta_summary["delta_quick_stats"] = quick_stats

                delta_extracted = int(delta_summary.get("extracted_total_tenders", 0))
                delta_skipped = int(delta_summary.get("skipped_existing_total", 0))
                delta_processed = int(delta_summary.get("processed_departments", 0))
                portal_log(
                    f"MajorStep[DELTA-END] processed_depts={delta_processed}, "
                    f"delta_extracted={delta_extracted}, delta_skipped={delta_skipped}"
                )
                summary = self._merge_pass_summaries(summary, delta_summary)
                summary["delta_mode"] = delta_mode
                merged_extracted = int(summary.get("extracted_total_tenders", 0))
                merged_skipped = int(summary.get("skipped_existing_total", 0))
                merged_expected = int(summary.get("expected_total_tenders", 0))
                portal_log(
                    f"MajorStep[MERGED] expected={merged_expected}, extracted={merged_extracted}, "
                    f"skipped_known={merged_skipped}, resolved={merged_extracted + merged_skipped}"
                )
                portal_log(f"Delta sweep extracted: {summary.get('delta_sweep_extracted', 0)}")
                self._push_global_progress(state="Running", active_portal=portal_name)
        finally:
            watchdog_done.set()
            if watchdog_thread:
                watchdog_thread.join(timeout=1)
            self._unregister_active_driver(shared_driver)

        status_text = str(summary.get("status", "")).lower()
        if "no departments" in status_text:
            state_value = "NoData"
        else:
            state_value = "Done" if "completed" in status_text else "Error"

        known_total = self._update_manifest_for_portal(portal_name, summary)
        dept_url_stats = self._get_department_url_stats(portal_name)
        portal_log(
            "Dept URL tracker -> "
            f"mapped={dept_url_stats.get('mapped_departments', 0)}, "
            f"known={dept_url_stats.get('known_departments', 0)}, "
            f"coverage={dept_url_stats.get('coverage_percent', 0)}%"
        )
        self._update_dashboard_threadsafe(
            portal_name,
            state=state_value,
            expected=summary.get("expected_total_tenders", 0),
            extracted=summary.get("extracted_total_tenders", 0),
            skipped=summary.get("skipped_existing_total", 0),
            known=known_total
        )

        output_file_path = summary.get("output_file_path")
        if output_file_path:
            save_kind = "PARTIAL" if summary.get("partial_saved") else "FINAL"
            portal_log(f"{save_kind} output saved: {output_file_path}")
        else:
            portal_log("No output file path reported for this portal run.")

        gap = max(0, summary.get("expected_total_tenders", 0) - summary.get("extracted_total_tenders", 0) - summary.get("skipped_existing_total", 0))
        if summary.get("skipped_resume_departments", 0) > 0:
            portal_log(f"Resume skipped departments: {summary.get('skipped_resume_departments', 0)}")
        portal_log(
            f"Verification summary -> expected={summary.get('expected_total_tenders', 0)}, "
            f"extracted={summary.get('extracted_total_tenders', 0)}, "
            f"skipped_known={summary.get('skipped_existing_total', 0)}, "
            f"remaining_gap={gap}"
        )

        sqlite_db_path = str(summary.get("sqlite_db_path") or "").strip()
        sqlite_run_id = summary.get("sqlite_run_id")
        output_file_path = str(summary.get("output_file_path") or "").strip()
        output_file_type = str(summary.get("output_file_type") or "").strip().upper()

        if sqlite_db_path and sqlite_run_id is not None:
            portal_log(f"[PERSIST][BATCH] SQLite: SAVED | run_id={sqlite_run_id} | path={sqlite_db_path}")
        elif sqlite_db_path:
            portal_log(f"[PERSIST][BATCH] SQLite: NOT CONFIRMED | path={sqlite_db_path}")
        else:
            portal_log("[PERSIST][BATCH] SQLite: NOT AVAILABLE")

        if output_file_path:
            export_fmt = output_file_type or "UNKNOWN"
            portal_log(f"[PERSIST][BATCH] File: SAVED | format={export_fmt} | path={output_file_path}")
            self._update_dashboard_threadsafe(
                portal_name,
                message=f"Persisted -> SQLite run {sqlite_run_id if sqlite_run_id is not None else '-'} | {export_fmt}: {output_file_path}"
            )
        else:
            portal_log("[PERSIST][BATCH] File: NOT GENERATED")
            self._update_dashboard_threadsafe(
                portal_name,
                message=f"Persisted -> SQLite run {sqlite_run_id if sqlite_run_id is not None else '-'} | file not generated"
            )

        completed_at = datetime.now()
        errors = [msg for msg in portal_messages if re.search(r"\b(error|failed|critical|exception)\b", msg, re.IGNORECASE)]
        report = {
            "portal": portal_name,
            "started_at": started_at.isoformat(timespec="seconds"),
            "completed_at": completed_at.isoformat(timespec="seconds"),
            "duration_sec": max(0.0, (completed_at - started_at).total_seconds()),
            "status": summary.get("status", "Unknown"),
            "pass1_expected_tenders": int(first_pass_summary.get("expected_total_tenders", 0)),
            "pass1_extracted_tenders": int(first_pass_summary.get("extracted_total_tenders", 0)),
            "pass1_skipped_known_tenders": int(first_pass_summary.get("skipped_existing_total", 0)),
            "attempted_departments": int(summary.get("processed_departments", 0)) + int(summary.get("skipped_resume_departments", 0)),
            "processed_departments": int(summary.get("processed_departments", 0)),
            "resume_skipped_departments": int(summary.get("skipped_resume_departments", 0)),
            "expected_tenders": int(summary.get("expected_total_tenders", 0)),
            "extracted_tenders": int(summary.get("extracted_total_tenders", 0)),
            "skipped_known_tenders": int(summary.get("skipped_existing_total", 0)),
            "output_file_path": summary.get("output_file_path"),
            "output_file_type": summary.get("output_file_type"),
            "sqlite_db_path": summary.get("sqlite_db_path"),
            "sqlite_run_id": summary.get("sqlite_run_id"),
            "partial_saved": bool(summary.get("partial_saved", False)),
            "delta_sweep_enabled": bool(only_new),
            "delta_mode": str(summary.get("delta_mode") or delta_mode),
            "delta_sweep_extracted": int(summary.get("delta_sweep_extracted", 0)),
            "delta_quick_stats": summary.get("delta_quick_stats", {}),
            "department_url_tracker": dept_url_stats,
            "error_count": len(errors),
            "errors": errors[:30]
        }
        json_report_path, csv_report_path = self._write_portal_report(portal_name, report)
        portal_log(f"Run report saved (JSON): {json_report_path}")
        portal_log(f"Run report saved (CSV): {csv_report_path}")

        return summary

    def _run_batch_worker(self, selected_portals, download_dir, mode, max_parallel, ip_safety, only_new,
                          driver=None, log_callback=None, progress_callback=None,
                          timer_callback=None, status_callback=None, stop_event=None, **kwargs):
        log_callback = log_callback or (lambda _message: None)
        status_callback = status_callback or (lambda _message: None)
        progress_callback = progress_callback or (lambda *_args: None)

        total_portals = len(selected_portals)
        self._prepare_batch_report_dir()

        if mode == "parallel":
            self._run_parallel(selected_portals, download_dir, max_parallel, ip_safety, only_new, log_callback, status_callback, progress_callback, stop_event, kwargs)
            return

        completed = 0
        min_delay = ip_safety.get("min_delay_sec", 1.0)
        max_delay = ip_safety.get("max_delay_sec", 3.0)

        if driver:
            self._register_active_driver(driver)

        for idx, portal_name in enumerate(selected_portals, start=1):
            if stop_event and stop_event.is_set():
                log_callback("Batch stop requested. Ending remaining portals.")
                break

            if idx > 1:
                delay = random.uniform(min_delay, max_delay)
                log_callback(f"Sequential IP safety delay: sleeping {delay:.1f}s before next portal.")
                if not self._interruptible_sleep(delay, stop_event=stop_event):
                    log_callback("Batch stop requested during sequential delay.")
                    break

            portal_config = self._portal_config_by_name(portal_name)
            if not portal_config:
                log_callback(f"SKIP: Could not resolve portal config for '{portal_name}'.")
                self._update_dashboard_threadsafe(portal_name, state="Error")
                continue

            portal_log = self._build_portal_logger(portal_name, log_callback)
            portal_log(f"BATCH PORTAL {idx}/{total_portals} START")

            try:
                self._run_single_portal(
                    portal_name=portal_name,
                    portal_config=portal_config,
                    download_dir=download_dir,
                    stop_event=stop_event,
                    deep_scrape=kwargs.get("deep_scrape", False),
                    only_new=only_new,
                    shared_driver=driver,
                    portal_log=portal_log,
                    status_callback=status_callback
                )
            except Exception as error:
                portal_log(f"ERROR in portal run: {error}")
                self._update_dashboard_threadsafe(portal_name, state="Error")

            completed += 1
            if hasattr(self.main_app, "set_status_context"):
                try:
                    self.main_app.set_status_context(
                        completed_portals=completed,
                        total_portals=total_portals,
                        active_portal=portal_name,
                        state="Running"
                    )
                except Exception:
                    pass
            progress_callback(completed, total_portals, f"Completed {completed}/{total_portals}")

        stopped = bool(stop_event and stop_event.is_set())
        status_callback("Batch scraping stopped by user" if stopped else "Batch scraping completed")
        self._push_global_progress(state="Stopped" if stopped else "Completed")
        if hasattr(self.main_app, "set_status_context"):
            try:
                self.main_app.set_status_context(
                    state="Stopped" if stopped else "Completed",
                    completed_portals=completed if stopped else total_portals
                )
            except Exception:
                pass
        self._export_department_url_coverage_report(log_callback=log_callback)
        if self.current_batch_report_dir:
            log_callback(f"Batch run reports saved in: {self.current_batch_report_dir}")

        if driver:
            self._unregister_active_driver(driver)

    def _run_parallel(self, selected_portals, download_dir, max_parallel, ip_safety, only_new, log_callback, status_callback, progress_callback, stop_event, common_kwargs):
        lock = threading.Lock()
        completed = {"count": 0}
        total = len(selected_portals)

        per_domain_max = max(1, int(ip_safety.get("per_domain_max", 1)))
        min_delay = float(ip_safety.get("min_delay_sec", 1.0))
        max_delay = float(ip_safety.get("max_delay_sec", 3.0))
        cooldown_sec = max(0, int(ip_safety.get("cooldown_sec", 10)))
        max_retries = max(0, int(ip_safety.get("max_retries", 2)))

        domain_semaphores = {}
        domain_lock = threading.Lock()

        def _get_domain_semaphore(domain):
            with domain_lock:
                if domain not in domain_semaphores:
                    domain_semaphores[domain] = threading.Semaphore(per_domain_max)
                return domain_semaphores[domain]

        def _process_one(portal_name):
            local_driver = None
            portal_log = self._build_portal_logger(portal_name, log_callback)
            try:
                if stop_event and stop_event.is_set():
                    return

                portal_config = self._portal_config_by_name(portal_name)
                if not portal_config:
                    portal_log("SKIP: Could not resolve portal config.")
                    self._update_dashboard_threadsafe(portal_name, state="Error")
                    return

                domain = self._domain_from_config(portal_config)
                domain_semaphore = _get_domain_semaphore(domain)
                portal_log(f"waiting for domain slot (domain={domain}, per-domain max={per_domain_max})")

                with domain_semaphore:
                    portal_log("acquired domain slot")
                    for attempt in range(max_retries + 1):
                        if stop_event and stop_event.is_set():
                            return

                        startup_delay = random.uniform(min_delay, max_delay)
                        portal_log(f"IP safety delay {startup_delay:.1f}s (attempt {attempt + 1}/{max_retries + 1})")
                        if not self._interruptible_sleep(startup_delay, stop_event=stop_event):
                            return

                        try:
                            local_driver = setup_driver(initial_download_dir=download_dir)
                            self._register_active_driver(local_driver)
                            self._run_single_portal(
                                portal_name=portal_name,
                                portal_config=portal_config,
                                download_dir=download_dir,
                                stop_event=stop_event,
                                deep_scrape=common_kwargs.get("deep_scrape", False),
                                only_new=only_new,
                                shared_driver=local_driver,
                                portal_log=portal_log,
                                status_callback=status_callback
                            )
                            break
                        except Exception as error:
                            blocked = self._is_probable_block(error)
                            if attempt < max_retries and blocked:
                                sleep_for = max(cooldown_sec, 5) * (attempt + 1)
                                portal_log(f"probable IP/rate block detected ({error}); retrying after {sleep_for}s")
                                if not self._interruptible_sleep(sleep_for, stop_event=stop_event):
                                    return
                                continue
                            portal_log(f"ERROR in parallel portal (attempt {attempt + 1}): {error}")
                            self._update_dashboard_threadsafe(portal_name, state="Error")
                            break
                        finally:
                            if local_driver:
                                safe_quit_driver(local_driver, portal_log)
                                self._unregister_active_driver(local_driver)
                                local_driver = None

                    if cooldown_sec > 0 and not (stop_event and stop_event.is_set()):
                        portal_log(f"cooldown {cooldown_sec}s before releasing domain slot")
                        self._interruptible_sleep(cooldown_sec, stop_event=stop_event)
            finally:
                with lock:
                    completed["count"] += 1
                    done = completed["count"]
                if hasattr(self.main_app, "set_status_context"):
                    try:
                        self.main_app.set_status_context(
                            completed_portals=done,
                            total_portals=total,
                            active_portal=portal_name,
                            state="Running"
                        )
                    except Exception:
                        pass
                progress_callback(done, total, f"Parallel completed {done}/{total}")
                status_callback(f"Parallel batch {done}/{total} completed")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = [executor.submit(_process_one, portal_name) for portal_name in selected_portals]
            for future in concurrent.futures.as_completed(futures):
                if stop_event and stop_event.is_set():
                    break
                future.result()

        stopped = bool(stop_event and stop_event.is_set())
        status_callback("Batch scraping stopped by user" if stopped else "Batch scraping completed")
        self._push_global_progress(state="Stopped" if stopped else "Completed")
        if hasattr(self.main_app, "set_status_context"):
            try:
                self.main_app.set_status_context(
                    state="Stopped" if stopped else "Completed",
                    completed_portals=completed["count"] if stopped else total
                )
            except Exception:
                pass
        self._export_department_url_coverage_report(log_callback=log_callback)
        if self.current_batch_report_dir:
            log_callback(f"Batch run reports saved in: {self.current_batch_report_dir}")

    def set_controls_state(self, state):
        widgets = [
            self.start_batch_button,
            self.export_bat_button,
            self.export_ps1_button,
            self.scope_new_radio,
            self.scope_all_radio,
            self.delta_mode_combo,
            self.max_parallel_spin,
            self.per_domain_spin,
            self.min_delay_entry,
            self.max_delay_entry,
            self.cooldown_spin,
            self.retries_spin,
            self.group_combo,
            self.portal_listbox,
            self.batch_portal_filter_combo,
            self.batch_log_search_entry
        ]
        for widget in widgets:
            try:
                widget.configure(state=state)
            except Exception:
                pass
