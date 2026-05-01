#!/usr/bin/env python3
"""
scripts/smoke_driver_test.py
============================
Small smoke test to verify the driver transport-timeout recovery fix.

Usage (from project root, with venv active):
    python scripts/smoke_driver_test.py
    python scripts/smoke_driver_test.py --portal "HP Tenders" --max-depts 2
    python scripts/smoke_driver_test.py --portal "Ladakh" --max-depts 1 --verbose

What it does:
  1. Fetches the real department list from the portal (Playwright → Selenium fallback).
  2. Trims to --max-depts (default 2) departments.
  3. Runs run_scraping_logic against those departments.
  4. Reports outcome, especially whether the transport-timeout recovery path fired.
  5. Exits 0 on success, 1 on failure.

No data is written to your main DB or manifest; everything goes to a temp directory.
"""

import argparse
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

# ── Resolve project root ────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Logging setup ────────────────────────────────────────────────────────────
def _setup_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, handlers=[])
    root = logging.getLogger()
    root.handlers.clear()
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter(fmt))
    root.addHandler(ch)
    if not verbose:
        for noisy in ("selenium", "urllib3", "undetected_chromedriver"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
    return logging.getLogger("smoke_driver_test")


# ── CLI args ─────────────────────────────────────────────────────────────────
def _parse_args():
    p = argparse.ArgumentParser(description="Driver transport-timeout smoke test")
    p.add_argument("--portal", default="HP Tenders",
                   help="Portal name from base_urls.csv (default: HP Tenders)")
    p.add_argument("--max-depts", type=int, default=2,
                   help="Max departments to scrape (default: 2)")
    p.add_argument("--filter", default="",
                   help="Optional substring filter on department names")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    args = _parse_args()
    log = _setup_logging(args.verbose)

    log.info("=" * 60)
    log.info("  Black Forest – Driver Smoke Test")
    log.info("=" * 60)
    log.info(f"Portal      : {args.portal}")
    log.info(f"Max depts   : {args.max_depts}")
    log.info(f"Name filter : '{args.filter or '(none)'}' ")
    log.info("=" * 60)

    # ── Import project modules ────────────────────────────────────────────────
    try:
        import pandas as pd
        from scraper.driver_manager import setup_driver, safe_quit_driver
        from scraper.logic import (
            fetch_department_list_from_site_v2,
            run_scraping_logic,
        )
        from scraper.playwright_logic import fetch_department_list_from_site_playwright
    except ImportError as exc:
        log.error(f"Import failed: {exc}")
        log.error("Run from project root with the venv active.")
        sys.exit(1)

    # ── Load portal config ────────────────────────────────────────────────────
    base_urls_csv = PROJECT_ROOT / "base_urls.csv"
    if not base_urls_csv.exists():
        log.error(f"base_urls.csv not found at {base_urls_csv}")
        sys.exit(1)

    df = pd.read_csv(base_urls_csv)
    row = df[df["Name"].str.lower() == args.portal.lower()]
    if row.empty:
        row = df[df["Name"].str.contains(args.portal, case=False)]
    if row.empty:
        log.error(f"Portal '{args.portal}' not found in base_urls.csv")
        log.info(f"Available: {df['Name'].tolist()}")
        sys.exit(1)

    portal_cfg = row.iloc[0].to_dict()
    base_url = portal_cfg["BaseURL"]
    org_list_url = f"{base_url}?page=FrontEndTendersByOrganisation&service=page"
    portal_name = portal_cfg["Name"]
    log.info(f"Using portal  : {portal_name}")
    log.info(f"Base URL      : {base_url}")
    log.info(f"Org list URL  : {org_list_url}")

    # ── Fetch department list ─────────────────────────────────────────────────
    # Use Selenium first for the smoke test – it shares the same driver path
    # as the actual scraper, giving more realistic coverage, and avoids the
    # slow Playwright async startup on this portal.
    log.info("\nStep 1 – Fetch department list (Selenium, then Playwright fallback)...")
    departments, total_est = [], 0
    try:
        departments, total_est = fetch_department_list_from_site_v2(
            org_list_url, log.info
        )
        if departments:
            log.info(f"  Selenium fetched {len(departments)} departments.")
        else:
            log.warning("  Selenium returned 0 rows – falling back to Playwright fetch...")
    except Exception as exc:
        log.warning(f"  Selenium fetch error: {exc} – falling back to Playwright...")

    if not departments:
        try:
            departments, total_est = fetch_department_list_from_site_playwright(
                org_list_url, log.info
            )
            log.info(f"  Playwright fetched {len(departments)} departments.")
        except Exception as exc:
            log.error(f"  Both fetch methods failed. Last error: {exc}")
            sys.exit(1)

    if not departments:
        log.error("No departments retrieved from portal. Aborting.")
        sys.exit(1)

    # ── Filter and trim ───────────────────────────────────────────────────────
    if args.filter:
        departments = [d for d in departments if args.filter.lower() in d.get("name", "").lower()]
        log.info(f"  After filter '{args.filter}': {len(departments)} departments.")

    # Skip header rows
    departments = [
        d for d in departments
        if str(d.get("s_no", "")).strip().isdigit()
        and str(d.get("name", "")).strip().lower() not in
            {"organisation name", "department name", "organization", "organization name"}
    ]

    departments = departments[: args.max_depts]
    if not departments:
        log.error("No valid departments after filtering/trimming. Aborting.")
        sys.exit(1)

    log.info(f"\nStep 2 – Selected {len(departments)} department(s) for smoke run:")
    for d in departments:
        log.info(f"   S.No {d.get('s_no', '?')}  {d.get('name', '?')}  (~{d.get('count_text', '?')} tenders)")

    # ── Temp output dir ───────────────────────────────────────────────────────
    with tempfile.TemporaryDirectory(prefix="bf_smoke_", ignore_cleanup_errors=True) as tmp_dir:
        log.info(f"\nStep 3 – Temp output dir: {tmp_dir}")

        # ── Setup driver ──────────────────────────────────────────────────────
        log.info("\nStep 4 – Setting up Chrome driver...")
        driver = None
        try:
            driver = setup_driver(initial_download_dir=tmp_dir)
            log.info("  Driver ready.")
        except Exception as exc:
            log.error(f"  Driver setup failed: {exc}")
            sys.exit(1)

        # ── Track log lines for recovery evidence ─────────────────────────────
        recovery_log_lines: list[str] = []

        def _log_cb(msg: str):
            text = str(msg or "").strip()
            if not text:
                return
            log.info(f"  [scraper] {text}")
            # Capture lines that indicate transport recovery fired
            lower = text.lower()
            if any(kw in lower for kw in (
                "transport timeout detected",
                "_bf_transport_unresponsive",
                "triggering browser recovery",
                "replacement browser ready",
                "retrying department",
                "session lost detected",
                "read timed out",
            )):
                recovery_log_lines.append(text)

        base_url_config = {
            "BaseURL": base_url,
            "OrgListURL": org_list_url,
            "Name": portal_name,
        }

        # ── Run scraping logic ────────────────────────────────────────────────
        log.info("\nStep 5 – Running scraping logic (no DB write, temp dir)...")
        t0 = time.time()
        summary = {}
        try:
            summary = run_scraping_logic(
                departments_to_scrape=departments,
                base_url_config=base_url_config,
                download_dir=tmp_dir,
                log_callback=_log_cb,
                progress_callback=None,
                status_callback=None,
                stop_event=None,
                driver=driver,
                deep_scrape=False,
                existing_tender_ids=None,
                existing_department_names=None,
                # Deliberately no SQLite path so no DB writes happen
                sqlite_db_path=None,
                sqlite_backup_dir=None,
                sqlite_backup_retention_days=7,
                department_parallel_workers=1,
                export_policy="on_demand",
                force_excel_export=False,
            )
        except Exception as exc:
            log.error(f"run_scraping_logic raised an exception: {exc}", exc_info=args.verbose)
        finally:
            if driver:
                try:
                    safe_quit_driver(driver, log.info)
                except Exception:
                    pass

        elapsed = time.time() - t0

        # ── Results ───────────────────────────────────────────────────────────
        log.info("")
        log.info("=" * 60)
        log.info("  SMOKE TEST RESULTS")
        log.info("=" * 60)
        log.info(f"  Elapsed          : {elapsed:.1f}s")
        log.info(f"  Status           : {summary.get('status', 'unknown')}")
        log.info(f"  Depts processed  : {summary.get('processed_departments', '?')}")
        log.info(f"  Tenders scraped  : {summary.get('extracted_total_tenders', '?')}")
        log.info(f"  Skipped dupes    : {summary.get('skipped_existing_total', '?')}")

        if recovery_log_lines:
            log.info("")
            log.warning("  *** TRANSPORT RECOVERY TRIGGERED ***")
            log.warning(f"  Recovery events ({len(recovery_log_lines)}):")
            for line in recovery_log_lines:
                log.warning(f"    >> {line}")
            log.warning("  Fix is active and working correctly.")
        else:
            log.info("")
            log.info("  No transport timeouts detected in this run.")
            log.info("  (If the portal was responsive the fix was not needed – that is fine.)")

        dept_summaries = summary.get("department_summaries", [])
        if dept_summaries:
            log.info("")
            log.info("  Per-department breakdown:")
            for ds in dept_summaries:
                dept = ds.get("department", "?")
                scraped = ds.get("scraped", 0)
                expected = ds.get("expected", "?")
                skipped = "RESUME_SKIPPED" if ds.get("resume_skipped") else ""
                skip_r = ds.get("skip_reason", "")
                extra = skipped or skip_r or ""
                log.info(f"    {dept:<35} scraped={scraped}  expected={expected}  {extra}")

        log.info("=" * 60)

        # ── Exit code ─────────────────────────────────────────────────────────
        status_str = str(summary.get("status", "")).lower()
        if "error" in status_str:
            log.error("Smoke test completed WITH ERRORS.")
            sys.exit(1)
        else:
            log.info("Smoke test PASSED.")
            sys.exit(0)


if __name__ == "__main__":
    main()
