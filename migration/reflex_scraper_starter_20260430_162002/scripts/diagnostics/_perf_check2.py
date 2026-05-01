import sqlite3, time

db = r"d:\Dev84\BF 2.1.4\database\blackforest_tenders.sqlite3"
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
c = con.cursor()

c.execute("SELECT sqlite_version() v")
print("SQLite:", c.fetchone()[0])

c.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='tenders'")
for r in c.fetchall():
    print(" IDX:", r["name"], "|", (r["sql"] or "")[:120])

c.execute("SELECT closing_date FROM tenders WHERE closing_date IS NOT NULL AND closing_date != '' LIMIT 5")
print("Sample dates:", [r[0] for r in c.fetchall()])

print("Counting expiry buckets (full CASE scan)...")
t0 = time.perf_counter()
c.execute("""
SELECT
  SUM(CASE WHEN cd_iso IS NULL THEN 1 ELSE 0 END) as no_date,
  SUM(CASE WHEN cd_iso >= DATE('now','+330 minutes') THEN 1 ELSE 0 END) as live,
  SUM(CASE WHEN cd_iso < DATE('now','+330 minutes')
           AND cd_iso >= DATE('now','-60 days','+330 minutes') THEN 1 ELSE 0 END) as exp_60d,
  SUM(CASE WHEN cd_iso < DATE('now','-60 days','+330 minutes') THEN 1 ELSE 0 END) as exp_older
FROM (
  SELECT CASE WHEN LENGTH(TRIM(COALESCE(closing_date,'')))>=11
    THEN SUBSTR(closing_date,8,4)||'-'||
      CASE UPPER(SUBSTR(closing_date,4,3))
        WHEN 'JAN' THEN '01' WHEN 'FEB' THEN '02' WHEN 'MAR' THEN '03'
        WHEN 'APR' THEN '04' WHEN 'MAY' THEN '05' WHEN 'JUN' THEN '06'
        WHEN 'JUL' THEN '07' WHEN 'AUG' THEN '08' WHEN 'SEP' THEN '09'
        WHEN 'OCT' THEN '10' WHEN 'NOV' THEN '11' WHEN 'DEC' THEN '12'
        ELSE '00' END||'-'||SUBSTR(closing_date,1,2)
    ELSE NULL END AS cd_iso
  FROM tenders
)
""")
r = c.fetchone()
ms = int((time.perf_counter() - t0) * 1000)
print(f"  no_date={r[0]}, live={r[1]}, recent_expired(0-60d)={r[2]}, old_expired(>60d)={r[3]}  ({ms}ms)")

c.execute("PRAGMA table_info(tenders)")
cols = [row["name"] for row in c.fetchall()]
print("Has closing_date_iso:", "closing_date_iso" in cols)
print("Columns:", cols)
con.close()
