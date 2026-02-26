import sys
sys.path.insert(0, r'D:\Dev84\BF 2.1.4')

from tender_store import TenderDataStore
import sqlite3

# Initialize the database (this creates schema if needed)
store = TenderDataStore('database/blackforest_tenders.sqlite3')

# Now check the schema
conn = sqlite3.connect('database/blackforest_tenders.sqlite3')
cursor = conn.cursor()

print('=== DATABASE TENDERS TABLE SCHEMA ===\n')
cursor.execute('PRAGMA table_info(tenders)')
cols = cursor.fetchall()

print(f'Total Columns: {len(cols)}\n')
for col in cols:
    default_val = f"DEFAULT '{col[4]}'" if col[4] else ""
    print(f'{col[0]+1:2d}. {col[1]:30s} {col[2]:15s} {default_val}')

print('\n=== COLUMN NAMES LIST ===')
print([col[1] for col in cols])

conn.close()
