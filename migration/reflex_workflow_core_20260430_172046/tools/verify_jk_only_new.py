import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app_settings import load_base_urls
from scraper.logic import fetch_department_list_from_site_v2, run_scraping_logic, normalize_tender_id
from scraper.driver_manager import setup_driver, safe_quit_driver

BASE_URLS = os.path.join(ROOT, "base_urls.csv")
DB_PATH = os.path.join(ROOT, "data", "blackforest_tenders.sqlite3")
DOWNLOAD_DIR = os.path.join(ROOT, "Tender_Downloads")
PORTAL_NAME = "Jammu Kashmir"
LIMIT_DEPTS = 5


def log(msg):
    print(msg)


def get_portal_config(name):
    rows = load_base_urls(BASE_URLS)
    for row in rows:
        if str(row.get("Name", "")).strip() == name:
            return row
    raise RuntimeError(f"Portal not found: {name}")


def get_known_ids_from_sqlite(portal_names):
    if not os.path.exists(DB_PATH):
        return set()
    conn = sqlite3.connect(DB_PATH)
    try:
        placeholders = ",".join(["?"] * len(portal_names))
        query = (
            "SELECT DISTINCT trim(tender_id_extracted) FROM tenders "
            "WHERE trim(coalesce(tender_id_extracted, '')) <> '' "
            f"AND lower(trim(coalesce(portal_name, ''))) IN ({placeholders})"
        )
        rows = conn.execute(query, [p.lower() for p in portal_names]).fetchall()
        return {str(r[0]).strip() for r in rows if r and str(r[0]).strip()}
    finally:
        conn.close()


def main():
    portal = get_portal_config(PORTAL_NAME)
    departments, _ = fetch_department_list_from_site_v2(portal.get("OrgListURL"), log)

    valid = []
    for d in departments:
        s_no = str(d.get("s_no", "")).strip().lower()
        dname = str(d.get("name", "")).strip().lower()
        if s_no.isdigit() and dname not in ["organisation name", "department name", "organization", "organization name"]:
            valid.append(d)

    to_run = valid[:LIMIT_DEPTS]
    portal_candidates = {
        PORTAL_NAME,
        str(portal.get("Keyword") or "").strip(),
        "jktenders_gov_in",
        "jammu and kashmir",
    }
    known_ids = get_known_ids_from_sqlite([x for x in portal_candidates if x])
    known_ids_norm = {normalize_tender_id(x) for x in known_ids if normalize_tender_id(x)}

    print(f"[VERIFY] Departments selected: {len(to_run)} / {len(valid)}")
    print(f"[VERIFY] Known IDs from SQLite: {len(known_ids)} (normalized: {len(known_ids_norm)})")

    driver = None
    try:
        driver = setup_driver(initial_download_dir=DOWNLOAD_DIR)
        summary = run_scraping_logic(
            departments_to_scrape=to_run,
            base_url_config=portal,
            download_dir=DOWNLOAD_DIR,
            log_callback=log,
            progress_callback=lambda *_: None,
            timer_callback=lambda *_: None,
            status_callback=lambda *_: None,
            stop_event=None,
            driver=driver,
            deep_scrape=False,
            existing_tender_ids=known_ids,
            existing_department_names=set(),
            sqlite_db_path=DB_PATH,
            sqlite_backup_dir=os.path.join(ROOT, "db_backups"),
            sqlite_backup_retention_days=30,
            department_parallel_workers=1,
        )
        print("\n[VERIFY] Summary")
        print(f"  status={summary.get('status')}")
        print(f"  processed_departments={summary.get('processed_departments')}")
        print(f"  extracted_total_tenders={summary.get('extracted_total_tenders')}")
        print(f"  skipped_existing_total={summary.get('skipped_existing_total')}")
        print(f"  expected_total_tenders={summary.get('expected_total_tenders')}")
    finally:
        if driver is not None:
            safe_quit_driver(driver, log)


if __name__ == "__main__":
    main()
