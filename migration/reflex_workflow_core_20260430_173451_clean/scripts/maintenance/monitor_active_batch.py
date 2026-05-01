"""
Monitor currently running scraping batches
"""
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import sys

sys.path.insert(0, str(Path(__file__).parent))
from tender_store import TenderDataStore

db_path = Path("database/blackforest_tenders.sqlite3")
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

print("\n" + "=" * 80)
print("🔍 ACTIVE SCRAPING BATCH MONITOR")
print("=" * 80)
print()

# Check for running or very recent runs (last 5 minutes)
cursor = conn.execute("""
    SELECT 
        portal_name,
        started_at,
        completed_at,
        status,
        extracted_total_tenders,
        skipped_existing_total,
        expected_total_tenders
    FROM runs
    WHERE status = 'running' 
       OR (started_at > datetime('now', '-10 minutes') AND status != 'error')
    ORDER BY started_at DESC
    LIMIT 10
""")

runs = cursor.fetchall()

if not runs:
    print("⚠️  No active or recent scraping runs found")
    print()
else:
    active_count = sum(1 for r in runs if r['status'] == 'running')
    recent_completed = sum(1 for r in runs if r['status'] != 'running')
    
    print(f"📊 Found: {active_count} active, {recent_completed} recently completed")
    print()
    
    for run in runs:
        portal = run['portal_name']
        started = run['started_at']
        completed = run['completed_at']
        status = run['status']
        extracted = run['extracted_total_tenders'] or 0
        skipped = run['skipped_existing_total'] or 0
        expected = run['expected_total_tenders'] or 0
        
        # Calculate progress
        total_processed = extracted + skipped
        progress_pct = (total_processed / expected * 100) if expected > 0 else 0
        
        # Parse start time for duration
        try:
            start_dt = datetime.fromisoformat(started)
            if completed:
                end_dt = datetime.fromisoformat(completed)
                duration = (end_dt - start_dt).total_seconds() / 60
                duration_str = f"{duration:.1f} min"
            else:
                duration = (datetime.now() - start_dt).total_seconds() / 60
                duration_str = f"{duration:.1f} min (ongoing)"
        except:
            duration_str = "N/A"
        
        if status == 'running':
            print(f"🔄 {portal} (ACTIVE)")
        else:
            print(f"✅ {portal} (COMPLETED)")
        
        print(f"   ├─ Started: {started}")
        print(f"   ├─ Status: {status}")
        print(f"   ├─ Duration: {duration_str}")
        print(f"   ├─ Extracted: {extracted:,} tenders")
        print(f"   ├─ Skipped: {skipped:,} duplicates")
        
        if expected > 0:
            print(f"   ├─ Progress: {total_processed:,}/{expected:,} ({progress_pct:.1f}%)")
        
        if status == 'running':
            print(f"   └─ ⚡ Currently scraping... (watch dashboard for live updates)")
        else:
            print(f"   └─ Completed: {completed}")
        
        print()

# Show total counts by portal
print("=" * 80)
print("📊 CURRENT DATABASE TOTALS")
print("=" * 80)
print()

store = TenderDataStore(str(db_path))

# Get all unique portal names
cursor = conn.execute("SELECT DISTINCT portal_name FROM runs ORDER BY portal_name")
portals = [row['portal_name'] for row in cursor.fetchall()]

total_tenders = 0
for portal_name in portals:
    count = len(store.get_existing_tender_ids_for_portal(portal_name))
    if count > 0:
        total_tenders += count
        print(f"{portal_name:35s}: {count:6,} tenders")

print("-" * 80)
print(f"{'TOTAL':35s}: {total_tenders:6,} tenders")
print()

conn.close()
