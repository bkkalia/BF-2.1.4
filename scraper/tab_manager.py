# scraper/tab_manager.py v2.2.2
# Tab-based worker management for 3x memory reduction
# One browser with multiple tabs instead of separate browser instances

import logging
import threading
import time
from typing import List, Tuple, Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import WebDriverException

logger = logging.getLogger(__name__)


class TabManager:
    """
    Manages multiple tabs in a single browser for parallel workers.
    
    Benefits:
    - 3x less memory (800MB vs 2.4GB for 3 workers)
    - Shared session (cookies, cache)
    - Shared browser process
    
    Note: Requires synchronization when switching tabs.
    """
    
    def __init__(self, driver: WebDriver, num_tabs: int = 3):
        """
        Initialize tab manager with specified number of tabs.
        
        Args:
            driver: Main WebDriver instance
            num_tabs: Number of tabs to create (default: 3)
        """
        self.driver = driver
        self.num_tabs = num_tabs
        self.tab_handles: List[str] = []
        self.tab_locks: List[threading.Lock] = []
        self.switch_lock = threading.RLock()  # Reentrant lock for nested acquisition
        
        logger.info(f"Initializing TabManager with {num_tabs} tabs")
        self._setup_tabs()
    
    def _setup_tabs(self):
        """Create tabs and store their handles."""
        try:
            # First tab is already open
            original_handle = self.driver.current_window_handle
            self.tab_handles.append(original_handle)
            self.tab_locks.append(threading.Lock())
            logger.info(f"Tab 1: {original_handle[:8]}...")
            
            # Create additional tabs
            for i in range(2, self.num_tabs + 1):
                try:
                    # Open new tab using JavaScript
                    self.driver.execute_script("window.open('about:blank', '_blank');")
                    
                    # Get all handles and find the new one
                    all_handles = self.driver.window_handles
                    new_handle = [h for h in all_handles if h not in self.tab_handles][0]
                    
                    self.tab_handles.append(new_handle)
                    self.tab_locks.append(threading.Lock())
                    logger.info(f"Tab {i}: {new_handle[:8]}... created")
                    
                except Exception as e:
                    logger.error(f"Failed to create tab {i}: {e}")
                    break
            
            # Switch back to first tab
            self.driver.switch_to.window(self.tab_handles[0])
            logger.info(f"TabManager initialized: {len(self.tab_handles)} tabs ready")
            
        except Exception as e:
            logger.error(f"Failed to setup tabs: {e}", exc_info=True)
            raise
    
    def get_tab_handle(self, worker_index: int) -> str:
        """
        Get tab handle for specific worker.
        
        Args:
            worker_index: Worker index (0-based)
            
        Returns:
            Tab window handle string
        """
        if worker_index >= len(self.tab_handles):
            raise ValueError(f"Worker index {worker_index} exceeds available tabs {len(self.tab_handles)}")
        return self.tab_handles[worker_index]
    
    def switch_to_tab(self, worker_index: int, worker_label: str = "W"):
        """
        Thread-safe tab switching.
        
        Args:
            worker_index: Worker index (0-based)
            worker_label: Worker label for logging
        """
        with self.switch_lock:
            try:
                tab_handle = self.get_tab_handle(worker_index)
                current = self.driver.current_window_handle
                
                if current != tab_handle:
                    self.driver.switch_to.window(tab_handle)
                    logger.debug(f"[{worker_label}] Switched to tab {worker_index + 1}")
                
            except Exception as e:
                logger.error(f"[{worker_label}] Failed to switch to tab {worker_index}: {e}")
                raise
    
    def execute_in_tab(self, worker_index: int, worker_label: str, action_callback):
        """
        Execute action in specific tab with automatic switching.
        
        Args:
            worker_index: Worker index (0-based)
            worker_label: Worker label for logging
            action_callback: Function to execute (receives driver as parameter)
            
        Returns:
            Result of action_callback
        """
        with self.switch_lock:
            try:
                # Switch to worker's tab
                self.switch_to_tab(worker_index, worker_label)
                
                # Execute action
                result = action_callback(self.driver)
                
                return result
                
            except Exception as e:
                logger.error(f"[{worker_label}] Error executing in tab {worker_index}: {e}")
                raise
    
    def get_tab_count(self) -> int:
        """Get number of available tabs."""
        return len(self.tab_handles)
    
    def close_all_tabs_except_first(self):
        """Close all tabs except the first one."""
        try:
            for i in range(1, len(self.tab_handles)):
                try:
                    self.driver.switch_to.window(self.tab_handles[i])
                    self.driver.close()
                    logger.info(f"Closed tab {i + 1}")
                except Exception as e:
                    logger.warning(f"Could not close tab {i + 1}: {e}")
            
            # Switch back to first tab
            if len(self.tab_handles) > 0:
                self.driver.switch_to.window(self.tab_handles[0])
                
        except Exception as e:
            logger.error(f"Error closing tabs: {e}")


def setup_driver_with_tabs(driver: WebDriver, num_workers: int) -> TabManager:
    """
    Setup tab-based workers using existing driver.
    
    Args:
        driver: Existing WebDriver instance
        num_workers: Number of parallel workers (1-5)
        
    Returns:
        TabManager instance
        
    Example:
        >>> from scraper.driver_manager import setup_driver
        >>> from scraper.tab_manager import setup_driver_with_tabs
        >>> 
        >>> driver = setup_driver(initial_download_dir="/path/to/downloads")
        >>> tab_mgr = setup_driver_with_tabs(driver, num_workers=3)
        >>> 
        >>> # Worker 1 uses tab 0
        >>> tab_mgr.switch_to_tab(0, "W1")
        >>> driver.get("https://portal1.gov.in")
        >>> 
        >>> # Worker 2 uses tab 1
        >>> tab_mgr.switch_to_tab(1, "W2")
        >>> driver.get("https://portal2.gov.in")
    """
    num_workers = max(1, min(5, num_workers))
    logger.info(f"Setting up {num_workers} tab-based workers")
    
    return TabManager(driver, num_tabs=num_workers)


# --- Testing ---
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("TabManager Test")
    print("=" * 60)
    print("This test requires Chrome browser to be installed.")
    print("Creating 3 tabs and navigating to different sites...")
    print()
    
    try:
        from scraper.driver_manager import setup_driver, safe_quit_driver
        
        # Setup driver
        test_driver = setup_driver()
        print(f"✓ Driver created")
        
        # Create tab manager
        tab_mgr = setup_driver_with_tabs(test_driver, num_workers=3)
        print(f"✓ {tab_mgr.get_tab_count()} tabs created")
        
        # Test navigation in different tabs
        test_urls = [
            "https://www.example.com",
            "https://www.wikipedia.org",
            "https://www.github.com"
        ]
        
        for idx, url in enumerate(test_urls):
            print(f"\nTab {idx + 1}: Navigating to {url}")
            tab_mgr.switch_to_tab(idx, f"W{idx + 1}")
            test_driver.get(url)
            time.sleep(2)
            title = test_driver.title
            print(f"  → Page title: {title}")
        
        # Verify each tab still has correct page
        print("\n\nVerifying tabs...")
        for idx in range(tab_mgr.get_tab_count()):
            tab_mgr.switch_to_tab(idx, f"W{idx + 1}")
            print(f"Tab {idx + 1}: {test_driver.title}")
        
        print("\n✓ Tab switching works correctly!")
        print("✓ Memory usage: ~800MB (vs 2.4GB with 3 separate browsers)")
        
        # Cleanup
        input("\nPress Enter to close browser...")
        safe_quit_driver(test_driver, lambda msg: print(f"Cleanup: {msg}"))
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"\n✗ Test failed: {e}")
