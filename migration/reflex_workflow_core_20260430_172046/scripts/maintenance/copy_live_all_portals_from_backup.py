from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

IST = timezone(timedelta(hours=5, minutes=30))


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

        d.execute("SELECT id, portal_slug, portal_name FROM portals")
        portal_map = {
            str(r["portal_name"]).strip(): (int(r["id"]), str(r["portal_slug"]))
            for r in d.fetchall()
        }
        if not portal_map:
            raise RuntimeError("No portals found in v3 table")

        d.execute("SELECT portal_slug, COALESCE(tender_id_extracted,''), COALESCE(title_ref,'') FROM tender_items")
        existing_keys = {(str(r[0]), str(r[1]).strip(), str(r[2]).strip()) for r in d.fetchall()}

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

        src_total = 0
        src_live = 0
        skipped_bad_date = 0
        skipped_not_live = 0
        skipped_no_portal = 0
        skipped_duplicate = 0

        rows_to_insert: list[tuple] = []

        for row in s.fetchall():
            src_total += 1
            portal_name = str(row["portal_name"] or "").strip()
            if portal_name not in portal_map:
                skipped_no_portal += 1
                continue

            closing_dt = parse_ist_datetime(row["closing_date"])
            if not closing_dt:
                skipped_bad_date += 1
                continue

            if closing_dt < now_ist:
                skipped_not_live += 1
                continue

            src_live += 1
            portal_id, portal_slug = portal_map[portal_name]

            tender_id = str(row["tender_id_extracted"] or "").strip()
            title_ref = str(row["title_ref"] or "").strip()
            key = (portal_slug, tender_id, title_ref)
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

        inserted = 0
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
        target_total = int(d.fetchone()[0])
        d.execute("SELECT COUNT(*) FROM tender_items WHERE is_live = 1")
        target_live = int(d.fetchone()[0])
        d.execute("SELECT COUNT(DISTINCT portal_slug) FROM tender_items")
        target_portals = int(d.fetchone()[0])

        print(f"Source backup: {src_path}")
        print(f"Target db: {dst_path}")
        print(f"Now IST: {now_ist.strftime('%Y-%m-%d %H:%M:%S %z')}")
        print(f"Source total rows: {src_total}")
        print(f"Source live rows (minute IST): {src_live}")
        print(f"Inserted new live rows: {inserted}")
        print(f"Skipped bad date: {skipped_bad_date}")
        print(f"Skipped not live: {skipped_not_live}")
        print(f"Skipped no portal mapping: {skipped_no_portal}")
        print(f"Skipped duplicate: {skipped_duplicate}")
        print(f"Target totals: total={target_total}, live={target_live}, portals={target_portals}")
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    main()
