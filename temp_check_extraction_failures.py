import sqlite3

conn = sqlite3.connect('database/blackforest_tenders.sqlite3')
cur = conn.cursor()

# Get totals first
total_tenders = cur.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
print(f'\n📋 Total tenders in database: {total_tenders:,}\n')

# Check cases where extraction failed
rows = cur.execute("""
    SELECT title_ref, tender_id_extracted, portal_name
    FROM tenders 
    WHERE tender_id_extracted IS NULL 
       OR TRIM(tender_id_extracted) = '' 
       OR LOWER(TRIM(tender_id_extracted)) IN ('nan', 'none', 'null')
    ORDER BY RANDOM() 
    LIMIT 10
""").fetchall()

print('\n🚨 Cases where Tender ID extraction FAILED:\n')
print('='*80)
for i, (title, extracted_id, portal) in enumerate(rows, 1):
    title_display = (title[:100] + '...') if title and len(title) > 100 else (title or '(NULL)')
    id_display = extracted_id if extracted_id else '(NULL/EMPTY)'
    print(f'{i}. Portal: {portal}')
    print(f'   Title: {title_display}')
    print(f'   Extracted ID: {id_display}')
    print()

# Get count of failures
stats = cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN tender_id_extracted IS NULL 
                    OR TRIM(tender_id_extracted) = '' 
                    OR LOWER(TRIM(tender_id_extracted)) IN ('nan', 'none', 'null')
              THEN 1 END) as failed,
        COUNT(CASE WHEN tender_id_extracted IS NOT NULL 
                    AND TRIM(tender_id_extracted) != ''
                    AND LOWER(TRIM(tender_id_extracted)) NOT IN ('nan', 'none', 'null')
              THEN 1 END) as success
    FROM tenders
""").fetchone()

total, failed, success = stats
success_rate = (success / total * 100) if total > 0 else 0

print('='*80)
print(f'\n📊 EXTRACTION STATISTICS:')
print(f'   Total Tenders: {total:,}')
print(f'   ✅ Successful Extractions: {success:,} ({success_rate:.1f}%)')
print(f'   ❌ Failed Extractions: {failed:,} ({100-success_rate:.1f}%)')

conn.close()
