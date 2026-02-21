# Version 2.4.0 → 2.5.0 Testing Guide

**Current Status:** Version 2.3.3 tested with 2 portals (HP, Punjab)  
**Goal:** Test all 29 portals before 2.5.0 release

---

## 🎯 Strategy

1. **Current Phase (2.4.0):** Test all 29 portals with existing CLI + Reflex + SQLite
2. **When Stable:** Bump to 2.5.0 with PostgreSQL migration
3. **Future:** Export stable code and start fresh 3.0 migration

---

## 📋 Quick Start

### Test a Single Portal
```bash
# Using CLI directly
python cli_main.py --portal "HP Tenders" --only-new

# Using test helper
python test_portals.py --portal "HP Tenders"
```

### Test a Batch of Portals
```bash
# Test North India NIC portals
python test_portals.py --batch batch_1_nic_north

# Test all central portals
python test_portals.py --batch batch_7_central
```

### Test All Portals (Overnight Run)
```bash
# Test all 29 portals in sequence
python test_portals.py --all --mode only-new

# Full rescrape mode (for clean baseline)
python test_portals.py --all --mode full-rescrape
```

---

## 📊 Monitoring Progress

### View Testing Progress
Open `PORTAL_TESTING_PROGRESS.md` to see:
- Which portals have been tested
- Success/failure status
- Tender and department counts
- Known issues per portal

### View Detailed Roadmap
See `ROADMAP_TO_2.5.md` for:
- Complete testing checklist
- Infrastructure requirements
- Success criteria
- Timeline estimates

### View Test Reports
Check `batch_run_reports/portal_tests/` for:
- JSON test results
- Markdown summaries
- Performance metrics
- Error logs

---

## 🔧 Testing Workflow

### Phase 1: Quick Validation (Week 1)
1. Run `batch_1_nic_north` - Similar to tested HP/Punjab
2. Review results, fix any issues
3. Run `batch_2_nic_east` 
4. Continue through batches 3-6

### Phase 2: Central Portals (Week 2)
1. Run `batch_7_central` - May have different layouts
2. Document any unique quirks
3. Update scraper if needed

### Phase 3: Full Regression (Week 3)
1. Run `--all` overnight
2. Review all results
3. Fix any remaining issues
4. Re-test failed portals

### Phase 4: Performance Testing (Week 4)
1. Test 10 portals in parallel
2. Monitor memory usage
3. Verify checkpoint resume works
4. Benchmark scraping times

---

## 📈 Tracking Tools

### 1. Manual Testing
Use Reflex dashboard at http://localhost:3000:
- Navigate to "Scraping Control" 
- Select portal from dropdown
- Click "Start Scraping"
- Monitor real-time progress
- Check results in "Dashboard" tab

### 2. CLI Testing
Run portals individually:
```bash
python cli_main.py --portal "Maharashtra"
```

### 3. Batch Testing (Recommended)
Use the test helper script:
```bash
# Test one batch
python test_portals.py --batch batch_3_nic_west

# This will:
# - Run each portal in sequence
# - Generate JSON + Markdown reports
# - Show success/failure summary
# - Log all errors
```

---

## 🐛 Troubleshooting

### Portal Fails to Load
1. Check portal URL in `base_urls.csv`
2. Verify portal is online (visit URL in browser)
3. Check for CAPTCHA requirements
4. Review error logs in `logs/` folder

### Tender Extraction Issues
1. Check if portal layout changed
2. Review `portal_config_memory.json` for learned locators
3. Add portal-specific handling in `scraper/logic.py` if needed
4. Test with `--full-rescrape` to get fresh baseline

### Performance Issues
1. Check memory usage with Task Manager
2. Reduce parallel workers if needed
3. Increase timeout values in Settings
4. Check network connectivity

### Data Quality Issues
1. Run duplicate check: `python tools/check_sqlite_duplicates.py`
2. Verify tender ID extraction in exports
3. Check closing date parsing accuracy
4. Review SQLite database integrity

---

## ✅ Success Criteria per Portal

Each portal passes when:
- ✅ Department list loads (count > 0)
- ✅ Tender extraction works (count > 0)
- ✅ No critical errors in logs
- ✅ Tender IDs extracted correctly
- ✅ Closing dates parsed accurately
- ✅ Export generates successfully
- ✅ Dashboard shows correct portal health

---

## 📝 Reporting Issues

When a portal test fails:

1. **Document the Issue:**
   - Portal name
   - Error message
   - Timestamp
   - Mode (only-new vs full-rescrape)

2. **Add to Known Issues:**
   Update `PORTAL_TESTING_PROGRESS.md` with:
   - Issue description
   - Reproduction steps
   - Temporary workaround (if any)

3. **Fix Priority:**
   - **High:** Portal completely broken
   - **Medium:** Partial extraction working
   - **Low:** Minor data quality issues

---

## 🎯 Next Steps After All Tests Pass

Once all 29 portals are tested:

1. **Update Documentation:**
   - Mark all portals as ✅ in progress tracker
   - Document portal-specific quirks
   - Update performance benchmarks

2. **Version Bump:**
   - Update `config.py` to version 2.4.0
   - Update `CHANGELOG.md` with test results
   - Commit and tag in git

3. **Start 2.5.0 Migration:**
   - Set up PostgreSQL locally
   - Create migration scripts
   - Test data migration
   - Update all database access code
   - Re-test all portals with PostgreSQL

4. **Code Export:**
   - Clean up unused code
   - Document all configurations
   - Create `BF-2.5-stable` export
   - Prepare for 3.0 development

---

## 📞 Need Help?

Check these resources:
- `ROADMAP_TO_2.5.md` - Complete roadmap
- `PORTAL_TESTING_PROGRESS.md` - Current status
- `docs/DASHBOARD_USER_GUIDE.md` - Dashboard usage
- `CLI_HELP.md` - CLI reference
- `MIGRATION_GUIDE_FASTAPI_REFLEX.md` - Future 3.0 architecture

---

**Happy Testing! 🚀**

*Remember: Version 2.5 is about stability and validation. Take time to test thoroughly before the big 3.0 migration.*
