"""
Test script to determine if HTTP requests can replace Selenium for NIC portals.

This script compares:
1. HTTP request speed vs Selenium page load speed
2. Whether portal HTML is accessible via simple HTTP GET
3. Whether tender data tables are in static HTML or require JavaScript

Usage:
    python test_http_vs_selenium.py
    
Results will help decide if HTTP-first hybrid approach can achieve 10-50x speedup.
"""

import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class PortalSpeedTester:
    """Compare HTTP vs Selenium performance for NIC portals"""
    
    def __init__(self):
        self.results = []
    
    def test_http(self, url, description=""):
        """Test HTTP GET request speed and content"""
        print(f"\n{'='*60}")
        print(f"Testing HTTP: {description or url}")
        print(f"{'='*60}")
        
        try:
            start = time.time()
            response = requests.get(
                url,
                timeout=15,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            http_time = time.time() - start
            
            print(f"✓ HTTP Status: {response.status_code}")
            print(f"✓ Response time: {http_time:.2f} seconds")
            print(f"✓ Content size: {len(response.text):,} bytes")
            
   # Analyze HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            tables = soup.find_all('table')
            forms = soup.find_all('form')
            scripts = soup.find_all('script')
            
            print(f"\n📊 Content Analysis:")
            print(f"   Tables found: {len(tables)}")
            print(f"   Forms found: {len(forms)}")
            print(f"   JavaScript tags: {len(scripts)}")
            
            # Check for common tender table indicators
            has_tender_table = False
            for table in tables[:5]:  # Check first 5 tables
                table_text = table.get_text().lower()
                if any(keyword in table_text for keyword in ['tender', 'department', 'closing', 'published']):
                    has_tender_table = True
                    print(f"   ✓ Found tender-related table")
                    break
            
            # Check if JavaScript-heavy
            inline_js = sum(len(script.string or '') for script in scripts)
            is_js_heavy = len(scripts) > 10 or inline_js > 50000
            
            print(f"\n🔍 Verdict:")
            if has_tender_table and not is_js_heavy:
                print(f"   ✅ LIKELY WORKS WITH HTTP")
                print(f"   → Static HTML tables detected")
                print(f"   → Minimal JavaScript")
                verdict = "HTTP_SUITABLE"
            elif has_tender_table:
                print(f"   ⚠️  MAY NEED SELENIUM")
                print(f"   → Tables found but heavy JavaScript detected")
                print(f"   → Try HTTP first, fallback to Selenium")
                verdict = "HTTP_FALLBACK"
            else:
                print(f"   ❌ NEEDS SELENIUM")
                print(f "   → No tender tables in static HTML")
                print(f"   → Page likely requires JavaScript rendering")
                verdict = "SELENIUM_REQUIRED"
            
            return {
                'method': 'HTTP',
                'url': url,
                'time': http_time,
                'status_code': response.status_code,
                'tables': len(tables),
                'verdict': verdict,
                'success': True
            }
            
        except Exception as e:
            print(f"❌ HTTP request failed: {e}")
            return {
                'method': 'HTTP',
                'url': url,
                'time': None,
                'error': str(e),
                'verdict': 'HTTP_FAILED',
                'success': False
            }
    
    def test_selenium(self, url, description=""):
        """Test Selenium WebDriver speed"""
        print(f"\n{'='*60}")
        print(f"Testing Selenium: {description or url}")
        print(f"{'='*60}")
        
        driver = None
        try:
            # Setup Chrome options
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # Run headless for speed test
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            print("Setting up ChromeDriver...")
            service = Service(ChromeDriverManager().install())
            
            start = time.time()
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver_setup_time = time.time() - start
            print(f"✓ Driver setup: {driver_setup_time:.2f} seconds")
            
            # Navigate to page
            print(f"Loading page...")
            start = time.time()
            driver.get(url)
            
            # Wait for page to be ready
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            page_load_time = time.time() - start
            print(f"✓ Page load: {page_load_time:.2f} seconds")
            
            # Find tables
            tables = driver.find_elements(By.TAG_NAME, "table")
            print(f"✓ Tables found: {len(tables)}")
            
            total_time = driver_setup_time + page_load_time
            print(f"\n📊 Total time (driver + page): {total_time:.2f} seconds")
            
            return {
                'method': 'Selenium',
                'url': url,
                'setup_time': driver_setup_time,
                'load_time': page_load_time,
                'total_time': total_time,
                'tables': len(tables),
                'success': True
            }
            
        except Exception as e:
            print(f"❌ Selenium failed: {e}")
            return {
                'method': 'Selenium',
                'url': url,
                'error': str(e),
                'success': False
            }
        finally:
            if driver:
                driver.quit()
    
    def compare(self, url, description=""):
        """Compare HTTP vs Selenium for a portal"""
        print(f"\n\n{'#'*60}")
        print(f"# PORTAL TEST: {description or url}")
        print(f"{'#'*60}")
        
        # Test HTTP first
        http_result = self.test_http(url, description)
        self.results.append(http_result)
        
        # Test Selenium
        selenium_result = self.test_selenium(url, description)
        self.results.append(selenium_result)
        
        # Comparison
        if http_result['success'] and selenium_result['success']:
            speedup = selenium_result['load_time'] / http_result['time']
            print(f"\n{'='*60}")
            print(f"⚡ SPEED COMPARISON")
            print(f"{'='*60}")
            print(f"HTTP time:      {http_result['time']:.2f}s")
            print(f"Selenium time:  {selenium_result['load_time']:.2f}s")
            print(f"Speedup:        {speedup:.1f}x faster with HTTP")
            
            if http_result['verdict'] == 'HTTP_SUITABLE':
                print(f"\n🎯 RECOMMENDATION: Use HTTP-first approach")
                print(f"   → {speedup:.0f}x speedup possible")
                print(f"   → Static HTML parsing works")
            elif http_result['verdict'] == 'HTTP_FALLBACK':
                print(f"\n🎯 RECOMMENDATION: Try HTTP first, fallback to Selenium")
                print(f"   → {speedup:.0f}x speedup for successful HTTP requests")
                print(f"   → Keep Selenium as backup for JS-heavy pages")
            else:
                print(f"\n🎯 RECOMMENDATION: Stick with Selenium")
                print(f"   → Page requires JavaScript rendering")
        
        return http_result, selenium_result
    
    def print_summary(self):
        """Print summary of all tests"""
        print(f"\n\n{'#'*60}")
        print(f"# SUMMARY OF ALL TESTS")
        print(f"{'#'*60}\n")
        
        http_results = [r for r in self.results if r['method'] == 'HTTP' and r['success']]
        selenium_results = [r for r in self.results if r['method'] == 'Selenium' and r['success']]
        
        if http_results and selenium_results:
            avg_http = sum(r['time'] for r in http_results) / len(http_results)
            avg_selenium = sum(r['load_time'] for r in selenium_results) / len(selenium_results)
            avg_speedup = avg_selenium / avg_http
            
            print(f"Average HTTP time:      {avg_http:.2f}s")
            print(f"Average Selenium time:  {avg_selenium:.2f}s")
            print(f"Average speedup:        {avg_speedup:.1f}x")
            
            # Count verdicts
            http_suitable = sum(1 for r in http_results if r.get('verdict') == 'HTTP_SUITABLE')
            http_fallback = sum(1 for r in http_results if r.get('verdict') == 'HTTP_FALLBACK')
            selenium_required = sum(1 for r in http_results if r.get('verdict') == 'SELENIUM_REQUIRED')
            
            print(f"\nVerdicts:")
            print(f"   HTTP suitable:       {http_suitable}/{len(http_results)} portals")
            print(f"   HTTP with fallback:  {http_fallback}/{len(http_results)} portals")
            print(f"   Selenium required:   {selenium_required}/{len(http_results)} portals")
            
            if http_suitable > 0:
                print(f"\n✅ FINAL RECOMMENDATION:")
                print(f"   Implement HTTP-first hybrid approach")
                print(f"   Expected speedup: {avg_speedup:.0f}x for {http_suitable + http_fallback} portals")
                print(f"   Estimated time savings: {(avg_selenium - avg_http) * (http_suitable + http_fallback):.0f}s per full scrape")
            else:
                print(f"\n⚠️  FINAL RECOMMENDATION:")
                print(f"   Continue using Selenium (HTTP not viable for these portals)")


def main():
    """Test common NIC portals"""
    tester = PortalSpeedTester()
    
    # List of NIC portals to test
    test_portals = [
        {
            'url': 'https://hptenders.gov.in/nicgep/app?page=FrontEndTendersByOrganisation&service=page',
            'description': 'Himachal Pradesh Tenders'
        },
        {
            'url': 'https://etenders.gov.in/eprocure/app?page=FrontEndTendersByOrganisation&service=page',
            'description': 'Central Public Procurement Portal'
        },
        {
            'url': 'https://arunachaltenders.gov.in/nicgep/app?page=FrontEndTendersByOrganisation&service=page',
            'description': 'Arunachal Pradesh Tenders'
        }
    ]
    
    print("=" * 60)
    print("NIC PORTAL HTTP vs SELENIUM SPEED TEST")
    print("=" * 60)
    print("\nThis test will:")
    print("1. Try HTTP GET requests to each portal")
    print("2. Try Selenium WebDriver page loads")
    print("3. Compare speeds and analyze content")
    print("4. Recommend best strategy\n")
    
    input("Press Enter to start testing...")
    
    # Test each portal
    for portal in test_portals:
        try:
            tester.compare(portal['url'], portal['description'])
            time.sleep(2)  # Brief pause between tests
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user.")
            break
        except Exception as e:
            print(f"\n❌ Error testing {portal['description']}: {e}")
            continue
    
    # Print summary
    tester.print_summary()
    
    print("\n" + "="*60)
    print("Testing complete! Review results above.")
    print("="*60)


if __name__ == "__main__":
    main()
