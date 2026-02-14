import hashlib
import json
import os
import csv
import sqlite3
import threading
import time
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import ttk, scrolledtext, filedialog
from typing import Any, cast

from app_settings import save_settings
from batch_config_memory import get_batch_memory
from gui import gui_utils
from scraper.logic import fetch_department_list_from_site_v2
from utils import get_website_keyword_from_url

try:
    import pandas as pd
except Exception:
    pd = None


class RefreshWatchTab(ttk.Frame):
    """Portal refresh scheduler with change detection and auto-triggered full scrape."""

    MAX_HISTORY_EVENTS = 50
    DEFAULT_INTERVAL_MIN = 180

    def __init__(self, parent, main_app_ref, **kwargs):
        super().__init__(parent, **kwargs)
        self.main_app = main_app_ref

        self.watch_enabled_var = tk.BooleanVar(value=bool(self.main_app.settings.get("refresh_watch_enabled", False)))
        self.loop_seconds_var = tk.StringVar(value=str(self.main_app.settings.get("refresh_watch_loop_seconds", 30)))

        self.portal_var = tk.StringVar(value="")
        self.interval_var = tk.StringVar(value=str(self.DEFAULT_INTERVAL_MIN))
        self.enabled_var = tk.BooleanVar(value=True)

        self._watch_thread = None
        self._watch_stop_event = threading.Event()
        self._pending_portals = set()
        self._portal_rules = {}
        self._watch_state = dict(self.main_app.settings.get("refresh_watch_state", {}) or {})
        self._history_events = []
        self._diagnostics_file = None
        self._portal_health_job = None
        self._portal_health_refresh_ms = 15000
        self._manifest_path = os.path.join(os.getcwd(), "batch_tender_manifest.json")
        self._health_sort_col = "portal"
        self._health_sort_reverse = False
        self._portal_alias_map = {}
        self._group_membership_map = {}
        self._health_context_menu = None
        self._daily_batch_active = False
        self._last_tender84_export_epoch = 0.0
        self._batch_memory = get_batch_memory()

        try:
            logs_dir = os.path.join(os.path.dirname(self.main_app.settings_filepath), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            self._diagnostics_file = os.path.join(logs_dir, "refresh_watch_diagnostics.jsonl")
        except Exception:
            self._diagnostics_file = None

        self._create_widgets()
        self._load_from_settings()
        self._refresh_tree()
        self._refresh_history_view()
        self._refresh_portal_health()
        self._schedule_portal_health_refresh()
        self.after(2500, self._auto_daily_start_if_due)

        if self.watch_enabled_var.get():
            self.start_watch(auto=True)

    def _create_widgets(self):
        section = ttk.Labelframe(self, text="Dashboard", style="Section.TLabelframe")
        section.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        health_lab = ttk.Labelframe(section, text="Portal Health Overview", style="Section.TLabelframe")
        health_lab.pack(fill=tk.BOTH, expand=True, padx=5, pady=(6, 5))

        health_top = ttk.Frame(health_lab)
        health_top.pack(fill=tk.X, padx=5, pady=(5, 2))
        ttk.Label(health_top, text="Tick (sec):", font=self.main_app.label_font).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(health_top, textvariable=self.loop_seconds_var, width=6).pack(side=tk.LEFT, padx=(0, 10))

        self.start_watch_button = ttk.Button(health_top, text="Start Watch", style="Accent.TButton", width=12, command=self.start_watch)
        self.start_watch_button.pack(side=tk.LEFT, padx=(0, 6))
        self.stop_watch_button = ttk.Button(health_top, text="Stop Watch", width=12, command=self.stop_watch)
        self.stop_watch_button.pack(side=tk.LEFT, padx=(0, 6))

        ttk.Label(health_top, text="Every (min):", font=self.main_app.label_font).pack(side=tk.LEFT, padx=(10, 4))
        ttk.Entry(health_top, textvariable=self.interval_var, width=8).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Checkbutton(health_top, text="Enable Selected", variable=self.enabled_var).pack(side=tk.LEFT, padx=(0, 8))
        self.add_update_button = ttk.Button(health_top, text="Apply Selected", width=14, command=self._add_or_update_rule)
        self.add_update_button.pack(side=tk.LEFT, padx=(0, 6))
        self.remove_rule_button = ttk.Button(health_top, text="Disable Selected", width=14, command=self._remove_selected_rule)
        self.remove_rule_button.pack(side=tk.LEFT, padx=(0, 6))
        self.run_now_button = ttk.Button(health_top, text="Run Selected Now", width=14, command=self._run_selected_now)
        self.run_now_button.pack(side=tk.LEFT, padx=(0, 6))

        self.save_watch_button = ttk.Button(health_top, text="Save", width=8, command=self._save_watch_settings)
        self.save_watch_button.pack(side=tk.LEFT, padx=(6, 6))
        self.export_history_button = ttk.Button(health_top, text="Export History", width=14, command=self._export_history_csv)
        self.export_history_button.pack(side=tk.LEFT, padx=(0, 8))

        self.watch_state_label = ttk.Label(health_top, text="Watcher: Stopped", font=self.main_app.label_font)
        self.watch_state_label.pack(side=tk.LEFT, padx=(4, 0))

        self.refresh_health_button = ttk.Button(
            health_top,
            text="Refresh Health",
            width=14,
            command=self._refresh_portal_health,
        )
        self.refresh_health_button.pack(side=tk.RIGHT)
        self.health_summary_label = ttk.Label(
            health_top,
            text="Portals: 0   Live: 0   Expired: 0",
            font=self.main_app.label_font,
        )
        self.health_summary_label.pack(side=tk.RIGHT, padx=(0, 10))

        self.health_tree = ttk.Treeview(
            health_lab,
            columns=("group", "portal", "last_scrape", "live", "expired", "enabled", "interval", "status"),
            show="headings",
            height=13,
        )
        health_columns = [
            ("group", "Group", 130, "w"),
            ("portal", "Portal", 220, "w"),
            ("last_scrape", "Last Scrape", 155, "center"),
            ("live", "Live", 80, "center"),
            ("expired", "Expired", 90, "center"),
            ("enabled", "Watch", 80, "center"),
            ("interval", "Watch Freq (min)", 120, "center"),
            ("status", "Current Status", 220, "w"),
        ]
        for col, text, width, anchor in health_columns:
            self.health_tree.heading(col, text=text, command=lambda c=col: self._sort_health_tree(c))
            self.health_tree.column(col, width=width, anchor=cast(Any, anchor))
        self.health_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        self.health_tree.bind("<<TreeviewSelect>>", self._on_rule_selected)
        self.health_tree.bind("<Button-3>", self._on_health_right_click)

        self._health_context_menu = tk.Menu(self, tearoff=0)
        self._health_context_menu.add_command(label="Run Selected (Only New)", command=lambda: self._run_selected_batch("only_new"))
        self._health_context_menu.add_command(label="Run Selected (All)", command=lambda: self._run_selected_batch("all"))
        self._health_context_menu.add_separator()
        self._health_context_menu.add_command(label="Run Group (Only New)", command=lambda: self._run_selected_group_batch("only_new"))
        self._health_context_menu.add_command(label="Run Group (All)", command=lambda: self._run_selected_group_batch("all"))

        history_lab = ttk.Labelframe(section, text="Watch Event History (Last 50)", style="Section.TLabelframe")
        history_lab.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        self.history_text = scrolledtext.ScrolledText(
            history_lab,
            height=8,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=self.main_app.log_font
        )
        self.history_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _all_portal_names(self):
        names = []
        for config in self.main_app.base_urls_data:
            name = str(config.get("Name", "")).strip()
            if name:
                names.append(name)
        return sorted(set(names))

    def _portal_config_by_name(self, portal_name):
        target = str(portal_name or "").strip().lower()
        for config in self.main_app.base_urls_data:
            if str(config.get("Name", "")).strip().lower() == target:
                return dict(config)
        return None

    def _load_from_settings(self):
        portal_names = self._all_portal_names()
        if portal_names and not self.portal_var.get():
            self.portal_var.set(portal_names[0])

        loaded_rules = self.main_app.settings.get("refresh_watch_portals", [])
        self._portal_rules = {}
        if isinstance(loaded_rules, list):
            for rule in loaded_rules:
                if not isinstance(rule, dict):
                    continue
                name = str(rule.get("name", "")).strip()
                if not name:
                    continue
                try:
                    interval_min = max(1, int(rule.get("interval_min", self.DEFAULT_INTERVAL_MIN)))
                except Exception:
                    interval_min = self.DEFAULT_INTERVAL_MIN
                self._portal_rules[name] = {
                    "enabled": bool(rule.get("enabled", True)),
                    "interval_min": interval_min,
                }

        self._build_portal_alias_map()

        loaded_history = self.main_app.settings.get("refresh_watch_history", [])
        self._history_events = []
        if isinstance(loaded_history, list):
            for event in loaded_history[-self.MAX_HISTORY_EVENTS:]:
                if not isinstance(event, dict):
                    continue
                ts = str(event.get("ts", "")).strip()
                portal = str(event.get("portal", "-")).strip() or "-"
                event_name = str(event.get("event", "INFO")).strip() or "INFO"
                detail = str(event.get("detail", "")).strip()
                self._history_events.append({
                    "ts": ts or datetime.now().strftime("%H:%M:%S"),
                    "portal": portal,
                    "event": event_name,
                    "detail": detail,
                })

    def _record_event(self, portal_name, event_name, detail):
        portal = str(portal_name or "-").strip() or "-"
        item = {
            "ts": datetime.now().strftime("%H:%M:%S"),
            "iso_ts": datetime.now().isoformat(timespec="seconds"),
            "portal": portal,
            "event": str(event_name or "INFO").strip() or "INFO",
            "detail": str(detail or "").strip(),
        }
        self._history_events.append(item)
        if len(self._history_events) > self.MAX_HISTORY_EVENTS:
            self._history_events = self._history_events[-self.MAX_HISTORY_EVENTS:]

        self._append_diagnostics_event(item)

        if self.winfo_exists():
            self.after(0, self._refresh_history_view)

    def _append_diagnostics_event(self, event_item):
        if not self._diagnostics_file:
            return
        try:
            payload = {
                "timestamp": event_item.get("iso_ts"),
                "portal": event_item.get("portal", "-"),
                "event": event_item.get("event", "INFO"),
                "detail": event_item.get("detail", ""),
                "watch_enabled": bool(self.watch_enabled_var.get()),
                "pending_queue": len(self._pending_portals),
            }
            with open(self._diagnostics_file, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            return

    def _export_history_csv(self):
        if not self._history_events:
            gui_utils.show_message("No History", "No watch events available to export.", type="info", parent=self.main_app.root)
            return

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"refresh_watch_history_{stamp}.csv"
        save_path = filedialog.asksaveasfilename(
            parent=self.main_app.root,
            title="Export Watch History CSV",
            initialfile=default_name,
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if not save_path:
            return

        try:
            with open(save_path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=["ts", "iso_ts", "portal", "event", "detail"])
                writer.writeheader()
                for row in self._history_events:
                    writer.writerow({
                        "ts": row.get("ts", ""),
                        "iso_ts": row.get("iso_ts", ""),
                        "portal": row.get("portal", ""),
                        "event": row.get("event", ""),
                        "detail": row.get("detail", ""),
                    })
            self.main_app.update_log(f"[WATCH] History exported: {save_path}")
            self._record_event("-", "EXPORT", f"History CSV exported: {os.path.basename(save_path)}")
        except Exception as export_err:
            gui_utils.show_message("Export Error", f"Failed to export history:\n{export_err}", type="error", parent=self.main_app.root)
            self.main_app.update_log(f"[WATCH] History export failed: {export_err}")

    def _refresh_history_view(self):
        if not hasattr(self, "history_text") or not self.history_text.winfo_exists():
            return
        self.history_text.config(state=tk.NORMAL)
        self.history_text.delete("1.0", tk.END)
        for event in self._history_events:
            line = f"[{event.get('ts', '--:--:--')}][{event.get('portal', '-')}] {event.get('event', 'INFO')} - {event.get('detail', '')}"
            gui_utils.append_styled_log_line(self.history_text, line)
        self.history_text.see(tk.END)
        self.history_text.config(state=tk.DISABLED)

    def _rules_to_list(self):
        rows = []
        for portal_name in sorted(self._portal_rules.keys()):
            rule = self._portal_rules[portal_name]
            rows.append({
                "name": portal_name,
                "enabled": bool(rule.get("enabled", True)),
                "interval_min": int(rule.get("interval_min", self.DEFAULT_INTERVAL_MIN)),
            })
        return rows

    def _save_watch_settings(self, log_message=False):
        self.main_app.settings["refresh_watch_enabled"] = bool(self.watch_enabled_var.get())
        try:
            loop_seconds = max(5, int(float(self.loop_seconds_var.get())))
        except Exception:
            loop_seconds = 30
        self.loop_seconds_var.set(str(loop_seconds))
        self.main_app.settings["refresh_watch_loop_seconds"] = loop_seconds
        self.main_app.settings["refresh_watch_portals"] = self._rules_to_list()
        self.main_app.settings["refresh_watch_state"] = self._watch_state
        self.main_app.settings["refresh_watch_history"] = list(self._history_events[-self.MAX_HISTORY_EVENTS:])
        save_settings(self.main_app.settings, self.main_app.settings_filepath)
        if log_message:
            self.main_app.update_log("[WATCH] Refresh watch settings saved.")

    def _format_ts(self, ts_value):
        try:
            if not ts_value:
                return "--:--:--"
            return datetime.fromtimestamp(float(ts_value)).strftime("%H:%M:%S")
        except Exception:
            return "--:--:--"

    def _refresh_tree(self):
        self._build_portal_alias_map()
        self._refresh_portal_health()

    def _normalize_portal_key(self, portal_name):
        return str(portal_name or "").strip().lower()

    def _build_portal_alias_map(self):
        alias_map = {}
        for config in self.main_app.base_urls_data:
            portal_name = str(config.get("Name", "")).strip()
            if not portal_name:
                continue
            canonical = self._normalize_portal_key(portal_name)
            if not canonical:
                continue

            aliases = {canonical}
            keyword = str(config.get("Keyword", "")).strip().lower()
            if keyword:
                aliases.add(keyword)
                aliases.add(keyword.replace(".", "_").replace("-", "_"))
            base_url = str(config.get("BaseURL", "")).strip()
            if base_url:
                try:
                    key_from_url = str(get_website_keyword_from_url(base_url) or "").strip().lower()
                except Exception:
                    key_from_url = ""
                if key_from_url:
                    aliases.add(key_from_url)
                    aliases.add(key_from_url.replace(".", "_").replace("-", "_"))

            for alias in aliases:
                clean = self._normalize_portal_key(alias)
                if clean:
                    alias_map[clean] = canonical

        for portal_name in list(self._portal_rules.keys()) + list(self._watch_state.keys()):
            clean = self._normalize_portal_key(portal_name)
            if clean and clean not in alias_map:
                alias_map[clean] = clean

        self._portal_alias_map = alias_map

    def _canonical_portal_key(self, portal_name):
        raw = self._normalize_portal_key(portal_name)
        if not raw:
            return ""
        return self._portal_alias_map.get(raw, raw)

    def _display_portal_name(self, portal_key):
        key = self._normalize_portal_key(portal_key)
        if not key:
            return ""
        for config in self.main_app.base_urls_data:
            name = str(config.get("Name", "")).strip()
            if self._normalize_portal_key(name) == key:
                return name
        return portal_key

    def _build_group_membership_map(self):
        group_map = {}
        try:
            groups = self._batch_memory.get_groups()
        except Exception:
            groups = {}

        for group_name, portals in (groups or {}).items():
            clean_group = str(group_name or "").strip()
            if not clean_group:
                continue
            for portal_name in portals or []:
                canonical = self._canonical_portal_key(portal_name)
                if not canonical:
                    continue
                group_map.setdefault(canonical, set()).add(clean_group)

        self._group_membership_map = {
            key: sorted(values)
            for key, values in group_map.items()
        }

    def _groups_for_portal(self, portal_key):
        groups = self._group_membership_map.get(self._canonical_portal_key(portal_key), [])
        if not groups:
            return "-"
        return ", ".join(groups)

    def _load_manifest_last_runs(self):
        if not os.path.exists(self._manifest_path):
            return {}
        try:
            with open(self._manifest_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return {}

        portals = data.get("portals", {}) if isinstance(data, dict) else {}
        if not isinstance(portals, dict):
            return {}

        output = {}
        for portal_name, row in portals.items():
            if not isinstance(row, dict):
                continue
            key = self._canonical_portal_key(portal_name)
            if not key:
                continue
            last_run = str(row.get("last_run", "")).strip()
            if last_run:
                output[key] = last_run
        return output

    def _sqlite_db_path(self):
        candidates = []

        configured = str(self.main_app.settings.get("central_sqlite_db_path", "")).strip()
        if configured:
            candidates.append(configured)
            if not os.path.isabs(configured):
                base_dir = os.path.dirname(self.main_app.settings_filepath)
                candidates.append(os.path.normpath(os.path.join(base_dir, configured)))

        if hasattr(self.main_app, "_get_default_central_sqlite_path"):
            try:
                candidates.append(str(self.main_app._get_default_central_sqlite_path()))
            except Exception:
                pass

        download_var = getattr(self.main_app, "download_dir_var", None)
        download_dir = str(download_var.get() if download_var is not None else "").strip()
        if download_dir:
            candidates.append(os.path.join(download_dir, "blackforest_tenders.sqlite3"))

        workspace_db = os.path.join(os.getcwd(), "blackforest_tenders.sqlite3")
        candidates.append(workspace_db)

        for item in candidates:
            path = str(item or "").strip()
            if path and os.path.exists(path):
                return path
        return ""

    def _selected_health_values(self):
        selected = self.health_tree.selection()
        if not selected:
            return None
        values = self.health_tree.item(selected[0], "values")
        if not values:
            return None
        return values

    def _on_health_right_click(self, event):
        if not self.health_tree.winfo_exists():
            return
        if self._health_context_menu is None:
            return
        row_id = self.health_tree.identify_row(event.y)
        if row_id:
            self.health_tree.selection_set(row_id)
            self.health_tree.focus(row_id)
        try:
            self._health_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._health_context_menu.grab_release()

    def _run_selected_batch(self, scope):
        values = self._selected_health_values()
        if not values:
            gui_utils.show_message("No Selection", "Select a portal row first.", type="warning", parent=self.main_app.root)
            return
        portal_name = str(values[1]).strip()
        if not portal_name:
            return
        batch_tab = self._get_batch_tab()
        if not batch_tab:
            gui_utils.show_message("Unavailable", "Batch tab is not available.", type="warning", parent=self.main_app.root)
            return
        started = batch_tab.start_batch_for_portals(
            [portal_name],
            only_new=(scope == "only_new"),
            mode="sequential",
            max_parallel=1,
            reason=f"dashboard-{scope}"
        )
        if started:
            self._record_event(portal_name, "MANUAL", f"Started {scope} scrape from Dashboard")
        else:
            self._record_event(portal_name, "QUEUE", f"Could not start {scope} scrape (busy)")

    def _run_selected_group_batch(self, scope):
        values = self._selected_health_values()
        if not values:
            gui_utils.show_message("No Selection", "Select a portal row first.", type="warning", parent=self.main_app.root)
            return
        group_text = str(values[0]).strip()
        if not group_text or group_text == "-":
            gui_utils.show_message("No Group", "Selected portal is not part of any saved group.", type="warning", parent=self.main_app.root)
            return

        groups = self._batch_memory.get_groups()
        target_group = group_text.split(",")[0].strip()
        portals = [str(name).strip() for name in groups.get(target_group, []) if str(name).strip()]
        if not portals:
            gui_utils.show_message("No Portals", f"Saved group '{target_group}' has no portals.", type="warning", parent=self.main_app.root)
            return

        batch_tab = self._get_batch_tab()
        if not batch_tab:
            gui_utils.show_message("Unavailable", "Batch tab is not available.", type="warning", parent=self.main_app.root)
            return
        started = batch_tab.start_batch_for_portals(
            portals,
            only_new=(scope == "only_new"),
            mode="sequential",
            max_parallel=1,
            reason=f"dashboard-group-{target_group}-{scope}"
        )
        if started:
            self._record_event(target_group, "GROUP", f"Started {scope} scrape for group '{target_group}' ({len(portals)} portals)")
        else:
            self._record_event(target_group, "GROUP", f"Could not start group run '{target_group}' (busy)")

    def _parse_closing_date(self, text):
        value = str(text or "").strip()
        if not value:
            return None
        parts = [value]
        if " " in value:
            parts.append(value.split(" ", 1)[0])
        if "T" in value:
            parts.append(value.split("T", 1)[0])
        date_formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%d.%m.%Y",
            "%Y/%m/%d",
            "%Y.%m.%d",
        ]
        for part in parts:
            for fmt in date_formats:
                try:
                    return datetime.strptime(part, fmt).date()
                except Exception:
                    continue
        return None

    def _load_portal_stats_from_db(self):
        db_path = self._sqlite_db_path()
        if not db_path:
            return {}, {}

        counts = {}
        last_runs = {}
        try:
            conn = sqlite3.connect(db_path)
            try:
                tender_rows = conn.execute(
                    """
                    SELECT
                        trim(coalesce(portal_name, '')) AS portal_name,
                        trim(coalesce(tender_id_extracted, '')) AS tender_id,
                        lower(trim(coalesce(lifecycle_status, 'active'))) AS lifecycle_status,
                        trim(coalesce(closing_date, '')) AS closing_date
                    FROM tenders
                    WHERE trim(coalesce(tender_id_extracted, '')) <> ''
                    """
                ).fetchall()

                today = datetime.now().date()
                tender_state = {}
                for portal_name, tender_id, lifecycle_status, closing_date in tender_rows:
                    portal_key = self._canonical_portal_key(portal_name)
                    tender_key = str(tender_id or "").strip()
                    if not portal_key or not tender_key:
                        continue

                    is_expired = str(lifecycle_status or "").strip() == "cancelled"
                    if not is_expired:
                        parsed_close = self._parse_closing_date(closing_date)
                        if parsed_close and parsed_close < today:
                            is_expired = True

                    state_key = (portal_key, tender_key)
                    existing = tender_state.get(state_key, False)
                    tender_state[state_key] = bool(existing or is_expired)

                for (portal_key, _tender_key), is_expired in tender_state.items():
                    bucket = counts.setdefault(portal_key, {"live": 0, "expired": 0})
                    if is_expired:
                        bucket["expired"] += 1
                    else:
                        bucket["live"] += 1

                run_rows = conn.execute(
                    """
                    SELECT
                        trim(coalesce(portal_name, '')) AS portal_name,
                        trim(coalesce(completed_at, started_at, '')) AS last_run
                    FROM runs
                    """
                ).fetchall()
                for portal_name, last_run in run_rows:
                    key = self._canonical_portal_key(portal_name)
                    value = str(last_run or "").strip()
                    if not key or not value:
                        continue
                    current = str(last_runs.get(key, "")).strip()
                    if not current or value > current:
                        last_runs[key] = value
            finally:
                conn.close()
        except Exception as error:
            self.main_app.update_log(f"[WATCH] Portal health DB read failed: {error}")
            return {}, {}

        return counts, last_runs

    def _format_iso_ts(self, text):
        raw = str(text or "").strip()
        if not raw:
            return "-"
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return raw[:16]

    def _portal_runtime_status(self, portal_name):
        key = self._canonical_portal_key(portal_name)
        rule = self._portal_rules.get(portal_name, {})
        if not rule:
            for rule_name, rule_value in self._portal_rules.items():
                if self._canonical_portal_key(rule_name) == key:
                    rule = rule_value
                    break
        rule_enabled = bool(rule.get("enabled", True)) if rule else False

        if key in {self._canonical_portal_key(item) for item in self._pending_portals}:
            return "Queued by Watch"

        if getattr(self.main_app, "scraping_in_progress", False):
            status_ctx = getattr(self.main_app, "status_context", {})
            active_portal = str(status_ctx.get("active_portal", "") or "")
            active_set = {
                self._canonical_portal_key(part)
                for part in active_portal.replace("...", "").split(",")
                if str(part).strip()
            }
            if key and key in active_set:
                state = str(status_ctx.get("state", "Running") or "Running")
                return f"Scraping ({state})"

        if rule_enabled and self.watch_enabled_var.get():
            return "Watching"
        if rule and not rule_enabled:
            return "Watch Disabled"
        return "Idle"

    def _refresh_portal_health(self):
        if not hasattr(self, "health_tree") or not self.health_tree.winfo_exists():
            return

        for item in self.health_tree.get_children():
            self.health_tree.delete(item)

        counts_by_portal, db_last_runs = self._load_portal_stats_from_db()
        manifest_last_runs = self._load_manifest_last_runs()
        self._build_group_membership_map()

        key_to_name = {}
        for portal_name in self._all_portal_names():
            key = self._canonical_portal_key(portal_name)
            if key and key not in key_to_name:
                key_to_name[key] = self._display_portal_name(key)
        for portal_name in list(self._portal_rules.keys()) + list(self._watch_state.keys()) + list(self._pending_portals):
            key = self._canonical_portal_key(portal_name)
            if key and key not in key_to_name:
                key_to_name[key] = self._display_portal_name(key)
        for key in list(counts_by_portal.keys()) + list(db_last_runs.keys()) + list(manifest_last_runs.keys()):
            norm_key = self._canonical_portal_key(key)
            if norm_key and norm_key not in key_to_name:
                key_to_name[norm_key] = self._display_portal_name(norm_key)

        all_portal_keys = sorted(key_to_name.keys())

        total_live = 0
        total_expired = 0
        for key in all_portal_keys:
            portal_name = key_to_name.get(key, key)
            counts = counts_by_portal.get(key, {})
            live_count = int(counts.get("live", 0))
            expired_count = int(counts.get("expired", 0))
            total_live += live_count
            total_expired += expired_count

            rule = self._portal_rules.get(portal_name, {})
            if not rule:
                for rule_name, rule_value in self._portal_rules.items():
                    if self._canonical_portal_key(rule_name) == key:
                        rule = rule_value
                        break
            interval_text = str(int(rule.get("interval_min", self.DEFAULT_INTERVAL_MIN)))
            enabled_text = "Yes" if bool(rule.get("enabled", False)) else "No"

            last_run = db_last_runs.get(key) or manifest_last_runs.get(key) or ""
            status_text = self._portal_runtime_status(portal_name)

            self.health_tree.insert(
                "",
                tk.END,
                values=(
                    self._groups_for_portal(key),
                    portal_name,
                    self._format_iso_ts(last_run),
                    live_count,
                    expired_count,
                    enabled_text,
                    interval_text,
                    status_text,
                ),
            )

        self.health_summary_label.config(
            text=f"Portals: {len(all_portal_keys)}   Live: {total_live}   Expired: {total_expired}"
        )
        self._sort_health_tree(self._health_sort_col, preserve=True)

    def _sort_health_tree(self, column, preserve=False):
        if not hasattr(self, "health_tree") or not self.health_tree.winfo_exists():
            return

        if not preserve:
            if self._health_sort_col == column:
                self._health_sort_reverse = not self._health_sort_reverse
            else:
                self._health_sort_col = column
                self._health_sort_reverse = False

        col_index = {"group": 0, "portal": 1, "last_scrape": 2, "live": 3, "expired": 4, "enabled": 5, "interval": 6, "status": 7}
        idx = col_index.get(self._health_sort_col, 0)
        items = []
        for item_id in self.health_tree.get_children():
            values = self.health_tree.item(item_id, "values")
            value = values[idx] if idx < len(values) else ""
            items.append((item_id, value))

        def key_func(entry):
            value = str(entry[1]).strip()
            if self._health_sort_col in {"live", "expired", "interval"}:
                try:
                    return int(value)
                except Exception:
                    return -1
            if self._health_sort_col == "enabled":
                return 1 if value.lower() == "yes" else 0
            if self._health_sort_col == "last_scrape":
                if value in {"", "-"}:
                    return ""
                return value
            return value.lower()

        items.sort(key=key_func, reverse=self._health_sort_reverse)
        for position, (item_id, _value) in enumerate(items):
            self.health_tree.move(item_id, "", position)

    def _schedule_portal_health_refresh(self):
        if self._portal_health_job and self.winfo_exists():
            try:
                self.after_cancel(self._portal_health_job)
            except Exception:
                pass
        if not self.winfo_exists():
            return
        self._refresh_portal_health()
        self._check_daily_batch_completion()
        self._maybe_auto_export_tender84_snapshot()
        self._portal_health_job = self.after(self._portal_health_refresh_ms, self._schedule_portal_health_refresh)

    def _daily_last_run_date(self):
        return str(self.main_app.settings.get("dashboard_daily_last_run_date", "")).strip()

    def _set_daily_last_run_date(self, date_text):
        self.main_app.settings["dashboard_daily_last_run_date"] = str(date_text or "").strip()
        save_settings(self.main_app.settings, self.main_app.settings_filepath)

    def _get_nic_portals_for_daily(self):
        portals = []
        for config in self.main_app.base_urls_data:
            name = str(config.get("Name", "")).strip()
            base_url = str(config.get("BaseURL", "")).strip().lower()
            if not name or not base_url:
                continue
            if "gem.gov.in" in base_url:
                continue
            if ".gov.in" in base_url:
                portals.append(name)
        return sorted(set(portals))

    def _auto_daily_start_if_due(self):
        enabled = bool(self.main_app.settings.get("dashboard_auto_daily_enabled", False))
        if not enabled:
            return
        today = datetime.now().strftime("%Y-%m-%d")
        if self._daily_last_run_date() == today:
            return
        if self.main_app.scraping_in_progress:
            return

        portals = self._get_nic_portals_for_daily()
        if not portals:
            self.main_app.update_log("[DASHBOARD] Daily auto-start skipped: no NIC portals detected.")
            return

        batch_tab = self._get_batch_tab()
        if not batch_tab:
            self.main_app.update_log("[DASHBOARD] Daily auto-start skipped: Batch tab unavailable.")
            return

        started = batch_tab.start_batch_for_portals(
            portals,
            only_new=False,
            mode="sequential",
            max_parallel=1,
            reason="dashboard-daily"
        )
        if started:
            self._daily_batch_active = True
            self._set_daily_last_run_date(today)
            self.main_app.update_log(f"[DASHBOARD] Daily auto batch started for {len(portals)} NIC portal(s).")
            self._record_event("-", "DAILY", f"Auto daily scrape started for {len(portals)} portal(s)")

    def _check_daily_batch_completion(self):
        if not self._daily_batch_active:
            return
        if self.main_app.scraping_in_progress:
            return
        state_text = str(getattr(self.main_app, "status_context", {}).get("state", "") or "").lower()
        if state_text in {"completed", "ready"}:
            self._daily_batch_active = False
            self._record_event("-", "DAILY", "Daily batch completed")
            self._export_tender84_snapshot(force=True)

    def _tender84_export_dir(self):
        configured = str(self.main_app.settings.get("tender84_export_dir", "")).strip()
        if configured:
            return configured
        base_dir = os.path.dirname(self.main_app.settings_filepath)
        return os.path.join(base_dir, "Tender84_Exports")

    def _maybe_auto_export_tender84_snapshot(self):
        enabled = bool(self.main_app.settings.get("tender84_auto_export_enabled", True))
        if not enabled:
            return
        now_epoch = time.time()
        if now_epoch - float(self._last_tender84_export_epoch or 0) < 1800:
            return
        if self.main_app.scraping_in_progress:
            return
        self._export_tender84_snapshot(force=False)

    def _export_tender84_snapshot(self, force=False):
        db_path = self._sqlite_db_path()
        if not db_path or not os.path.exists(db_path):
            return False

        out_dir = self._tender84_export_dir()
        os.makedirs(out_dir, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")
        xlsx_path = os.path.join(out_dir, f"tender84_feed_{today}.xlsx")
        csv_path = os.path.join(out_dir, f"tender84_feed_{today}.csv")

        if not force and os.path.exists(xlsx_path):
            self._last_tender84_export_epoch = time.time()
            return True

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """
                    SELECT
                        trim(coalesce(portal_name, '')) AS portal_name,
                        trim(coalesce(department_name, '')) AS department_name,
                        trim(coalesce(tender_id_extracted, '')) AS tender_id,
                        lower(trim(coalesce(lifecycle_status, 'active'))) AS lifecycle_status,
                        trim(coalesce(cancelled_detected_at, '')) AS cancelled_detected_at,
                        trim(coalesce(closing_date, '')) AS closing_date,
                        trim(coalesce(published_date, '')) AS published_date,
                        trim(coalesce(opening_date, '')) AS opening_date,
                        trim(coalesce(title_ref, '')) AS title_ref,
                        trim(coalesce(organisation_chain, '')) AS organisation_chain,
                        trim(coalesce(emd_amount, '')) AS emd_amount,
                        run_id
                    FROM v_tender_export
                    WHERE trim(coalesce(tender_id_extracted, '')) <> ''
                    """
                ).fetchall()
            finally:
                conn.close()
        except Exception as export_err:
            self.main_app.update_log(f"[DASHBOARD] Tender84 export failed (read): {export_err}")
            return False

        if not rows:
            return False

        deduped = {}
        for row in rows:
            portal_name = str(row["portal_name"] or "").strip()
            tender_id = str(row["tender_id"] or "").strip()
            if not portal_name or not tender_id:
                continue
            key = (self._canonical_portal_key(portal_name), tender_id)
            prev = deduped.get(key)
            if prev is None or int(row["run_id"] or 0) >= int(prev["run_id"] or 0):
                deduped[key] = dict(row)

        cutoff_date = datetime.now().date() - timedelta(days=30)
        export_rows = []
        for row in deduped.values():
            closing_date = self._parse_closing_date(row.get("closing_date"))
            cancelled_ts = self._parse_closing_date(str(row.get("cancelled_detected_at", "")).split("T", 1)[0])
            lifecycle_status = str(row.get("lifecycle_status") or "active").strip().lower()

            is_expired = lifecycle_status == "cancelled"
            if not is_expired and closing_date is not None and closing_date < datetime.now().date():
                is_expired = True

            include_row = False
            if not is_expired:
                include_row = True
            else:
                base_date = closing_date or cancelled_ts
                if base_date and base_date >= cutoff_date:
                    include_row = True

            if include_row:
                row_out = {
                    "Portal": row.get("portal_name", ""),
                    "Department": row.get("department_name", ""),
                    "Tender ID": row.get("tender_id", ""),
                    "Status": "Expired" if is_expired else "Live",
                    "Published Date": row.get("published_date", ""),
                    "Closing Date": row.get("closing_date", ""),
                    "Opening Date": row.get("opening_date", ""),
                    "Title": row.get("title_ref", ""),
                    "Organisation": row.get("organisation_chain", ""),
                    "EMD": row.get("emd_amount", ""),
                }
                export_rows.append(row_out)

        if not export_rows:
            return False

        try:
            if pd is not None:
                pd.DataFrame(export_rows).to_excel(xlsx_path, index=False)
                output_path = xlsx_path
            else:
                with open(csv_path, "w", newline="", encoding="utf-8-sig") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(export_rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(export_rows)
                output_path = csv_path
        except Exception as export_err:
            self.main_app.update_log(f"[DASHBOARD] Tender84 export failed (write): {export_err}")
            return False

        self._last_tender84_export_epoch = time.time()
        self.main_app.update_log(f"[DASHBOARD] Tender84 export updated: {output_path}")
        self._record_event("-", "EXPORT", f"Tender84 snapshot updated ({Path(output_path).name})")
        return True

    def _on_rule_selected(self, _event=None):
        selected = self.health_tree.selection()
        if not selected:
            return
        values = self.health_tree.item(selected[0], "values")
        if not values:
            return
        portal_name = str(values[1])
        rule = self._portal_rules.get(portal_name, {})
        if not rule:
            for rule_name, rule_value in self._portal_rules.items():
                if self._canonical_portal_key(rule_name) == self._canonical_portal_key(portal_name):
                    rule = rule_value
                    break
        self.portal_var.set(portal_name)
        self.interval_var.set(str(int(rule.get("interval_min", self.DEFAULT_INTERVAL_MIN))))
        self.enabled_var.set(bool(rule.get("enabled", False)))

    def _add_or_update_rule(self):
        portal_name = str(self.portal_var.get() or "").strip()
        if not portal_name:
            gui_utils.show_message("Missing Portal", "Select a portal first.", type="warning", parent=self.main_app.root)
            return

        try:
            interval_min = max(1, int(float(self.interval_var.get())))
        except Exception:
            gui_utils.show_message("Invalid Interval", "Interval must be a number in minutes.", type="warning", parent=self.main_app.root)
            return

        canonical = self._canonical_portal_key(portal_name)
        display_name = self._display_portal_name(canonical) if canonical else portal_name
        self._portal_rules[display_name] = {
            "enabled": bool(self.enabled_var.get()),
            "interval_min": interval_min,
        }
        self._watch_state.setdefault(display_name, {}).setdefault("status", "Waiting")
        self._record_event(display_name, "RULE", f"Rule updated (enabled={bool(self.enabled_var.get())}, interval={interval_min}m)")
        self._refresh_tree()
        self._save_watch_settings(log_message=True)

    def _remove_selected_rule(self):
        selected = self.health_tree.selection()
        if not selected:
            return
        values = self.health_tree.item(selected[0], "values")
        if not values:
            return
        portal_name = str(values[1])
        key = self._canonical_portal_key(portal_name)
        target_name = None
        for rule_name in self._portal_rules.keys():
            if self._canonical_portal_key(rule_name) == key:
                target_name = rule_name
                break
        if not target_name:
            target_name = portal_name

        self._portal_rules[target_name] = {
            "enabled": False,
            "interval_min": self.DEFAULT_INTERVAL_MIN,
        }
        self._watch_state.setdefault(target_name, {}).setdefault("status", "Watch Disabled")
        self._pending_portals.discard(portal_name)
        self._record_event(target_name, "RULE", "Rule disabled")
        self._refresh_tree()
        self._save_watch_settings(log_message=True)

    def _set_portal_status(self, portal_name, status_text, checked=False, changed=False):
        state = self._watch_state.setdefault(portal_name, {})
        state["status"] = str(status_text)
        now_epoch = time.time()
        if checked:
            state["last_check_epoch"] = now_epoch
        if changed:
            state["last_change_epoch"] = now_epoch

        self._record_event(portal_name, "STATUS", str(status_text))

        if self.winfo_exists():
            self.after(0, self._refresh_tree)

    def _compute_department_signature(self, departments):
        normalized = []
        for dept in departments or []:
            s_no = str(dept.get("s_no", "")).strip()
            name = str(dept.get("name", "")).strip().lower()
            count_text = str(dept.get("count_text", "")).strip()
            if not s_no and not name:
                continue
            if name in ["organisation name", "department name", "organization", "organization name"]:
                continue
            normalized.append((s_no, name, count_text))

        normalized.sort()
        payload = json.dumps(normalized, ensure_ascii=False)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest(), len(normalized)

    def _check_portal_for_change(self, portal_name):
        portal_cfg = self._portal_config_by_name(portal_name)
        if not portal_cfg:
            self._set_portal_status(portal_name, "Config not found", checked=True)
            return False

        org_url = portal_cfg.get("OrgListURL")
        if not org_url:
            self._set_portal_status(portal_name, "Org list URL missing", checked=True)
            return False

        def _watch_log(msg):
            self.main_app.update_log(f"[WATCH:{portal_name}] {msg}")

        departments, _ = fetch_department_list_from_site_v2(org_url, _watch_log)
        if not departments:
            self._set_portal_status(portal_name, "No departments fetched", checked=True)
            return False

        signature, dept_count = self._compute_department_signature(departments)
        state = self._watch_state.setdefault(portal_name, {})
        previous = str(state.get("signature", "")).strip()
        state["signature"] = signature
        state["department_count"] = dept_count

        if not previous:
            self._set_portal_status(portal_name, f"Baseline captured ({dept_count} depts)", checked=True)
            return False

        if previous != signature:
            self._set_portal_status(portal_name, f"Change detected ({dept_count} depts)", checked=True, changed=True)
            self._record_event(portal_name, "CHANGE", f"Signature changed, departments={dept_count}")
            return True

        self._set_portal_status(portal_name, f"No change ({dept_count} depts)", checked=True)
        self._record_event(portal_name, "CHECK", f"No change, departments={dept_count}")
        return False

    def _get_batch_tab(self):
        frame = self.main_app.section_frames.get("Batch Scrape")
        if not frame or not frame.winfo_children():
            return None
        return frame.winfo_children()[0]

    def _trigger_scrape_for_portal(self, portal_name):
        batch_tab = self._get_batch_tab()
        if not batch_tab or not hasattr(batch_tab, "start_batch_for_portals"):
            self._set_portal_status(portal_name, "Batch tab unavailable", checked=False)
            return False

        started = batch_tab.start_batch_for_portals(
            [portal_name],
            only_new=False,
            mode="sequential",
            max_parallel=1,
            reason="change-detected"
        )
        if started:
            self._set_portal_status(portal_name, "Triggered full scrape", checked=False, changed=True)
            self.main_app.update_log(f"[WATCH] Triggered full scrape for {portal_name} due to detected change.")
            self._record_event(portal_name, "TRIGGER", "Triggered full scrape")
            return True

        self._set_portal_status(portal_name, "Queued (runner busy)", checked=False)
        self._record_event(portal_name, "QUEUE", "Runner busy; queued")
        return False

    def _run_selected_now(self):
        selected = self.health_tree.selection()
        if not selected:
            gui_utils.show_message("No Selection", "Select a portal row first.", type="warning", parent=self.main_app.root)
            return
        values = self.health_tree.item(selected[0], "values")
        if not values:
            return
        portal_name = str(values[1])
        self._pending_portals.add(portal_name)
        self.main_app.update_log(f"[WATCH] Manual trigger queued for {portal_name}.")
        self._record_event(portal_name, "MANUAL", "Manual trigger queued")

    def _watcher_loop(self):
        while not self._watch_stop_event.is_set():
            try:
                try:
                    loop_seconds = max(5, int(float(self.loop_seconds_var.get())))
                except Exception:
                    loop_seconds = 30

                if not self.main_app.scraping_in_progress and self._pending_portals:
                    portal_name = sorted(self._pending_portals)[0]
                    self._pending_portals.discard(portal_name)
                    started = self._trigger_scrape_for_portal(portal_name)
                    if not started:
                        self._pending_portals.add(portal_name)

                now_epoch = time.time()
                if not self.main_app.scraping_in_progress:
                    for portal_name, rule in list(self._portal_rules.items()):
                        if not rule.get("enabled", True):
                            continue

                        interval_sec = max(60, int(rule.get("interval_min", 60)) * 60)
                        state = self._watch_state.setdefault(portal_name, {})
                        last_check = float(state.get("last_check_epoch", 0) or 0)
                        if now_epoch - last_check < interval_sec:
                            continue

                        self._set_portal_status(portal_name, "Checking for changes...", checked=False)
                        changed = self._check_portal_for_change(portal_name)
                        if changed:
                            self._pending_portals.add(portal_name)
                self._save_watch_settings(log_message=False)
                if self._watch_stop_event.wait(loop_seconds):
                    break
            except Exception as watch_err:
                self.main_app.update_log(f"[WATCH] Watch loop error: {watch_err}")
                self._record_event("-", "ERROR", f"Watch loop error: {watch_err}")
                if self._watch_stop_event.wait(10):
                    break

        if self.winfo_exists():
            self.after(0, lambda: self.watch_state_label.config(text="Watcher: Stopped"))

    def start_watch(self, auto=False):
        if self._watch_thread and self._watch_thread.is_alive():
            if not auto:
                self.main_app.update_log("[WATCH] Watcher already running.")
            return

        enabled_rules = [r for r in self._portal_rules.values() if bool(r.get("enabled", False))]
        if not enabled_rules:
            if not auto:
                gui_utils.show_message("No Rules", "Enable at least one portal in Portal Health first.", type="warning", parent=self.main_app.root)
            return

        self.watch_enabled_var.set(True)
        self._watch_stop_event.clear()
        self._watch_thread = threading.Thread(target=self._watcher_loop, name="RefreshWatch", daemon=True)
        self._watch_thread.start()
        self.watch_state_label.config(text="Watcher: Running")
        self._record_event("-", "WATCHER", "Watcher started")
        self._save_watch_settings(log_message=True)
        if not auto:
            self.main_app.update_log("[WATCH] Watcher started.")

    def stop_watch(self):
        self.watch_enabled_var.set(False)
        self._watch_stop_event.set()
        self.watch_state_label.config(text="Watcher: Stopping...")
        self._record_event("-", "WATCHER", "Watcher stop requested")
        self._save_watch_settings(log_message=True)
        self.main_app.update_log("[WATCH] Watcher stop requested.")

    def shutdown(self):
        self._watch_stop_event.set()
        if self._portal_health_job and self.winfo_exists():
            try:
                self.after_cancel(self._portal_health_job)
            except Exception:
                pass
            self._portal_health_job = None

    def set_controls_state(self, state):
        widgets = [
            self.start_watch_button,
            self.stop_watch_button,
            self.save_watch_button,
            self.export_history_button,
            self.add_update_button,
            self.remove_rule_button,
            self.run_now_button,
            self.health_tree,
            self.history_text,
            self.refresh_health_button,
        ]
        for widget in widgets:
            try:
                widget.configure(state=state)
            except Exception:
                pass
