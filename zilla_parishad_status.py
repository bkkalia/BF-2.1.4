import sqlite3

conn = sqlite3.connect('database/blackforest_tenders.sqlite3')
c = conn.cursor()

print("=" * 100)
print("ZILLA PARISHAD BATCHED EXTRACTION STATUS REPORT")
print("=" * 100)
print()

# Count total Zilla Parishad tenders
c.execute('''
    SELECT COUNT(*) 
    FROM tenders 
    WHERE portal_name = "West Bengal" 
    AND department_name LIKE "%Zilla%"
''')
total_count = c.fetchone()[0]

print(f"📊 CURRENT DATABASE STATUS:")
print(f"   Total Zilla Parishad tenders: {total_count:,}")
print()

# Get run information
c.execute('''
    SELECT 
        t.run_id,
        COUNT(*) as tender_count,
        r.started_at,
        r.completed_at,
        r.status
    FROM tenders t
    JOIN runs r ON t.run_id = r.id
    WHERE t.portal_name = "West Bengal" 
    AND t.department_name LIKE "%Zilla%"
    GROUP BY t.run_id
    ORDER BY r.started_at DESC
''')

runs = c.fetchall()

if runs:
    print("📅 SCRAPING HISTORY:")
    print()
    for run_id, count, started, completed, status in runs:
        print(f"   Run #{run_id}:")
        print(f"   ├─ Started: {started}")
        print(f"   ├─ Completed: {completed}")
        print(f"   ├─ Status: {status}")
        print(f"   └─ Zilla Parishad tenders scraped: {count:,}")
        print()

# Check the most recent West Bengal run
c.execute('''
    SELECT id, started_at, completed_at, status
    FROM runs
    WHERE portal_name = "West Bengal"
    ORDER BY started_at DESC
    LIMIT 1
''')

latest_run = c.fetchone()
if latest_run:
    run_id, started, completed, status = latest_run
    print("🔍 LATEST WEST BENGAL RUN:")
    print(f"   Run #{run_id}")
    print(f"   Started: {started}")
    print(f"   Completed: {completed}")
    print(f"   Status: {status}")
    
    # Check if Zilla Parishad was scraped in this run
    c.execute('''
        SELECT COUNT(*)
        FROM tenders
        WHERE run_id = ?
        AND department_name LIKE "%Zilla%"
    ''', (run_id,))
    zilla_in_run = c.fetchone()[0]
    
    if zilla_in_run > 0:
        print(f"   ✅ Zilla Parishad scraped: {zilla_in_run:,} tenders")
    else:
        print(f"   ⏭️  Zilla Parishad SKIPPED (already processed in earlier run)")

print()
print("=" * 100)
print("BATCHED EXTRACTION STATUS:")
print("=" * 100)
print()
print("❌ BATCHED EXTRACTION NOT TESTED YET")
print()
print("Why:")
print("   • Batched JS extraction was implemented on Feb 20, 2026")
print("   • Threshold: Automatically triggered for departments with 3000+ rows")
print("   • Batch size: 2000 rows per batch")
print()
print(f"   • Zilla Parishad has 13,000+ rows - WOULD trigger batched mode")
print(f"   • However, it was already scraped in an earlier run (before implementation)")
print(f"   • Yesterday's run SKIPPED it due to resume detection")
print()
print("To test batched extraction on Zilla Parishad:")
print("   1. Delete Zilla Parishad tenders from database")
print("   2. Re-scrape West Bengal portal")
print("   3. Monitor logs for:")
print("      - '[JS] Large department detected (13000+ rows)'")
print("      - '[JS] Batch 1/7: rows 0-1999...'")
print("      - '[JS] Batched mode successful: XXXX rows extracted'")
print()
print("=" * 100)

conn.close()
