import argparse
import csv
import json
import os
from datetime import datetime


def _normalize_portal_data(value):
    return value if isinstance(value, dict) else {}


def _compute_stats(portal_data):
    known_departments = {
        str(name).strip().lower()
        for name in portal_data.get("processed_departments", [])
        if str(name).strip()
    }
    dept_url_map = portal_data.get("department_url_map", {})
    if not isinstance(dept_url_map, dict):
        dept_url_map = {}

    mapped = 0
    for row in dept_url_map.values():
        if isinstance(row, dict) and str(row.get("direct_url", "") or "").strip():
            mapped += 1

    known = len(known_departments)
    coverage = int(round((mapped / max(1, known)) * 100)) if known > 0 else 0
    return mapped, known, coverage


def generate_report(manifest_path, output_dir):
    with open(manifest_path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    portals = manifest.get("portals", {})
    if not isinstance(portals, dict):
        portals = {}

    rows = []
    mapped_total = 0
    known_total = 0

    for portal_name in sorted(portals.keys()):
        portal_data = _normalize_portal_data(portals.get(portal_name, {}))
        mapped, known, coverage = _compute_stats(portal_data)
        row = {
            "portal": portal_name,
            "mapped_departments": mapped,
            "known_departments": known,
            "coverage_percent": coverage,
            "last_run": str(portal_data.get("last_run") or ""),
        }
        rows.append(row)
        mapped_total += mapped
        known_total += known

    overall_coverage = int(round((mapped_total / max(1, known_total)) * 100)) if known_total > 0 else 0

    os.makedirs(output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(output_dir, f"department_url_coverage_{stamp}.json")
    csv_path = os.path.join(output_dir, f"department_url_coverage_{stamp}.csv")

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "manifest_path": os.path.abspath(manifest_path),
        "portal_count": len(rows),
        "mapped_departments_total": mapped_total,
        "known_departments_total": known_total,
        "overall_coverage_percent": overall_coverage,
        "portals": rows,
    }

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["portal", "mapped_departments", "known_departments", "coverage_percent", "last_run"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return {
        "json_path": json_path,
        "csv_path": csv_path,
        "overall_coverage_percent": overall_coverage,
        "mapped_departments_total": mapped_total,
        "known_departments_total": known_total,
        "portal_count": len(rows),
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate department direct-URL coverage report from batch manifest.")
    parser.add_argument(
        "--manifest",
        default="batch_tender_manifest.json",
        help="Path to batch manifest JSON file (default: batch_tender_manifest.json)",
    )
    parser.add_argument(
        "--out-dir",
        default=os.path.join("batch_run_reports", "manual_reports"),
        help="Directory to write coverage report files",
    )
    args = parser.parse_args()

    manifest_path = os.path.abspath(args.manifest)
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    result = generate_report(manifest_path, os.path.abspath(args.out_dir))

    print(
        "Department URL coverage report created: "
        f"overall={result['overall_coverage_percent']}% "
        f"({result['mapped_departments_total']}/{result['known_departments_total']}) "
        f"portals={result['portal_count']}"
    )
    print(f"JSON: {result['json_path']}")
    print(f"CSV: {result['csv_path']}")


if __name__ == "__main__":
    main()
