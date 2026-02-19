# pyright: reportArgumentType=false, reportCallIssue=false, reportAttributeAccessIssue=false
"""
Scraping Control Page - Real-time tender scraping with process-based workers.
"""

import asyncio
import json
import queue as py_queue
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import reflex as rx
from pydantic import BaseModel


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
    last_update: str = ""


class ScrapingControlState(rx.State):
    """State management for scraping control page."""

    available_portals: List[Dict[str, str]] = []
    selected_portals: List[str] = []

    worker_count: int = 2
    worker_names: List[str] = ["Worker 1", "Worker 2", "Worker 3", "Worker 4"]

    workers: List[WorkerStatus] = []

    is_scraping: bool = False
    scraping_start_time: Optional[str] = None

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
    def has_checkpoint(self) -> bool:
        return self.checkpoint_available

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
            )

            self.add_log("Initializing worker processes...")
            yield
            updates_queue: py_queue.Queue = py_queue.Queue()

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

            self.is_scraping = False
            self.auto_refresh_enabled = False
            self.resume_mode = False
            self._clear_checkpoint_file()
            self.checkpoint_available = False
            self.checkpoint_remaining_portals = 0
            self.checkpoint_summary = ""
            self.portal_progress = {}
            self.add_log("Scraping completed!")
            yield

        except Exception as e:
            self.add_log(f"ERROR: {str(e)}")
            self.is_scraping = False
            self.auto_refresh_enabled = False
            self._save_checkpoint()
            yield

    def _update_progress_sync(self, update_data: Dict):
        """Update progress from worker callback."""
        try:
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
                        last_update=datetime.now().isoformat(),
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
        if not self.is_scraping:
            return

        self.add_log("Stopping scraping...")
        self.is_scraping = False
        self.auto_refresh_enabled = False
        self._save_checkpoint()

    def clear_logs(self):
        self.log_messages = []


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
            rx.callout(
                rx.text(
                    "Process-based workers avoid UI freeze and provide better throughput. "
                    "Set names and defaults in Scraping Settings.",
                    size="2",
                ),
                color_scheme="blue",
                size="1",
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
                rx.button(
                    rx.icon("play", size=16),
                    " Start Scraping",
                    on_click=ScrapingControlState.start_scraping,
                    disabled=ScrapingControlState.is_scraping,
                    color_scheme="green",
                    size="3",
                    variant="solid",
                ),
                rx.button(
                    rx.icon("square", size=16),
                    " Stop",
                    on_click=ScrapingControlState.stop_scraping,
                    disabled=~ScrapingControlState.is_scraping,
                    color_scheme="red",
                    size="3",
                    variant="soft",
                ),
                spacing="2",
            ),
            rx.hstack(
                rx.button(
                    rx.icon("rotate-ccw", size=14),
                    " Resume Checkpoint",
                    on_click=ScrapingControlState.resume_from_checkpoint,
                    disabled=ScrapingControlState.is_scraping | (~ScrapingControlState.has_checkpoint),
                    color_scheme="blue",
                    variant="soft",
                    size="2",
                ),
                rx.button(
                    "Clear Checkpoint",
                    on_click=ScrapingControlState.clear_checkpoint,
                    disabled=~ScrapingControlState.has_checkpoint,
                    variant="outline",
                    size="2",
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
            rx.heading("Global Progress", size="4", weight="bold"),
            rx.grid(
                rx.box(rx.text("Tenders Found", size="1", color="gray"), rx.heading(ScrapingControlState.total_tenders_found, size="5", color="blue")),
                rx.box(rx.text("Departments", size="1", color="gray"), rx.heading(ScrapingControlState.total_departments_processed, size="5", color="purple")),
                rx.box(rx.text("Portals Done", size="1", color="gray"), rx.heading(ScrapingControlState.total_portals_completed, size="5", color="green")),
                rx.box(rx.text("Active Workers", size="1", color="gray"), rx.heading(ScrapingControlState.active_workers, size="5", color="orange")),
                rx.box(rx.text("Skipped Existing", size="1", color="gray"), rx.heading(ScrapingControlState.total_skipped_existing, size="5", color="gray")),
                rx.box(rx.text("Date Reprocessed", size="1", color="gray"), rx.heading(ScrapingControlState.total_closing_date_reprocessed, size="5", color="indigo")),
                columns="6",
                spacing="4",
                width="100%",
            ),
            rx.divider(),
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
                            spacing="2",
                            width="100%",
                        ),
                        rx.cond(
                            worker.portal_name != "",
                            rx.text(f"Portal: {worker.portal_name}", size="2", weight="medium", color="blue"),
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
                    rx.button("Reset Names", on_click=ScrapingControlState.reset_worker_names, variant="outline", size="2"),
                    spacing="2",
                    align="start",
                    width="100%",
                ),
                size="2",
                width="100%",
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
