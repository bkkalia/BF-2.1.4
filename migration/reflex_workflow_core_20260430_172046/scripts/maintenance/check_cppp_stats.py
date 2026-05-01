import sqlite3
from pathlib import Path

db_path = Path("database/blackforest_tenders.sqlite3")
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

portals = ['CPPP1 eProcure', 'CPPP2 eTenders']

print("\n" + "=" * 70)
print("CPPP PORTALS - EXISTING TENDERS BASELINE")
print("=" * 70)

for portal in portals:
    cursor = conn.execute("SELECT COUNT(*) as count FROM tenders WHERE portal_name = ?", (portal,))
    count = cursor.fetchone()['count']
    
    print(f"\n{portal}:")
    print(f"  Existing Tenders: {count:,}")
    
    if count > 0:
        # Get department count
        cursor = conn.execute("""
            SELECT COUNT(DISTINCT department_name) as dept_count 
            FROM tenders 
            WHERE portal_name = ?
        """, (portal,))
        dept_count = cursor.fetchone()['dept_count']
        print(f"  Departments: {dept_count}")
        
        # Get latest run
        cursor = conn.execute("""
            SELECT 
                started_at,
                extracted_total_tenders,
                skipped_existing_total
            FROM runs
            WHERE portal_name = ?
            ORDER BY started_at DESC
            LIMIT 1
        """, (portal,))
        
        last_run = cursor.fetchone()
        if last_run:
            print(f"  Last Scraped: {last_run['started_at']}")
            print(f"  Last Run: {last_run['extracted_total_tenders']} new, {last_run['skipped_existing_total']} skipped")
    else:
        print(f"  Status: NEVER SCRAPED BEFORE")
        print(f"  Expected: First scrape will be SLOW (0% duplicates)")

print("\n" + "=" * 70)
print("MONITORING READY - Watch for:")
print("=" * 70)
print("  - Bulk filter logs showing duplicate %")
print("  - Multi-worker parallelism (W1, W2, W3)")
print("  - Speed metrics (tenders/min, depts/min)")
print("  - Final performance summary")
print("=" * 70 + "\n")

conn.close()
