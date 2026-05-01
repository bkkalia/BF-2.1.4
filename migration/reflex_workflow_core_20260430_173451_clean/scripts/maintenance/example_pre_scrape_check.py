"""
Example: Pre-Scrape Resume Check

This shows how to use cleanup_service.check_portal_resume()
before starting a new portal scrape.

This is the BEST integration option per user requirements.
"""

from cleanup_service import check_portal_resume, cleanup_run

def start_portal_scrape(portal_name):
    """
    Example function showing how to integrate pre-scrape check.
    
    This should be called BEFORE starting actual scrape.
    """
    print(f"\n{'='*60}")
    print(f"Pre-Scrape Check: {portal_name}")
    print(f"{'='*60}")
    
    # Check if portal has resumable run
    check = check_portal_resume(portal_name)
    
    if not check['has_running']:
        print(f"✓ No active run found - safe to start new scrape")
        # START NEW SCRAPE HERE
        return
    
    # Active run exists
    run_id = check['run_id']
    age_hours = check['age_hours']
    action = check['action']
    
    print(f"⚠️  Active run found: #{run_id}")
    print(f"   Started: {check['started_at']}")
    print(f"   Age: {age_hours:.1f} hours")
    print(f"   Resumable: {check['resumable']}")
    print(f"   Reason: {check['reason']}")
    print(f"   Recommended action: {action}")
    
    if action == 'resume':
        print(f"\n✓ RESUME existing run #{run_id}")
        # RESUME SCRAPE WITH CHECKPOINT HERE
        
    elif action == 'cleanup':
        print(f"\n✗ Run is too old and cannot be resumed")
        print(f"   Cleaning up run #{run_id}...")
        if cleanup_run(run_id):
            print(f"   ✓ Cleaned up - safe to start new scrape")
            # START NEW SCRAPE HERE
        else:
            print(f"   ✗ Cleanup failed - manual intervention needed")
            
    elif action == 'wait':
        print(f"\n⏳ Run is recent but has no progress - might still be starting")
        print(f"   Recommend waiting or manual inspection")
        
    else:
        print(f"\n❓ Unknown action: {action}")


if __name__ == '__main__':
    # Test with all portals
    test_portals = [
        "Delhi",
        "Punjab", 
        "CPPP1",
        "CPPP2",
        "Kerala",
        "HP",
        "Haryana",
        "Jharkhand",
        "Odisha",
        "Ladakh"
    ]
    
    print("\n" + "="*60)
    print("PRE-SCRAPE RESUME CHECK EXAMPLES")
    print("="*60)
    
    for portal in test_portals:
        start_portal_scrape(portal)
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print("="*60)
    print("Key points:")
    print("  1. Always call check_portal_resume() BEFORE starting scrape")
    print("  2. If action='resume', use existing checkpoint")
    print("  3. If action='cleanup', clean old run and start fresh")
    print("  4. If action='wait', defer to user or wait")
    print("  5. 24-hour threshold prevents false positives")
