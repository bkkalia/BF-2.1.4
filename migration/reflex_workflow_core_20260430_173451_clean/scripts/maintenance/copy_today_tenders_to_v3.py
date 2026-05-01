from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


IST = timezone(timedelta(hours=5, minutes=30))


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def target_db_path() -> Path:
    return workspace_root() / "database" / "blackforest_tenders.sqlite3"


def latest_backup_path() -> Path:
    backups = sorted((workspace_root() / "db_backups").glob("blackforest_tenders_pre_v3_fresh_*.sqlite3"))
    if not backups:
        raise FileNotFoundError("No pre-v3 backup found in db_backups/")
    return backups[-1]


def parse_ist_datetime(text: str) -> Optional[datetime]:
    value = str(text or "").strip()
    if not value:
        return None

    for fmt in (
        "%d-%b-%Y %I:%M %p",
        "%d/%b/%Y %I:%M %p",
        "%d-%m-%Y %I:%M %p",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            if fmt == "%Y-%m-%d":
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt.replace(tzinfo=IST)
        except ValueError:
            continue

    # Try forgiving ISO parse
    try:
        dt2 = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt2.tzinfo is None:
            return dt2.replace(tzinfo=IST)
        return dt2.astimezone(IST)
    except ValueError:
        return None


def to_iso_no_tz(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    return dt.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    src_db = latest_backup_path()
    dst_db = target_db_path()

    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    src = sqlite3.connect(str(src_db))
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(str(dst_db))
    dst.row_factory = sqlite3.Row

    try:
        s = src.cursor()
        d = dst.cursor()

        # Validate v3 target exists
        d.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('portals','tender_items')")
        tables = {row[0] for row in d.fetchall()}
        if "portals" not in tables or "tender_items" not in tables:
            raise RuntimeError("Target DB is not v3-ready (missing portals/tender_items)")

        # Build portal map (portal_name -> (id, slug))
        d.execute("SELECT id, portal_slug, portal_name FROM portals")
        portal_map: dict[str, tuple[int, str]] = {}
        for row in d.fetchall():
            portal_map[str(row["portal_name"]).strip()] = (int(row["id"]), str(row["portal_slug"]))

        # Existing dedupe keys in target
        d.execute("SELECT portal_slug, COALESCE(tender_id_extracted,''), COALESCE(title_ref,'') FROM tender_items")
        existing_keys = {
            (str(r[0]), str(r[1]).strip(), str(r[2]).strip())
            for r in d.fetchall()
        }

        s.execute(
            """
            SELECT
                portal_name,
                tender_id_extracted,
                title_ref,
                department_name,
                published_date,
                closing_date,
                opening_date,
                organisation_chain,
                direct_url,
                status_url,
                emd_amount_numeric,
                lifecycle_status
            FROM tenders
            """
        )

        inserted = 0
        skipped_bad_date = 0
        skipped_not_today = 0
        skipped_no_portal = 0
        skipped_duplicate = 0

        rows_to_insert: list[tuple] = []

        for row in s.fetchall():
            portal_name = str(row["portal_name"] or "").strip()
            if portal_name not in portal_map:
                skipped_no_portal += 1
                continue

            closing_dt = parse_ist_datetime(str(row["closing_date"] or ""))
            if not closing_dt:
                skipped_bad_date += 1
                continue

            # Copy only today's tenders by IST closing date
            if closing_dt.date() != today_ist:
                skipped_not_today += 1
                continue

            portal_id, portal_slug = portal_map[portal_name]
            tender_id = str(row["tender_id_extracted"] or "").strip()
            title_ref = str(row["title_ref"] or "").strip()
            key = (portal_slug, tender_id, title_ref)
            if key in existing_keys:
                skipped_duplicate += 1
                continue

            published_dt = parse_ist_datetime(str(row["published_date"] or ""))
            now_live = 1 if closing_dt >= now_ist else 0

            rows_to_insert.append(
                (
                    portal_id,
                    portal_slug,
                    tender_id or None,
                    title_ref or None,
                    (str(row["department_name"] or "").strip() or None),
                    to_iso_no_tz(published_dt),
                    to_iso_no_tz(closing_dt),
                    (str(row["opening_date"] or "").strip() or None),
                    (str(row["organisation_chain"] or "").strip() or None),
                    (str(row["direct_url"] or "").strip() or None),
                    (str(row["status_url"] or "").strip() or None),
                    (float(row["emd_amount_numeric"]) if row["emd_amount_numeric"] not in (None, "") else None),
                    (str(row["lifecycle_status"] or "").strip() or None),
                    now_live,
                    None,
                    None,
                    None,
                    None,
                    None,
                )
            )
            existing_keys.add(key)

        if rows_to_insert:
            d.executemany(
                """
                INSERT INTO tender_items (
                    portal_id, portal_slug, tender_id_extracted, title_ref, department_name,
                    published_at, closing_at, opening_date, organisation_chain,
                    tender_url, status_url, estimated_cost_value, tender_status, is_live,
                    state_name, district, city, tender_type, work_type
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                rows_to_insert,
            )
            inserted = len(rows_to_insert)

        # Update portal last_updated from inserted rows
        d.execute(
            """
            UPDATE portals
            SET last_updated = (
                SELECT MAX(ti.updated_at)
                FROM tender_items ti
                WHERE ti.portal_slug = portals.portal_slug
            )
            WHERE EXISTS (
                SELECT 1 FROM tender_items ti2 WHERE ti2.portal_slug = portals.portal_slug
            )
            """
        )

        dst.commit()

        d.execute("SELECT COUNT(*) FROM tender_items")
        total_target = int(d.fetchone()[0])
        d.execute("SELECT COUNT(*) FROM tender_items WHERE is_live = 1")
        live_target = int(d.fetchone()[0])

        print(f"Source backup: {src_db}")
        print(f"Target db: {dst_db}")
        print(f"IST today: {today_ist}")
        print(f"Inserted today rows: {inserted}")
        print(f"Skipped bad date: {skipped_bad_date}")
        print(f"Skipped not today: {skipped_not_today}")
        print(f"Skipped no portal mapping: {skipped_no_portal}")
        print(f"Skipped duplicate: {skipped_duplicate}")
        print(f"Target totals: total={total_target}, live={live_target}")
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    main()
