import sqlite3
conn = sqlite3.connect("D:/Dev84/BF 2.1.4/data/blackforest_tenders.sqlite3")
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Latest runs for HP and Punjab
c.execute("""
    SELECT portal_name, id, started_at, completed_at, status,
           extracted_total_tenders, skipped_existing_total, expected_total_tenders
    FROM runs
    WHERE LOWER(portal_name) IN ('hp tenders', 'punjab')
    ORDER BY id DESC
    LIMIT 6
""")
rows = c.fetchall()
print(f"{'Portal':<15} {'Run ID':<8} {'Started':<22} {'Status':<12} {'Scraped':<10} {'Skipped':<10} {'Expected':<10}")
print("-" * 90)
for r in rows:
    print(f"{r['portal_name']:<15} {r['id']:<8} {r['started_at']:<22} {r['status']:<12} {str(r['extracted_total_tenders']):<10} {str(r['skipped_existing_total']):<10} {str(r['expected_total_tenders']):<10}")
conn.close()
