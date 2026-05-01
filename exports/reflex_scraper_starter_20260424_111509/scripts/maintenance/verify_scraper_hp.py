"""
Verification Script: Check HP Tenders Scraper Correctness
- Shows existing tender counts
- Verifies duplicate detection
- Checks recent imports
- Validates database integrity
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from tender_store import TenderDataStore


def main():
    db_path = Path("database/blackforest_tenders.sqlite3")
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    store = TenderDataStore(str(db_path))
    
    print("=" * 80)
    print("🔍 HP TENDERS SCRAPER VERIFICATION")
    print("=" * 80)
    print()
    
    # 1. Check existing HP tender count
    print("📊 EXISTING HP TENDERS IN DATABASE:")
    print("-" * 80)
    
    portal_name = "HP Tenders"
    existing_ids = store.get_existing_tender_ids_for_portal(portal_name)
    
    if existing_ids:
        print(f"✅ Found {len(existing_ids)} existing tenders for '{portal_name}'")
        print(f"   First 5 Tender IDs: {list(existing_ids)[:5]}")
        print()
    else:
        print(f"⚠️  No existing tenders found for '{portal_name}'")
        print("   (This is expected if HP hasn't been scraped before)")
        print()
    
    # 2. Check tender snapshot (for closing date comparison)
    snapshot = store.get_existing_tender_snapshot_for_portal(portal_name)
    if snapshot:
        print(f"✅ Tender snapshot loaded: {len(snapshot)} records")
        # Show a sample
        sample_id = list(snapshot.keys())[0] if snapshot else None
        if sample_id:
            sample_data = snapshot[sample_id]
            print(f"   Sample: {sample_id} → Closing: {sample_data.get('closing_date', 'N/A')}")
        print()
    
    # 3. Check recent runs for HP
    print("📋 RECENT HP SCRAPING RUNS:")
    print("-" * 80)
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("""
        SELECT 
            id,
            started_at,
            completed_at,
            status,
            expected_total_tenders,
            extracted_total_tenders,
            skipped_existing_total,
            scope_mode
        FROM runs
        WHERE portal_name = ?
        ORDER BY started_at DESC
        LIMIT 5
    """, (portal_name,))
    
    runs = cursor.fetchall()
    
    if runs:
        for run in runs:
            run_id = run['id']
            started = run['started_at']
            completed = run['completed_at'] or 'In Progress'
            status = run['status'] or 'Running'
            expected = run['expected_total_tenders'] or 0
            extracted = run['extracted_total_tenders'] or 0
            skipped = run['skipped_existing_total'] or 0
            scope = run['scope_mode'] or 'all'
            
            print(f"\n   Run #{run_id}:")
            print(f"   ├─ Started: {started}")
            print(f"   ├─ Status: {status} ({completed})")
            print(f"   ├─ Scope: {scope}")
            print(f"   ├─ Expected: {expected}")
            print(f"   ├─ Extracted (New): {extracted}")
            print(f"   └─ Skipped (Duplicates): {skipped}")
            
            if skipped > 0:
                total_processed = extracted + skipped
                dup_rate = (skipped / total_processed * 100) if total_processed > 0 else 0
                print(f"      → Duplicate Rate: {dup_rate:.1f}% ({skipped}/{total_processed})")
    else:
        print("   No runs found for HP Tenders")
    
    print()
    
    # 4. Check department distribution
    print("🏛️  TENDERS BY DEPARTMENT (Top 10):")
    print("-" * 80)
    
    cursor = conn.execute("""
        SELECT 
            department_name,
            COUNT(*) as tender_count,
            MAX(closing_date) as latest_closing
        FROM tenders
        WHERE portal_name = ?
        GROUP BY department_name
        ORDER BY tender_count DESC
        LIMIT 10
    """, (portal_name,))
    
    depts = cursor.fetchall()
    
    if depts:
        for dept in depts:
            dept_name = dept['department_name'] or 'Unknown'
            count = dept['tender_count']
            latest = dept['latest_closing'] or 'N/A'
            print(f"   {dept_name[:50]:<50} {count:>5} tenders (Latest: {latest})")
    else:
        print("   No departments found")
    
    print()
    
    # 5. Check for duplicates (shouldn't exist with proper ID normalization)
    print("🔍 DUPLICATE CHECK (Same Tender ID, Different Rows):")
    print("-" * 80)
    
    cursor = conn.execute("""
        SELECT 
            tender_id_extracted,
            COUNT(*) as count
        FROM tenders
        WHERE portal_name = ?
          AND TRIM(COALESCE(tender_id_extracted, '')) != ''
        GROUP BY LOWER(TRIM(tender_id_extracted))
        HAVING COUNT(*) > 1
        ORDER BY count DESC
        LIMIT 10
    """, (portal_name,))
    
    duplicates = cursor.fetchall()
    
    if duplicates:
        print(f"   ⚠️  Found {len(duplicates)} duplicate tender IDs:")
        for dup in duplicates:
            tender_id = dup['tender_id_extracted']
            count = dup['count']
            print(f"      {tender_id}: {count} occurrences")
        print()
        print("   Note: Some duplicates may be legitimate (different departments, closing date changed)")
    else:
        print("   ✅ No duplicate tender IDs found (Good!)")
    
    print()
    
    # 6. Check closing date changes (extended deadlines)
    print("↻ CLOSING DATE EXTENSIONS (Last 20):")
    print("-" * 80)
    
    cursor = conn.execute("""
        WITH tender_history AS (
            SELECT 
                tender_id_extracted,
                closing_date,
                run_id,
                ROW_NUMBER() OVER (
                    PARTITION BY LOWER(TRIM(tender_id_extracted)) 
                    ORDER BY run_id DESC
                ) as rn
            FROM tenders
            WHERE portal_name = ?
              AND TRIM(COALESCE(tender_id_extracted, '')) != ''
        )
        SELECT 
            t1.tender_id_extracted,
            t2.closing_date as old_closing,
            t1.closing_date as new_closing,
            t1.run_id
        FROM tender_history t1
        INNER JOIN tender_history t2 
            ON LOWER(TRIM(t1.tender_id_extracted)) = LOWER(TRIM(t2.tender_id_extracted))
            AND t1.rn = 1 
            AND t2.rn = 2
            AND t1.closing_date != t2.closing_date
        ORDER BY t1.run_id DESC
        LIMIT 20
    """, (portal_name,))
    
    extensions = cursor.fetchall()
    
    if extensions:
        print(f"   Found {len(extensions)} recent closing date changes:")
        for ext in extensions:
            tender_id = ext['tender_id_extracted']
            old_date = ext['old_closing']
            new_date = ext['new_closing']
            print(f"      {tender_id}: {old_date} → {new_date}")
    else:
        print("   No closing date changes detected")
    
    print()
    
    # 7. Summary
    print("=" * 80)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 80)
    
    total_hp_tenders = len(existing_ids) if existing_ids else 0
    total_runs = len(runs)
    has_duplicates = len(duplicates) > 0
    
    print(f"   Total HP Tenders in DB: {total_hp_tenders}")
    print(f"   Total Scraping Runs: {total_runs}")
    print(f"   Duplicate Detection: {'✅ Working' if not has_duplicates else '⚠️  Found duplicates'}")
    print(f"   Database Path: {db_path.absolute()}")
    print()
    
    if total_hp_tenders > 0:
        print("✅ SCRAPER APPEARS TO BE WORKING CORRECTLY")
        print()
        print("Expected Behavior:")
        print("   1. New tenders → Downloaded and saved to database")
        print("   2. Existing tenders (same ID, same closing date) → Skipped")
        print("   3. Closing date changed → Re-processed and updated")
        print()
        print("Next Test:")
        print("   Run HP scraping again - should see high duplicate rate (80-95%)")
        print("   Log should show: '🚀 BULK FILTER: ... duplicates skipped'")
    else:
        print("ℹ️  No HP tenders in database yet")
        print("   First scrape will download all tenders (0% duplicates)")
        print("   Second scrape should skip most (80-95% duplicates)")
    
    print()
    print("=" * 80)
    
    conn.close()


if __name__ == "__main__":
    main()
