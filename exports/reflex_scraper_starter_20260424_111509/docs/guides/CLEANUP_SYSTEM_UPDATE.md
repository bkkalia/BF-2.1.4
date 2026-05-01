# Auto-Cleanup System - UPDATED ✅

## Summary of Changes

Based on your strategic feedback, the cleanup system has been redesigned with **smart resume detection** and a **24-hour threshold** for maximum safety.

## Key Improvements

### 1. **24-Hour Threshold** (Changed from 2 hours)
- ✅ Much safer - won't kill slow-running portals
- ✅ Prevents false positives on large scrapes
- ✅ Default in both CLI and API modules

### 2. **Smart Resume Detection**
- ✅ Checks for checkpoint files before cleaning
- ✅ Distinguishes "resumable" vs "dead" runs
- ✅ Preserves runs with progress or checkpoint data
- ✅ New function: `is_run_resumable()`

### 3. **Pre-Scrape Check** (BEST INTEGRATION)
- ✅ New function: `check_portal_resume(portal_name)`
- ✅ Call BEFORE starting any portal scrape
- ✅ Automatically detects:
  - No active run → Start new scrape
  - Resumable run → Resume with checkpoint
  - Dead run → Clean and start fresh
  - Recent run → Wait or manual inspection

### 4. **Removed Startup Cleanup** (TOO RISKY)
- ❌ `startup_cleanup()` function deprecated
- ✅ Reason: Server restart shouldn't kill legitimate runs
- ✅ Use pre-scrape check instead

### 5. **New Helper Functions**
```python
# Check if checkpoint file exists
check_checkpoint_exists(portal_name, started_at)

# Determine if run can be resumed
is_run_resumable(run_dict)

# Pre-scrape check for portal
check_portal_resume(portal_name)

# Get detailed summary with resume info
get_stuck_run_summary()
```

---

## How to Use

### ⭐ RECOMMENDED: Pre-Scrape Check

Add this to your scraping workflow **before** starting any portal:

```python
from cleanup_service import check_portal_resume, cleanup_run

def start_portal_scrape(portal_name):
    """Call before starting portal scrape."""
    
    # Check for existing run
    check = check_portal_resume(portal_name)
    
    if not check['has_running']:
        # No active run - safe to start
        start_new_scrape(portal_name)
        return
    
    # Active run exists - decide action
    if check['action'] == 'resume':
        # Resume with checkpoint
        print(f"Resuming run #{check['run_id']}")
        resume_scrape(portal_name, check['run_id'])
        
    elif check['action'] == 'cleanup':
        # Old dead run - clean and start fresh
        print(f"Cleaning old run #{check['run_id']}")
        cleanup_run(check['run_id'])
        start_new_scrape(portal_name)
        
    elif check['action'] == 'wait':
        # Recent run, might still be starting
        print(f"Waiting for recent run #{check['run_id']}")
        # Wait or defer to user
```

### Manual Cleanup (CLI)

```bash
# Check what would be cleaned (24-hour threshold)
python cleanup_stuck_runs.py --dry-run

# Auto cleanup (24-hour threshold)
python cleanup_stuck_runs.py --auto

# Custom threshold (48 hours)
python cleanup_stuck_runs.py --auto --age-hours 48

# Show detailed summary with resume info
python cleanup_service.py
```

### Dashboard Integration

**Manual Button (Required):**

```python
from cleanup_service import get_stuck_run_summary, cleanup_run

class DashboardState(rx.State):
    def manual_cleanup(self):
        """Show resumable vs dead runs, clean dead ones."""
        summary = get_stuck_run_summary()
        
        print(f"Total stuck: {summary['total_stuck']}")
        print(f"  Resumable: {summary['resumable_count']}")
        print(f"  Dead: {summary['dead_count']}")
        
        # Only clean dead runs
        cleaned = 0
        for run in summary['dead_runs']:
            if cleanup_run(run['id']):
                cleaned += 1
        
        return f"Cleaned {cleaned} dead runs, {summary['resumable_count']} resumable preserved"
```

---

## What Changed in Code

### `cleanup_service.py`
- ✅ `DEFAULT_AGE_THRESHOLD_HOURS = 24.0` (was 2.0)
- ✅ Added `CHECKPOINT_DIR` constant
- ✅ Added `check_checkpoint_exists()` function
- ✅ Added `is_run_resumable()` function  
- ✅ Added `check_portal_resume()` function (pre-scrape check)
- ✅ Updated `get_stuck_runs()` to include resume info
- ✅ Added `get_stuck_run_summary()` function
- ❌ Removed `startup_cleanup()` (deprecated)

### `cleanup_stuck_runs.py`
- ✅ Changed default threshold: `age_threshold_hours=24` (was 2)
- ✅ Updated argparse default: `default=24.0` (was 2.0)
- ✅ Updated help text to show 24.0 as default

### `AUTO_CLEANUP_GUIDE.md`
- ✅ Updated all threshold references from 2h → 24h
- ✅ Added "Pre-Scrape Check" as recommended option
- ✅ Removed startup cleanup recommendations
- ✅ Added resume detection documentation
- ✅ Updated all code examples with new thresholds
- ✅ Added best practices section

### New Files Created
- ✅ `example_pre_scrape_check.py` - Working example of pre-scrape integration

---

## Testing

All components tested and working:

```bash
# ✅ CLI tool with 24-hour threshold
python cleanup_stuck_runs.py --dry-run

# ✅ Service module with resume detection
python cleanup_service.py

# ✅ Pre-scrape check example
python example_pre_scrape_check.py
```

Current status: **0 stuck runs** (all cleaned previously)

---

## Next Steps

1. **Integrate pre-scrape check** into your scraping workflow
   - Add `check_portal_resume()` call before each `start_portal()`
   - Handle 'resume', 'cleanup', and 'wait' actions

2. **Add manual cleanup button** to dashboard
   - Show stuck run count with resumable/dead breakdown
   - Button to clean dead runs only

3. **Test with real checkpoint files**
   - Create test checkpoint in `data/checkpoints/`
   - Verify resume detection works correctly

4. **Monitor effectiveness**
   - Track how often pre-scrape detects resumable runs
   - Verify 24-hour threshold prevents false positives

---

## Files Modified

- ✅ `cleanup_service.py` - Enhanced with resume detection
- ✅ `cleanup_stuck_runs.py` - Updated 24-hour threshold
- ✅ `AUTO_CLEANUP_GUIDE.md` - Complete rewrite with new strategy
- ✅ `example_pre_scrape_check.py` - New example file

## Your Feedback Incorporated

✅ "On-startup is risky" → Removed startup_cleanup()
✅ "24 hours better than 2" → Changed all thresholds to 24h
✅ "Need to understand if stuck or resumable" → Added checkpoint detection
✅ "Pre-scrape is good" → Made it the recommended option
✅ "Manual force required" → Documented manual button integration

---

## Questions?

- How do you want to integrate `check_portal_resume()` in your scraper?
- Should I add the manual cleanup button to the dashboard UI now?
- Do you want to test the resume detection with a sample checkpoint file?
