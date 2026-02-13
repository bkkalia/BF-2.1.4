import argparse
import os
import shutil
import sqlite3
from datetime import datetime


def normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def is_missing_tender_id(value):
    tender_id = normalize_text(value)
    if not tender_id:
        return True
    return tender_id.lower() in {"nan", "none", "null", "na", "n/a", "-"}


def backup_db(db_path, backup_dir):
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.splitext(os.path.basename(db_path))[0]
    target = os.path.join(backup_dir, f"{base}_pre_cleanup_{stamp}.sqlite3")
    shutil.copy2(db_path, target)
    return target


def main():
    parser = argparse.ArgumentParser(description="Keep latest record per portal+tender_id and remove missing IDs")
    parser.add_argument("--db", required=True, help="SQLite db path")
    parser.add_argument("--backup-dir", required=True, help="Backup directory")
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    backup_path = backup_db(db_path, os.path.abspath(args.backup_dir))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT id, run_id, portal_name, tender_id_extracted
        FROM tenders
        ORDER BY id ASC
        """
    ).fetchall()

    total_before = len(rows)
    missing_ids = []
    keep_by_key = {}

    for row in rows:
        tender_id = normalize_text(row["tender_id_extracted"])
        portal_name = normalize_text(row["portal_name"])

        if is_missing_tender_id(tender_id):
            missing_ids.append(int(row["id"]))
            continue

        key = (portal_name.lower(), tender_id)
        existing = keep_by_key.get(key)
        current_sort = (int(row["run_id"] or 0), int(row["id"]))
        if existing is None or current_sort > existing[0]:
            keep_by_key[key] = (current_sort, int(row["id"]))

    keep_ids = {v[1] for v in keep_by_key.values()}
    duplicate_ids = [int(r["id"]) for r in rows if int(r["id"]) not in keep_ids and int(r["id"]) not in set(missing_ids)]

    delete_ids = missing_ids + duplicate_ids

    if delete_ids:
        cur.executemany("DELETE FROM tenders WHERE id = ?", [(x,) for x in delete_ids])

    conn.commit()

    total_after = cur.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
    remaining_dup_groups = cur.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT LOWER(TRIM(COALESCE(portal_name, ''))) AS p,
                   TRIM(COALESCE(tender_id_extracted, '')) AS t,
                   COUNT(*) AS c
            FROM tenders
            WHERE TRIM(COALESCE(tender_id_extracted, '')) <> ''
              AND LOWER(TRIM(COALESCE(tender_id_extracted, ''))) NOT IN ('nan','none','null','na','n/a','-')
            GROUP BY p, t
            HAVING c > 1
        )
        """
    ).fetchone()[0]

    conn.close()

    print("Cleanup complete")
    print(f"DB: {db_path}")
    print(f"Backup: {backup_path}")
    print(f"Rows before: {total_before}")
    print(f"Removed missing tender IDs: {len(missing_ids)}")
    print(f"Removed older duplicates: {len(duplicate_ids)}")
    print(f"Rows after: {total_after}")
    print(f"Remaining duplicate groups: {remaining_dup_groups}")


if __name__ == "__main__":
    main()
