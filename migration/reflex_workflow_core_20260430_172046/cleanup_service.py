"""
Auto-cleanup service for stuck/zombie runs.

SMART DETECTION:
- Checks if run can be resumed (has checkpoint file)
- Distinguishes between "paused" and "truly stuck"
- 24-hour default threshold (not 2 hours - too aggressive)

INTEGRATION OPTIONS:
1. Pre-scrape check (BEST) - Before starting same portal
2. Periodic 24h cleanup (SAFE) - Background task
3. Manual button (REQUIRED) - Admin override
4. NO startup cleanup (TOO RISKY)

Usage:
    # Pre-scrape check
    from cleanup_service import check_portal_resume
    can_resume, run_id = check_portal_resume("Punjab")
    
    # Manual cleanup
    from cleanup_service import cleanup_if_needed
    cleaned = cleanup_if_needed(age_threshold_hours=24)
    
    # Get stuck count
    from cleanup_service import get_stuck_run_info
    stuck_info = get_stuck_run_info()
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import logging
import os
import json

logger = logging.getLogger(__name__)

# Configuration
DB_PATH = Path("database/blackforest_tenders.sqlite3")
CHECKPOINT_DIR = Path("data/checkpoints")
DEFAULT_AGE_THRESHOLD_HOURS = 24.0  # Changed from 2 to 24 hours
DEFAULT_MIN_IDLE_MINUTES = 30


def check_checkpoint_exists(portal_name, started_at):
    """
    Check if checkpoint file exists for this run.
    
    Args:
        portal_name: Name of the portal
        started_at: When run started (ISO format)
    
    Returns:
        tuple (exists: bool, checkpoint_path: Path or None, has_data: bool)
    """
    if not CHECKPOINT_DIR.exists():
        return False, None, False
    
    # Checkpoint filename format: {portal_slug}_checkpoint.json
    portal_slug = portal_name.lower().replace(" ", "_").replace("-", "_")
    checkpoint_path = CHECKPOINT_DIR / f"{portal_slug}_checkpoint.json"
    
    if not checkpoint_path.exists():
        return False, None, False
    
    try:
        # Check if checkpoint has actual data
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            has_tenders = len(data.get('tenders', [])) > 0
            has_depts = len(data.get('processed_departments', [])) > 0
            return True, checkpoint_path, (has_tenders or has_depts)
    except Exception as e:
        logger.warning(f"Error reading checkpoint {checkpoint_path}: {e}")
        return True, checkpoint_path, False  # Exists but can't read


def is_run_resumable(run_dict):
    """
    Determine if a run can be resumed.
    
    A run is resumable if:
    - Has checkpoint file with data, OR
    - Has made some progress (extracted > 0 or skipped > 0)
    
    Args:
        run_dict: Dict with run details (id, portal_name, started_at, extracted, skipped)
    
    Returns:
        tuple (resumable: bool, reason: str)
    """
    # Check for progress
    extracted = run_dict.get('extracted_total_tenders') or 0
    skipped = run_dict.get('skipped_existing_total') or 0
    has_progress = extracted > 0 or skipped > 0
    
    if has_progress:
        return True, f"Has progress ({extracted} extracted, {skipped} skipped)"
    
    # Check for checkpoint
    checkpoint_exists, checkpoint_path, has_data = check_checkpoint_exists(
        run_dict['portal_name'],
        run_dict['started_at']
    )
    
    if checkpoint_exists and has_data:
        return True, f"Has checkpoint with data at {checkpoint_path}"
    
    if checkpoint_exists and not has_data:
        return False, "Checkpoint exists but empty"
    
    return False, "No checkpoint and no progress"


def check_portal_resume(portal_name, age_threshold_hours=DEFAULT_AGE_THRESHOLD_HOURS):
    """
    Check if portal has a resumable run before starting new scrape.
    
    This is the PRE-SCRAPE check.
    
    Args:
        portal_name: Portal to check
        age_threshold_hours: How old before considering stuck
    
    Returns:
        dict with:
            'has_running': bool - Has active run?
            'run_id': int or None - ID of running run
            'resumable': bool - Can be resumed?
            'reason': str - Why resumable/not
            'age_hours': float - How old is the run?
            'action': str - Recommended action ('resume', 'cleanup', 'start_new')
    """
    if not DB_PATH.exists():
        return {'has_running': False, 'action': 'start_new'}
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        
        query = """
            SELECT id, portal_name, started_at, status,
                   extracted_total_tenders, skipped_existing_total
            FROM runs
            WHERE portal_name = ?
              AND status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
        """
        
        cursor = conn.execute(query, (portal_name,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {'has_running': False, 'action': 'start_new'}
        
        run = dict(row)
        start_dt = datetime.fromisoformat(run['started_at'])
        age_hours = (datetime.now() - start_dt).total_seconds() / 3600
        
        resumable, reason = is_run_resumable(run)
        
        # Determine action
        if age_hours < age_threshold_hours:
            # Still within acceptable time - might still be running
            action = 'resume' if resumable else 'wait'
        else:
            # Old run
            action = 'resume' if resumable else 'cleanup'
        
        return {
            'has_running': True,
            'run_id': run['id'],
            'resumable': resumable,
            'reason': reason,
            'age_hours': age_hours,
            'started_at': run['started_at'],
            'action': action
        }
        
    except Exception as e:
        logger.error(f"Error checking portal resume: {e}")
        return {'has_running': False, 'action': 'start_new', 'error': str(e)}


def get_stuck_runs(age_threshold_hours=DEFAULT_AGE_THRESHOLD_HOURS, include_resume_info=True):
    """
    Find runs that appear stuck.
    
    Args:
        age_threshold_hours: How old before considering stuck
        include_resume_info: Add resumable status to each run
    
    Returns:
        list of dicts with run details (with 'resumable' and 'resume_reason' if include_resume_info=True)
    """
    if not DB_PATH.exists():
        logger.warning(f"Database not found: {DB_PATH}")
        return []
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        
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
        
        # Add resume info if requested
        if include_resume_info:
            for run in stuck_runs:
                resumable, reason = is_run_resumable(run)
                run['resumable'] = resumable
                run['resume_reason'] = reason
                
                # Calculate age
                start_dt = datetime.fromisoformat(run['started_at'])
                age_hours = (now - start_dt).total_seconds() / 3600
                run['age_hours'] = round(age_hours, 1)
        
        return stuck_runs
        
    except Exception as e:
        logger.error(f"Error finding stuck runs: {e}")
        return []


def cleanup_run(run_id, mark_as="Timeout - Auto-cleaned"):
    """
    Cleanup a single stuck run.
    
    Args:
        run_id: ID of run to cleanup
        mark_as: Status to set (default: "Timeout - Auto-cleaned")
    
    Returns:
        True if successful, False otherwise
    """
    if not DB_PATH.exists():
        logger.error(f"Database not found: {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        now = datetime.now().isoformat(timespec="seconds")
        
        conn.execute("""
            UPDATE runs
            SET 
                status = ?,
                completed_at = ?
            WHERE id = ?
        """, (mark_as, now, run_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Cleaned up stuck run {run_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error cleaning up run {run_id}: {e}")
        return False


def cleanup_stuck_runs(age_threshold_hours=DEFAULT_AGE_THRESHOLD_HOURS, silent=False):
    """
    Find and cleanup all stuck runs.
    
    Args:
        age_threshold_hours: Minimum age for stuck detection
        silent: If True, don't log individual cleanups
    
    Returns:
        Number of runs cleaned
    """
    stuck_runs = get_stuck_runs(age_threshold_hours)
    
    if not stuck_runs:
        if not silent:
            logger.info("No stuck runs found")
        return 0
    
    cleaned = 0
    for run in stuck_runs:
        if cleanup_run(run['id']):
            cleaned += 1
            if not silent:
                duration_hours = (datetime.now() - datetime.fromisoformat(run['started_at'])).total_seconds() / 3600
                logger.info(f"Cleaned stuck run: {run['portal_name']} ({duration_hours:.1f}h old)")
    
    logger.info(f"Auto-cleanup: {cleaned}/{len(stuck_runs)} stuck runs cleaned")
    return cleaned


def get_stuck_run_count(age_threshold_hours=DEFAULT_AGE_THRESHOLD_HOURS):
    """
    Get count of stuck runs without cleaning.
    
    Returns:
        Number of stuck runs found
    """
    stuck_runs = get_stuck_runs(age_threshold_hours)
    return len(stuck_runs)


def cleanup_if_needed(age_threshold_hours=DEFAULT_AGE_THRESHOLD_HOURS):
    """
    Convenience function - cleanup if stuck runs exist.
    
    Returns:
        Number of runs cleaned (0 if none found)
    """
    count = get_stuck_run_count(age_threshold_hours)
    if count > 0:
        return cleanup_stuck_runs(age_threshold_hours, silent=True)
    return 0


def get_stuck_run_summary():
    """
    Get detailed summary of stuck runs with resume info.
    
    Returns:
        dict with:
            'total_stuck': int
            'resumable_count': int
            'dead_count': int
            'runs': list of dicts with full details
    """
    stuck_runs = get_stuck_runs(include_resume_info=True)
    
    resumable = [r for r in stuck_runs if r.get('resumable', False)]
    dead = [r for r in stuck_runs if not r.get('resumable', False)]
    
    return {
        'total_stuck': len(stuck_runs),
        'resumable_count': len(resumable),
        'dead_count': len(dead),
        'runs': stuck_runs,
        'resumable_runs': resumable,
        'dead_runs': dead
    }


# DO NOT USE startup_cleanup() - TOO RISKY!
# If server restarts, legitimate slow runs would be killed.
# Use check_portal_resume() before starting new scrapes instead.
#
# def startup_cleanup():
#     """DEPRECATED - DO NOT USE - Too risky if server restarts"""
#     pass


# Background task wrapper for async contexts
async def async_cleanup_task():
    """
    Async wrapper for background cleanup tasks.
    
    Can be called periodically from Reflex dashboard.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, cleanup_if_needed)


if __name__ == '__main__':
    # Quick test - show stuck run summary
    logging.basicConfig(level=logging.INFO)
    
    summary = get_stuck_run_summary()
    print(f"\n=== Stuck Run Summary ===")
    print(f"Total stuck: {summary['total_stuck']}")
    print(f"  Resumable: {summary['resumable_count']}")
    print(f"  Dead: {summary['dead_count']}")
    
    if summary['runs']:
        print(f"\nDetails:")
        for run in summary['runs']:
            status_icon = "✓" if run['resumable'] else "✗"
            print(f"  {status_icon} Run #{run['id']} - {run['portal_name']}")
            print(f"    Started: {run['started_at']}")
            print(f"    Age: {run['age_hours']}h")
            print(f"    Resume: {run['resume_reason']}")
    
    # Only cleanup non-resumable runs
    if summary['dead_count'] > 0:
        print(f"\nCleaning {summary['dead_count']} dead run(s)...")
        for run in summary['dead_runs']:
            if cleanup_run(run['id']):
                print(f"  ✓ Cleaned run #{run['id']} - {run['portal_name']}")

