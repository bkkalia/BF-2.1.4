"""
Portal Testing Helper Script
Automates testing of multiple portals and generates reports
"""

import subprocess
import json
import os
from datetime import datetime
from pathlib import Path

# Portal batches for organized testing
PORTAL_BATCHES = {
    "batch_1_nic_north": [
        "HP Tenders",
        "Punjab",
        "Haryana",
        "Chandigarh",
        "Delhi"
    ],
    "batch_2_nic_east": [
        "Jharkhand",
        "Odisha",
        "West Bengal",
        "Meghalaya"
    ],
    "batch_3_nic_west": [
        "Maharashtra",
        "Goa",
        "Madhya Pradesh",
        "Chhattisgarh"
    ],
    "batch_4_nic_south": [
        "Kerala",
        "Tamil Nadu",
        "Telangana",
        "Andaman Nicobar"
    ],
    "batch_5_nic_northeast": [
        "Arunachal Pradesh",
        "Manipur",
        "Tripura",
        "Ladakh",
        "Jammu Kashmir"
    ],
    "batch_6_nic_central_uttar": [
        "Uttar Pradesh",
        "Uttarakhand",
        "Rajasthan"
    ],
    "batch_7_central": [
        "CPPP1 eProcure",
        "CPPP2 eTenders",
        "DefProc",
        "GePNIC",
        "NRRDA"
    ]
}

def run_portal_test(portal_name, mode="only-new"):
    """
    Run a single portal test using CLI
    
    Args:
        portal_name: Name of portal from base_urls.csv
        mode: 'only-new' or 'full-rescrape'
    
    Returns:
        dict: Test results
    """
    print(f"\n{'='*60}")
    print(f"Testing Portal: {portal_name}")
    print(f"Mode: {mode}")
    print(f"{'='*60}\n")
    
    start_time = datetime.now()
    
    # Build CLI command
    cli_args = [
        "python", "cli_main.py",
        "--portal", portal_name,
        "--json-events"
    ]
    
    if mode == "full-rescrape":
        cli_args.append("--full-rescrape")
    
    try:
        # Run the scraping process
        result = subprocess.run(
            cli_args,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout per portal
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Parse results from output
        success = result.returncode == 0
        
        # Extract key metrics from JSON events
        tenders_extracted = 0
        departments_count = 0
        errors = []
        
        for line in result.stdout.split('\n'):
            if line.strip().startswith('{'):
                try:
                    event = json.loads(line)
                    if event.get('event_type') == 'completed':
                        tenders_extracted = event.get('tenders_extracted', 0)
                        departments_count = event.get('departments_processed', 0)
                    elif event.get('event_type') == 'error':
                        errors.append(event.get('message', 'Unknown error'))
                except json.JSONDecodeError:
                    pass
        
        return {
            'portal': portal_name,
            'success': success,
            'duration_seconds': duration,
            'tenders': tenders_extracted,
            'departments': departments_count,
            'errors': errors,
            'timestamp': start_time.isoformat(),
            'mode': mode
        }
        
    except subprocess.TimeoutExpired:
        return {
            'portal': portal_name,
            'success': False,
            'duration_seconds': 600,
            'tenders': 0,
            'departments': 0,
            'errors': ['Timeout after 10 minutes'],
            'timestamp': start_time.isoformat(),
            'mode': mode
        }
    except Exception as e:
        return {
            'portal': portal_name,
            'success': False,
            'duration_seconds': 0,
            'tenders': 0,
            'departments': 0,
            'errors': [str(e)],
            'timestamp': start_time.isoformat(),
            'mode': mode
        }

def run_batch_test(batch_name, portals, mode="only-new"):
    """
    Run tests for a batch of portals
    
    Args:
        batch_name: Name of the batch
        portals: List of portal names
        mode: 'only-new' or 'full-rescrape'
    
    Returns:
        dict: Batch test results
    """
    print(f"\n{'#'*60}")
    print(f"# BATCH TEST: {batch_name}")
    print(f"# Portals: {len(portals)}")
    print(f"# Mode: {mode}")
    print(f"{'#'*60}\n")
    
    results = []
    for portal in portals:
        result = run_portal_test(portal, mode)
        results.append(result)
        
        # Print summary
        status = "✅ SUCCESS" if result['success'] else "❌ FAILED"
        print(f"\n{status} - {portal}")
        print(f"  Tenders: {result['tenders']}, Departments: {result['departments']}")
        print(f"  Duration: {result['duration_seconds']:.1f}s")
        if result['errors']:
            print(f"  Errors: {', '.join(result['errors'])}")
    
    return {
        'batch_name': batch_name,
        'total_portals': len(portals),
        'results': results,
        'timestamp': datetime.now().isoformat()
    }

def save_test_report(batch_result):
    """Save test results to JSON file"""
    report_dir = Path("batch_run_reports") / "portal_tests"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_name = batch_result['batch_name']
    filename = report_dir / f"{batch_name}_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(batch_result, f, indent=2)
    
    print(f"\n📄 Test report saved: {filename}")
    return filename

def generate_markdown_summary(batch_result):
    """Generate markdown summary of batch test"""
    lines = []
    lines.append(f"# Batch Test Summary: {batch_result['batch_name']}")
    lines.append(f"**Date:** {batch_result['timestamp']}")
    lines.append(f"**Total Portals:** {batch_result['total_portals']}")
    lines.append("")
    
    # Success summary
    successful = sum(1 for r in batch_result['results'] if r['success'])
    failed = batch_result['total_portals'] - successful
    lines.append(f"**Success Rate:** {successful}/{batch_result['total_portals']} ({100*successful/batch_result['total_portals']:.1f}%)")
    lines.append("")
    
    # Portal results table
    lines.append("| Portal | Status | Tenders | Departments | Duration | Errors |")
    lines.append("|--------|--------|---------|-------------|----------|--------|")
    
    for result in batch_result['results']:
        status = "✅" if result['success'] else "❌"
        errors = ", ".join(result['errors'][:2]) if result['errors'] else "None"
        if len(result['errors']) > 2:
            errors += f" (+{len(result['errors'])-2} more)"
        
        lines.append(
            f"| {result['portal']} | {status} | {result['tenders']} | "
            f"{result['departments']} | {result['duration_seconds']:.1f}s | {errors} |"
        )
    
    return "\n".join(lines)

def main():
    """Main test runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Portal Testing Helper")
    parser.add_argument("--batch", choices=list(PORTAL_BATCHES.keys()),
                       help="Batch to test")
    parser.add_argument("--all", action="store_true",
                       help="Test all portals (all batches)")
    parser.add_argument("--portal", type=str,
                       help="Test single portal by name")
    parser.add_argument("--mode", choices=["only-new", "full-rescrape"],
                       default="only-new",
                       help="Scraping mode")
    
    args = parser.parse_args()
    
    if args.portal:
        # Test single portal
        result = run_portal_test(args.portal, args.mode)
        print(f"\n{'='*60}")
        print(f"Test Result: {'✅ SUCCESS' if result['success'] else '❌ FAILED'}")
        print(f"Tenders: {result['tenders']}, Departments: {result['departments']}")
        print(f"Duration: {result['duration_seconds']:.1f}s")
        if result['errors']:
            print(f"Errors: {', '.join(result['errors'])}")
        print(f"{'='*60}\n")
        
    elif args.batch:
        # Test specific batch
        portals = PORTAL_BATCHES[args.batch]
        batch_result = run_batch_test(args.batch, portals, args.mode)
        
        # Save report
        report_file = save_test_report(batch_result)
        
        # Generate markdown summary
        summary = generate_markdown_summary(batch_result)
        print("\n" + summary)
        
        # Save markdown summary
        md_file = report_file.with_suffix('.md')
        with open(md_file, 'w') as f:
            f.write(summary)
        print(f"\n📄 Markdown summary saved: {md_file}")
        
    elif args.all:
        # Test all batches
        print("\n🚀 Starting full portal testing suite...")
        print(f"Total portals: {sum(len(p) for p in PORTAL_BATCHES.values())}")
        
        all_results = []
        for batch_name, portals in PORTAL_BATCHES.items():
            batch_result = run_batch_test(batch_name, portals, args.mode)
            all_results.append(batch_result)
            save_test_report(batch_result)
        
        # Overall summary
        total_portals = sum(r['total_portals'] for r in all_results)
        total_success = sum(
            sum(1 for res in r['results'] if res['success'])
            for r in all_results
        )
        
        print(f"\n{'='*60}")
        print(f"OVERALL RESULTS")
        print(f"{'='*60}")
        print(f"Total Portals Tested: {total_portals}")
        print(f"Successful: {total_success}")
        print(f"Failed: {total_portals - total_success}")
        print(f"Success Rate: {100*total_success/total_portals:.1f}%")
        print(f"{'='*60}\n")
        
    else:
        parser.print_help()
        print("\nExample usage:")
        print("  python test_portals.py --batch batch_1_nic_north")
        print("  python test_portals.py --portal 'HP Tenders'")
        print("  python test_portals.py --all --mode only-new")

if __name__ == "__main__":
    main()
