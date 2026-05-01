import sys, time
sys.path.insert(0, 'd:/Dev84/BF 2.1.4/tender_dashboard_reflex')
import tender_dashboard_reflex.db as db

f = db.TenderFilters(portal='HP Tenders', show_live_only=True, search_query='road')

# Warm up (first call also runs _ensure_search_indexes migration)
print("Running migration on first call...")
s = db.get_summary(f)
db.search_tenders(f, prefetched_count=int(s['filtered_results']))

# Benchmark
runs = 8
t0 = time.perf_counter()
for _ in range(runs):
    s = db.get_summary(f)
    db.search_tenders(f, prefetched_count=int(s['filtered_results']))
elapsed = (time.perf_counter() - t0) * 1000 / runs

print(f"Avg full refresh: {elapsed:.1f}ms  (8 runs)")
print(f"  filtered={s['filtered_results']}  live={s['live_tenders']}  due_today={s['due_today']}")
print(f"  has_iso_column: {db._has_closing_iso_column}")

# Check indexes created
import sqlite3
conn = sqlite3.connect(r'd:\Dev84\BF 2.1.4\database\blackforest_tenders.sqlite3')
rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tenders'").fetchall()
print("Indexes now:")
for r in rows:
    print(f"  {r[0]}")
conn.close()
