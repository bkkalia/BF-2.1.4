import sqlite3
DB = r'd:\Dev84\BF 2.1.4\database\blackforest_tenders.sqlite3'
with sqlite3.connect(DB) as conn:
    conn.row_factory = sqlite3.Row

    hp_scraped = conn.execute("SELECT COUNT(*) FROM tenders WHERE LOWER(TRIM(portal_name))='hp tenders'").fetchone()[0]
    hp_exc = conn.execute("SELECT COUNT(*) FROM tenders WHERE LOWER(TRIM(portal_name))='hptenders.gov.in'").fetchone()[0]
    print(f"HP Tenders (scraped, all runs): {hp_scraped}")
    print(f"hptenders.gov.in (Excel import): {hp_exc}")

    # Create temp index for speed
    conn.execute("CREATE INDEX IF NOT EXISTS _tmp_idx ON tenders(LOWER(TRIM(tender_id_extracted)), LOWER(TRIM(portal_name)))")

    overlap = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT LOWER(TRIM(tender_id_extracted)) AS tid
            FROM tenders WHERE LOWER(TRIM(portal_name))='hptenders.gov.in'
            INTERSECT
            SELECT LOWER(TRIM(tender_id_extracted)) AS tid
            FROM tenders WHERE LOWER(TRIM(portal_name))='hp tenders'
        )
    """).fetchone()[0]
    print(f"\nOverlap (same ID in both portals): {overlap}")
    print(f"Only in Excel (scraper never got these): {hp_exc - overlap}")
    print(f"Only in scraped (not in Excel): {hp_scraped - overlap}")

    # HP Tenders runs breakdown
    print("\n--- HP Tenders scrape runs ---")
    for r in conn.execute("""
        SELECT r.id, r.status, COUNT(t.id) cnt, r.started_at,
               r.expected_total_tenders, r.skipped_existing_total
        FROM runs r LEFT JOIN tenders t ON t.run_id=r.id
        WHERE LOWER(TRIM(r.portal_name))='hp tenders'
        GROUP BY r.id ORDER BY r.started_at
    """).fetchall():
        print(f"  run {r['id']}: {r['cnt']} tenders, skipped={r['skipped_existing_total']}, "
              f"expected={r['expected_total_tenders']}, status={r['status']}, at={r['started_at']}")

    # IDs only in Excel (scraper missed) — sample
    print("\n--- Sample IDs in Excel but NOT scraped (scraper missed) ---")
    for r in conn.execute("""
        SELECT a.tender_id_extracted, a.department_name, a.published_date, a.closing_date
        FROM tenders a
        WHERE LOWER(TRIM(a.portal_name))='hptenders.gov.in'
          AND NOT EXISTS (
              SELECT 1 FROM tenders b
              WHERE LOWER(TRIM(b.portal_name))='hp tenders'
                AND LOWER(TRIM(b.tender_id_extracted))=LOWER(TRIM(a.tender_id_extracted)))
        ORDER BY a.published_date DESC
        LIMIT 15
    """).fetchall():
        print(f"  {r['tender_id_extracted']!r}  {r['department_name']!r}  pub={r['published_date']!r}  close={r['closing_date']!r}")
