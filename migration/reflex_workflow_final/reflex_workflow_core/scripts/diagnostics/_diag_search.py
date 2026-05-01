import sqlite3, time

db = r'd:\Dev84\BF 2.1.4\database\blackforest_tenders.sqlite3'
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
c = conn.cursor()

tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)

c.execute("SELECT COUNT(*) FROM tenders WHERE portal_name='HP Tenders'")
hp_count = c.fetchone()[0]
print(f"HP Tenders rows: {hp_count:,}")

c.execute("SELECT COUNT(*) FROM tenders")
total = c.fetchone()[0]
print(f"Total rows: {total:,}")

# FTS5 support
try:
    c.execute("CREATE VIRTUAL TABLE _fts_test USING fts5(x)")
    c.execute("DROP TABLE _fts_test")
    print("FTS5: SUPPORTED")
except Exception as e:
    print(f"FTS5: NOT available - {e}")

# Current indexes
rows = c.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tenders'").fetchall()
print("Existing indexes:")
for r in rows:
    print(f"  {r[0]}")

# FTS table present?
fts_exists = c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='tenders_fts'").fetchone()[0]
print(f"tenders_fts table exists: {fts_exists > 0}")

# Time a live search
t0 = time.perf_counter()
c.execute("SELECT COUNT(*) FROM tenders WHERE portal_name='HP Tenders' AND (title_ref LIKE '%road%' OR department_name LIKE '%road%')")
ms = (time.perf_counter() - t0) * 1000
r2 = c.fetchone()
print(f"\nLIKE search (HP Tenders, 'road'): {ms:.1f}ms")

conn.close()
