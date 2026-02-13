import hashlib
import json
import os
import csv
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk, scrolledtext, filedialog
from typing import Literal

from app_settings import save_settings
from gui import gui_utils
from scraper.logic import fetch_department_list_from_site_v2


class RefreshWatchTab(ttk.Frame):
    """Portal refresh scheduler with change detection and auto-triggered full scrape."""

    MAX_HISTORY_EVENTS = 50

    def __init__(self, parent, main_app_ref, **kwargs):
        super().__init__(parent, **kwargs)
        self.main_app = main_app_ref

        self.watch_enabled_var = tk.BooleanVar(value=bool(self.main_app.settings.get("refresh_watch_enabled", False)))
        self.loop_seconds_var = tk.StringVar(value=str(self.main_app.settings.get("refresh_watch_loop_seconds", 30)))

        self.portal_var = tk.StringVar(value="")
        self.interval_var = tk.StringVar(value="60")
        self.enabled_var = tk.BooleanVar(value=True)

        self._watch_thread = None
        self._watch_stop_event = threading.Event()
        self._pending_portals = set()
        self._portal_rules = {}
        self._watch_state = dict(self.main_app.settings.get("refresh_watch_state", {}) or {})
        self._history_events = []
        self._diagnostics_file = None

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

        if self.watch_enabled_var.get():
            self.start_watch(auto=True)

    def _create_widgets(self):
        section = ttk.Labelframe(self, text="Refresh Watch (Change-Triggered Scrape)", style="Section.TLabelframe")
        section.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        top = ttk.Frame(section)
        top.pack(fill=tk.X, padx=5, pady=(8, 6))

        ttk.Label(top, text="Check Every (sec):", font=self.main_app.label_font).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(top, textvariable=self.loop_seconds_var, width=8).pack(side=tk.LEFT, padx=(0, 10))

        self.start_watch_button = ttk.Button(top, text="Start Watch", style="Accent.TButton", width=14, command=self.start_watch)
        self.start_watch_button.pack(side=tk.LEFT, padx=(0, 6))
        self.stop_watch_button = ttk.Button(top, text="Stop Watch", width=14, command=self.stop_watch)
        self.stop_watch_button.pack(side=tk.LEFT, padx=(0, 6))
        self.save_watch_button = ttk.Button(top, text="Save Watch Settings", width=18, command=self._save_watch_settings)
        self.save_watch_button.pack(side=tk.LEFT, padx=(0, 6))
        self.export_history_button = ttk.Button(top, text="Export History CSV", width=18, command=self._export_history_csv)
        self.export_history_button.pack(side=tk.LEFT, padx=(0, 6))

        self.watch_state_label = ttk.Label(top, text="Watcher: Stopped", font=self.main_app.label_font)
        self.watch_state_label.pack(side=tk.LEFT, padx=(10, 0))

        cfg = ttk.Labelframe(section, text="Portal Rule", style="Section.TLabelframe")
        cfg.pack(fill=tk.X, padx=5, pady=(4, 8))

        ttk.Label(cfg, text="Portal:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.portal_combo = ttk.Combobox(cfg, textvariable=self.portal_var, state="readonly", width=42)
        self.portal_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(cfg, text="Interval (min):").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ttk.Entry(cfg, textvariable=self.interval_var, width=8).grid(row=0, column=3, padx=5, pady=5, sticky="w")

        ttk.Checkbutton(cfg, text="Enabled", variable=self.enabled_var).grid(row=0, column=4, padx=10, pady=5, sticky="w")

        self.add_update_button = ttk.Button(cfg, text="Add/Update", width=12, command=self._add_or_update_rule)
        self.add_update_button.grid(row=0, column=5, padx=5, pady=5)
        self.remove_rule_button = ttk.Button(cfg, text="Remove", width=10, command=self._remove_selected_rule)
        self.remove_rule_button.grid(row=0, column=6, padx=5, pady=5)
        self.run_now_button = ttk.Button(cfg, text="Run Selected Now", width=16, command=self._run_selected_now)
        self.run_now_button.grid(row=0, column=7, padx=5, pady=5)

        cfg.columnconfigure(1, weight=1)

        tree_lab = ttk.Labelframe(section, text="Watched Portals", style="Section.TLabelframe")
        tree_lab.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        self.watch_tree = ttk.Treeview(
            tree_lab,
            columns=("portal", "enabled", "interval", "last_check", "last_change", "status"),
            show="headings",
            height=10
        )
        AnchorType = Literal["nw", "n", "ne", "w", "center", "e", "sw", "s", "se"]
        columns: list[tuple[str, str, int, AnchorType]] = [
            ("portal", "Portal", 260, "w"),
            ("enabled", "Enabled", 80, "center"),
            ("interval", "Interval(min)", 100, "center"),
            ("last_check", "Last Check", 120, "center"),
            ("last_change", "Last Change", 120, "center"),
            ("status", "Status", 300, "w"),
        ]
        for col, text, width, anchor in columns:
            self.watch_tree.heading(col, text=text)
            self.watch_tree.column(col, width=width, anchor=anchor)
        self.watch_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.watch_tree.bind("<<TreeviewSelect>>", self._on_rule_selected)

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
        self.portal_combo["values"] = portal_names
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
                    interval_min = max(1, int(rule.get("interval_min", 60)))
                except Exception:
                    interval_min = 60
                self._portal_rules[name] = {
                    "enabled": bool(rule.get("enabled", True)),
                    "interval_min": interval_min,
                }

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
                "interval_min": int(rule.get("interval_min", 60)),
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
        for item in self.watch_tree.get_children():
            self.watch_tree.delete(item)

        for portal_name in sorted(self._portal_rules.keys()):
            rule = self._portal_rules[portal_name]
            state = self._watch_state.get(portal_name, {}) if isinstance(self._watch_state, dict) else {}
            enabled_text = "Yes" if rule.get("enabled", True) else "No"
            interval_min = int(rule.get("interval_min", 60))
            self.watch_tree.insert(
                "",
                tk.END,
                values=(
                    portal_name,
                    enabled_text,
                    interval_min,
                    self._format_ts(state.get("last_check_epoch")),
                    self._format_ts(state.get("last_change_epoch")),
                    str(state.get("status", "Waiting"))[:280],
                )
            )

    def _on_rule_selected(self, _event=None):
        selected = self.watch_tree.selection()
        if not selected:
            return
        values = self.watch_tree.item(selected[0], "values")
        if not values:
            return
        portal_name = str(values[0])
        rule = self._portal_rules.get(portal_name, {})
        self.portal_var.set(portal_name)
        self.interval_var.set(str(rule.get("interval_min", 60)))
        self.enabled_var.set(bool(rule.get("enabled", True)))

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

        self._portal_rules[portal_name] = {
            "enabled": bool(self.enabled_var.get()),
            "interval_min": interval_min,
        }
        self._watch_state.setdefault(portal_name, {}).setdefault("status", "Waiting")
        self._record_event(portal_name, "RULE", f"Rule updated (enabled={bool(self.enabled_var.get())}, interval={interval_min}m)")
        self._refresh_tree()
        self._save_watch_settings(log_message=True)

    def _remove_selected_rule(self):
        selected = self.watch_tree.selection()
        if not selected:
            return
        values = self.watch_tree.item(selected[0], "values")
        if not values:
            return
        portal_name = str(values[0])
        self._portal_rules.pop(portal_name, None)
        self._watch_state.pop(portal_name, None)
        self._pending_portals.discard(portal_name)
        self._record_event(portal_name, "RULE", "Rule removed")
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
        selected = self.watch_tree.selection()
        if not selected:
            gui_utils.show_message("No Selection", "Select a watched portal row first.", type="warning", parent=self.main_app.root)
            return
        values = self.watch_tree.item(selected[0], "values")
        if not values:
            return
        portal_name = str(values[0])
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

        if not self._portal_rules:
            if not auto:
                gui_utils.show_message("No Rules", "Add at least one watched portal rule first.", type="warning", parent=self.main_app.root)
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

    def set_controls_state(self, state):
        widgets = [
            self.start_watch_button,
            self.stop_watch_button,
            self.save_watch_button,
            self.export_history_button,
            self.add_update_button,
            self.remove_rule_button,
            self.run_now_button,
            self.portal_combo,
            self.watch_tree,
            self.history_text,
        ]
        for widget in widgets:
            try:
                widget.configure(state=state)
            except Exception:
                pass
