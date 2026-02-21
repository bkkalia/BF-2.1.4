"""Check West Bengal scraping status"""
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from tender_store import TenderDataStore

db_path = Path("database/blackforest_tenders.sqlite3")
store = TenderDataStore(str(db_path))

# Check tenders in database
wb_ids = store.get_existing_tender_ids_for_portal('West Bengal')
print(f"\n{'='*80}")
print(f"WEST BENGAL DATABASE CHECK")
print(f"{'='*80}\n")
print(f"Tenders in database: {len(wb_ids):,}")

# Check run status
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.execute("""
    SELECT status, started_at, completed_at, extracted_total_tenders, skipped_existing_total
    FROM runs 
    WHERE portal_name = 'West Bengal' 
    AND started_at > '2026-02-19 20:30:00'
    ORDER BY started_at DESC 
    LIMIT 1
""")
result = cursor.fetchone()

if result:
    print(f"\nRun Status:")
    print(f"  Status: {result['status']}")
    print(f"  Started: {result['started_at']}")
    print(f"  Completed: {result['completed_at'] or 'Still running'}")
    print(f"  Extracted: {result['extracted_total_tenders'] or 0:,}")
    print(f"  Skipped: {result['skipped_existing_total'] or 0:,}")
else:
    print("\nNo recent West Bengal run found")

conn.close()
print(f"\n{'='*80}\n")
