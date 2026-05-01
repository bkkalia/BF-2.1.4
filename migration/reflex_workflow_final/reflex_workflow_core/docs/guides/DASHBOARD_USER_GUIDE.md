# Tender Dashboard - User Guide

## Overview

The Tender Dashboard is a web-based interface for viewing and managing tender data scraped from various government portals. It provides two main pages:
1. **Dashboard** - Browse and search tenders with advanced filtering
2. **Portal Management** - Monitor portal health and manage bulk exports

Access the dashboard at `http://localhost:3600` after launching it from the GUI.

---

## Dashboard Page

### Features

#### 1. Tender Table
- **Real-time Data**: Displays tenders from the SQLite database
- **Pagination**: Navigate through large tender datasets efficiently
- **Sortable Columns**: Click column headers to sort
- **Status Indicators**: Visual badges for tender lifecycle status

#### 2. Advanced Filtering

##### Portal Filter
- **All Portals**: Shows tenders from all sources
- **Select Portal**: Filter by specific government portal
- Dynamically updates based on available portals in database

##### Lifecycle Status Filter
- **All**: Show all tenders regardless of status
- **Live**: Only active tenders
- **Expired**: Only closed/expired tenders
- **Cancelled**: Only cancelled tenders

##### Days Filter
- **All**: No date filtering
- **0 Days**: Published today
- **7 Days**: Published within last week
- **30 Days**: Published within last month

##### Search
- **Text Search**: Search across tender titles, departments, and references
- **Real-time**: Results update as you type

#### 3. Export Functions
- **Export All**: Export complete filtered dataset to Excel
- **Export Selected**: Export only checked tender rows
- Exports saved to `Tender84_Exports/` directory with timestamp
- Includes all tender fields in structured Excel format

#### 4. Tender Details
Each tender row displays:
- **Portal Name**: Source portal with visual badge
- **Department**: Issuing organization
- **Serial Number**: Portal-specific identifier
- **Tender ID**: Extracted unique identifier
- **Title/Reference**: Tender description
- **Published Date**: Tender publication date
- **Closing Date**: Bid submission deadline with urgency color coding
- **Lifecycle Status**: Current status badge (Live/Expired/Cancelled)
- **Actions**: Checkbox for bulk export selection

---

## Portal Management Page

### Features

#### 1. Portal Health Dashboard
Visual overview of all portals with key metrics:

##### Health Status Indicators
- **🟢 Green (0 days)**: Scraped today - Portal is current
- **🟡 Yellow (1-7 days)**: Scraped within last week - Acceptable
- **🟠 Orange (8-30 days)**: Scraped 1-4 weeks ago - Consider refreshing
- **🔴 Red (>30 days)**: Stale data - Needs immediate attention

##### Portal Metrics
- **Total Tenders**: All tenders in database for this portal
- **Live Tenders**: Currently active opportunities
- **Expired Tenders**: Closed opportunities
- **Last Scrape**: Timestamp with days-since indicator
- **Base URL**: Portal homepage link

#### 2. Portal Categories
Portals are automatically categorized based on their URL:
- **Central**: Central government portals (e.g., CPPP, DefProc)
- **State**: State government portals (e.g., Chandigarh, Arunachal Pradesh)
- **PSU**: Public Sector Undertaking portals (e.g., Limited portals)

Category badges appear next to portal names in the table.

#### 3. Category Filtering
Use the dropdown filter to view specific portal groups:
- **All**: Show all portals (default)
- **Central**: Only central government portals
- **State**: Only state portals
- **PSU**: Only PSU portals

Filter persists across page visits for convenience.

#### 4. Bulk Export by Category
Quick export buttons at the top of the page:
- **Export Central Portals**: Export all tenders from central portals
- **Export State Portals**: Export all tenders from state portals
- **Export PSU Portals**: Export all tenders from PSU portals

Each export includes:
- All tenders from portals in the category
- Separate Excel file per portal
- Organized in `Portal_Exports/<category>/` directory
- Timestamp-based folder structure

#### 5. Export History Tracking
- **View Export History**: Click button to see recent exports
- **Last 20 Exports**: Chronological list of export operations
- **Export Details**:
  - Timestamp of export
  - Export type (All Portals, Category, Selected, Single Portal)
  - Number of portals included
  - Total tenders exported
  - Number of files generated
  - Export directory path

Export history is stored in `Portal_Exports/export_history.json`.

#### 6. Portal Selection Export
- **Select All**: Check all visible portals
- **Deselect All**: Uncheck all portals
- **Export Selected**: Export only checked portals to Excel
- Individual checkboxes for granular control

---

## Common Workflows

### Workflow 1: Find Urgent Tenders
1. Open Dashboard page
2. Set Lifecycle Status to "Live"
3. Set Days Filter to "7 Days"
4. Review tenders with closing dates highlighted in red (urgent)
5. Export selected urgent tenders

### Workflow 2: Monitor Portal Health
1. Open Portal Management page
2. Review health status colors
3. Focus on red/orange portals (stale data)
4. Trigger scraping for outdated portals from main GUI

### Workflow 3: Generate Department Report
1. Open Portal Management page
2. Filter by category (e.g., "Central")
3. Click "Export Central Portals" button
4. Navigate to `Portal_Exports/Central/` for generated files

### Workflow 4: Track Export Activity
1. Open Portal Management page
2. Click "Export History" button
3. Review recent export operations
4. Verify exports completed successfully

---

## Tips & Best Practices

### Performance
- **Pagination**: Use page navigation for large datasets instead of exporting all
- **Filters**: Apply filters before exporting to reduce file size
- **Search**: Use search for specific tenders instead of scrolling

### Data Freshness
- **Check Portal Health**: Regularly review portal management page
- **Scrape Schedule**: Schedule scrapes for red/orange portals
- **Export History**: Use to track when data was last exported

### Organization
- **Category Exports**: Use category-based exports for consistent folder structure
- **Naming Convention**: Exports include timestamps for version tracking
- **Cleanup**: Periodically archive old exports from `Portal_Exports/`

### Troubleshooting
- **No Data Showing**: Check that scraping has completed successfully
- **Portal Missing**: Verify portal is in `base_urls.csv` and has been scraped
- **Export Failed**: Check disk space and folder write permissions
- **Slow Loading**: Reduce page size or apply filters to limit results

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+F` | Focus search box |
| `Esc` | Clear search |
| `Tab` | Navigate between filters |

---

## Export File Formats

### Dashboard Exports
- **Format**: Excel (.xlsx)
- **Location**: `Tender84_Exports/dashboard_export_YYYYMMDD_HHMMSS.xlsx`
- **Structure**: Single sheet with all tender fields
- **Columns**: Portal, Department, Serial No, Tender ID, Title, Published, Closing, Status

### Portal Management Exports
- **Format**: Excel (.xlsx) - one file per portal
- **Location**: `Portal_Exports/<category>/<timestamp>/`
- **Naming**: `<PortalName>_YYYYMMDD_HHMMSS.xlsx`
- **Structure**: Sheet 1 - Live tenders, Sheet 2 - Expired tenders

---

## Advanced Features

### Auto-Refresh (Coming Soon)
Dashboard will auto-refresh when new scrapes complete.

### Portal Click Navigation (Coming Soon)
Click portal name in Portal Management to jump to filtered dashboard view.

### Export Scheduling (Coming Soon)
Schedule category exports to run automatically on a recurring basis.

### Portal Health Alerts (Coming Soon)
Email/notification when portals become stale (>30 days).

---

## Support

For technical issues or feature requests:
1. Check error logs in `logs/` directory
2. Review `CHANGELOG.md` for known issues
3. Contact development team with:
   - Steps to reproduce issue
   - Screenshot of error
   - Log file excerpt
