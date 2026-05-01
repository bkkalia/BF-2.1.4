import sqlite3
import csv
from datetime import datetime

# Read all portals from base_urls.csv
portals_in_config = set()
with open('base_urls.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('Name'):
            portals_in_config.add(row['Name'].strip())

# Check which portals have data in database
conn = sqlite3.connect('database/blackforest_tenders.sqlite3')
cur = conn.cursor()

portals_with_data = cur.execute("""
    SELECT 
        portal_name,
        COUNT(*) as tender_count,
        MAX(published_date) as latest_published,
        MAX(run_id) as latest_run_id
    FROM tenders
    WHERE portal_name IS NOT NULL
    GROUP BY portal_name
    ORDER BY tender_count DESC
""").fetchall()

print('\n📊 PORTAL STATUS ANALYSIS:\n')
print('='*100)

print(f'\n✅ PORTALS WITH DATA ({len(portals_with_data)} portals):\n')
print(f'{"Portal Name":<30} {"Tenders":<12} {"Latest Published":<20} {"Latest Run ID":<15}')
print('-'*100)

scraped_portals = set()
for portal, count, latest_pub, latest_run in portals_with_data:
    scraped_portals.add(portal)
    print(f'{portal:<30} {count:>10,}   {latest_pub or "N/A":<20} {latest_run or "N/A":<15}')

# Find pending portals
pending_portals = portals_in_config - scraped_portals

print(f'\n\n❌ PENDING PORTALS ({len(pending_portals)} portals):\n')
print('-'*100)
if pending_portals:
    for i, portal in enumerate(sorted(pending_portals), 1):
        print(f'{i}. {portal}')
else:
    print('No pending portals - all configured portals have been scraped!')

print('\n' + '='*100)
print(f'\n📈 SUMMARY:')
print(f'   Total Configured Portals: {len(portals_in_config)}')
print(f'   ✅ Scraped: {len(scraped_portals)}')
print(f'   ❌ Pending: {len(pending_portals)}')

conn.close()
