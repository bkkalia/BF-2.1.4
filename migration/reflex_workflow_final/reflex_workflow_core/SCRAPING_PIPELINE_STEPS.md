# BlackForest Tender Scraper - Pipeline Steps Guide

**Purpose:** This document maps every step in the data scraping pipeline. Use this to identify EXACTLY where in the process you want to inject new logic, transform data, or add new fields to the database.

---

## Quick Reference: Main Pipeline Flow

```
STEP 1: Initialize Scraper
    ↓
STEP 2: Navigate to Portal & Organization Page
    ↓
STEP 3: Fetch Department/Organization List
    ↓
STEP 4: Iterate Through Departments
    ├─ STEP 5: Navigate to Department Page
    ├─ STEP 6: Extract Tender Summary Row
    ├─ STEP 7: Click Tender Link → Load Tender Detail Page
    ├─ STEP 8: Extract Tender Detail Fields
    ├─ STEP 9: Download Tender Documents (Optional)
    ├─ STEP 10: Extract Additional Deep-Scrape Fields (Optional)
    ├─ STEP 11: Transform & Normalize Tender Data
    ├─ STEP 12: Check for Duplicates
    ├─ STEP 13: Store Tender in SQLite
    └─ STEP 14: Export to Excel (Optional)
    ↓
STEP 15: Finalize Scraping Session
```

---

## Detailed Steps with File References & Hooks

### **STEP 1: Initialize Scraper**

**Location:** `cli_runner.py` → `run_scraping_logic()` in `scraper/logic.py` (line ~1755)

**What happens:**
- CLI arguments parsed in `cli_parser.py`
- WebDriver created via `scraper/driver_manager.py::setup_driver()`
- Download directory set via `scraper/driver_manager.py::set_download_directory()`
- SQLite database initialized via `tender_store.py::TenderDataStore()`
- Portal configuration loaded from `base_urls.csv`

**Data at this step:**
- Portal config: `{ Name, BaseURL, OrgListURL }`
- WebDriver instance (Chrome/Chromium)
- SQLite connection ready
- Empty data collections

**Key variables in code:**
```python
base_url_config = portal_config  # from cli_runner.py
sqlite_db_path = kwargs.get("sqlite_db_path") or os.path.join(download_dir, "...")
tender_data_store = TenderDataStore(sqlite_db_path)
```

**If you want to add NEW INITIALIZATION LOGIC:**
- Hook into `cli_runner.py` before `run_scraping_logic()` call
- Or modify `run_scraping_logic()` first 50 lines (init section)
- Example: pre-fetch portal rules, initialize custom state objects

---

### **STEP 2: Navigate to Portal & Organization Page**

**Location:** `scraper/logic.py::navigate_to_org_list()` (line ~3980+)

**What happens:**
- Driver loads `base_url_config['BaseURL']` 
- Portal home page loads
- Navigation to "Tenders by Organisation" page
- Handles portal-specific redirects and compatibility pages
- Portal memory records successful navigation

**Data at this step:**
- Current URL on organization/department list page
- Portal name detected from URL

**Key function signature:**
```python
def navigate_to_org_list(driver, log_callback=None, org_list_url=None):
    """Navigate to the organization list page."""
```

**If you want to add CUSTOM NAVIGATION LOGIC:**
- Modify `navigate_to_org_list()` function
- Add portal-specific handling in the conditional blocks
- Example: custom wait conditions, JavaScript execution, portal-specific selectors

---

### **STEP 3: Fetch Department/Organization List**

**Location:** `scraper/logic.py::run_scraping_logic()` (line ~1900+) + `scraper/playwright_logic.py`

**What happens:**
- Fetch list of all departments/organizations from portal
- Two strategies: Selenium-first (`fetch_department_list_from_site_v2`) or Playwright (`fetch_department_list_from_site_playwright`)
- Parse HTML table to extract `{ S.No, Name, Link }`
- Filter departments based on existing/resume logic

**Data at this step:**
```python
departments_to_scrape = [
    {
        'S.No': 1,
        'Name': 'Department Name',
        'Link': 'https://...',
        'processed': False
    },
    ...
]
```

**Key function:**
```python
# From scraper/logic.py
departments_to_scrape = _prepare_department_tasks(
    departments_to_scrape,
    log_callback,
    base_reference_url=base_url_config.get('OrgListURL') or base_url_config.get('BaseURL')
)
```

**If you want to add CUSTOM DEPARTMENT FILTERING or ENRICHMENT:**
- Modify `_prepare_department_tasks()` function
- Filter based on name patterns, priority, custom metadata
- Example: add department priority, cost center, region info to dept object

---

### **STEP 4: Iterate Through Departments**

**Location:** `scraper/logic.py::run_scraping_logic()` (line ~2100+)

**What happens:**
- For each department, spawn a worker thread (if multi-threaded)
- Call `_process_department_with_recovery()` for each dept
- Collect tenders from all threads
- Track recovery events (transport timeouts, session loss)

**Data at this step:**
- Processing each department one at a time
- Per-thread tender lists being accumulated

**If you want to add CROSS-DEPARTMENT LOGIC:**
- Modify loop in `run_scraping_logic()` around line ~2150
- Add logic between departments (e.g., cache clearing, memory stats)
- Example: aggregate statistics per portal, pause between departments

---

### **STEP 5: Navigate to Department Page**

**Location:** `scraper/logic.py::_process_department_with_driver()` (line ~2500+)

**What happens:**
- From organization list page, click or navigate to specific department
- Load department-specific tenders list page
- Wait for page stabilization
- Extract department name from page

**Data at this step:**
- Department table with tenders visible (initial load ~10-20 rows per page)
- Department metadata extracted

**Key variables:**
```python
department_name = dept_info.get('Name')
dept_link = dept_info.get('Link')
# Click link or navigate directly
```

**If you want to add DEPARTMENT-LEVEL METADATA:**
- Modify `_process_department_with_driver()` to extract more fields
- Example: department budget, contact info, last updated date

---

### **STEP 6: Extract Tender Summary Row**

**Location:** `scraper/logic.py::_extract_tender_rows_from_table()` (line ~2800+)

**What happens:**
- Find tender table on department page
- For each row (excluding header), extract:
  - S.No
  - Tender Title / Reference
  - Publication Date
  - Closing Date
  - Organization
  - Tender Link

**Data structure at this step:**
```python
tender_summary = {
    'S.No': row_index,
    'Title and Ref.No./Tender ID': 'TENDER-2025-001',
    'Publication Date': '2025-01-10',
    'Closing Date': '2025-02-10',
    'Organization': 'Department Name',
    'Link': 'https://portal.../tender/123'
}
```

**Key function:**
```python
# In _process_department_with_driver()
rows = driver.find_elements(By.XPATH, MAIN_TABLE_BODY_LOCATOR)
for row in rows:
    tender_summary = _extract_row_data(row)  # Extracts S.No, Title, Dates, Link
```

**If you want to add CUSTOM SUMMARY-LEVEL FIELDS:**
- Modify the row extraction loop
- Add new columns to the table parse
- Example: estimated budget, bid type, classification

---

### **STEP 7: Click Tender Link → Load Tender Detail Page**

**Location:** `scraper/logic.py::_process_department_with_driver()` + `scraper/actions.py::click_element()` (line ~100+)

**What happens:**
- For each tender summary, click the tender link
- Driver navigates to detailed tender page
- **[TRANSPORT TIMEOUT DETECTION HAPPENS HERE]** ← If driver hangs, flagged for recovery
- Wait for tender detail page to load
- Extract URL, tender ID from page

**Data at this step:**
- Single tender detailed page loaded
- URL contains tender reference/ID

**Key function with TIMEOUT HANDLING:**
```python
def click_element(driver, locator, description, timeout=None, retries=1):
    """Click element with transport timeout detection."""
    # If ReadTimeoutError occurs → _mark_driver_transport_unresponsive()
    # Error caught, driver._bf_transport_unresponsive flag set to True
```

**If you want to add PRE/POST-CLICK LOGIC:**
- Modify `click_element()` in `scraper/actions.py`
- Add screenshot capture, page state validation
- Example: screenshot failed clicks, extract error messages

---

### **STEP 8: Extract Tender Detail Fields (Basic)**

**Location:** `scraper/logic.py::extract_tender_details()` (line ~3899+)

**What happens:**
- Always extracted (basic fields):
  - Tender ID (from page)
  - Tender Title (from page)

**Data extracted:**
```python
details = {
    'Tender ID': '2025-DEPT-12345',
    'Title': 'Construction of New Office Building'
}
```

**Key function:**
```python
def extract_tender_details(driver, deep_scrape=False):
    """Extracts tender details from the details page."""
    details = {
        'Tender ID': safe_extract_text(driver, TENDER_ID_ON_PAGE_LOCATOR, "Tender ID"),
        'Title': safe_extract_text(driver, TENDER_TITLE_LOCATOR, "Tender Title")
    }
    # If deep_scrape=True, more fields added (see STEP 10)
    return details
```

**If you want to add NEW BASIC FIELDS:**
- Modify the dictionary returned by `extract_tender_details()`
- Add to the `details = { ... }` dict
- Example: add `'Vendor Name'`, `'Tender Status'`

---

### **STEP 9: Download Tender Documents (Optional)**

**Location:** `scraper/logic.py` + `scraper/actions.py::wait_for_downloads()` (line ~200+)

**What happens:**
- Click "Download as ZIP" or individual document links
- Wait for file to download to configured download directory
- Monitor browser downloads folder
- Check file presence and integrity

**Data at this step:**
- Document files on disk at `download_dir/tender_id/`
- No data structure change yet

**Key function:**
```python
def wait_for_downloads(driver, download_dir, timeout=120, file_pattern=None):
    """Wait for downloads to complete, with file monitoring."""
    # Monitors download progress, validates file arrival
```

**If you want to add CUSTOM DOWNLOAD HANDLING:**
- Modify `wait_for_downloads()` in `scraper/actions.py`
- Add post-download processing (unzip, extract, OCR)
- Example: extract invoice numbers from downloaded PDFs, validate file format

---

### **STEP 10: Extract Additional Deep-Scrape Fields (Optional)**

**Location:** `scraper/logic.py::extract_tender_details()` (line ~3915+)

**What happens:**
- Only when `deep_scrape=True` (controlled via `--deep-scrape` CLI flag)
- Extract additional tender page fields:
  - Contract Type
  - Tender Fee
  - EMD Amount
  - Tender Value
  - Work Description
  - Work Location
  - Inviting Officer
  - Inviting Officer Address

**Data extracted:**
```python
details = {
    'Contract Type': 'Works',
    'Tender Fee': '₹500',  # Cleaned to '500'
    'EMD Amount': '₹50000',  # Cleaned
    'Tender Value': '₹5,00,00,000',  # Cleaned
    'Work Description': 'Construct 5 km road...',
    'Location': 'Bangalore',
    'Inviting Officer': 'Ram Sharma',
    'Inviting Officer Address': '...'
}
```

**If you want to add MORE DEEP-SCRAPE FIELDS:**
- Add new locators to `config.py` (define selectors)
- Add field extraction in the `if deep_scrape:` block of `extract_tender_details()`
- Example: add `'Bid Submission Mode'`, `'Pre-bid Meeting Date'`

---

### **STEP 11: Transform & Normalize Tender Data**

**Location:** `scraper/logic.py::_normalize_tender_data()` + `utils.py` (line ~100+)

**What happens:**
- Tender ID normalized: `extract_tender_id_from_title()` or `extract_tender_id_by_skill()`
- Dates normalized: `normalize_closing_date()` → ISO format (YYYY-MM-DD)
- Monetary values cleaned: remove currency symbols, parse amounts
- Tender title sanitized
- Status checked and set (e.g., "Published", "Closing Soon")

**Data before transformation:**
```python
{
    'Title and Ref.No./Tender ID': 'TENDER REF 2025/001',
    'Closing Date': '10-Feb-2025',
    'EMD Amount': '₹50,000'
}
```

**Data after transformation:**
```python
{
    'Tender ID': '2025_001',  # Normalized
    'Title': 'Tender Ref 2025/001',
    'Closing Date': '2025-02-10',  # ISO format
    'EMD Amount': '50000',  # Numeric string
    'Status': 'Closing in 5 days'
}
```

**Key functions:**
```python
normalize_tender_id(title)  # Extract tender ID from title
normalize_closing_date(date_str)  # Convert to YYYY-MM-DD
sanitise_filename(title)  # Clean for file names
```

**If you want to add CUSTOM TRANSFORMATION LOGIC:**
- Create new helper function in `utils.py`
- Call it during data transformation phase
- Example: classify tender by type, extract cost center from title, assign priority tier

---

### **STEP 12: Check for Duplicates**

**Location:** `scraper/logic.py::run_scraping_logic()` (line ~2200+)

**What happens:**
- Query SQLite for existing tender ID
- Check `existing_tender_ids_normalized` set
- If exists:
  - Compare closing date (if date changed → mark for reprocessing)
  - If no change → skip (count as skipped_existing)
- If new:
  - Continue to storage

**Data at this step:**
```python
if normalized_tender_id in existing_tender_ids_normalized:
    # Duplicate detected
    if closing_date_changed(new_date, old_date):
        # Mark for reprocessing
        changed_reprocessed_ids.add(normalized_tender_id)
    else:
        # Skip
        skipped_existing_total += 1
else:
    # New tender → proceed to storage
```

**If you want to add CUSTOM DUPLICATE DETECTION:**
- Modify duplicate check logic in `run_scraping_logic()`
- Add custom comparison fields (e.g., tender value, organization)
- Example: detect if organization or value changed, trigger reprocessing

---

### **STEP 13: Store Tender in SQLite**

**Location:** `tender_store.py::TenderDataStore.save_tender()` (line ~100+)

**What happens:**
- INSERT or UPDATE record in `tender_items` table (v3 schema)
- Fields stored:
  - `tender_id_extracted`
  - `title`
  - `portal_slug`
  - `organization_name`
  - `publication_date`
  - `closing_date`
  - `tender_value`
  - `emd_amount`
  - `work_location`
  - `contract_type`
  - `inviting_officer`
  - `json_data` (for additional custom fields)
- Record insertion time and modification time
- Create reference in `scrape_run_items` linking to this run

**Data stored in DB:**
```sql
INSERT INTO tender_items (
    tender_id_extracted,
    title,
    portal_slug,
    organization_name,
    publication_date,
    closing_date,
    tender_value,
    emd_amount,
    work_location,
    contract_type,
    inviting_officer,
    json_data,
    inserted_at,
    modified_at
) VALUES (...)
```

**If you want to add NEW DATABASE FIELDS:**
- Modify `tender_store.py::TenderDataStore._ensure_schema()` to add column
- Update INSERT statement in `save_tender()` method
- Or use `json_data` column to store custom fields without schema changes
- Example: add `budget_code`, `department_id`, `bid_status` columns

---

### **STEP 14: Export to Excel (Optional)**

**Location:** `scraper/logic.py::run_scraping_logic()` (line ~2300+) + `tender_store.py`

**What happens:**
- Policy checked: `export_policy` (on_demand, always, alternate_days)
- If export needed:
  - Query all tenders from this run
  - Create DataFrame with columns
  - Apply formatting (colors, borders, bold headers)
  - Save as Excel file with timestamp

**Data exported:**
```
Excel Sheet:
┌─────┬─────────────┬──────────┬───────────┬───────────────┐
│ ID  │ Title       │ Org      │ Pub Date  │ Closing Date  │
├─────┼─────────────┼──────────┼───────────┼───────────────┤
│ 001 │ Tender A    │ Dept X   │ 2025-01  │ 2025-02-10    │
└─────┴─────────────┴──────────┴───────────┴───────────────┘
```

**Key function:**
```python
def export_to_excel(tenders, output_path):
    """Export tender list to formatted Excel file."""
    df = pd.DataFrame(tenders)
    # Apply formatting
    df.to_excel(output_path, index=False)
```

**If you want to add CUSTOM EXPORT FIELDS or FORMATTING:**
- Modify DataFrame columns in export function
- Add conditional formatting, sheets by organization
- Example: add summary statistics sheet, color-code by status

---

### **STEP 15: Finalize Scraping Session**

**Location:** `scraper/logic.py::run_scraping_logic()` (line ~2400+)

**What happens:**
- Generate summary statistics:
  - Total tenders extracted
  - Total skipped (duplicates)
  - Total reprocessed (changed closing dates)
  - Timing breakdown (per dept, per tender)
  - Success/failure counts
- Close WebDriver via `safe_quit_driver()`
- Persist metrics to logs
- Release sleep prevention lock
- Update scrape run status to "Completed"

**Data at this step:**
```python
summary = {
    'Status': 'Scraping completed',
    'Processed Departments': 2,
    'Total Tenders Found': 24,
    'New Tenders': 18,
    'Skipped (Duplicate)': 5,
    'Reprocessed (Changed)': 1,
    'Elapsed Time': '14.7s',
    'Per-Tender Average': '0.13s',
    'Throughput': '97.6 per minute'
}
```

**If you want to add POST-SCRAPING LOGIC:**
- Modify final section of `run_scraping_logic()`
- Add post-processing, cleanup, notifications
- Example: send email report, upload to API, trigger downstream jobs

---

## Adding New Fields to Database

### **Scenario 1: Add field to existing tender_items table**

1. **Define new column** in `tender_store.py::_ensure_schema()`:
   ```python
   # In the CREATE TABLE IF NOT EXISTS tender_items block
   new_field_name TEXT DEFAULT NULL,
   ```

2. **Extract data** where needed (STEP 8 or 10):
   ```python
   # In extract_tender_details() or _extract_row_data()
   details['New Field'] = safe_extract_text(driver, NEW_FIELD_LOCATOR, "New Field")
   ```

3. **Store in database** in `tender_store.py::save_tender()`:
   ```python
   # Add to INSERT VALUES
   new_field_name=tender_data.get('New Field')
   ```

### **Scenario 2: Store complex data in json_data column (no schema change)**

1. **Collect custom fields**:
   ```python
   custom_data = {
       'custom_field_1': value1,
       'custom_field_2': value2
   }
   ```

2. **Store as JSON**:
   ```python
   tender_data['json_data'] = json.dumps(custom_data)
   ```

3. **Query and deserialize**:
   ```python
   tender = store.get_tender(tender_id)
   custom = json.loads(tender['json_data'])
   ```

---

## Adding New Processing Steps

### **Example 1: Add scraping step BETWEEN extraction and normalization**

**Location to modify:** `scraper/logic.py::_process_department_with_driver()` after extraction

```python
# After _extract_row_data() or extract_tender_details()
# STEP 11.5: Custom enrichment
enriched_data = my_custom_enrichment_function(tender_data, driver, context)
tender_data.update(enriched_data)
```

### **Example 2: Add validation step BEFORE database storage**

**Location to modify:** `scraper/logic.py::run_scraping_logic()` before `tender_data_store.save_tender()`

```python
# STEP 12.5: Custom validation
if not validate_tender_data(tender_data):
    log_callback(f"Validation failed: {tender_data['Tender ID']}")
    continue  # Skip this tender
```

### **Example 3: Add post-processing step AFTER database storage**

**Location to modify:** `scraper/logic.py::run_scraping_logic()` after `tender_data_store.save_tender()`

```python
# STEP 13.5: Post-storage processing
trigger_downstream_process(tender_id, db_record_id)
```

---

## File Responsibility Summary

| File | Responsible for Step(s) |
|------|------------------------|
| `cli_runner.py` | 1 - Initialize & orchestrate |
| `scraper/driver_manager.py` | 1 - Setup WebDriver |
| `scraper/logic.py` | 2-15 - Main pipeline |
| `scraper/playwright_logic.py` | 3 - Fetch dept list (alt) |
| `scraper/actions.py` | 7, 9 - Low-level actions, downloads |
| `config.py` | All - Locators, timeouts |
| `utils.py` | 11 - Normalization helpers |
| `tender_store.py` | 13-14 - Database & export |
| `portal_config_memory.py` | 2 - Portal memory |
| `base_urls.csv` | 1 - Portal config source |

---

## Debugging: Where To Add Logging

To track your data through the pipeline:

1. **STEP 5/6 level**: Add in `_extract_row_data()` after each field extraction
2. **STEP 8 level**: Add in `extract_tender_details()` to log each detail field
3. **STEP 11 level**: Add in normalization functions to log transformations
4. **STEP 13 level**: Add in `tender_store.py::save_tender()` to log DB inserts

Example:
```python
logger.debug(f"[STEP X] Field: {field_name} = {value}")
```

---

## Modification Checklist for New Version

- [ ] Identify which STEP to modify
- [ ] Find file & function in summary table
- [ ] Plan data structure changes (new fields, transformations)
- [ ] Modify database schema in `tender_store.py` if needed
- [ ] Add extraction/transformation code at identified step
- [ ] Add storage code in `tender_store.py::save_tender()`
- [ ] Test with smoke test script: `python scripts/smoke_driver_test.py`
- [ ] Validate data in SQLite: `SELECT * FROM tender_items LIMIT 1;`
- [ ] Generate sample export to verify new fields appear in Excel

---

**Last Updated:** April 24, 2026  
**Version:** 2.1.4 → Migration Guide v1.0
