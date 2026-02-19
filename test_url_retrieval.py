"""Test script to verify URL retrieval from database"""
import sys
sys.path.insert(0, r'D:\Dev84\BF 2.1.4\tender_dashboard_reflex')

from tender_dashboard_reflex import db

# Test search with default filters
filters = db.TenderFilters()
results, total = db.search_tenders(filters, page=1, page_size=5)

print(f"=== RETRIEVED {len(results)} TENDERS (Total: {total}) ===\n")

for i, tender in enumerate(results[:5], 1):
    print(f"--- Tender {i} ---")
    print(f"Portal: {tender.get('portal_name', 'N/A')}")
    print(f"ID: {tender.get('tender_id_extracted', 'N/A')}")
    print(f"Title: {tender.get('title_ref', 'N/A')[:80]}...")
    print(f"Department: {tender.get('department_name', 'N/A')}")
    print(f"Closing: {tender.get('closing_at', 'N/A')}")
    
    # Check URL fields
    tender_url = tender.get('tender_url', '')
    status_url = tender.get('status_url', '')
    
    print(f"\n✅ Direct URL: {tender_url[:100]}..." if tender_url else "❌ Direct URL: EMPTY")
    print(f"✅ Status URL: {status_url[:100]}..." if status_url else "❌ Status URL: EMPTY")
    print()

print("\n=== URL SUMMARY ===")
tenders_with_urls = sum(1 for t in results if t.get('tender_url') and t.get('status_url'))
print(f"Tenders with both URLs: {tenders_with_urls}/{len(results)}")
print(f"Success Rate: {tenders_with_urls/len(results)*100:.1f}%" if results else "No data")
