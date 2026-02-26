import sqlite3
from pathlib import Path

db_path = Path("D:/Dev84/BF 2.1.4/data/blackforest_tenders.sqlite3")
if not db_path.exists():
    print(f"Database not found: {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row

# Search for the specific tender
tender_id = "2026_PWD_128306_1"

print(f"\n{'='*80}")
print(f"Searching for tender ID: {tender_id}")
print(f"{'='*80}\n")

# Total occurrences
total = conn.execute(
    "SELECT COUNT(*) FROM tenders WHERE tender_id_extracted = ?",
    (tender_id,)
).fetchone()[0]

print(f"Total occurrences in database: {total}\n")

if total > 0:
    # Get detailed information
    cursor = conn.execute("""
        SELECT 
            id,
            run_id,
            portal_name,
            department_name,
            tender_id_extracted,
            closing_date,
            published_date,
            title_ref
        FROM tenders 
        WHERE tender_id_extracted = ?
        ORDER BY id
    """, (tender_id,))
    
    rows = cursor.fetchall()
    
    print("Duplicate records found:")
    print("-" * 80)
    for i, row in enumerate(rows, 1):
        print(f"\nOccurrence #{i}:")
        print(f"  Database ID: {row['id']}")
        print(f"  Run ID: {row['run_id']}")
        print(f"  Portal: {row['portal_name']}")
        print(f"  Department: {row['department_name']}")
        print(f"  Tender ID: {row['tender_id_extracted']}")
        print(f"  Closing Date: {row['closing_date']}")
        print(f"  Published Date: {row['published_date']}")
        print(f"  Title: {row['title_ref']}")

# Check for duplicates across all tenders (not just this specific ID)
print(f"\n{'='*80}")
print("Checking for ALL duplicates in database...")
print(f"{'='*80}\n")

duplicates_cursor = conn.execute("""
    SELECT 
        portal_name,
        tender_id_extracted,
        closing_date,
        COUNT(*) as count
    FROM tenders
    WHERE tender_id_extracted IS NOT NULL 
      AND tender_id_extracted != ''
    GROUP BY 
        LOWER(TRIM(portal_name)),
        TRIM(tender_id_extracted),
        closing_date
    HAVING COUNT(*) > 1
    ORDER BY count DESC
    LIMIT 20
""")

dups = duplicates_cursor.fetchall()

if dups:
    print(f"Found {len(dups)} groups of duplicates (showing top 20):")
    print("-" * 80)
    for row in dups:
        print(f"Portal: {row['portal_name']}, Tender: {row['tender_id_extracted']}, "
              f"Closing: {row['closing_date']}, Count: {row['count']}")
else:
    print("No duplicates found!")

conn.close()
