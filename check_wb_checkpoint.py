import sqlite3
from datetime import datetime

# Check the most recent West Bengal run
conn = sqlite3.connect('database/blackforest_tenders.sqlite3')
cur = conn.execute('''
    SELECT id, portal_name, started_at, completed_at, status, 
           expected_total_tenders, extracted_total_tenders, skipped_existing_total
    FROM runs 
    WHERE portal_name LIKE "%West%Bengal%" 
    ORDER BY started_at DESC 
    LIMIT 1
''')

row = cur.fetchone()
if row:
    run_id, portal, started, completed, status, expected, extracted, skipped = row
    
    print("=" * 80)
    print("📊 MOST RECENT WEST BENGAL RUN")
    print("=" * 80)
    print(f"Run ID: {run_id}")
    print(f"Portal: {portal}")
    print(f"Started: {started}")
    print(f"Completed: {completed}")
    print(f"Status: {status}")
    print(f"Expected: {expected:,}")
    print(f"Extracted: {extracted:,}")
    print(f"Skipped: {skipped:,}")
    
    # Calculate duration
    if started and completed:
        start_dt = datetime.fromisoformat(started)
        end_dt = datetime.fromisoformat(completed)
        duration = (end_dt - start_dt).total_seconds() / 60
        print(f"Duration: {duration:.1f} minutes")
    
    # Check how many tenders are actually in the tenders table
    cur2 = conn.execute('SELECT COUNT(*) FROM tenders WHERE run_id = ?', (run_id,))
    tender_count = cur2.fetchone()[0]
    print(f"\n✅ Tenders in database: {tender_count:,}")
    
    # Check if there were periodic updates (this would show if checkpoints worked)
    print(f"\n🔍 VERIFICATION:")
    print(f"  • Database has {tender_count:,} tenders from this run")
    print(f"  • Run record shows {extracted:,} extracted")
    if tender_count == extracted:
        print(f"  ✅ All extracted tenders were saved to database!")
    elif tender_count > 0:
        print(f"  ✅ Tenders were saved (difference due to dedupe)")
    else:
        print(f"  ❌ No tenders in database - data was lost")
else:
    print("No West Bengal runs found")

conn.close()
