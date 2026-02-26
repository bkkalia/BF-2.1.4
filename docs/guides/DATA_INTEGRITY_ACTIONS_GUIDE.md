# Data Integrity Actions Guide

## Overview

The Data Integrity Verification page (`/integrity`) now includes **actionable tools** to clean, export, and validate your tender data directly from the dashboard. This transforms the page from a monitoring tool into a **complete data quality management system**.

---

## 🎯 Quick Reference

### **Action Buttons**

| Button | Icon | Location | Purpose | When to Use |
|--------|------|----------|---------|-------------|
| **Details** | 👁️ | Each portal row | View detailed problematic records | Before cleanup to see exactly what's wrong |
| **Clean Duplicates** | 🗑️ | Each portal row (if duplicates exist) | Remove duplicate tender IDs | Portal has duplicate badge (orange) |
| **Remove Invalid** | ❌ | Each portal row (if invalid data exists) | Delete records with missing/invalid IDs or dates | Portal has missing IDs/dates badges (red/orange) |
| **Export Issues** | 📊 | Each portal row (if issues exist) | Download problematic records to Excel | Manual review or external analysis needed |
| **Fix All Issues** | 🔧 | Page header | Clean all problems across ALL portals | Database-wide cleanup required |
| **Re-check** | 🔄 | Page header | Run integrity check again | After cleanup to verify results |
| **Run Cleanup** | 🗑️ | Page header | Execute legacy cleanup script | Alternative to new action buttons |

---

## 📋 Features by Category

### **1. Per-Portal Actions** (Table Row Buttons)

#### 👁️ **View Details**
- **Purpose**: See exactly which records have problems
- **Opens**: Tabbed modal with three tabs:
  - **Duplicates**: Tender IDs that appear multiple times
  - **Invalid IDs**: Records with NULL, empty, or placeholder tender IDs
  - **Missing Dates**: Records with NULL, empty, or placeholder closing dates
- **Limits**: Shows up to 100 records per category
- **Use Case**: 
  ```
  Before cleaning West Bengal portal:
  1. Click "Details" button
  2. Review Duplicates tab → See tender IDs with counts
  3. Review Invalid IDs tab → See which departments have bad data
  4. Review Missing Dates tab → See records without closing dates
  5. Decide whether to clean or investigate further
  ```

#### 🗑️ **Clean Duplicates**
- **Purpose**: Remove duplicate tender IDs, keeping the newest record
- **Process**:
  1. Click "Clean Duplicates" button
  2. **Preview dialog appears** showing:
     - Portal name
     - Action description
     - Exact count of records to delete
     - Backup confirmation
  3. Click "Confirm Cleanup" to proceed or "Cancel" to abort
- **Safety**: 
  - ✅ Automatic backup created before deletion
  - ✅ Keeps newest record (highest ID) for each tender ID
  - ✅ Cannot be executed without confirmation
- **Use Case**:
  ```
  Kerala has 3 duplicate groups (11 rows):
  1. Click "Clean Duplicates"
  2. Preview: "Will delete 8 duplicate tender(s), keeping newest"
  3. Confirm
  4. Result: 3 tenders remain (1 per unique tender ID)
  ```

#### ❌ **Remove Invalid Records**
- **Purpose**: Delete records with missing or invalid required fields
- **Deletes Records With**:
  - Tender ID: NULL, empty, 'nan', 'none', 'null', 'n/a', 'na', '-', '--'
  - Closing Date: NULL, empty, 'nan', 'none', 'null', 'n/a', 'na', '-', '--'
- **Process**:
  1. Click "Remove Invalid" button
  2. Preview dialog shows count to delete
  3. Confirm or cancel
- **Safety**: Automatic backup before deletion
- **Use Case**:
  ```
  Haryana has 1523 records without closing dates:
  1. Click "Remove Invalid"
  2. Preview: "Will delete 1523 record(s) with missing IDs or dates"
  3. Confirm
  4. Result: Only records with valid IDs AND dates remain
  ```

#### 📊 **Export Issues**
- **Purpose**: Download problematic records to Excel for external review or manual fixing
- **Output**: Excel file with two sheets:
  - **Duplicates**: Tender IDs, counts, department, closing date
  - **Invalid Records**: Full records with missing/invalid data
- **Filename**: `portal_issues_<portal_name>_<timestamp>.xlsx`
- **Location**: `Tender84_Exports/` folder
- **Use Case**:
  ```
  Delhi has 994 duplicate rows - need manual investigation:
  1. Click "Export Issues"
  2. Open Excel file: portal_issues_Delhi_20260221_143022.xlsx
  3. Review Duplicates sheet to identify why duplicates exist
  4. Share with team for analysis before cleanup
  ```

---

### **2. Bulk Actions** (Header Buttons)

#### 🔧 **Fix All Issues**
- **Purpose**: Clean duplicates AND invalid records across ALL portals in one operation
- **Scope**: Entire database (all portals)
- **Process**:
  1. Click "Fix All Issues" button
  2. Preview dialog shows:
     - "🌐 All Portals"
     - "🗑️ Action: Fix All Issues (Duplicates + Invalid)"
     - Total count: e.g., "Will delete 1234 duplicate(s) and 567 invalid record(s). Total: 1801 records."
  3. Confirm or cancel
- **Order of Operations**:
  1. Creates timestamped backup
  2. Deletes duplicates (keeps newest)
  3. Deletes invalid records
  4. Commits transaction
  5. Re-runs integrity check
- **Safety**: 
  - ✅ Single backup covers all changes
  - ✅ Preview shows exact counts before execution
  - ✅ Disabled while check is running
- **Use Case**:
  ```
  Before exporting to tender84.com:
  1. Run Re-check to get latest metrics
  2. Click "Fix All Issues"
  3. Preview: "Will delete 150 duplicate(s) and 75 invalid record(s). Total: 225 records."
  4. Confirm
  5. Wait for completion
  6. Verify integrity score is now 95+ (Safe to Export)
  ```

#### 🔄 **Re-check**
- **Purpose**: Re-run integrity analysis to see current database status
- **When to Use**:
  - After any cleanup operation (to verify success)
  - After manual database edits
  - After importing new data
  - Periodically to monitor data quality
- **Process**: 
  1. Disables button with loading spinner
  2. Runs 7 SQL queries
  3. Updates all metrics and tables
  4. Re-enables button
- **Auto-run**: Automatically runs on page load

#### 🗑️ **Run Cleanup** (Legacy)
- **Purpose**: Execute old cleanup script (`tools/cleanup_tender_records.py`)
- **Difference from "Fix All Issues"**: 
  - Uses external script vs. built-in SQL
  - May have different logic for identifying issues
  - Less preview information
- **Recommendation**: Use "Fix All Issues" for better control and preview

---

## 🛡️ Safety Features

### **Automatic Backups**
- **When**: Before every cleanup action (per-portal or bulk)
- **Location**: `db_backups/` folder
- **Naming**: `backup_before_cleanup_<timestamp>.sqlite3`
- **Example**: `backup_before_cleanup_20260221_143022.sqlite3`
- **Restoration**:
  ```bash
  # If cleanup went wrong, restore from backup:
  copy db_backups\backup_before_cleanup_20260221_143022.sqlite3 database\blackforest_tenders.sqlite3
  ```

### **Preview Before Delete**
- **Every cleanup shows**:
  - Which portal (or "All Portals")
  - What action (Duplicates, Invalid, or All)
  - Exact count of records to delete
  - Detailed explanation
- **Cannot proceed** without clicking "Confirm Cleanup"
- **Cancel anytime** before confirmation

### **Transaction Safety**
- All SQL deletions wrapped in transactions
- Either all changes succeed or all are rolled back
- No partial cleanups

---

## 📊 Common Workflows

### **Workflow 1: Before Public Export** (Recommended)
**Goal**: Ensure data quality before uploading to tender84.com

1. **Navigate to `/integrity` page**
2. **Check overall score**:
   - ✅ Score ≥ 95: Safe to export
   - ⚠️ Score 85-94: Review warnings → Export may be okay
   - ❌ Score 70-84: Fix issues before export
   - 🚫 Score < 70: DO NOT export

3. **If score < 95**:
   ```
   a. Review portal table → Identify "Fair" or "Poor" portals
   b. Click "Details" on problematic portals → See specific issues
   c. Decision:
      - If issues are fixable → Click "Fix All Issues" (for all portals)
      - If specific portal has issues → Use per-portal buttons
      - If unsure → Click "Export Issues" → Manual review
   d. After cleanup → Click "Re-check"
   e. Verify score is now ≥ 95
   ```

4. **Export clean data**:
   - All portals with "Excellent" status are safe to export
   - Use existing export features with confidence

---

### **Workflow 2: Daily Data Quality Check**
**Goal**: Proactive monitoring to catch issues early

1. **Open dashboard at start of day**
2. **Navigate to `/integrity`** (auto-runs check)
3. **Review metrics**:
   - Check if duplicate count increased
   - Check if missing IDs/dates increased
   - Check if any portal changed from "Excellent" to "Good" or worse
4. **If new issues found**:
   ```
   a. Click "Details" on affected portal
   b. Investigate why new issues appeared (recent scrape? data source problem?)
   c. If data is bad → Use "Remove Invalid" or "Clean Duplicates"
   d. If scraper issue → Fix scraper logic
   ```

---

### **Workflow 3: Per-Portal Cleanup** (Targeted)
**Goal**: Fix one portal without touching others

1. **Identify problem portal** (e.g., "Haryana" has "Fair" status)
2. **Click "Details"** on Haryana row
3. **Review tabs**:
   - Duplicates: 1523 groups → Definitely need cleaning
   - Invalid IDs: 0 → No action needed
   - Missing Dates: 1523 records → Need removal
4. **Click "Clean Duplicates"** on Haryana row
   - Preview: "Will delete X duplicate tender(s)"
   - Confirm
5. **Click "Remove Invalid"** on Haryana row
   - Preview: "Will delete 1523 record(s) with missing dates"
   - Confirm
6. **Click "Re-check"**
7. **Result**: Haryana status changes from "Fair" (70) to "Excellent" (100)

---

### **Workflow 4: Investigate Before Cleanup** (Cautious)
**Goal**: Understand issues before deleting data

1. **Identify portal with issues** (e.g., "Delhi" has 994 duplicate rows)
2. **Click "Export Issues"** on Delhi row
3. **Open Excel file**: `portal_issues_Delhi_<timestamp>.xlsx`
4. **Review Duplicates sheet**:
   ```
   tender_id       | count | department_name          | closing_date
   ----------------|-------|--------------------------|---------------
   DDA/2024/001    | 5     | Delhi Development Auth   | 2024-03-15
   PWD/2024/123    | 3     | Public Works Department  | 2024-04-20
   ```
5. **Analyze patterns**:
   - Why 5 copies of DDA/2024/001?
   - Are they true duplicates or re-posted tenders?
   - Should we keep all or clean?
6. **Decision**:
   - If true duplicates → Click "Clean Duplicates" in dashboard
   - If re-posts → Investigate scraper logic
   - If unsure → Keep for now, flag for manual review

---

### **Workflow 5: Bulk Cleanup** (All Portals)
**Goal**: Clean entire database in one operation

1. **Click "Re-check"** to get latest metrics
2. **Review counts**:
   - Duplicate groups: 4914
   - Duplicate extra rows: 5323
   - Missing tender IDs: 0
   - Missing closing dates: 0
3. **Click "Fix All Issues"**
4. **Preview confirmation**:
   ```
   🌐 All Portals
   🗑️ Action: Fix All Issues (Duplicates + Invalid)
   Will delete 5323 duplicate(s) and 0 invalid record(s). Total: 5323 records.
   
   ✅ A backup will be created automatically.
   ⚠️ This will permanently delete 5323 record(s).
   ```
5. **Click "Confirm Cleanup"**
6. **Wait for completion** (check log shows progress)
7. **Verify results**:
   - Overall score increased
   - Duplicate groups = 0
   - All portals show "Excellent" status

---

## ⚠️ Important Notes

### **When to Use Each Action**

| Scenario | Recommended Action |
|----------|-------------------|
| Before public export | "Fix All Issues" → Verify score ≥95 |
| Single portal has issues | Per-portal "Clean Duplicates" or "Remove Invalid" |
| Want to investigate first | "Details" → Review → "Export Issues" |
| After manual database edits | "Re-check" |
| Unsure what's wrong | "Details" → Understand → Then act |
| Testing cleanup impact | "Export Issues" → Manual review → Compare before/after |

### **What Each Action Does NOT Do**

- **Clean Duplicates**: Does NOT remove invalid records (only duplicates)
- **Remove Invalid**: Does NOT remove duplicates (only invalid/missing data)
- **Export Issues**: Does NOT modify database (read-only)
- **Details**: Does NOT modify database (read-only)
- **Fix All Issues**: Does NOT fix scraper logic (only cleans existing data)

### **Best Practices**

✅ **DO**:
- Review "Details" before first cleanup on a portal
- Use "Export Issues" when you need to analyze or share data
- Run "Re-check" after cleanup to verify success
- Check backup folder after major cleanups
- Use "Fix All Issues" before public export
- Keep portal scores ≥ 95 for production data

❌ **DON'T**:
- Spam-click cleanup buttons (wait for completion)
- Delete backups (keep at least the last 5)
- Export data with score < 95 to tender84.com
- Ignore "Fair" or "Poor" status portals
- Clean without previewing first (always review counts)

---

## 🔗 Integration with Other Tools

### **Excel Export** (Existing Feature)
- **Before**: Export all portals → Manual cleanup in Excel
- **Now**: 
  1. Use "Fix All Issues" in `/integrity`
  2. Verify score ≥ 95
  3. Export clean data with confidence
  4. No manual Excel cleanup needed

### **Scraping Control** (Existing Feature)
- **If "Missing Dates" count is high**:
  1. Check if scraper is extracting closing dates correctly
  2. Use "Details" to see which departments are affected
  3. Adjust scraper config if needed
  4. Re-scrape affected portal
  5. Run "Re-check" to verify improvement

### **Data Visualization** (Existing Feature)
- **Before creating charts**:
  1. Check integrity score ≥ 90
  2. If score is low → Use "Fix All Issues"
  3. Re-run visualizations with clean data
  4. Charts will be more accurate

---

## 📈 Tracking Data Quality Over Time

### **Monthly Workflow**
```
Week 1: Run "Re-check" → Note baseline scores
Week 2: After all scraping → Run "Re-check" → Compare to Week 1
Week 3: Use "Fix All Issues" if score dropped
Week 4: Export to tender84.com with confidence (score ≥ 95)
```

### **Metrics to Monitor**
- Overall integrity score trend (should stay ≥ 95)
- Duplicate count trend (should stay low)
- Portal status distribution (aim for all "Excellent")
- Check log for cleanup history

---

## 🚀 Quick Start Examples

### **Example 1: New User - First Cleanup**
```
1. Open dashboard → Navigate to "Data Integrity"
2. Page auto-loads → See overall score: 91/100
3. Review portal table → See "Haryana" has "Fair" status (70/100)
4. Click "Details" on Haryana → See 1523 missing dates
5. Click "Export Issues" → Download Excel for review
6. After review → Click "Remove Invalid" → Confirm
7. Click "Re-check" → See Haryana is now "Excellent" (100/100)
8. Overall score increased to 96/100 → Safe to export!
```

### **Example 2: Experienced User - Routine Maintenance**
```
1. Navigate to `/integrity`
2. Click "Fix All Issues" → Confirm (5 second operation)
3. Click "Re-check" → Verify all portals are "Excellent"
4. Done! (No manual intervention needed)
```

### **Example 3: Data Analyst - Investigation**
```
1. Navigate to `/integrity`
2. Sort portals by score (lowest first)
3. For each "Fair" or "Poor" portal:
   a. Click "Details" → Analyze patterns
   b. Click "Export Issues" → Download for Tableau/Power BI
4. Share Excel files with team
5. After team review → Use cleanup buttons
```

---

## 📝 Summary

The Data Integrity Actions system transforms data quality management from a **reactive problem** (manual SQL queries, scripts) into a **proactive workflow** (visual monitoring, one-click cleanup, preview-before-delete).

**Key Benefits**:
- ✅ **Excel Replacement**: Confidence to use SQLite instead of manual Excel review
- ✅ **Multi-Portal Management**: Manage 10+ portals with ease
- ✅ **Safety First**: Backups + previews prevent accidental data loss
- ✅ **Export Confidence**: Verify data quality (score ≥95) before public upload
- ✅ **Time Savings**: Minutes instead of hours for cleanup operations
- ✅ **Visibility**: See exactly what's wrong, not just error counts

**Next Steps**:
1. Read this guide
2. Practice with "Details" button (read-only, safe to explore)
3. Try "Export Issues" (downloads Excel, no database changes)
4. When confident → Use cleanup buttons (always preview first!)
5. Bookmark `/integrity` page for daily monitoring

---

**See Also**:
- [DATA_INTEGRITY_VERIFICATION.md](DATA_INTEGRITY_VERIFICATION.md) - Technical details on verification mechanisms
- [PER_PORTAL_INTEGRITY_GUIDE.md](PER_PORTAL_INTEGRITY_GUIDE.md) - Per-portal metrics documentation
- [CHANGELOG.md](CHANGELOG.md) - Version 2.3.5 release notes
