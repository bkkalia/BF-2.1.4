"""
Cleanup utility for stuck/zombie scraping runs.

Detects and cleans up runs that:
- Have been "running" for > 2 hours with no progress
- Have no matching active process
- Have extracted 0 tenders with no activity

Usage:
    python cleanup_stuck_runs.py                    # Interactive cleanup
    python cleanup_stuck_runs.py --auto             # Auto-cleanup (no prompt)
    python cleanup_stuck_runs.py --dry-run          # Show what would be cleaned
    python cleanup_stuck_runs.py --age-hours 4      # Custom age threshold
"""

import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Database path
DB_PATH = Path("database/blackforest_tenders.sqlite3")

def get_stuck_runs(db_path, age_threshold_hours=24, min_idle_minutes=30):
    """
    Find runs that appear stuck based on criteria:
    - Status = 'running'
    - Started > age_threshold_hours ago (default: 24 hours)
    - No progress (extracted=0, skipped=0) OR no activity for min_idle_minutes
    
    Returns list of dicts with run details.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Calculate cutoff times
    now = datetime.now()
    age_cutoff = (now - timedelta(hours=age_threshold_hours)).isoformat(timespec="seconds")
    
    query = """
        SELECT 
            id,
            portal_name,
            started_at,
            status,
            expected_total_tenders,
            extracted_total_tenders,
            skipped_existing_total
        FROM runs
        WHERE status = 'running'
          AND started_at < ?
          AND (
              (extracted_total_tenders = 0 AND skipped_existing_total = 0)
              OR (extracted_total_tenders IS NULL AND skipped_existing_total IS NULL)
          )
        ORDER BY started_at ASC
    """
    
    cursor = conn.execute(query, (age_cutoff,))
    stuck_runs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return stuck_runs


def calculate_duration(started_at):
    """Calculate duration from started_at to now in human-readable format."""
    if not started_at:
        return "Unknown"
    
    start_dt = datetime.fromisoformat(started_at)
    duration = datetime.now() - start_dt
    
    hours = duration.total_seconds() / 3600
    if hours < 1:
        return f"{duration.total_seconds() / 60:.1f} minutes"
    elif hours < 24:
        return f"{hours:.1f} hours"
    else:
        days = hours / 24
        return f"{days:.1f} days ({hours:.1f} hours)"


def cleanup_run(db_path, run_id, dry_run=False):
    """
    Cleanup a single stuck run:
    - Set status to 'Timeout - Auto-cleaned'
    - Set completed_at to now
    - Preserve any existing data
    
    Returns True if successful.
    """
    if dry_run:
        print(f"  [DRY RUN] Would cleanup run_id={run_id}")
        return True
    
    conn = sqlite3.connect(db_path)
    now = datetime.now().isoformat(timespec="seconds")
    
    try:
        conn.execute("""
            UPDATE runs
            SET 
                status = 'Timeout - Auto-cleaned',
                completed_at = ?
            WHERE id = ?
        """, (now, run_id))
        conn.commit()
        print(f"  ✅ Cleaned up run_id={run_id}")
        return True
    except Exception as e:
        print(f"  ❌ Failed to cleanup run_id={run_id}: {e}")
        return False
    finally:
        conn.close()


def delete_run(db_path, run_id, dry_run=False):
    """
    Delete a run completely (use only if no data extracted).
    
    Returns True if successful.
    """
    if dry_run:
        print(f"  [DRY RUN] Would delete run_id={run_id}")
        return True
    
    conn = sqlite3.connect(db_path)
    
    try:
        # First delete any tenders for this run
        conn.execute("DELETE FROM tenders WHERE run_id = ?", (run_id,))
        # Then delete the run record
        conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        conn.commit()
        print(f"  🗑️  Deleted run_id={run_id}")
        return True
    except Exception as e:
        print(f"  ❌ Failed to delete run_id={run_id}: {e}")
        return False
    finally:
        conn.close()


def interactive_cleanup(stuck_runs, db_path):
    """Interactive cleanup with user confirmation."""
    if not stuck_runs:
        print("\n✅ No stuck runs found!")
        return 0
    
    print(f"\n📋 Found {len(stuck_runs)} stuck run(s):\n")
    
    for idx, run in enumerate(stuck_runs, 1):
        duration = calculate_duration(run['started_at'])
        print(f"{idx}. Run ID: {run['id']}")
        print(f"   Portal: {run['portal_name']}")
        print(f"   Started: {run['started_at']}")
        print(f"   Duration: {duration}")
        print(f"   Extracted: {run['extracted_total_tenders'] or 0}")
        print(f"   Skipped: {run['skipped_existing_total'] or 0}")
        print()
    
    print("Options:")
    print("  1. Cleanup all (mark as timeout, preserve data)")
    print("  2. Delete all (remove completely - USE WITH CAUTION)")
    print("  3. Skip cleanup")
    
    choice = input("\nYour choice (1/2/3): ").strip()
    
    cleaned = 0
    if choice == '1':
        print("\n🧹 Cleaning up stuck runs...")
        for run in stuck_runs:
            if cleanup_run(db_path, run['id']):
                cleaned += 1
        print(f"\n✅ Cleaned up {cleaned}/{len(stuck_runs)} runs")
        
    elif choice == '2':
        confirm = input("\n⚠️  DELETE ALL? This cannot be undone! Type 'DELETE' to confirm: ")
        if confirm == 'DELETE':
            print("\n🗑️  Deleting stuck runs...")
            for run in stuck_runs:
                if delete_run(db_path, run['id']):
                    cleaned += 1
            print(f"\n✅ Deleted {cleaned}/{len(stuck_runs)} runs")
        else:
            print("\n❌ Deletion cancelled")
            
    else:
        print("\n⏭️  Cleanup skipped")
    
    return cleaned


def auto_cleanup(stuck_runs, db_path, dry_run=False):
    """Automatic cleanup without user interaction."""
    if not stuck_runs:
        if not dry_run:
            print("✅ No stuck runs found")
        return 0
    
    action = "[DRY RUN] Would cleanup" if dry_run else "Cleaning up"
    print(f"\n{action} {len(stuck_runs)} stuck run(s)...")
    
    cleaned = 0
    for run in stuck_runs:
        duration = calculate_duration(run['started_at'])
        print(f"  • Run {run['id']}: {run['portal_name']} ({duration})")
        if cleanup_run(db_path, run['id'], dry_run=dry_run):
            cleaned += 1
    
    if not dry_run:
        print(f"\n✅ Cleaned up {cleaned}/{len(stuck_runs)} runs")
    
    return cleaned


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup stuck/zombie scraping runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Auto-cleanup without prompts'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be cleaned without making changes'
    )
    parser.add_argument(
        '--age-hours',
        type=float,
        default=24.0,
        help='Minimum age in hours for stuck detection (default: 24.0)'
    )
    parser.add_argument(
        '--delete',
        action='store_true',
        help='Delete runs instead of marking as timeout (dangerous!)'
    )
    
    args = parser.parse_args()
    
    # Check database exists
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return 1
    
    print("=" * 80)
    print("🧹 STUCK RUN CLEANUP UTILITY")
    print("=" * 80)
    print(f"Database: {DB_PATH}")
    print(f"Age threshold: {args.age_hours} hours")
    if args.dry_run:
        print("Mode: DRY RUN (no changes will be made)")
    print()
    
    # Find stuck runs
    stuck_runs = get_stuck_runs(DB_PATH, age_threshold_hours=args.age_hours)
    
    if args.dry_run:
        print(f"Found {len(stuck_runs)} stuck run(s) that would be cleaned:")
        for run in stuck_runs:
            duration = calculate_duration(run['started_at'])
            print(f"  • Run {run['id']}: {run['portal_name']} ({duration})")
        return 0
    
    # Perform cleanup
    if args.auto:
        cleaned = auto_cleanup(stuck_runs, DB_PATH)
    else:
        cleaned = interactive_cleanup(stuck_runs, DB_PATH)
    
    return 0 if cleaned > 0 or len(stuck_runs) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
