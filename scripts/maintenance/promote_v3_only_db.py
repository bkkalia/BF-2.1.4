from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def active_db_path() -> Path:
    return workspace_root() / "database" / "blackforest_tenders.sqlite3"


def archive_path() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = workspace_root() / "db_backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"blackforest_tenders_mixed_archive_{stamp}.sqlite3"


def temp_v3_path() -> Path:
    return workspace_root() / "database" / "blackforest_tenders_v3_only.tmp.sqlite3"


def create_v3_only_copy(src_path: Path, dst_path: Path) -> tuple[int, int]:
    if dst_path.exists():
        dst_path.unlink()

    src = sqlite3.connect(str(src_path))
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(str(dst_path))
    dst.row_factory = sqlite3.Row

    try:
        s = src.cursor()
        d = dst.cursor()

        d.execute("PRAGMA foreign_keys=ON")
        d.execute("PRAGMA journal_mode=WAL")

        d.execute(
            """
            CREATE TABLE portals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portal_slug TEXT NOT NULL UNIQUE,
                portal_name TEXT NOT NULL,
                base_url TEXT,
                last_updated TEXT
            )
            """
        )

        d.execute(
            """
            CREATE TABLE tender_items (
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
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (portal_id) REFERENCES portals(id) ON DELETE CASCADE
            )
            """
        )

        d.execute("CREATE INDEX idx_portals_slug ON portals(portal_slug)")
        d.execute("CREATE INDEX idx_portals_name ON portals(portal_name)")
        d.execute("CREATE INDEX idx_ti_portal_id ON tender_items(portal_id)")
        d.execute("CREATE INDEX idx_ti_portal_slug ON tender_items(portal_slug)")
        d.execute("CREATE INDEX idx_ti_is_live ON tender_items(is_live)")
        d.execute("CREATE INDEX idx_ti_closing_at ON tender_items(closing_at)")
        d.execute("CREATE INDEX idx_ti_published_at ON tender_items(published_at)")
        d.execute("CREATE INDEX idx_ti_department_name ON tender_items(department_name)")

        s.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='portals'")
        if s.fetchone() is None:
            raise RuntimeError("Source DB missing v3 portals table")
        s.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tender_items'")
        if s.fetchone() is None:
            raise RuntimeError("Source DB missing v3 tender_items table")

        s.execute("SELECT portal_slug, portal_name, base_url, last_updated FROM portals ORDER BY id")
        portal_rows = [tuple(row) for row in s.fetchall()]
        d.executemany(
            """
            INSERT INTO portals (portal_slug, portal_name, base_url, last_updated)
            VALUES (?, ?, ?, ?)
            """,
            portal_rows,
        )

        s.execute(
            """
            SELECT
                portal_slug, tender_id_extracted, title_ref, department_name,
                published_at, closing_at, opening_date, organisation_chain,
                tender_url, status_url, estimated_cost_value, tender_status,
                is_live, state_name, district, city, tender_type, work_type,
                created_at, updated_at
            FROM tender_items
            ORDER BY id
            """
        )
        src_items = s.fetchall()

        d.execute("SELECT id, portal_slug FROM portals")
        portal_id_map = {str(r[1]): int(r[0]) for r in d.fetchall()}

        item_rows = []
        for row in src_items:
            slug = str(row["portal_slug"] or "")
            portal_id = portal_id_map.get(slug)
            if portal_id is None:
                continue
            item_rows.append(
                (
                    portal_id,
                    slug,
                    row["tender_id_extracted"],
                    row["title_ref"],
                    row["department_name"],
                    row["published_at"],
                    row["closing_at"],
                    row["opening_date"],
                    row["organisation_chain"],
                    row["tender_url"],
                    row["status_url"],
                    row["estimated_cost_value"],
                    row["tender_status"],
                    row["is_live"],
                    row["state_name"],
                    row["district"],
                    row["city"],
                    row["tender_type"],
                    row["work_type"],
                    row["created_at"],
                    row["updated_at"],
                )
            )

        d.executemany(
            """
            INSERT INTO tender_items (
                portal_id, portal_slug, tender_id_extracted, title_ref, department_name,
                published_at, closing_at, opening_date, organisation_chain,
                tender_url, status_url, estimated_cost_value, tender_status,
                is_live, state_name, district, city, tender_type, work_type,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            item_rows,
        )

        dst.commit()

        d.execute("SELECT COUNT(*) FROM portals")
        portal_count = int(d.fetchone()[0])
        d.execute("SELECT COUNT(*) FROM tender_items")
        item_count = int(d.fetchone()[0])
        return portal_count, item_count
    finally:
        src.close()
        dst.close()


def main() -> None:
    active = active_db_path()
    if not active.exists():
        raise FileNotFoundError(f"Active DB not found: {active}")

    archived = archive_path()
    temp_v3 = temp_v3_path()

    portal_count, item_count = create_v3_only_copy(active, temp_v3)

    shutil.copy2(active, archived)
    shutil.move(str(temp_v3), str(active))

    print(f"Archived mixed DB: {archived}")
    print(f"Promoted v3-only DB: {active}")
    print(f"Portals copied: {portal_count}")
    print(f"Tender items copied: {item_count}")


if __name__ == "__main__":
    main()
