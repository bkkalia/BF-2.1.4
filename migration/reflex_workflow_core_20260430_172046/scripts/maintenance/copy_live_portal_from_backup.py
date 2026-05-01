from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

IST = timezone(timedelta(hours=5, minutes=30))
PORTAL_NAME = "HP Tenders"


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def latest_backup_path() -> Path:
    backups = sorted((workspace_root() / "db_backups").glob("blackforest_tenders_pre_v3_fresh_*.sqlite3"))
    if not backups:
        raise FileNotFoundError("No pre-v3 backup found in db_backups/")
    return backups[-1]


def target_db_path() -> Path:
    return workspace_root() / "database" / "blackforest_tenders.sqlite3"


def parse_ist_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
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
            dt = datetime.strptime(text, fmt)
            if fmt == "%Y-%m-%d":
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt.replace(tzinfo=IST)
        except ValueError:
            continue

    try:
        dt2 = datetime.fromisoformat(text.replace("Z", "+00:00"))
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
    src_path = latest_backup_path()
    dst_path = target_db_path()
    now_ist = datetime.now(IST)

    src = sqlite3.connect(str(src_path))
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(str(dst_path))
    dst.row_factory = sqlite3.Row

    try:
        s = src.cursor()
        d = dst.cursor()

        d.execute("SELECT id, portal_slug, portal_name FROM portals WHERE portal_name = ?", [PORTAL_NAME])
        portal_row = d.fetchone()
        if not portal_row:
            raise RuntimeError(f"Portal not found in v3 portals: {PORTAL_NAME}")
        portal_id = int(portal_row["id"])
        portal_slug = str(portal_row["portal_slug"])

        # Existing keys to avoid duplicates.
        d.execute(
            """
            SELECT COALESCE(tender_id_extracted,''), COALESCE(title_ref,'')
            FROM tender_items
            WHERE portal_slug = ?
            """,
            [portal_slug],
        )
        existing_keys = {(str(r[0]).strip(), str(r[1]).strip()) for r in d.fetchall()}

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
            WHERE portal_name = ?
            """,
            [PORTAL_NAME],
        )

        source_total = 0
        source_live = 0
        inserted = 0
        skipped_bad_date = 0
        skipped_not_live = 0
        skipped_duplicate = 0

        rows_to_insert: list[tuple] = []

        for row in s.fetchall():
            source_total += 1
            closing_dt = parse_ist_datetime(row["closing_date"])
            if not closing_dt:
                skipped_bad_date += 1
                continue

            is_live = closing_dt >= now_ist
            if is_live:
                source_live += 1
            else:
                skipped_not_live += 1
                continue

            tender_id = str(row["tender_id_extracted"] or "").strip()
            title_ref = str(row["title_ref"] or "").strip()
            key = (tender_id, title_ref)
            if key in existing_keys:
                skipped_duplicate += 1
                continue

            published_dt = parse_ist_datetime(row["published_date"])

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
                    1,
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

        dst.commit()

        d.execute(
            """
            UPDATE portals
            SET last_updated = (
                SELECT MAX(ti.updated_at)
                FROM tender_items ti
                WHERE ti.portal_slug = portals.portal_slug
            )
            WHERE portal_slug = ?
            """,
            [portal_slug],
        )
        dst.commit()

        d.execute("SELECT COUNT(*) FROM tender_items WHERE portal_slug = ?", [portal_slug])
        target_total = int(d.fetchone()[0])
        d.execute("SELECT COUNT(*) FROM tender_items WHERE portal_slug = ? AND is_live = 1", [portal_slug])
        target_live = int(d.fetchone()[0])

        print(f"Source backup: {src_path}")
        print(f"Target db: {dst_path}")
        print(f"Now IST: {now_ist.strftime('%Y-%m-%d %H:%M:%S %z')}")
        print(f"Portal: {PORTAL_NAME} ({portal_slug})")
        print(f"Source total: {source_total}")
        print(f"Source live (minute IST): {source_live}")
        print(f"Inserted new live rows: {inserted}")
        print(f"Skipped bad date: {skipped_bad_date}")
        print(f"Skipped not live: {skipped_not_live}")
        print(f"Skipped duplicate: {skipped_duplicate}")
        print(f"Target portal total: {target_total}")
        print(f"Target portal live: {target_live}")
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    main()
