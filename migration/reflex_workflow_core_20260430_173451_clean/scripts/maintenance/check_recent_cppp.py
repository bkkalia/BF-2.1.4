import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from tender_store import TenderDataStore

db_path = Path("database/blackforest_tenders.sqlite3")
store = TenderDataStore(str(db_path))

# Get database connection for raw queries
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

# Check recent CPPP runs
c = conn.cursor()
c.execute("""
    SELECT 
        portal_name,
        started_at,
        completed_at,
        status,
        extracted_total_tenders,
        skipped_existing_total
    FROM runs
    WHERE portal_name LIKE 'CPPP%'
    AND started_at > '2026-02-19 19:00:00'
    ORDER BY started_at DESC
""")
results = c.fetchall()

print("\n" + "=" * 80)
print("🔍 CPPP SCRAPING ACTIVITY AFTER 19:00 (7:00 PM)")
print("=" * 80 + "\n")

if results:
    for run in results:
        portal = run['portal_name']
        started = run['started_at']
        completed = run['completed_at'] or 'In Progress'
        status = run['status'] or 'Running'
        extracted = run['extracted_total_tenders'] or 0
        skipped = run['skipped_existing_total'] or 0
        
        print(f"🔄 {portal}:")
        print(f"  ├─ Started: {started}")
        print(f"  ├─ Completed: {completed}")
        print(f"  ├─ Status: {status}")
        print(f"  ├─ Extracted: {extracted:,} tenders")
        print(f"  └─ Skipped: {skipped:,} (duplicates)")
        print()
else:
    print("⚠️  No CPPP scraping runs found after 19:00")
    print()

# Check all CPPP portals for context
print("\n" + "=" * 80)
print("📊 ALL CPPP TENDERS IN DATABASE")
print("=" * 80 + "\n")

for portal_name in ["CPPP1 eProcure", "CPPP2 eTenders"]:
    existing_ids = store.get_existing_tender_ids_for_portal(portal_name)
    print(f"{portal_name}: {len(existing_ids):,} tenders")

conn.close()

