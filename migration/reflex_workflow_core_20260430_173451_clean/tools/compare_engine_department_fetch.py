import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.logic import fetch_department_list_from_site_v2
from scraper.playwright_logic import fetch_department_list_from_site_playwright


def _load_portal_config(base_urls_csv: Path, portal_name: str):
    df = pd.read_csv(base_urls_csv)
    row = df[df["Name"].str.lower() == portal_name.lower()]
    if row.empty:
        row = df[df["Name"].str.contains(portal_name, case=False, na=False)]
    if row.empty:
        raise ValueError(f"Portal not found: {portal_name}")
    item = row.iloc[0].to_dict()
    base = str(item.get("BaseURL") or "").strip()
    return {
        "Name": str(item.get("Name") or portal_name).strip(),
        "BaseURL": base,
        "OrgListURL": f"{base}?page=FrontEndTendersByOrganisation&service=page",
    }


def _to_key_set(departments):
    out = set()
    for d in departments or []:
        s_no = str(d.get("s_no", "")).strip()
        name = str(d.get("name", "")).strip().lower()
        key = (s_no, name)
        if s_no or name:
            out.add(key)
    return out


def main():
    parser = argparse.ArgumentParser(description="Compare Selenium vs Playwright department discovery")
    parser.add_argument("--portal", required=True, help="Portal name from base_urls.csv")
    parser.add_argument("--base-urls", default=str(ROOT / "base_urls.csv"), help="Path to base_urls.csv")
    parser.add_argument("--output", default="", help="Optional output JSON path")
    args = parser.parse_args()

    cfg = _load_portal_config(Path(args.base_urls), args.portal)
    org_url = cfg["OrgListURL"]

    print(f"Comparing engines for portal: {cfg['Name']}")
    print(f"OrgListURL: {org_url}")

    s_depts, s_total = fetch_department_list_from_site_v2(org_url, print)
    p_depts, p_total = fetch_department_list_from_site_playwright(org_url, print)

    s_depts = s_depts or []
    p_depts = p_depts or []

    s_set = _to_key_set(s_depts)
    p_set = _to_key_set(p_depts)

    only_s = sorted(list(s_set - p_set))
    only_p = sorted(list(p_set - s_set))

    report = {
        "portal": cfg["Name"],
        "org_list_url": org_url,
        "selenium": {
            "departments": len(s_depts),
            "estimated_tenders": int(s_total or 0),
        },
        "playwright": {
            "departments": len(p_depts),
            "estimated_tenders": int(p_total or 0),
        },
        "comparison": {
            "common_department_keys": len(s_set.intersection(p_set)),
            "only_in_selenium": len(only_s),
            "only_in_playwright": len(only_p),
            "sample_only_in_selenium": only_s[:10],
            "sample_only_in_playwright": only_p[:10],
        },
    }

    print("\n=== ENGINE COMPARISON SUMMARY ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Saved report: {out_path}")


if __name__ == "__main__":
    main()
