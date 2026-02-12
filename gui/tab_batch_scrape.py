import concurrent.futures
import csv
import glob
import json
import os
import random
import re
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk, scrolledtext, Listbox, Scrollbar, END, EXTENDED, StringVar, IntVar, BooleanVar, filedialog
from urllib.parse import urlparse

from batch_config_memory import get_batch_memory
from gui import gui_utils
from scraper.driver_manager import setup_driver, safe_quit_driver
from scraper.logic import fetch_department_list_from_site_v2, run_scraping_logic
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

        self.mode_var = StringVar(value="sequential")
        self.max_parallel_var = IntVar(value=2)
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
        self._dashboard_lock = threading.Lock()

        self.manifest_path = os.path.join(os.getcwd(), "batch_tender_manifest.json")
        self.download_manifest = self._load_manifest()

        self.enable_delta_sweep = True
        self.portal_watchdog_inactivity_sec = 120
        self.portal_watchdog_sleep_jump_sec = 180
        self.current_batch_report_dir = None

        self._create_widgets()
        self._load_initial_data()

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

        ttk.Label(top_controls, text="Scrape:", font=self.main_app.label_font).pack(side=tk.LEFT, padx=(12, 4))
        self.scope_new_radio = ttk.Radiobutton(top_controls, text="Only New", variable=self.scrape_scope_var, value="only_new")
        self.scope_new_radio.pack(side=tk.LEFT, padx=(0, 6))
        self.scope_all_radio = ttk.Radiobutton(top_controls, text="All", variable=self.scrape_scope_var, value="all")
        self.scope_all_radio.pack(side=tk.LEFT, padx=(0, 0))

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

    def _get_known_ids_for_portal(self, portal_name):
        portal_data = self.download_manifest.get("portals", {}).get(portal_name, {})
        return set(portal_data.get("tender_ids", []))

    def _get_known_departments_for_portal(self, portal_name):
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
        portal_data["tender_ids"] = sorted(known)
        portal_data["processed_departments"] = sorted(known_departments)
        portal_data["last_run"] = datetime.now().isoformat(timespec="seconds")
        portal_data["last_expected"] = summary.get("expected_total_tenders", 0)
        portal_data["last_extracted"] = summary.get("extracted_total_tenders", 0)
        self._save_manifest()
        return len(known)

    def _append_batch_log(self, portal_name, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        message_text = str(message)
        entry = {
            "timestamp": timestamp,
            "portal": portal_name,
            "message": message_text
        }
        self.batch_log_messages.append(entry)
        self._update_dashboard(
            portal_name,
            state=self._derive_state_from_message(message_text),
            message=message_text
        )
        self._render_batch_logs()

    def _derive_state_from_message(self, message):
        text = str(message).lower()
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
            self.batch_log_text.insert(tk.END, line + "\n")

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

        for portal in selected_portals:
            known_total = len(self._get_known_ids_for_portal(portal))
            item_id = self.dashboard_tree.insert(
                "", tk.END,
                values=(portal, "Idle", 0, 0, 0, known_total, "Waiting to start...", "--:--:--")
            )
            self.portal_dashboard_rows[portal] = item_id

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
        if self.main_app.scraping_in_progress:
            gui_utils.show_message("Busy", "Another process is currently running.", type="warning", parent=self.main_app.root)
            return

        selected_portals = self._get_selected_portals()
        if not selected_portals:
            gui_utils.show_message("No Selection", "Select one or more portals first.", type="warning", parent=self.main_app.root)
            return

        self._init_dashboard_rows(selected_portals)
        self._refresh_portal_filter_values()

        download_dir = self.main_app.download_dir_var.get()
        if not self.main_app.validate_download_dir(download_dir):
            return

        mode = self.mode_var.get()
        only_new = self.scrape_scope_var.get() == "only_new"
        max_parallel = max(1, int(self.max_parallel_var.get() or 1))
        if mode == "parallel":
            max_parallel = min(max_parallel, len(selected_portals), 4)

        ip_safety = self._get_ip_safety_settings()

        if not gui_utils.show_message(
            "Confirm Batch",
            f"Start batch scrape for {len(selected_portals)} portal(s)?\n"
            f"Mode: {mode.title()}\n"
            f"Scope: {'Only New' if only_new else 'All'}\n"
            f"Max Parallel: {max_parallel}\n"
            f"Per-Domain: {ip_safety['per_domain_max']}\n"
            f"Delay: {ip_safety['min_delay_sec']}s to {ip_safety['max_delay_sec']}s\n"
            f"Cooldown: {ip_safety['cooldown_sec']}s\n"
            f"Retries: {ip_safety['max_retries']}",
            type="askyesno",
            parent=self.main_app.root
        ):
            return

        self.only_new_var.set(only_new)
        self.batch_memory.save_last_settings(selected_portals, mode, max_parallel, ip_safety, only_new)

        self.main_app.total_estimated_tenders_for_run = len(selected_portals)
        self.main_app.reset_progress_and_timer()
        self.main_app.update_status(f"Starting batch ({mode})...")
        self.log_callback(f"Starting batch scrape for {len(selected_portals)} portal(s) in {mode} mode.")

        self.main_app.start_background_task(
            self._run_batch_worker,
            args=(selected_portals, download_dir, mode, max_parallel, ip_safety, only_new),
            task_name="Batch Scrape"
        )

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

                time.sleep(10)

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

    def _run_portal_pass(self, portal_name, portal_config, download_dir, stop_event, deep_scrape, only_new, shared_driver, portal_log, status_callback, resume_departments=True):
        self._update_dashboard_threadsafe(portal_name, state="Fetching", message="Fetching departments...")
        departments, _estimated = fetch_department_list_from_site_v2(portal_config.get("OrgListURL"), portal_log)
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
                "partial_saved": False,
                "department_summaries": []
            }

        valid_departments = []
        expected_total = 0
        for dept in departments:
            s_no = str(dept.get("s_no", "")).strip().lower()
            dept_name = str(dept.get("name", "")).strip().lower()
            count_text = str(dept.get("count_text", "")).strip()
            if s_no.isdigit() and dept_name not in ["organisation name", "department name", "organization", "organization name"]:
                valid_departments.append(dept)
                if count_text.isdigit():
                    expected_total += int(count_text)

        known_ids = self._get_known_ids_for_portal(portal_name) if only_new else set()
        known_departments = self._get_known_departments_for_portal(portal_name) if (only_new and resume_departments) else set()
        if only_new:
            portal_log(f"Known tender IDs for resume/new-only: {len(known_ids)}")
            if resume_departments:
                portal_log(f"Known processed departments for resume: {len(known_departments)}")
            else:
                portal_log("Delta sweep: re-checking all departments with tender-ID de-duplication.")

        self._update_dashboard_threadsafe(portal_name, state="Scraping", expected=expected_total)
        status_callback(f"Batch: {portal_name}")

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
            existing_department_names=known_departments
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
        summary.setdefault("partial_saved", False)
        return summary

    def _merge_pass_summaries(self, first_summary, delta_summary):
        combined_ids = sorted(set(first_summary.get("extracted_tender_ids", [])).union(delta_summary.get("extracted_tender_ids", [])))
        combined_departments = sorted(set(first_summary.get("processed_department_names", [])).union(delta_summary.get("processed_department_names", [])))
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
            "partial_saved": bool(first_summary.get("partial_saved") or delta_summary.get("partial_saved")),
            "delta_sweep_extracted": int(delta_summary.get("extracted_total_tenders", 0))
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

    def _run_single_portal(self, portal_name, portal_config, download_dir, stop_event, deep_scrape, only_new, shared_driver, portal_log, status_callback):
        started_at = datetime.now()
        portal_messages = []
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
                    resume_departments=True
                )

                if not watchdog_trigger.is_set() and "error" not in str(summary.get("status", "")).lower():
                    break

                if attempt == 0 and (watchdog_trigger.is_set() or self._is_recoverable_portal_error(summary.get("status"))):
                    portal_log("Watchdog/session recovery: retrying portal with fresh browser session.")
                    try:
                        if shared_driver:
                            safe_quit_driver(shared_driver, portal_log)
                    except Exception:
                        pass
                    shared_driver = setup_driver(initial_download_dir=download_dir)
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
                    "partial_saved": False
                }

            if self.enable_delta_sweep and only_new and not composite_stop.is_set() and "error" not in str(summary.get("status", "")).lower():
                portal_log("Starting optional final delta sweep (quick second pass)...")
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
                    resume_departments=False
                )
                summary = self._merge_pass_summaries(summary, delta_summary)
                portal_log(f"Delta sweep extracted: {summary.get('delta_sweep_extracted', 0)}")
        finally:
            watchdog_done.set()
            if watchdog_thread:
                watchdog_thread.join(timeout=1)

        status_text = str(summary.get("status", "")).lower()
        if "no departments" in status_text:
            state_value = "NoData"
        else:
            state_value = "Done" if "completed" in status_text else "Error"

        known_total = self._update_manifest_for_portal(portal_name, summary)
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

        completed_at = datetime.now()
        errors = [msg for msg in portal_messages if re.search(r"\b(error|failed|critical|exception)\b", msg, re.IGNORECASE)]
        report = {
            "portal": portal_name,
            "started_at": started_at.isoformat(timespec="seconds"),
            "completed_at": completed_at.isoformat(timespec="seconds"),
            "duration_sec": max(0.0, (completed_at - started_at).total_seconds()),
            "status": summary.get("status", "Unknown"),
            "attempted_departments": int(summary.get("processed_departments", 0)) + int(summary.get("skipped_resume_departments", 0)),
            "processed_departments": int(summary.get("processed_departments", 0)),
            "resume_skipped_departments": int(summary.get("skipped_resume_departments", 0)),
            "expected_tenders": int(summary.get("expected_total_tenders", 0)),
            "extracted_tenders": int(summary.get("extracted_total_tenders", 0)),
            "skipped_known_tenders": int(summary.get("skipped_existing_total", 0)),
            "output_file_path": summary.get("output_file_path"),
            "output_file_type": summary.get("output_file_type"),
            "partial_saved": bool(summary.get("partial_saved", False)),
            "delta_sweep_enabled": bool(self.enable_delta_sweep and only_new),
            "delta_sweep_extracted": int(summary.get("delta_sweep_extracted", 0)),
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

        for idx, portal_name in enumerate(selected_portals, start=1):
            if stop_event and stop_event.is_set():
                log_callback("Batch stop requested. Ending remaining portals.")
                break

            if idx > 1:
                delay = random.uniform(min_delay, max_delay)
                log_callback(f"Sequential IP safety delay: sleeping {delay:.1f}s before next portal.")
                time.sleep(delay)

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
            progress_callback(completed, total_portals, f"Completed {completed}/{total_portals}")

        status_callback("Batch scraping completed")
        if self.current_batch_report_dir:
            log_callback(f"Batch run reports saved in: {self.current_batch_report_dir}")

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
                        time.sleep(startup_delay)

                        try:
                            local_driver = setup_driver(initial_download_dir=download_dir)
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
                                time.sleep(sleep_for)
                                continue
                            portal_log(f"ERROR in parallel portal (attempt {attempt + 1}): {error}")
                            self._update_dashboard_threadsafe(portal_name, state="Error")
                            break
                        finally:
                            if local_driver:
                                safe_quit_driver(local_driver, portal_log)
                                local_driver = None

                    if cooldown_sec > 0 and not (stop_event and stop_event.is_set()):
                        portal_log(f"cooldown {cooldown_sec}s before releasing domain slot")
                        time.sleep(cooldown_sec)
            finally:
                with lock:
                    completed["count"] += 1
                    done = completed["count"]
                progress_callback(done, total, f"Parallel completed {done}/{total}")
                status_callback(f"Parallel batch {done}/{total} completed")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = [executor.submit(_process_one, portal_name) for portal_name in selected_portals]
            for future in concurrent.futures.as_completed(futures):
                if stop_event and stop_event.is_set():
                    break
                future.result()

        status_callback("Batch scraping completed")
        if self.current_batch_report_dir:
            log_callback(f"Batch run reports saved in: {self.current_batch_report_dir}")

    def set_controls_state(self, state):
        widgets = [
            self.start_batch_button,
            self.export_bat_button,
            self.export_ps1_button,
            self.scope_new_radio,
            self.scope_all_radio,
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
