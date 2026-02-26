# Tests

Automated and manual test scripts for Black Forest components.

## Running Tests

```bash
# From project root with venv active:
python -m pytest tests/ -v
```

## Files

| File | What It Tests |
|------|--------------|
| `test_portals.py` | Portal URL retrieval, live scraping sanity check |
| `test_portal_query.py` | DB portal filter queries |
| `test_url_retrieval.py` | HTTP vs Selenium URL fetching paths |
| `test_http_vs_selenium.py` | Engine selection logic |
| `test_excel_db_roundtrip.py` | Excel → SQLite → Excel round-trip integrity |
| `test_excel_import_feature.py` | Excel import edge cases (column mapping, deduplication) |
| `test_batched_extraction_config.py` | Batch extraction threshold/size config |
| `test_tab_workers.py` | Tab-based parallel scraping workers |
| `test_ui_queue_integration.py` | UI message queue event pipeline |
| `test.py` | Miscellaneous one-off tests |

## Notes

- Tests that require a live portal connection are skipped by default when no network is available.
- DB-related tests write to a temp copy of the SQLite database, never the production DB.
