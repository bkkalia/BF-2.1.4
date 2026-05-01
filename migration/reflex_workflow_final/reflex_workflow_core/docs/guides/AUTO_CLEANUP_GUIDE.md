# Auto-Cleanup System for Stuck Runs

## Overview

The auto-cleanup system prevents database pollution from zombie/stuck scraping runs that fail to complete properly. **Uses 24-hour threshold and checkpoint-based resume detection for safety.**

## Problem Solved

**Before:** Runs that crash, freeze, or are force-stopped remain in "running" status indefinitely, cluttering the database and making it hard to see actual active runs.

**After:** Stuck runs are automatically detected and marked as "Timeout - Auto-cleaned", freeing up the database while preserving any extracted data. **Resumable runs are preserved.**

---

## How It Works

### Detection Criteria

A run is considered "stuck" if **ALL** of these conditions are met:

1. **Status** = `"running"` in database
2. **Age** > **24 hours** (changed from 2 hours for safety)
3. **No Progress**:
   - `extracted_total_tenders` = 0 AND
   - `skipped_existing_total` = 0
   
   OR both are NULL
4. **No Checkpoint File** with data (resumable runs are preserved)

### Resume Detection (Smart Cleanup)

The system distinguishes between **resumable** and **dead** runs:

**Resumable Run** (preserved):
- Has checkpoint file with tender data, OR
- Has made progress (extracted > 0 or skipped > 0)

**Dead Run** (cleaned):
- No checkpoint file
- No progress (0 extracted, 0 skipped)
- Age > 24 hours

### What Happens During Cleanup

1. **Status Update**: `status` → `"Timeout - Auto-cleaned"`
2. **Completion Time**: `completed_at` → current timestamp
3. **Data Preserved**: Any extracted tenders remain in database
4. **Logging**: Event logged for audit trail
5. **Resumable runs**: Left untouched for manual resume

### Safety Measures

- ✅ **Never deletes data** - only marks status (unless explicitly requested)
- ✅ **24-hour threshold** - prevents false positives on slow portals
- ✅ **Resume detection** - checks for checkpoint files before cleaning
- ✅ **Progress check** - only cleans runs with zero progress
- ✅ **Preserves history** - run records kept for analysis
- ✅ **No startup cleanup** - server restart won't kill legitimate runs

---

## Usage Methods

### ⭐ RECOMMENDED: Pre-Scrape Check (BEST)

**This is the safest and most effective approach.** Check for resumable runs BEFORE starting new portal scrapes.

```python
from cleanup_service import check_portal_resume, cleanup_run

def start_portal_scrape(portal_name):
    """Called before starting portal scrape."""
    
    # Check if portal has active run
    check = check_portal_resume(portal_name)
    
    if not check['has_running']:
        # No active run - safe to start
        start_new_scrape(portal_name)
        return
    
    # Active run exists - check if resumable
    if check['action'] == 'resume':
        # Resume with checkpoint
        resume_scrape(portal_name, check['run_id'])
        
    elif check['action'] == 'cleanup':
        # Old dead run - clean and start fresh
        cleanup_run(check['run_id'])
        start_new_scrape(portal_name)
        
    elif check['action'] == 'wait':
        # Recent run, might still be starting
        log.warning(f"Portal {portal_name} has recent run - waiting")
```

**Why Pre-Scrape is Best:**
- ✅ Prevents duplicate runs on same portal
- ✅ Automatically resumes paused/crashed runs
- ✅ Only cleans truly dead runs
- ✅ No risk from server restarts
- ✅ Perfect integration point before scraping

See `example_pre_scrape_check.py` for full working example.

---

### 1. Manual Cleanup (Interactive)

```bash
# Show what would be cleaned (dry run)
python cleanup_stuck_runs.py --dry-run

# Interactive cleanup with prompts
python cleanup_stuck_runs.py

# Automatic cleanup (no prompts)
python cleanup_stuck_runs.py --auto

# Custom age threshold (48 hours instead of 24)
python cleanup_stuck_runs.py --auto --age-hours 48
```

---

### 2. Programmatic Usage (In Code)

```python
from cleanup_service import (
    get_stuck_run_summary,
    cleanup_run,
    check_portal_resume
)

# Get detailed summary with resume info
summary = get_stuck_run_summary()
print(f"Total stuck: {summary['total_stuck']}")
print(f"Resumable: {summary['resumable_count']}")
print(f"Dead: {summary['dead_count']}")

# Only cleanup dead runs
for run in summary['dead_runs']:
    cleanup_run(run['id'])
```

---

### 3. Dashboard Integration

**Manual Cleanup Button (Required):**

Add admin button to dashboard for manual intervention:

```python
class DashboardState(rx.State):
    stuck_count: int = 0
    
    def check_stuck_runs(self):
        """Update stuck run count."""
        summary = get_stuck_run_summary()
        self.stuck_count = summary['dead_count']
        return summary
    
    def manual_cleanup(self):
        """Force cleanup dead runs."""
        summary = get_stuck_run_summary()
        cleaned = 0
        for run in summary['dead_runs']:
            if cleanup_run(run['id']):
                cleaned += 1
        self.stuck_count = 0
        return f"Cleaned {cleaned} dead runs"
```

**Periodic Background Check (Optional):**

```python
# Only use with 24+ hour threshold
async def periodic_cleanup_task():
    """Run every 6-12 hours."""
    summary = get_stuck_run_summary()
    if summary['dead_count'] > 0:
        # Alert admin instead of auto-cleaning
        send_admin_alert(f"{summary['dead_count']} dead runs found")
```

---

### ⚠️ DO NOT USE: Startup Cleanup

**Startup cleanup is DISABLED** - too risky if server restarts frequently.

```python
# DEPRECATED - DO NOT USE
# from cleanup_service import startup_cleanup  # ← Removed

# Why not use startup cleanup:
# - Server restart would kill legitimate slow runs
# - 24+ hour runs are common for large portals
# - Use pre-scrape check instead
```

---

### 4. Scheduled Task (Windows)

Create a Windows Task Scheduler job to run daily:

```powershell
# Run daily at 3 AM
schtasks /create /tn "TenderCleanup" /tr "D:\Dev84\BF 2.1.4\.venv\Scripts\python.exe D:\Dev84\BF 2.1.4\cleanup_stuck_runs.py --auto" /sc daily /st 03:00
```

### 5. Before Starting New Scrape

```python
# In scraping_worker.py or similar
from cleanup_service import cleanup_if_needed

def start_scraping(portal_name):
    # Cleanup stuck runs before starting
    cleanup_if_needed()
    
    # Then start your scrape
    # ...
```

---

## Integration Points

### Option A: Dashboard Startup (Recommended)

**When:** Dashboard/CLI starts  
**Threshold:** 1 hour (aggressive)  
**Function:** `startup_cleanup()`

```python
# In tender_dashboard_reflex/scraping_worker.py
---

## Integration Options Summary

### ✅ Option A: Pre-Scrape Check (BEST - RECOMMENDED)

**When:** Before starting any portal scrape  
**Threshold:** 24 hours  
**Function:** `check_portal_resume(portal_name)`

**Why Best:**
- Prevents duplicate runs
- Auto-resumes paused scrapes
- Only cleans truly dead runs
- No risk from server restarts

```python
# In scraping_worker.py
from cleanup_service import check_portal_resume, cleanup_run

def start_portal(portal_name):
    check = check_portal_resume(portal_name)
    
    if check['action'] == 'resume':
        resume_scrape(portal_name, check['run_id'])
    elif check['action'] == 'cleanup':
        cleanup_run(check['run_id'])
        start_new_scrape(portal_name)
    else:
        start_new_scrape(portal_name)
```

### ✅ Option B: Manual Dashboard Button (REQUIRED)

**When:** User clicks "Clean Stuck Runs"  
**Threshold:** 24 hours (configurable)  
**Function:** `get_stuck_run_summary()` + `cleanup_run()`

**Why Required:**
- Admin override capability
- Shows resumable vs dead runs
- Full control and transparency

```python
# In dashboard state
from cleanup_service import get_stuck_run_summary, cleanup_run

class DashboardState(rx.State):
    def manual_cleanup(self):
        summary = get_stuck_run_summary()
        cleaned = 0
        for run in summary['dead_runs']:
            if cleanup_run(run['id']):
                cleaned += 1
        return f"Cleaned {cleaned}/{summary['dead_count']} dead runs"
```

### ⚠️ Option C: Periodic Background Task (OPTIONAL)

**When:** Every 6-12 hours  
**Threshold:** 24+ hours  
**Function:** `get_stuck_run_summary()` (alert only)

**Use only for monitoring:**

```python
# Alert admin instead of auto-cleaning
async def periodic_check():
    summary = get_stuck_run_summary()
    if summary['dead_count'] > 0:
        notify_admin(f"{summary['dead_count']} dead runs need cleanup")
```

### ❌ Option D: Startup Cleanup (REMOVED - TOO RISKY)

**Deprecated:** Server restart would kill legitimate runs.

**Use pre-scrape check instead.**

---

## Configuration

### Age Threshold

**Default:** 24 hours  
**Recommendation:**
- **Pre-scrape check:** 24 hours (balanced)
- **Manual cleanup:** 24-48 hours (your choice)
- **Periodic alerts:** 24+ hours (monitoring only)

```python
# Custom thresholds
check_portal_resume(portal_name, age_threshold_hours=48.0)  # 48 hours
get_stuck_run_summary()  # Uses 24 hours default
```

### Resume Detection  
**Future Enhancement:** Could add "last activity" timestamp

---

## Monitoring & Logging

### View Cleanup History

```sql
-- See all auto-cleaned runs
SELECT * FROM runs 
WHERE status LIKE '%Auto-cleaned%' 
ORDER BY completed_at DESC;

-- Count by portal
SELECT portal_name, COUNT(*) as cleaned_count
FROM runs 
WHERE status LIKE '%Auto-cleaned%'
GROUP BY portal_name;
```

### Enable Detailed Logging

```python
import logging
logging.basicConfig(level=logging.INFO)

from cleanup_service import cleanup_if_needed
cleaned = cleanup_if_needed()  # Will log details
```

---

## Safety & Recovery

### What If Cleanup Is Wrong?

Cleanup **never deletes** data by default. If a run was incorrectly cleaned:

1. **Data preserved:** All tenders remain in `tenders` table
2. **Status changeable:** Can manually update status back to "running" if needed
3. **History kept:** Run record remains for analysis

### Manual Recovery

```sql
-- Revert a cleaned run back to running (rare case)
UPDATE runs 
SET status = 'running', completed_at = NULL 
WHERE id = <run_id>;
```

### Delete Truly Failed Runs

If you want to remove runs completely:

```bash
# Interactive deletion (with confirmation)
python cleanup_stuck_runs.py

# Then choose option 2 (Delete all)
```

---

## Performance Impact

- **Overhead:** < 100ms per check
- **Database locks:** Minimal (quick SELECT + UPDATE)
- **Frequency:** Safe to run every 30 minutes
- **Scalability:** O(n) where n = number of stuck runs (typically 0-10)

---

## Recommended Setup

**For Production:**

1. **On startup:** `startup_cleanup()` (1-hour threshold)
2. **Periodic:** Every 30-60 minutes via background thread
3. **Pre-scrape:** Optional check before starting batch scrapes
4. **Manual:** Dashboard button for admin override

**Example Implementation:**

```python
# In main.py or dashboard startup
from cleanup_service import startup_cleanup
import threading
import time

# Startup cleanup
startup_cleanup()

# Background thread
def cleanup_loop():
    while True:
        time.sleep(1800)  # 30 min
        cleanup_if_needed()

threading.Thread(target=cleanup_loop, daemon=True).start()
```

---

## Testing

```bash
# Test without making changes
python cleanup_stuck_runs.py --dry-run

# Test with verbose logging
python cleanup_service.py

# Check current status
python -c "from cleanup_service import get_stuck_run_count; print(f'Stuck runs: {get_stuck_run_count()}')"
```

---

## Troubleshooting

### "No stuck runs found" but dashboard shows active runs

**Cause:** Runs may have extracted some tenders (not stuck, just slow)  
**Solution:** Check `extracted_total_tenders` - cleanup only targets zero-progress runs

### Cleanup not running

**Cause:** Database locked or threshold too high  
**Solution:** 
- Check database permissions
- Lower threshold: `--age-hours 12` (but keep ≥ 12 hours)
- Check logs for errors

### False positives (cleaning active runs)

**Cause:** Threshold too low or slow portal  
**Solution:**
- Use 24-48 hour threshold (current default: 24)
- Check for checkpoint files (resume detection)
- Use pre-scrape check instead of periodic cleanup

---

## Best Practices

1. **Always use pre-scrape check** before starting new portal scrapes
2. **24-hour minimum threshold** to avoid false positives
3. **Manual button in dashboard** for admin control
4. **Check resume status** before cleaning any run
5. **Never use startup cleanup** (too risky)
6. **Monitor but don't auto-clean** with periodic tasks

---

## Future Enhancements

- [x] Add resume detection via checkpoint files
- [x] 24-hour threshold for safety
- [x] Pre-scrape integration
- [ ] Dashboard UI showing stuck runs with resume status
- [ ] Email/notification when dead runs found
- [ ] More granular detection (department-level timeout)
- [ ] Configurable cleanup policies per portal
- [ ] Auto-resume capability in scraper

---

## Summary

**Quick Start:**
```bash
# One-time cleanup
python cleanup_stuck_runs.py --auto

# Check for stuck runs
python cleanup_service.py

# Test pre-scrape check
python example_pre_scrape_check.py
```

**Best Integration:**
```python
# RECOMMENDED: Pre-scrape check
from cleanup_service import check_portal_resume, cleanup_run

def start_portal(portal_name):
    check = check_portal_resume(portal_name)
    if check['action'] == 'resume':
        resume_scrape(portal_name, check['run_id'])
    elif check['action'] == 'cleanup':
        cleanup_run(check['run_id'])
        start_new_scrape(portal_name)
    else:
        start_new_scrape(portal_name)
```

**Manual Control:**
```python
# Dashboard button
from cleanup_service import get_stuck_run_summary, cleanup_run

summary = get_stuck_run_summary()
for run in summary['dead_runs']:
    cleanup_run(run['id'])
```

**Best Practice:**
- Run on startup (cleans old zombies)
- Run periodically (prevents accumulation)
- Monitor logs (verify working correctly)
- Keep threshold ≥ 2 hours (avoid false positives)
