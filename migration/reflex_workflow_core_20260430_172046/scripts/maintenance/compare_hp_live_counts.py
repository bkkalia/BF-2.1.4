from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

IST = timezone(timedelta(hours=5, minutes=30))

JSON_PATH = Path(r"g:\My Drive\0dev\t84\hp\temp_json_20260303_104837\tenders.json")
DB_PATH = Path(r"d:\Dev84\BF 2.1.4\database\blackforest_tenders.sqlite3")
PORTAL_NAME = "HP Tenders"


def parse_ist_dt(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None

    for fmt in (
        "%d-%b-%Y %I:%M %p",
        "%d/%b/%Y %I:%M %p",
        "%d-%m-%Y %I:%M %p",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(text, fmt)
            if fmt == "%Y-%m-%d":
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt.replace(tzinfo=IST)
        except ValueError:
            continue

    try:
        dt2 = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt2.tzinfo is None:
            return dt2.replace(tzinfo=IST)
        return dt2.astimezone(IST)
    except ValueError:
        return None


def is_live_ist(closing_raw: Any, now_ist: datetime) -> bool:
    dt = parse_ist_dt(closing_raw)
    if not dt:
        return True
    return dt >= now_ist


def load_json_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("tenders", "items", "data", "rows"):
            val = data.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def get_json_portal_value(row: dict[str, Any]) -> str:
    for key in ("portal_name", "Portal Name", "portal", "Portal", "source"):
        val = row.get(key)
        if val is not None:
            return str(val).strip()
    return ""


def get_json_closing_value(row: dict[str, Any]) -> Any:
    for key in ("closing_date", "Closing Date", "closing_at", "closingDate", "closing"):
        if key in row:
            return row.get(key)
    return None


def main() -> None:
    now_ist = datetime.now(IST)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute(
        """
        SELECT COUNT(*) AS c
        FROM tender_items ti
        JOIN portals p ON p.id = ti.portal_id
        WHERE p.portal_name = ?
        """,
        [PORTAL_NAME],
    )
    db_total = int(c.fetchone()["c"])

    c.execute(
        """
        SELECT COUNT(*) AS c
        FROM tender_items ti
        JOIN portals p ON p.id = ti.portal_id
        WHERE p.portal_name = ? AND ti.is_live = 1
        """,
        [PORTAL_NAME],
    )
    db_live = int(c.fetchone()["c"])
    conn.close()

    if not JSON_PATH.exists():
        print(f"JSON not found: {JSON_PATH}")
        print(f"DB {PORTAL_NAME}: total={db_total}, live={db_live}")
        return

    rows = load_json_rows(JSON_PATH)
    has_portal_field = any(bool(get_json_portal_value(r)) for r in rows)
    hp_rows = (
        [r for r in rows if get_json_portal_value(r).lower() == PORTAL_NAME.lower()]
        if has_portal_field
        else rows
    )
    json_total = len(hp_rows)
    json_live = sum(1 for r in hp_rows if is_live_ist(get_json_closing_value(r), now_ist))

    print(f"Now IST: {now_ist.strftime('%Y-%m-%d %H:%M:%S %z')}")
    print(f"JSON file: {JSON_PATH}")
    print(f"JSON {PORTAL_NAME}: total={json_total}, live={json_live}")
    print(f"DB   {PORTAL_NAME}: total={db_total}, live={db_live}")
    print(f"Diff live (DB-JSON): {db_live - json_live}")


if __name__ == "__main__":
    main()
