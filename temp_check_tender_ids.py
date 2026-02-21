import sqlite3

conn = sqlite3.connect('database/blackforest_tenders.sqlite3')
cursor = conn.cursor()

# Get examples from different portals
cursor.execute("""
    SELECT tender_id_extracted, portal_name, department_name 
    FROM tenders 
    WHERE tender_id_extracted IS NOT NULL 
        AND TRIM(tender_id_extracted) != ''
    ORDER BY portal_name
    LIMIT 15
""")

rows = cursor.fetchall()

print("\n" + "="*80)
print("TENDER ID EXAMPLES FROM DATABASE (Multiple Portals)")
print("="*80 + "\n")

current_portal = None
count = 0
for i, row in enumerate(rows, 1):
    tender_id, portal, dept = row
    
    # Group by portal
    if portal != current_portal:
        if current_portal is not None:
            print()
        print(f"📍 {portal}:")
        current_portal = portal
        count = 0
    
    count += 1
    if count <= 3:  # Show max 3 per portal
        print(f"   {count}. {tender_id}")
        print(f"      Department: {dept}")

# Also check the data type and format
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(DISTINCT tender_id_extracted) as unique_ids,
        COUNT(*) - COUNT(DISTINCT tender_id_extracted) as duplicates
    FROM tenders
    WHERE tender_id_extracted IS NOT NULL 
        AND TRIM(tender_id_extracted) != ''
""")

stats = cursor.fetchone()
print("\n" + "="*80)
print(f"Database Stats:")
print(f"  Total tenders with IDs: {stats[0]:,}")
print(f"  Unique tender IDs: {stats[1]:,}")
print(f"  Duplicate tender IDs: {stats[2]:,}")
print("="*80)

# Show tender ID format patterns
print("\n" + "="*80)
print("TENDER ID FORMAT ANALYSIS")
print("="*80 + "\n")

cursor.execute("""
    SELECT portal_name, tender_id_extracted
    FROM tenders 
    WHERE tender_id_extracted IS NOT NULL 
        AND TRIM(tender_id_extracted) != ''
    ORDER BY RANDOM()
    LIMIT 10
""")

formats = cursor.fetchall()
print("Sample Tender ID Formats:")
for portal, tid in formats:
    print(f"  {portal:20} | {tid}")

conn.close()
