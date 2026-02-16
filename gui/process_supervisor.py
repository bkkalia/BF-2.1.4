# gui/process_supervisor.py
# Shared subprocess orchestration supervisor for GUI-controlled CLI jobs.

import threading
import time
import uuid
from datetime import datetime

from gui.subprocess_runner import SubprocessRunner


class ProcessSupervisor:
    """Tracks and controls CLI subprocess jobs with heartbeat monitoring."""

    def __init__(self, heartbeat_timeout_sec=180, heartbeat_check_sec=5):
        self.heartbeat_timeout_sec = max(30, int(heartbeat_timeout_sec or 180))
        self.heartbeat_check_sec = max(1, int(heartbeat_check_sec or 5))
        self._jobs = {}
        self._lock = threading.Lock()
        self._shutdown = threading.Event()

        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, name="ProcessSupervisorWatchdog", daemon=True)
        self._watchdog_thread.start()

    def create_job_id(self, prefix="job"):
        token = uuid.uuid4().hex[:10]
        return f"{prefix}_{token}"

    def start_job(
        self,
        job_id,
        command,
        cwd,
        group="default",
        tail_log_file=None,
        on_log=None,
        on_event=None,
        on_state_change=None,
        on_exit=None,
        on_error=None,
    ):
        if not job_id:
            raise ValueError("job_id is required")

        with self._lock:
            existing = self._jobs.get(job_id)
            if existing and existing.get("state") in {"starting", "running", "stopping"}:
                raise RuntimeError(f"job '{job_id}' is already active")

        started_at = datetime.utcnow().isoformat() + "Z"
        state_payload = {
            "job_id": job_id,
            "group": str(group or "default"),
            "state": "starting",
            "started_at": started_at,
            "last_event_at": time.time(),
            "last_event_type": "start",
            "command": list(command or []),
        }

        def _emit_state(new_state, reason=None):
            with self._lock:
                job = self._jobs.get(job_id, state_payload)
                job["state"] = str(new_state)
                job["last_event_at"] = time.time()
                job["last_event_type"] = str(reason or new_state)
                self._jobs[job_id] = job
            if on_state_change:
                try:
                    on_state_change(job_id, new_state, reason)
                except Exception:
                    pass

        def _handle_log(message):
            with self._lock:
                job = self._jobs.get(job_id, state_payload)
                job["last_event_at"] = time.time()
                job["last_event_type"] = "log"
                self._jobs[job_id] = job
            if on_log:
                try:
                    on_log(message)
                except Exception:
                    pass

        def _handle_event(event):
            event_type = str((event or {}).get("type", "event")).strip().lower() or "event"
            with self._lock:
                job = self._jobs.get(job_id, state_payload)
                job["last_event_at"] = time.time()
                job["last_event_type"] = event_type
                self._jobs[job_id] = job

            if event_type in {"start", "portal", "departments_loaded", "progress", "status"}:
                _emit_state("running", reason=event_type)
            elif event_type in {"completed"}:
                _emit_state("completed", reason=event_type)
            elif event_type in {"error"}:
                _emit_state("failed", reason=event_type)
            elif event_type in {"cancelled"}:
                _emit_state("cancelled", reason=event_type)

            if on_event:
                try:
                    on_event(event)
                except Exception:
                    pass

        def _handle_error(message):
            with self._lock:
                job = self._jobs.get(job_id, state_payload)
                job["last_event_at"] = time.time()
                job["last_event_type"] = "stderr"
                self._jobs[job_id] = job
            if on_error:
                try:
                    on_error(message)
                except Exception:
                    pass

        def _handle_exit(exit_code):
            if int(exit_code) == 0:
                _emit_state("completed", reason="exit_0")
            else:
                current = self.get_job(job_id)
                if current.get("state") == "stopping":
                    _emit_state("cancelled", reason=f"exit_{exit_code}")
                else:
                    _emit_state("failed", reason=f"exit_{exit_code}")
            if on_exit:
                try:
                    on_exit(int(exit_code))
                except Exception:
                    pass

        runner = SubprocessRunner(
            command=command,
            cwd=cwd,
            on_log=_handle_log,
            on_event=_handle_event,
            on_exit=_handle_exit,
            on_error=_handle_error,
            tail_log_file=tail_log_file,
        )

        state_payload["runner"] = runner
        with self._lock:
            self._jobs[job_id] = state_payload

        runner.start()
        _emit_state("running", reason="spawned")
        return job_id

    def stop_job(self, job_id, force=False, timeout_sec=3.0):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            runner = job.get("runner")
            if not runner:
                return False
            job["state"] = "stopping"
            job["last_event_at"] = time.time()
            job["last_event_type"] = "stop_request"
            self._jobs[job_id] = job

        try:
            runner.stop(timeout_sec=0 if force else timeout_sec)
            return True
        except Exception:
            return False

    def stop_group(self, group, force=False):
        target = str(group or "").strip()
        job_ids = []
        with self._lock:
            for job_id, job in self._jobs.items():
                if str(job.get("group", "")).strip() == target and str(job.get("state", "")).lower() in {"starting", "running", "stopping"}:
                    job_ids.append(job_id)
        stopped_any = False
        for job_id in job_ids:
            stopped_any = self.stop_job(job_id, force=force) or stopped_any
        return stopped_any

    def stop_all(self, force=False):
        with self._lock:
            job_ids = [
                job_id for job_id, job in self._jobs.items()
                if str(job.get("state", "")).lower() in {"starting", "running", "stopping"}
            ]
        stopped_any = False
        for job_id in job_ids:
            stopped_any = self.stop_job(job_id, force=force) or stopped_any
        return stopped_any

    def get_job(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return {}
            return {
                "job_id": job_id,
                "group": job.get("group"),
                "state": job.get("state"),
                "last_event_type": job.get("last_event_type"),
                "last_event_at": job.get("last_event_at"),
                "command": list(job.get("command") or []),
                "started_at": job.get("started_at"),
            }

    def _watchdog_loop(self):
        while not self._shutdown.is_set():
            now = time.time()
            with self._lock:
                candidates = [
                    (job_id, job) for job_id, job in self._jobs.items()
                    if str(job.get("state", "")).lower() in {"starting", "running"}
                ]

            for job_id, job in candidates:
                last_event_at = float(job.get("last_event_at") or now)
                if (now - last_event_at) < self.heartbeat_timeout_sec:
                    continue
                self.stop_job(job_id, force=True)
                with self._lock:
                    current = self._jobs.get(job_id)
                    if current:
                        current["state"] = "failed"
                        current["last_event_type"] = "heartbeat_timeout"
                        current["last_event_at"] = time.time()
                        self._jobs[job_id] = current

            self._shutdown.wait(self.heartbeat_check_sec)

    def shutdown(self):
        self._shutdown.set()
        self.stop_all(force=True)
