# Black Forest Tender Scraper - Roadmap

## Baseline (Current)
- Version: **2.2.2**
- SQLite-first persistence active
- Tiered backup policy active (daily/weekly/monthly/yearly)
- Tender integrity rules active (latest per portal+tender ID, missing IDs removed)
- Quick Delta default + optional Full Delta active
- Department URL coverage tracker active (manifest + report export)
- **Time-based load balancing** for multi-worker scraping (dept overhead + tender count)

## Phase 1 (IMMEDIATE - Next Version)
### **CLI Subprocess Architecture with GUI Control** 🎯 PRIORITY
**Problem:** Current threading architecture causes:
- GUI freezing during scraping (2-6 min per department)
- Emergency stop delays (5+ minutes)
- UI unresponsiveness
- Multi-worker performance degradation (3x slower than single worker!)

**Solution:** Process separation architecture
```
GUI Process (always responsive)
  └─> Launch: python cli_main.py department --all
  └─> Monitor: stdout/logs for progress
  └─> Control: subprocess.terminate() for instant stop
```

**Implementation Tasks:**
1. Create `gui/subprocess_runner.py` - subprocess management layer
2. Add structured JSON output to CLI (`{"type": "progress", ...}`)
3. Update GUI tabs to use subprocess instead of direct scraper calls
4. Implement real-time log monitoring (tail -f logs/app_*.log)
5. Add instant emergency stop via subprocess.kill()
6. Preserve resume functionality (partial saves + restart)

**Benefits:**
- ✅ GUI always responsive (no blocking operations)
- ✅ Emergency stop works instantly (kill subprocess)
- ✅ Better error isolation (crash doesn't kill GUI)
- ✅ Can run CLI standalone for debugging
- ✅ Foundation for multi-portal dashboard (monitor multiple processes)

**Target:** v2.3.0 - "CLI Subprocess Architecture"

## Phase 2 (Near-term)
### 1) Archive Lifecycle
- Introduce explicit live/archive status on persisted tenders.
- Mark/archive tenders older than threshold (for example, closed > 90 days).
- Keep archive queryable without slowing live searches.

### 2) Portal Normalization
- Normalize portal aliases (example: human label vs slug form).
- Standardize stored portal key for stronger dedupe/search consistency.

### 3) Date Normalization
- Parse and store canonical date formats for published/open/closing fields.
- Improve date-range filtering and archive automation reliability.

### 4) Operational Hardening
- Extend portal diagnostics capture (DOM/config snapshots).
- Improve automated recovery paths for changed portal layouts.

## Phase 3 (Mid-term)
### 1) Foundation Schema Parallel Write
- Begin parallel writes to foundation entities:
  - `portals`
  - `scrape_runs`
  - `tender_items`
- Maintain compatibility with current `runs`/`tenders` reads.

### 2) History Tracking
- Add immutable snapshot/status history for tender changes.
- Prepare for future corrigendum-aware monitoring.

### 3) Search Enhancements
- Add high-performance live filters on normalized fields.
- Optional FTS for title/organization keyword search.

## Phase 4 (Future)
### 1) Alerting & Accounts
- User-defined saved filters and alerts.
- Event-driven notifications (new/changed tenders).

### 2) Deep Tender Expansion
- Capture deeper tender details and files metadata.
- Link deep details to canonical portal+tender identity.

### 3) Integration Surface
- Stable export/report interfaces for downstream systems.

## Guiding Principles
- Reliability first over feature volume.
- Backward-compatible migrations.
- Clear observability in logs and reports.
- Centralized data model with predictable retention.

---
Last updated: February 13, 2026
