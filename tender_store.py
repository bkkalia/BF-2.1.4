import os
import shutil
import sqlite3
from datetime import datetime, timedelta

import pandas as pd


class TenderDataStore:
    """SQLite-backed primary datastore for tender runs and extracted tenders."""

    def __init__(self, db_path):
        self.db_path = db_path
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
                    tender_id_extracted TEXT,
                    lifecycle_status TEXT DEFAULT 'active',
                    cancelled_detected_at TEXT,
                    cancelled_source TEXT,
                    published_date TEXT,
                    closing_date TEXT,
                    opening_date TEXT,
                    title_ref TEXT,
                    organisation_chain TEXT,
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
                    t.tender_id_extracted AS tender_id_extracted,
                    t.lifecycle_status AS lifecycle_status,
                    t.cancelled_detected_at AS cancelled_detected_at,
                    t.cancelled_source AS cancelled_source,
                    t.published_date AS published_date,
                    t.closing_date AS closing_date,
                    t.opening_date AS opening_date,
                    t.title_ref AS title_ref,
                    t.organisation_chain AS organisation_chain,
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
            conn.execute(
                """
                UPDATE tenders
                SET lifecycle_status = 'active'
                WHERE trim(coalesce(lifecycle_status, '')) = ''
                """
            )

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

    def get_existing_tender_ids_for_portal(self, portal_name):
        """
        Fetch all active tender IDs for a given portal from the database.
        
        Args:
            portal_name: Portal name to query (case-insensitive)
            
        Returns:
            Set of tender IDs (strings)
        """
        portal_key = str(portal_name or "").strip().lower()
        if not portal_key:
            return set()
        
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT TRIM(tender_id_extracted)
                FROM tenders
                WHERE LOWER(TRIM(COALESCE(portal_name, ''))) = ?
                  AND TRIM(COALESCE(tender_id_extracted, '')) != ''
                  AND lifecycle_status = 'active'
                """,
                (portal_key,)
            )
            # Return set of tender IDs
            return {row[0] for row in cursor.fetchall() if row[0]}

    def start_run(self, portal_name, base_url, scope_mode="all"):
        started_at = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
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
                        _normalize_text(item.get("Published Date")),
                        _normalize_text(item.get("Closing Date")),
                        _normalize_text(item.get("Opening Date")),
                        _normalize_text(item.get("Title and Ref.No./Tender ID")),
                        _normalize_text(item.get("Organisation Chain")),
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
                          AND k.tender_key = TRIM(COALESCE(tenders.tender_id_extracted, ''))
                    )
                    """
                )
                conn.execute("DROP TABLE IF EXISTS _incoming_keys")

            conn.executemany(
                """
                INSERT INTO tenders (
                    run_id, portal_name, department_name, tender_id_extracted,
                    published_date, closing_date, opening_date,
                    title_ref, organisation_chain, emd_amount, emd_amount_numeric, tender_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows
            )
            return len(rows)

    def export_run(self, run_id, output_dir, website_keyword, mark_partial=False):
        query = """
            SELECT
                department_name AS [Department Name],
                published_date AS [Published Date],
                closing_date AS [Closing Date],
                opening_date AS [Opening Date],
                title_ref AS [Title and Ref.No./Tender ID],
                organisation_chain AS [Organisation Chain],
                tender_id_extracted AS [Tender ID (Extracted)],
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

    def finalize_run(self, run_id, status, expected_total, extracted_total, skipped_total, partial_saved=False, output_file_path=None, output_file_type=None):
        completed_at = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
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
