from __future__ import annotations

import sqlite3
import csv
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from typing import Any
import json


# IST = UTC+5:30 (Indian Standard Time used by all NIC portals)
_IST = timezone(timedelta(hours=5, minutes=30))


def _resolve_db_path() -> Path:
    env_path = os.getenv("TENDER_DB_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()

    # Prefer 'database/' (where the scraper writes), fall back to legacy 'data/' location
    candidates = [
        Path(__file__).resolve().parents[2] / "database" / "blackforest_tenders.sqlite3",
        Path(__file__).resolve().parents[2] / "data" / "blackforest_tenders.sqlite3",
        Path.cwd() / "database" / "blackforest_tenders.sqlite3",
        Path.cwd() / "data" / "blackforest_tenders.sqlite3",
        Path.cwd().parent / "database" / "blackforest_tenders.sqlite3",
        Path.cwd().parent / "data" / "blackforest_tenders.sqlite3",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


DB_PATH = _resolve_db_path()

# ---------------------------------------------------------------------------
# Thread-local persistent connection — avoids reopening SQLite on every query.
# SQLite context manager commits/rolls-back but does NOT close the connection,
# so reuse is safe across multiple with-statement calls on the same thread.
# ---------------------------------------------------------------------------
_db_local = threading.local()


# ---------------------------------------------------------------------------
# SQL expression: converts NIC portal date text "DD-Mon-YYYY HH:MM AM/PM"
# (e.g. "25-Feb-2026 03:00 PM") into an ISO-8601 date string "YYYY-MM-DD"
# so SQLite can compare it with DATE('now', '+330 minutes') (current IST date).
# Used in live/expired WHERE clauses and summary counts.
# ---------------------------------------------------------------------------
_NIC_DATE_COL = "ti.closing_date"  # default table alias used in most queries

def _nic_iso_expr(col: str = "ti.closing_date") -> str:
    """Return SQL expression yielding an ISO-8601 date from a NIC closing_date.
    Uses the pre-computed closing_date_iso column when available (fast index path),
    falls back to the CASE expression for compatibility."""
    if _has_closing_iso_column:
        # Map 'ti.closing_date' -> 'ti.closing_date_iso', 'closing_date' -> 'closing_date_iso'
        return col.replace("closing_date", "closing_date_iso")
    return _ISO_CASE_BODY.format(col=col)

# IST offset expressed as SQLite modifier string (UTC+05:30 = +330 minutes)
_IST_NOW_SQL = "DATE('now', '+330 minutes')"  # current date in IST

# Set to True by _ensure_search_indexes once closing_date_iso column is confirmed
_has_closing_iso_column: bool = False

# Shared CASE expression body (without table alias) used in trigger + UPDATE
_ISO_CASE_BODY = """
  CASE WHEN LENGTH(TRIM(COALESCE({col},'')))>=11
  THEN SUBSTR({col},8,4)||'-'||
    CASE UPPER(SUBSTR({col},4,3))
      WHEN 'JAN' THEN '01' WHEN 'FEB' THEN '02' WHEN 'MAR' THEN '03'
      WHEN 'APR' THEN '04' WHEN 'MAY' THEN '05' WHEN 'JUN' THEN '06'
      WHEN 'JUL' THEN '07' WHEN 'AUG' THEN '08' WHEN 'SEP' THEN '09'
      WHEN 'OCT' THEN '10' WHEN 'NOV' THEN '11' WHEN 'DEC' THEN '12'
      ELSE '00' END||'-'||SUBSTR({col},1,2)
  ELSE NULL END"""

# ---------------------------------------------------------------------------
# Performance: ensure critical indexes exist on first use.
# These are idempotent (IF NOT EXISTS) so safe to run every startup.
# ---------------------------------------------------------------------------
_indexes_ensured: bool = False


def _ensure_search_indexes() -> None:
    """Create missing read-performance indexes on the legacy tenders table.
    Also adds the closing_date_iso computed column + trigger if absent.
    Runs once per process; skips if already done or if DB is read-only."""
    global _indexes_ensured, _has_closing_iso_column
    if _indexes_ensured:
        return
    _indexes_ensured = True
    try:
        with _get_connection() as conn:
            c = conn.cursor()
            c.execute("PRAGMA journal_mode=WAL")

            # 1. Core portal_name index (already created on previous run, idempotent)
            c.execute("CREATE INDEX IF NOT EXISTS idx_tenders_portal_name ON tenders(portal_name)")

            # 2. Add closing_date_iso TEXT column (ISO date, pre-converted for indexing)
            try:
                c.execute("ALTER TABLE tenders ADD COLUMN closing_date_iso TEXT")
            except Exception:
                pass  # Already exists

            # 3. Bulk-populate from the CASE expression (only rows where NULL)
            iso_expr = _ISO_CASE_BODY.format(col="closing_date")
            c.execute(f"UPDATE tenders SET closing_date_iso = {iso_expr} WHERE closing_date_iso IS NULL")

            # 4. CREATE TRIGGER: keep closing_date_iso in sync on INSERT
            c.execute("DROP TRIGGER IF EXISTS tg_tenders_iso_ins")
            c.execute(f"""
                CREATE TRIGGER tg_tenders_iso_ins AFTER INSERT ON tenders
                BEGIN
                  UPDATE tenders SET closing_date_iso = {_ISO_CASE_BODY.format(col='NEW.closing_date')}
                  WHERE id = NEW.id AND closing_date_iso IS NULL;
                END
            """)
            # 5. CREATE TRIGGER: keep in sync on UPDATE of closing_date
            c.execute("DROP TRIGGER IF EXISTS tg_tenders_iso_upd")
            c.execute(f"""
                CREATE TRIGGER tg_tenders_iso_upd AFTER UPDATE OF closing_date ON tenders
                BEGIN
                  UPDATE tenders SET closing_date_iso = {_ISO_CASE_BODY.format(col='NEW.closing_date')}
                  WHERE id = NEW.id;
                END
            """)

            # 6. Compound covering index for portal + date range (the hot path)
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_tenders_portal_iso "
                "ON tenders(portal_name, closing_date_iso)"
            )
            # 7. Index on closing_date_iso alone for global live/expired counts
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_tenders_closing_iso "
                "ON tenders(closing_date_iso)"
            )
            # 8. Cover index: portal + sort-by-published date (legacy schema uses published_date)
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_tenders_portal_published "
                "ON tenders(portal_name, published_date)"
            )
            # 9. Drop the old raw-text closing_date index (wrong sort order, unused)
            c.execute("DROP INDEX IF EXISTS idx_tenders_closing_date")

            conn.commit()
            _has_closing_iso_column = True
    except Exception as _e:
        pass  # Read-only DB or locked — non-fatal


# ---------------------------------------------------------------------------
# Summary cache: live/expired/total counts change max once per scrape run.
# Cache them for 120 s so the 3×full-scan doesn't repeat on every keystroke.
# ---------------------------------------------------------------------------
import time as _time_mod

_summary_global_cache: dict[str, int] = {}
_summary_global_ts: float = 0.0
_SUMMARY_CACHE_TTL: float = 120.0  # seconds


def _get_global_counts() -> tuple[int, int, int]:
    """Return (total, live, expired) with 120-second cache."""
    global _summary_global_cache, _summary_global_ts
    now = _time_mod.monotonic()
    if _summary_global_cache and (now - _summary_global_ts) < _SUMMARY_CACHE_TTL:
        return (
            _summary_global_cache["total"],
            _summary_global_cache["live"],
            _summary_global_cache["expired"],
        )
    with _get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) AS n FROM tenders")
        total = int(c.fetchone()["n"])
        _iso = _nic_iso_expr("closing_date")  # uses column if available
        c.execute(
            f"SELECT COUNT(*) AS n FROM tenders "
            f"WHERE ({_iso} >= {_IST_NOW_SQL} OR {_iso} IS NULL)"
        )
        live = int(c.fetchone()["n"])
        expired = total - live
    _summary_global_cache = {"total": total, "live": live, "expired": expired}
    _summary_global_ts = now
    return total, live, expired



def _get_portal_categories() -> dict[str, str]:
    """Load portal categories from base_urls.csv.
    Returns mapping of portal_name -> category (Central/State/PSU).
    """
    categories = {}
    csv_path = Path(__file__).resolve().parents[2] / "base_urls.csv"
    
    if not csv_path.exists():
        return categories
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('Name', '').strip()
                keyword = row.get('Keyword', '').strip()
                
                # Categorize based on keyword
                if 'Central' in keyword or 'CPPP' in keyword or 'Defence' in keyword or 'NIC GePNIC' in keyword or 'PMGSY' in keyword:
                    category = 'Central'
                elif 'Limited' in keyword or 'Coal India' in keyword or 'Shipyard' in keyword or 'Corporation' in keyword:
                    category = 'PSU'
                else:
                    category = 'State'
                
                categories[name] = category
    except Exception as ex:
        print(f"Error loading portal categories: {ex}")
    
    return categories


def _get_portal_name_normalization() -> dict[str, str]:
    """Build a mapping from URL-slug style portal names to canonical display names.
    e.g. 'hptenders_gov_in' -> 'HP Tenders', 'jktenders_gov_in' -> 'JK Tenders'
    Derived by converting each BaseURL hostname to an underscore slug and mapping
    it to the portal's configured Name.
    """
    import re
    from urllib.parse import urlparse
    mapping: dict[str, str] = {}
    csv_path = Path(__file__).resolve().parents[2] / "base_urls.csv"
    if not csv_path.exists():
        return mapping
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('Name', '').strip()
                base_url = row.get('BaseURL', '').strip()
                if not name or not base_url:
                    continue
                host = urlparse(base_url).hostname or ''
                host = host.lower().replace('www.', '')
                slug = re.sub(r'[^a-z0-9]+', '_', host).strip('_')
                if slug:
                    mapping[slug] = name
    except Exception as ex:
        print(f"Error building portal name normalization: {ex}")
    return mapping


@dataclass
class TenderFilters:
    portal: str = "All"
    portal_group: str = "All"
    status: str = "All"
    state: str = "All"
    district: str = "All"
    city: str = "All"
    tender_type: str = "All"
    work_type: str = "All"
    from_date: str = ""
    to_date: str = ""
    min_amount: str = ""
    max_amount: str = ""
    search_query: str = ""
    search_logic: str = "OR"
    department_filter: str = ""
    department_logic: str = "OR"
    show_live_only: bool = False
    show_expired_only: bool = False
    show_live_recent: bool = False   # Live + expired within recent_days
    recent_days: int = 30            # How many days back "recent expired" looks


def _get_connection() -> sqlite3.Connection:
    conn: sqlite3.Connection | None = getattr(_db_local, "conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except Exception:
            _db_local.conn = None
    db_path_str = str(DB_PATH)
    try:
        conn = sqlite3.connect(db_path_str, check_same_thread=False)
    except sqlite3.OperationalError:
        uri = f"file:{Path(db_path_str).as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _db_local.conn = conn
    return conn


def _table_exists(table_name: str) -> bool:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", [table_name])
        return cursor.fetchone() is not None


def _is_v3_schema() -> bool:
    return _table_exists("portals") and _table_exists("tender_items")


# Ensure indexes on first module load (only for legacy schema — v3 has its own)
try:
    if not _is_v3_schema():
        _ensure_search_indexes()
except Exception:
    pass


def _parse_portal_datetime(value: str | None) -> datetime | None:
    """
    Parse portal datetime string as IST (Indian Standard Time).
    All NIC government portals use IST for tender dates/times.
    Returns timezone-aware datetime object for proper timezone conversion in browser.
    """
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%d-%b-%Y %I:%M %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt)
            # Mark as IST so browsers can convert to local timezone
            return dt.replace(tzinfo=_IST)
        except ValueError:
            continue
    return None


def _build_where(filters: TenderFilters) -> tuple[str, list[Any]]:
    clauses: list[str] = ["1=1"]
    params: list[Any] = []
    use_v3 = _is_v3_schema()

    # Live/Expired filter (applied first)
    if filters.show_live_only:
        if use_v3:
            clauses.append("ti.is_live = 1")
        else:
            iso = _nic_iso_expr("ti.closing_date")
            clauses.append(f"({iso} >= {_IST_NOW_SQL} OR {iso} IS NULL)")
    elif filters.show_expired_only:
        if use_v3:
            clauses.append("ti.is_live = 0")
        else:
            iso = _nic_iso_expr("ti.closing_date")
            clauses.append(f"({iso} IS NOT NULL AND {iso} < {_IST_NOW_SQL})")
    elif filters.show_live_recent:
        if use_v3:
            clauses.append(
                f"(ti.is_live = 1 OR "
                f"DATE(ti.closing_at) >= DATE({_IST_NOW_SQL}, '-{filters.recent_days} days'))"
            )
        else:
            iso = _nic_iso_expr("ti.closing_date")
            cutoff = f"DATE({_IST_NOW_SQL}, '-{filters.recent_days} days')"
            clauses.append(f"({iso} IS NULL OR {iso} >= {cutoff})")

    # Portal group filter
    if filters.portal_group and filters.portal_group != "All":
        portal_groups = _get_portal_group_mapping()
        if filters.portal_group in portal_groups:
            portals = portal_groups[filters.portal_group]
            if portals:
                placeholders = ",".join("?" * len(portals))
                if use_v3:
                    clauses.append(f"p.portal_slug IN ({placeholders})")
                else:
                    clauses.append(f"ti.portal_name IN ({placeholders})")
                params.extend(portals)

    # Individual portal filter (overrides group if both selected)
    if filters.portal and filters.portal != "All":
        clauses.append("p.portal_slug = ?" if use_v3 else "ti.portal_name = ?")
        params.append(filters.portal)

    # Status filter
    if filters.status and filters.status != "All":
        if use_v3:
            if filters.status == "Live":
                clauses.append("ti.is_live = 1")
            elif filters.status == "Archived":
                clauses.append("ti.is_live = 0")
            else:
                clauses.append("ti.tender_status = ?")
                params.append(filters.status)
        else:
            if filters.status == "Live":
                clauses.append("LOWER(COALESCE(ti.lifecycle_status, '')) = 'active'")
            elif filters.status == "Archived":
                clauses.append("LOWER(COALESCE(ti.lifecycle_status, '')) != 'active'")
            else:
                clauses.append("LOWER(COALESCE(ti.lifecycle_status, '')) = LOWER(?)")
                params.append(filters.status)

    if use_v3 and filters.state and filters.state != "All":
        clauses.append("ti.state_name = ?")
        params.append(filters.state)

    if use_v3 and filters.district and filters.district != "All":
        clauses.append("ti.district = ?")
        params.append(filters.district)

    if use_v3 and filters.city and filters.city != "All":
        clauses.append("ti.city = ?")
        params.append(filters.city)

    if use_v3 and filters.tender_type and filters.tender_type != "All":
        clauses.append("ti.tender_type = ?")
        params.append(filters.tender_type)

    if use_v3 and filters.work_type and filters.work_type != "All":
        clauses.append("ti.work_type = ?")
        params.append(filters.work_type)

    if use_v3 and filters.from_date:
        clauses.append("ti.published_at >= ?")
        params.append(f"{filters.from_date} 00:00:00")

    if use_v3 and filters.to_date:
        clauses.append("ti.published_at <= ?")
        params.append(f"{filters.to_date} 23:59:59")

    if use_v3 and filters.min_amount:
        try:
            clauses.append("ti.estimated_cost_value >= ?")
            params.append(float(filters.min_amount))
        except ValueError:
            pass

    if use_v3 and filters.max_amount:
        try:
            clauses.append("ti.estimated_cost_value <= ?")
            params.append(float(filters.max_amount))
        except ValueError:
            pass

    # Department filter with AND/OR logic
    if filters.department_filter:
        dept_terms = [term.strip() for term in filters.department_filter.split(",") if term.strip()]
        if dept_terms:
            dept_clauses = []
            for term in dept_terms:
                dept_clauses.append("ti.department_name LIKE ?")
                params.append(f"%{term}%")
            operator = " OR " if filters.department_logic == "OR" else " AND "
            clauses.append(f"({operator.join(dept_clauses)})")

    # Enhanced search with AND/OR logic
    if filters.search_query:
        search_terms = [term.strip() for term in filters.search_query.split(",") if term.strip()]
        if search_terms:
            term_clauses = []
            for term in search_terms:
                term_clauses.append(
                    """(
                        ti.title_ref LIKE ?
                        OR ti.department_name LIKE ?
                        OR ti.tender_id_extracted LIKE ?
                        OR ti.organisation_chain LIKE ?
                    )"""
                )
                search_pattern = f"%{term}%"
                params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
            operator = " OR " if filters.search_logic == "OR" else " AND "
            clauses.append(f"({operator.join(term_clauses)})")

    return " AND ".join(clauses), params


def _get_portal_group_mapping() -> dict[str, list[str]]:
    """Returns portal groups mapping. Customize based on your portal names."""
    return {
        "North India": ["delhi", "haryana", "punjab", "himachal", "uttarakhand", "jammu", "rajasthan"],
        "PSUs": ["psu", "ntpc", "ongc", "bhel", "sail", "coal", "railway"],
        "CPPP": ["cppp", "gem", "eprocure"],
        "State Portals": ["mp", "up", "bihar", "maharashtra", "gujarat", "karnataka", "kerala"],
        "Others": [],
    }


def _list_distinct(column: str, where: str = "1=1", params: list[Any] | None = None) -> list[str]:
    params = params or []
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT DISTINCT {column}
            FROM tender_items ti
            WHERE {where} AND {column} IS NOT NULL AND TRIM({column}) != ''
            ORDER BY {column}
            """,
            params,
        )
        return [str(row[column]) for row in cursor.fetchall() if row[column]]


def get_portal_options() -> list[str]:
    with _get_connection() as conn:
        cursor = conn.cursor()
        if _is_v3_schema():
            cursor.execute(
                """
                SELECT portal_slug
                FROM portals
                ORDER BY portal_name
                """
            )
            return [str(row["portal_slug"]) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT DISTINCT portal_name
            FROM tenders
            WHERE portal_name IS NOT NULL AND TRIM(portal_name) != ''
            ORDER BY portal_name
            """
        )
        return [str(row["portal_name"]) for row in cursor.fetchall()]


def get_portal_statistics(days_filter: int = 0) -> list[dict[str, Any]]:
    """Get statistics for all portals including total, live, expired counts and last updated.
    
    Args:
        days_filter: If > 0, only include portals updated in last X days (0 = all portals)
    """
    with _get_connection() as conn:
        cursor = conn.cursor()
        
        if _is_v3_schema():
            # V3 schema with portals and tender_items tables
            date_filter = ""
            if days_filter > 0:
                date_filter = f"AND p.last_updated >= date('now', '-{days_filter} days')"
            
            query = f"""
                SELECT 
                    p.portal_slug,
                    p.portal_name,
                    p.base_url,
                    p.last_updated,
                    COUNT(ti.id) as total_tenders,
                    SUM(CASE WHEN ti.is_live = 1 THEN 1 ELSE 0 END) as live_tenders,
                    SUM(CASE WHEN ti.is_live = 0 THEN 1 ELSE 0 END) as expired_tenders
                FROM portals p
                LEFT JOIN tender_items ti ON p.portal_slug = ti.portal_slug
                WHERE 1=1 {date_filter}
                GROUP BY p.portal_slug, p.portal_name, p.base_url, p.last_updated
                ORDER BY p.portal_name
            """
        else:
            # Legacy schema - join with runs table to get timestamps and base_url.
            # FIX: use COALESCE(completed_at, started_at) so in-progress/failed runs
            #      still show a meaningful date.
            # FIX: derive live/expired from closing_date (scraper only stores active
            #      tenders so lifecycle_status is always 'active' and useless here).
            days_having = ""
            if days_filter > 0:
                days_having = f"""
                    HAVING (SELECT MAX(COALESCE(completed_at, started_at))
                            FROM runs WHERE portal_name = t.portal_name)
                           >= datetime('now', '-{days_filter} days')
                """
            
            # Build the NIC date -> ISO CASE expression for the tenders table
            _cd_iso = _nic_iso_expr("t.closing_date")
            query = f"""
                SELECT 
                    t.portal_name as portal_slug,
                    t.portal_name,
                    (SELECT base_url FROM runs
                     WHERE portal_name = t.portal_name
                     ORDER BY COALESCE(completed_at, started_at) DESC LIMIT 1) as base_url,
                    (SELECT MAX(COALESCE(completed_at, started_at)) FROM runs
                     WHERE portal_name = t.portal_name) as last_updated,
                    COUNT(*) as total_tenders,
                    SUM(CASE
                        WHEN ({_cd_iso}) >= {_IST_NOW_SQL} THEN 1
                        WHEN ({_cd_iso}) IS NULL THEN 1
                        ELSE 0 END) as live_tenders,
                    SUM(CASE
                        WHEN ({_cd_iso}) IS NOT NULL
                             AND ({_cd_iso}) < {_IST_NOW_SQL} THEN 1
                        ELSE 0 END) as expired_tenders
                FROM tenders t
                WHERE t.portal_name IS NOT NULL AND TRIM(t.portal_name) != ''
                GROUP BY t.portal_name
                {days_having}
                ORDER BY t.portal_name
            """
        
        cursor.execute(query)
        raw_rows = cursor.fetchall()
        
        categories = _get_portal_categories()
        name_norm = _get_portal_name_normalization()  # slug -> canonical name

        # Build merged results keyed by canonical portal name
        merged: dict[str, dict[str, Any]] = {}
        
        for row in raw_rows:
            portal_name_raw = str(row["portal_name"] or "")
            last_updated = str(row["last_updated"] or "")
            
            # Normalize slug-style names (e.g. "hptenders_gov_in" -> "HP Tenders")
            canonical_name = name_norm.get(portal_name_raw, portal_name_raw)
            
            # Calculate days since update
            days_since_update = -1
            if last_updated:
                try:
                    if 'T' in last_updated or ' ' in last_updated:
                        update_time = datetime.fromisoformat(last_updated.replace(' ', 'T').split('.')[0])
                    else:
                        update_time = datetime.strptime(last_updated, '%Y-%m-%d')
                    days_since_update = (datetime.now() - update_time).days
                except Exception:
                    days_since_update = -1
            
            entry: dict[str, Any] = {
                "portal_slug": str(row["portal_slug"] or ""),
                "portal_name": canonical_name,
                "base_url": str(row["base_url"] or ""),
                "last_updated": last_updated,
                "total_tenders": int(row["total_tenders"] or 0),
                "live_tenders": int(row["live_tenders"] or 0),
                "expired_tenders": int(row["expired_tenders"] or 0),
                "category": categories.get(canonical_name, categories.get(portal_name_raw, "State")),
                "days_since_update": days_since_update,
            }
            
            if canonical_name in merged:
                # Merge: sum counts, keep most recent date
                existing = merged[canonical_name]
                existing["total_tenders"] += entry["total_tenders"]
                existing["live_tenders"] += entry["live_tenders"]
                existing["expired_tenders"] += entry["expired_tenders"]
                # Keep whichever last_updated is more recent
                if entry["last_updated"] > existing["last_updated"]:
                    existing["last_updated"] = entry["last_updated"]
                    existing["days_since_update"] = entry["days_since_update"]
                    existing["base_url"] = entry["base_url"]
            else:
                merged[canonical_name] = entry
        
        return list(merged.values())


def get_state_options() -> list[str]:
    if not _is_v3_schema():
        return []
    return _list_distinct("state_name")


def get_district_options(state_name: str = "All") -> list[str]:
    if not _is_v3_schema():
        return []
    if state_name and state_name != "All":
        return _list_distinct("district", "state_name = ?", [state_name])
    return _list_distinct("district")


def get_city_options(state_name: str = "All", district: str = "All") -> list[str]:
    if not _is_v3_schema():
        return []
    where_parts = ["1=1"]
    params: list[Any] = []
    if state_name and state_name != "All":
        where_parts.append("state_name = ?")
        params.append(state_name)
    if district and district != "All":
        where_parts.append("district = ?")
        params.append(district)
    return _list_distinct("city", " AND ".join(where_parts), params)


def get_tender_type_options() -> list[str]:
    if not _is_v3_schema():
        return []
    return _list_distinct("tender_type")


def get_work_type_options() -> list[str]:
    if not _is_v3_schema():
        return []
    return _list_distinct("work_type")


def get_summary(filters: TenderFilters) -> dict[str, Any]:
    where_sql, where_params = _build_where(filters)
    use_v3 = _is_v3_schema()

    with _get_connection() as conn:
        cursor = conn.cursor()

        if use_v3:
            cursor.execute("SELECT COUNT(*) AS c FROM tender_items")
            total_tenders = int(cursor.fetchone()["c"])
            cursor.execute("SELECT COUNT(*) AS c FROM tender_items WHERE is_live = 1")
            live_tenders = int(cursor.fetchone()["c"])
            cursor.execute("SELECT COUNT(*) AS c FROM tender_items WHERE is_live = 0")
            expired_tenders = int(cursor.fetchone()["c"])
        else:
            # Cached 120-second global counts — avoids 3×full-table CASE scan
            total_tenders, live_tenders, expired_tenders = _get_global_counts()

        if use_v3:
            cursor.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM tender_items ti
                JOIN portals p ON p.id = ti.portal_id
                WHERE {where_sql}
                """,
                where_params,
            )
            filtered_results = int(cursor.fetchone()["c"])

            cursor.execute(
                f"""
                SELECT COUNT(DISTINCT ti.department_name) AS c
                FROM tender_items ti
                JOIN portals p ON p.id = ti.portal_id
                WHERE {where_sql} AND ti.department_name IS NOT NULL AND TRIM(ti.department_name) != ''
                """,
                where_params,
            )
            departments = int(cursor.fetchone()["c"])

            cursor.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM tender_items ti
                JOIN portals p ON p.id = ti.portal_id
                WHERE {where_sql} AND ti.is_live = 1 AND DATE(ti.closing_at) = DATE('now')
                """,
                where_params,
            )
            due_today = int(cursor.fetchone()["c"])

            cursor.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM tender_items ti
                JOIN portals p ON p.id = ti.portal_id
                WHERE {where_sql}
                  AND ti.is_live = 1
                  AND DATE(ti.closing_at) > DATE('now')
                  AND DATE(ti.closing_at) <= DATE('now', '+3 day')
                """,
                where_params,
            )
            due_3_days = int(cursor.fetchone()["c"])

            cursor.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM tender_items ti
                JOIN portals p ON p.id = ti.portal_id
                WHERE {where_sql}
                  AND ti.is_live = 1
                  AND DATE(ti.closing_at) > DATE('now')
                  AND DATE(ti.closing_at) <= DATE('now', '+7 day')
                """,
                where_params,
            )
            due_7_days = int(cursor.fetchone()["c"])

            cursor.execute("SELECT COUNT(*) AS c FROM portals")
            data_sources = int(cursor.fetchone()["c"])
        else:
            # SINGLE aggregation: replaces 3 separate scans → 1 pass over the filtered set.
            # filtered_results + departments + due_today/3/7 all computed together.
            _cd_iso = _nic_iso_expr("ti.closing_date")
            cursor.execute(
                f"""
                SELECT
                  COUNT(*) AS filtered_results,
                  COUNT(DISTINCT CASE WHEN ti.department_name IS NOT NULL
                                           AND TRIM(ti.department_name) != ''
                                      THEN ti.department_name END) AS departments,
                  SUM(CASE WHEN ({_cd_iso}) = {_IST_NOW_SQL} THEN 1 ELSE 0 END) AS due_today,
                  SUM(CASE WHEN ({_cd_iso}) > {_IST_NOW_SQL}
                           AND ({_cd_iso}) <= DATE({_IST_NOW_SQL}, '+3 days') THEN 1 ELSE 0 END) AS due_3,
                  SUM(CASE WHEN ({_cd_iso}) > {_IST_NOW_SQL}
                           AND ({_cd_iso}) <= DATE({_IST_NOW_SQL}, '+7 days') THEN 1 ELSE 0 END) AS due_7
                FROM tenders ti
                WHERE {where_sql}
                """,
                where_params,
            )
            _agg = cursor.fetchone()
            filtered_results = int(_agg["filtered_results"])
            departments = int(_agg["departments"] or 0)
            due_today = int(_agg["due_today"] or 0)
            due_3_days = int(_agg["due_3"] or 0)
            due_7_days = int(_agg["due_7"] or 0)

            cursor.execute(
                """
                SELECT COUNT(DISTINCT portal_name) AS c
                FROM tenders
                WHERE portal_name IS NOT NULL AND TRIM(portal_name) != ''
                """
            )
            data_sources = int(cursor.fetchone()["c"])

    match_percent = (filtered_results / total_tenders * 100.0) if total_tenders else 0.0
    return {
        "total_tenders": total_tenders,
        "live_tenders": live_tenders,
        "expired_tenders": expired_tenders,
        "filtered_results": filtered_results,
        "match_percent": f"{match_percent:.1f}%",
        "departments": departments,
        "due_today": due_today,
        "due_3_days": due_3_days,
        "due_7_days": due_7_days,
        "data_sources": data_sources,
    }


def get_recommendations(filters: TenderFilters) -> list[dict[str, str]]:
    where_sql, where_params = _build_where(filters)
    recommendations: list[dict[str, str]] = []
    use_v3 = _is_v3_schema()

    with _get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            (
                f"""
                SELECT p.portal_name AS label, COUNT(*) AS c
                FROM tender_items ti
                JOIN portals p ON p.id = ti.portal_id
                WHERE {where_sql}
                GROUP BY p.portal_name
                ORDER BY c DESC
                LIMIT 1
                """
                if use_v3
                else f"""
                SELECT ti.portal_name AS label, COUNT(*) AS c
                FROM tenders ti
                WHERE {where_sql}
                GROUP BY ti.portal_name
                ORDER BY c DESC
                LIMIT 1
                """
            ),
            where_params,
        )
        top_portal = cursor.fetchone()
        if top_portal:
            recommendations.append(
                {
                    "title": "Top Portal",
                    "value": f"{top_portal['label']} ({top_portal['c']})",
                }
            )

        if use_v3:
            cursor.execute(
                f"""
                SELECT ti.state_name AS label, COUNT(*) AS c
                FROM tender_items ti
                JOIN portals p ON p.id = ti.portal_id
                WHERE {where_sql} AND ti.state_name IS NOT NULL AND TRIM(ti.state_name) != ''
                GROUP BY ti.state_name
                ORDER BY c DESC
                LIMIT 1
                """,
                where_params,
            )
            top_state = cursor.fetchone()
            if top_state:
                recommendations.append(
                    {
                        "title": "Top State",
                        "value": f"{top_state['label']} ({top_state['c']})",
                    }
                )

            cursor.execute(
                f"""
                SELECT ti.work_type AS label, COUNT(*) AS c
                FROM tender_items ti
                JOIN portals p ON p.id = ti.portal_id
                WHERE {where_sql} AND ti.work_type IS NOT NULL AND TRIM(ti.work_type) != ''
                GROUP BY ti.work_type
                ORDER BY c DESC
                LIMIT 1
                """,
                where_params,
            )
            top_work_type = cursor.fetchone()
            if top_work_type:
                recommendations.append(
                    {
                        "title": "Top Work Type",
                        "value": f"{top_work_type['label']} ({top_work_type['c']})",
                    }
                )

            cursor.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM tender_items ti
                JOIN portals p ON p.id = ti.portal_id
                WHERE {where_sql}
                  AND ti.is_live = 1
                  AND DATE(ti.closing_at) <= DATE('now', '+3 day')
                  AND DATE(ti.closing_at) >= DATE('now')
                """,
                where_params,
            )
            urgent_count = int(cursor.fetchone()["c"])
        else:
            cursor.execute(
                f"""
                SELECT ti.department_name AS label, COUNT(*) AS c
                FROM tenders ti
                WHERE {where_sql} AND ti.department_name IS NOT NULL AND TRIM(ti.department_name) != ''
                GROUP BY ti.department_name
                ORDER BY c DESC
                LIMIT 1
                """,
                where_params,
            )
            top_department = cursor.fetchone()
            if top_department:
                recommendations.append(
                    {
                        "title": "Top Department",
                        "value": f"{top_department['label']} ({top_department['c']})",
                    }
                )

            cursor.execute(
                f"""
                SELECT ti.lifecycle_status, ti.closing_date
                FROM tenders ti
                WHERE {where_sql}
                """,
                where_params,
            )
            urgent_count = 0
            today = datetime.now().date()
            for row in cursor.fetchall():
                if str(row["lifecycle_status"] or "").lower() != "active":
                    continue
                closing_dt = _parse_portal_datetime(row["closing_date"])
                if not closing_dt:
                    continue
                if 0 <= (closing_dt.date() - today).days <= 3:
                    urgent_count += 1

        recommendations.append(
            {
                "title": "Urgent Closures",
                "value": f"{urgent_count} tenders close in 3 days",
            }
        )

    return recommendations


def search_tenders(
    filters: TenderFilters,
    page: int = 1,
    page_size: int = 25,
    sort_by: str = "published_at",
    sort_order: str = "desc",
    prefetched_count: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    where_sql, where_params = _build_where(filters)
    use_v3 = _is_v3_schema()

    sort_map = {
        "published_at": "ti.published_at" if use_v3 else "ti.published_date",
        "closing_at": "ti.closing_at" if use_v3 else "ti.closing_date",
        "estimated_cost_value": "ti.estimated_cost_value" if use_v3 else "ti.emd_amount_numeric",
        "portal_name": "p.portal_name" if use_v3 else "ti.portal_name",
        "department_name": "ti.department_name",
    }
    sort_column = sort_map.get(sort_by, "ti.published_at" if use_v3 else "ti.published_date")
    order = "ASC" if str(sort_order).lower() == "asc" else "DESC"

    offset = max(page - 1, 0) * page_size

    with _get_connection() as conn:
        cursor = conn.cursor()

        if prefetched_count is not None:
            total_count = prefetched_count
        else:
            cursor.execute(
                (
                    f"""
                    SELECT COUNT(*) AS c
                    FROM tender_items ti
                    JOIN portals p ON p.id = ti.portal_id
                    WHERE {where_sql}
                    """
                    if use_v3
                    else f"""
                    SELECT COUNT(*) AS c
                    FROM tenders ti
                    WHERE {where_sql}
                    """
                ),
                where_params,
            )
            total_count = int(cursor.fetchone()["c"])

        cursor.execute(
            (
                f"""
                SELECT
                    ti.id,
                    p.portal_name,
                    ti.tender_id_extracted,
                    ti.title_ref,
                    ti.department_name,
                    ti.published_at,
                    ti.closing_at,
                    ti.estimated_cost_value,
                    ti.tender_status,
                    ti.state_name,
                    ti.district,
                    ti.city,
                    COALESCE(ti.tender_url, '') AS tender_url,
                    COALESCE(ti.status_url, '') AS status_url
                FROM tender_items ti
                JOIN portals p ON p.id = ti.portal_id
                WHERE {where_sql}
                ORDER BY {sort_column} {order}
                LIMIT ? OFFSET ?
                """
                if use_v3
                else f"""
                SELECT
                    ti.id,
                    ti.portal_name AS portal_name,
                    ti.tender_id_extracted,
                    ti.title_ref,
                    ti.department_name,
                    ti.published_date AS published_at,
                    ti.closing_date AS closing_at,
                    ti.emd_amount_numeric AS estimated_cost_value,
                    ti.lifecycle_status AS tender_status,
                    '' AS state_name,
                    '' AS district,
                    '' AS city,
                    COALESCE(ti.direct_url, '') AS tender_url,
                    COALESCE(ti.status_url, '') AS status_url
                FROM tenders ti
                WHERE {where_sql}
                ORDER BY {sort_column} {order}
                LIMIT ? OFFSET ?
                """
            ),
            [*where_params, page_size, offset],
        )
        rows = cursor.fetchall()

    return [dict(row) for row in rows], total_count


def export_tenders_by_portal(filters: TenderFilters, expired_days: int = 30) -> dict[str, list[dict[str, Any]]]:
    """
    Export tenders grouped by portal for Excel export.
    Returns dict with portal_name as key and list of tender dicts as value.
    Columns match: Department Name, S.No, e-Published Date, Closing Date, Opening Date,
                  Organisation Chain, Title and Ref.No./Tender ID, Tender ID (Extracted),
                  Direct URL, Status URL
    """
    use_v3 = _is_v3_schema()
    
    # Build WHERE clause with expired tenders option
    where_clauses: list[str] = ["1=1"]
    params: list[Any] = []
    
    # Handle expired tenders (include if within expired_days)
    if filters.show_live_only:
        if use_v3:
            where_clauses.append("ti.is_live = 1")
        else:
            where_clauses.append("LOWER(COALESCE(ti.lifecycle_status, '')) = 'active'")
    elif expired_days > 0:
        # Include expired tenders from last X days
        if use_v3:
            where_clauses.append(f"""
                (ti.is_live = 1 OR 
                 julianday('now') - julianday(ti.closing_at) <= {expired_days})
            """)
        else:
            where_clauses.append(f"""
                (LOWER(COALESCE(ti.lifecycle_status, '')) = 'active' OR
                 julianday('now') - julianday(ti.closing_date) <= {expired_days})
            """)
    
    # Apply other filters
    if filters.portal_group and filters.portal_group != "All":
        group_mapping = _get_portal_group_mapping()
        portals_in_group = group_mapping.get(filters.portal_group, [])
        if portals_in_group:
            placeholders = ",".join("?" * len(portals_in_group))
            if use_v3:
                where_clauses.append(f"p.portal_slug IN ({placeholders})")
            else:
                where_clauses.append(f"LOWER(ti.portal_name) IN ({placeholders})")
            params.extend([p.lower() for p in portals_in_group])
    
    if filters.portal and filters.portal != "All":
        if use_v3:
            where_clauses.append("p.portal_slug = ?")
        else:
            where_clauses.append("ti.portal_name = ?")
        params.append(filters.portal)
    
    if filters.search_query:
        search_terms = [term.strip() for term in filters.search_query.split(",") if term.strip()]
        if search_terms:
            term_clauses = []
            for term in search_terms:
                term_clauses.append(
                    """(
                        ti.title_ref LIKE ?
                        OR ti.department_name LIKE ?
                        OR ti.tender_id_extracted LIKE ?
                        OR ti.organisation_chain LIKE ?
                    )"""
                )
                search_pattern = f"%{term}%"
                params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
            operator = " OR " if filters.search_logic == "OR" else " AND "
            where_clauses.append(f"({operator.join(term_clauses)})")
    
    if filters.department_filter:
        dept_terms = [term.strip() for term in filters.department_filter.split(",") if term.strip()]
        if dept_terms:
            dept_clauses = []
            for term in dept_terms:
                dept_clauses.append("ti.department_name LIKE ?")
                params.append(f"%{term}%")
            operator = " OR " if filters.department_logic == "OR" else " AND "
            where_clauses.append(f"({operator.join(dept_clauses)})")
    
    where_sql = " AND ".join(where_clauses)
    
    # Query all matching tenders
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            (
                f"""
                SELECT
                    p.portal_name,
                    ti.department_name,
                    ti.published_at AS e_published_date,
                    ti.closing_at AS closing_date,
                    ti.opening_date,
                    ti.organisation_chain,
                    ti.title_ref AS title_and_ref,
                    ti.tender_id_extracted,
                    COALESCE(ti.tender_url, '') AS direct_url,
                    COALESCE(ti.status_url, '') AS status_url
                FROM tender_items ti
                JOIN portals p ON p.id = ti.portal_id
                WHERE {where_sql}
                ORDER BY p.portal_name, ti.closing_at
                """
                if use_v3
                else f"""
                SELECT
                    ti.portal_name,
                    ti.department_name,
                    ti.published_date AS e_published_date,
                    ti.closing_date AS closing_date,
                    '' AS opening_date,
                    ti.organization_chain AS organisation_chain,
                    ti.title_ref AS title_and_ref,
                    ti.tender_id_extracted,
                    COALESCE(ti.direct_url, '') AS direct_url,
                    COALESCE(ti.status_url, '') AS status_url
                FROM tenders ti
                WHERE {where_sql}
                ORDER BY ti.portal_name, ti.closing_date
                """
            ),
            params,
        )
        rows = cursor.fetchall()
    
    # Group by portal
    portals_dict: dict[str, list[dict[str, Any]]] = {}
    for idx, row in enumerate(rows, start=1):
        portal = str(row["portal_name"])
        if portal not in portals_dict:
            portals_dict[portal] = []
        
        # Format data to match Excel columns
        tender_dict = {
            "Department Name": row["department_name"] or "",
            "S.No": idx if portal not in portals_dict else len(portals_dict[portal]) + 1,
            "e-Published Date": row["e_published_date"] or "",
            "Closing Date": row["closing_date"] or "",
            "Opening Date": row["opening_date"] or "",
            "Organisation Chain": row["organisation_chain"] or "",
            "Title and Ref.No./Tender ID": row["title_and_ref"] or "",
            "Tender ID (Extracted)": row["tender_id_extracted"] or "",
            "Direct URL": row["direct_url"] or "",
            "Status URL": row["status_url"] or "",
        }
        portals_dict[portal].append(tender_dict)
    
    # Renumber S.No for each portal
    for portal_data in portals_dict.values():
        for idx, tender in enumerate(portal_data, start=1):
            tender["S.No"] = idx
    
    return portals_dict

def portal_url_to_filename(base_url: str, portal_name: str) -> str:
    """Convert portal base URL to filename format.
    
    Examples:
        https://eproc.punjab.gov.in/nicgep/app → eproc_punjab_gov_in
        https://govtprocurement.delhi.gov.in/nicgep/app → govtprocurement_delhi_gov_in
        https://jktenders.gov.in/nicgep/app → jktenders_gov_in
    """
    if not base_url:
        # Fallback to portal name if no base_url
        return portal_name.lower().replace(" ", "_").replace("-", "_")
    
    # Extract domain from URL
    import re
    domain_match = re.search(r'https?://([^/]+)', base_url)
    if not domain_match:
        return portal_name.lower().replace(" ", "_").replace("-", "_")
    
    domain = domain_match.group(1)
    # Replace dots with underscores, remove www
    filename = domain.replace("www.", "").replace(".", "_")
    return filename


def export_portal_data(
    portal_slug: str,
    portal_name: str,
    base_url: str,
    expired_days: int = 30,
    live_only: bool = False
) -> list[dict[str, Any]]:
    """Export tender data for a specific portal.
    
    Args:
        portal_slug: Portal identifier
        portal_name: Display name
        base_url: Portal base URL (for filename generation)
        expired_days: Days of expired tenders to include (0 = none, live_only must be False)
        live_only: If True, only export live tenders
    
    Returns:
        List of tender dictionaries with proper column names
    """
    filters = TenderFilters(
        portal=portal_slug,
        show_live_only=live_only,
    )
    
    # Use existing export function
    portals_data = export_tenders_by_portal(filters, expired_days)
    
    # Return data for this specific portal
    return portals_data.get(portal_name, [])


def log_export_history(
    export_type: str,
    portals: list[str],
    total_tenders: int,
    file_count: int,
    export_dir: str,
    settings: dict[str, Any]
) -> None:
    """Log export history to JSON file.
    
    Args:
        export_type: Type of export (e.g., 'selected_portals', 'category')
        portals: List of portal names exported
        total_tenders: Total number of tenders exported
        file_count: Number of files created
        export_dir: Export directory path
        settings: Export settings (live_only, expired_days, etc.)
    """
    history_file = Path("Portal_Exports") / "export_history.json"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing history
    history = []
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except:
            history = []
    
    # Add new entry
    entry = {
        "timestamp": datetime.now().isoformat(),
        "export_type": export_type,
        "portals": portals,
        "total_tenders": total_tenders,
        "file_count": file_count,
        "export_dir": export_dir,
        "settings": settings,
    }
    history.append(entry)
    
    # Keep only last 100 entries
    history = history[-100:]
    
    # Save history
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)


def get_export_history(limit: int = 20) -> list[dict[str, Any]]:
    """Get export history entries.
    
    Args:
        limit: Maximum number of entries to return
    
    Returns:
        List of export history entries (most recent first)
    """
    history_file = Path("Portal_Exports") / "export_history.json"
    
    if not history_file.exists():
        return []
    
    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        return list(reversed(history[-limit:]))
    except:
        return []


def get_tender_count(filters: TenderFilters) -> int:
    """Get total count of tenders matching filters.
    
    Args:
        filters: TenderFilters object with filter criteria
    
    Returns:
        int: Total number of matching tenders
    """
    where_sql, where_params = _build_where(filters)
    use_v3 = _is_v3_schema()
    
    with _get_connection() as conn:
        cursor = conn.cursor()
        
        if use_v3:
            query = f"""
                SELECT COUNT(*) as count
                FROM tender_items ti
                JOIN portals p ON p.id = ti.portal_id
                WHERE {where_sql}
            """
        else:
            query = f"""
                SELECT COUNT(*) as count
                FROM tenders ti
                WHERE {where_sql}
            """
        
        cursor.execute(query, where_params)
        result = cursor.fetchone()
        return int(result["count"]) if result else 0


def get_tender_data_paginated(filters: TenderFilters, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """Get paginated tender data for data grid display.
    
    Returns RAW database values without any text processing or formatting.
    This allows users to see exactly how data is stored in the database.
    
    Args:
        filters: TenderFilters object with filter criteria
        limit: Number of records to return
        offset: Number of records to skip
    
    Returns:
        List of tender data dictionaries with raw values
    """
    where_sql, where_params = _build_where(filters)
    use_v3 = _is_v3_schema()
    
    with _get_connection() as conn:
        cursor = conn.cursor()
        
        if use_v3:
            query = f"""
                SELECT 
                    p.portal_name,
                    ti.tender_id_extracted,
                    ti.title_ref,
                    ti.department_name,
                    ti.organization_chain as organisation_chain,
                    '' as serial_no,
                    ti.published_at as published_date,
                    ti.opening_at as opening_date,
                    ti.closing_at as closing_date,
                    ti.emd_amount_raw as emd_amount,
                    ti.estimated_cost_raw as estimated_cost,
                    CASE WHEN ti.is_live = 1 THEN 'Live' ELSE 'Expired' END as lifecycle_status,
                    ti.tender_status,
                    ti.state_name,
                    ti.district,
                    ti.city,
                    ti.pincode,
                    ti.location_text,
                    ti.tender_type,
                    ti.work_type,
                    ti.payment_type,
                    ti.direct_url,
                    ti.status_url,
                    CAST(ti.is_live AS TEXT) as is_live,
                    CAST(ti.source_run_id AS TEXT) as run_id,
                    ti.first_seen_at,
                    ti.last_seen_at
                FROM tender_items ti
                JOIN portals p ON p.id = ti.portal_id
                WHERE {where_sql}
                ORDER BY ti.published_at DESC
                LIMIT ? OFFSET ?
            """
        else:
            query = f"""
                SELECT 
                    ti.portal_name,
                    ti.tender_id_extracted,
                    ti.title_ref,
                    ti.department_name,
                    ti.organisation_chain,
                    ti.serial_no,
                    ti.published_date,
                    ti.opening_date,
                    ti.closing_date,
                    ti.emd_amount,
                    '' as estimated_cost,
                    ti.lifecycle_status,
                    ti.lifecycle_status as tender_status,
                    '' as state_name,
                    '' as district,
                    '' as city,
                    '' as pincode,
                    '' as location_text,
                    '' as tender_type,
                    '' as work_type,
                    '' as payment_type,
                    ti.direct_url,
                    ti.status_url,
                    CASE WHEN ti.lifecycle_status = 'active' THEN '1' ELSE '0' END as is_live,
                    CAST(ti.run_id AS TEXT) as run_id,
                    '' as first_seen_at,
                    '' as last_seen_at
                FROM tenders ti
                WHERE {where_sql}
                ORDER BY ti.published_date DESC
                LIMIT ? OFFSET ?
            """
        
        cursor.execute(query, where_params + [limit, offset])
        results = []
        
        for row in cursor.fetchall():
            # Display RAW database values without any processing
            # This allows users to see exactly how data is stored
            
            results.append({
                "portal_name": str(row["portal_name"] or ""),
                "tender_id_extracted": str(row["tender_id_extracted"] or ""),
                "title_ref": str(row["title_ref"] or ""),
                "department_name": str(row["department_name"] or ""),
                "organisation_chain": str(row["organisation_chain"] or ""),
                "serial_no": str(row["serial_no"] or ""),
                "published_date": str(row["published_date"] or ""),
                "opening_date": str(row["opening_date"] or ""),
                "closing_date": str(row["closing_date"] or ""),
                "emd_amount": str(row["emd_amount"] or ""),
                "estimated_cost": str(row["estimated_cost"] or ""),
                "lifecycle_status": str(row["lifecycle_status"] or ""),
                "tender_status": str(row["tender_status"] or ""),
                "state_name": str(row["state_name"] or ""),
                "district": str(row["district"] or ""),
                "city": str(row["city"] or ""),
                "pincode": str(row["pincode"] or ""),
                "location_text": str(row["location_text"] or ""),
                "tender_type": str(row["tender_type"] or ""),
                "work_type": str(row["work_type"] or ""),
                "payment_type": str(row["payment_type"] or ""),
                "direct_url": str(row["direct_url"] or ""),
                "status_url": str(row["status_url"] or ""),
                "is_live": str(row["is_live"] or ""),
                "run_id": str(row["run_id"] or ""),
                "first_seen_at": str(row["first_seen_at"] or ""),
                "last_seen_at": str(row["last_seen_at"] or ""),
            })
        
        return results


def get_database_statistics() -> dict[str, int]:
    """Get database statistics for schema visualization.
    
    Returns:
        Dictionary with database statistics
    """
    use_v3 = _is_v3_schema()
    
    with _get_connection() as conn:
        cursor = conn.cursor()
        
        # Total records
        if use_v3:
            cursor.execute("SELECT COUNT(*) as count FROM tender_items")
        else:
            cursor.execute("SELECT COUNT(*) as count FROM tenders")
        total_records = int(cursor.fetchone()["count"])
        
        # Active records
        if use_v3:
            cursor.execute("SELECT COUNT(*) as count FROM tender_items WHERE is_live = 1")
        else:
            cursor.execute("SELECT COUNT(*) as count FROM tenders WHERE LOWER(COALESCE(lifecycle_status, '')) = 'active'")
        active_records = int(cursor.fetchone()["count"])
        
        # Portal count
        if use_v3:
            cursor.execute("SELECT COUNT(DISTINCT portal_id) as count FROM tender_items")
        else:
            cursor.execute("SELECT COUNT(DISTINCT portal_name) as count FROM tenders")
        portal_count = int(cursor.fetchone()["count"])
        
        return {
            "total_records": total_records,
            "active_records": active_records,
            "portal_count": portal_count,
        }
