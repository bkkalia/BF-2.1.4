import sqlite3

conn = sqlite3.connect('data/blackforest_tenders.sqlite3')
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print(f"Tables: {tables}")

# Check if V3 schema
if 'portals' in tables and 'tender_items' in tables:
    print("\nV3 Schema detected!")
    cursor.execute("PRAGMA table_info(portals)")
    print("Portals columns:", [r[1] for r in cursor.fetchall()])
    
    cursor.execute("PRAGMA table_info(tender_items)")
    print("Tender_items columns:", [r[1] for r in cursor.fetchall()])
    
    # Test query
    cursor.execute("SELECT COUNT(*) FROM portals")
    print(f"Number of portals: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM tender_items")
    print(f"Number of tender items: {cursor.fetchone()[0]}")
else:
    print("\nLegacy schema detected!")
    cursor.execute("PRAGMA table_info(tenders)")
    print("Tenders columns:", [r[1] for r in cursor.fetchall()])

conn.close()
