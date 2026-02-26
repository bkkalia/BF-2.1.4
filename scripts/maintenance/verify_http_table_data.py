"""
Verify if NIC portal department tables have complete data via HTTP.
This will tell us if we can get 5-10x speedup with HTTP-first approach.
"""

import requests
from bs4 import BeautifulSoup
import time


def verify_table_data(portal_url, portal_name):
    """Check if HTTP returns complete table data"""
    
    print(f"\n{'='*70}")
    print(f"Testing: {portal_name}")
    print(f"URL: {portal_url}")
    print(f"{'='*70}")
    
    try:
        # Fetch via HTTP
        print("Fetching page via HTTP...")
        start = time.time()
        response = requests.get(
            portal_url,
            timeout=15,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        fetch_time = time.time() - start
        
        print(f"✓ HTTP request: {fetch_time:.2f}s")
        print(f"✓ Status code: {response.status_code}")
        print(f"✓ Content size: {len(response.text):,} bytes")
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all tables
        tables = soup.find_all('table')
        print(f"\n📊 Found {len(tables)} tables in HTML")
        
        # Analyze each table
        for i, table in enumerate(tables, 1):
            rows = table.find_all('tr')
            
            if len(rows) < 3:  # Skip tiny tables
                continue
            
            print(f"\n--- Table {i} ---")
            print(f"Total rows: {len(rows)}")
            
            # Check header row
            header_row = rows[0]
            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            
            if headers:
                print(f"Headers: {headers[:5]}...")  # First 5 headers
            
            # Check data rows
            data_rows_with_content = 0
            sample_data = []
            
            for row in rows[1:11]:  # Check first 10 data rows
                cells = row.find_all(['td', 'th'])
                cell_data = [cell.get_text(strip=True) for cell in cells]
                
                # Count non-empty cells
                non_empty = [c for c in cell_data if c and c not in ['', ' ', '\n']]
                
                if len(non_empty) >= 3:  # At least 3 cells with data
                    data_rows_with_content += 1
                    if len(sample_data) < 3:
                        sample_data.append(cell_data)
            
            print(f"Data rows with content (first 10): {data_rows_with_content}/10")
            
            # Show sample data
            if sample_data:
                print(f"\n📋 Sample data:")
                for idx, row_data in enumerate(sample_data, 1):
                    # Show first 5 cells of each row
                    display_data = row_data[:5] if len(row_data) > 5 else row_data
                    print(f"   Row {idx}: {display_data}")
            else:
                print(f"   ⚠️  No data found in rows!")
            
            # Check for department-related keywords
            table_text = table.get_text().lower()
            keywords = ['department', 'tender', 'organisation', 'published', 'closing']
            found_keywords = [kw for kw in keywords if kw in table_text]
            
            if found_keywords:
                print(f"\n✓ Found keywords: {', '.join(found_keywords)}")
                print(f"✓ This appears to be the department/tender table!")
                
                # Final verdict for this table
                if data_rows_with_content >= 5:
                    print(f"\n{'='*70}")
                    print(f"✅ SUCCESS: Table has complete data via HTTP!")
                    print(f"   → {data_rows_with_content} rows with real data")
                    print(f"   → HTTP-first approach WILL WORK")
                    print(f"   → Expected speedup: 3-10x faster")
                    print(f"{'='*70}")
                    return True
                else:
                    print(f"\n{'='*70}")
                    print(f"⚠️  PARTIAL: Table exists but may need JavaScript")
                    print(f"   → Only {data_rows_with_content} rows with data")
                    print(f"   → Need to verify with Selenium comparison")
                    print(f"{'='*70}")
                    return False
        
        print(f"\n{'='*70}")
        print(f"❌ NO SUITABLE TABLE FOUND")
        print(f"   → Tables exist but no department/tender data detected")
        print(f"   → Selenium required for this portal")
        print(f"{'='*70}")
        return False
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print(f"   → HTTP method failed")
        print(f"   → Must use Selenium")
        return False


def main():
    """Test multiple NIC portals"""
    
    print("="*70)
    print("NIC PORTAL TABLE DATA VERIFICATION")
    print("="*70)
    print("\nThis will check if department tables have complete data via HTTP")
    print("If YES → 5-10x speedup possible with HTTP-first approach")
    print("If NO → Continue with Selenium (but still optimize UI)\n")
    
    portals = [
        {
            'url': 'https://hptenders.gov.in/nicgep/app?page=FrontEndTendersByOrganisation&service=page',
            'name': 'Himachal Pradesh Tenders'
        },
        {
            'url': 'https://etenders.gov.in/eprocure/app?page=FrontEndTendersByOrganisation&service=page',
            'name': 'Central Public Procurement'
        },
        {
            'url': 'https://arunachaltenders.gov.in/nicgep/app?page=FrontEndTendersByOrganisation&service=page',
            'name': 'Arunachal Pradesh Tenders'
        }
    ]
    
    results = {}
    
    for portal in portals:
        try:
            results[portal['name']] = verify_table_data(portal['url'], portal['name'])
            time.sleep(1)  # Brief pause between tests
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user.")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            results[portal['name']] = False
    
    # Summary
    print(f"\n\n{'='*70}")
    print(f"FINAL SUMMARY")
    print(f"{'='*70}\n")
    
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    print(f"Portals tested: {total_count}")
    print(f"HTTP-compatible: {success_count}/{total_count}")
    
    if success_count > 0:
        print(f"\n✅ RECOMMENDATION: Implement HTTP-first hybrid approach")
        print(f"   → {success_count} portal(s) can use fast HTTP parsing")
        print(f"   → Expected speedup: 3-10x for compatible portals")
        print(f"   → Fallback to Selenium for others")
    else:
        print(f"\n⚠️  RECOMMENDATION: Focus on UI queue and tab-based workers")
        print(f"   → HTTP doesn't provide complete data")
        print(f"   → Stick with Selenium for reliability")
        print(f"   → Use UI message queue to eliminate freezing")
        print(f"   → Use tab-based workers for 3x less memory")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
