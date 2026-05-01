from __future__ import annotations

import csv
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _db_path() -> Path:
    return _workspace_root() / "database" / "blackforest_tenders.sqlite3"


def _backup_db(db_path: Path) -> Path:
    backup_dir = _workspace_root() / "db_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"blackforest_tenders_pre_v3_fresh_{stamp}.sqlite3"
    shutil.copy2(db_path, backup_path)
    return backup_path


def _load_base_urls() -> list[tuple[str, str, str]]:
    csv_path = _workspace_root() / "base_urls.csv"
    if not csv_path.exists():
        return []

    rows: list[tuple[str, str, str]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            name = str(row.get("Name") or "").strip()
            base_url = str(row.get("BaseURL") or "").strip()
            if not name:
                continue
            rows.append((name, name, base_url))
    return rows


def init_v3_fresh() -> None:
    db_path = _db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    backup = _backup_db(db_path)
    portal_rows = _load_base_urls()

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")

        # v3 schema
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS portals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portal_slug TEXT NOT NULL UNIQUE,
                portal_name TEXT NOT NULL,
                base_url TEXT,
                last_updated TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tender_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portal_id INTEGER NOT NULL,
                portal_slug TEXT NOT NULL,
                tender_id_extracted TEXT,
                title_ref TEXT,
                department_name TEXT,
                published_at TEXT,
                closing_at TEXT,
                opening_date TEXT,
                organisation_chain TEXT,
                tender_url TEXT,
                status_url TEXT,
                estimated_cost_value REAL,
                tender_status TEXT,
                is_live INTEGER,
                state_name TEXT,
                district TEXT,
                city TEXT,
                tender_type TEXT,
                work_type TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (portal_id) REFERENCES portals(id) ON DELETE CASCADE
            )
            """
        )

        cur.execute("CREATE INDEX IF NOT EXISTS idx_portals_slug ON portals(portal_slug)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_portals_name ON portals(portal_name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ti_portal_id ON tender_items(portal_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ti_portal_slug ON tender_items(portal_slug)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ti_is_live ON tender_items(is_live)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ti_closing_at ON tender_items(closing_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ti_published_at ON tender_items(published_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ti_department_name ON tender_items(department_name)")

        # Fresh start: clear any existing v3 rows and seed portals only.
        cur.execute("DELETE FROM tender_items")
        cur.execute("DELETE FROM portals")

        if portal_rows:
            cur.executemany(
                """
                INSERT INTO portals (portal_slug, portal_name, base_url, last_updated)
                VALUES (?, ?, ?, NULL)
                """,
                portal_rows,
            )

        conn.commit()

        cur.execute("SELECT COUNT(*) FROM portals")
        portal_count = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM tender_items")
        tender_count = int(cur.fetchone()[0])

        print(f"DB: {db_path}")
        print(f"Backup: {backup}")
        print(f"V3 initialized. portals={portal_count}, tender_items={tender_count}")
    finally:
        conn.close()


if __name__ == "__main__":
    init_v3_fresh()
