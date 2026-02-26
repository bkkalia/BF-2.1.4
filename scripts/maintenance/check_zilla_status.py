import sqlite3
from datetime import datetime

conn = sqlite3.connect('database/blackforest_tenders.sqlite3')
c = conn.cursor()

print("=" * 80)
print("ZILLA PARISHAD STATUS CHECK")
print("=" * 80)
print()

# Count tenders
c.execute('''
    SELECT COUNT(*) 
    FROM tenders 
    WHERE portal_name = "West Bengal" 
    AND department_name LIKE "%Zilla%"
''')
count = c.fetchone()[0]
print(f"Total Zilla Parishad tenders in database: {count:,}")

# Get last scrape time
c.execute('''
    SELECT MAX(created_at), MAX(run_id)
    FROM tenders 
    WHERE portal_name = "West Bengal" 
    AND department_name LIKE "%Zilla%"
''')
last_created, last_run_id = c.fetchone()
print(f"Last scraped: {last_created}")
print(f"Last run_id: {last_run_id}")

# Get run details
if last_run_id:
    c.execute('''
        SELECT started_at, completed_at, status, portal_name
        FROM runs
        WHERE id = ?
    ''', (last_run_id,))
    run = c.fetchone()
    if run:
        print(f"\nRun #{last_run_id} details:")
        print(f"  Started: {run[0]}")
        print(f"  Completed: {run[1]}")
        print(f"  Status: {run[2]}")
        print(f"  Portal: {run[3]}")

# Check if there are any runs from today
c.execute('''
    SELECT id, started_at, status, portal_name
    FROM runs
    WHERE portal_name = "West Bengal"
    AND DATE(started_at) = DATE('now')
    ORDER BY started_at DESC
''')
today_runs = c.fetchall()

if today_runs:
    print(f"\n{'=' * 80}")
    print("TODAY'S WEST BENGAL RUNS:")
    print("=" * 80)
    for run_id, started, status, portal in today_runs:
        print(f"Run #{run_id}: {started} - Status: {status}")

        # Check if Zilla Parishad was scraped in this run
        c.execute('''
            SELECT COUNT(*)
            FROM tenders
            WHERE run_id = ?
            AND department_name LIKE "%Zilla%"
        ''', (run_id,))
        zilla_count = c.fetchone()[0]
        if zilla_count > 0:
            print(f"  └─ Zilla Parishad tenders: {zilla_count}")
else:
    print("\nNo West Bengal runs today.")

# Check yesterday's runs
c.execute('''
    SELECT id, started_at, status, portal_name
    FROM runs
    WHERE portal_name = "West Bengal"
    AND DATE(started_at) = DATE('now', '-1 day')
    ORDER BY started_at DESC
''')
yesterday_runs = c.fetchall()

if yesterday_runs:
    print(f"\n{'=' * 80}")
    print("YESTERDAY'S WEST BENGAL RUNS:")
    print("=" * 80)
    for run_id, started, status, portal in yesterday_runs:
        print(f"Run #{run_id}: {started} - Status: {status}")
        
        c.execute('''
            SELECT COUNT(*)
            FROM tenders
            WHERE run_id = ?
            AND department_name LIKE "%Zilla%"
        ''', (run_id,))
        zilla_count = c.fetchone()[0]
        if zilla_count > 0:
            print(f"  └─ Zilla Parishad tenders: {zilla_count}")

print()
print("=" * 80)

conn.close()
