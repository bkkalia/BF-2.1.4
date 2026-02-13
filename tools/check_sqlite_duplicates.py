import json
import sqlite3

DB_PATH = r"D:/Dev84/BF 2.1.4/data/blackforest_tenders.sqlite3"


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    total = cur.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
    distinct_pairs = cur.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                LOWER(TRIM(COALESCE(portal_name, ''))) AS portal_key,
                TRIM(COALESCE(tender_id_extracted, '')) AS tender_key
            FROM tenders
            WHERE TRIM(COALESCE(tender_id_extracted, '')) <> ''
            GROUP BY portal_key, tender_key
        )
        """
    ).fetchone()[0]

    duplicate_groups = cur.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                LOWER(TRIM(COALESCE(portal_name, ''))) AS portal_key,
                TRIM(COALESCE(tender_id_extracted, '')) AS tender_key,
                COUNT(*) AS c
            FROM tenders
            WHERE TRIM(COALESCE(tender_id_extracted, '')) <> ''
            GROUP BY portal_key, tender_key
            HAVING c > 1
        )
        """
    ).fetchone()[0]

    duplicate_extra_rows = cur.execute(
        """
        SELECT COALESCE(SUM(c - 1), 0)
        FROM (
            SELECT COUNT(*) AS c
            FROM tenders
            WHERE TRIM(COALESCE(tender_id_extracted, '')) <> ''
            GROUP BY LOWER(TRIM(COALESCE(portal_name, ''))), TRIM(COALESCE(tender_id_extracted, ''))
            HAVING c > 1
        )
        """
    ).fetchone()[0]

    blank_tender_ids = cur.execute(
        "SELECT COUNT(*) FROM tenders WHERE TRIM(COALESCE(tender_id_extracted, '')) = ''"
    ).fetchone()[0]

    sample_duplicates = cur.execute(
        """
        SELECT
            portal_name,
            tender_id_extracted,
            COUNT(*) AS c
        FROM tenders
        WHERE TRIM(COALESCE(tender_id_extracted, '')) <> ''
        GROUP BY LOWER(TRIM(COALESCE(portal_name, ''))), TRIM(COALESCE(tender_id_extracted, ''))
        HAVING c > 1
        ORDER BY c DESC, portal_name ASC, tender_id_extracted ASC
        LIMIT 20
        """
    ).fetchall()

    schema_info = cur.execute(
        """
        SELECT name, sql
        FROM sqlite_master
        WHERE type IN ('index', 'table')
          AND tbl_name = 'tenders'
        ORDER BY type, name
        """
    ).fetchall()

    conn.close()

    result = {
        "db": DB_PATH,
        "total_tenders": total,
        "distinct_portal_tender_pairs": distinct_pairs,
        "duplicate_groups": duplicate_groups,
        "duplicate_extra_rows": duplicate_extra_rows,
        "blank_tender_ids": blank_tender_ids,
        "sample_duplicates": sample_duplicates,
        "schema_items": schema_info,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
