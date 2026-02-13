import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tender_store import TenderDataStore


def _parse_ids_from_file(path):
    ext = os.path.splitext(path)[1].lower()
    ids = set()

    if ext in {".txt", ".log"}:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                value = str(line or "").strip()
                if value:
                    ids.add(value)
        return ids

    if ext == ".csv":
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = [str(c or "").strip() for c in (reader.fieldnames or [])]
            col_map = {c.lower(): c for c in columns}
            id_col = col_map.get("tender_id") or col_map.get("tender id") or col_map.get("tender_id_extracted")

            if id_col:
                for row in reader:
                    value = str(row.get(id_col) or "").strip()
                    if value:
                        ids.add(value)
            else:
                handle.seek(0)
                raw = csv.reader(handle)
                for row in raw:
                    for cell in row:
                        value = str(cell or "").strip()
                        if value and value.lower() not in {"tender_id", "tender id", "tender_id_extracted"}:
                            ids.add(value)
        return ids

    raise ValueError(f"Unsupported file extension: {ext}")


def _parse_ids_inline(values):
    ids = set()
    for item in values or []:
        for token in str(item or "").replace("\n", ",").split(","):
            value = token.strip()
            if value:
                ids.add(value)
    return ids


def main():
    parser = argparse.ArgumentParser(
        description="Mark portal-specific tender IDs as cancelled in SQLite datastore."
    )
    parser.add_argument("--portal", required=True, help="Portal name as stored in tenders.portal_name")
    parser.add_argument("--db", default=os.path.join(ROOT, "data", "blackforest_tenders.sqlite3"), help="SQLite DB path")
    parser.add_argument("--source", default="cancelled_page", help="Cancellation source tag")
    parser.add_argument("--ids", nargs="*", help="Comma-separated or spaced tender IDs")
    parser.add_argument("--ids-file", help="Path to TXT/CSV file with tender IDs")
    args = parser.parse_args()

    cancelled_ids = set()
    cancelled_ids.update(_parse_ids_inline(args.ids))
    if args.ids_file:
        cancelled_ids.update(_parse_ids_from_file(os.path.abspath(args.ids_file)))

    if not cancelled_ids:
        raise ValueError("No tender IDs provided. Use --ids and/or --ids-file.")

    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"SQLite DB not found: {db_path}")

    store = TenderDataStore(db_path)
    updated = store.mark_tenders_cancelled(
        portal_name=args.portal,
        tender_ids=sorted(cancelled_ids),
        source=args.source,
    )

    print(
        f"Cancelled reconcile complete | portal={args.portal} | input_ids={len(cancelled_ids)} | updated_rows={updated}"
    )


if __name__ == "__main__":
    main()
