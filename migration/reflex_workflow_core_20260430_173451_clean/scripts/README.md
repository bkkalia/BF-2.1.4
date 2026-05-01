# Scripts

Utility scripts for database maintenance, diagnostics, and operational checks.
These are **not** part of the core application — run them manually as needed.

## Subdirectories

### `diagnostics/`
Performance benchmarks and one-off investigative scripts.

| Script | Purpose |
|--------|---------|
| `_bench_search.py` | Benchmark full refresh cycle (get_summary + search_tenders) |
| `_diag_search.py` | Diagnose DB indexes, FTS support, LIKE query timing |
| `_perf_check.py` / `_perf_check2.py` | Portal query performance spot-checks |
| `_run_stats.py` | Print run statistics from the DB |
| `_verify_overlap.py` | Detect duplicate tenders across portals |
| `analyze_db_schema.py` | Print full schema of the SQLite database |
| `analyze_js_batch_performance.py` | Profile JS batch extraction timings |

### `maintenance/`
Database cleanup, integrity checks, and portal health scripts.

| Script | Purpose |
|--------|---------|
| `check_*.py` | Per-portal or per-feature health checks |
| `verify_*.py` | Post-scrape data verification |
| `fix_database_duplicates.py` | Remove exact-duplicate rows from tenders table |
| `cleanup_stuck_runs.py` | Mark runs stuck in `running` state as failed |
| `monitor_active_batch.py` | Watch a currently-running batch scrape in real time |
| `temp_*.py` | Temporary investigation scripts (safe to delete after use) |
| `zilla_parishad_status.py` | Zilla Parishad portal status report |

## Usage

```bash
# From project root with venv active:
python scripts/diagnostics/_bench_search.py
python scripts/maintenance/check_db_schema.py
```
