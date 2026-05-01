import sqlite3

conn = sqlite3.connect('database/blackforest_tenders.sqlite3')
cursor = conn.cursor()

# Get top departments by tender count
cursor.execute('''
    SELECT department_name, COUNT(*) as tender_count 
    FROM tenders 
    WHERE portal_name = "West Bengal" 
    GROUP BY department_name 
    ORDER BY tender_count DESC 
    LIMIT 15
''')

results = cursor.fetchall()

print('\n' + '=' * 100)
print('Top 15 West Bengal departments by tender count:')
print('=' * 100)

for dept, count in results:
    print(f'{count:6d} tenders - {dept}')

# Check for Zila Parishad specifically
cursor.execute('''
    SELECT department_name, COUNT(*) as tender_count 
    FROM tenders 
    WHERE portal_name = "West Bengal" 
    AND department_name LIKE "%Zila%"
    GROUP BY department_name
''')

zila_results = cursor.fetchall()

if zila_results:
    print('\n' + '=' * 100)
    print('Zila Parishad departments:')
    print('=' * 100)
    for dept, count in zila_results:
        print(f'{count:6d} tenders - {dept}')
else:
    print('\nNo Zila Parishad departments found yet.')

# Total West Bengal tenders
cursor.execute('SELECT COUNT(*) FROM tenders WHERE portal_name = "West Bengal"')
total = cursor.fetchone()[0]
print('\n' + '=' * 100)
print(f'Total West Bengal tenders in database: {total:,}')
print('=' * 100)

conn.close()
