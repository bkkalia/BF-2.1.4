import sqlite3
conn = sqlite3.connect('database/blackforest_tenders.sqlite3')
cur = conn.cursor()
rows = cur.execute("""
SELECT id, tender_id_extracted, title_ref, closing_date
FROM tenders
WHERE lower(trim(coalesce(portal_name,'')))='hp tenders'
ORDER BY id DESC
LIMIT 30
""").fetchall()
for r in rows:
    print(r)
conn.close()
