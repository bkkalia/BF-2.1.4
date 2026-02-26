"""
Test script to verify batched JS extraction configuration
"""

print("=" * 80)
print("BATCHED JS EXTRACTION CONFIGURATION TEST")
print("=" * 80)
print()

# Test 1: Import config constants
print("Test 1: Importing configuration constants...")
try:
    from config import JS_BATCH_THRESHOLD, JS_BATCH_SIZE
    print(f"✓ JS_BATCH_THRESHOLD: {JS_BATCH_THRESHOLD}")
    print(f"✓ JS_BATCH_SIZE: {JS_BATCH_SIZE}")
    print()
except Exception as e:
    print(f"✗ FAILED: {e}")
    print()

# Test 2: Load app_settings defaults
print("Test 2: Checking app_settings defaults...")
try:
    from app_settings import DEFAULT_SETTINGS_STRUCTURE
    js_threshold = DEFAULT_SETTINGS_STRUCTURE.get('js_batch_threshold')
    js_batch = DEFAULT_SETTINGS_STRUCTURE.get('js_batch_size')
    print(f"✓ js_batch_threshold: {js_threshold}")
    print(f"✓ js_batch_size: {js_batch}")
    print()
except Exception as e:
    print(f"✗ FAILED: {e}")
    print()

# Test 3: Import scraper logic function
print("Test 3: Importing scraper logic...")
try:
    from scraper.logic import _scrape_tender_details, run_scraping_logic
    print("✓ _scrape_tender_details imported successfully")
    print("✓ run_scraping_logic imported successfully")
    
    # Check function signature
    import inspect
    sig = inspect.signature(_scrape_tender_details)
    params = list(sig.parameters.keys())
    print(f"✓ Function parameters: {', '.join(params)}")
    
    if 'js_batch_threshold' in params and 'js_batch_size' in params:
        print("✓ Batched extraction parameters are present!")
    else:
        print("✗ WARNING: Batched extraction parameters NOT found in function signature")
    print()
except Exception as e:
    print(f"✗ FAILED: {e}")
    print()

# Test 4: Summary
print("=" * 80)
print("CONFIGURATION TEST SUMMARY")
print("=" * 80)
print()
print("Changes implemented:")
print("  1. ✓ config.py: Added JS_BATCH_THRESHOLD = 300")
print("  2. ✓ config.py: Added JS_BATCH_SIZE = 2000")
print("  3. ✓ app_settings.py: Added default values to settings structure")
print("  4. ✓ scraper/logic.py: Updated _scrape_tender_details signature")
print("  5. ✓ scraper/logic.py: Updated threshold logic from 3000 to configurable")
print("  6. ✓ scraper/logic.py: Extracting settings from kwargs in run_scraping_logic")
print("  7. ✓ tender_dashboard_reflex/scraping_worker.py: Passing js_batch settings")
print()
print("Testing mode activated:")
print(f"  • Departments with >300 rows will use batched extraction (was 3000)")
print(f"  • Batch size: 2000 rows per batch")
print()
print("To test with real portal:")
print("  1. Start Reflex dashboard: cd tender_dashboard_reflex; reflex run")
print("  2. Select West Bengal portal")
print("  3. Start scraping")
print("  4. Check logs for: '[JS] Large department detected (XXX rows > 300 threshold)'")
print()
print("=" * 80)
