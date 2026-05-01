import sqlite3

conn = sqlite3.connect('database/blackforest_tenders.sqlite3')
cur = conn.cursor()

print('\n📊 COMPLETE DATABASE ANALYSIS:\n')
print('='*80)

# Total count
total = cur.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
print(f'Total tenders in database: {total:,}')

# With valid tender IDs
valid_ids = cur.execute("""
    SELECT COUNT(*) FROM tenders 
    WHERE tender_id_extracted IS NOT NULL 
      AND TRIM(tender_id_extracted) != ''
      AND LOWER(TRIM(tender_id_extracted)) NOT IN ('nan', 'none', 'null', 'na', 'n/a', '-')
""").fetchone()[0]
print(f'✅ Tenders with valid extracted IDs: {valid_ids:,}')

# Missing IDs (NULL or empty)
missing_ids = cur.execute("""
    SELECT COUNT(*) FROM tenders 
    WHERE tender_id_extracted IS NULL 
       OR TRIM(tender_id_extracted) = ''
""").fetchone()[0]
print(f'❌ Tenders with NULL/empty IDs: {missing_ids:,}')

# Invalid placeholder IDs
placeholder_ids = cur.execute("""
    SELECT COUNT(*) FROM tenders 
    WHERE LOWER(TRIM(tender_id_extracted)) IN ('nan', 'none', 'null', 'na', 'n/a', '-')
""").fetchone()[0]
print(f'⚠️  Tenders with placeholder IDs: {placeholder_ids:,}')

print('='*80)

# Show examples of missing/invalid
print('\n🔍 Examples of tenders without valid IDs:\n')
examples = cur.execute("""
    SELECT title_ref, tender_id_extracted, portal_name, closing_date
    FROM tenders 
    WHERE tender_id_extracted IS NULL 
       OR TRIM(tender_id_extracted) = ''
       OR LOWER(TRIM(tender_id_extracted)) IN ('nan', 'none', 'null', 'na', 'n/a', '-')
    LIMIT 10
""").fetchall()

for i, (title, tid, portal, closing) in enumerate(examples, 1):
    title_display = (title[:80] + '...') if title and len(title) > 80 else (title or '(NULL)')
    id_display = tid if tid else '(NULL/EMPTY)'
    print(f'{i}. {portal} | Closing: {closing}')
    print(f'   Title: {title_display}')
    print(f'   Extracted ID: {id_display}')
    print()

# Success rate
success_rate = (valid_ids / total * 100) if total > 0 else 0
failure_rate = ((missing_ids + placeholder_ids) / total * 100) if total > 0 else 0

print('='*80)
print(f'\n📈 EXTRACTION SUCCESS RATE: {success_rate:.2f}%')
print(f'📉 EXTRACTION FAILURE RATE: {failure_rate:.2f}%')

conn.close()
