import os
import sqlite3
from datetime import datetime

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

                CREATE VIEW IF NOT EXISTS v_tender_export AS
                SELECT
                    t.run_id AS run_id,
                    t.portal_name AS portal_name,
                    t.department_name AS department_name,
                    t.tender_id_extracted AS tender_id_extracted,
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
        with self._connect() as conn:
            conn.execute("DELETE FROM tenders WHERE run_id = ?", (run_id,))
            if not tenders:
                return 0

            rows = []
            for item in tenders:
                tender_id = str(item.get("Tender ID (Extracted)", "")).strip()
                emd_raw = item.get("EMD Amount")
                emd_numeric = item.get("EMD Amount (Numeric)")
                try:
                    emd_numeric = float(emd_numeric) if emd_numeric is not None else None
                except Exception:
                    emd_numeric = None
                rows.append(
                    (
                        run_id,
                        str(item.get("Portal", "")).strip(),
                        str(item.get("Department Name", "")).strip(),
                        tender_id,
                        str(item.get("Published Date", "")).strip(),
                        str(item.get("Closing Date", "")).strip(),
                        str(item.get("Opening Date", "")).strip(),
                        str(item.get("Title and Ref.No./Tender ID", "")).strip(),
                        str(item.get("Organisation Chain", "")).strip(),
                        str(emd_raw).strip() if emd_raw is not None else "",
                        emd_numeric,
                        str(item)
                    )
                )

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
