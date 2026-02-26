import sqlite3
import sys

sys.path.insert(0, r'D:\Dev84\BF 2.1.4')

conn = sqlite3.connect(r'database/blackforest_tenders.sqlite3')
cursor = conn.cursor()

print('=== TENDERS TABLE SCHEMA ===')
cursor.execute('PRAGMA table_info(tenders)')
cols = cursor.fetchall()
for col in cols:
    print(f'{col[0]:3d}. {col[1]:30s} {col[2]:15s} NotNull={col[3]} Default={col[4]}')

print(f'\n=== TOTAL COLUMNS: {len(cols)} ===')

print('\n=== SAMPLE DATA (1 ROW) ===')
cursor.execute('SELECT * FROM tenders LIMIT 1')
row = cursor.fetchone()
if row:
    for i, val in enumerate(row):
        print(f'{cols[i][1]:30s}: {str(val)[:100]}')

print(f'\n=== TOTAL TENDERS IN DATABASE ===')
cursor.execute('SELECT COUNT(*) FROM tenders')
print(f'Total: {cursor.fetchone()[0]}')

conn.close()
