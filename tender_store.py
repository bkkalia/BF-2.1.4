import os
import re
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone

import pandas as pd


# IST = UTC+5:30  (all portal closing times are in Indian Standard Time)
_IST = timezone(timedelta(hours=5, minutes=30))


class TenderDataStore:
    """SQLite-backed primary datastore for tender runs and extracted tenders."""

    def __init__(self, db_path):
        self.db_path = db_path
        self._use_v3 = False
        self._ensure_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _ensure_schema(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        with self._connect() as conn:
            tables = {
                str(row[0]).strip().lower()
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            has_v3 = "portals" in tables and "tender_items" in tables

            if has_v3:
                self._use_v3 = True
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS scrape_runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        portal_name TEXT NOT NULL,
                        base_url TEXT,
                        scope_mode TEXT,
                        started_at TEXT NOT NULL,
                        completed_at TEXT,
                        status TEXT,
                        expected_total_tenders INTEGER DEFAULT 0,
                        extracted_total_tenders INTEGER DEFAULT 0,
                        skipped_existing_total INTEGER DEFAULT 0,
                        partial_saved INTEGER DEFAULT 0,
                        output_file_path TEXT,
                        output_file_type TEXT
                    );

                    CREATE TABLE IF NOT EXISTS scrape_run_items (
                        run_id INTEGER NOT NULL,
                        tender_item_id INTEGER NOT NULL,
                        PRIMARY KEY (run_id, tender_item_id),
                        FOREIGN KEY (run_id) REFERENCES scrape_runs(id) ON DELETE CASCADE,
                        FOREIGN KEY (tender_item_id) REFERENCES tender_items(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_scrape_run_items_run_id ON scrape_run_items(run_id);
                    CREATE INDEX IF NOT EXISTS idx_scrape_runs_portal_name ON scrape_runs(LOWER(TRIM(COALESCE(portal_name, ''))));
                    CREATE INDEX IF NOT EXISTS idx_tender_items_portal_slug_tender_id
                        ON tender_items(LOWER(TRIM(COALESCE(portal_slug, ''))), TRIM(COALESCE(tender_id_extracted, '')));
                    """
                )
                return

            self._use_v3 = False
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    portal_name TEXT NOT NULL,
                    base_url TEXT,
                    scope_mode TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT,
                    expected_total_tenders INTEGER DEFAULT 0,
                    extracted_total_tenders INTEGER DEFAULT 0,
                    skipped_existing_total INTEGER DEFAULT 0,
                    partial_saved INTEGER DEFAULT 0,
                    output_file_path TEXT,
                    output_file_type TEXT
                );

                CREATE TABLE IF NOT EXISTS tenders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    portal_name TEXT,
                    department_name TEXT,
                    serial_no TEXT,
                    tender_id_extracted TEXT,
                    lifecycle_status TEXT DEFAULT 'active',
                    cancelled_detected_at TEXT,
                    cancelled_source TEXT,
                    published_date TEXT,
                    closing_date TEXT,
                    opening_date TEXT,
                    title_ref TEXT,
                    organisation_chain TEXT,
                    direct_url TEXT,
                    status_url TEXT,
                    emd_amount TEXT,
                    emd_amount_numeric REAL,
                    tender_json TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_tenders_run_id ON tenders(run_id);
                CREATE INDEX IF NOT EXISTS idx_tenders_tender_id ON tenders(tender_id_extracted);
                CREATE INDEX IF NOT EXISTS idx_tenders_portal_tender_norm
                    ON tenders(LOWER(TRIM(COALESCE(portal_name, ''))), TRIM(COALESCE(tender_id_extracted, '')));

                DROP VIEW IF EXISTS v_tender_export;

                CREATE VIEW v_tender_export AS
                SELECT
                    t.run_id AS run_id,
                    t.portal_name AS portal_name,
                    t.department_name AS department_name,
                    t.serial_no AS serial_no,
                    t.tender_id_extracted AS tender_id_extracted,
                    t.lifecycle_status AS lifecycle_status,
                    t.cancelled_detected_at AS cancelled_detected_at,
                    t.cancelled_source AS cancelled_source,
                    t.published_date AS published_date,
                    t.closing_date AS closing_date,
                    t.opening_date AS opening_date,
                    t.title_ref AS title_ref,
                    t.organisation_chain AS organisation_chain,
                    t.direct_url AS direct_url,
                    t.status_url AS status_url,
                    t.emd_amount AS emd_amount,
                    t.emd_amount_numeric AS emd_amount_numeric,
                    r.scope_mode AS scope_mode,
                    r.started_at AS run_started_at,
                    r.completed_at AS run_completed_at,
                    r.status AS run_status
                FROM tenders t
                JOIN runs r ON r.id = t.run_id;
                """
            )

            self._ensure_column(conn, "tenders", "lifecycle_status", "TEXT DEFAULT 'active'")
            self._ensure_column(conn, "tenders", "cancelled_detected_at", "TEXT")
            self._ensure_column(conn, "tenders", "cancelled_source", "TEXT")
            self._ensure_column(conn, "tenders", "serial_no", "TEXT")
            self._ensure_column(conn, "tenders", "direct_url", "TEXT")
            self._ensure_column(conn, "tenders", "status_url", "TEXT")
            conn.execute(
                """
                UPDATE tenders
                SET lifecycle_status = 'active'
                WHERE trim(coalesce(lifecycle_status, '')) = ''
                """
            )

    @staticmethod
    def _portal_key(portal_name):
        return str(portal_name or "").strip().lower()

    def _resolve_portal_record(self, conn, portal_name):
        portal_text = str(portal_name or "").strip()
        portal_key = self._portal_key(portal_name)
        if not portal_key:
            return None

        row = conn.execute(
            """
            SELECT id, portal_slug, portal_name
            FROM portals
            WHERE LOWER(TRIM(COALESCE(portal_slug, ''))) = ?
               OR LOWER(TRIM(COALESCE(portal_name, ''))) = ?
            ORDER BY CASE WHEN LOWER(TRIM(COALESCE(portal_slug, ''))) = ? THEN 0 ELSE 1 END, id ASC
            LIMIT 1
            """,
            (portal_key, portal_key, portal_key),
        ).fetchone()
        if row:
            return row

        conn.execute(
            """
            INSERT INTO portals (portal_slug, portal_name, base_url, last_updated)
            VALUES (?, ?, NULL, NULL)
            """,
            (portal_text or portal_key, portal_text or portal_key),
        )
        return conn.execute(
            """
            SELECT id, portal_slug, portal_name
            FROM portals
            WHERE id = last_insert_rowid()
            """
        ).fetchone()

    def _ensure_column(self, conn, table_name, column_name, ddl):
        columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {str(row[1]).strip().lower() for row in columns}
        if column_name.strip().lower() in existing:
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")

    def backup_if_due(self, backup_dir, retention_days=30):
        backup_target = str(backup_dir or "").strip()
        if not backup_target:
            return None

        if not os.path.exists(self.db_path):
            return None

        retention_days = max(7, int(retention_days or 30))
        os.makedirs(backup_target, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(self.db_path))[0]
        now = datetime.now()
        day_stamp = now.strftime("%Y%m%d")
        backup_filename = f"{base_name}_{day_stamp}.sqlite3"
        backup_path = os.path.join(backup_target, backup_filename)

        if not os.path.exists(backup_path):
            shutil.copy2(self.db_path, backup_path)

        weekly_dir = os.path.join(backup_target, "weekly")
        monthly_dir = os.path.join(backup_target, "monthly")
        yearly_dir = os.path.join(backup_target, "yearly")
        os.makedirs(weekly_dir, exist_ok=True)
        os.makedirs(monthly_dir, exist_ok=True)
        os.makedirs(yearly_dir, exist_ok=True)

        iso_year, iso_week, _ = now.isocalendar()
        week_stamp = f"{iso_year}W{iso_week:02d}"
        week_path = os.path.join(weekly_dir, f"{base_name}_{week_stamp}.sqlite3")
        if not os.path.exists(week_path):
            shutil.copy2(self.db_path, week_path)

        month_stamp = now.strftime("%Y%m")
        month_path = os.path.join(monthly_dir, f"{base_name}_{month_stamp}.sqlite3")
        if not os.path.exists(month_path):
            shutil.copy2(self.db_path, month_path)

        year_stamp = now.strftime("%Y")
        year_path = os.path.join(yearly_dir, f"{base_name}_{year_stamp}.sqlite3")
        if not os.path.exists(year_path):
            shutil.copy2(self.db_path, year_path)

        cutoff = datetime.now() - timedelta(days=retention_days)
        for entry in os.listdir(backup_target):
            if not entry.lower().endswith(".sqlite3"):
                continue
            entry_path = os.path.join(backup_target, entry)
            try:
                modified_time = datetime.fromtimestamp(os.path.getmtime(entry_path))
                if modified_time < cutoff:
                    os.remove(entry_path)
            except Exception:
                continue

        weekly_cutoff = now - timedelta(days=7 * 16)
        for entry in os.listdir(weekly_dir):
            if not entry.lower().endswith(".sqlite3"):
                continue
            entry_path = os.path.join(weekly_dir, entry)
            try:
                modified_time = datetime.fromtimestamp(os.path.getmtime(entry_path))
                if modified_time < weekly_cutoff:
                    os.remove(entry_path)
            except Exception:
                continue

        monthly_cutoff = now - timedelta(days=31 * 24)
        for entry in os.listdir(monthly_dir):
            if not entry.lower().endswith(".sqlite3"):
                continue
            entry_path = os.path.join(monthly_dir, entry)
            try:
                modified_time = datetime.fromtimestamp(os.path.getmtime(entry_path))
                if modified_time < monthly_cutoff:
                    os.remove(entry_path)
            except Exception:
                continue

        yearly_cutoff = now - timedelta(days=366 * 7)
        for entry in os.listdir(yearly_dir):
            if not entry.lower().endswith(".sqlite3"):
                continue
            entry_path = os.path.join(yearly_dir, entry)
            try:
                modified_time = datetime.fromtimestamp(os.path.getmtime(entry_path))
                if modified_time < yearly_cutoff:
                    os.remove(entry_path)
            except Exception:
                continue

        return backup_path

    @staticmethod
    def _parse_closing_date_ist(value: str) -> "datetime | None":
        """Parse a closing date string (e.g. '05-Mar-2026 09:00 AM') as IST datetime.
        Returns None if the string cannot be parsed.
        """
        text = str(value or "").strip()
        if not text:
            return None
        for fmt in (
            "%d-%b-%Y %I:%M %p",   # 05-Mar-2026 09:00 AM
            "%d/%b/%Y %I:%M %p",   # 05/Mar/2026 09:00 AM
            "%d-%m-%Y %I:%M %p",   # 05-03-2026 09:00 AM
            "%d-%b-%Y %H:%M",      # 05-Mar-2026 09:00
            "%Y-%m-%d %H:%M:%S",   # ISO format
        ):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=_IST)
            except ValueError:
                continue
        return None

    def get_existing_tender_ids_for_portal(self, portal_name):
        """
        Return the set of tender IDs from this portal that are still live
        right now in IST (closing datetime > current IST time).

        Only tenders that are genuinely not yet expired are loaded into memory
        so the scraper skips exactly those — and re-scrapes anything whose
        closing date has passed or whose ID is new.

        Tenders with an unparseable / missing closing date are included
        conservatively (to avoid re-scraping unknowns).
        """
        portal_key = str(portal_name or "").strip().lower()
        if not portal_key:
            return set()

        now_ist = datetime.now(tz=_IST)

        with self._connect() as conn:
            if self._use_v3:
                rows = conn.execute(
                    """
                    SELECT DISTINCT
                        TRIM(COALESCE(ti.tender_id_extracted, '')) AS tender_id,
                        TRIM(COALESCE(ti.closing_at, '')) AS closing_date
                    FROM tender_items ti
                    JOIN portals p ON p.id = ti.portal_id
                    WHERE (
                            LOWER(TRIM(COALESCE(ti.portal_slug, ''))) = ?
                         OR LOWER(TRIM(COALESCE(p.portal_name, ''))) = ?
                    )
                      AND TRIM(COALESCE(ti.tender_id_extracted, '')) != ''
                    """,
                    (portal_key, portal_key),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT DISTINCT
                        TRIM(tender_id_extracted) AS tender_id,
                        TRIM(COALESCE(closing_date, ''))  AS closing_date
                    FROM tenders
                    WHERE LOWER(TRIM(COALESCE(portal_name, ''))) = ?
                      AND TRIM(COALESCE(tender_id_extracted, '')) != ''
                    """,
                    (portal_key,),
                ).fetchall()

        live_ids: set[str] = set()
        for row in rows:
            tid = row["tender_id"]
            if not tid:
                continue
            parsed = self._parse_closing_date_ist(row["closing_date"])
            # Include if: still in future (IST) OR date couldn't be parsed
            if parsed is None or parsed > now_ist:
                live_ids.add(tid)
        return live_ids

    @staticmethod
    def _normalize_date_text(value):
        text = str(value or "").strip().upper()
        if not text:
            return ""
        text = text.replace("-", "/").replace(".", "/")
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _normalize_tender_id_text(value):
        text = str(value or "").strip()
        if not text:
            return ""
        text = re.sub(r'(?i)^\s*(tender\s*id|tenderid|id)\s*[:#\-]?\s*', '', text)
        if text.startswith('[') and text.endswith(']') and len(text) > 2:
            text = text[1:-1]
        text = text.upper().strip()
        text = re.sub(r'[\s\-\./]+', '_', text)
        text = re.sub(r'_+', '_', text).strip('_')
        return text

    def get_existing_tender_snapshot_for_portal(self, portal_name):
        """
        Return a dict of { normalized_tender_id -> {tender_id, closing_date} }
        for all tenders from this portal that are still live in IST.

        Used by the scraper to:
          - skip a row  when tender_id matches AND closing_date matches
          - re-scrape   when tender_id matches BUT  closing_date differs (extended)
          - scrape new  when tender_id is not present at all

        Tenders with unparseable / missing closing date are included
        conservatively.
        """
        portal_key = str(portal_name or "").strip().lower()
        if not portal_key:
            return {}

        now_ist = datetime.now(tz=_IST)

        with self._connect() as conn:
                        if self._use_v3:
                                rows = conn.execute(
                                        """
                                        SELECT TRIM(COALESCE(ti.tender_id_extracted, '')) AS tender_id,
                                                     TRIM(COALESCE(ti.closing_at, ''))          AS closing_date
                                        FROM tender_items ti
                                        JOIN portals p ON p.id = ti.portal_id
                                        WHERE (
                                                        LOWER(TRIM(COALESCE(ti.portal_slug, ''))) = ?
                                                 OR LOWER(TRIM(COALESCE(p.portal_name, ''))) = ?
                                        )
                                            AND TRIM(COALESCE(ti.tender_id_extracted, '')) != ''
                                        """,
                                        (portal_key, portal_key),
                                ).fetchall()
                        else:
                                rows = conn.execute(
                                        """
                                        SELECT TRIM(COALESCE(tender_id_extracted, '')) AS tender_id,
                                                     TRIM(COALESCE(closing_date, ''))        AS closing_date
                                        FROM tenders
                                        WHERE LOWER(TRIM(COALESCE(portal_name, ''))) = ?
                                            AND TRIM(COALESCE(tender_id_extracted, '')) != ''
                                        """,
                                        (portal_key,),
                                ).fetchall()

        snapshot: dict = {}
        for row in rows:
            tender_id = str(row["tender_id"] or "").strip()
            if not tender_id:
                continue
            parsed = self._parse_closing_date_ist(row["closing_date"])
            # Skip tenders that have already expired in IST
            if parsed is not None and parsed <= now_ist:
                continue
            normalized_id = self._normalize_tender_id_text(tender_id)
            if not normalized_id:
                continue
            # Keep first occurrence (most recent insert wins naturally)
            if normalized_id not in snapshot:
                snapshot[normalized_id] = {
                    "tender_id": tender_id,
                    "closing_date": self._normalize_date_text(row["closing_date"]),
                }

        return snapshot

    def start_run(self, portal_name, base_url, scope_mode="all"):
        started_at = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            if self._use_v3:
                cur = conn.execute(
                    """
                    INSERT INTO scrape_runs (portal_name, base_url, scope_mode, started_at, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (portal_name or "Unknown", base_url or "", scope_mode, started_at, "running")
                )
                run_id = cur.lastrowid
                if run_id is None:
                    raise RuntimeError("Failed to create run record in SQLite datastore")
                return int(run_id)

            cur = conn.execute(
                """
                INSERT INTO runs (portal_name, base_url, scope_mode, started_at, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (portal_name or "Unknown", base_url or "", scope_mode, started_at, "running")
            )
            run_id = cur.lastrowid
            if run_id is None:
                raise RuntimeError("Failed to create run record in SQLite datastore")
            return int(run_id)

    def replace_run_tenders(self, run_id, tenders):
        def _normalize_text(value):
            if value is None:
                return ""
            return str(value).strip()

        def _is_missing_tender_id(value):
            tender_id = _normalize_text(value)
            if not tender_id:
                return True
            return tender_id.lower() in {"nan", "none", "null", "na", "n/a", "-"}

        with self._connect() as conn:
            if self._use_v3:
                run_row = conn.execute(
                    """
                    SELECT portal_name
                    FROM scrape_runs
                    WHERE id = ?
                    """,
                    (int(run_id),)
                ).fetchone()
                if not run_row:
                    raise RuntimeError(f"Run id {run_id} not found")

                portal_row = self._resolve_portal_record(conn, run_row["portal_name"])
                if not portal_row:
                    return 0

                portal_id = int(portal_row["id"])
                portal_slug = str(portal_row["portal_slug"] or "").strip()

                conn.execute("DELETE FROM scrape_run_items WHERE run_id = ?", (int(run_id),))
                if not tenders:
                    return 0

                deduped = {}
                ordered_keys = []
                for item in tenders:
                    tender_id = _normalize_text(item.get("Tender ID (Extracted)"))
                    if _is_missing_tender_id(tender_id):
                        continue

                    key = tender_id
                    if key not in deduped:
                        ordered_keys.append(key)
                    deduped[key] = item

                now_ts = datetime.now().isoformat(timespec="seconds")
                now_ist = datetime.now(tz=_IST)
                inserted_item_ids = []

                for key in ordered_keys:
                    item = deduped[key]
                    tender_id = _normalize_text(item.get("Tender ID (Extracted)"))
                    if not tender_id:
                        continue

                    published_at = _normalize_text(item.get("Published Date") or item.get("e-Published Date"))
                    closing_at = _normalize_text(item.get("Closing Date"))
                    parsed_close = self._parse_closing_date_ist(closing_at)
                    is_live = 1 if (parsed_close is None or parsed_close > now_ist) else 0

                    conn.execute(
                        """
                        DELETE FROM tender_items
                        WHERE portal_id = ?
                          AND TRIM(COALESCE(tender_id_extracted, '')) = ?
                        """,
                        (portal_id, tender_id),
                    )

                    cur = conn.execute(
                        """
                        INSERT INTO tender_items (
                            portal_id,
                            portal_slug,
                            tender_id_extracted,
                            title_ref,
                            department_name,
                            published_at,
                            closing_at,
                            opening_date,
                            organisation_chain,
                            tender_url,
                            status_url,
                            estimated_cost_value,
                            tender_status,
                            is_live,
                            created_at,
                            updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            portal_id,
                            portal_slug,
                            tender_id,
                            _normalize_text(item.get("Title and Ref.No./Tender ID")),
                            _normalize_text(item.get("Department Name")),
                            published_at,
                            closing_at,
                            _normalize_text(item.get("Opening Date")),
                            _normalize_text(item.get("Organisation Chain")),
                            _normalize_text(item.get("Direct URL")),
                            _normalize_text(item.get("Status URL")),
                            None,
                            "active" if is_live else "expired",
                            is_live,
                            now_ts,
                            now_ts,
                        ),
                    )
                    item_id = cur.lastrowid
                    if item_id is not None:
                        inserted_item_ids.append((int(run_id), int(item_id)))

                if inserted_item_ids:
                    conn.executemany(
                        """
                        INSERT OR IGNORE INTO scrape_run_items (run_id, tender_item_id)
                        VALUES (?, ?)
                        """,
                        inserted_item_ids,
                    )

                conn.execute(
                    """
                    UPDATE portals
                    SET last_updated = ?
                    WHERE id = ?
                    """,
                    (now_ts, portal_id),
                )

                return len(inserted_item_ids)

            conn.execute("DELETE FROM tenders WHERE run_id = ?", (run_id,))
            if not tenders:
                return 0

            deduped = {}
            ordered_keys = []
            for item in tenders:
                portal_name = _normalize_text(item.get("Portal"))
                tender_id = _normalize_text(item.get("Tender ID (Extracted)"))
                if _is_missing_tender_id(tender_id):
                    continue

                key = (portal_name.lower(), tender_id)
                if key not in deduped:
                    ordered_keys.append(key)
                deduped[key] = item

            rows = []
            dedupe_keys = []
            for key in ordered_keys:
                item = deduped[key]
                portal_name = _normalize_text(item.get("Portal"))
                tender_id = _normalize_text(item.get("Tender ID (Extracted)"))
                emd_raw = item.get("EMD Amount")
                emd_numeric = item.get("EMD Amount (Numeric)")
                try:
                    emd_numeric = float(emd_numeric) if emd_numeric is not None else None
                except Exception:
                    emd_numeric = None
                dedupe_keys.append((key[0], tender_id))

                rows.append(
                    (
                        run_id,
                        portal_name,
                        _normalize_text(item.get("Department Name")),
                        tender_id,
                        _normalize_text(item.get("S.No")),
                        _normalize_text(item.get("Published Date") or item.get("e-Published Date")),
                        _normalize_text(item.get("Closing Date")),
                        _normalize_text(item.get("Opening Date")),
                        _normalize_text(item.get("Title and Ref.No./Tender ID")),
                        _normalize_text(item.get("Organisation Chain")),
                        _normalize_text(item.get("Direct URL")),
                        _normalize_text(item.get("Status URL")),
                        _normalize_text(emd_raw),
                        emd_numeric,
                        str(item)
                    )
                )

            if dedupe_keys:
                conn.execute("DROP TABLE IF EXISTS _incoming_keys")
                conn.execute(
                    """
                    CREATE TEMP TABLE _incoming_keys (
                        portal_key TEXT NOT NULL,
                        tender_key TEXT NOT NULL
                    )
                    """
                )
                conn.executemany(
                    "INSERT INTO _incoming_keys (portal_key, tender_key) VALUES (?, ?)",
                    dedupe_keys
                )
                conn.execute(
                    """
                    DELETE FROM tenders
                    WHERE EXISTS (
                        SELECT 1
                        FROM _incoming_keys k
                        WHERE k.portal_key = LOWER(TRIM(COALESCE(tenders.portal_name, '')))
                          AND (
                              k.tender_key = TRIM(COALESCE(tenders.tender_id_extracted, ''))
                              OR COALESCE(tenders.title_ref, '') LIKE '%[' || k.tender_key || ']%'
                          )
                    )
                    """
                )
                conn.execute("DROP TABLE IF EXISTS _incoming_keys")

            conn.executemany(
                """
                INSERT INTO tenders (
                    run_id, portal_name, department_name, tender_id_extracted,
                    serial_no, published_date, closing_date, opening_date,
                    title_ref, organisation_chain, direct_url, status_url,
                    emd_amount, emd_amount_numeric, tender_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows
            )
            return len(rows)

    def export_run(self, run_id, output_dir, website_keyword, mark_partial=False):
        if self._use_v3:
            query = """
                SELECT
                    ti.department_name AS [Department Name],
                    '' AS [S.No],
                    ti.published_at AS [e-Published Date],
                    ti.published_at AS [Published Date],
                    ti.closing_at AS [Closing Date],
                    ti.opening_date AS [Opening Date],
                    ti.tender_url AS [Direct URL],
                    ti.status_url AS [Status URL],
                    ti.title_ref AS [Title and Ref.No./Tender ID],
                    ti.organisation_chain AS [Organisation Chain],
                    TRIM(COALESCE(ti.tender_id_extracted, '')) AS [Tender ID (Extracted)],
                    CASE
                        WHEN LOWER(TRIM(COALESCE(ti.tender_status, ''))) = 'cancelled' THEN 'cancelled'
                        WHEN COALESCE(ti.is_live, 0) = 1 THEN 'active'
                        ELSE 'expired'
                    END AS [Lifecycle Status],
                    '' AS [Cancelled Detected At],
                    '' AS [Cancelled Source],
                    '' AS [EMD Amount],
                    NULL AS [EMD Amount (Numeric)],
                    p.portal_name AS [Portal],
                    sr.started_at AS [Run Started At],
                    sr.completed_at AS [Run Completed At],
                    sr.status AS [Run Status],
                    sr.scope_mode AS [Scope]
                FROM scrape_run_items sri
                JOIN tender_items ti ON ti.id = sri.tender_item_id
                JOIN portals p ON p.id = ti.portal_id
                JOIN scrape_runs sr ON sr.id = sri.run_id
                WHERE sri.run_id = ?
                ORDER BY [Department Name] ASC, [Tender ID (Extracted)] ASC
            """

            with self._connect() as conn:
                df = pd.read_sql_query(query, conn, params=(run_id,))

            if df.empty:
                return None, None

            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = "_partial" if mark_partial else ""
            file_stem = f"{website_keyword}{suffix}_tenders_{timestamp}"
            excel_path = os.path.join(output_dir, f"{file_stem}.xlsx")

            try:
                df.to_excel(excel_path, index=False, engine="openpyxl")
                return excel_path, "excel"
            except Exception:
                csv_path = os.path.join(output_dir, f"{file_stem}.csv")
                df.to_csv(csv_path, index=False, encoding="utf-8-sig")
                return csv_path, "csv"

        query = """
            SELECT
                department_name AS [Department Name],
                serial_no AS [S.No],
                published_date AS [e-Published Date],
                published_date AS [Published Date],
                closing_date AS [Closing Date],
                opening_date AS [Opening Date],
                direct_url AS [Direct URL],
                status_url AS [Status URL],
                title_ref AS [Title and Ref.No./Tender ID],
                organisation_chain AS [Organisation Chain],
                CASE
                    WHEN TRIM(COALESCE(tender_id_extracted, '')) <> '' THEN TRIM(tender_id_extracted)
                    ELSE TRIM(COALESCE(serial_no, ''))
                END AS [Tender ID (Extracted)],
                lifecycle_status AS [Lifecycle Status],
                cancelled_detected_at AS [Cancelled Detected At],
                cancelled_source AS [Cancelled Source],
                emd_amount AS [EMD Amount],
                emd_amount_numeric AS [EMD Amount (Numeric)],
                portal_name AS [Portal],
                run_started_at AS [Run Started At],
                run_completed_at AS [Run Completed At],
                run_status AS [Run Status],
                scope_mode AS [Scope]
            FROM v_tender_export
            WHERE run_id = ?
            ORDER BY [Department Name] ASC, [Tender ID (Extracted)] ASC
        """

        with self._connect() as conn:
            df = pd.read_sql_query(query, conn, params=(run_id,))

        if df.empty:
            return None, None

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = "_partial" if mark_partial else ""
        file_stem = f"{website_keyword}{suffix}_tenders_{timestamp}"
        excel_path = os.path.join(output_dir, f"{file_stem}.xlsx")

        try:
            df.to_excel(excel_path, index=False, engine="openpyxl")
            return excel_path, "excel"
        except Exception:
            csv_path = os.path.join(output_dir, f"{file_stem}.csv")
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            return csv_path, "csv"

    def get_latest_completed_run_id(self, portal_name=None, full_only=False):
        if self._use_v3:
            where = ["completed_at IS NOT NULL", "LOWER(TRIM(COALESCE(status, ''))) LIKE 'scraping completed%'"]
            params = []

            portal_key = str(portal_name or "").strip().lower()
            if portal_key:
                where.append("LOWER(TRIM(COALESCE(portal_name, ''))) = ?")
                params.append(portal_key)

            if full_only:
                where.append("LOWER(TRIM(COALESCE(scope_mode, 'all'))) = 'all'")

            query = f"""
                SELECT id
                FROM scrape_runs
                WHERE {' AND '.join(where)}
                ORDER BY id DESC
                LIMIT 1
            """

            with self._connect() as conn:
                row = conn.execute(query, tuple(params)).fetchone()
                return int(row[0]) if row and row[0] is not None else None

        where = ["completed_at IS NOT NULL", "LOWER(TRIM(COALESCE(status, ''))) LIKE 'scraping completed%'"]
        params = []

        portal_key = str(portal_name or "").strip().lower()
        if portal_key:
            where.append("LOWER(TRIM(COALESCE(portal_name, ''))) = ?")
            params.append(portal_key)

        if full_only:
            where.append("LOWER(TRIM(COALESCE(scope_mode, 'all'))) = 'all'")

        query = f"""
            SELECT id
            FROM runs
            WHERE {' AND '.join(where)}
            ORDER BY id DESC
            LIMIT 1
        """

        with self._connect() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
            return int(row[0]) if row and row[0] is not None else None

    def get_portal_status_snapshot(self, portal_name=None):
        if self._use_v3:
            params = []
            portal_filter = ""
            portal_key = str(portal_name or "").strip().lower()
            if portal_key:
                portal_filter = " AND LOWER(TRIM(COALESCE(portal_name, ''))) = ?"
                params.append(portal_key)

            with self._connect() as conn:
                last_run = conn.execute(
                    f"""
                    SELECT portal_name, scope_mode, status, started_at, completed_at,
                           output_file_path, output_file_type
                    FROM scrape_runs
                    WHERE 1=1 {portal_filter}
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    tuple(params),
                ).fetchone()

                last_full = conn.execute(
                    f"""
                    SELECT completed_at
                    FROM scrape_runs
                    WHERE LOWER(TRIM(COALESCE(status, ''))) LIKE 'scraping completed%'
                      AND LOWER(TRIM(COALESCE(scope_mode, 'all'))) = 'all'
                      {portal_filter}
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    tuple(params),
                ).fetchone()

                last_excel = conn.execute(
                    f"""
                    SELECT completed_at, output_file_path
                    FROM scrape_runs
                    WHERE TRIM(COALESCE(output_file_path, '')) <> ''
                      AND LOWER(TRIM(COALESCE(output_file_type, ''))) = 'excel'
                      {portal_filter}
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    tuple(params),
                ).fetchone()

            return {
                "last_run": dict(last_run) if last_run else None,
                "last_full_scrape_at": str(last_full[0]) if last_full and last_full[0] else None,
                "last_excel_export_at": str(last_excel[0]) if last_excel and last_excel[0] else None,
                "last_excel_export_path": str(last_excel[1]) if last_excel and len(last_excel) > 1 and last_excel[1] else None,
            }

        params = []
        portal_filter = ""
        portal_key = str(portal_name or "").strip().lower()
        if portal_key:
            portal_filter = " AND LOWER(TRIM(COALESCE(portal_name, ''))) = ?"
            params.append(portal_key)

        with self._connect() as conn:
            last_run = conn.execute(
                f"""
                SELECT portal_name, scope_mode, status, started_at, completed_at,
                       output_file_path, output_file_type
                FROM runs
                WHERE 1=1 {portal_filter}
                ORDER BY id DESC
                LIMIT 1
                """,
                tuple(params),
            ).fetchone()

            last_full = conn.execute(
                f"""
                SELECT completed_at
                FROM runs
                WHERE LOWER(TRIM(COALESCE(status, ''))) LIKE 'scraping completed%'
                  AND LOWER(TRIM(COALESCE(scope_mode, 'all'))) = 'all'
                  {portal_filter}
                ORDER BY id DESC
                LIMIT 1
                """,
                tuple(params),
            ).fetchone()

            last_excel = conn.execute(
                f"""
                SELECT completed_at, output_file_path
                FROM runs
                WHERE TRIM(COALESCE(output_file_path, '')) <> ''
                  AND LOWER(TRIM(COALESCE(output_file_type, ''))) = 'excel'
                  {portal_filter}
                ORDER BY id DESC
                LIMIT 1
                """,
                tuple(params),
            ).fetchone()

        return {
            "last_run": dict(last_run) if last_run else None,
            "last_full_scrape_at": str(last_full[0]) if last_full and last_full[0] else None,
            "last_excel_export_at": str(last_excel[0]) if last_excel and last_excel[0] else None,
            "last_excel_export_path": str(last_excel[1]) if last_excel and len(last_excel) > 1 and last_excel[1] else None,
        }

    def update_run_progress(self, run_id, expected_total=None, extracted_total=None, skipped_total=None):
        """Update run progress counters without finalizing the run."""
        with self._connect() as conn:
            updates = []
            params = []
            if expected_total is not None:
                updates.append("expected_total_tenders = ?")
                params.append(int(expected_total))
            if extracted_total is not None:
                updates.append("extracted_total_tenders = ?")
                params.append(int(extracted_total))
            if skipped_total is not None:
                updates.append("skipped_existing_total = ?")
                params.append(int(skipped_total))
            
            if not updates:
                return
            
            params.append(int(run_id))
            if self._use_v3:
                conn.execute(
                    f"UPDATE scrape_runs SET {', '.join(updates)} WHERE id = ?",
                    params
                )
                return

            conn.execute(
                f"UPDATE runs SET {', '.join(updates)} WHERE id = ?",
                params
            )

    def finalize_run(self, run_id, status, expected_total, extracted_total, skipped_total, partial_saved=False, output_file_path=None, output_file_type=None):
        completed_at = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            if self._use_v3:
                conn.execute(
                    """
                    UPDATE scrape_runs
                    SET
                        completed_at = ?,
                        status = ?,
                        expected_total_tenders = ?,
                        extracted_total_tenders = ?,
                        skipped_existing_total = ?,
                        partial_saved = ?,
                        output_file_path = ?,
                        output_file_type = ?
                    WHERE id = ?
                    """,
                    (
                        completed_at,
                        status,
                        int(expected_total or 0),
                        int(extracted_total or 0),
                        int(skipped_total or 0),
                        1 if partial_saved else 0,
                        output_file_path,
                        output_file_type,
                        int(run_id)
                    )
                )
                return

            conn.execute(
                """
                UPDATE runs
                SET
                    completed_at = ?,
                    status = ?,
                    expected_total_tenders = ?,
                    extracted_total_tenders = ?,
                    skipped_existing_total = ?,
                    partial_saved = ?,
                    output_file_path = ?,
                    output_file_type = ?
                WHERE id = ?
                """,
                (
                    completed_at,
                    status,
                    int(expected_total or 0),
                    int(extracted_total or 0),
                    int(skipped_total or 0),
                    1 if partial_saved else 0,
                    output_file_path,
                    output_file_type,
                    int(run_id)
                )
            )

    def mark_tenders_cancelled(self, portal_name, tender_ids, source="cancelled_page"):
        portal_key = str(portal_name or "").strip().lower()
        clean_ids = sorted({str(item).strip() for item in (tender_ids or []) if str(item).strip()})
        if not portal_key or not clean_ids:
            return 0

        now = datetime.now().isoformat(timespec="seconds")
        placeholders = ",".join(["?"] * len(clean_ids))
        params = [now, str(source or "cancelled_page"), portal_key] + clean_ids

        with self._connect() as conn:
            if self._use_v3:
                cur = conn.execute(
                    f"""
                    UPDATE tender_items
                    SET
                        tender_status = 'cancelled',
                        is_live = 0,
                        updated_at = ?
                    WHERE (
                            lower(trim(coalesce(portal_slug, ''))) = ?
                         OR portal_id IN (
                                SELECT id FROM portals WHERE lower(trim(coalesce(portal_name, ''))) = ?
                            )
                    )
                      AND trim(coalesce(tender_id_extracted, '')) IN ({placeholders})
                    """,
                    [now, portal_key, portal_key] + clean_ids,
                )
                return int(cur.rowcount or 0)

            cur = conn.execute(
                f"""
                UPDATE tenders
                SET
                    lifecycle_status = 'cancelled',
                    cancelled_detected_at = ?,
                    cancelled_source = ?
                WHERE lower(trim(coalesce(portal_name, ''))) = ?
                  AND trim(coalesce(tender_id_extracted, '')) IN ({placeholders})
                """,
                params
            )
            return int(cur.rowcount or 0)
