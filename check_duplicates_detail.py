"""
Check Duplicate Tender IDs - Are they legitimate?
"""

import sqlite3
from pathlib import Path
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    try:
        # Try to reconfigure stdout for UTF-8
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        # Fallback for older Python or non-reconfigurable streams
        try:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        except Exception:
            # Last resort: just continue with default encoding
            pass

db_path = Path("database/blackforest_tenders.sqlite3")
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

print("=" * 80)
print("INVESTIGATING DUPLICATE TENDER IDs")
print("=" * 80)
print()

# Check the specific duplicates found
cursor = conn.execute("""
    WITH dup_ids AS (
        SELECT 
            LOWER(TRIM(tender_id_extracted)) as normalized_id,
            COUNT(*) as count
        FROM tenders
        WHERE portal_name = 'HP Tenders'
          AND TRIM(COALESCE(tender_id_extracted, '')) != ''
        GROUP BY LOWER(TRIM(tender_id_extracted))
        HAVING COUNT(*) > 1
    )
    SELECT 
        t.tender_id_extracted,
        t.department_name,
        t.closing_date,
        t.run_id,
        r.started_at as run_started,
        t.title_ref
    FROM tenders t
    INNER JOIN runs r ON t.run_id = r.id
    WHERE LOWER(TRIM(t.tender_id_extracted)) IN (SELECT normalized_id FROM dup_ids)
    ORDER BY t.tender_id_extracted, t.run_id DESC
    LIMIT 50
""")

rows = cursor.fetchall()

current_id = None
dup_count = 0

for row in rows:
    tender_id = row['tender_id_extracted']
    dept = row['department_name'] or 'Unknown'
    closing = row['closing_date'] or 'N/A'
    run_id = row['run_id']
    run_started = row['run_started']
    title = row['title_ref'] or 'N/A'
    
    if tender_id != current_id:
        if current_id is not None:
            print()
        current_id = tender_id
        dup_count += 1
        print(f"\n{dup_count}. Tender ID: {tender_id}")
        print("-" * 80)
    
    print(f"   Run #{run_id} ({run_started}):")
    print(f"   ├─ Department: {dept[:60]}")
    print(f"   ├─ Closing: {closing}")
    print(f"   └─ Title: {title[:70]}")

print()
print("=" * 80)
print("ANALYSIS")
print("=" * 80)

# Check if duplicates are from different runs (closing date changes)
cursor = conn.execute("""
    WITH dup_ids AS (
        SELECT 
            LOWER(TRIM(tender_id_extracted)) as normalized_id,
            COUNT(*) as count
        FROM tenders
        WHERE portal_name = 'HP Tenders'
          AND TRIM(COALESCE(tender_id_extracted, '')) != ''
        GROUP BY LOWER(TRIM(tender_id_extracted))
        HAVING COUNT(*) > 1
    ),
    dup_analysis AS (
        SELECT 
            t.tender_id_extracted,
            COUNT(DISTINCT t.run_id) as run_count,
            COUNT(DISTINCT t.closing_date) as closing_date_count,
            COUNT(*) as total_occurrences
        FROM tenders t
        WHERE LOWER(TRIM(t.tender_id_extracted)) IN (SELECT normalized_id FROM dup_ids)
        GROUP BY LOWER(TRIM(t.tender_id_extracted))
    )
    SELECT 
        COUNT(*) as total_dup_tender_ids,
        SUM(CASE WHEN closing_date_count > 1 THEN 1 ELSE 0 END) as with_diff_closing,
        SUM(CASE WHEN run_count > 1 THEN 1 ELSE 0 END) as from_diff_runs,
        SUM(CASE WHEN run_count = 1 AND closing_date_count = 1 THEN 1 ELSE 0 END) as true_duplicates
    FROM dup_analysis
""")

analysis = cursor.fetchone()

total = analysis['total_dup_tender_ids']
diff_closing = analysis['with_diff_closing']
diff_runs = analysis['from_diff_runs']
true_dups = analysis['true_duplicates']

print()
print(f"Total Duplicate Tender IDs: {total}")
print(f"├─ With Different Closing Dates (Extended Deadlines): {diff_closing}")
print(f"├─ From Different Runs (Re-scraped): {diff_runs}")
print(f"└─ True Duplicates (Same Run, Same Closing): {true_dups}")
print()

if true_dups > 0:
    print("WARNING: TRUE DUPLICATES FOUND - Database cleanup recommended")
    print("   These shouldn't exist if duplicate detection is working properly")
else:
    print("OK: NO TRUE DUPLICATES")
    print("   All duplicate IDs are from:")
    print("   - Different scraping runs (re-scraping same portal)")
    print("   - Closing date changes (deadline extensions)")
    print("   - Different departments (rare but can happen)")

# Check if duplicates need cleanup
if total > 0:
    print()
    print("RECOMMENDATION:")
    print()
    
    if true_dups > 0:
        print("   Run database deduplication to remove true duplicates:")
        print("   python fix_database_duplicates.py")
    else:
        print("   Duplicates appear legitimate - keep both versions for audit trail")
        print("   Consider implementing duplicate cleanup strategy:")
        print("   - Keep latest run's version only")
        print("   - Or keep version with latest closing date")

print()
print("=" * 80)

conn.close()
