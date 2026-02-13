import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app_settings import DEFAULT_SETTINGS_STRUCTURE
from tender_store import TenderDataStore


def resolve_settings_paths(workspace: Path):
    settings_path = workspace / "settings.json"
    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except Exception:
            settings = {}

    db_path = str(settings.get("central_sqlite_db_path") or "").strip()
    if not db_path:
        db_path = str(workspace / "data" / "blackforest_tenders.sqlite3")
    elif not os.path.isabs(db_path):
        db_path = str((workspace / db_path).resolve())

    backup_dir = str(settings.get("sqlite_backup_directory") or "").strip()
    if not backup_dir:
        backup_dir = str(workspace / "db_backups")
    elif not os.path.isabs(backup_dir):
        backup_dir = str((workspace / backup_dir).resolve())

    try:
        retention_days = int(settings.get("sqlite_backup_retention_days", DEFAULT_SETTINGS_STRUCTURE.get("sqlite_backup_retention_days", 30)) or 30)
    except Exception:
        retention_days = 30

    return db_path, backup_dir, max(7, retention_days)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "e-Published Date": "Published Date",
        "Published Date": "Published Date",
        "Department": "Department Name",
    }
    cols = {col: mapping.get(col, col) for col in df.columns}
    return df.rename(columns=cols)


def is_scrape_export(df: pd.DataFrame) -> bool:
    cols = set(df.columns)
    required_signals = {
        "Department Name",
        "Title and Ref.No./Tender ID",
        "Tender ID (Extracted)",
        "Direct URL",
        "Status URL",
    }
    signal_count = len(cols.intersection(required_signals))
    if signal_count < 2:
        return False

    if "Title and Ref.No./Tender ID" in cols and df["Title and Ref.No./Tender ID"].astype(str).str.strip().any():
        return True
    if "Tender ID (Extracted)" in cols and df["Tender ID (Extracted)"].astype(str).str.strip().any():
        return True
    return signal_count >= 3


def infer_portal_name(file_path: Path, row_df: pd.DataFrame) -> str:
    if "Portal" in row_df.columns and row_df["Portal"].astype(str).str.strip().any():
        return str(row_df["Portal"].astype(str).iloc[0]).strip()
    stem = file_path.stem
    if "_tenders_" in stem:
        return stem.split("_tenders_")[0]
    return stem


def to_store_rows(df: pd.DataFrame, portal_name: str):
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "Portal": portal_name,
                "Department Name": str(row.get("Department Name", "")).strip(),
                "Published Date": str(row.get("Published Date", "")).strip(),
                "Closing Date": str(row.get("Closing Date", "")).strip(),
                "Opening Date": str(row.get("Opening Date", "")).strip(),
                "Title and Ref.No./Tender ID": str(row.get("Title and Ref.No./Tender ID", "")).strip(),
                "Organisation Chain": str(row.get("Organisation Chain", "")).strip(),
                "Tender ID (Extracted)": str(row.get("Tender ID (Extracted)", "")).strip(),
                "EMD Amount": str(row.get("EMD Amount", "")).strip() if row.get("EMD Amount", "") is not None else "",
                "EMD Amount (Numeric)": None,
            }
        )
    return rows


def load_table(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix == ".xlsx":
        df = pd.read_excel(file_path)
    elif suffix == ".csv":
        df = pd.read_csv(file_path, encoding="utf-8-sig")
    else:
        raise ValueError(f"Unsupported file type: {file_path}")
    return normalize_columns(df)


def collect_source_files(source_dir: Path, cutoff_ts: float, max_files: int):
    candidates = [
        p for p in source_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in {".xlsx", ".csv"} and p.stat().st_mtime >= cutoff_ts
    ]
    candidates = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[: max(1, int(max_files))]


def get_already_imported_output_paths(store: TenderDataStore):
    with store._connect() as conn:
        rows = conn.execute(
            """
            SELECT output_file_path
            FROM runs
            WHERE output_file_path IS NOT NULL AND TRIM(output_file_path) <> ''
            """
        ).fetchall()
    return {str(row[0]).strip() for row in rows if row and row[0]}


def main():
    parser = argparse.ArgumentParser(description="Import recent scrape exports into centralized SQLite datastore")
    parser.add_argument("--workspace", default=".", help="Workspace root path")
    parser.add_argument("--source-dir", default="Tender_Downloads", help="Directory containing scrape export files")
    parser.add_argument("--source-file", default="", help="Single Excel/CSV file to import")
    parser.add_argument("--days", type=int, default=180, help="Import files modified in last N days")
    parser.add_argument("--max-files", type=int, default=25, help="Maximum files to import")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    source_dir = (workspace / args.source_dir).resolve()
    source_file = str(args.source_file or "").strip()
    db_path, backup_dir, retention_days = resolve_settings_paths(workspace)

    if source_file:
        file_candidate = Path(source_file).expanduser().resolve()
        if not file_candidate.exists() or not file_candidate.is_file():
            print(f"Source file not found: {file_candidate}")
            return 1
        candidates = [file_candidate]
    else:
        if not source_dir.exists():
            print(f"Source directory not found: {source_dir}")
            return 1

        cutoff = datetime.now().timestamp() - (max(1, int(args.days)) * 86400)
        candidates = collect_source_files(source_dir, cutoff, args.max_files)

    if not candidates:
        print("No recent scrape files found to import.")
        print(f"DB path: {db_path}")
        print(f"Backup dir: {backup_dir}")
        return 0

    store = TenderDataStore(db_path)
    backup_path = store.backup_if_due(backup_dir=backup_dir, retention_days=retention_days)
    already_imported = get_already_imported_output_paths(store)

    imported_files = 0
    imported_rows = 0
    skipped_existing = 0
    skipped_non_scrape = 0
    for file_path in reversed(candidates):
        try:
            file_abs = str(file_path.resolve())
            if file_abs in already_imported:
                skipped_existing += 1
                continue

            df = load_table(file_path)
            if df.empty:
                continue
            if not is_scrape_export(df):
                skipped_non_scrape += 1
                continue
            portal_name = infer_portal_name(file_path, df)
            rows = to_store_rows(df, portal_name)
            if not rows:
                continue
            run_id = store.start_run(portal_name=portal_name, base_url="imported://recent-scrape", scope_mode="import_recent")
            saved = store.replace_run_tenders(run_id, rows)
            store.finalize_run(
                run_id=run_id,
                status="Imported",
                expected_total=len(rows),
                extracted_total=saved,
                skipped_total=0,
                partial_saved=False,
                output_file_path=file_abs,
                output_file_type=file_path.suffix.lower().lstrip('.'),
            )
            imported_files += 1
            imported_rows += int(saved)
            print(f"Imported {saved:>4} rows from {file_path.name} -> run_id={run_id}")
        except Exception as exc:
            print(f"Skipped {file_path.name}: {exc}")

    print("--- Import Summary ---")
    print(f"Imported files: {imported_files}")
    print(f"Imported rows : {imported_rows}")
    print(f"Skipped existing imports: {skipped_existing}")
    print(f"Skipped non-scrape files: {skipped_non_scrape}")
    print(f"Main DB path  : {db_path}")
    print(f"Backup dir    : {backup_dir}")
    print(f"Backup file   : {backup_path if backup_path else 'not-created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
