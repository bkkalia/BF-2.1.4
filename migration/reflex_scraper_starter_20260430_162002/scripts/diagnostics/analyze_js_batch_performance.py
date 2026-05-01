import sqlite3
from datetime import datetime

# Analyze the latest scraping runs to understand JS batch performance
conn = sqlite3.connect('database/blackforest_tenders.sqlite3')
cur = conn.cursor()

print('\n📊 SCRAPING PERFORMANCE ANALYSIS - JS BATCH STATUS:\n')
print('='*100)

# Get unique run IDs with stats
runs = cur.execute("""
    SELECT 
        run_id,
        portal_name,
        COUNT(*) as tender_count,
        MIN(id) as first_tender_id,
        MAX(id) as last_tender_id
    FROM tenders
    GROUP BY run_id, portal_name
    ORDER BY run_id DESC
    LIMIT 20
""").fetchall()

print('\n🔄 RECENT SCRAPING RUNS:\n')
print(f'{"Run ID":<8} {"Portal":<25} {"Tenders":<10} {"First ID":<12} {"Last ID":<12}')
print('-'*100)

for run_id, portal, count, first_id, last_id in runs:
    print(f'{run_id:<8} {portal:<25} {count:>8,}   {first_id:>10}   {last_id:>10}')

# Analyze department sizes to see which ones would trigger JS batching
print('\n\n📈 DEPARTMENT SIZES (JS Batch triggers at 300+ rows):\n')
print('='*100)

dept_sizes = cur.execute("""
    SELECT 
        portal_name,
        department_name,
        COUNT(*) as tender_count,
        MAX(run_id) as latest_run
    FROM tenders
    GROUP BY portal_name, department_name
    HAVING COUNT(*) > 100
    ORDER BY tender_count DESC
    LIMIT 30
""").fetchall()

print(f'{"Portal":<25} {"Department":<50} {"Tenders":<10} {"Latest Run":<12}')
print('-'*100)

js_batch_count = 0
normal_count = 0

for portal, dept, count, run_id in dept_sizes:
    dept_display = (dept[:47] + '...') if len(dept) > 50 else dept
    marker = '🚀 [JS BATCH]' if count >= 300 else ''
    if count >= 300:
        js_batch_count += 1
    else:
        normal_count += 1
    print(f'{portal:<25} {dept_display:<50} {count:>8,}   {run_id:<12} {marker}')

print('\n' + '='*100)
print(f'\n📊 BATCH STATISTICS:')
print(f'   Departments with 300+ tenders (JS Batch mode): {js_batch_count}')
print(f'   Departments with 100-299 tenders (Normal mode): {normal_count}')
print(f'   Total large departments: {js_batch_count + normal_count}')

# Check West Bengal specifically (known to have large departments)
print('\n\n🔍 WEST BENGAL ANALYSIS (Largest Portal - 26,882 tenders):\n')
print('='*100)

wb_depts = cur.execute("""
    SELECT 
        department_name,
        COUNT(*) as tender_count,
        MAX(closing_date) as latest_closing
    FROM tenders
    WHERE LOWER(portal_name) = 'west bengal'
    GROUP BY department_name
    ORDER BY tender_count DESC
    LIMIT 20
""").fetchall()

print(f'{"Department":<60} {"Tenders":<10} {"Latest Closing":<20}')
print('-'*100)

wb_js_batch = 0
for dept, count, closing in wb_depts:
    dept_display = (dept[:57] + '...') if len(dept) > 60 else dept
    marker = '🚀' if count >= 300 else ''
    if count >= 300:
        wb_js_batch += 1
    print(f'{dept_display:<60} {count:>8,}   {closing or "N/A":<20} {marker}')

print(f'\nWest Bengal departments using JS Batch: {wb_js_batch}/20')

# Check Kerala (second largest)
print('\n\n🔍 KERALA ANALYSIS (Second Largest - 6,025 tenders):\n')
print('='*100)

kerala_depts = cur.execute("""
    SELECT 
        department_name,
        COUNT(*) as tender_count
    FROM tenders
    WHERE LOWER(portal_name) = 'kerala'
    GROUP BY department_name
    ORDER BY tender_count DESC
    LIMIT 15
""").fetchall()

print(f'{"Department":<60} {"Tenders":<10}')
print('-'*100)

kerala_js_batch = 0
for dept, count in kerala_depts:
    dept_display = (dept[:57] + '...') if len(dept) > 60 else dept
    marker = '🚀' if count >= 300 else ''
    if count >= 300:
        kerala_js_batch += 1
    print(f'{dept_display:<60} {count:>8,}   {marker}')

print(f'\nKerala departments using JS Batch: {kerala_js_batch}/15')

# Overall stats
print('\n\n' + '='*100)
print('\n✅ CURRENT JS BATCH CONFIGURATION:')
print('   Threshold: 300 rows (departments with 300+ rows use batched JS extraction)')
print('   Batch Size: 2000 rows per batch')
print('   ')
print('   💡 This means:')
print('      - Departments with 1-299 rows: Extract all at once (fast)')
print('      - Departments with 300-1999 rows: Extract all at once (fast)')
print('      - Departments with 2000+ rows: Extract in batches of 2000 (ultra-fast)')

conn.close()
