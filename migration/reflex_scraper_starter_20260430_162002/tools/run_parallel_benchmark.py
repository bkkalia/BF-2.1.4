import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


PORTALS = [
    ("Haryana", "haryana"),
    ("Chandigarh", "chandigarh"),
    ("CPPP1 eProcure", "cppp1"),
    ("CPPP2 eTenders", "cppp2"),
    ("Uttar Pradesh", "up"),
]


def _extract_metrics(log_text: str) -> dict:
    def _m(pattern: str):
        m = re.search(pattern, log_text, flags=re.IGNORECASE)
        return m.group(1) if m else None

    return {
        "processed_departments": _m(r"Processed\s+(\d+)\s+departments"),
        "total_tenders_found": _m(r"Total tenders found:\s*(\d+)"),
        "elapsed_summary_seconds": _m(r"Total Elapsed Time:\s*([0-9.]+)s"),
        "elapsed_completed_seconds": _m(r"Scraping completed in\s*([0-9.]+)\s*seconds"),
        "throughput_per_min": _m(r"New Tenders:\s*([0-9.]+)\s*per minute"),
        "worker_efficiency_pct": _m(r"Worker Efficiency:\s*([0-9.]+)%"),
        "workers_successful": _m(r"Workers Successful:\s*([^\n\r]+)"),
        "sqlite_rows_saved": _m(r"SQLite save: SUCCESS \| run_id=\d+ \| rows=(\d+)"),
        "sqlite_run_id": _m(r"SQLite save: SUCCESS \| run_id=(\d+)"),
        "export_path": _m(r"\[FINAL\] Export path:\s*([^\n\r]+)"),
        "app_completed": bool(re.search(r"Scraping completed successfully", log_text, flags=re.IGNORECASE)),
    }



def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    python_exe = project_root / ".venv" / "Scripts" / "python.exe"
    downloads_dir = Path(r"C:\Users\kalia\Downloads")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = project_root / "logs" / "parallel_benchmark"
    report_dir = project_root / "batch_run_reports" / "manual_reports"
    log_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    jobs = []
    start_epoch = time.time()

    print(f"[PARALLEL] Starting {len(PORTALS)} portal runs at {datetime.now().isoformat(timespec='seconds')}")

    for portal_name, slug in PORTALS:
        log_path = log_dir / f"{slug}_{ts}.log"
        cmd = [
            str(python_exe),
            "cli_main.py",
            "--engine",
            "playwright",
            "--url",
            portal_name,
            "--output",
            str(downloads_dir),
            "department",
            "--all",
            "--dept-workers",
            "3",
        ]

        log_handle = open(log_path, "w", encoding="utf-8", errors="replace")
        proc = subprocess.Popen(
            cmd,
            cwd=str(project_root),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )

        jobs.append(
            {
                "portal": portal_name,
                "slug": slug,
                "cmd": cmd,
                "log_path": str(log_path),
                "process": proc,
                "log_handle": log_handle,
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "start_epoch": time.time(),
            }
        )
        print(f"[PARALLEL] Launched {portal_name} | pid={proc.pid} | log={log_path}")

    remaining = len(jobs)
    while remaining > 0:
        remaining = 0
        for job in jobs:
            proc = job["process"]
            if proc.poll() is None:
                remaining += 1
        if remaining > 0:
            print(f"[PARALLEL] Running jobs: {remaining}")
            time.sleep(20)

    total_wall = round(time.time() - start_epoch, 2)

    for job in jobs:
        job["ended_at"] = datetime.now().isoformat(timespec="seconds")
        job["return_code"] = int(job["process"].returncode)
        job["wall_seconds"] = round(time.time() - job["start_epoch"], 2)
        job["log_handle"].flush()
        job["log_handle"].close()

        text = Path(job["log_path"]).read_text(encoding="utf-8", errors="replace")
        job["metrics"] = _extract_metrics(text)

        del job["process"]
        del job["log_handle"]
        del job["start_epoch"]

    report = {
        "started_at": datetime.fromtimestamp(start_epoch).isoformat(timespec="seconds"),
        "ended_at": datetime.now().isoformat(timespec="seconds"),
        "total_wall_seconds": total_wall,
        "engine": "playwright",
        "dept_workers_per_portal": 3,
        "portals": jobs,
    }

    report_path = report_dir / f"parallel_benchmark_{ts}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== PARALLEL BENCHMARK SUMMARY ===")
    print(f"total_wall_seconds={total_wall}")
    for job in jobs:
        m = job.get("metrics", {})
        print(
            f"- {job['portal']}: rc={job['return_code']} | wall={job['wall_seconds']}s | "
            f"depts={m.get('processed_departments')} | tenders={m.get('total_tenders_found')} | "
            f"sqlite_rows={m.get('sqlite_rows_saved')}"
        )
    print(f"report={report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
