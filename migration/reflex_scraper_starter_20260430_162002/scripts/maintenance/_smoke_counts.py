import sqlite3
from pathlib import Path

p = Path(r"d:/Dev84/BF 2.1.4/database/blackforest_tenders.sqlite3")
conn = sqlite3.connect(str(p))
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM tender_items")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM tender_items WHERE portal_slug='HP Tenders'")
hp = c.fetchone()[0]
c.execute("SELECT COALESCE(MAX(updated_at), '-') FROM tender_items")
mx = c.fetchone()[0]
print(f"total={total} hp={hp} max_updated={mx}")
conn.close()
