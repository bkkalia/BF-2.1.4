# Excel/CSV Import User Guide

## Overview

The Excel/CSV Import feature allows you to import tender data from various sources with intelligent column matching. This feature is production-ready and handles different Excel formats and column naming conventions automatically.

## Quick Start

1. **Access the Import Page**
   - Navigate to: http://localhost:3700/import
   - Or click "Import Data" from the dashboard navigation

2. **Upload Your File**
   - Click "Select Excel/CSV File" or drag & drop
   - Supported formats: `.xlsx`, `.xls`, `.csv`
   - Maximum file size: 50 MB

3. **Review Smart Matching**
   - The system automatically detects column mappings
   - Green checkmarks (✓) indicate successful matches
   - Red alerts (!) indicate required columns need manual mapping

4. **Adjust Mappings (if needed)**
   - Use dropdown selectors to manually map columns
   - Preview sample data to verify correct mapping

5. **Configure Settings**
   - Portal name (auto-detected from filename)
   - Base URL (optional)
   - Skip duplicates (recommended: ON)
   - Validate data (recommended: ON)

6. **Import**
   - Click "Import to Database"
   - Real-time progress tracking
   - View results summary

## Smart Column Matching

### How It Works

The system uses a 4-strategy approach to match columns:

**Strategy 1: Exact Match** (case-insensitive)
```
"Tender ID" → tender_id_extracted ✓
"published_date" → published_date ✓
```

**Strategy 2: Normalized Match** (remove spaces, special chars)
```
"Tender-ID" → tender_id_extracted ✓
"e Published Date" → published_date ✓
```

**Strategy 3: Keyword Matching** (multiple keywords)
```
"Tender ID (Extracted)" → tender_id_extracted ✓ (keywords: tender, id, extracted)
"Department Name" → department_name ✓ (keywords: department, name)
```

**Strategy 4: Single Keyword** (best match)
```
"ID" → tender_id_extracted ✓ (keyword: id)
"Date" → published_date ✓ (keyword: date)
```

### Column Variations Supported

| Database Column | Excel Column Examples | Notes |
|----------------|----------------------|-------|
| `tender_id_extracted` | "Tender ID", "TenderID", "ID", "Tender ID (Extracted)" | Required |
| `department_name` | "Department", "Dept Name", "Department Name" | Required |
| `serial_no` | "S.No", "Serial No", "SNo", "Number" | Required |
| `published_date` | "Published Date", "e-Published Date", "Publish Date" | Required |
| `closing_date` | "Closing Date", "Close Date", "Deadline" | Required |
| `opening_date` | "Opening Date", "Open Date" | Optional |
| `organisation_chain` | "Organisation Chain", "Organization", "Org Chain" | Optional |
| `title_ref` | "Title and Ref.No.", "Title", "Reference" | Required |
| `direct_url` | "Direct URL", "Tender URL", "Link" | Required |
| `status_url` | "Status URL", "Status Link" | Optional |
| `emd_amount` | "EMD Amount", "EMD", "Earnest Money" | Optional |

## Portal Name Auto-Detection

The system automatically detects portal names from filenames:

- `hptenders_gov_in_*.xlsx` → Portal: `hptenders.gov.in`, URL: `https://hptenders.gov.in`
- `eprocure_gov_in_*.csv` → Portal: `eprocure.gov.in`, URL: `https://eprocure.gov.in`
- `ddtenders_*.xlsx` → Portal: `ddtenders.gov.in`, URL: `https://ddtenders.gov.in`
- Unknown patterns → Portal: `imported`, URL: (empty)

You can override auto-detected values in the Import Settings section.

## Import Settings Explained

### Portal Name
- **Default**: Auto-detected from filename
- **Purpose**: Identifies the source portal for these tenders
- **Example**: `hptenders.gov.in`, `eprocure.gov.in`

### Base URL
- **Default**: Auto-detected for known portals
- **Purpose**: Base URL for constructing tender links
- **Example**: `https://hptenders.gov.in`

### Skip Duplicates
- **Default**: ON (recommended)
- **Purpose**: Prevents re-importing existing tenders
- **Logic**: Checks by `(portal_name, tender_id_extracted)` combination
- **Result**: Duplicate rows are counted as "Skipped"

### Validate Data
- **Default**: ON (recommended)
- **Purpose**: Ensures required fields are not empty
- **Validation**: Checks `tender_id_extracted` is present
- **Result**: Invalid rows are counted as "Errors"

## Import Progress

### Real-Time Tracking

The import process shows:
- **Progress Bar**: 0-100%
- **Status**: Current operation (e.g., "Processing row 150/1414...")
- **Statistics Grid**:
  - **Processed**: Total rows processed
  - **Imported**: Successfully imported (green)
  - **Skipped**: Duplicates skipped (yellow)
  - **Errors**: Validation failures (red)

### Import Duration

- Small files (<1,000 rows): ~30 seconds
- Medium files (1,000-5,000 rows): 1-2 minutes
- Large files (5,000+ rows): 3-5 minutes

## Example Workflows

### Workflow 1: Import HP Tenders Export

**File**: `hptenders_gov_in_tenders_20260214_181931.xlsx`

1. Upload file → Auto-matches 10/10 columns ✓
2. Portal: `hptenders.gov.in` (auto-detected)
3. Base URL: `https://hptenders.gov.in` (auto-detected)
4. Skip duplicates: ON
5. Click "Import to Database"
6. **Result**: 1,409 imported, 5 skipped (duplicates)

### Workflow 2: Import Custom CSV

**File**: `custom_tenders.csv` (different column names)

```csv
TenderID,Dept,PublishDate,CloseDate,Title,URL
T123,PWD,2026-01-15,2026-02-15,Road Construction,https://...
```

1. Upload file
2. Smart matching:
   - `TenderID` → `tender_id_extracted` ✓
   - `Dept` → `department_name` ✓
   - `PublishDate` → `published_date` ✓
   - `CloseDate` → `closing_date` ✓
   - `Title` → `title_ref` ✓
   - `URL` → `direct_url` ✓
3. Manual mapping (if needed):
   - `serial_no` ← Select "(Not Mapped)" or add S.No column
4. Portal: `custom` (manual entry)
5. Import

### Workflow 3: Import from Multiple Sources

**Scenario**: You have data from HP, DD, and CPPP portals

1. **Import HP Tenders**:
   - File: `hptenders_*.xlsx`
   - Portal: `hptenders.gov.in`
   - Import → 1,409 tenders

2. **Import DD Tenders**:
   - File: `ddtenders_*.xlsx`
   - Portal: `ddtenders.gov.in`
   - Import → 856 tenders

3. **Import CPPP Tenders**:
   - File: `cppp_*.xlsx`
   - Portal: `eprocure.gov.in`
   - Import → 2,341 tenders

4. **View All Data**: Navigate to `/data` → See 4,606 total tenders from 3 portals

## After Import

### View Imported Data

Click "View Data" or navigate to http://localhost:3700/data

**Features**:
- Color-coded columns (green = listing fields, yellow = detail fields)
- Filters: Portal selector, Lifecycle (Live/Expired)
- Pagination: 50 rows per page
- Search: Tender ID, department, keywords

### Export Data

Navigate to http://localhost:3700/portals → "Export" button

**Options**:
- Live tenders only
- Expired days filter
- Export to Excel/CSV
- Upload to tender84.com

## Troubleshooting

### Issue: No Columns Auto-Matched

**Cause**: Column names don't match any known patterns

**Solution**:
1. Check column names in your Excel file
2. Manually map required columns using dropdowns
3. Ensure at least these 7 required columns are mapped:
   - `tender_id_extracted`
   - `department_name`
   - `serial_no`
   - `published_date`
   - `closing_date`
   - `title_ref`
   - `direct_url`

### Issue: Import Button Disabled

**Cause**: Not all required columns are mapped

**Solution**:
1. Look for red alert icons (!) in the Status column
2. Map all columns marked "Required" (red badge)
3. Button enables when all required columns are mapped

### Issue: Many Rows Skipped

**Cause**: Duplicates detected (skip duplicates ON)

**Solution**:
- **Expected behavior**: Re-importing same file will skip all rows
- **To re-import**: Delete existing data first or turn off "Skip duplicates"
- **Check**: View `/data` page to see existing tenders

### Issue: Import Errors

**Cause**: Missing required fields (validate data ON)

**Solution**:
1. Check error messages in red callout box
2. Common issues:
   - Empty `tender_id_extracted` fields
   - Invalid date formats
   - Missing required columns
3. Fix data in Excel and re-upload

### Issue: File Upload Fails

**Cause**: File too large (>50 MB) or corrupt

**Solution**:
- Split large files into smaller chunks
- Re-export from source
- Convert to CSV for smaller file size

## Database Schema

### Tender Table (19 columns)

**System Columns**:
- `id` - Auto-generated unique ID
- `run_id` - Import batch ID

**Listing Page Columns** (from Excel):
- `portal_name` - Portal identifier
- `department_name` - Department/organization
- `serial_no` - Serial number
- `tender_id_extracted` - Extracted tender ID
- `published_date` - Published/e-published date
- `closing_date` - Closing date
- `opening_date` - Opening date
- `title_ref` - Title and reference
- `organisation_chain` - Organization chain
- `direct_url` - Direct tender URL
- `status_url` - Status URL

**Lifecycle Tracking**:
- `lifecycle_status` - "active" or "archived"
- `cancelled_detected_at` - Cancellation detection time
- `cancelled_source` - Cancellation source

**Detail Page Columns** (future deep scraping):
- `emd_amount` - EMD amount text
- `emd_amount_numeric` - EMD amount numeric
- `tender_json` - Full tender metadata JSON

## API Reference

### State Variables

```python
ExcelImportState.file_uploaded: bool          # File uploaded status
ExcelImportState.file_name: str               # Uploaded filename
ExcelImportState.file_rows: int               # Row count
ExcelImportState.file_columns: int            # Column count
ExcelImportState.excel_columns: list[str]     # Excel column names
ExcelImportState.column_mappings: list        # Column mappings
ExcelImportState.auto_matched_columns: int    # Auto-matched count
ExcelImportState.all_required_mapped: bool    # All required mapped
ExcelImportState.portal_name: str             # Portal name
ExcelImportState.base_url: str                # Base URL
ExcelImportState.skip_duplicates: bool        # Skip duplicates flag
ExcelImportState.validate_data: bool          # Validate data flag
ExcelImportState.importing: bool              # Import in progress
ExcelImportState.import_progress: int         # Progress (0-100)
ExcelImportState.import_success: int          # Successful imports
ExcelImportState.import_skipped: int          # Skipped duplicates
ExcelImportState.import_errors: int           # Error count
ExcelImportState.import_completed: bool       # Import completed
```

### State Methods

```python
ExcelImportState.handle_upload(files)         # Handle file upload
ExcelImportState.update_column_mapping()      # Update column mapping
ExcelImportState.start_import()               # Start import process
ExcelImportState.clear_upload()               # Clear and reset
```

## Best Practices

### Data Preparation

1. **Standardize Column Names**: Use consistent naming across exports
2. **Include Required Columns**: Ensure all 7 required columns are present
3. **Clean Data**: Remove empty rows, fix date formats
4. **Unique Tender IDs**: Ensure `tender_id_extracted` is unique per portal

### Import Strategy

1. **Test with Small File**: Import 10-50 rows first to verify mappings
2. **Verify Results**: Check `/data` page after import
3. **Batch Imports**: Import one portal at a time for easier tracking
4. **Regular Exports**: Export data regularly from portals before importing

### Performance Tips

1. **CSV vs Excel**: CSV is faster for large files
2. **Chunk Large Files**: Split files >10,000 rows
3. **Database Cleanup**: Delete old/archived tenders periodically
4. **Skip Duplicates**: Always ON for re-imports

## Related Features

### Portal Management (`/portals`)
- View portal statistics
- Export tenders by portal
- Health status monitoring

### Data Visualization (`/data`)
- View all tender data
- Filter by portal, lifecycle
- Color-coded columns
- Pagination

### Scraping Control (`/scraping`)
- Automated scraping from portals
- Process-based workers
- Real-time progress tracking

## Support

For issues or questions:
1. Check this guide for common solutions
2. Review [EXCEL_DATABASE_COMPATIBILITY_REPORT.md](EXCEL_DATABASE_COMPATIBILITY_REPORT.md)
3. Check error messages in red callout boxes
4. Verify database schema matches expected structure

## Version History

- **v1.0** (2026-02-14): Initial release
  - Excel/CSV import with smart column matching
  - Auto-detection of portal names
  - Duplicate detection and validation
  - Real-time progress tracking
  - Support for 11 database columns
  - 4-strategy matching algorithm
  - Production-tested with 1,414 HP tenders

---

**Last Updated**: 2026-02-14  
**Component**: Excel Import Feature  
**Route**: `/import`  
**State Class**: `ExcelImportState`  
**UI Component**: `excel_import_page()`
