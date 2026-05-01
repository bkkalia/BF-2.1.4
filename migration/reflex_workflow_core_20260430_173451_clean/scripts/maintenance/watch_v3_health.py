import argparse
import sqlite3
import time
from datetime import datetime
from pathlib import Path


DB_DEFAULT = Path(r"d:/Dev84/BF 2.1.4/database/blackforest_tenders.sqlite3")


def snapshot(db_path: Path, portal: str | None = None) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        legacy_tables = cur.execute(
            "SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name IN ('runs','tenders')"
        ).fetchone()["c"]

        total_tenders = cur.execute("SELECT COUNT(*) AS c FROM tender_items").fetchone()["c"]

        if portal:
            portal_tenders = cur.execute(
                "SELECT COUNT(*) AS c FROM tender_items WHERE LOWER(TRIM(COALESCE(portal_slug,''))) = LOWER(TRIM(?))",
                (portal,),
            ).fetchone()["c"]
            latest_run = cur.execute(
                """
                SELECT id, portal_name, status, started_at, completed_at, extracted_total_tenders, skipped_existing_total
                FROM scrape_runs
                WHERE LOWER(TRIM(COALESCE(portal_name,''))) = LOWER(TRIM(?))
                ORDER BY id DESC
                LIMIT 1
                """,
                (portal,),
            ).fetchone()
        else:
            portal_tenders = None
            latest_run = cur.execute(
                """
                SELECT id, portal_name, status, started_at, completed_at, extracted_total_tenders, skipped_existing_total
                FROM scrape_runs
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

        return {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "legacy_tables": int(legacy_tables or 0),
            "total_tenders": int(total_tenders or 0),
            "portal": portal or "ALL",
            "portal_tenders": int(portal_tenders) if portal_tenders is not None else None,
            "latest_run": dict(latest_run) if latest_run else None,
        }
    finally:
        conn.close()


def print_snapshot(data: dict) -> None:
    latest = data.get("latest_run") or {}
    latest_id = latest.get("id", "-")
    latest_portal = latest.get("portal_name", "-")
    latest_status = latest.get("status", "-")
    extracted = latest.get("extracted_total_tenders", 0)
    skipped = latest.get("skipped_existing_total", 0)

    portal_part = (
        f"portal_tenders={data['portal_tenders']}"
        if data.get("portal_tenders") is not None
        else "portal_tenders=-"
    )

    print(
        f"[{data['ts']}] legacy_tables={data['legacy_tables']} total_tenders={data['total_tenders']} "
        f"portal={data['portal']} {portal_part} latest_run={latest_id} latest_portal={latest_portal} "
        f"status={latest_status} extracted={extracted} skipped={skipped}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch v3 scrape/database health")
    parser.add_argument("--db", default=str(DB_DEFAULT), help="Path to SQLite DB")
    parser.add_argument("--portal", default="", help="Optional portal slug/name filter")
    parser.add_argument("--interval", type=int, default=60, help="Refresh interval seconds")
    parser.add_argument("--once", action="store_true", help="Print one snapshot and exit")
    args = parser.parse_args()

    db_path = Path(args.db)
    portal = args.portal.strip() or None

    if args.once:
        print_snapshot(snapshot(db_path, portal))
        return

    while True:
        try:
            print_snapshot(snapshot(db_path, portal))
        except Exception as exc:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] monitor_error={exc}")
        time.sleep(max(5, int(args.interval or 60)))


if __name__ == "__main__":
    main()
