# Per-Portal Data Integrity Testing Guide

## Overview

The Data Integrity Verification page now includes **per-portal metrics** to help you identify and fix data quality issues for specific portals.

## Features

### 🎯 Per-Portal Integrity Metrics Table

Each portal gets its own integrity score and detailed metrics:

| Metric | Description | What It Means |
|--------|-------------|---------------|
| **Portal Name** | Name of the tender portal | e.g., "West Bengal", "HP Tenders" |
| **Total Tenders** | Number of tenders from this portal | Higher is better (more data) |
| **Duplicates** | Duplicate groups (extra rows) | ✓ = none, badge = count |
| **Missing IDs** | Records without valid tender IDs | ✓ = none, badge = count |
| **Missing Dates** | Records without closing dates | ✓ = none, badge = count |
| **Score** | Integrity score (0-100) | Color-coded: green/orange/red |
| **Status** | Overall quality rating | Excellent/Good/Fair/Poor |

### 📊 Integrity Score Calculation (Per Portal)

Each portal's score starts at **100** and deducts points for issues:

```
Initial Score: 100

Duplicates:     -0 to -30 points (based on % of duplicate rows)
Missing IDs:    -0 to -40 points (based on % of missing IDs)
Missing Dates:  -0 to -20 points (based on % of missing dates)

Final Score: 0-100
```

**Status Ratings**:
- **95-100**: Excellent ✅ (Green badge)
- **85-94**: Good ✅ (Blue badge)
- **70-84**: Fair ⚠️ (Yellow badge)
- **0-69**: Poor ❌ (Red badge)

### 🔍 Portal Filter

Use the dropdown to:
- View **All Portals** - See all portals sorted by tender count
- Select **Specific Portal** - Focus on one portal's metrics

## Use Cases

### 1. **Before Public Export**

**Problem**: You want to export West Bengal tenders to the public website, but you're not sure if the data is clean.

**Solution**:
1. Go to `/integrity` page
2. Filter to "West Bengal" in the dropdown
3. Check the integrity score:
   - **95+**: Safe to export ✅
   - **85-94**: Review warnings, probably safe ⚠️
   - **70-84**: Fix duplicates/missing data before export ⚠️
   - **<70**: Do NOT export until cleaned ❌

### 2. **Identify Problematic Portals**

**Problem**: Some portals have scraping issues, but you don't know which ones.

**Solution**:
1. Go to `/integrity` page
2. Sort by "Status" column
3. Portals with "Poor" or "Fair" status need attention
4. Click "Run Cleanup" to fix duplicates automatically
5. Re-scrape portals with high missing data counts

### 3. **Compare Portal Quality**

**Problem**: You want to know which portals have the best/worst data quality.

**Solution**:
1. Go to `/integrity` page
2. View "All Portals" (default)
3. Compare integrity scores:
   - **Excellent portals**: Use as reference for scraping config
   - **Poor portals**: May need portal-specific fixes or config adjustments

### 4. **Validate After Scraping**

**Problem**: Just finished scraping a portal, want to verify data integrity.

**Solution**:
1. Go to `/integrity` page
2. Click "Re-check" to refresh metrics
3. Filter to the portal you just scraped
4. Verify:
   - Total tenders matches expected count
   - No duplicates (✓ in Duplicates column)
   - No missing IDs (✓ in Missing IDs column)
   - Score is 95+ (Excellent)

### 5. **Track Improvement Over Time**

**Problem**: You've run cleanup scripts and re-scraped. Did it help?

**Solution**:
1. **Before cleanup**: Note portal scores (e.g., "West Bengal: 72")
2. Run cleanup script (click "Run Cleanup")
3. Re-scrape if needed
4. **After cleanup**: Click "Re-check"
5. Compare new scores (e.g., "West Bengal: 98")
6. Improvement = Success! ✅

## SQL Queries Behind the Scenes

The per-portal metrics use these SQL queries:

### Duplicates Per Portal
```sql
SELECT COUNT(*) as duplicate_groups
FROM (
    SELECT COUNT(*) as c
    FROM tenders
    WHERE portal_name = 'West Bengal'
      AND tender_id_extracted IS NOT NULL
    GROUP BY tender_id_extracted
    HAVING c > 1
)
```

### Missing IDs Per Portal
```sql
SELECT COUNT(*) as missing_ids
FROM tenders
WHERE portal_name = 'West Bengal'
  AND (
      tender_id_extracted IS NULL 
      OR TRIM(tender_id_extracted) = ''
      OR LOWER(tender_id_extracted) IN ('nan', 'none', 'null', 'na', 'n/a', '-')
  )
```

### Missing Dates Per Portal
```sql
SELECT COUNT(*) as missing_dates
FROM tenders
WHERE portal_name = 'West Bengal'
  AND (closing_date IS NULL OR TRIM(closing_date) = '')
```

## Common Scenarios & Solutions

### Scenario 1: Portal has duplicates but good score (90+)

**Cause**: Small number of duplicates relative to total tenders  
**Action**: Run cleanup script to remove them (click "Run Cleanup")  
**Impact**: Score may increase to 95-100 (Excellent)

### Scenario 2: Portal has poor score (<70) with many missing IDs

**Cause**: Scraping failed or portal structure changed  
**Action**: 
1. Check scraper logs for errors
2. Update portal configuration in base_urls.csv
3. Re-scrape the portal
4. Verify score improves

### Scenario 3: Portal has missing closing dates

**Cause**: Portal doesn't publish closing dates, or data extraction failed  
**Action**:
1. Check a few sample tenders on the portal website
2. If dates exist: Fix scraper selector for closing_date
3. If dates don't exist: Expected behavior (some portals don't have dates)

### Scenario 4: All portals show "No portal metrics available"

**Cause**: Integrity check hasn't run yet  
**Action**: Click "Re-check" button to analyze database

## Best Practices

### ✅ Do's

- **Check before export**: Always verify portal score ≥95 before public export
- **Run cleanup regularly**: Weekly cleanup keeps duplicates low
- **Re-check after scraping**: Verify data quality immediately after scraping
- **Compare portals**: Use scores to identify configuration issues
- **Track trends**: Note portal scores over time to detect regressions

### ❌ Don'ts

- **Don't export poor-quality portals**: Score <85 may contain bad data
- **Don't ignore warnings**: "Fair" status means action needed soon
- **Don't cleanup without backup**: "Run Cleanup" creates backup, but verify it exists
- **Don't assume all portals are equal**: Each portal may have different quality

## Integration with Existing Tools

### 1. **Excel Export** (Portal Management page)
- Check portal integrity score **before** exporting
- Only export portals with "Excellent" or "Good" status
- Warn users if exporting "Fair" or "Poor" portals

### 2. **Scraping Control** (Scraping page)
- After scraping completes, check portal integrity
- If score dropped, investigate scraping logs
- Re-scrape if score is unexpectedly low

### 3. **Cleanup Scripts**
- Before cleanup: Note portal scores
- Run cleanup: `python tools/cleanup_tender_records.py`
- After cleanup: Re-check to verify improvement

### 4. **Data Visualization** (Data Viz page)
- Filter to high-quality portals (score ≥95) for accurate charts
- Exclude low-quality portals from trend analysis

## Technical Details

### Database Schema Requirements
- **tenders table**: portal_name, tender_id_extracted, closing_date columns
- **Indexes**: Index on portal_name for fast filtering

### Performance
- Full integrity check: ~1-3 seconds (50,000+ tenders)
- Per-portal metrics: Calculated in single query with subqueries
- Real-time filtering: Client-side (instant)

### Memory Usage
- Stores metrics for all portals in state
- Typical usage: <1MB for 30 portals
- Efficient: Only fetches metrics on "Re-check"

## Future Enhancements (Planned)

1. **Historical Tracking**: Chart portal scores over time
2. **Automated Alerts**: Email when portal score drops below threshold
3. **Export Portal Report**: PDF/Excel report of portal integrity
4. **Scheduled Checks**: Auto-run integrity check daily at midnight
5. **Portal Health Dashboard**: Real-time monitor with red/green indicators

## Conclusion

Per-portal integrity testing gives you **visibility** and **control** over data quality at the portal level. Use it to:

- ✅ Validate data before public export
- ✅ Identify problematic portals quickly
- ✅ Compare quality across portals
- ✅ Track improvement after cleanup
- ✅ Build confidence in your data

**Quick Start**: Go to `/integrity` → Click "Re-check" → Review portal scores → Take action on "Fair" or "Poor" portals

---

**Last Updated**: February 21, 2026  
**Version**: 2.3.5  
**Related**: [DATA_INTEGRITY_VERIFICATION.md](DATA_INTEGRITY_VERIFICATION.md), [CHANGELOG.md](CHANGELOG.md)
