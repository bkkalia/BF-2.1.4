# NIC Portal Architecture & Data Flow

## Overview

This document explains the architecture of NIC (National Informatics Centre) developed e-procurement portals and how the BlackForest scraper handles their two-tier data structure.

## Portal Landscape

**NIC Portals**: 50+ government e-procurement portals with 99% similar architecture
- Examples: etenders.gov.in, HP Tenders, Arunachal Tenders, UP e-Tenders, etc.
- Standard URL pattern: `https://{portal}.nic.in/nicgep/app` or `https://{portal}.gov.in/nicgep/app`
- Consistent page structure, locators, and data organization

## Two-Tier Data Architecture

NIC portals follow a **Listing Page → Detail Page** structure:

### 1️⃣ **Listing Page** (FrontEndTendersByOrganisation)
**URL Pattern**: 
```
https://etender.up.nic.in/nicgep/app?component=%24DirectLink&page=FrontEndTendersByOrganisation&service=direct
```

**Purpose**: Display summary table of all tenders organized by department/organization

**Data Available** (currently scraped):
- ✅ Portal Name
- ✅ Tender ID (Extracted) - portal's internal serial number
- ✅ Published Date
- ✅ Opening Date  
- ✅ Closing Date
- ✅ Lifecycle Status (Live/Expired based on closing date)
- ✅ Direct URL (link to detail page)
- ✅ Status URL (generated from direct URL)

**What's Missing**:
- ❌ Title/Description
- ❌ Department Name
- ❌ Organization Chain
- ❌ EMD Amount
- ❌ Estimated Cost
- ❌ Work Type / Tender Type / Payment Type
- ❌ Location details (State, District, City, Pincode)

### 2️⃣ **Detail Page** (FrontEndViewTender) 
**URL Pattern**:
```
https://etender.up.nic.in/nicgep/app?component=%24DirectLink&page=FrontEndViewTender&service=direct&sp=SQbA52aP009uqMqbSDp6nkA%3D%3D
```

**Purpose**: Display comprehensive details for a single tender

**Data Available** (requires deep scraping - future enhancement):
- 📋 Full Title with embedded unique ID: `[2025_WR_152946_9] Title Text`
- 📋 Department Name
- 📋 Organization Hierarchy/Chain
- 💰 EMD Amount (detailed)
- 💰 Estimated Cost/Tender Value
- 📍 Complete Location: State, District, City, Pincode
- 🔖 Work Type, Tender Type, Payment Mode
- 📄 Contract details, specifications
- 📎 Document downloads (ZIP, Notice PDFs)

### 3️⃣ **Status Page** (WebTenderStatusLists)
**URL Pattern**:
```
https://etender.up.nic.in/nicgep/app?component=view&page=WebTenderStatusLists&service=direct&sp=SQbA52aP009uqMqbSDp6nkA%3D%3D
```

**Purpose**: Display bid results and tender status
- Winning bid information
- Bid opening results
- Tender outcome/status

## URL Generation Logic

The scraper uses a smart URL generation strategy:

```python
# From listing page title link (href):
original_url = "...component=%24DirectLink&page=FrontEndViewTender&service=direct&session=T&sp=xyz..."

# Generate Direct URL (remove session parameter):
direct_url = "...component=%24DirectLink&page=FrontEndViewTender&service=direct&sp=xyz..."

# Generate Status URL (replace page component):
status_url = "...component=view&page=WebTenderStatusLists&service=direct&sp=xyz..."
```

**Implementation**: See `utils.py::generate_tender_urls()`

## Current Scraping Strategy

### Phase 1: Listing Page Scraping (✅ Implemented)
**Scope**: Extract basic metadata from tender tables
**Location**: `scraper/logic.py::_scrape_tender_details()`

**Process**:
1. Navigate to `FrontEndTendersByOrganisation`
2. Select department from list (each department has tender count + direct link)
3. Navigate to department's tender table
4. Extract data from each table row:
   - S.No, Tender ID, Publishing/Closing dates
   - Extract `href` from title cell → generate URLs
5. Store in database with status "listing_scraped"

**Result**: Lightweight, fast scraping (5-50 tenders/minute)

### Phase 2: Deep Scraping (⏳ Future Enhancement)
**Scope**: Extract comprehensive details from individual tender pages
**Location**: To be implemented

**Process**:
1. Query database for tenders with `direct_url` populated
2. For each tender:
   - Navigate to `direct_url` (FrontEndViewTender page)
   - Extract all detail fields
   - Parse title to extract unique tender ID
   - Update database record with complete information
3. Mark tender as "fully_scraped"

**Challenge**: Slower (requires page navigation per tender), but captures 100% data

## Database Schema Alignment

The v3 database schema (`database/schema_foundation_v1.sql`) was designed to accommodate **both** listing and detail page data:

### Fields from Listing Page:
```sql
portal_id               INT          -- From portal selection
tender_id_extracted     TEXT         -- Portal serial number
published_at            DATETIME     -- e-Published Date
opening_at              DATETIME     -- Opening Date
closing_at              DATETIME     -- Closing Date
is_live                 BOOLEAN      -- Calculated from closing_at
direct_url              TEXT         -- Link to detail page
status_url              TEXT         -- Generated link
```

### Fields from Detail Page (currently empty):
```sql
title_ref               TEXT         -- Full title with [UNIQUE_ID]
department_name         TEXT
organization_chain      TEXT
emd_amount_raw          TEXT
emd_amount_value        REAL
estimated_cost_raw      TEXT
estimated_cost_value    REAL
tender_type             TEXT
work_type               TEXT
payment_type            TEXT
state_name              TEXT
district                TEXT
city                    TEXT
pincode                 TEXT
location_text           TEXT
```

## Why Fields Are Empty

**User Discovery**: "Most columns are empty in the data grid"

**Root Cause**: Not a display bug or database issue - it's the scraping strategy!
- The scraper is **currently only accessing listing pages**
- Detail page fields **require deep scraping** to populate
- Database schema is ready, but deep scraping is **not yet implemented**

## Future Development Roadmap

### 1. Implement Deep Scraping Module
- Create `scraper/deep_scrape.py` module
- Add database flag: `needs_deep_scrape`, `deep_scrape_completed_at`
- Implement batch processing for `direct_url` navigation
- Add error handling for session timeouts, CAPTCHAs

### 2. Selector/Field Mapping
- Map detail page selectors (similar to listing page locators in `config.py`)
- Create extraction functions for each field type
- Handle variations across NIC portals (1% edge cases)

### 3. Smart Scheduling
- Prioritize high-value tenders (by EMD amount, closing date)
- Incremental deep scraping (scrape new tenders daily)
- Background processing (don't block listing scrape)

### 4. Portal Expansion Beyond NIC
- **Future**: Support non-NIC portals (GEM, state-specific platforms)
- Abstract portal "skills" (see `MIGRATION_GUIDE_FASTAPI_REFLEX.md`)
- Each portal type has different listing/detail page patterns

## Data Visualization Page Indicators

The Data Visualization page now shows **all 28 database columns** to help verify data:

**Visual Distinction** (recommended enhancement):
- 🟢 **Green header**: Fields from listing page (currently populated)
- 🟡 **Yellow header**: Fields requiring deep scraping (future enhancement)
- Badge/tooltip: "Available now" vs "Requires deep scraping"

Example:
```
| Portal 🟢 | Tender ID 🟢 | Title 🟡 | Dept 🟡 | Published 🟢 | Closing 🟢 | EMD 🟡 |
```

## Key Takeaways

1. **NIC portals are highly standardized** - 50+ portals with 99% same structure
2. **Two-tier architecture** - Listing page (fast, basic) vs Detail page (slow, comprehensive)
3. **Current scraping = Phase 1 only** - Listing page metadata extraction
4. **Empty columns ≠ bug** - They're waiting for Phase 2 deep scraping implementation
5. **Database schema is ready** - All 28 columns defined, just need to populate them
6. **URLs are critical** - `direct_url` enables future deep scraping without re-listing

## Technical References

- **Listing Page Extraction**: `scraper/logic.py::_scrape_tender_details()` (line ~729)
- **URL Generation**: `utils.py::generate_tender_urls()` (line ~57)
- **Database Schema**: `database/schema_foundation_v1.sql`
- **Portal Configs**: `base_urls.csv` (50+ NIC portals)
- **Data Visualization**: `tender_dashboard_reflex/dashboard_app/data_visualization.py`

---

**Document Version**: 1.0  
**Last Updated**: February 18, 2026  
**Author**: BlackForest Development Team
