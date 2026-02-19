import sqlite3
import pandas as pd

db_path = r'D:\Dev84\BF 2.1.4\data\blackforest_tenders.sqlite3'

# Connect to database
conn = sqlite3.connect(db_path)

print('=== DATABASE SCHEMA ===')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f'Tables: {[t[0] for t in tables]}')
print()

# Get tenders table schema
cursor.execute('PRAGMA table_info(tenders)')
columns_info = cursor.fetchall()
print('=== TENDERS TABLE COLUMNS ===')
for col in columns_info:
    print(f'{col[1]:30} {col[2]:15}')
print()

# Check if URL columns exist
url_columns = []
for col in columns_info:
    if 'url' in col[1].lower() or 'link' in col[1].lower():
        url_columns.append(col[1])

print(f'=== URL/LINK COLUMNS IN DATABASE: {url_columns} ===')
print()

# Get sample data
df = pd.read_sql('SELECT * FROM tenders LIMIT 3', conn)
print('=== DATABASE COLUMNS ===')
print(df.columns.tolist())
print()

# Check if we have URL data
if url_columns:
    print('=== URL COLUMN DATA ===')
    for col in url_columns:
        query = f"SELECT {col} FROM tenders WHERE {col} IS NOT NULL AND {col} != '' LIMIT 3"
        cursor.execute(query)
        results = cursor.fetchall()
        print(f'{col}: {len(results)} non-empty values found')
        for r in results[:3]:
            url_val = r[0] if r[0] else ''
            print(f'  - {url_val[:100]}...' if len(url_val) > 100 else f'  - {url_val}')
    print()
else:
    print('=== NO URL COLUMNS FOUND IN DATABASE ===')
    print()
    
# Check what columns we DO have with sample data
print('=== ALL DATABASE COLUMNS WITH SAMPLE DATA ===')
for col in df.columns:
    sample = df[col].dropna().head(1)
    if not sample.empty:
        val = str(sample.values[0])
        display = f'{val[:80]}...' if len(val) > 80 else val
        print(f'{col:30} {display}')
    else:
        print(f'{col:30} (No data in first 3 rows)')

conn.close()
