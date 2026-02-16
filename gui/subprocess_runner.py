# gui/subprocess_runner.py
# Subprocess management for GUI-controlled CLI execution.

import json
import os
import subprocess
import threading
import time
from typing import Callable, Optional


class SubprocessRunner:
    """Runs and monitors a CLI subprocess with optional JSON event parsing."""

    def __init__(
        self,
        command,
        cwd,
        on_log: Optional[Callable[[str], None]] = None,
        on_event: Optional[Callable[[dict], None]] = None,
        on_exit: Optional[Callable[[int], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        tail_log_file: Optional[str] = None,
    ):
        self.command = list(command or [])
        self.cwd = str(cwd)
        self.on_log = on_log
        self.on_event = on_event
        self.on_exit = on_exit
        self.on_error = on_error
        self.tail_log_file = tail_log_file

        self.process = None
        self._lock = threading.Lock()
        self._stop_requested = threading.Event()
        self._threads = []

    def is_running(self):
        with self._lock:
            return self.process is not None and self.process.poll() is None

    def start(self):
        if not self.command:
            raise ValueError("Subprocess command is empty")

        with self._lock:
            if self.process is not None and self.process.poll() is None:
                raise RuntimeError("Subprocess is already running")

            self.process = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                env={
                    **os.environ,
                    "PYTHONUTF8": "1",
                    "PYTHONIOENCODING": "utf-8",
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )

        self._emit_log("Subprocess started: " + " ".join(self.command))

        stdout_thread = threading.Thread(target=self._read_stream, args=(self.process.stdout, False), daemon=True)
        stderr_thread = threading.Thread(target=self._read_stream, args=(self.process.stderr, True), daemon=True)
        waiter_thread = threading.Thread(target=self._wait_for_exit, daemon=True)
        self._threads.extend([stdout_thread, stderr_thread, waiter_thread])

        stdout_thread.start()
        stderr_thread.start()
        waiter_thread.start()

        if self.tail_log_file:
            tail_thread = threading.Thread(target=self._tail_log_file, daemon=True)
            self._threads.append(tail_thread)
            tail_thread.start()

    def stop(self, timeout_sec=3.0):
        self._stop_requested.set()
        proc = self.process
        if not proc:
            return

        if proc.poll() is not None:
            return

        try:
            proc.terminate()
        except Exception:
            pass

        deadline = time.time() + max(0.5, float(timeout_sec or 3.0))
        while time.time() < deadline:
            if proc.poll() is not None:
                return
            time.sleep(0.1)

        try:
            proc.kill()
        except Exception:
            pass

    def _emit_log(self, message):
        if self.on_log:
            try:
                self.on_log(str(message))
            except Exception:
                pass

    def _emit_event(self, event):
        if self.on_event:
            try:
                self.on_event(event)
            except Exception:
                pass

    def _emit_error(self, message):
        if self.on_error:
            try:
                self.on_error(str(message))
            except Exception:
                pass

    def _read_stream(self, stream, is_stderr):
        if not stream:
            return

        for raw_line in iter(stream.readline, ""):
            line = str(raw_line or "").strip()
            if not line:
                continue

            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)
                    if isinstance(data, dict) and data.get("type"):
                        self._emit_event(data)
                        continue
                except Exception:
                    pass

            if is_stderr:
                self._emit_error(line)
            else:
                self._emit_log(line)

    def _wait_for_exit(self):
        proc = self.process
        if not proc:
            return

        exit_code = proc.wait()
        self._emit_log(f"Subprocess exited with code: {exit_code}")
        if self.on_exit:
            try:
                self.on_exit(int(exit_code))
            except Exception:
                pass

    def _tail_log_file(self):
        path = self.tail_log_file
        if not path:
            return

        try:
            while not self._stop_requested.is_set() and not os.path.exists(path):
                if not self.is_running():
                    return
                time.sleep(0.2)

            if not os.path.exists(path):
                return

            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                handle.seek(0, os.SEEK_END)
                while not self._stop_requested.is_set():
                    line = handle.readline()
                    if line:
                        text = line.rstrip("\r\n")
                        if text:
                            self._emit_log(f"[CLI-LOG] {text}")
                        continue
                    if not self.is_running():
                        return
                    time.sleep(0.2)
        except Exception as err:
            self._emit_error(f"Log tail error: {err}")
