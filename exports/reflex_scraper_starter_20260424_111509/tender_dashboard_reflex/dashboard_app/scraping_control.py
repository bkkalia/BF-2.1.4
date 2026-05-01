# pyright: reportArgumentType=false, reportCallIssue=false, reportAttributeAccessIssue=false
"""
Scraping Control Page - Real-time tender scraping with process-based workers.
"""

import asyncio
import json
import logging
import queue as py_queue
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import reflex as rx
from pydantic import BaseModel

from .visuals.scraping_hero_visuals import hero_visual_section

logger = logging.getLogger(__name__)

# Module-level reference to the active ScrapingWorkerManager so that
# stop_scraping() can terminate worker processes from a different async task.
_active_manager = None


class WorkerStatus(BaseModel):
    """Status for a single worker process."""

    worker_id: int = 0
    worker_name: str = ""
    status: str = "idle"  # idle, running, completed, failed
    portal_name: str = ""
    current_department: str = ""
    department_name: str = ""
    dept_current: int = 0
    dept_total: int = 0
    expected_departments: int = 0
    tenders_found: int = 0
    expected_tenders: int = 0
    tender_percent: int = 0
    pending_depts: int = 0
    progress_percent: int = 0
    skipped_existing: int = 0
    last_update: str = ""
    portal_ip: str = ""


class ScrapingControlState(rx.State):
    """State management for scraping control page."""

    available_portals: List[Dict[str, str]] = []
    selected_portals: List[str] = []

    worker_count: int = 2
    worker_names: List[str] = ["Worker 1", "Worker 2", "Worker 3", "Worker 4"]
    js_batch_threshold: int = 300  # Trigger batched extraction for departments with 300+ rows
    js_batch_size: int = 2000  # Extract rows in batches of this size
    settings_saved: bool = False  # Track if settings have been saved

    workers: List[WorkerStatus] = []

    is_scraping: bool = False
    scraping_start_time: Optional[str] = None
    elapsed_seconds: int = 0  # Track elapsed time in seconds

    log_messages: List[str] = []
    max_log_messages: int = 100

    total_tenders_found: int = 0
    total_departments_processed: int = 0
    total_portals_completed: int = 0
    total_skipped_existing: int = 0
    total_closing_date_reprocessed: int = 0

    run_portals_all: List[str] = []
    completed_portals: List[str] = []
    portal_progress: Dict[str, Dict] = {}

    resume_mode: bool = False
    resume_base_tenders: int = 0
    resume_base_departments: int = 0
    resume_base_portals: int = 0
    resume_base_skipped_existing: int = 0
    resume_base_closing_date_reprocessed: int = 0

    checkpoint_available: bool = False
    checkpoint_remaining_portals: int = 0
    checkpoint_summary: str = ""

    auto_refresh_enabled: bool = False
    last_refresh: str = ""

    # Portal status management
    portal_status_list: List[Dict] = []
    portal_sort_by: str = "status"  # status, name, tenders, date
    portal_filter: str = "all"  # all, scraped, pending
    portal_search_query: str = ""
    show_portal_dashboard: bool = True

    # Completion webhook – called once when scraping finishes
    webhook_enabled: bool = False
    completion_webhook_url: str = ""
    completion_webhook_secret: str = ""   # sent as X-BF-Secret header

    # Telegram notification
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Local post-scrape script (full path to .py file, optional CLI args)
    post_scrape_script_enabled: bool = False
    post_scrape_script: str = ""
    post_scrape_script_args: str = ""   # e.g. --mode data --env prod

    # Dry-run / test busy flags for automation buttons
    test_script_running: bool = False
    test_telegram_running: bool = False
    test_webhook_running: bool = False

    # ── Enhanced Telegram options ──────────────────────────────────────
    telegram_per_portal_alert: bool = False   # optional per-portal done alert
    telegram_error_alert: bool = True          # alert on scraping error

    # ── Scheduled auto-scrape ──────────────────────────────────────────
    scheduler_enabled: bool = False
    scheduler_hour: str = "2"     # 0-23
    scheduler_minute: str = "0"   # 0-59
    scheduler_portals: str = ""   # comma-separated portal names; blank = all

    # ── Health watchdog ────────────────────────────────────────────────
    watchdog_enabled: bool = True
    watchdog_stall_minutes: int = 15   # alert if no tenders/depts update for this many minutes
    _watchdog_last_tenders: int = 0
    _watchdog_last_depts: int = 0
    _watchdog_last_change_ts: str = ""  # ISO timestamp of last progress change

    def _settings_file_candidates(self) -> List[Path]:
        """Candidate locations for shared settings file."""
        project_root = Path(__file__).resolve().parents[2]
        dashboard_root = Path(__file__).resolve().parents[1]
        return [
            project_root / "portal_config_memory.json",
            dashboard_root / "portal_config_memory.json",
            Path.cwd() / "portal_config_memory.json",
        ]

    def _settings_file_path(self) -> Path:
        """Canonical settings path with automatic migration from legacy locations."""
        candidates = self._settings_file_candidates()
        canonical = candidates[0]

        for existing in candidates:
            if existing.exists():
                if existing != canonical and not canonical.exists():
                    try:
                        canonical.write_text(existing.read_text(encoding="utf-8"), encoding="utf-8")
                    except Exception:
                        return existing
                return canonical

        return canonical

    def on_load(self):
        """Load saved worker settings and portal status when page loads"""
        try:
            config_path = self._settings_file_path()
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    if "worker_count" in config_data:
                        self.worker_count = int(config_data["worker_count"])
                    if "worker_names" in config_data and isinstance(config_data["worker_names"], list):
                        self.worker_names = config_data["worker_names"][:]
                    if "js_batch_threshold" in config_data:
                        self.js_batch_threshold = int(config_data["js_batch_threshold"])
                    if "js_batch_size" in config_data:
                        self.js_batch_size = int(config_data["js_batch_size"])
                    if "webhook_enabled" in config_data:
                        self.webhook_enabled = bool(config_data["webhook_enabled"])
                    if "completion_webhook_url" in config_data:
                        self.completion_webhook_url = str(config_data["completion_webhook_url"])
                    if "completion_webhook_secret" in config_data:
                        self.completion_webhook_secret = str(config_data["completion_webhook_secret"])
                    if "telegram_enabled" in config_data:
                        self.telegram_enabled = bool(config_data["telegram_enabled"])
                    if "telegram_bot_token" in config_data:
                        self.telegram_bot_token = str(config_data["telegram_bot_token"])
                    if "telegram_chat_id" in config_data:
                        self.telegram_chat_id = str(config_data["telegram_chat_id"])
                    if "post_scrape_script_enabled" in config_data:
                        self.post_scrape_script_enabled = bool(config_data["post_scrape_script_enabled"])
                    if "post_scrape_script" in config_data:
                        self.post_scrape_script = str(config_data["post_scrape_script"])
                    if "post_scrape_script_args" in config_data:
                        self.post_scrape_script_args = str(config_data["post_scrape_script_args"])
                    if "telegram_per_portal_alert" in config_data:
                        self.telegram_per_portal_alert = bool(config_data["telegram_per_portal_alert"])
                    if "telegram_error_alert" in config_data:
                        self.telegram_error_alert = bool(config_data["telegram_error_alert"])
                    if "scheduler_enabled" in config_data:
                        self.scheduler_enabled = bool(config_data["scheduler_enabled"])
                    if "scheduler_hour" in config_data:
                        self.scheduler_hour = str(config_data["scheduler_hour"])
                    if "scheduler_minute" in config_data:
                        self.scheduler_minute = str(config_data["scheduler_minute"])
                    if "scheduler_portals" in config_data:
                        self.scheduler_portals = str(config_data["scheduler_portals"])
                    if "watchdog_enabled" in config_data:
                        self.watchdog_enabled = bool(config_data["watchdog_enabled"])
                    if "watchdog_stall_minutes" in config_data:
                        self.watchdog_stall_minutes = int(config_data["watchdog_stall_minutes"])
            
            # Load portal status from database
            self._load_portal_status()
        except Exception as e:
            logger.warning(f"Could not load worker settings: {e}")

    @rx.var
    def global_expected_departments(self) -> int:
        return sum(max(w.expected_departments, w.dept_total) for w in self.workers)

    @rx.var
    def global_expected_tenders(self) -> int:
        return sum(w.expected_tenders for w in self.workers)

    @rx.var
    def global_department_percent(self) -> int:
        expected = self.global_expected_departments
        if expected <= 0:
            return 0
        current = sum(w.dept_current for w in self.workers)
        return min(100, int((current / expected) * 100))

    @rx.var
    def global_tender_percent(self) -> int:
        expected = self.global_expected_tenders
        if expected <= 0:
            return 0
        current = sum(w.tenders_found for w in self.workers)
        return min(100, int((current / expected) * 100))

    @rx.var
    def active_workers(self) -> int:
        return len([w for w in self.workers if w.status != "idle"])

    @rx.var
    def extended_unique_this_run(self) -> int:
        """Unique changed tender IDs counted in the active run.
        In resume mode, exclude checkpoint baseline so this reflects current run only.
        """
        if self.resume_mode:
            return max(0, int(self.total_closing_date_reprocessed) - int(self.resume_base_closing_date_reprocessed))
        return max(0, int(self.total_closing_date_reprocessed))

    @rx.var
    def has_checkpoint(self) -> bool:
        return self.checkpoint_available

    @rx.var
    def elapsed_time_formatted(self) -> str:
        """Format elapsed time as HH:MM:SS"""
        hours = self.elapsed_seconds // 3600
        minutes = (self.elapsed_seconds % 3600) // 60
        seconds = self.elapsed_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @rx.var
    def tenders_per_minute(self) -> str:
        """Calculate tenders processed per minute"""
        if self.elapsed_seconds < 10 or self.total_tenders_found == 0:
            return "0.0"
        rate = (self.total_tenders_found / self.elapsed_seconds) * 60
        return f"{rate:.1f}"

    @rx.var
    def departments_per_minute(self) -> str:
        """Calculate departments processed per minute"""
        if self.elapsed_seconds < 10 or self.total_departments_processed == 0:
            return "0.0"
        rate = (self.total_departments_processed / self.elapsed_seconds) * 60
        return f"{rate:.1f}"

    async def save_worker_settings(self):
        """Save worker count and names to persistent config"""
        try:
            # Save to portal_config_memory for persistence
            import json
            config_path = self._settings_file_path()
            
            config_data = {}
            if config_path.exists():
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                except:
                    config_data = {}
            
            config_data["worker_count"] = self.worker_count
            config_data["worker_names"] = self.worker_names[:]
            config_data["js_batch_threshold"] = self.js_batch_threshold
            config_data["js_batch_size"] = self.js_batch_size
            config_data["webhook_enabled"] = self.webhook_enabled
            config_data["completion_webhook_url"] = self.completion_webhook_url
            config_data["completion_webhook_secret"] = self.completion_webhook_secret
            config_data["telegram_enabled"] = self.telegram_enabled
            config_data["telegram_bot_token"] = self.telegram_bot_token
            config_data["telegram_chat_id"] = self.telegram_chat_id
            config_data["post_scrape_script_enabled"] = self.post_scrape_script_enabled
            config_data["post_scrape_script"] = self.post_scrape_script
            config_data["post_scrape_script_args"] = self.post_scrape_script_args
            config_data["telegram_per_portal_alert"] = self.telegram_per_portal_alert
            config_data["telegram_error_alert"] = self.telegram_error_alert
            config_data["scheduler_enabled"] = self.scheduler_enabled
            config_data["scheduler_hour"] = self.scheduler_hour
            config_data["scheduler_minute"] = self.scheduler_minute
            config_data["scheduler_portals"] = self.scheduler_portals
            config_data["watchdog_enabled"] = self.watchdog_enabled
            config_data["watchdog_stall_minutes"] = self.watchdog_stall_minutes
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)
            
            self.settings_saved = True
            self.add_log(f"💾 Settings saved: {self.worker_count} workers, batch threshold: {self.js_batch_threshold}, batch size: {self.js_batch_size}")
            await asyncio.sleep(2)
            self.settings_saved = False
        except Exception as e:
            self.add_log(f"❌ Failed to save settings: {str(e)}")

    def set_webhook_enabled(self, value: bool):
        self.webhook_enabled = value

    def set_completion_webhook_url(self, value: str):
        self.completion_webhook_url = value.strip()

    def set_completion_webhook_secret(self, value: str):
        self.completion_webhook_secret = value.strip()

    def set_telegram_enabled(self, value: bool):
        self.telegram_enabled = value

    def set_telegram_bot_token(self, value: str):
        self.telegram_bot_token = value.strip()

    def set_telegram_chat_id(self, value: str):
        self.telegram_chat_id = value.strip()

    def set_post_scrape_script_enabled(self, value: bool):
        self.post_scrape_script_enabled = value

    def set_post_scrape_script(self, value: str):
        self.post_scrape_script = value.strip()

    def set_post_scrape_script_args(self, value: str):
        self.post_scrape_script_args = value

    def set_telegram_per_portal_alert(self, value: bool):
        self.telegram_per_portal_alert = value

    def set_telegram_error_alert(self, value: bool):
        self.telegram_error_alert = value

    def set_scheduler_enabled(self, value: bool):
        self.scheduler_enabled = value

    def set_scheduler_hour(self, value: str):
        self.scheduler_hour = value.strip()

    def set_scheduler_minute(self, value: str):
        self.scheduler_minute = value.strip()

    def set_scheduler_portals(self, value: str):
        self.scheduler_portals = value

    def set_watchdog_enabled(self, value: bool):
        self.watchdog_enabled = value

    def set_watchdog_stall_minutes(self, value: str):
        try:
            self.watchdog_stall_minutes = max(5, min(120, int(value)))
        except Exception:
            self.watchdog_stall_minutes = 15

    # ── Internal helpers ───────────────────────────────────────────────

    def _tg_escape(self, text: str) -> str:
        """Escape MarkdownV2 special characters."""
        for ch in r"\_*[]()~`>#+-=|{}.!":
            text = text.replace(ch, f"\\{ch}")
        return text

    def _tg_send_sync(self, token: str, chat_id: str, text: str) -> None:
        """Synchronous Telegram send — call via asyncio.to_thread. Raises on failure."""
        import urllib.request as _ur
        import json as _json
        api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = _json.dumps({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "MarkdownV2",
        }).encode("utf-8")
        req = _ur.Request(
            api_url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _ur.urlopen(req, timeout=15) as resp:
            _ = resp.read()

    async def _fire_completion_webhook(self):
        """POST a JSON summary to completion_webhook_url. Retries once on failure."""
        if not self.webhook_enabled:
            return
        url = self.completion_webhook_url.strip()
        if not url:
            return
        elapsed_h = self.elapsed_seconds // 3600
        elapsed_m = (self.elapsed_seconds % 3600) // 60
        elapsed_s = self.elapsed_seconds % 60
        payload = {
            "event": "scraping_completed",
            "timestamp": datetime.now().isoformat(),
            "total_tenders": self.total_tenders_found,
            "total_departments": self.total_departments_processed,
            "total_portals": self.total_portals_completed,
            "skipped_existing": self.total_skipped_existing,
            "elapsed_seconds": self.elapsed_seconds,
            "elapsed_formatted": f"{elapsed_h:02d}:{elapsed_m:02d}:{elapsed_s:02d}",
            "tenders_per_minute": self.tenders_per_minute,
        }
        import urllib.request as _ur
        import json as _json

        def _post() -> str:
            data = _json.dumps(payload).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "BlackForest-Webhook/1.0",
            }
            if self.completion_webhook_secret:
                headers["X-BF-Secret"] = self.completion_webhook_secret
            req = _ur.Request(url, data=data, headers=headers, method="POST")
            with _ur.urlopen(req, timeout=10) as resp:
                return str(resp.status)

        try:
            status = await asyncio.to_thread(_post)
            self.add_log(f"🔔 Webhook delivered: HTTP {status}")
        except Exception as e1:
            self.add_log(f"⚠️ Webhook attempt 1 failed: {e1} — retrying in 5 s…")
            await asyncio.sleep(5)
            try:
                status = await asyncio.to_thread(_post)
                self.add_log(f"🔔 Webhook delivered (retry): HTTP {status}")
            except Exception as e2:
                self.add_log(f"❌ Webhook retry failed: {e2}")

    def _write_bf_done_signal(self) -> None:
        """
        Write bf_done_signal.json so the T84 Telegram monitor can trigger the pipeline.
        Called unconditionally after every scrape — Telegram bots cannot receive messages
        from other bots, so this file is the only reliable cross-bot trigger path.
        Option-C watchdog: verifies file after write; sends Telegram alert if write fails.
        """
        import json as _json_sig, pathlib as _pl_sig, urllib.request as _ur
        ts_iso    = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        new_count = max(0, self.total_tenders_found - self.total_skipped_existing)
        _payload  = {
            "ts":      ts_iso,
            "portals": self.total_portals_completed,
            "tenders": self.total_tenders_found,
            "new":     new_count,
            "skipped": self.total_skipped_existing,
            "elapsed": self.elapsed_seconds,
        }
        _sig = _pl_sig.Path(r"G:\My Drive\0dev\t84\xscripts\bf_done_signal.json")
        _write_ok = False
        try:
            _sig.write_text(_json_sig.dumps(_payload), encoding="utf-8")
            # Verify: read back and parse to confirm disk write succeeded
            _readback = _json_sig.loads(_sig.read_text(encoding="utf-8"))
            if _readback.get("ts") == ts_iso:
                self.add_log("📁 BF_DONE signal file written ✅")
                _write_ok = True
            else:
                raise ValueError("readback ts mismatch")
        except Exception as _sig_err:
            self.add_log(f"⚠️ BF_DONE signal file FAILED: {_sig_err}")
            # Send Telegram alert so pipeline can be triggered manually
            _token = (self.telegram_bot_token or "").strip()
            _chat  = (self.telegram_chat_id or "").strip()
            if _token and _chat:
                try:
                    _alert = (
                        f"⚠️ *BF Signal File Failed*\n"
                        f"Signal file could not be written: `{_sig_err}`\n"
                        f"Scrape complete: portals={self.total_portals_completed} "
                        f"new={new_count}\n"
                        f"👉 Tap ▶ Pipeline button to run pipeline manually."
                    )
                    _body = _json_sig.dumps({
                        "chat_id": _chat, "text": _alert, "parse_mode": "Markdown"
                    }).encode()
                    _req = _ur.Request(
                        f"https://api.telegram.org/bot{_token}/sendMessage",
                        data=_body,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    _ur.urlopen(_req, timeout=10)
                    self.add_log("📱 Signal-fail Telegram alert sent")
                except Exception as _tg_err:
                    self.add_log(f"⚠️ Signal-fail alert also failed: {_tg_err}")

    async def _fire_telegram_notification(self):
        """Send a rich Telegram summary when scraping finishes."""
        if not self.telegram_enabled:
            return
        token = self.telegram_bot_token.strip()
        chat_id = self.telegram_chat_id.strip()
        if not token or not chat_id:
            return
        ts = datetime.now().strftime("%d %b %Y, %H:%M")
        ts_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        elapsed_h = self.elapsed_seconds // 3600
        elapsed_m = (self.elapsed_seconds % 3600) // 60
        elapsed_s = self.elapsed_seconds % 60
        elapsed_str = f"{elapsed_h:02d}:{elapsed_m:02d}:{elapsed_s:02d}"
        tpm = self.tenders_per_minute
        dpm = self.departments_per_minute
        new_tenders = max(0, self.total_tenders_found - self.total_skipped_existing)
        e = self._tg_escape
        # Human-readable body
        text = (
            f"🔔 *T84 Scrape Complete — Pipeline Starting*\n"
            f"📅 {e(ts)}\n\n"
            f"📋 Portals: *{self.total_portals_completed}*\n"
            f"🗂 Departments: *{self.total_departments_processed:,}*\n"
            f"💼 Total tenders: *{self.total_tenders_found:,}*\n"
            f"🆕 New \\(unique\\): *{new_tenders:,}*\n"
            f"⏭ Skipped \\(duplicates\\): *{self.total_skipped_existing:,}*\n\n"
            f"⏱ Duration: *{e(elapsed_str)}*\n"
            f"🚀 Speed: *{e(tpm)}* tenders/min · *{e(dpm)}* depts/min\n\n"
            # Machine-readable tag — T84 pipeline can match on #BF_DONE and parse key=value pairs
            f"`#BF_DONE ts={ts_iso} portals={self.total_portals_completed} "
            f"tenders={self.total_tenders_found} new={new_tenders} "
            f"skipped={self.total_skipped_existing} elapsed={self.elapsed_seconds}`"
        )
        try:
            await asyncio.to_thread(self._tg_send_sync, token, chat_id, text)
            self.add_log("📱 Telegram summary sent")
        except Exception as err:
            self.add_log(f"⚠️ Telegram summary failed: {err}")

        # NOTE: signal file is now written unconditionally by _write_bf_done_signal()
        # (called at pipeline completion before this method, independent of Telegram config)

    async def _fire_telegram_error_alert(self, error_msg: str):
        """Send a brief error alert on Telegram when scraping crashes."""
        if not self.telegram_enabled or not self.telegram_error_alert:
            return
        token = self.telegram_bot_token.strip()
        chat_id = self.telegram_chat_id.strip()
        if not token or not chat_id:
            return
        ts = datetime.now().strftime("%d %b %Y, %H:%M")
        e = self._tg_escape
        short_err = (error_msg or "unknown error")[:200]
        text = (
            f"🚨 *Black Forest — Scraping Error*\n"
            f"📅 {e(ts)}\n\n"
            f"❌ {e(short_err)}\n\n"
            f"_Check dashboard logs for details\\._"
        )
        try:
            await asyncio.to_thread(self._tg_send_sync, token, chat_id, text)
        except Exception:
            pass  # Do not cascade errors from error handler

    async def _fire_telegram_portal_alert(self, portal_name: str, tenders: int, depts: int):
        """Send a brief per-portal completion alert (optional)."""
        if not self.telegram_enabled or not self.telegram_per_portal_alert:
            return
        token = self.telegram_bot_token.strip()
        chat_id = self.telegram_chat_id.strip()
        if not token or not chat_id:
            return
        e = self._tg_escape
        text = (
            f"✔️ *Portal done:* {e(portal_name)}\n"
            f"💼 {tenders:,} tenders · 🗂 {depts:,} depts"
        )
        try:
            await asyncio.to_thread(self._tg_send_sync, token, chat_id, text)
        except Exception:
            pass

    async def _run_post_scrape_script(self):
        """Run the configured local Python script after scraping finishes."""
        if not self.post_scrape_script_enabled:
            return
        script = self.post_scrape_script.strip()
        if not script:
            return
        try:
            import subprocess
            import sys as _sys
            import shlex
            args = self.post_scrape_script_args.strip()
            cmd = [_sys.executable, script]
            if args:
                cmd.extend(shlex.split(args))
            label = script + (f" {args}" if args else "")
            self.add_log(f"⚙️ Running post-scrape script: {label}")
            result = await asyncio.to_thread(
                lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            )
            if result.returncode == 0:
                self.add_log(f"✅ Post-scrape script finished (exit 0)")
                if result.stdout.strip():
                    self.add_log(f"   stdout: {result.stdout.strip()[:300]}")
            else:
                self.add_log(f"⚠️ Post-scrape script exited {result.returncode}: {result.stderr.strip()[:300]}")
        except Exception as e:
            self.add_log(f"❌ Post-scrape script error: {e}")

    async def test_post_scrape_script(self):
        """Dry-run the configured post-scrape script for testing (ignores enabled flag)."""
        script = self.post_scrape_script.strip()
        if not script:
            self.add_log("⚠️ [DRY RUN] No script path set — nothing to test.")
            return
        self.test_script_running = True
        yield
        try:
            import subprocess
            import sys as _sys
            import shlex
            args = self.post_scrape_script_args.strip()
            cmd = [_sys.executable, script]
            if args:
                cmd.extend(shlex.split(args))
            label = script + (f" {args}" if args else "")
            self.add_log(f"🧪 [DRY RUN] Running post-scrape script: {label}")
            result = await asyncio.to_thread(
                lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            )
            if result.returncode == 0:
                self.add_log("✅ [DRY RUN] Script finished (exit 0)")
                if result.stdout.strip():
                    self.add_log(f"   stdout: {result.stdout.strip()[:300]}")
                yield rx.call_script(
                    "(function(){var c=new(window.AudioContext||window.webkitAudioContext)();"
                    "var o=c.createOscillator();var g=c.createGain();"
                    "o.connect(g);g.connect(c.destination);"
                    "o.type='sine';o.frequency.value=880;"
                    "g.gain.setValueAtTime(0.4,c.currentTime);"
                    "g.gain.exponentialRampToValueAtTime(0.001,c.currentTime+0.6);"
                    "o.start(c.currentTime);o.stop(c.currentTime+0.6)})()"
                )
            else:
                self.add_log(f"⚠️ [DRY RUN] Script exited {result.returncode}: {result.stderr.strip()[:300]}")
        except Exception as e:
            self.add_log(f"❌ [DRY RUN] Script error: {e}")
        finally:
            self.test_script_running = False

    async def test_telegram_notification(self):
        """Send a test Telegram message to verify the integration."""
        token = self.telegram_bot_token.strip()
        chat_id = self.telegram_chat_id.strip()
        if not token or not chat_id:
            self.add_log("⚠️ Telegram Bot Token and Chat ID are required for test.")
            return
        self.test_telegram_running = True
        yield
        try:
            import urllib.request
            import json as _json
            ts = datetime.now().strftime("%d %b %Y, %H:%M")
            text = (
                f"🧪 *Black Forest — Test Message*\n"
                f"📅 {ts}\n"
                f"✅ Telegram integration is working correctly\\.\n"
                f"Real scraping summaries will be sent here when a run completes\\."
            )
            api_url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = _json.dumps({
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "MarkdownV2",
            }).encode("utf-8")
            req = urllib.request.Request(
                api_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.add_log("📱 Test Telegram message sent successfully!")
        except Exception as e:
            self.add_log(f"⚠️ Test Telegram message failed: {e}")
        finally:
            self.test_telegram_running = False

    async def test_webhook(self):
        """Fire a test POST to the configured webhook URL."""
        url = self.completion_webhook_url.strip()
        if not url:
            self.add_log("⚠️ No webhook URL set — nothing to test.")
            return
        self.test_webhook_running = True
        yield
        try:
            import urllib.request
            import json as _json
            payload = {
                "event": "test",
                "timestamp": datetime.now().isoformat(),
                "total_tenders": 0,
                "total_departments": 0,
                "total_portals": 0,
                "skipped_existing": 0,
            }
            data = _json.dumps(payload).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "BlackForest-Webhook/1.0",
            }
            if self.completion_webhook_secret:
                headers["X-BF-Secret"] = self.completion_webhook_secret
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.add_log(f"🔔 Test webhook delivered: HTTP {resp.status}")
        except Exception as e:
            self.add_log(f"⚠️ Test webhook failed: {e}")
        finally:
            self.test_webhook_running = False

    async def pause_worker(self, worker_id: int):
        """Pause a specific worker."""
        self.add_log(f"⏸️ Pause is not yet supported for individual workers.")

    async def resume_worker(self, worker_id: int):
        """Resume a paused worker."""
        self.add_log(f"▶️ Resume is not yet supported for individual workers.")

    async def stop_worker(self, worker_id: int):
        """Stop a specific worker — currently stops all workers (global stop)."""
        self.add_log(f"⏹️ Stopping all workers (per-worker stop not yet supported)...")
        await self.stop_scraping()

    def _load_portal_status(self):
        """Load portal status from database and base_urls.csv"""
        try:
            import csv
            import sqlite3

            project_root = Path(__file__).resolve().parents[2]
            dashboard_root = Path(__file__).resolve().parents[1]

            csv_candidates = [
                project_root / "base_urls.csv",
                dashboard_root / "base_urls.csv",
                Path("base_urls.csv"),
            ]

            db_candidates = [
                project_root / "database" / "blackforest_tenders.sqlite3",
                project_root / "data" / "blackforest_tenders.sqlite3",
                dashboard_root / "database" / "blackforest_tenders.sqlite3",
                Path("database/blackforest_tenders.sqlite3"),
            ]

            csv_path = next((path for path in csv_candidates if path.exists()), csv_candidates[0])
            db_path = next((path for path in db_candidates if path.exists()), db_candidates[0])
            
            # Read all configured portals
            portals_config = {}
            if csv_path.exists():
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('Name'):
                            portals_config[row['Name'].strip()] = {
                                'name': row['Name'].strip(),
                                'url': row.get('BaseURL', ''),
                                'keyword': row.get('Keyword', '')
                            }
            
            # Get portal stats from database
            portal_stats = {}
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()

                # Detect V3 schema (portals + tender_items) vs V2 (tenders)
                existing_tables = {
                    r[0] for r in cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                use_v3 = "portals" in existing_tables and "tender_items" in existing_tables

                if use_v3:
                    results = cursor.execute("""
                        SELECT
                            p.portal_name,
                            COUNT(ti.id) AS tender_count,
                            MAX(ti.published_at) AS latest_published,
                            MAX(sr.id) AS latest_run_id
                        FROM portals p
                        LEFT JOIN tender_items ti ON ti.portal_id = p.id
                        LEFT JOIN scrape_runs sr
                            ON LOWER(TRIM(COALESCE(sr.portal_name, ''))) =
                               LOWER(TRIM(COALESCE(p.portal_name, '')))
                        GROUP BY p.portal_name
                    """).fetchall()
                else:
                    results = cursor.execute("""
                        SELECT
                            portal_name,
                            COUNT(*) AS tender_count,
                            MAX(published_date) AS latest_published,
                            MAX(run_id) AS latest_run_id
                        FROM tenders
                        WHERE portal_name IS NOT NULL
                        GROUP BY portal_name
                    """).fetchall()

                for portal, count, latest_pub, latest_run in results:
                    if portal:
                        portal_stats[portal] = {
                            'tender_count': count,
                            'latest_published': latest_pub or '',
                            'latest_run_id': latest_run or 0
                        }
                        # Also store by lowercase key for case-insensitive matching
                        portal_stats[portal.lower()] = portal_stats[portal]
                conn.close()

            logger.info(
                f"Portal status load: csv='{csv_path}', db='{db_path}', "
                f"configured_portals={len(portals_config)}, portal_stats={len(portal_stats)}"
            )
            
            # Combine data
            status_list = []
            for portal_name, config in portals_config.items():
                stats = portal_stats.get(portal_name) or portal_stats.get(portal_name.lower(), {})
                status_list.append({
                    'name': portal_name,
                    'url': config.get('url', ''),
                    'keyword': config.get('keyword', ''),
                    'status': 'scraped' if stats else 'pending',
                    'tender_count': stats.get('tender_count', 0),
                    'latest_published': stats.get('latest_published', ''),
                    'latest_run_id': stats.get('latest_run_id', 0)
                })
            
            self.portal_status_list = status_list
        except Exception as e:
            logger.error(f"Error loading portal status: {e}")
            self.portal_status_list = []

    def refresh_portal_status(self):
        """Refresh portal status from database"""
        self._load_portal_status()

    def set_portal_sort(self, value: str):
        """Set portal sorting option"""
        self.portal_sort_by = value

    def set_portal_filter(self, value: str):
        """Set portal filter option"""
        self.portal_filter = value

    def set_portal_search(self, value: str):
        """Set portal search query"""
        self.portal_search_query = value.lower()

    def toggle_portal_dashboard(self):
        """Toggle portal dashboard visibility"""
        self.show_portal_dashboard = not self.show_portal_dashboard

    async def scrape_single_portal(self, portal_name: str):
        """Start scraping a single portal"""
        if self.is_scraping:
            self.add_log("❌ Scraping already in progress. Please wait for completion.")
            return
        
        self.selected_portals = [portal_name]
        self.add_log(f"🚀 Starting scraping for: {portal_name}")
        async for _ in self.start_scraping():
            yield

    @rx.var
    def filtered_sorted_portals(self) -> List[Dict]:
        """Get filtered and sorted portal list"""
        portals = self.portal_status_list
        
        # Apply filter
        if self.portal_filter == "scraped":
            portals = [p for p in portals if p['status'] == 'scraped']
        elif self.portal_filter == "pending":
            portals = [p for p in portals if p['status'] == 'pending']
        
        # Apply search
        if self.portal_search_query:
            portals = [p for p in portals if 
                      self.portal_search_query in p['name'].lower() or
                      self.portal_search_query in p['keyword'].lower()]
        
        # Apply sorting
        if self.portal_sort_by == "name":
            portals = sorted(portals, key=lambda p: p['name'].lower())
        elif self.portal_sort_by == "tenders":
            portals = sorted(portals, key=lambda p: p['tender_count'], reverse=True)
        elif self.portal_sort_by == "date":
            portals = sorted(portals, key=lambda p: p['latest_published'] or '', reverse=True)
        else:  # status
            # Sort by status (pending first), then by name
            portals = sorted(portals, key=lambda p: (p['status'] != 'pending', p['name'].lower()))
        
        return portals

    @rx.var
    def portal_stats_summary(self) -> Dict:
        """Get summary statistics for portals"""
        total = len(self.portal_status_list)
        scraped = sum(1 for p in self.portal_status_list if p['status'] == 'scraped')
        pending = total - scraped
        total_tenders = sum(p['tender_count'] for p in self.portal_status_list)
        
        return {
            'total': total,
            'scraped': scraped,
            'pending': pending,
            'total_tenders': total_tenders
        }

    def _checkpoint_file_path(self) -> Path:
        project_root = Path(__file__).parent.parent.parent
        checkpoint_dir = project_root / "dashboard" / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        return checkpoint_dir / "scraping_dashboard_checkpoint.json"

    def _save_checkpoint(self):
        """Persist current scraping progress for crash-safe resume."""
        try:
            checkpoint_path = self._checkpoint_file_path()
            all_portals = self.run_portals_all if self.run_portals_all else list(self.selected_portals)
            completed = list(self.completed_portals)
            remaining_count = max(0, len(all_portals) - len(completed))

            payload = {
                "version": 1,
                "updated_at": datetime.now().isoformat(),
                "is_scraping": self.is_scraping,
                "all_portals": all_portals,
                "completed_portals": completed,
                "remaining_portals": [p for p in all_portals if p not in completed],
                "worker_count": self.worker_count,
                "worker_names": self.worker_names,
                "totals": {
                    "tenders": self.total_tenders_found,
                    "departments": self.total_departments_processed,
                    "portals": self.total_portals_completed,
                    "skipped_existing": self.total_skipped_existing,
                    "closing_date_reprocessed": self.total_closing_date_reprocessed,
                },
                "portal_progress": self.portal_progress,
            }

            checkpoint_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            self.checkpoint_available = True
            self.checkpoint_remaining_portals = remaining_count
            self.checkpoint_summary = (
                f"Checkpoint: {len(completed)}/{len(all_portals)} portals completed, "
                f"{remaining_count} remaining"
            )
            
            # Log checkpoint save with department counts
            total_depts_saved = sum(
                len(portal_data.get("processed_departments", []))
                for portal_data in self.portal_progress.values()
            )
            if total_depts_saved > 0:
                self.add_log(f"💾 Checkpoint saved: {total_depts_saved} completed department(s) across {len(self.portal_progress)} portal(s)")
        except Exception as e:
            self.add_log(f"WARNING: could not save checkpoint: {str(e)}")

    @staticmethod
    def _normalize_department_name(name: str) -> str:
        return str(name or "").strip().lower()

    def _merge_portal_progress(self, portal_name: str, update_data: Dict):
        if not portal_name:
            return

        current_entry = dict(self.portal_progress.get(portal_name, {}))
        current_entry.setdefault("processed_departments", [])

        current_processed = [
            self._normalize_department_name(item)
            for item in (current_entry.get("processed_departments") or [])
            if self._normalize_department_name(item)
        ]
        processed_set = set(current_processed)

        completed_department = self._normalize_department_name(update_data.get("checkpoint_department_completed", ""))
        if completed_department:
            processed_set.add(completed_department)

        extra_completed = update_data.get("checkpoint_processed_departments", [])
        if isinstance(extra_completed, list):
            processed_set.update(
                self._normalize_department_name(item)
                for item in extra_completed
                if self._normalize_department_name(item)
            )

        current_entry["processed_departments"] = sorted(processed_set)

        for numeric_key in ["dept_current", "dept_total", "expected_departments", "tenders_found", "expected_tenders", "pending_depts"]:
            if numeric_key in update_data:
                try:
                    current_entry[numeric_key] = int(update_data.get(numeric_key, current_entry.get(numeric_key, 0)))
                except Exception:
                    pass

        if "status" in update_data:
            current_entry["status"] = str(update_data.get("status") or current_entry.get("status") or "")

        current_entry["updated_at"] = datetime.now().isoformat()
        self.portal_progress[portal_name] = current_entry

    def _clear_checkpoint_file(self):
        try:
            checkpoint_path = self._checkpoint_file_path()
            if checkpoint_path.exists():
                checkpoint_path.unlink()
        except Exception as e:
            self.add_log(f"WARNING: could not clear checkpoint: {str(e)}")

    async def clear_checkpoint(self):
        self._clear_checkpoint_file()
        self.checkpoint_available = False
        self.checkpoint_remaining_portals = 0
        self.checkpoint_summary = ""
        self.resume_mode = False
        self.resume_base_tenders = 0
        self.resume_base_departments = 0
        self.resume_base_portals = 0
        self.resume_base_skipped_existing = 0
        self.resume_base_closing_date_reprocessed = 0
        self.run_portals_all = []
        self.completed_portals = []
        self.portal_progress = {}
        self.add_log("Checkpoint cleared")

    async def load_checkpoint_status(self):
        """Load checkpoint metadata if available."""
        try:
            checkpoint_path = self._checkpoint_file_path()
            if not checkpoint_path.exists():
                self.checkpoint_available = False
                self.checkpoint_remaining_portals = 0
                self.checkpoint_summary = ""
                return

            data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            all_portals = data.get("all_portals", [])
            completed = data.get("completed_portals", [])
            remaining = [p for p in all_portals if p not in completed]
            loaded_progress = data.get("portal_progress", {})

            if isinstance(loaded_progress, dict):
                self.portal_progress = {
                    str(portal): {
                        **(entry if isinstance(entry, dict) else {}),
                        "processed_departments": sorted({
                            self._normalize_department_name(item)
                            for item in ((entry or {}).get("processed_departments") or [])
                            if self._normalize_department_name(item)
                        }),
                    }
                    for portal, entry in loaded_progress.items()
                    if str(portal).strip()
                }
            else:
                self.portal_progress = {}

            self.checkpoint_available = len(remaining) > 0
            self.checkpoint_remaining_portals = len(remaining)
            self.checkpoint_summary = (
                f"Checkpoint found: {len(completed)}/{len(all_portals)} portals done, "
                f"{len(remaining)} pending"
            )
        except Exception as e:
            self.add_log(f"WARNING: failed to read checkpoint: {str(e)}")
            self.checkpoint_available = False
            self.checkpoint_remaining_portals = 0
            self.checkpoint_summary = ""
            self.portal_progress = {}

    async def initialize_page(self):
        await self.load_available_portals()
        await self.load_checkpoint_status()

    @rx.var
    def worker_name_0(self) -> str:
        return self.worker_names[0] if len(self.worker_names) > 0 else "Worker 1"

    @rx.var
    def worker_name_1(self) -> str:
        return self.worker_names[1] if len(self.worker_names) > 1 else "Worker 2"

    @rx.var
    def worker_name_2(self) -> str:
        return self.worker_names[2] if len(self.worker_names) > 2 else "Worker 3"

    @rx.var
    def worker_name_3(self) -> str:
        return self.worker_names[3] if len(self.worker_names) > 3 else "Worker 4"

    async def load_available_portals(self):
        """Load portal list from base_urls.csv."""
        try:
            import sys
            from pathlib import Path

            project_root = Path(__file__).parent.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            import pandas as pd

            csv_path = project_root / "base_urls.csv"
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                self.available_portals = [
                    {
                        "name": row["Name"],
                        "url": row["BaseURL"],
                        "keyword": row.get("Keyword", ""),
                    }
                    for _, row in df.iterrows()
                ]
                self.add_log(f"Loaded {len(self.available_portals)} portals from base_urls.csv")
            else:
                self.add_log("ERROR: base_urls.csv not found")
        except Exception as e:
            self.add_log(f"ERROR loading portals: {str(e)}")

    def toggle_portal_selection(self, portal_name: str):
        if portal_name in self.selected_portals:
            self.selected_portals.remove(portal_name)
        else:
            self.selected_portals.append(portal_name)

    def select_all_portals(self):
        self.selected_portals = [p["name"] for p in self.available_portals]
        self.add_log(f"Selected all {len(self.selected_portals)} portals")

    def clear_portal_selection(self):
        self.selected_portals = []
        self.add_log("Cleared portal selection")

    def set_worker_count(self, count: str):
        try:
            count_int = int(count)
            self.worker_count = max(2, min(4, count_int))
        except Exception:
            self.worker_count = 2

    def set_js_batch_threshold(self, value: str):
        """Set the threshold for triggering batched JS extraction"""
        try:
            threshold = int(value)
            self.js_batch_threshold = max(100, min(10000, threshold))
        except Exception:
            self.js_batch_threshold = 300

    def set_js_batch_size(self, value: str):
        """Set the batch size for JS extraction"""
        try:
            size = int(value)
            self.js_batch_size = max(500, min(5000, size))
        except Exception:
            self.js_batch_size = 2000

    def _set_worker_name(self, index: int, value: str):
        clean = value.strip() if value else ""
        default_name = f"Worker {index + 1}"
        updated = list(self.worker_names)
        while len(updated) < 4:
            updated.append(f"Worker {len(updated) + 1}")
        updated[index] = clean if clean else default_name
        self.worker_names = updated

    def set_worker_name_0(self, value: str):
        self._set_worker_name(0, value)

    def set_worker_name_1(self, value: str):
        self._set_worker_name(1, value)

    def set_worker_name_2(self, value: str):
        self._set_worker_name(2, value)

    def set_worker_name_3(self, value: str):
        self._set_worker_name(3, value)

    def reset_worker_names(self):
        self.worker_names = ["Worker 1", "Worker 2", "Worker 3", "Worker 4"]

    def add_log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_messages = [log_entry] + self.log_messages[: self.max_log_messages - 1]

    async def start_scraping(self):
        if not self.selected_portals:
            self.add_log("ERROR: No portals selected")
            return

        if self.is_scraping:
            self.add_log("Scraping already in progress")
            return

        self.workers = [
            WorkerStatus(
                worker_id=i,
                worker_name=self.worker_names[i] if i < len(self.worker_names) else f"Worker {i + 1}",
                status="idle",
                last_update=datetime.now().isoformat(),
            )
            for i in range(self.worker_count)
        ]

        self.is_scraping = True
        self.scraping_start_time = datetime.now().isoformat()
        self.elapsed_seconds = 0  # Reset elapsed time counter

        if not self.resume_mode:
            self.total_tenders_found = 0
            self.total_departments_processed = 0
            self.total_portals_completed = 0
            self.total_skipped_existing = 0
            self.total_closing_date_reprocessed = 0
            self.resume_base_tenders = 0
            self.resume_base_departments = 0
            self.resume_base_portals = 0
            self.resume_base_skipped_existing = 0
            self.resume_base_closing_date_reprocessed = 0
            self.run_portals_all = list(self.selected_portals)
            self.completed_portals = []
            self.portal_progress = {}

        self.auto_refresh_enabled = True

        self.add_log(f"Starting scraping: {len(self.selected_portals)} portals with {self.worker_count} workers")
        self._save_checkpoint()
        yield

        async for _ in self._run_scraping_background():
            yield

    async def resume_from_checkpoint(self):
        """Resume pending portals from last saved dashboard checkpoint."""
        if self.is_scraping:
            self.add_log("Cannot resume while scraping is already running")
            return

        try:
            checkpoint_path = self._checkpoint_file_path()
            if not checkpoint_path.exists():
                self.add_log("No checkpoint file found")
                self.checkpoint_available = False
                return

            data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            all_portals = data.get("all_portals", [])
            completed = data.get("completed_portals", [])
            remaining = [p for p in all_portals if p not in completed]

            if not remaining:
                self.add_log("Checkpoint has no pending portals. Nothing to resume.")
                await self.clear_checkpoint()
                return

            self.worker_count = int(data.get("worker_count", self.worker_count))
            saved_names = data.get("worker_names", self.worker_names)
            if isinstance(saved_names, list) and len(saved_names) >= 2:
                self.worker_names = saved_names[:4]

            totals = data.get("totals", {})
            self.resume_base_tenders = int(totals.get("tenders", 0))
            self.resume_base_departments = int(totals.get("departments", 0))
            self.resume_base_portals = int(totals.get("portals", 0))
            self.resume_base_skipped_existing = int(totals.get("skipped_existing", 0))
            self.resume_base_closing_date_reprocessed = int(totals.get("closing_date_reprocessed", 0))

            self.total_tenders_found = self.resume_base_tenders
            self.total_departments_processed = self.resume_base_departments
            self.total_portals_completed = self.resume_base_portals
            self.total_skipped_existing = self.resume_base_skipped_existing
            self.total_closing_date_reprocessed = self.resume_base_closing_date_reprocessed

            self.run_portals_all = all_portals
            self.completed_portals = completed
            self.selected_portals = remaining

            loaded_progress = data.get("portal_progress", {})
            if isinstance(loaded_progress, dict):
                self.portal_progress = {
                    str(portal): {
                        **(entry if isinstance(entry, dict) else {}),
                        "processed_departments": sorted({
                            self._normalize_department_name(item)
                            for item in ((entry or {}).get("processed_departments") or [])
                            if self._normalize_department_name(item)
                        }),
                    }
                    for portal, entry in loaded_progress.items()
                    if str(portal).strip()
                }
                # Log department resume info for each portal
                for portal_name, portal_data in self.portal_progress.items():
                    dept_count = len(portal_data.get("processed_departments", []))
                    if dept_count > 0:
                        self.add_log(f"  ✓ Portal '{portal_name}': Will skip {dept_count} already-completed department(s)")
            else:
                self.portal_progress = {}

            self.resume_mode = True

            self.add_log(
                f"Resuming checkpoint: {len(completed)} completed, {len(remaining)} pending portal(s)"
            )
            async for _ in self.start_scraping():
                yield
        except Exception as e:
            self.add_log(f"ERROR resuming checkpoint: {str(e)}")

    async def _run_scraping_background(self):
        global _active_manager
        try:
            import sys
            from pathlib import Path

            project_root = Path(__file__).parent.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            from tender_dashboard_reflex.scraping_worker import ScrapingWorkerManager

            manager = ScrapingWorkerManager(
                selected_portals=self.selected_portals,
                worker_count=self.worker_count,
                project_root=str(project_root),
                portal_resume_data=self.portal_progress,
                js_batch_threshold=self.js_batch_threshold,
                js_batch_size=self.js_batch_size,
            )

            # Store globally so stop_scraping() can terminate processes
            _active_manager = manager

            self.add_log("Initializing worker processes...")
            yield
            updates_queue: py_queue.Queue = py_queue.Queue()

            # Reset watchdog counters
            self._watchdog_last_tenders = 0
            self._watchdog_last_depts = 0
            self._watchdog_last_change_ts = datetime.now().isoformat()

            # Start watchdog background task
            watchdog_task = asyncio.create_task(self._watchdog_loop())

            def enqueue_update(update_data: Dict):
                updates_queue.put(update_data)

            scraping_task = asyncio.create_task(asyncio.to_thread(manager.start_scraping, enqueue_update))

            while not scraping_task.done():
                drained_any = False
                while True:
                    try:
                        update_data = updates_queue.get_nowait()
                    except py_queue.Empty:
                        break
                    self._update_progress_sync(update_data)
                    drained_any = True

                if drained_any:
                    yield
                else:
                    await asyncio.sleep(0.1)

            while True:
                try:
                    update_data = updates_queue.get_nowait()
                except py_queue.Empty:
                    break
                self._update_progress_sync(update_data)
                yield

            await scraping_task

            # Cancel watchdog now that scraping is done
            watchdog_task.cancel()

            self.is_scraping = False
            self.auto_refresh_enabled = False
            self.resume_mode = False
            self._clear_checkpoint_file()
            self.checkpoint_available = False
            self.checkpoint_remaining_portals = 0
            self.checkpoint_summary = ""
            self.portal_progress = {}
            self.add_log("Scraping completed!")

            # Play ding sound in browser
            yield rx.call_script(
                "(function(){var c=new(window.AudioContext||window.webkitAudioContext)();"
                "var o=c.createOscillator();var g=c.createGain();"
                "o.connect(g);g.connect(c.destination);"
                "o.type='sine';o.frequency.value=880;"
                "g.gain.setValueAtTime(0.4,c.currentTime);"
                "g.gain.exponentialRampToValueAtTime(0.001,c.currentTime+0.6);"
                "o.start(c.currentTime);o.stop(c.currentTime+0.6)})()"
            )

            # Fire completion webhook (if enabled)
            await self._fire_completion_webhook()

            # Write BF_DONE signal file — always, regardless of Telegram config.
            # T84 monitor cannot read bot-to-bot Telegram messages; this file is the trigger.
            await asyncio.to_thread(self._write_bf_done_signal)

            # Send Telegram notification (if enabled)
            await self._fire_telegram_notification()

            # Run local post-scrape script (if enabled)
            if self.post_scrape_script_enabled and self.post_scrape_script:
                await self._run_post_scrape_script()
                yield

            _active_manager = None
            yield

        except Exception as e:
            err_msg = str(e)
            self.add_log(f"ERROR: {err_msg}")
            self.is_scraping = False
            self.auto_refresh_enabled = False
            self._save_checkpoint()
            _active_manager = None
            # Cancel watchdog
            try:
                watchdog_task.cancel()
            except Exception:
                pass
            # Send error alert via Telegram
            await self._fire_telegram_error_alert(err_msg)
            yield

    def _update_progress_sync(self, update_data: Dict):
        """Update progress from worker callback."""
        try:
            # Update elapsed time if scraping is active
            if self.is_scraping and self.scraping_start_time:
                try:
                    start_dt = datetime.fromisoformat(self.scraping_start_time)
                    elapsed_td = datetime.now() - start_dt
                    self.elapsed_seconds = int(elapsed_td.total_seconds())
                except Exception:
                    pass  # Keep previous elapsed_seconds value on parse error
            
            update_type = update_data.get("type", "log")

            if update_type == "log":
                self.add_log(update_data.get("message", ""))

            elif update_type == "worker_status":
                worker_id = update_data.get("worker_id")
                if worker_id is not None and 0 <= worker_id < len(self.workers):
                    old_worker = self.workers[worker_id]
                    self.workers[worker_id] = WorkerStatus(
                        worker_id=worker_id,
                        worker_name=self.worker_names[worker_id] if worker_id < len(self.worker_names) else old_worker.worker_name,
                        status=update_data.get("status", old_worker.status),
                        portal_name=update_data.get("portal_name", old_worker.portal_name),
                        current_department=update_data.get("current_department", old_worker.current_department),
                        department_name=update_data.get("department_name", old_worker.department_name),
                        dept_current=update_data.get("dept_current", old_worker.dept_current),
                        dept_total=update_data.get("dept_total", old_worker.dept_total),
                        expected_departments=update_data.get("expected_departments", old_worker.expected_departments),
                        tenders_found=update_data.get("tenders_found", old_worker.tenders_found),
                        expected_tenders=update_data.get("expected_tenders", old_worker.expected_tenders),
                        tender_percent=update_data.get("tender_percent", old_worker.tender_percent),
                        pending_depts=update_data.get("pending_depts", old_worker.pending_depts),
                        progress_percent=update_data.get("progress_percent", old_worker.progress_percent),
                        skipped_existing=update_data.get("skipped_existing", old_worker.skipped_existing),
                        last_update=datetime.now().isoformat(),
                        portal_ip=update_data.get("portal_ip", old_worker.portal_ip),
                    )

                portal_name = str(update_data.get("portal_name") or "").strip()
                if portal_name:
                    self._merge_portal_progress(portal_name, update_data)

                if update_data.get("checkpoint_department_completed"):
                    self._save_checkpoint()

            elif update_type == "totals":
                current_tenders = int(update_data.get("total_tenders", 0))
                current_depts = int(update_data.get("total_departments", 0))
                current_portals = int(update_data.get("portals_completed", self.total_portals_completed))
                current_skipped_existing = int(update_data.get("skipped_existing_total", 0))
                current_closing_date_reprocessed = int(update_data.get("closing_date_reprocessed_total", 0))

                if self.resume_mode:
                    self.total_tenders_found = max(self.total_tenders_found, self.resume_base_tenders + current_tenders)
                    self.total_departments_processed = max(
                        self.total_departments_processed,
                        self.resume_base_departments + current_depts,
                    )
                    self.total_portals_completed = max(self.total_portals_completed, self.resume_base_portals + current_portals)
                    self.total_skipped_existing = max(
                        self.total_skipped_existing,
                        self.resume_base_skipped_existing + current_skipped_existing,
                    )
                    self.total_closing_date_reprocessed = max(
                        self.total_closing_date_reprocessed,
                        self.resume_base_closing_date_reprocessed + current_closing_date_reprocessed,
                    )
                else:
                    self.total_tenders_found = max(self.total_tenders_found, current_tenders)
                    self.total_departments_processed = max(self.total_departments_processed, current_depts)
                    self.total_portals_completed = max(self.total_portals_completed, current_portals)
                    self.total_skipped_existing = max(self.total_skipped_existing, current_skipped_existing)
                    self.total_closing_date_reprocessed = max(
                        self.total_closing_date_reprocessed,
                        current_closing_date_reprocessed,
                    )

                self._save_checkpoint()

                # Watchdog progress tracking — record when totals last moved
                new_t = self.total_tenders_found
                new_d = self.total_departments_processed
                if new_t != self._watchdog_last_tenders or new_d != self._watchdog_last_depts:
                    self._watchdog_last_tenders = new_t
                    self._watchdog_last_depts = new_d
                    self._watchdog_last_change_ts = datetime.now().isoformat()

            elif update_type == "portal_complete":
                portal_name = update_data.get("portal_name", "")
                if portal_name and portal_name not in self.completed_portals:
                    self.completed_portals.append(portal_name)

                if portal_name:
                    completion_update = {
                        "status": "completed",
                        "checkpoint_processed_departments": update_data.get("checkpoint_processed_departments", []),
                        "tenders_found": update_data.get("tenders_found", 0),
                        "dept_current": update_data.get("departments_processed", 0),
                    }
                    self._merge_portal_progress(portal_name, completion_update)
                    # Per-portal Telegram alert (fire-and-forget, non-blocking)
                    asyncio.get_event_loop().call_soon(
                        lambda pn=portal_name, tf=update_data.get("tenders_found", 0), dp=update_data.get("departments_processed", 0):
                        asyncio.ensure_future(self._fire_telegram_portal_alert(pn, int(tf), int(dp)))
                    )

                self.total_portals_completed = max(self.total_portals_completed, len(self.completed_portals))
                self._save_checkpoint()

            # Keep totals synced to latest workers
            self.total_tenders_found = max(self.total_tenders_found, sum(w.tenders_found for w in self.workers))
            self.total_departments_processed = max(
                self.total_departments_processed,
                sum(w.dept_current for w in self.workers),
            )

            self.last_refresh = datetime.now().isoformat()

        except Exception as e:
            self.add_log(f"ERROR in progress update: {str(e)}")

    async def stop_scraping(self):
        global _active_manager
        if not self.is_scraping:
            return

        self.add_log("Stopping scraping...")
        self.is_scraping = False
        self.auto_refresh_enabled = False

        # Terminate worker processes via the module-level manager reference
        if _active_manager is not None:
            try:
                _active_manager.stop()
            except Exception as e:
                logger.warning(f"Error stopping workers: {e}")
            _active_manager = None

        self._save_checkpoint()

    def clear_logs(self):
        self.log_messages = []

    # ── Health Watchdog ────────────────────────────────────────────────

    async def _watchdog_loop(self):
        """Background task: alert via Telegram if no scraping progress for N minutes."""
        alerted = False
        while self.is_scraping:
            await asyncio.sleep(60)  # check every minute
            if not self.is_scraping or not self.watchdog_enabled:
                break
            last_ts = self._watchdog_last_change_ts
            if not last_ts:
                continue
            try:
                last_dt = datetime.fromisoformat(last_ts)
                stall_secs = (datetime.now() - last_dt).total_seconds()
                threshold_secs = self.watchdog_stall_minutes * 60
                if stall_secs >= threshold_secs and not alerted:
                    stall_min = int(stall_secs // 60)
                    self.add_log(f"🐕 Watchdog: No progress for {stall_min} min — sending alert")
                    await self._fire_telegram_watchdog_alert(stall_min)
                    alerted = True
                elif stall_secs < threshold_secs:
                    alerted = False  # reset if progress resumed
            except Exception:
                pass

    async def _fire_telegram_watchdog_alert(self, stall_minutes: int):
        """Telegram alert when scraping appears stalled."""
        if not self.telegram_enabled:
            return
        token = self.telegram_bot_token.strip()
        chat_id = self.telegram_chat_id.strip()
        if not token or not chat_id:
            return
        ts = datetime.now().strftime("%d %b %Y, %H:%M")
        e = self._tg_escape
        text = (
            f"⚠️ *Black Forest — Scraping Stalled*\n"
            f"📅 {e(ts)}\n\n"
            f"No new tenders or departments in the last *{stall_minutes} min*\\.\n"
            f"Portals: {self.total_portals_completed} done · "
            f"{self.total_tenders_found:,} tenders so far\\.\n\n"
            f"_Check dashboard — worker may be frozen or portal is unresponsive\\._"
        )
        try:
            await asyncio.to_thread(self._tg_send_sync, token, chat_id, text)
        except Exception:
            pass

    # ── Scheduled Auto-Scrape ──────────────────────────────────────────

    async def _scheduler_loop(self):
        """Background scheduler: wake up every minute and fire at configured time (HH:MM)."""
        while True:
            await asyncio.sleep(30)
            if not self.scheduler_enabled:
                continue
            now = datetime.now()
            try:
                target_h = int(self.scheduler_hour or "2")
                target_m = int(self.scheduler_minute or "0")
            except ValueError:
                continue
            if now.hour == target_h and now.minute == target_m:
                if self.is_scraping:
                    continue  # already running — skip
                portals_raw = self.scheduler_portals.strip()
                if portals_raw:
                    names = [p.strip() for p in portals_raw.split(",") if p.strip()]
                    available = {p["name"] for p in self.available_portals}
                    self.selected_portals = [n for n in names if n in available] or list(available)
                else:
                    self.selected_portals = [p["name"] for p in self.available_portals]
                if not self.selected_portals:
                    continue
                self.add_log(f"⏰ Scheduled scrape triggered at {now.strftime('%H:%M')}")
                async for _ in self.start_scraping():
                    yield
                # Sleep 90 s to avoid double-triggering within the same minute
                await asyncio.sleep(90)

    async def start_scheduler(self):
        """Start the background scheduler loop (call once on app init)."""
        asyncio.ensure_future(self._scheduler_loop())


def portal_status_dashboard() -> rx.Component:
    """Visual portal status dashboard with sorting, filtering, and quick actions"""
    return rx.card(
        rx.vstack(
            # Header with stats
            rx.hstack(
                rx.heading("📊 Portal Status Dashboard", size="5", weight="bold"),
                rx.spacer(),
                rx.tooltip(
                    rx.icon_button(
                        rx.icon("refresh-cw", size=18),
                        on_click=ScrapingControlState.refresh_portal_status,
                        variant="soft",
                        color_scheme="blue",
                        size="2",
                    ),
                    content="Refresh portal status",
                ),
                rx.tooltip(
                    rx.icon_button(
                        rx.icon(rx.cond(ScrapingControlState.show_portal_dashboard, "eye-off", "eye"), size=18),
                        on_click=ScrapingControlState.toggle_portal_dashboard,
                        variant="soft",
                        color_scheme="gray",
                        size="2",
                    ),
                    content="Toggle dashboard",
                ),
                spacing="2",
                width="100%",
            ),
            
            # Summary stats
            rx.hstack(
                rx.box(
                    rx.vstack(
                        rx.text("Total Portals", size="1", color="gray.11", weight="medium"),
                        rx.text(ScrapingControlState.portal_stats_summary["total"].to_string(), size="6", weight="bold", color="blue.11"),
                        spacing="0",
                    ),
                    padding="0.75rem",
                    border="1px solid",
                    border_color="blue.6",
                    border_radius="8px",
                    background="blue.2",
                ),
                rx.box(
                    rx.vstack(
                        rx.text("Scraped", size="1", color="gray.11", weight="medium"),
                        rx.text(ScrapingControlState.portal_stats_summary["scraped"].to_string(), size="6", weight="bold", color="green.11"),
                        spacing="0",
                    ),
                    padding="0.75rem",
                    border="1px solid",
                    border_color="green.6",
                    border_radius="8px",
                    background="green.2",
                ),
                rx.box(
                    rx.vstack(
                        rx.text("Pending", size="1", color="gray.11", weight="medium"),
                        rx.text(ScrapingControlState.portal_stats_summary["pending"].to_string(), size="6", weight="bold", color="orange.11"),
                        spacing="0",
                    ),
                    padding="0.75rem",
                    border="1px solid",
                    border_color="orange.6",
                    border_radius="8px",
                    background="orange.2",
                ),
                rx.box(
                    rx.vstack(
                        rx.text("Total Tenders", size="1", color="gray.11", weight="medium"),
                        rx.text(ScrapingControlState.portal_stats_summary["total_tenders"].to_string(), size="6", weight="bold", color="violet.11"),
                        spacing="0",
                    ),
                    padding="0.75rem",
                    border="1px solid",
                    border_color="violet.6",
                    border_radius="8px",
                    background="violet.2",
                ),
                spacing="3",
                width="100%",
            ),
            
            # Controls: Search, Sort, Filter
            rx.cond(
                ScrapingControlState.show_portal_dashboard,
                rx.vstack(
                    rx.hstack(
                        rx.input(
                            placeholder="🔍 Search portals...",
                            value=ScrapingControlState.portal_search_query,
                            on_change=ScrapingControlState.set_portal_search,
                            width="100%",
                            size="2",
                        ),
                        rx.select(
                            ["status", "name", "tenders", "date"],
                            value=ScrapingControlState.portal_sort_by,
                            on_change=ScrapingControlState.set_portal_sort,
                            placeholder="Sort by",
                            size="2",
                        ),
                        rx.select(
                            ["all", "scraped", "pending"],
                            value=ScrapingControlState.portal_filter,
                            on_change=ScrapingControlState.set_portal_filter,
                            placeholder="Filter",
                            size="2",
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    
                    # Portal list
                    rx.box(
                        rx.foreach(
                            ScrapingControlState.filtered_sorted_portals,
                            lambda portal: rx.box(
                                rx.vstack(
                                    rx.hstack(
                                        # Status indicator
                                        rx.badge(
                                            rx.cond(
                                                portal["status"] == "scraped",
                                                "✅ Scraped",
                                                "⏳ Pending"
                                            ),
                                            color_scheme=rx.cond(
                                                portal["status"] == "scraped",
                                                "green",
                                                "orange"
                                            ),
                                            size="2",
                                        ),
                                        # Portal name
                                        rx.text(portal["name"], size="3", weight="bold"),
                                        rx.spacer(),
                                        # Tender count - always show
                                        rx.badge(f"{portal['tender_count']} tenders", color_scheme="blue", size="2"),
                                        # Action button
                                        rx.tooltip(
                                            rx.icon_button(
                                                rx.icon("play", size=16),
                                                on_click=lambda: ScrapingControlState.scrape_single_portal(portal["name"]),
                                                variant="soft",
                                                color_scheme=rx.cond(
                                                    portal["status"] == "pending",
                                                    "green",
                                                    "blue"
                                                ),
                                                size="2",
                                                disabled=ScrapingControlState.is_scraping,
                                            ),
                                            content=rx.cond(
                                                portal["status"] == "pending",
                                                "Start scraping",
                                                "Scrape again"
                                            ),
                                        ),
                                        spacing="2",
                                        width="100%",
                                        align="center",
                                    ),
                                    rx.hstack(
                                        rx.text(portal["keyword"], size="1", color="gray.10"),
                                        rx.cond(
                                            portal["latest_published"] != "",
                                            rx.text(f"📅 {portal['latest_published']}", size="1", color="gray.10"),
                                        ),
                                        spacing="2",
                                    ),
                                    spacing="1",
                                    width="100%",
                                ),
                                padding="0.75rem",
                                border="1px solid",
                                border_color=rx.cond(
                                    portal["status"] == "scraped",
                                    "green.5",
                                    "orange.5"
                                ),
                                border_radius="8px",
                                background=rx.cond(
                                    portal["status"] == "scraped",
                                    "green.1",
                                    "orange.1"
                                ),
                                margin_bottom="0.5rem",
                                _hover={"background": rx.cond(portal["status"] == "scraped", "green.2", "orange.2")},
                            ),
                        ),
                        max_height="500px",
                        overflow_y="auto",
                        width="100%",
                        padding="0.5rem",
                    ),
                    spacing="3",
                    width="100%",
                ),
            ),
            
            spacing="3",
            width="100%",
        ),
        size="2",
    )


def portal_selector() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("Select Portals", size="4", weight="bold"),
            rx.hstack(
                rx.button("Select All", on_click=ScrapingControlState.select_all_portals, variant="soft", color_scheme="blue", size="2"),
                rx.button("Clear All", on_click=ScrapingControlState.clear_portal_selection, variant="soft", color_scheme="gray", size="2"),
                rx.badge(rx.text(f"{ScrapingControlState.selected_portals.length()} selected"), color_scheme="green", size="2"),
                spacing="2",
            ),
            rx.box(
                rx.foreach(
                    ScrapingControlState.available_portals,
                    lambda portal: rx.checkbox(
                        rx.text(portal["name"], size="2"),
                        checked=ScrapingControlState.selected_portals.contains(portal["name"]),
                        on_change=lambda _: ScrapingControlState.toggle_portal_selection(portal["name"]),
                    ),
                ),
                max_height="300px",
                overflow_y="auto",
                width="100%",
                padding="0.5rem",
                border="1px solid",
                border_color="gray.6",
                border_radius="8px",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        size="2",
    )


def worker_config_panel() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("Worker Configuration", size="4", weight="bold"),
            rx.hstack(
                rx.text("Workers:", size="2", weight="medium"),
                rx.select(["2", "3", "4"], value=ScrapingControlState.worker_count.to_string(), on_change=ScrapingControlState.set_worker_count, size="2"),
                rx.text("processes", size="2", color="gray"),
                spacing="2",
                align="center",
            ),
            rx.divider(),
            rx.heading("Batched JS Extraction", size="3", weight="medium"),
            rx.hstack(
                rx.text("Batch Threshold:", size="2", weight="medium"),
                rx.input(
                    value=ScrapingControlState.js_batch_threshold.to_string(),
                    on_change=ScrapingControlState.set_js_batch_threshold,
                    type="number",
                    min=100,
                    max=10000,
                    width="120px",
                    size="2",
                ),
                rx.text("rows", size="2", color="gray"),
                spacing="2",
                align="center",
            ),
            rx.text("Departments with more rows than this will use batched extraction", size="1", color="gray"),
            rx.hstack(
                rx.text("Batch Size:", size="2", weight="medium"),
                rx.input(
                    value=ScrapingControlState.js_batch_size.to_string(),
                    on_change=ScrapingControlState.set_js_batch_size,
                    type="number",
                    min=500,
                    max=5000,
                    width="120px",
                    size="2",
                ),
                rx.text("rows per batch", size="2", color="gray"),
                spacing="2",
                align="center",
            ),
            rx.text("Number of rows to extract per JavaScript batch", size="1", color="gray"),
            rx.divider(),
            rx.callout(
                rx.text(
                    "Process-based workers avoid UI freeze and provide better throughput. "
                    "Batched extraction prevents browser timeouts on large departments (10,000+ tenders).",
                    size="2",
                ),
                color_scheme="blue",
                size="1",
            ),
            rx.hstack(
                rx.spacer(),
                rx.cond(
                    ScrapingControlState.settings_saved,
                    rx.button(
                        rx.icon("check", size=15),
                        " Saved!",
                        color_scheme="green",
                        variant="soft",
                        size="2",
                        disabled=True,
                    ),
                    rx.button(
                        rx.icon("save", size=15),
                        " Save",
                        on_click=ScrapingControlState.save_worker_settings,
                        color_scheme="blue",
                        variant="soft",
                        size="2",
                    ),
                ),
                width="100%",
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        size="2",
    )


def control_buttons() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("Controls", size="4", weight="bold"),
            rx.hstack(
                rx.tooltip(
                    rx.button(
                        rx.icon("play", size=16),
                        " Start Scraping",
                        on_click=ScrapingControlState.start_scraping,
                        disabled=ScrapingControlState.is_scraping,
                        color_scheme="green",
                        size="3",
                        variant="solid",
                    ),
                    content="Start scraping selected portals with configured workers",
                ),
                rx.tooltip(
                    rx.button(
                        rx.icon("square", size=16),
                        " Stop",
                        on_click=ScrapingControlState.stop_scraping,
                        disabled=~ScrapingControlState.is_scraping,
                        color_scheme="red",
                        size="3",
                        variant="soft",
                    ),
                    content="Stop all active scraping workers",
                ),
                spacing="2",
            ),
            rx.hstack(
                rx.tooltip(
                    rx.button(
                        rx.icon("rotate-ccw", size=14),
                        " Resume Checkpoint",
                        on_click=ScrapingControlState.resume_from_checkpoint,
                        disabled=ScrapingControlState.is_scraping | (~ScrapingControlState.has_checkpoint),
                        color_scheme="blue",
                        variant="soft",
                        size="2",
                    ),
                    content="Resume scraping from last saved checkpoint",
                ),
                rx.tooltip(
                    rx.button(
                        "Clear Checkpoint",
                        on_click=ScrapingControlState.clear_checkpoint,
                        disabled=~ScrapingControlState.has_checkpoint,
                        variant="outline",
                        size="2",
                    ),
                    content="Clear saved checkpoint data",
                ),
                spacing="2",
                wrap="wrap",
            ),
            rx.cond(
                ScrapingControlState.has_checkpoint,
                rx.badge(
                    ScrapingControlState.checkpoint_summary,
                    color_scheme="orange",
                    size="1",
                    variant="soft",
                ),
            ),
            rx.link(
                rx.button(rx.icon("settings", size=14), " Scraping Settings", variant="soft", color_scheme="gray", size="2"),
                href="/scraping-settings",
            ),
            rx.cond(
                ScrapingControlState.is_scraping,
                rx.badge(rx.icon("activity", size=14), " Scraping in progress...", color_scheme="green", size="2", variant="soft"),
                rx.badge(" Ready", color_scheme="gray", size="2"),
            ),
            spacing="3",
            align="start",
            width="100%",
        ),
        size="2",
    )


def progress_stats() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("Global Progress & Performance", size="4", weight="bold"),
            rx.grid(
                rx.tooltip(
                    rx.box(rx.text("Tenders Found", size="1", color="gray"), rx.heading(ScrapingControlState.total_tenders_found, size="5", color="blue")),
                    content="Total new tenders discovered",
                ),
                rx.tooltip(
                    rx.box(rx.text("Departments", size="1", color="gray"), rx.heading(ScrapingControlState.total_departments_processed, size="5", color="purple")),
                    content="Departments processed",
                ),
                rx.tooltip(
                    rx.box(rx.text("Portals Done", size="1", color="gray"), rx.heading(ScrapingControlState.total_portals_completed, size="5", color="green")),
                    content="Portals completed",
                ),
                rx.tooltip(
                    rx.box(rx.text("Active Workers", size="1", color="gray"), rx.heading(ScrapingControlState.active_workers, size="5", color="orange")),
                    content="Currently running workers",
                ),
                rx.tooltip(
                    rx.box(rx.text("Skipped (Existing)", size="1", color="gray"), rx.heading(ScrapingControlState.total_skipped_existing, size="5", color="gray")),
                    content="Tenders already in database",
                ),
                rx.tooltip(
                    rx.box(rx.text("Extended Deadlines", size="1", color="gray"), rx.heading(ScrapingControlState.total_closing_date_reprocessed, size="5", color="indigo")),
                    content="Tenders with changed closing dates",
                ),
                columns="6",
                spacing="4",
                width="100%",
            ),
            rx.divider(),
            # Speed metrics row
            rx.grid(
                rx.tooltip(
                    rx.box(
                        rx.hstack(
                            rx.icon("clock", size=18, color="blue.9"),
                            rx.text("Elapsed Time", size="1", color="gray"),
                            spacing="1",
                            align="center",
                        ),
                        rx.heading(ScrapingControlState.elapsed_time_formatted, size="5", color="blue.9", font_family="monospace"),
                    ),
                    content="Time since scraping started (HH:MM:SS)",
                ),
                rx.tooltip(
                    rx.box(
                        rx.hstack(
                            rx.icon("zap", size=18, color="green.9"),
                            rx.text("Tenders/min", size="1", color="gray"),
                            spacing="1",
                            align="center",
                        ),
                        rx.heading(ScrapingControlState.tenders_per_minute, size="5", color="green.9", font_family="monospace"),
                    ),
                    content="Tenders processed per minute",
                ),
                rx.tooltip(
                    rx.box(
                        rx.hstack(
                            rx.icon("trending-up", size=18, color="purple.9"),
                            rx.text("Depts/min", size="1", color="gray"),
                            spacing="1",
                            align="center",
                        ),
                        rx.heading(ScrapingControlState.departments_per_minute, size="5", color="purple.9", font_family="monospace"),
                    ),
                    content="Departments processed per minute",
                ),
                columns="3",
                spacing="4",
                width="100%",
            ),
            rx.divider(),
            rx.hstack(
                rx.badge("Audit", color_scheme="indigo", variant="soft", size="1"),
                rx.text(
                    f"Unique changed tender IDs (this run): {ScrapingControlState.extended_unique_this_run}",
                    size="2",
                    color="gray.11",
                ),
                width="100%",
                align="center",
                spacing="2",
            ),
            rx.vstack(
                rx.hstack(
                    rx.text("All Workers Department Progress", size="2", weight="medium"),
                    rx.spacer(),
                    rx.text(
                        f"{ScrapingControlState.total_departments_processed}/{ScrapingControlState.global_expected_departments} ({ScrapingControlState.global_department_percent}%)",
                        size="1",
                        color="blue",
                        weight="bold",
                    ),
                    width="100%",
                ),
                rx.progress(value=ScrapingControlState.global_department_percent, max=100, width="100%", color_scheme="blue"),
                spacing="1",
                width="100%",
            ),
            rx.vstack(
                rx.hstack(
                    rx.text("All Workers Tender Progress", size="2", weight="medium"),
                    rx.spacer(),
                    rx.text(
                        f"{ScrapingControlState.total_tenders_found}/{ScrapingControlState.global_expected_tenders} ({ScrapingControlState.global_tender_percent}%)",
                        size="1",
                        color="green",
                        weight="bold",
                    ),
                    width="100%",
                ),
                rx.progress(value=ScrapingControlState.global_tender_percent, max=100, width="100%", color_scheme="green"),
                spacing="1",
                width="100%",
            ),
            spacing="3",
            width="100%",
        ),
        size="2",
    )


def worker_status_cards() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading("Worker Status", size="4", weight="bold"),
            rx.foreach(
                ScrapingControlState.workers,
                lambda worker: rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.badge(worker.worker_name, color_scheme="blue", size="2"),
                            rx.badge(f"ID {worker.worker_id + 1}", color_scheme="gray", size="1"),
                            rx.badge(
                                worker.status,
                                color_scheme=rx.cond(
                                    worker.status == "running",
                                    "green",
                                    rx.cond(worker.status == "completed", "blue", "gray"),
                                ),
                                size="2",
                            ),
                            rx.spacer(),
                            rx.badge(f"Tender {worker.tenders_found}/{worker.expected_tenders}", color_scheme="cyan", size="2"),
                            rx.cond(
                                worker.skipped_existing > 0,
                                rx.tooltip(
                                    rx.badge(f"⏭️ {worker.skipped_existing} skipped", color_scheme="gray", size="2"),
                                    content="Duplicates already in database",
                                ),
                            ),
                            # Worker control buttons
                            rx.tooltip(
                                rx.icon_button(
                                    rx.icon("play", size=14),
                                    on_click=ScrapingControlState.resume_worker(worker.worker_id),
                                    variant="soft",
                                    color_scheme="green",
                                    size="1",
                                    disabled=worker.status == "running",
                                ),
                                content="Resume worker",
                            ),
                            rx.tooltip(
                                rx.icon_button(
                                    rx.icon("pause", size=14),
                                    on_click=ScrapingControlState.pause_worker(worker.worker_id),
                                    variant="soft",
                                    color_scheme="orange",
                                    size="1",
                                    disabled=worker.status != "running",
                                ),
                                content="Pause worker",
                            ),
                            rx.tooltip(
                                rx.icon_button(
                                    rx.icon("square", size=14),
                                    on_click=ScrapingControlState.stop_worker(worker.worker_id),
                                    variant="soft",
                                    color_scheme="red",
                                    size="1",
                                    disabled=worker.status == "completed",
                                ),
                                content="Stop worker",
                            ),
                            spacing="2",
                            width="100%",
                        ),
                        rx.cond(
                            worker.portal_name != "",
                            rx.hstack(
                                rx.text(f"Portal: {worker.portal_name}", size="2", weight="medium", color="blue"),
                                rx.cond(
                                    worker.portal_ip != "",
                                    rx.tooltip(
                                        rx.badge(worker.portal_ip, color_scheme="gray", size="1", variant="outline"),
                                        content="Resolved portal IP address",
                                    ),
                                ),
                                spacing="2",
                                align="center",
                            ),
                        ),
                        rx.cond(
                            worker.dept_total > 0,
                            rx.vstack(
                                rx.hstack(
                                    rx.text(f"Current Department #{worker.dept_current}/{worker.dept_total}", size="2", weight="medium"),
                                    rx.spacer(),
                                    rx.cond(worker.pending_depts > 0, rx.text(f"{worker.pending_depts} pending", size="1", color="gray")),
                                    width="100%",
                                ),
                                rx.cond(
                                    worker.department_name != "",
                                    rx.text(
                                        worker.department_name,
                                        size="1",
                                        color="gray.11",
                                        style={"overflow": "hidden", "text-overflow": "ellipsis", "white-space": "nowrap"},
                                    ),
                                ),
                                spacing="1",
                                width="100%",
                            ),
                            rx.cond(worker.current_department != "", rx.text(worker.current_department, size="2", color="gray")),
                        ),
                        rx.vstack(
                            rx.hstack(
                                rx.text("Department %", size="1", color="gray"),
                                rx.spacer(),
                                rx.text(f"{worker.dept_current}/{worker.dept_total} ({worker.progress_percent}%)", size="1", color="blue", weight="bold"),
                                width="100%",
                            ),
                            rx.progress(value=worker.progress_percent, max=100, width="100%", color_scheme="blue"),
                            spacing="1",
                            width="100%",
                        ),
                        rx.vstack(
                            rx.hstack(
                                rx.text("Tender %", size="1", color="gray"),
                                rx.spacer(),
                                rx.text(f"{worker.tenders_found}/{worker.expected_tenders} ({worker.tender_percent}%)", size="1", color="green", weight="bold"),
                                width="100%",
                            ),
                            rx.progress(value=worker.tender_percent, max=100, width="100%", color_scheme="green"),
                            spacing="1",
                            width="100%",
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    padding="0.75rem",
                    border="1px solid",
                    border_color=rx.cond(worker.status == "running", "blue.6", rx.cond(worker.status == "completed", "green.6", "gray.6")),
                    border_radius="8px",
                    margin_bottom="0.5rem",
                    background=rx.cond(worker.status == "running", "blue.1", rx.cond(worker.status == "completed", "green.1", "gray.1")),
                ),
            ),
            spacing="2",
            width="100%",
        ),
        size="2",
    )


def log_viewer() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.heading("Live Logs", size="4", weight="bold"),
                rx.spacer(),
                rx.button(rx.icon("trash-2", size=14), " Clear", on_click=ScrapingControlState.clear_logs, variant="ghost", size="1"),
                spacing="2",
                width="100%",
            ),
            rx.box(
                rx.foreach(
                    ScrapingControlState.log_messages,
                    lambda msg: rx.text(msg, size="1", font_family="monospace", color="gray.11"),
                ),
                max_height="400px",
                overflow_y="auto",
                width="100%",
                padding="0.75rem",
                background="gray.2",
                border_radius="8px",
            ),
            spacing="3",
            width="100%",
        ),
        size="2",
    )


def scraping_settings_page() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.heading("⚙️ Scraping Settings", size="7", weight="bold"),
                rx.spacer(),
                rx.link(rx.button("Back to Scraping", color_scheme="blue", variant="soft", size="2"), href="/scraping"),
                width="100%",
            ),
            rx.card(
                rx.vstack(
                    rx.heading("Worker Naming", size="4", weight="bold"),
                    rx.hstack(
                        rx.text("Default Workers", size="2", weight="medium"),
                        rx.select(["2", "3", "4"], value=ScrapingControlState.worker_count.to_string(), on_change=ScrapingControlState.set_worker_count, size="2"),
                        spacing="3",
                        align="center",
                    ),
                    rx.text("Worker 1 Name", size="2", weight="medium"),
                    rx.input(value=ScrapingControlState.worker_name_0, on_change=ScrapingControlState.set_worker_name_0, placeholder="Worker 1", width="100%"),
                    rx.text("Worker 2 Name", size="2", weight="medium"),
                    rx.input(value=ScrapingControlState.worker_name_1, on_change=ScrapingControlState.set_worker_name_1, placeholder="Worker 2", width="100%"),
                    rx.text("Worker 3 Name", size="2", weight="medium"),
                    rx.input(value=ScrapingControlState.worker_name_2, on_change=ScrapingControlState.set_worker_name_2, placeholder="Worker 3", width="100%"),
                    rx.text("Worker 4 Name", size="2", weight="medium"),
                    rx.input(value=ScrapingControlState.worker_name_3, on_change=ScrapingControlState.set_worker_name_3, placeholder="Worker 4", width="100%"),
                    rx.hstack(
                        rx.button("Reset Names", on_click=ScrapingControlState.reset_worker_names, variant="outline", color_scheme="gray", size="2"),
                        rx.spacer(),
                        rx.cond(
                            ScrapingControlState.settings_saved,
                            rx.button(
                                rx.icon("check", size=18),
                                " Saved!",
                                color_scheme="green",
                                variant="soft",
                                size="2",
                                disabled=True,
                            ),
                            rx.tooltip(
                                rx.button(
                                    rx.icon("save", size=18),
                                    " Save Settings",
                                    on_click=ScrapingControlState.save_worker_settings,
                                    color_scheme="blue",
                                    size="2",
                                ),
                                content="Save worker count and names",
                            ),
                        ),
                        width="100%",
                    ),
                    spacing="2",
                    align="start",
                    width="100%",
                ),
                size="2",
                width="100%",
            ),
            # ── Webhook card ──────────────────────────────────────────────
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.vstack(
                            rx.heading("🔔 Completion Webhook", size="4", weight="bold"),
                            rx.text("Notify a web server (e.g. cPanel PHP) when scraping finishes.", size="2", color="gray"),
                            align="start", spacing="0",
                        ),
                        rx.spacer(),
                        rx.vstack(
                            rx.switch(
                                checked=ScrapingControlState.webhook_enabled,
                                on_change=ScrapingControlState.set_webhook_enabled,
                            ),
                            rx.text(
                                rx.cond(ScrapingControlState.webhook_enabled, "Enabled", "Disabled"),
                                size="1",
                                color=rx.cond(ScrapingControlState.webhook_enabled, "green", "gray"),
                            ),
                            align="center", spacing="1",
                        ),
                        width="100%", align="start",
                    ),
                    rx.divider(),
                    rx.text("Webhook URL", size="2", weight="medium"),
                    rx.input(
                        value=ScrapingControlState.completion_webhook_url,
                        on_change=ScrapingControlState.set_completion_webhook_url,
                        placeholder="https://yoursite.com/bf_hook.php",
                        disabled=~ScrapingControlState.webhook_enabled,
                        width="100%",
                    ),
                    rx.text("Secret Token (X-BF-Secret header)", size="2", weight="medium"),
                    rx.input(
                        value=ScrapingControlState.completion_webhook_secret,
                        on_change=ScrapingControlState.set_completion_webhook_secret,
                        placeholder="Random string — prevents strangers from triggering your hook",
                        type="password",
                        disabled=~ScrapingControlState.webhook_enabled,
                        width="100%",
                    ),
                    rx.callout(
                        rx.vstack(
                            rx.text("📌 Local use: PHP on cPanel reads the JSON body and emails you.", size="2", weight="medium"),
                            rx.text(
                                "PHP: check $_SERVER['HTTP_X_BF_SECRET'] matches your secret, then mail() the stats.",
                                size="2",
                            ),
                            rx.text("☁️ Cloud use: same — your scraper server POSTs outbound to cPanel. Works identically.", size="2", weight="medium"),
                            rx.text(
                                "Payload: event, timestamp, total_tenders, total_departments, total_portals, skipped_existing.",
                                size="2", color="gray",
                            ),
                            spacing="1", align="start",
                        ),
                        color_scheme="gray",
                        size="1",
                    ),
                    rx.hstack(
                        rx.button(
                            rx.cond(
                                ScrapingControlState.test_webhook_running,
                                rx.spinner(size="2"),
                                rx.icon("send", size=16),
                            ),
                            " Test Webhook",
                            on_click=ScrapingControlState.test_webhook,
                            color_scheme="gray",
                            variant="outline",
                            size="2",
                            disabled=ScrapingControlState.test_webhook_running,
                        ),
                        rx.spacer(),
                        rx.cond(
                            ScrapingControlState.settings_saved,
                            rx.button(rx.icon("check", size=18), " Saved!", color_scheme="green", variant="soft", size="2", disabled=True),
                            rx.button(rx.icon("save", size=18), " Save", on_click=ScrapingControlState.save_worker_settings, color_scheme="blue", size="2"),
                        ),
                        width="100%",
                    ),
                    spacing="2", align="start", width="100%",
                ),
                size="2", width="100%",
            ),

            # ── Telegram card ─────────────────────────────────────────────
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.vstack(
                            rx.heading("📱 Telegram Notification", size="4", weight="bold"),
                            rx.text("Receive a Telegram message on your phone when scraping finishes.", size="2", color="gray"),
                            align="start", spacing="0",
                        ),
                        rx.spacer(),
                        rx.vstack(
                            rx.switch(
                                checked=ScrapingControlState.telegram_enabled,
                                on_change=ScrapingControlState.set_telegram_enabled,
                            ),
                            rx.text(
                                rx.cond(ScrapingControlState.telegram_enabled, "Enabled", "Disabled"),
                                size="1",
                                color=rx.cond(ScrapingControlState.telegram_enabled, "green", "gray"),
                            ),
                            align="center", spacing="1",
                        ),
                        width="100%", align="start",
                    ),
                    rx.divider(),
                    rx.text("Bot Token", size="2", weight="medium"),
                    rx.input(
                        value=ScrapingControlState.telegram_bot_token,
                        on_change=ScrapingControlState.set_telegram_bot_token,
                        placeholder="123456789:ABCdef...  (get from @BotFather on Telegram)",
                        type="password",
                        disabled=~ScrapingControlState.telegram_enabled,
                        width="100%",
                    ),
                    rx.text("Chat ID", size="2", weight="medium"),
                    rx.input(
                        value=ScrapingControlState.telegram_chat_id,
                        on_change=ScrapingControlState.set_telegram_chat_id,
                        placeholder="Numeric chat ID — see help below",
                        disabled=~ScrapingControlState.telegram_enabled,
                        width="100%",
                    ),
                    rx.callout(
                        rx.vstack(
                            rx.text("How to set up (2 min):", size="2", weight="medium"),
                            rx.text("1. Message @BotFather → /newbot → copy the token above.", size="2"),
                            rx.text("2. Send any message to your new bot.", size="2"),
                            rx.text("3. Open api.telegram.org/bot<TOKEN>/getUpdates in browser → find id inside chat → paste as Chat ID.", size="2"),
                            rx.text("☁️ Cloud use: Telegram is outbound HTTP — works exactly the same whether scraper is local or on a VPS. No changes needed when you migrate.", size="2", weight="medium"),
                            spacing="1", align="start",
                        ),
                        color_scheme="blue",
                        size="1",
                    ),
                    rx.divider(),
                    rx.text("Alert Options", size="2", weight="medium"),
                    rx.hstack(
                        rx.switch(
                            checked=ScrapingControlState.telegram_error_alert,
                            on_change=ScrapingControlState.set_telegram_error_alert,
                            disabled=~ScrapingControlState.telegram_enabled,
                        ),
                        rx.text("Error alert — send when scraping fails", size="2"),
                        spacing="2", align="center",
                    ),
                    rx.hstack(
                        rx.switch(
                            checked=ScrapingControlState.telegram_per_portal_alert,
                            on_change=ScrapingControlState.set_telegram_per_portal_alert,
                            disabled=~ScrapingControlState.telegram_enabled,
                        ),
                        rx.text("Per-portal alert — notify each time a portal finishes (optional)", size="2"),
                        spacing="2", align="center",
                    ),
                    rx.hstack(
                        rx.button(
                            rx.cond(
                                ScrapingControlState.test_telegram_running,
                                rx.spinner(size="2"),
                                rx.icon("send", size=16),
                            ),
                            " Send Test Message",
                            on_click=ScrapingControlState.test_telegram_notification,
                            color_scheme="blue",
                            variant="outline",
                            size="2",
                            disabled=ScrapingControlState.test_telegram_running,
                        ),
                        rx.spacer(),
                        rx.cond(
                            ScrapingControlState.settings_saved,
                            rx.button(rx.icon("check", size=18), " Saved!", color_scheme="green", variant="soft", size="2", disabled=True),
                            rx.button(rx.icon("save", size=18), " Save", on_click=ScrapingControlState.save_worker_settings, color_scheme="blue", size="2"),
                        ),
                        width="100%",
                    ),
                    spacing="2", align="start", width="100%",
                ),
                size="2", width="100%",
            ),

            # ── Post-scrape script card ───────────────────────────────────
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.vstack(
                            rx.heading("⚙️ Post-Scrape Script", size="4", weight="bold"),
                            rx.text("Auto-run a local Python script when scraping finishes.", size="2", color="gray"),
                            align="start", spacing="0",
                        ),
                        rx.spacer(),
                        rx.vstack(
                            rx.switch(
                                checked=ScrapingControlState.post_scrape_script_enabled,
                                on_change=ScrapingControlState.set_post_scrape_script_enabled,
                            ),
                            rx.text(
                                rx.cond(ScrapingControlState.post_scrape_script_enabled, "Enabled", "Disabled"),
                                size="1",
                                color=rx.cond(ScrapingControlState.post_scrape_script_enabled, "green", "gray"),
                            ),
                            align="center", spacing="1",
                        ),
                        width="100%", align="start",
                    ),
                    rx.divider(),
                    rx.text("Script Path (full absolute path to .py file)", size="2", weight="medium"),
                    rx.input(
                        value=ScrapingControlState.post_scrape_script,
                        on_change=ScrapingControlState.set_post_scrape_script,
                        placeholder=r"G:\My Drive\0dev\t84\xscripts\convert_data.py",
                        disabled=~ScrapingControlState.post_scrape_script_enabled,
                        width="100%",
                    ),
                    rx.text("CLI Arguments (optional flags passed to the script)", size="2", weight="medium"),
                    rx.input(
                        value=ScrapingControlState.post_scrape_script_args,
                        on_change=ScrapingControlState.set_post_scrape_script_args,
                        placeholder="e.g.  --mode data   or   --env prod --full",
                        disabled=~ScrapingControlState.post_scrape_script_enabled,
                        width="100%",
                    ),
                    rx.callout(
                        rx.vstack(
                            rx.text("How it works:", size="2", weight="medium"),
                            rx.text("Runs as: python <script_path> <args>  — uses the same Python as the dashboard.", size="2"),
                            rx.text("Timeout: 5 min. Exit code and first 300 chars of output appear in the scraping log.", size="2"),
                            rx.text("Your convert_data.py can import from this project's SQLite normally — path is resolved on the machine running the dashboard.", size="2"),
                            rx.text(
                                "☁️ Cloud note: this only works when BOTH projects run on the same cloud server. "
                                "If they are on different machines, use the Webhook (cPanel PHP can exec() your convert script) "
                                "or Telegram to get notified and run manually.",
                                size="2", weight="medium",
                            ),
                            spacing="1", align="start",
                        ),
                        color_scheme="green",
                        size="1",
                    ),
                    rx.hstack(
                        rx.button(
                            rx.cond(
                                ScrapingControlState.test_script_running,
                                rx.spinner(size="2"),
                                rx.icon("play", size=16),
                            ),
                            " Dry Run",
                            on_click=ScrapingControlState.test_post_scrape_script,
                            color_scheme="green",
                            variant="outline",
                            size="2",
                            disabled=ScrapingControlState.test_script_running,
                        ),
                        rx.spacer(),
                        rx.cond(
                            ScrapingControlState.settings_saved,
                            rx.button(rx.icon("check", size=18), " Saved!", color_scheme="green", variant="soft", size="2", disabled=True),
                            rx.button(rx.icon("save", size=18), " Save", on_click=ScrapingControlState.save_worker_settings, color_scheme="blue", size="2"),
                        ),
                        width="100%",
                    ),
                    spacing="2", align="start", width="100%",
                ),
                size="2", width="100%",
            ),
            # ── Scheduled Auto-Scrape card ────────────────────────────────
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.vstack(
                            rx.heading("⏰ Scheduled Auto-Scrape", size="4", weight="bold"),
                            rx.text("Automatically start scraping at a fixed time every day.", size="2", color="gray"),
                            align="start", spacing="0",
                        ),
                        rx.spacer(),
                        rx.vstack(
                            rx.switch(
                                checked=ScrapingControlState.scheduler_enabled,
                                on_change=ScrapingControlState.set_scheduler_enabled,
                            ),
                            rx.text(
                                rx.cond(ScrapingControlState.scheduler_enabled, "Enabled", "Disabled"),
                                size="1",
                                color=rx.cond(ScrapingControlState.scheduler_enabled, "green", "gray"),
                            ),
                            align="center", spacing="1",
                        ),
                        width="100%", align="start",
                    ),
                    rx.divider(),
                    rx.hstack(
                        rx.vstack(
                            rx.text("Hour (0–23)", size="2", weight="medium"),
                            rx.input(
                                value=ScrapingControlState.scheduler_hour,
                                on_change=ScrapingControlState.set_scheduler_hour,
                                placeholder="2",
                                type="number",
                                width="100px",
                                disabled=~ScrapingControlState.scheduler_enabled,
                            ),
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text("Minute (0–59)", size="2", weight="medium"),
                            rx.input(
                                value=ScrapingControlState.scheduler_minute,
                                on_change=ScrapingControlState.set_scheduler_minute,
                                placeholder="0",
                                type="number",
                                width="100px",
                                disabled=~ScrapingControlState.scheduler_enabled,
                            ),
                            spacing="1",
                        ),
                        spacing="4", align="start",
                    ),
                    rx.text("Portals to scrape (comma-separated names, blank = all)", size="2", weight="medium"),
                    rx.input(
                        value=ScrapingControlState.scheduler_portals,
                        on_change=ScrapingControlState.set_scheduler_portals,
                        placeholder="Leave blank to scrape all portals",
                        disabled=~ScrapingControlState.scheduler_enabled,
                        width="100%",
                    ),
                    rx.callout(
                        rx.vstack(
                            rx.text("⚠️ The dashboard must be running for the schedule to trigger.", size="2", weight="medium"),
                            rx.text("Uses local server time. The scheduler checks every 30 s — fires within 30 s of the set time.", size="2"),
                            rx.text("If scraping is already in progress at trigger time, the scheduled run is skipped until next day.", size="2"),
                            spacing="1", align="start",
                        ),
                        color_scheme="orange",
                        size="1",
                    ),
                    rx.hstack(
                        rx.spacer(),
                        rx.cond(
                            ScrapingControlState.settings_saved,
                            rx.button(rx.icon("check", size=18), " Saved!", color_scheme="green", variant="soft", size="2", disabled=True),
                            rx.button(rx.icon("save", size=18), " Save", on_click=ScrapingControlState.save_worker_settings, color_scheme="blue", size="2"),
                        ),
                        width="100%",
                    ),
                    spacing="2", align="start", width="100%",
                ),
                size="2", width="100%",
            ),

            # ── Health Watchdog card ──────────────────────────────────────
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.vstack(
                            rx.heading("🐕 Health Watchdog", size="4", weight="bold"),
                            rx.text("Alert via Telegram if scraping stalls with no progress.", size="2", color="gray"),
                            align="start", spacing="0",
                        ),
                        rx.spacer(),
                        rx.vstack(
                            rx.switch(
                                checked=ScrapingControlState.watchdog_enabled,
                                on_change=ScrapingControlState.set_watchdog_enabled,
                            ),
                            rx.text(
                                rx.cond(ScrapingControlState.watchdog_enabled, "Enabled", "Disabled"),
                                size="1",
                                color=rx.cond(ScrapingControlState.watchdog_enabled, "green", "gray"),
                            ),
                            align="center", spacing="1",
                        ),
                        width="100%", align="start",
                    ),
                    rx.divider(),
                    rx.text("Stall threshold (minutes)", size="2", weight="medium"),
                    rx.hstack(
                        rx.input(
                            value=ScrapingControlState.watchdog_stall_minutes.to_string(),
                            on_change=ScrapingControlState.set_watchdog_stall_minutes,
                            type="number",
                            width="120px",
                            disabled=~ScrapingControlState.watchdog_enabled,
                        ),
                        rx.text("minutes without new tenders/departments triggers the alert", size="2", color="gray"),
                        spacing="2", align="center",
                    ),
                    rx.callout(
                        rx.vstack(
                            rx.text("Monitors total tenders and departments counters every minute.", size="2"),
                            rx.text("Sends one alert per stall event. Resets automatically if scraping resumes.", size="2"),
                            rx.text("Requires Telegram to be enabled and configured.", size="2", weight="medium"),
                            spacing="1", align="start",
                        ),
                        color_scheme="orange",
                        size="1",
                    ),
                    rx.hstack(
                        rx.spacer(),
                        rx.cond(
                            ScrapingControlState.settings_saved,
                            rx.button(rx.icon("check", size=18), " Saved!", color_scheme="green", variant="soft", size="2", disabled=True),
                            rx.button(rx.icon("save", size=18), " Save", on_click=ScrapingControlState.save_worker_settings, color_scheme="blue", size="2"),
                        ),
                        width="100%",
                    ),
                    spacing="2", align="start", width="100%",
                ),
                size="2", width="100%",
            ),

            rx.card(
                rx.vstack(
                    rx.heading("Behavior Notes", size="4", weight="bold"),
                    rx.callout(
                        rx.text(
                            "Dashboard now supports crash-safe checkpoint resume for pending portals and in-portal department progress. "
                            "Use Resume Checkpoint on the Scraping page after restart.",
                            size="2",
                        ),
                        color_scheme="blue",
                        size="1",
                    ),
                    rx.callout(
                        rx.text(
                            "Duplicate tenders are checked against database records in scraping logic and skipped when already present.",
                            size="2",
                        ),
                        color_scheme="green",
                        size="1",
                    ),
                    spacing="2",
                    width="100%",
                    align="start",
                ),
                size="2",
                width="100%",
            ),
            spacing="4",
            width="100%",
            padding="2rem",
            max_width="1200px",
            margin_x="auto",
            on_mount=ScrapingControlState.initialize_page,
        ),
        width="100%",
    )


def scraping_control_page() -> rx.Component:
    return rx.box(
        rx.vstack(
            # Navigation bar
            rx.hstack(
                rx.link(
                    rx.button(
                        rx.icon("bar-chart-2"),
                        "Dashboard",
                        variant="soft",
                        size="2",
                    ),
                    href="/",
                ),
                rx.link(
                    rx.button(
                        rx.icon("globe"),
                        "Portal Management",
                        variant="soft",
                        size="2",
                    ),
                    href="/portals",
                ),
                rx.link(
                    rx.button(
                        rx.icon("database"),
                        "Data Visualization",
                        variant="soft",
                        size="2",
                    ),
                    href="/data",
                ),
                rx.link(
                    rx.button(
                        rx.icon("zap"),
                        "Scraping Control",
                        variant="soft",
                        size="2",
                        color_scheme="green",
                    ),
                    href="/scraping",
                ),
                rx.link(
                    rx.button(
                        rx.icon("upload"),
                        "Import Data",
                        variant="soft",
                        size="2",
                        color_scheme="orange",
                    ),
                    href="/import",
                ),
                spacing="2",
                padding="0.5rem 0",
            ),
            rx.divider(),
            rx.heading("🚀 Scraping Control Center", size="7", weight="bold", margin_bottom="1rem"),
            rx.callout(
                rx.text(
                    "Real-time process-based scraping with detailed per-worker progress, "
                    "department/tender percentages, and global worker aggregation.",
                    size="2",
                ),
                color_scheme="green",
                size="1",
                margin_bottom="1rem",
            ),

            # Isolated decorative hero visuals (separate module/state)
            hero_visual_section(),
            
            # Portal Status Dashboard - NEW!
            portal_status_dashboard(),
            
            rx.grid(
                rx.vstack(portal_selector(), worker_config_panel(), control_buttons(), spacing="3"),
                rx.vstack(progress_stats(), worker_status_cards(), spacing="3"),
                columns="2",
                spacing="4",
                width="100%",
            ),
            log_viewer(),
            spacing="4",
            width="100%",
            padding="2rem",
            max_width="1600px",
            margin_x="auto",
            on_mount=ScrapingControlState.initialize_page,
        ),
        width="100%",
    )
