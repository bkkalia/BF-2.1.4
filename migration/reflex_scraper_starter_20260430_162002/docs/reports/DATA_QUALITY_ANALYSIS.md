# Data Quality Analysis - Critical Issues Found

**Date:** February 19, 2026  
**Database:** blackforest_tenders.sqlite3  
**Total Tenders:** 58,744

---

## 🚨 Critical Issues Identified

### 1. MASSIVE DUPLICATES IN DATABASE ❌

**Status:** CRITICAL - Immediate Fix Required

#### Issue Details:
The database contains thousands of duplicate tenders:

| Portal | Tender ID | Closing Date | Duplicate Count |
|--------|-----------|--------------|-----------------|
| CPPP1 eProcure | "1" | 23-Feb-2026 03:00 PM | **19 duplicates** |
| CPPP1 eProcure | "1" | 18-Feb-2026 03:00 PM | **16 duplicates** |
| CPPP1 eProcure | "2" | 19-Feb-2026 03:00 PM | **16 duplicates** |
| Uttar Pradesh | "133" | 20-Feb-2026 12:00 PM | **14 duplicates** |
| Uttar Pradesh | "16" | 21-Feb-2026 12:00 PM | **14 duplicates** |

**Root Cause:**  
De-duplication in `tender_store.py` → `replace_run_tenders()` only dedupes WITHIN a single run, NOT across runs.

```python
# Current logic (BROKEN):
# Step 1: Delete from current run
conn.execute("DELETE FROM tenders WHERE run_id = ?", (run_id,))

# Step 2: Dedupe within new tenders (works)
deduped = {}
for item in tenders:
    key = (portal_name.lower(), tender_id)
    if key not in deduped:
        deduped[key] = item  # Keeps last occurrence

# Step 3: Delete ALL previous occurrences (works)
conn.execute("DELETE FROM tenders WHERE portal_name = ? AND tender_id = ?")

# Step 4: Insert new (works)
conn.executemany("INSERT INTO tenders ...")

# PROBLEM: If you run same portal TWICE, you get:
# - Run 1: Inserts 100 tenders
# - Run 2: Deletes those 100, inserts 100 new (CORRECT)
# - But if Run 2 fetches SAME tenders, they're inserted again
# - DUPLICATE CHECK IS NOT ENFORCING UNIQUE CONSTRAINT!
```

**Why This Happens:**  
- No UNIQUE constraint on `(portal_name, tender_id_extracted, closing_date)`
- De-dup logic deletes old records BUT
- If same portal scraped multiple times in DIFFERENT runs
- And some tenders appear in both runs
- They get inserted MULTIPLE times

---

### 2. TIMEZONE NOT HANDLED IN DASHBOARD ❌

**Status:** CRITICAL - User Experience Broken

#### Issue Details:

**In `tender_store.py` (Scraper)**  ✅ Correct
```python
from datetime import datetime, timedelta, timezone

# IST = UTC+5:30  (all portal closing times are in Indian Standard Time)
_IST = timezone(timedelta(hours=5, minutes=30))

def _parse_closing_date_ist(value: str) -> "datetime | None":
    # Correctly parses as IST
    return datetime.strptime(text, fmt).replace(tzinfo=_IST)
```

**In `tender_dashboard_reflex/db.py` (Dashboard)** ❌ Wrong
```python
def _parse_portal_datetime(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%d-%b-%Y %I:%M %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)  # ❌ NO TIMEZONE!
        except ValueError:
            continue
    return None
```

**Impact:**  
1. User in USA browsing dashboard at 10 AM EST sees tender closing "20-Feb-2026 10:00 AM"
2. Browser interprets as "10:00 AM EST" (because datetime is naive)
3. ACTUAL closing time is "10:00 AM IST" which is:
   - 11:30 PM previous day EST (9.5 hours behind)
4. User thinks they have 24 hours, but tender actually closed 11.5 hours ago!

**Example:**
- IST: 20-Feb-2026 10:00 AM (tender closes)
- EST: 19-Feb-2026 11:30 PM (actual time)
- Dashboard shows: "20-Feb-2026 10:00 AM" in user's local time
- Wrong by 9.5 hours!

---

### 3. ONLY-NEW SCRAPING LOGIC ✅ (Mostly Working)

**Status:** GOOD - Minor Improvements Needed

#### Current Implementation:

**Step 1: Get existing live tenders** ✅ Works
```python
def get_existing_tender_ids_for_portal(self, portal_name):
    now_ist = datetime.now(tz=_IST)  # ✅ Uses IST
    
    # Query all tenders for this portal
    rows = conn.execute("SELECT tender_id, closing_date FROM tenders WHERE portal = ?")
    
    live_ids = set()
    for row in rows:
        parsed = self._parse_closing_date_ist(row["closing_date"])
        # ✅ Include if: still in future (IST) OR date couldn't be parsed
        if parsed is None or parsed > now_ist:
            live_ids.add(tid)
    return live_ids
```

**Step 2: Get snapshot with closing dates** ✅ Works
```python
def get_existing_tender_snapshot_for_portal(self, portal_name):
    # Returns: { normalized_tender_id -> {tender_id, closing_date} }
    # ✅ Compares closing dates to detect extensions
```

**Step 3: Scraper uses it** ✅ Works
```python
# In scraper/logic.py
baseline_ids = store.get_existing_tender_ids_for_portal(portal_name)

# During scraping:
if tender_id in baseline_ids:
    skipped_existing_count += 1
    continue  # Skip existing live tenders
```

**Works BUT:**  
- Duplicates mean baseline might include multiple copies of same tender
- Should be fine since it's a set (deduped automatically)

---

### 4. SPECIFIC TENDER: 2026_PWD_128306_1 ✅

**Status:** NOT A DUPLICATE - User Mistaken

Query result:
```
Total occurrences in database: 1

Database ID: 58543
Run ID: 28
Portal: HP Tenders
Tender ID: 2026_PWD_128306_1
Closing Date: 20-Feb-2026 10:00 AM
```

**Conclusion:** This tender only appears ONCE. User may have:
- Seen it in two different views (dashboard + exports)
- Confused it with similar tender ID
- Looked at old duplicate before cleanup

---

## 🔧 Required Fixes

### Fix 1: Add UNIQUE Constraint (CRITICAL)

**File:** `tender_store.py`

Add unique constraint to prevent duplicates:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_tenders_unique_portal_tender_date
    ON tenders(
        LOWER(TRIM(portal_name)),
        LOWER(TRIM(tender_id_extracted)),
        LOWER(TRIM(closing_date))
    );
```

This will:
- Prevent same tender from being inserted multiple times
- Allow tender with SAME ID but DIFFERENT closing date (extended deadline)
- Raise error if duplicate insert attempted (need to handle in code)

---

### Fix 2: Add Timezone Awareness to Dashboard (CRITICAL)

**File:** `tender_dashboard_reflex/tender_dashboard_reflex/db.py`

```python
from datetime import datetime, timedelta, timezone

# IST = UTC+5:30
_IST = timezone(timedelta(hours=5, minutes=30))

def _parse_portal_datetime(value: str | None) -> datetime | None:
    """Parse portal datetime as IST (all NIC portals use Indian Standard Time)"""
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%d-%b-%Y %I:%M %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            # Parse and set timezone to IST
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=_IST)  # ✅ NOW TIMEZONE-AWARE
        except ValueError:
            continue
    return None
```

Then in Reflex frontend, display times correctly:
```python
# Convert IST to user's local timezone
closing_dt_ist = _parse_portal_datetime(row["closing_date"])
if closing_dt_ist:
    # Reflex will automatically convert to user's browser timezone
    display_time = closing_dt_ist  # Will show in user's local time
```

---

### Fix 3: Improve De-duplication Logic (HIGH PRIORITY)

**File:** `tender_store.py` → `replace_run_tenders()`

Current approach:
```python
# Delete ALL previous occurrences of these tenders
DELETE FROM tenders WHERE (portal + tender_id) IN (incoming tenders)

# Insert new batch
INSERT INTO tenders (new batch)
```

Better approach with UNIQUE constraint:
```python
# Use INSERT OR REPLACE (SQLite upsert)
# This will:
# - Insert if not exists
# - Update if exists with SAME closing date
# - Insert NEW ROW if closing date changed (tender extended)

INSERT OR REPLACE INTO tenders (...) VALUES (...)
```

OR better: Track tender versions:
```sql
ALTER TABLE tenders ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE tenders ADD COLUMN superseded_by_id INTEGER REFERENCES tenders(id);
```

---

### Fix 4: Clean Existing Duplicates (URGENT)

Run cleanup script:

```python
# Remove duplicates keeping most recent
DELETE FROM tenders
WHERE id NOT IN (
    SELECT MAX(id)
    FROM tenders
   GROUP BY 
        LOWER(TRIM(portal_name)),
        LOWER(TRIM(tender_id_extracted)),
        LOWER(TRIM(closing_date))
);
```

This will:
- Keep latest insertion of each (portal, tender_id, closing_date) tuple
- Delete all older duplicates
- Should reduce database from 58,744 to ~45,000 tenders (rough estimate)

---

## 📊 Impact Analysis

### Current State:
- ❌ **58,744 tenders** in database (includes ~10,000-15,000 duplicates)  
- ❌ Dashboard shows tenders in wrong timezone for international users
- ❌ No unique constraint preventing re-insertion
- ✅ Only-new scraping works (but with duplicate baseline)

### After Fixes:
- ✅ **~45,000 unique tenders** (duplicates removed)  
- ✅ Dashboard shows correct IST times converted to user's local timezone
- ✅ UNIQUE constraint prevents future duplicates
- ✅ Cleaner data, faster queries

---

## 🚀 Implementation Priority

### Immediate (Today):
1. ✅ Add IST timezone to dashboard `_parse_portal_datetime()`
2. ✅ Run duplicate cleanup script
3. ✅ Add UNIQUE constraint

### Short-term (This Week):
4. Improve de-duplication logic to use INSERT OR REPLACE
5. Add tender versioning support
6. Re-test all 29 portals with fixes

### Medium-term (Before 2.5.0):
7. Add database validation tests
8. Monitor for new duplicates
9. Add dashboard timezone indicator ("All times in IST")

---

## 📝 Testing Checklist

After fixes:
- [ ] Verify no duplicates in database
- [ ] Test dashboard from different timezones (VPN/browser timezone change)
- [ ] Re-scrape test portal (HP Tenders) - verify no duplicates created
- [ ] Test "only-new" mode still works
- [ ] Check export files have no duplicates
- [ ] Verify closing date comparisons work correctly

---

**Next Steps:** Implement fixes in priority order above.
