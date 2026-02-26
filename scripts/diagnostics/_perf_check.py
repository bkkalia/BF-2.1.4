import sqlite3, time

db = r"d:\Dev84\BF 2.1.4\database\blackforest_tenders.sqlite3"
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
c = con.cursor()

print("=== Indexes ===")
c.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index' ORDER BY tbl_name")
for r in c.fetchall():
    print(f"  {r['tbl_name']} | {r['name']}")

print("\n=== Tables ===")
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print([r[0] for r in c.fetchall()])

print("\n=== Timing ===")

t0 = time.perf_counter()
c.execute("SELECT COUNT(*) n FROM tenders WHERE portal_name='HP Tenders'")
print(f"portal_name lookup:   {int((time.perf_counter()-t0)*1000)} ms  n={c.fetchone()[0]}")

t0 = time.perf_counter()
c.execute(
    "SELECT COUNT(*) n FROM tenders WHERE portal_name=? AND "
    "(title_ref LIKE ? OR department_name LIKE ? OR tender_id_extracted LIKE ?)",
    ("HP Tenders", "%doa%", "%doa%", "%doa%"),
)
print(f"portal+3xLIKE:        {int((time.perf_counter()-t0)*1000)} ms  n={c.fetchone()[0]}")

# Cost of the CASE date expr on all rows
t0 = time.perf_counter()
c.execute("""
SELECT COUNT(*) n FROM tenders
WHERE
  CASE WHEN LENGTH(TRIM(COALESCE(closing_date,'')))>=11
  THEN SUBSTR(closing_date,8,4)||'-'||
    CASE UPPER(SUBSTR(closing_date,4,3))
      WHEN 'JAN' THEN '01' WHEN 'FEB' THEN '02' WHEN 'MAR' THEN '03'
      WHEN 'APR' THEN '04' WHEN 'MAY' THEN '05' WHEN 'JUN' THEN '06'
      WHEN 'JUL' THEN '07' WHEN 'AUG' THEN '08' WHEN 'SEP' THEN '09'
      WHEN 'OCT' THEN '10' WHEN 'NOV' THEN '11' WHEN 'DEC' THEN '12'
      ELSE '00' END||'-'||SUBSTR(closing_date,1,2)
  ELSE NULL END >= DATE('now','+330 minutes')
""")
print(f"CASE date (live):     {int((time.perf_counter()-t0)*1000)} ms  n={c.fetchone()[0]}")

# Full live + portal + search combo (simulate actual query)
t0 = time.perf_counter()
c.execute("""
SELECT COUNT(*) n FROM tenders AS ti
WHERE portal_name='HP Tenders'
  AND (title_ref LIKE '%doa%' OR department_name LIKE '%doa%')
  AND (
    CASE WHEN LENGTH(TRIM(COALESCE(closing_date,'')))>=11
    THEN SUBSTR(closing_date,8,4)||'-'||
      CASE UPPER(SUBSTR(closing_date,4,3))
        WHEN 'JAN' THEN '01' WHEN 'FEB' THEN '02' WHEN 'MAR' THEN '03'
        WHEN 'APR' THEN '04' WHEN 'MAY' THEN '05' WHEN 'JUN' THEN '06'
        WHEN 'JUL' THEN '07' WHEN 'AUG' THEN '08' WHEN 'SEP' THEN '09'
        WHEN 'OCT' THEN '10' WHEN 'NOV' THEN '11' WHEN 'DEC' THEN '12'
        ELSE '00' END||'-'||SUBSTR(closing_date,1,2)
    ELSE NULL END >= DATE('now','+330 minutes')
  )
""")
print(f"portal+LIKE+date:     {int((time.perf_counter()-t0)*1000)} ms  n={c.fetchone()[0]}")

# Check if FTS exists
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%fts%'")
fts_tables = [r[0] for r in c.fetchall()]
print(f"\nFTS tables: {fts_tables}")

# Total row count
c.execute("SELECT COUNT(*) n FROM tenders")
print(f"Total rows: {c.fetchone()[0]}")

con.close()
