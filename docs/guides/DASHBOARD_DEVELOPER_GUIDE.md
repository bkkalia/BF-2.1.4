# Tender Dashboard - Developer Guide

## Architecture Overview

The Tender Dashboard is built using **Reflex** (v0.8.16), a full-stack Python framework that compiles to React.

### Technology Stack
- **Backend**: Python 3.13.5, Reflex framework
- **Frontend**: React (compiled from Reflex components)
- **Database**: SQLite3 (legacy schema)
- **Export**: pandas, openpyxl
- **State**: Reactive state management via Reflex

### Project Structure
```
tender_dashboard_reflex/
├── dashboard_app/           # Frontend UI components
│   ├── __init__.py          # App entry point
│   ├── dashboard.py         # Main tender dashboard page
│   └── portal_management.py # Portal management page
├── tender_dashboard_reflex/ # Backend logic
│   ├── state.py             # State management
│   └── db.py                # Database queries
├── rxconfig.py              # Reflex configuration
└── assets/                  # Static assets
```

---

## Database Schema (Legacy)

The dashboard uses a **legacy schema** (NOT V3 schema).

### Tables

#### `tenders` Table
Primary tender data storage.

**Columns**:
- `id`: INTEGER PRIMARY KEY
- `run_id`: INTEGER (FK to runs.id)
- `portal_name`: TEXT
- `department_name`: TEXT
- `serial_no`: TEXT
- `tender_id_extracted`: TEXT
- `lifecycle_status`: TEXT ('Live', 'Expired', 'Cancelled')
- `cancelled_detected_at`: TEXT
- `cancelled_source`: TEXT
- `published_date`: TEXT
- `closing_date`: TEXT
- `opening_date`: TEXT
- `title_ref`: TEXT
- `organisation_chain`: TEXT
- `direct_url`: TEXT
- `status_url`: TEXT
- `emd_amount`: TEXT
- `emd_amount_numeric`: REAL
- `tender_json`: TEXT (JSON blob)

**Indexes**:
- `portal_name`, `tender_id_extracted` (composite)
- `lifecycle_status`
- `published_date`, `closing_date`

#### `runs` Table
Scraping run metadata.

**Columns**:
- `id`: INTEGER PRIMARY KEY
- `portal_name`: TEXT
- `base_url`: TEXT
- `scope_mode`: TEXT
- `started_at`: TEXT
- `completed_at`: TEXT (timestamp for portal health)
- `status`: TEXT
- `expected_total_tenders`: INTEGER
- `extracted_total_tenders`: INTEGER
- `skipped_existing_total`: INTEGER
- `partial_saved`: INTEGER
- `output_file_path`: TEXT
- `output_file_type`: TEXT

**Key**: `completed_at` is used for portal health calculations (days since update).

---

## Backend Architecture

### State Management (`state.py`)

#### `DashboardState` (Main Dashboard)
Manages tender browsing and filtering.

**Key State Variables**:
```python
tenders: list[TenderRow]         # Current page of tenders
total_tenders: int               # Total matching tenders
current_page: int                # Pagination state
page_size: int                   # Items per page (default 20)
portal_names: list[str]          # Available portals
selected_portal: str             # Filter: portal selection
lifecycle_filter: str            # Filter: Live/Expired/All
days_filter: int                 # Filter: 0/7/30/-1 (all)
search_query: str                # Filter: text search
selected_tender_ids: list[int]   # Checked rows for export
```

**Key Methods**:
```python
load_tenders()                   # Query DB and populate table
next_page() / prev_page()        # Pagination
toggle_tender_selection(id)      # Checkbox handling
export_selected_tenders()        # Export checked rows
export_all_tenders()             # Export filtered dataset
```

#### `PortalManagementState` (Portal Management)
Manages portal health monitoring and bulk exports.

**Key State Variables**:
```python
portals: list[PortalRow]         # Portal statistics
category_filter: str             # Filter: All/Central/State/PSU
export_history: list[ExportHistoryEntry]  # Recent exports
selected_portals: list[str]      # Checked portals for export
```

**Key Methods**:
```python
load_portal_statistics()         # Query portal metrics
export_category_portals(cat)     # Bulk export by category
export_selected_portals()        # Export checked portals
load_export_history()            # Load from JSON
set_category_filter(cat)         # Filter and reload
```

**Models**:
```python
class PortalRow(rx.Base):
    portal_slug: str
    total_tenders: int
    live_tenders: int
    expired_tenders: int
    last_updated: Optional[str]
    base_url: str
    category: str                 # Central/State/PSU
    days_since_update: int        # Calculated health metric

class ExportHistoryEntry(rx.Base):
    timestamp: str
    export_type: str
    portals: list[str]
    total_tenders: int
    file_count: int
    export_dir: str
    settings: dict[str, Any]      # Additional metadata
```

### Database Layer (`db.py`)

#### Portal Categorization
```python
def _get_portal_categories() -> dict[str, str]:
    """
    Maps portals to categories based on base_urls.csv keywords.
    
    Returns:
        {'CPPP1': 'Central', 'Chandigarh': 'State', ...}
    """
```

**Category Logic**:
- Contains "Central" → Central
- Contains "Limited" or "Corporation" → PSU
- All others → State

#### Portal Statistics Query
```python
def get_portal_statistics(days_filter: int = -1) -> list[dict]:
    """
    Retrieves portal health metrics with category enrichment.
    
    CRITICAL: Uses subqueries for legacy schema compatibility.
    
    Query Structure:
    SELECT 
      t.portal_name as portal_slug,
      (SELECT MAX(completed_at) FROM runs 
       WHERE portal_name = t.portal_name) as last_updated,
      (SELECT base_url FROM runs 
       WHERE portal_name = t.portal_name 
       ORDER BY completed_at DESC LIMIT 1) as base_url,
      COUNT(*) as total_tenders,
      SUM(CASE lifecycle_status = 'Live' THEN 1 ELSE 0) as live,
      SUM(CASE lifecycle_status = 'Expired' THEN 1 ELSE 0) as expired
    FROM tenders t
    GROUP BY t.portal_name
    """
```

**Why Subqueries?**  
Legacy schema has no `last_scrape_time` column. Must join with `runs` table to get latest `completed_at` timestamp per portal.

**Days Since Update Calculation**:
```python
from datetime import datetime
if last_updated:
    delta = datetime.now() - datetime.fromisoformat(last_updated)
    days_since = delta.days
```

#### Export History
```python
def log_export_history(
    export_type: str,
    portals: list[str],
    total_tenders: int,
    file_count: int,
    export_dir: str,
    settings: dict = None
):
    """
    Appends export metadata to Portal_Exports/export_history.json.
    
    Schema:
    {
        "timestamp": "2026-02-17 14:30:00",
        "export_type": "Category: Central",
        "portals": ["CPPP1", "CPPP2"],
        "total_tenders": 8928,
        "file_count": 2,
        "export_dir": "Portal_Exports/Central/20260217_143000/",
        "settings": {"lifecycle": "all"}
    }
    """
```

---

## Frontend Architecture

### Component Structure (Reflex)

#### Dashboard Page (`dashboard_app/dashboard.py`)
```python
def index() -> rx.Component:
    """
    Main render function for dashboard page.
    
    Layout:
      - Header with title
      - Filters row (portal, lifecycle, days, search)
      - Actions row (export all, export selected)
      - Tender table with pagination
    """
    return rx.box(
        header(),
        filters_section(),
        table_section(),
        padding="2em"
    )
```

**Key Components**:
- `filters_section()`: Dropdowns and search input
- `table_section()`: Data table with rx.table.root
- `tender_table_row()`: Individual row with checkbox
- `pagination_controls()`: Next/prev buttons

#### Portal Management Page (`dashboard_app/portal_management.py`)
```python
def portal_management() -> rx.Component:
    """
    Portal health monitoring and bulk export page.
    
    Layout:
      - Header with title
      - Filters row (category filter, export history button)
      - Quick exports row (category buttons, select all, export selected)
      - Portal table with health indicators
    """
```

**Enhanced Components**:

##### Health Status Indicators
```python
def get_health_icon_and_color(days: int) -> tuple[str, str]:
    if days == 0:
        return "check-circle", "green.9"    # 🟢
    elif days <= 7:
        return "clock", "yellow.9"          # 🟡
    elif days <= 30:
        return "alert-circle", "orange.9"   # 🟠
    else:
        return "alert-triangle", "red.9"    # 🔴
```

##### Category Badges
```python
def category_badge(category: str) -> rx.Component:
    colors = {
        "Central": "blue",
        "State": "green",
        "PSU": "purple"
    }
    return rx.badge(category, color=colors.get(category, "gray"))
```

##### Export History Dialog
```python
def export_history_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(rx.button("Export History")),
        rx.dialog.content(
            rx.foreach(
                PortalManagementState.export_history,
                lambda entry: rx.card(
                    rx.text(entry.timestamp),
                    rx.text(f"Type: {entry.export_type}"),
                    rx.text(f"Portals: {', '.join(entry.portals)}"),
                    rx.text(f"Total: {entry.total_tenders} tenders"),
                    padding="1em"
                )
            )
        )
    )
```

**CRITICAL**: Use `entry.attribute` syntax (not `entry["key"]`) when accessing BaseModel properties in Reflex foreach loops.

---

## Export Implementation

### Excel Generation
```python
import pandas as pd

def export_portal_to_excel(
    portal_name: str, 
    output_path: str,
    lifecycle_filter: str = "all"
):
    """
    Exports portal tenders to Excel with sheets.
    
    Args:
        portal_name: Target portal
        output_path: Full file path
        lifecycle_filter: 'all', 'live', 'expired'
    
    Output:
        Sheet 1: Live tenders
        Sheet 2: Expired tenders
    """
    conn = sqlite3.connect(DB_PATH)
    query = f"""
        SELECT * FROM tenders 
        WHERE portal_name = ? 
        AND lifecycle_status = ?
    """
    
    # Live tenders
    live_df = pd.read_sql_query(query, conn, params=(portal_name, 'Live'))
    
    # Expired tenders
    expired_df = pd.read_sql_query(query, conn, params=(portal_name, 'Expired'))
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        live_df.to_excel(writer, sheet_name='Live Tenders', index=False)
        expired_df.to_excel(writer, sheet_name='Expired Tenders', index=False)
```

### Category-Based Export
```python
def export_category_portals(category: str):
    """
    Exports all portals in a category.
    
    Process:
    1. Filter portals by category
    2. Create timestamped directory
    3. Export each portal to separate Excel
    4. Log to export history
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = f"Portal_Exports/{category}/{timestamp}/"
    os.makedirs(export_dir, exist_ok=True)
    
    portals = [p for p in self.portals if p.category == category]
    
    for portal in portals:
        output_path = f"{export_dir}{portal.portal_slug}_{timestamp}.xlsx"
        export_portal_to_excel(portal.portal_slug, output_path)
    
    log_export_history(
        export_type=f"Category: {category}",
        portals=[p.portal_slug for p in portals],
        total_tenders=sum(p.total_tenders for p in portals),
        file_count=len(portals),
        export_dir=export_dir
    )
```

---

## Configuration

### Reflex Config (`rxconfig.py`)
```python
import reflex as rx

config = rx.Config(
    app_name="tender_dashboard_reflex",
    frontend_port=3600,
    backend_port=8600,
)
```

### Database Path
```python
# tender_dashboard_reflex/db.py
DB_PATH = "../database/db_v3.sqlite"
```

### Base URLs CSV
```python
# base_urls.csv location
BASE_URLS_CSV = "../base_urls.csv"
```

---

## Development Workflow

### Setup
```bash
cd tender_dashboard_reflex
python -m venv .venv
.venv\Scripts\activate
pip install reflex pandas openpyxl
reflex init
```

### Run Development Server
```bash
cd tender_dashboard_reflex
reflex run --frontend-port 3600 --backend-port 8600
```

Access at: `http://localhost:3600`

### Hot Reload
Reflex auto-reloads on file changes. Edit `.py` files and refresh browser.

### Debugging
```python
# Add print statements in state methods
def load_tenders(self):
    print(f"Loading tenders: portal={self.selected_portal}")
    # ... rest of method
```

Check terminal output where `reflex run` is executing.

### Testing DB Queries
```python
# Create test script: test_portal_query.py
import sys
sys.path.append('tender_dashboard_reflex')
from tender_dashboard_reflex.db import get_portal_statistics

portals = get_portal_statistics()
print(f"Found {len(portals)} portals")
for p in portals:
    print(f"{p['portal_slug']}: {p['total_tenders']} tenders")
```

---

## Common Issues & Solutions

### Issue: Portal Management Shows No Data
**Cause**: SQL query using non-existent column (e.g., `last_scrape_time` in V3 schema when using legacy schema).

**Solution**: Verify schema with `PRAGMA table_info(tenders)` and use subqueries for legacy schema:
```sql
(SELECT MAX(completed_at) FROM runs WHERE portal_name = t.portal_name)
```

### Issue: TypeError in foreach loop
**Cause**: Accessing BaseModel as dict (`entry["key"]`) instead of attribute (`entry.key`).

**Solution**: Use attribute syntax in Reflex components:
```python
rx.foreach(State.items, lambda item: rx.text(item.name))  # ✅
rx.foreach(State.items, lambda item: rx.text(item["name"]))  # ❌
```

### Issue: UntypedVarError
**Cause**: State variable not properly typed for Reflex.

**Solution**: Use BaseModel or explicit type annotations:
```python
export_history: list[ExportHistoryEntry] = []  # ✅
export_history: list[dict[str, Any]] = []      # ⚠️ Works but verbose
export_history = []                             # ❌ Untyped
```

### Issue: Icon Not Found
**Cause**: Invalid Lucide icon name.

**Solution**: Check [Lucide Icons](https://lucide.dev/) for valid names. Use `circle-help` not `help-circle`.

---

## Performance Optimization

### Pagination
Always paginate large datasets:
```python
LIMIT {page_size} OFFSET {(page - 1) * page_size}
```

### Indexing
Ensure indexes on frequently filtered columns:
```sql
CREATE INDEX idx_portal_lifecycle ON tenders(portal_name, lifecycle_status);
CREATE INDEX idx_published_date ON tenders(published_date);
```

### Query Optimization
Use `COUNT(*)` for totals instead of loading all rows:
```python
# Get total count
total = cursor.execute("SELECT COUNT(*) FROM tenders WHERE ...").fetchone()[0]

# Get page of data
rows = cursor.execute("SELECT * FROM tenders WHERE ... LIMIT ? OFFSET ?", 
                      (page_size, offset)).fetchall()
```

### Export Streaming
For large exports, stream to file instead of loading into memory:
```python
# Use pandas chunksize
for chunk in pd.read_sql_query(query, conn, chunksize=1000):
    chunk.to_excel(writer, startrow=row_offset, index=False, header=False)
    row_offset += len(chunk)
```

---

## Extending the Dashboard

### Adding New Filters
1. Add state variable in `state.py`:
   ```python
   new_filter: str = "default_value"
   ```

2. Add filter method:
   ```python
   def set_new_filter(self, value: str):
       self.new_filter = value
       self.load_tenders()
   ```

3. Add UI component in dashboard page:
   ```python
   rx.select(
       options,
       value=DashboardState.new_filter,
       on_change=DashboardState.set_new_filter
   )
   ```

4. Update DB query to use filter:
   ```python
   WHERE new_column = ?
   ```

### Adding New Export Types
1. Create export method in `state.py`:
   ```python
   def export_custom(self):
       # Custom export logic
       db.export_custom_format(...)
       db.log_export_history(...)
   ```

2. Add DB function in `db.py`:
   ```python
   def export_custom_format(...):
       # Query and format data
       # Write to file
   ```

3. Add UI button:
   ```python
   rx.button(
       "Export Custom",
       on_click=State.export_custom
   )
   ```

### Adding New Pages
1. Create page file `dashboard_app/new_page.py`:
   ```python
   import reflex as rx
   
   def new_page() -> rx.Component:
       return rx.box(...)
   ```

2. Register in `dashboard_app/__init__.py`:
   ```python
   app.add_page(new_page, route="/new-page")
   ```

3. Add navigation link:
   ```python
   rx.link("New Page", href="/new-page")
   ```

---

## Testing

### Unit Tests
```python
# tests/test_db.py
import unittest
from tender_dashboard_reflex.db import get_portal_statistics

class TestDatabase(unittest.TestCase):
    def test_portal_statistics(self):
        portals = get_portal_statistics()
        self.assertGreater(len(portals), 0)
        self.assertIn('portal_slug', portals[0])
```

### Integration Tests
```python
# tests/test_exports.py
def test_category_export():
    state = PortalManagementState()
    state.export_category_portals("Central")
    
    # Verify files created
    assert os.path.exists("Portal_Exports/Central/")
```

---

## Deployment

### Production Build
```bash
reflex export
```

Generates static build in `.web/_static/`.

### Docker
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY . .
RUN pip install reflex pandas openpyxl
EXPOSE 3600 8600
CMD ["reflex", "run", "--frontend-port", "3600", "--backend-port", "8600"]
```

### Environment Variables
```python
# Add to rxconfig.py
import os
config = rx.Config(
    db_url=os.getenv("DB_PATH", "../database/db_v3.sqlite")
)
```

---

## Maintenance

### Database Migrations
When schema changes:
1. Update queries in `db.py`
2. Test with `test_portal_query.py`
3. Update state models if columns added/removed
4. Verify all exports still work

### Dependency Updates
```bash
pip install --upgrade reflex
```

Check breaking changes in [Reflex Changelog](https://github.com/reflex-dev/reflex/releases).

### Log Monitoring
Reflex logs to console. For production:
```python
import logging
logging.basicConfig(
    filename='dashboard.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

---

## Resources

- **Reflex Documentation**: https://reflex.dev/docs
- **Reflex Examples**: https://github.com/reflex-dev/reflex-examples
- **Lucide Icons**: https://lucide.dev/
- **pandas Documentation**: https://pandas.pydata.org/docs/
- **SQLite Documentation**: https://www.sqlite.org/docs.html

---

## Contributing

### Code Style
- Follow PEP 8
- Type hints for all function parameters
- Docstrings for public functions
- Max line length: 100 characters

### Pull Request Process
1. Create feature branch
2. Implement changes with tests
3. Update documentation
4. Submit PR with description

### Commit Messages
```
feat: Add portal health alerts
fix: Correct category export path
docs: Update developer guide
refactor: Simplify export logic
```
