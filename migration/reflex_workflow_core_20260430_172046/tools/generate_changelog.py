#!/usr/bin/env python3
r"""
Generate/update CHANGELOG.md dates from local git history and file mentions.

Usage:
    python tools\generate_changelog.py

Notes:
- This runs git commands locally; must be executed inside the repository.
- The script makes a backup: CHANGELOG.md.bak.DATE
"""
import subprocess
import re
import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

def run_git(args):
    try:
        res = subprocess.run(["git"] + args, cwd=REPO_ROOT, capture_output=True, text=True)
        return res.stdout.strip()
    except Exception:
        return ""

def find_date_for_version(version):
    # Try to find a commit that mentions the version string
    grep = run_git(["log", "--grep", f"Version {version}", "--pretty=format:%ad", "--date=short", "-n", "1"])
    if grep:
        return grep.splitlines()[0].strip()
    # Try to find a commit that added/changed files that contain the version string
    grep2 = run_git(["grep", "-n", version])
    if grep2:
        first_file = grep2.splitlines()[0].split(":", 1)[0]
        file_date = run_git(["log", "-1", "--pretty=format:%ad", "--date=short", "--", first_file])
        if file_date:
            return file_date.strip()
    # Try searching commits that contain the version number anywhere
    search = run_git(["log", "--pretty=format:%ad %s", "--date=short", "--all"])
    for line in search.splitlines():
        if version in line:
            return line.split()[0]
    return None

def update_changelog_dates(contents, replacements):
    # Replace headings like: ## Version 2.1.4 (January 15, 2025)
    def repl(match):
        ver = match.group(1)
        current = match.group(2)
        new_date = replacements.get(ver)
        if new_date:
            return f"## Version {ver} ({new_date})"
        return match.group(0)
    return re.sub(r"##\s+Version\s+([\d\.]+)\s*\(([^)]*)\)", repl, contents)

def main():
    if not (REPO_ROOT / ".git").exists():
        print("ERROR: This directory is not a git repository (no .git). Run this script from the project root.")
        sys.exit(1)
    if not CHANGELOG.exists():
        print("ERROR: CHANGELOG.md not found at:", CHANGELOG)
        sys.exit(1)

    text = CHANGELOG.read_text(encoding="utf-8")
    versions = re.findall(r"##\s+Version\s+([\d\.]+)\s*\(", text)
    if not versions:
        print("No versions found in CHANGELOG.md headings. Nothing to update.")
        return

    replacements = {}
    for ver in sorted(set(versions), reverse=True):
        print(f"Inferring date for Version {ver} ...", end=" ")
        date = find_date_for_version(ver)
        if not date:
            # fallback: file modification time for files that mention the version
            matches = run_git(["grep", "-n", ver])
            if matches:
                f = matches.splitlines()[0].split(":",1)[0]
                try:
                    mtime = Path(REPO_ROOT / f).stat().st_mtime
                    date = datetime.utcfromtimestamp(mtime).strftime("%Y-%m-%d")
                except Exception:
                    date = None
        if date:
            print(date)
            replacements[ver] = date
        else:
            print("NOT FOUND")
    if not replacements:
        print("No dates discovered. Exiting without changes.")
        return

    # Backup
    bak = CHANGELOG.with_suffix(f".md.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}")
    CHANGELOG.replace(CHANGELOG.with_suffix(".md.tmp"))
    # read tmp, modify, then write backup + final
    tmp = REPO_ROOT / "CHANGELOG.md.tmp"
    contents = tmp.read_text(encoding="utf-8")
    new_contents = update_changelog_dates(contents, replacements)
    # write backup and final
    bak.write_text(contents, encoding="utf-8")
    CHANGELOG.write_text(new_contents, encoding="utf-8")
    tmp.unlink(missing_ok=True)
    print(f"\nCHANGELOG.md updated. Backup written to: {bak}")

if __name__ == "__main__":
    main()
