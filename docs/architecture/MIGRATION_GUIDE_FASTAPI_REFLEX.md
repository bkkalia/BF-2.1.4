# BlackForest Migration Guide: FastAPI + Reflex Architecture

**Target Timeline:** 6-9 months  
**Automation Goal:** 95%+ automated scraping  
**Vision:** Skill-based general scraping platform for government tender portals

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Target Architecture](#target-architecture)
4. [Skill-Based Portal Abstraction](#skill-based-portal-abstraction)
5. [Anti-Detection & Rate Limiting Strategy](#anti-detection--rate-limiting-strategy)
6. [Phase-by-Phase Migration](#phase-by-phase-migration)
7. [Code Migration Map](#code-migration-map)
8. [Automation Maximization](#automation-maximization)
9. [Deployment Architecture](#deployment-architecture)
10. [Risk Mitigation](#risk-mitigation)

---

## Executive Summary

### Current Architecture
```
[Tkinter Desktop GUI] → [SQLite] → [Selenium Scrapers]
- Single-machine desktop application
- Manual operation required
- 20-25 portals max capacity
- Sequential portal processing
```

### Target Architecture
```
[Reflex Web UI] ← [FastAPI Backend] → [PostgreSQL]
                        ↓
            [Celery Task Queue] → [Redis]
                        ↓
        [Skill Workers Pool] (10-50 parallel)
                        ↓
            [Portal Skills Library]
```

### Migration Benefits
- **Scale:** 20 portals → 100+ portals with daily freshness
- **Automation:** Manual runs → 95%+ auto-scheduled intelligent scraping
- **Resilience:** Single failure point → distributed fault-tolerant system
- **Maintainability:** Portal-specific code → pluggable skill modules
- **Accessibility:** Desktop only → web-accessible from anywhere

---

## Current State Analysis

### Reusable Components (70% of codebase)
✅ **Core scraping logic** (`scraper/logic.py`)
- Department list extraction
- Tender detail extraction
- Navigation patterns
- Error recovery mechanisms

✅ **Data models** (`tender_store.py`)
- Run/tender schema design
- Integrity rules
- Backup strategies

✅ **Portal configurations** (`base_urls.csv`, portal memory)
- URL patterns
- Locator strategies
- Portal-specific quirks

✅ **Business logic**
- Quick/Full delta algorithms
- Resume/only-new logic
- Manifest tracking

### Components Requiring Transformation (30%)
🔄 **GUI Layer** (`gui/*`)
- Tkinter → Reflex components
- Desktop events → WebSocket real-time updates

🔄 **Orchestration** (`main.py`, batch control)
- Synchronous → Async task scheduling
- Single-threaded → Distributed workers

🔄 **Driver Management** (`scraper/driver_manager.py`)
- Local Chrome instances → Remote Selenium Grid
- Per-session → Pooled connections

---

## Target Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     REFLEX WEB UI                           │
│  - Dashboard (portal status, real-time logs)                │
│  - Skill Manager (add/edit/test portal skills)              │
│  - Scheduler (configure auto-runs)                          │
│  - Reports & Analytics                                      │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/WebSocket
┌────────────────────▼────────────────────────────────────────┐
│                  FASTAPI BACKEND                            │
│  /api/portals     - Portal CRUD                             │
│  /api/skills      - Skill management                        │
│  /api/runs        - Trigger/monitor scraping                │
│  /api/tenders     - Query/export tenders                    │
│  /api/schedule    - Auto-schedule config                    │
│  /ws/logs         - Real-time log streaming                 │
└────────────┬──────────────┬─────────────┬──────────────────┘
             │              │             │
    ┌────────▼──────┐  ┌───▼───────┐  ┌─▼──────────┐
    │  PostgreSQL   │  │   Redis   │  │  Selenium  │
    │  (Tenders DB) │  │  (Queue)  │  │    Grid    │
    └───────────────┘  └─────┬─────┘  └────────────┘
                             │
                    ┌────────▼─────────┐
                    │  CELERY WORKERS  │
                    │  - Skill Loaders │
                    │  - Scrapers      │
                    │  - Processors    │
                    └──────────────────┘
```

### Technology Stack

| Layer | Current | Target | Reason |
|-------|---------|--------|--------|
| **Frontend** | Tkinter | Reflex | Modern web UI, Python-native |
| **Backend** | Direct calls | FastAPI | Async, REST API, auto docs |
| **Database** | SQLite | PostgreSQL | Scalability, concurrent writes |
| **Task Queue** | Threading | Celery + Redis | Distributed, fault-tolerant |
| **Caching** | In-memory | Redis | Shared state, pub/sub |
| **Scraping** | Local Selenium | Selenium Grid | Horizontal scaling |
| **Scheduling** | Manual | Celery Beat | Automated cron-like jobs |
| **Monitoring** | Logs | Prometheus + Grafana | Metrics, alerting |

---

## Skill-Based Portal Abstraction

### Skill Architecture

**Core Concept:** Each portal is a pluggable "skill" module with standardized interface.

```python
# skills/base_skill.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from selenium.webdriver.remote.webdriver import WebDriver

@dataclass
class PortalConfig:
    """Standardized portal configuration"""
    name: str
    base_url: str
    org_list_url: str
    portal_type: str  # "NIC", "STATE", "CUSTOM"
    requires_captcha: bool = False
    rate_limit_requests_per_minute: int = 30
    cooldown_seconds: int = 2
    priority: str = "medium"  # "high", "medium", "low"
    enabled: bool = True

@dataclass
class DepartmentInfo:
    """Standardized department data"""
    s_no: str
    name: str
    count_text: str
    has_link: bool
    direct_url: Optional[str] = None

@dataclass
class TenderInfo:
    """Standardized tender data"""
    tender_id: str
    title: str
    department: str
    published_date: Optional[str] = None
    closing_date: Optional[str] = None
    opening_date: Optional[str] = None
    emd_amount: Optional[str] = None
    organization_chain: Optional[str] = None
    status: str = "active"
    raw_data: Dict[str, Any] = None

class BasePortalSkill(ABC):
    """
    Base class for all portal scraping skills.
    Each portal implements this interface.
    """
    
    def __init__(self, config: PortalConfig):
        self.config = config
        self.session_state = {}
    
    @abstractmethod
    def get_department_list(self, driver: WebDriver) -> List[DepartmentInfo]:
        """
        Extract department list from portal.
        Override with portal-specific logic.
        """
        pass
    
    @abstractmethod
    def navigate_to_department(self, driver: WebDriver, dept: DepartmentInfo) -> bool:
        """
        Navigate to department tender list.
        Returns True if successful.
        """
        pass
    
    @abstractmethod
    def extract_tender_ids_from_page(self, driver: WebDriver) -> List[str]:
        """
        Extract all tender IDs from current department page.
        Handles pagination internally.
        """
        pass
    
    @abstractmethod
    def extract_tender_details(self, driver: WebDriver, tender_id: str) -> Optional[TenderInfo]:
        """
        Extract full tender details for a single tender.
        """
        pass
    
    # Optional hooks for customization
    def pre_scrape_hook(self, driver: WebDriver) -> None:
        """Called before scraping starts (e.g., login, CAPTCHA)"""
        pass
    
    def post_scrape_hook(self, driver: WebDriver) -> None:
        """Called after scraping completes (e.g., logout, cleanup)"""
        pass
    
    def handle_captcha(self, driver: WebDriver) -> bool:
        """Custom CAPTCHA handling logic"""
        return True
    
    def handle_rate_limit(self, attempt: int) -> int:
        """Custom rate limit backoff strategy"""
        return min(60, 2 ** attempt)  # Exponential backoff
    
    def detect_changes_fast(self) -> Optional[bool]:
        """
        Quick change detection without full scrape.
        Returns True if changes detected, False if no changes, None if unknown.
        """
        return None  # Default: always scrape
```

### Example: NIC Portal Skill

```python
# skills/nic_portal_skill.py
from skills.base_skill import BasePortalSkill, DepartmentInfo, TenderInfo, PortalConfig
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
from bs4 import BeautifulSoup

class NICPortalSkill(BasePortalSkill):
    """
    Standard NIC portal skill (covers ~70% of Indian government portals)
    """
    
    # NIC-specific locators
    TENDERS_BY_ORG_XPATH = "//a[contains(@href, 'FrontEndTendersByOrganisation')]"
    DEPT_TABLE_ID = "table"
    TENDER_ID_XPATH = "//b[contains(text(), 'Tender ID')]/following-sibling::span"
    
    def get_department_list(self, driver) -> List[DepartmentInfo]:
        """
        NIC portals use standard table format.
        Optimize: Try HTTP first, fallback to Selenium.
        """
        # Strategy 1: Try fast HTTP scraping
        departments = self._get_departments_via_http()
        if departments:
            return departments
        
        # Strategy 2: Fallback to Selenium (for JS-heavy pages)
        return self._get_departments_via_selenium(driver)
    
    def _get_departments_via_http(self) -> List[DepartmentInfo]:
        """Fast HTTP-based department list extraction (10-50x faster)"""
        try:
            response = requests.get(
                self.config.org_list_url,
                timeout=10,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', id='table')
            if not table:
                return []
            
            departments = []
            rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 3:
                    continue
                
                s_no = cells[0].get_text(strip=True)
                name = cells[1].get_text(strip=True)
                count_cell = cells[2]
                count_text = count_cell.get_text(strip=True)
                
                # Skip header rows
                if s_no.lower() in ['s.no', 'sr.no']:
                    continue
                
                # Extract direct URL if available
                link = count_cell.find('a')
                direct_url = link['href'] if link and link.get('href') else None
                
                departments.append(DepartmentInfo(
                    s_no=s_no,
                    name=name,
                    count_text=count_text,
                    has_link=bool(direct_url),
                    direct_url=direct_url
                ))
            
            return departments
        except Exception:
            return []  # Fallback to Selenium
    
    def _get_departments_via_selenium(self, driver) -> List[DepartmentInfo]:
        """Traditional Selenium-based extraction"""
        driver.get(self.config.org_list_url)
        
        # Click "Tenders by Organisation" if needed
        try:
            org_link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, self.TENDERS_BY_ORG_XPATH))
            )
            org_link.click()
        except:
            pass  # Already on correct page
        
        # Wait for table
        table = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, self.DEPT_TABLE_ID))
        )
        
        departments = []
        rows = table.find_elements(By.TAG_NAME, "tr")
        
        for row in rows[1:]:  # Skip header
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 3:
                continue
            
            s_no = cells[0].text.strip()
            name = cells[1].text.strip()
            count_text = cells[2].text.strip()
            
            try:
                link = cells[2].find_element(By.TAG_NAME, "a")
                direct_url = link.get_attribute('href')
            except:
                direct_url = None
            
            departments.append(DepartmentInfo(
                s_no=s_no,
                name=name,
                count_text=count_text,
                has_link=bool(direct_url),
                direct_url=direct_url
            ))
        
        return departments
    
    def navigate_to_department(self, driver, dept: DepartmentInfo) -> bool:
        """Navigate to department tender list"""
        if dept.direct_url:
            driver.get(dept.direct_url)
            return True
        # Fallback: click department link logic
        # ... implementation
        return False
    
    def extract_tender_ids_from_page(self, driver) -> List[str]:
        """Extract tender IDs with pagination handling"""
        tender_ids = []
        page = 1
        
        while True:
            # Extract IDs from current page
            id_elements = driver.find_elements(By.XPATH, "//td/a[contains(@href, 'Tender_ID')]")
            page_ids = [elem.text.strip() for elem in id_elements if elem.text.strip()]
            tender_ids.extend(page_ids)
            
            # Check for next page
            try:
                next_btn = driver.find_element(By.XPATH, "//a[contains(text(), 'Next')]")
                next_btn.click()
                WebDriverWait(driver, 10).until(EC.staleness_of(id_elements[0]))
                page += 1
            except:
                break  # No more pages
        
        return tender_ids
    
    def extract_tender_details(self, driver, tender_id: str) -> Optional[TenderInfo]:
        """Extract tender details from detail page"""
        # Navigate to tender detail page
        # ... extract using locators
        
        return TenderInfo(
            tender_id=tender_id,
            title="Extracted Title",
            department="Extracted Dept",
            # ... other fields
        )
    
    def detect_changes_fast(self) -> Optional[bool]:
        """
        Quick change detection using HTTP HEAD request.
        Check Last-Modified header or homepage hash.
        """
        try:
            resp = requests.head(self.config.base_url, timeout=5)
            last_modified = resp.headers.get('Last-Modified')
            
            if last_modified:
                # Compare with stored value
                stored_modified = self.session_state.get('last_modified')
                if stored_modified and stored_modified == last_modified:
                    return False  # No changes
                self.session_state['last_modified'] = last_modified
                return True  # Changed
            
            return None  # Unknown, proceed with scrape
        except:
            return None
```

### Skill Registry & Dynamic Loading

```python
# skills/registry.py
from typing import Dict, Type
from skills.base_skill import BasePortalSkill, PortalConfig
from skills.nic_portal_skill import NICPortalSkill
# Import other skills...

class SkillRegistry:
    """
    Central registry for all portal skills.
    Allows dynamic skill loading and hot-swapping.
    """
    
    _skills: Dict[str, Type[BasePortalSkill]] = {
        "NIC_STANDARD": NICPortalSkill,
        # "RAILWAY_PORTAL": RailwayPortalSkill,
        # "GEM_PORTAL": GEMPortalSkill,
        # Add more skills here
    }
    
    @classmethod
    def register_skill(cls, skill_name: str, skill_class: Type[BasePortalSkill]):
        """Register a new skill dynamically"""
        cls._skills[skill_name] = skill_class
    
    @classmethod
    def get_skill(cls, skill_name: str, config: PortalConfig) -> BasePortalSkill:
        """Get skill instance for portal"""
        skill_class = cls._skills.get(skill_name)
        if not skill_class:
            raise ValueError(f"Unknown skill: {skill_name}")
        return skill_class(config)
    
    @classmethod
    def list_skills(cls) -> List[str]:
        """List all available skills"""
        return list(cls._skills.keys())
    
    @classmethod
    def load_skill_from_file(cls, skill_file_path: str) -> str:
        """
        Hot-load a new skill from Python file.
        Useful for adding portals without redeploying.
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location("dynamic_skill", skill_file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Auto-discover skill class
        for name, obj in module.__dict__.items():
            if isinstance(obj, type) and issubclass(obj, BasePortalSkill) and obj != BasePortalSkill:
                skill_name = f"CUSTOM_{name.upper()}"
                cls.register_skill(skill_name, obj)
                return skill_name
        
        raise ValueError("No valid skill class found in file")
```

### Database Schema for Skills

```sql
-- Portal Skills Table
CREATE TABLE portal_skills (
    id SERIAL PRIMARY KEY,
    skill_name VARCHAR(100) UNIQUE NOT NULL,
    skill_class VARCHAR(200) NOT NULL,  -- Python class path
    skill_file_path TEXT,  -- For dynamically loaded skills
    version VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Portals Table (links portals to skills)
CREATE TABLE portals (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) UNIQUE NOT NULL,
    base_url TEXT NOT NULL,
    org_list_url TEXT NOT NULL,
    skill_id INTEGER REFERENCES portal_skills(id),
    portal_type VARCHAR(50),  -- "NIC", "STATE", "CUSTOM"
    priority VARCHAR(20) DEFAULT 'medium',  -- "high", "medium", "low"
    rate_limit_rpm INTEGER DEFAULT 30,
    cooldown_seconds INTEGER DEFAULT 2,
    requires_captcha BOOLEAN DEFAULT FALSE,
    enabled BOOLEAN DEFAULT TRUE,
    last_scraped_at TIMESTAMP,
    last_modified_check TIMESTAMP,
    last_change_detected TIMESTAMP,
    metadata JSONB,  -- Flexible metadata storage
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Portal Metrics (for monitoring)
CREATE TABLE portal_metrics (
    id SERIAL PRIMARY KEY,
    portal_id INTEGER REFERENCES portals(id),
    metric_date DATE NOT NULL,
    scrape_success_count INTEGER DEFAULT 0,
    scrape_failure_count INTEGER DEFAULT 0,
    avg_scrape_duration_seconds REAL,
    tenders_discovered INTEGER DEFAULT 0,
    captcha_encountered_count INTEGER DEFAULT 0,
    rate_limit_hit_count INTEGER DEFAULT 0,
    UNIQUE(portal_id, metric_date)
);

CREATE INDEX idx_portal_metrics_date ON portal_metrics(metric_date DESC);
CREATE INDEX idx_portal_metrics_portal ON portal_metrics(portal_id);
```

---

## Anti-Detection & Rate Limiting Strategy

### Challenge: Avoid IP Bans & Portal Blacklisting

NIC portals don't provide official API access, so aggressive scraping can trigger:
- IP-based blocking (temporary or permanent)
- CAPTCHA challenges increasing in frequency
- Session invalidation
- HTTP 429 (Too Many Requests) errors

### Multi-Layer Protection Strategy

#### 1. Request Rate Limiting (Portal-Aware)

```python
# backend/rate_limiter.py
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

class PortalRateLimiter:
    """
    Intelligent rate limiter respecting per-portal limits.
    """
    
    def __init__(self):
        self.portal_requests = defaultdict(list)  # portal_id -> [timestamp, ...]
        self.portal_cooldowns = {}  # portal_id -> next_allowed_time
    
    async def acquire(self, portal_id: int, rpm_limit: int = 30, cooldown_seconds: int = 2):
        """
        Acquire permission to make request for portal.
        Blocks until rate limit allows.
        """
        now = datetime.now()
        
        # Check cooldown
        if portal_id in self.portal_cooldowns:
            next_allowed = self.portal_cooldowns[portal_id]
            if now < next_allowed:
                wait_seconds = (next_allowed - now).total_seconds()
                await asyncio.sleep(wait_seconds)
        
        # Clean old requests (older than 1 minute)
        cutoff = now - timedelta(minutes=1)
        self.portal_requests[portal_id] = [
            ts for ts in self.portal_requests[portal_id]
            if ts > cutoff
        ]
        
        # Check RPM limit
        if len(self.portal_requests[portal_id]) >= rpm_limit:
            # Wait until oldest request expires
            oldest = min(self.portal_requests[portal_id])
            wait_until = oldest + timedelta(minutes=1)
            wait_seconds = (wait_until - now).total_seconds()
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
        
        # Record request
        self.portal_requests[portal_id].append(datetime.now())
        
        # Set cooldown for next request
        self.portal_cooldowns[portal_id] = datetime.now() + timedelta(seconds=cooldown_seconds)
    
    def release(self, portal_id: int):
        """Release any locks (for error cases)"""
        if portal_id in self.portal_cooldowns:
            del self.portal_cooldowns[portal_id]
```

#### 2. User-Agent Rotation & Request Headers

```python
# backend/scraper_utils.py
import random

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
]

def get_randomized_headers():
    """Generate realistic browser headers"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }

def configure_undetected_driver(driver_options):
    """Configure Selenium to avoid bot detection"""
    # Disable automation flags
    driver_options.add_argument('--disable-blink-features=AutomationControlled')
    driver_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    driver_options.add_experimental_option('useAutomationExtension', False)
    
    # Randomize window size
    widths = [1366, 1920, 1440, 1536]
    heights = [768, 1080, 900, 864]
    driver_options.add_argument(f'--window-size={random.choice(widths)},{random.choice(heights)}')
    
    return driver_options
```

#### 3. Adaptive Backoff Strategy

```python
# backend/backoff_strategy.py
import asyncio
from typing import Optional

class AdaptiveBackoff:
    """
    Exponential backoff with jitter and circuit breaker.
    """
    
    def __init__(self, portal_id: int):
        self.portal_id = portal_id
        self.failure_count = 0
        self.circuit_open = False
        self.circuit_open_until: Optional[datetime] = None
    
    async def handle_failure(self, is_rate_limit: bool = False):
        """Handle scraping failure"""
        self.failure_count += 1
        
        if is_rate_limit:
            # Aggressive backoff for rate limits
            wait_seconds = min(300, 30 * (2 ** self.failure_count))
        else:
            # Standard exponential backoff
            wait_seconds = min(120, 2 ** self.failure_count)
        
        # Add jitter to avoid thundering herd
        jitter = random.uniform(0, wait_seconds * 0.1)
        total_wait = wait_seconds + jitter
        
        # Open circuit breaker if too many failures
        if self.failure_count >= 5:
            self.circuit_open = True
            self.circuit_open_until = datetime.now() + timedelta(minutes=30)
            # Alert monitoring system
            await self._alert_circuit_open()
        
        await asyncio.sleep(total_wait)
    
    def handle_success(self):
        """Reset on successful scrape"""
        self.failure_count = max(0, self.failure_count - 1)
        if self.failure_count == 0:
            self.circuit_open = False
            self.circuit_open_until = None
    
    def is_circuit_open(self) -> bool:
        """Check if circuit breaker is open"""
        if not self.circuit_open:
            return False
        
        if self.circuit_open_until and datetime.now() > self.circuit_open_until:
            # Auto-reset circuit after timeout
            self.circuit_open = False
            self.circuit_open_until = None
            self.failure_count = 0
            return False
        
        return True
    
    async def _alert_circuit_open(self):
        """Send alert when circuit opens"""
        # Log to monitoring system
        # Send notification to admins
        pass
```

#### 4. Distributed IP Rotation (Optional - Advanced)

```python
# backend/proxy_manager.py
from typing import List, Optional
import random

class ProxyRotator:
    """
    Rotate requests through proxy pool.
    Use only if necessary (adds cost and complexity).
    """
    
    def __init__(self, proxy_list: List[str]):
        self.proxies = proxy_list
        self.proxy_health = {proxy: 1.0 for proxy in proxy_list}  # 0.0 to 1.0
    
    def get_proxy(self) -> Optional[str]:
        """Get healthy proxy using weighted random selection"""
        if not self.proxies:
            return None
        
        # Weight by health score
        weights = [self.proxy_health.get(p, 0.5) for p in self.proxies]
        if sum(weights) == 0:
            return None
        
        return random.choices(self.proxies, weights=weights)[0]
    
    def report_success(self, proxy: str):
        """Improve proxy health score"""
        current = self.proxy_health.get(proxy, 0.5)
        self.proxy_health[proxy] = min(1.0, current + 0.1)
    
    def report_failure(self, proxy: str):
        """Degrade proxy health score"""
        current = self.proxy_health.get(proxy, 0.5)
        self.proxy_health[proxy] = max(0.0, current - 0.2)
        
        # Remove if health too low
        if self.proxy_health[proxy] < 0.1:
            self.proxies.remove(proxy)
```

#### 5. Time-based Scraping Strategy

```python
# backend/scheduler.py
from datetime import time

class SmartScheduler:
    """
    Schedule scraping during low-traffic periods.
    Government portals typically have low usage at night.
    """
    
    # Indian Standard Time (IST) off-peak hours
    OFF_PEAK_HOURS = [
        (time(22, 0), time(6, 0)),   # 10 PM - 6 AM
        (time(13, 0), time(14, 30)),  # 1 PM - 2:30 PM (lunch)
    ]
    
    def is_off_peak(self, check_time: datetime = None) -> bool:
        """Check if current time is off-peak"""
        check_time = check_time or datetime.now()
        current_time = check_time.time()
        
        for start, end in self.OFF_PEAK_HOURS:
            if start < end:
                if start <= current_time <= end:
                    return True
            else:  # Crosses midnight
                if current_time >= start or current_time <= end:
                    return True
        return False
    
    def get_next_off_peak_window(self) -> datetime:
        """Get next off-peak scraping window"""
        now = datetime.now()
        
        for start, end in self.OFF_PEAK_HOURS:
            window_start = now.replace(hour=start.hour, minute=start.minute, second=0)
            if window_start < now:
                window_start += timedelta(days=1)
            
            if not self.is_off_peak(now):
                return window_start
        
        return now  # Fallback to immediate
```

---

## Phase-by-Phase Migration

### Phase 0: Preparation (Weeks 1-2)

**Goal:** Set up new infrastructure without disrupting current system.

#### Tasks
1. **Set up development environment**
   ```bash
   # New project structure
   mkdir blackforest-v3
   cd blackforest-v3
   
   # Backend
   mkdir backend
   cd backend
   python -m venv venv
   pip install fastapi uvicorn sqlalchemy psycopg2 celery redis reflex
   
   # Frontend (Reflex)
   mkdir ../frontend
   ```

2. **Database setup**
   ```sql
   -- Install PostgreSQL locally or use Docker
   docker run -d \
     --name bf-postgres \
     -e POSTGRES_PASSWORD=blackforest \
     -e POSTGRES_USER=bf_user \
     -e POSTGRES_DB=blackforest \
     -p 5432:5432 \
     postgres:15
   
   -- Redis for Celery
   docker run -d \
     --name bf-redis \
     -p 6379:6379 \
     redis:7
   ```

3. **Port existing data models**
   ```python
   # backend/models.py
   from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON
   from sqlalchemy.ext.declarative import declarative_base
   
   Base = declarative_base()
   
   class Portal(Base):
       __tablename__ = "portals"
       id = Column(Integer, primary_key=True)
       name = Column(String(200), unique=True, nullable=False)
       base_url = Column(Text, nullable=False)
       # ... (see schema above)
   
   class ScrapingRun(Base):
       __tablename__ = "scraping_runs"
       id = Column(Integer, primary_key=True)
       portal_id = Column(Integer, ForeignKey("portals.id"))
       # ... port from current runs table
   
   class Tender(Base):
       __tablename__ = "tenders"
       id = Column(Integer, primary_key=True)
       run_id = Column(Integer, ForeignKey("scraping_runs.id"))
       # ... port from current tenders table
   ```

**Deliverables:**
- ✅ PostgreSQL + Redis running
- ✅ SQLAlchemy models matching current schema
- ✅ Migration script: SQLite → PostgreSQL

---

### Phase 1: Backend API Layer (Weeks 3-6)

**Goal:** Build FastAPI backend with core CRUD operations.

#### 1.1 Basic FastAPI Setup

```python
# backend/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models, schemas, crud
from database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="BlackForest Scraper API", version="3.0.0")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "BlackForest API v3.0", "status": "ready"}

# Portal endpoints
@app.get("/api/portals", response_model=List[schemas.Portal])
def list_portals(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_portals(db, skip=skip, limit=limit)

@app.post("/api/portals", response_model=schemas.Portal)
def create_portal(portal: schemas.PortalCreate, db: Session = Depends(get_db)):
    return crud.create_portal(db, portal)

@app.get("/api/portals/{portal_id}", response_model=schemas.Portal)
def get_portal(portal_id: int, db: Session = Depends(get_db)):
    portal = crud.get_portal(db, portal_id)
    if not portal:
        raise HTTPException(status_code=404, detail="Portal not found")
    return portal

# Tender endpoints
@app.get("/api/tenders", response_model=List[schemas.Tender])
def list_tenders(
    portal_id: int = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return crud.get_tenders(db, portal_id=portal_id, skip=skip, limit=limit)

@app.post("/api/runs/{run_id}/tenders/bulk", response_model=schemas.BulkImportResult)
def bulk_import_tenders(run_id: int, tenders: List[schemas.TenderCreate], db: Session = Depends(get_db)):
    return crud.bulk_create_tenders(db, run_id, tenders)
```

#### 1.2 Real-time Logging via WebSocket

```python
# backend/websockets.py
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
    
    def disconnect(self, websocket: WebSocket, channel: str):
        self.active_connections[channel].remove(websocket)
    
    async def broadcast(self, channel: str, message: dict):
        if channel in self.active_connections:
            for connection in self.active_connections[channel]:
                await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/logs/{run_id}")
async def websocket_logs(websocket: WebSocket, run_id: int):
    await manager.connect(websocket, f"run_{run_id}")
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"run_{run_id}")
```

**Deliverables:**
- ✅ FastAPI backend with portal/tender CRUD
- ✅ WebSocket log streaming
- ✅ API documentation (auto-generated by FastAPI)

---

### Phase 2: Skill System Implementation (Weeks 7-10)

**Goal:** Implement pluggable skill architecture.

#### 2.1 Migrate Scraping Logic to Skills

```python
# backend/skills/nic_portal_skill.py
# (See detailed implementation in "Skill-Based Portal Abstraction" section above)
```

#### 2.2 Skill API Endpoints

```python
# backend/api/skills.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from skills.registry import SkillRegistry
import crud

router = APIRouter(prefix="/api/skills", tags=["skills"])

@router.get("/")
def list_skills():
    """List all available portal skills"""
    return {"skills": SkillRegistry.list_skills()}

@router.post("/upload")
async def upload_skill(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a new portal skill Python file.
    System will auto-discover and register the skill.
    """
    content = await file.read()
    
    # Save to skills directory
    skill_path = f"skills/custom/{file.filename}"
    with open(skill_path, "wb") as f:
        f.write(content)
    
    # Hot-load skill
    try:
        skill_name = SkillRegistry.load_skill_from_file(skill_path)
        
        # Save to database
        skill_record = crud.create_portal_skill(db, {
            "skill_name": skill_name,
            "skill_class": f"custom.{file.filename[:-3]}",
            "skill_file_path": skill_path,
            "version": "1.0.0"
        })
        
        return {
            "success": True,
            "skill_name": skill_name,
            "message": f"Skill '{skill_name}' registered successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/test/{skill_name}")
async def test_skill(skill_name: str, portal_config: dict):
    """Test a skill against a portal without full scrape"""
    try:
        skill = SkillRegistry.get_skill(skill_name, PortalConfig(**portal_config))
        
        # Quick smoke test
        from selenium import webdriver
        driver = webdriver.Chrome()
        try:
            departments = skill.get_department_list(driver)
            return {
                "success": True,
                "departments_found": len(departments),
                "sample": departments[:3] if departments else []
            }
        finally:
            driver.quit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Deliverables:**
- ✅ BasePortalSkill abstract class
- ✅ NICPortalSkill implementation
- ✅ Skill registry system
- ✅ Hot-loading capability
- ✅ Skill upload API endpoint

---

### Phase 3: Celery Task Queue (Weeks 11-14)

**Goal:** Distributed asynchronous scraping.

#### 3.1 Celery Configuration

```python
# backend/celery_app.py
from celery import Celery
from celery.schedules import crontab

celery = Celery(
    "blackforest",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1"
)

celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Kolkata',
    enable_utc=True,
    task_routes={
        'tasks.scrape_portal': {'queue': 'scraping'},
        'tasks.process_tender': {'queue': 'processing'},
    }
)

# Periodic tasks
celery.conf.beat_schedule = {
    'scrape-high-priority-portals': {
        'task': 'tasks.scrape_high_priority',
        'schedule': crontab(hour='*/4'),  # Every 4 hours
    },
    'scrape-medium-priority-portals': {
        'task': 'tasks.scrape_medium_priority',
        'schedule': crontab(hour='*/12'),  # Twice daily
    },
    'scrape-low-priority-portals': {
        'task': 'tasks.scrape_low_priority',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'cleanup-old-runs': {
        'task': 'tasks.cleanup_old_data',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Weekly Sunday 3 AM
    },
}
```

#### 3.2 Scraping Tasks

```python
# backend/tasks.py
from celery_app import celery
from sqlalchemy.orm import Session
from database import SessionLocal
from skills.registry import SkillRegistry
from skills.base_skill import PortalConfig
import crud

@celery.task(bind=True, max_retries=3)
def scrape_portal(self, portal_id: int):
    """
    Main task: Scrape a single portal using its skill.
    """
    db = SessionLocal()
    try:
        # Get portal config
        portal = crud.get_portal(db, portal_id)
        if not portal or not portal.enabled:
            return {"status": "skipped", "reason": "disabled"}
        
        # Check if changes detected (fast check)
        skill = SkillRegistry.get_skill(
            portal.skill.skill_name,
            PortalConfig(**portal.__dict__)
        )
        
        changes = skill.detect_changes_fast()
        if changes is False:
            return {"status": "skipped", "reason": "no_changes"}
        
        # Create scraping run
        run = crud.create_scraping_run(db, {
            "portal_id": portal_id,
            "status": "running",
            "started_at": datetime.now()
        })
        
        # Execute scraping
        from selenium import webdriver
        driver = webdriver.Remote(
            command_executor='http://selenium-grid:4444/wd/hub',
            options=webdriver.ChromeOptions()
        )
        
        try:
            # Pre-scrape hook
            skill.pre_scrape_hook(driver)
            
            # Get departments
            departments = skill.get_department_list(driver)
            
            total_tenders = 0
            for dept in departments:
                # Navigate to department
                if not skill.navigate_to_department(driver, dept):
                    continue
                
                # Extract tender IDs
                tender_ids = skill.extract_tender_ids_from_page(driver)
                
                # Extract each tender
                for tender_id in tender_ids:
                    tender_details = skill.extract_tender_details(driver, tender_id)
                    if tender_details:
                        crud.create_tender(db, run.id, tender_details)
                        total_tenders += 1
                        
                        # Broadcast progress via WebSocket
                        from websockets import manager
                        await manager.broadcast(f"run_{run.id}", {
                            "type": "progress",
                            "department": dept.name,
                            "tender_id": tender_id,
                            "total": total_tenders
                        })
            
            # Post-scrape hook
            skill.post_scrape_hook(driver)
            
            # Update run
            crud.update_scraping_run(db, run.id, {
                "status": "completed",
                "completed_at": datetime.now(),
                "extracted_total_tenders": total_tenders
            })
            
            return {
                "status": "success",
                "run_id": run.id,
                "tenders_scraped": total_tenders
            }
        
        finally:
            driver.quit()
    
    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    
    finally:
        db.close()

@celery.task
def scrape_high_priority():
    """Scrape all high-priority portals"""
    db = SessionLocal()
    portals = crud.get_portals_by_priority(db, "high")
    for portal in portals:
        scrape_portal.delay(portal.id)
    db.close()

@celery.task
def scrape_medium_priority():
    """Scrape all medium-priority portals"""
    db = SessionLocal()
    portals = crud.get_portals_by_priority(db, "medium")
    for portal in portals:
        scrape_portal.delay(portal.id)
    db.close()

@celery.task
def scrape_low_priority():
    """Scrape all low-priority portals"""
    db = SessionLocal()
    portals = crud.get_portals_by_priority(db, "low")
    for portal in portals:
        scrape_portal.delay(portal.id)
    db.close()
```

**Deliverables:**
- ✅ Celery + Redis setup
- ✅ Distributed scraping tasks
- ✅ Automatic scheduling (Celery Beat)
- ✅ Retry logic with backoff

---

### Phase 4: Reflex Frontend (Weeks 15-18)

**Goal:** Modern web UI replacing Tkinter.

#### 4.1 Reflex App Structure

```python
# frontend/app.py
import reflex as rx
from typing import List
import httpx

API_BASE = "http://localhost:8000"

class Portal(rx.Base):
    id: int
    name: str
    base_url: str
    enabled: bool
    priority: str
    last_scraped_at: str = None

class DashboardState(rx.State):
    """State management for dashboard"""
    portals: List[Portal] = []
    loading: bool = False
    
    async def load_portals(self):
        self.loading = True
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE}/api/portals")
            self.portals = [Portal(**p) for p in response.json()]
        self.loading = False
    
    async def trigger_scrape(self, portal_id: int):
        async with httpx.AsyncClient() as client:
            await client.post(f"{API_BASE}/api/runs/start", json={"portal_id": portal_id})

def portal_card(portal: Portal) -> rx.Component:
    """Single portal card component"""
    return rx.card(
        rx.vstack(
            rx.heading(portal.name, size="md"),
            rx.text(f"Priority: {portal.priority}"),
            rx.text(f"Last scraped: {portal.last_scraped_at or 'Never'}"),
            rx.hstack(
                rx.badge("Enabled" if portal.enabled else "Disabled",
                        color_scheme="green" if portal.enabled else "gray"),
                rx.button(
                    "Scrape Now",
                    on_click=lambda: DashboardState.trigger_scrape(portal.id),
                    size="sm"
                ),
            ),
        ),
        width="300px",
    )

def dashboard() -> rx.Component:
    """Main dashboard view"""
    return rx.container(
        rx.heading("BlackForest Portal Dashboard", size="xl"),
        rx.divider(),
        rx.cond(
            DashboardState.loading,
            rx.spinner(),
            rx.responsive_grid(
                rx.foreach(DashboardState.portals, portal_card),
                columns=[1, 2, 3, 4],
                spacing="4",
            ),
        ),
    )

def skill_manager() -> rx.Component:
    """Skill upload and management"""
    return rx.container(
        rx.heading("Portal Skills", size="xl"),
        rx.upload(
            rx.text("Drop skill file here"),
            id="skill-upload",
            border="1px dotted rgb(107,99,246)",
            padding="5em",
        ),
        rx.button("Upload Skill", on_click=SkillState.upload_skill),
    )

# App setup
app = rx.App()
app.add_page(dashboard, route="/", title="Dashboard")
app.add_page(skill_manager, route="/skills", title="Skills")
app.compile()
```

**Deliverables:**
- ✅ Reflex dashboard with portal cards
- ✅ Real-time log viewer (WebSocket)
- ✅ Skill upload interface
- ✅ Tender search and export

---

### Phase 5: Data Migration & Parallel Operation (Weeks 19-22)

**Goal:** Migrate existing data and run both systems in parallel.

#### 5.1 SQLite → PostgreSQL Migration Script

```python
# migration/migrate_sqlite_to_postgres.py
import sqlite3
import psycopg2
from psycopg2.extras import execute_batch
from tqdm import tqdm

def migrate_runs():
    """Migrate runs table"""
    sqlite_conn = sqlite3.connect("tenders.db")
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect("postgresql://bf_user:blackforest@localhost/blackforest")
    
    sqlite_cur = sqlite_conn.cursor()
    pg_cur = pg_conn.cursor()
    
    # Get all runs
    sqlite_cur.execute("SELECT * FROM runs")
    runs = sqlite_cur.fetchall()
    
    # Prepare INSERT
    insert_sql = """
        INSERT INTO scraping_runs 
        (portal_name, base_url, scope_mode, started_at, completed_at, status, 
         expected_total_tenders, extracted_total_tenders, skipped_existing_total,
         output_file_path, output_file_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    
    run_id_map = {}  # old_id -> new_id
    for run in tqdm(runs, desc="Migrating runs"):
        pg_cur.execute(insert_sql, (
            run['portal_name'], run['base_url'], run['scope_mode'],
            run['started_at'], run['completed_at'], run['status'],
            run['expected_total_tenders'], run['extracted_total_tenders'],
            run['skipped_existing_total'], run['output_file_path'], run['output_file_type']
        ))
        new_id = pg_cur.fetchone()[0]
        run_id_map[run['id']] = new_id
    
    pg_conn.commit()
    return run_id_map

def migrate_tenders(run_id_map):
    """Migrate tenders table in batches"""
    sqlite_conn = sqlite3.connect("tenders.db")
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect("postgresql://bf_user:blackforest@localhost/blackforest")
    
    sqlite_cur = sqlite_conn.cursor()
    pg_cur = pg_conn.cursor()
    
    # Get total count
    total = sqlite_cur.execute("SELECT COUNT(*) FROM tenders").fetchone()[0]
    
    # Batch migration
    batch_size = 1000
    offset = 0
    
    insert_sql = """
        INSERT INTO tenders 
        (run_id, portal_name, department_name, tender_id_extracted, lifecycle_status,
         published_date, closing_date, opening_date, title_ref, organisation_chain,
         emd_amount, emd_amount_numeric, tender_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    with tqdm(total=total, desc="Migrating tenders") as pbar:
        while offset < total:
            sqlite_cur.execute(f"SELECT * FROM tenders LIMIT {batch_size} OFFSET {offset}")
            batch = sqlite_cur.fetchall()
            
            tender_data = [
                (
                    run_id_map.get(row['run_id']),
                    row['portal_name'], row['department_name'], row['tender_id_extracted'],
                    row['lifecycle_status'], row['published_date'], row['closing_date'],
                    row['opening_date'], row['title_ref'], row['organisation_chain'],
                    row['emd_amount'], row['emd_amount_numeric'], row['tender_json']
                )
                for row in batch
            ]
            
            execute_batch(pg_cur, insert_sql, tender_data)
            pg_conn.commit()
            
            offset += batch_size
            pbar.update(len(batch))

if __name__ == "__main__":
    print("Starting migration...")
    run_id_map = migrate_runs()
    migrate_tenders(run_id_map)
    print("Migration complete!")
```

#### 5.2 Parallel Operation Strategy

**Run both systems for 2-4 weeks:**
1. Keep Tkinter app operational for daily scraping
2. New FastAPI system scrapes simultaneously (different schedule)
3. Compare results for data consistency
4. Fix any discrepancies
5. Gradual cutover portal by portal

**Deliverables:**
- ✅ Migration scripts (SQLite → PostgreSQL)
- ✅ Data validation reports
- ✅ Both systems running in parallel

---

### Phase 6: Cutover & Optimization (Weeks 23-26)

**Goal:** Full transition to new system, decommission old system.

#### 6.1 Performance Optimization

```python
# backend/optimizations.py

# 1. Database query optimization
from sqlalchemy import Index

# Add composite indexes for common queries
class Tender(Base):
    # ... existing columns
    
    __table_args__ = (
        Index('idx_portal_tender_date', 'portal_id', 'published_date'),
        Index('idx_tender_status', 'lifecycle_status'),
        Index('idx_closing_date', 'closing_date'),
    )

# 2. Connection pooling
from sqlalchemy.pool import QueuePool

engine = create_engine(
    "postgresql://...",
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True
)

# 3. Redis caching for frequently accessed data
from redis import Redis
import json

redis_client = Redis(host='localhost', port=6379, db=2)

def get_portal_cached(portal_id: int):
    """Get portal with Redis cache"""
    cache_key = f"portal:{portal_id}"
    cached = redis_client.get(cache_key)
    
    if cached:
        return json.loads(cached)
    
    # Query DB
    portal = db.query(Portal).filter(Portal.id == portal_id).first()
    
    # Cache for 1 hour
    redis_client.setex(cache_key, 3600, json.dumps(portal.__dict__))
    return portal
```

#### 6.2 Monitoring & Alerting

```python
# backend/monitoring.py
from prometheus_client import Counter, Histogram, Gauge
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

# Metrics
scrape_success_counter = Counter('scraping_success_total', 'Total successful scrapes', ['portal'])
scrape_failure_counter = Counter('scraping_failure_total', 'Total failed scrapes', ['portal'])
scrape_duration = Histogram('scraping_duration_seconds', 'Scraping duration', ['portal'])
active_scrapers = Gauge('active_scrapers', 'Number of active scraping workers')

# Instrument FastAPI
app = FastAPI()
Instrumentator().instrument(app).expose(app)

# Use in tasks
@celery.task
def scrape_portal(portal_id):
    with scrape_duration.labels(portal=portal_id).time():
        try:
            # ... scraping logic
            scrape_success_counter.labels(portal=portal_id).inc()
        except Exception:
            scrape_failure_counter.labels(portal=portal_id).inc()
            raise
```

**Deliverables:**
- ✅ Old system decommissioned
- ✅ Performance benchmarks met
- ✅ Monitoring dashboard (Grafana)
- ✅ Alert rules configured

---

## Code Migration Map

### Component Mapping

| Current (Tkinter) | Target (FastAPI/Reflex) | Migration Complexity |
|-------------------|-------------------------|---------------------|
| `main.py` | `backend/main.py` (FastAPI) | Medium |
| `gui/main_window.py` | `frontend/pages/dashboard.py` | High |
| `gui/tab_batch_scrape.py` | `backend/tasks.py` + Frontend | High |
| `scraper/logic.py` | `backend/skills/*.py` | Medium |
| `tender_store.py` | `backend/crud.py` + `models.py` | Low |
| `config.py` | `backend/config.py` | Low |
| `base_urls.csv` | `portals` table (DB) | Low |
| `batch_tender_manifest.json` | PostgreSQL tables | Medium |

### Reusable Code Percentage

- **scraper/logic.py:** 80% reusable (logic portable to skills)
- **tender_store.py:** 60% reusable (schema + integrity rules)
- **config.py:** 90% reusable (constants + locators)
- **GUI layer:** 10% reusable (UI paradigm completely different)

**Total Reusability: ~65-70%**

---

## Automation Maximization

### Target: 95%+ Automation

#### Automated Components

1. **Portal Discovery (50% manual → 95% auto)**
   ```python
   # Auto-detect new NIC portals
   async def discover_new_portals():
       """
       Scan common NIC URL patterns.
       Example: https://{state}tenders.gov.in/nicgep/app
       """
       states = ["hp", "delhi", "punjab", "kerala", ...]
       
       for state in states:
           url = f"https://{state}tenders.gov.in/nicgep/app"
           if await check_portal_exists(url):
               # Auto-register with NIC_STANDARD skill
               await register_portal({
                   "name": f"{state.title()} Tenders",
                   "base_url": url,
                   "skill": "NIC_STANDARD"
               })
   ```

2. **Skill Auto-Assignment (100% manual → 90% auto)**
   ```python
   # Intelligent skill matching
   async def auto_assign_skill(portal_url: str):
       """Analyze portal and suggest best skill"""
       response = requests.get(portal_url)
       soup = BeautifulSoup(response.content)
       
       # Check for NIC markers
       if soup.find(text=re.compile("NIC|National Informatics Centre")):
           return "NIC_STANDARD"
       
       # Check for Railway portal patterns
       if "ireps" in portal_url or "indianrailways" in portal_url:
           return "RAILWAY_PORTAL"
       
       # Default to manual review
       return None
   ```

3. **Schedule Auto-Optimization (100% manual → 95% auto)**
   ```python
   # ML-based schedule optimization
   from sklearn.ensemble import RandomForestClassifier
   
   def optimize_scraping_schedule(portal_id: int):
       """
       Predict best time to scrape based on historical data.
       """
       # Get historical tender publish patterns
       tenders = get_tenders_by_portal(portal_id)
       
       # Analyze publish time distribution
       publish_hours = [parse_hour(t.published_date) for t in tenders]
       
       # Most tenders published between 10 AM - 4 PM
       peak_hours = find_peak_hours(publish_hours)
       
       # Schedule scraping 1 hour after peak publish times
       return [h + 1 for h in peak_hours]
   ```

4. **CAPTCHA Auto-Solving (0% → 80%)**
   ```python
   # Integrate CAPTCHA solving service
   from twocaptcha import TwoCaptcha
   
   async def solve_captcha_auto(driver):
       """Auto-solve CAPTCHA using external service"""
       captcha_img = driver.find_element(By.ID, "captcha").screenshot_as_png
       
       solver = TwoCaptcha(api_key=CAPTCHA_API_KEY)
       result = solver.normal(captcha_img)
       
       driver.find_element(By.ID, "captcha_input").send_keys(result['code'])
       return True
   ```

5. **Error Auto-Recovery (50% → 95%)**
   ```python
   # Self-healing scrapers
   class AutoRecoverySkill(BasePortalSkill):
       def handle_element_not_found(self, driver, locator):
           """Auto-recover from changed locators"""
           # Try alternative locators
           alternatives = self.generate_alternative_locators(locator)
           
           for alt in alternatives:
               try:
                   element = driver.find_element(*alt)
                   # Log successful alternative for future use
                   self.update_preferred_locator(locator, alt)
                   return element
               except:
                   continue
           
           # Alert admin
           self.alert_locator_failure(locator)
           raise
   ```

#### Manual Intervention Remaining (5%)

- New portal types requiring custom skill development
- Complex CAPTCHA (image selection, puzzle)
- Portal layout major redesigns
- Login credentials management

---

## Deployment Architecture

### Production Deployment

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: blackforest
      POSTGRES_USER: bf_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    command: uvicorn main:app --host 0.0.0.0 --port 8000
    environment:
      DATABASE_URL: postgresql://bf_user:${DB_PASSWORD}@postgres/blackforest
      REDIS_URL: redis://redis:6379/0
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis

  celery_worker:
    build: ./backend
    command: celery -A celery_app worker --loglevel=info --concurrency=5
    environment:
      DATABASE_URL: postgresql://bf_user:${DB_PASSWORD}@postgres/blackforest
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - postgres
      - redis
      - selenium_hub

  celery_beat:
    build: ./backend
    command: celery -A celery_app beat --loglevel=info
    environment:
      DATABASE_URL: postgresql://bf_user:${DB_PASSWORD}@postgres/blackforest
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - postgres
      - redis

  selenium_hub:
    image: selenium/hub:4.15
    ports:
      - "4444:4444"

  selenium_chrome:
    image: selenium/node-chrome:4.15
    environment:
      SE_EVENT_BUS_HOST: selenium_hub
      SE_EVENT_BUS_PUBLISH_PORT: 4442
      SE_EVENT_BUS_SUBSCRIBE_PORT: 4443
      SE_NODE_MAX_SESSIONS: 3
    depends_on:
      - selenium_hub
    deploy:
      replicas: 3  # Run 3 Chrome instances

  frontend:
    build: ./frontend
    command: reflex run --env prod
    ports:
      - "3000:3000"
    environment:
      API_BASE_URL: http://backend:8000
    depends_on:
      - backend

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"
    depends_on:
      - prometheus

volumes:
  postgres_data:
```

### Scalability Plan

**Horizontal Scaling:**
```bash
# Scale Celery workers
docker-compose up -d --scale celery_worker=10

# Scale Selenium nodes
docker-compose up -d --scale selenium_chrome=10
```

**Expected Performance:**
- 3 workers: ~30 portals/day
- 10 workers: ~100 portals/day
- 50 workers: ~500 portals/day

---

## Risk Mitigation

### Risk 1: Portal Ban During Migration

**Mitigation:**
- Implement rate limiting from day 1
- Start with low-volume test portals
- Monitor for error rate spikes (alerts)
- Keep old system as fallback

### Risk 2: Data Loss During Migration

**Mitigation:**
- Comprehensive backups before migration
- Parallel operation for validation
- Automated data consistency checks
- Rollback plan documented

### Risk 3: Skill Development Complexity

**Mitigation:**
- Start with 80% NIC portals (single skill)
- Incremental skill addition
- Skill testing framework
- Community contribution model

### Risk 4: Performance Degradation

**Mitigation:**
- Load testing before production
- Database query optimization
- Caching strategy
- Gradual traffic migration

---

## Success Metrics

### Pre-Migration Baseline
- Portals: ~20-25
- Scraping frequency: Manual, every 2-4 days
- Data freshness: 48-96 hours
- Maintenance: High (manual intervention)

### Post-Migration Target
- Portals: 100+
- Scraping frequency: Automated, priority-based (4-48 hours)
- Data freshness: <24 hours for high-priority
- Maintenance: Low (95% automated)
- Scalability: Horizontal (add workers on-demand)

---

## Next Steps

1. **Week 1:** Review this blueprint with team
2. **Week 2:** Set up development environment (Phase 0)
3. **Week 3-6:** Build FastAPI backend (Phase 1)
4. **Week 7-10:** Implement skill system (Phase 2)
5. **Week 11-14:** Celery task queue (Phase 3)
6. **Week 15-18:** Reflex frontend (Phase 4)
7. **Week 19-22:** Data migration & parallel run (Phase 5)
8. **Week 23-26:** Cutover & optimization (Phase 6)

**Total Timeline: 6 months (26 weeks)**

---

## Conclusion

This migration transforms BlackForest from a **desktop scraping tool** into a **scalable scraping platform** with:

✅ **Skill-based architecture:** Easy to add new portals  
✅ **95%+ automation:** Minimal manual intervention  
✅ **10x scalability:** 25 portals → 250+ portals  
✅ **Modern stack:** FastAPI + Reflex + PostgreSQL + Celery  
✅ **Anti-detection:** Rate limiting, backoff, smart scheduling  
✅ **Production-ready:** Monitoring, alerting, fault tolerance  

**End Result:** A general-purpose government tender scraping platform that can scale to cover all Indian tender portals with near-zero manual operation.
