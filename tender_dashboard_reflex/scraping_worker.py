"""
Scraping Worker Manager - Process-based workers to avoid GIL/freezing.
Imports existing scraper logic without modifications.
"""

import multiprocessing as mp
import queue
import time
import copy
from pathlib import Path
from typing import List, Callable, Dict, Optional, Set
import sys


class ScrapingWorkerManager:
    """Manages multiprocessing workers for concurrent scraping without freezing."""
    
    def __init__(
        self,
        selected_portals: List[str],
        worker_count: int,
        project_root: str,
        portal_resume_data: Optional[Dict[str, Dict]] = None,
    ):
        self.selected_portals = selected_portals
        self.worker_count = worker_count
        self.project_root = Path(project_root)
        self.portal_resume_data = portal_resume_data or {}
        
        # Multiprocessing queues for communication
        self.task_queue = mp.Queue()
        self.result_queue = mp.Queue()
        
        # Worker processes
        self.workers = []
        
        # Progress tracking
        self.total_tenders = 0
        self.total_departments = 0
        self.portals_completed = 0
        self.total_skipped_existing = 0
        self.total_closing_date_reprocessed = 0
    
    def start_scraping(self, progress_callback: Callable[[Dict], None]):
        """Start scraping with worker processes."""
        try:
            # Add project root to path
            if str(self.project_root) not in sys.path:
                sys.path.insert(0, str(self.project_root))
            
            # Import required modules
            import pandas as pd
            from scraper.playwright_logic import fetch_department_list_from_site_playwright
            from scraper.logic import run_scraping_logic
            from scraper.driver_manager import setup_driver, safe_quit_driver
            from tender_store import TenderDataStore
            
            # Load portal configurations
            base_urls_csv = self.project_root / "base_urls.csv"
            if not base_urls_csv.exists():
                progress_callback({
                    "type": "log",
                    "message": "ERROR: base_urls.csv not found"
                })
                return
            
            portal_configs = pd.read_csv(base_urls_csv).to_dict('records')
            portal_config_map = {p['Name']: p for p in portal_configs}
            
            # Prepare tasks (portals to scrape)
            tasks = []
            for portal_name in self.selected_portals:
                if portal_name in portal_config_map:
                    task_config = copy.deepcopy(portal_config_map[portal_name])
                    task_config["_resume_data"] = self.portal_resume_data.get(portal_name, {})
                    tasks.append(task_config)
                else:
                    progress_callback({
                        "type": "log",
                        "message": f"WARNING: Portal '{portal_name}' not found in base_urls.csv"
                    })
            
            if not tasks:
                progress_callback({
                    "type": "log",
                    "message": "ERROR: No valid portals to scrape"
                })
                return
            
            progress_callback({
                "type": "log",
                "message": f"Prepared {len(tasks)} portal(s) for scraping"
            })
            
            # Put tasks in queue
            for task in tasks:
                self.task_queue.put(task)
            
            # Add poison pills to stop workers
            for _ in range(self.worker_count):
                self.task_queue.put(None)
            
            # Start worker processes
            progress_callback({
                "type": "log",
                "message": f"Starting {self.worker_count} worker processes..."
            })
            
            try:
                for worker_id in range(self.worker_count):
                    process = mp.Process(
                        target=ScrapingWorkerManager._worker_process,
                        args=(worker_id, self.task_queue, self.result_queue, str(self.project_root))
                    )
                    process.daemon = True
                    process.start()
                    self.workers.append(process)
                    
                    progress_callback({
                        "type": "log",
                        "message": f"Worker {worker_id + 1} started (PID: {process.pid})"
                    })
            except Exception as e:
                progress_callback({
                    "type": "log",
                    "message": f"ERROR starting workers: {str(e)}"
                })
                return
            
            # Monitor progress
            active_workers = self.worker_count
            while active_workers > 0:
                try:
                    # Non-blocking check for results
                    result = self.result_queue.get(timeout=1)
                    
                    if result is None:
                        # Worker finished
                        active_workers -= 1
                        continue
                    
                    # Process result
                    result_type = result.get("type", "log")
                    
                    if result_type == "log":
                        progress_callback(result)
                    
                    elif result_type == "worker_status":
                        progress_callback(result)
                    
                    elif result_type == "portal_complete":
                        self.portals_completed += 1
                        self.total_tenders += result.get("tenders_found", 0)
                        self.total_departments += result.get("departments_processed", 0)
                        self.total_skipped_existing += result.get("skipped_existing_total", 0)
                        self.total_closing_date_reprocessed += result.get("closing_date_reprocessed_total", 0)
                        
                        progress_callback({
                            "type": "totals",
                            "total_tenders": self.total_tenders,
                            "total_departments": self.total_departments,
                            "portals_completed": self.portals_completed,
                            "skipped_existing_total": self.total_skipped_existing,
                            "closing_date_reprocessed_total": self.total_closing_date_reprocessed,
                        })
                        
                        progress_callback({
                            "type": "log",
                            "message": f"✓ Portal '{result.get('portal_name')}' completed: "
                                      f"{result.get('tenders_found', 0)} tenders, "
                                      f"{result.get('departments_processed', 0)} departments"
                        })
                
                except queue.Empty:
                    # No results yet, continue monitoring
                    continue
                except Exception as e:
                    progress_callback({
                        "type": "log",
                        "message": f"ERROR processing result: {str(e)}"
                    })
            
            # Wait for all workers to complete
            for worker in self.workers:
                worker.join(timeout=5)
            
            progress_callback({
                "type": "log",
                "message": f"All workers completed! Total: {self.total_tenders} tenders, "
                          f"{self.total_departments} departments, {self.portals_completed} portals"
            })
        
        except Exception as e:
            progress_callback({
                "type": "log",
                "message": f"FATAL ERROR: {str(e)}"
            })
    
    @staticmethod
    def _worker_process(worker_id: int, task_queue: mp.Queue, result_queue: mp.Queue, project_root: str):
        """Worker process function - runs in separate process."""
        try:
            # Send immediate startup log
            result_queue.put({
                "type": "log",
                "message": f"[DEBUG] Worker {worker_id + 1} process started"
            })
            
            # Add project root to path
            project_root_path = Path(project_root)
            if str(project_root_path) not in sys.path:
                sys.path.insert(0, str(project_root_path))
            
            result_queue.put({
                "type": "log",
                "message": f"[DEBUG] Worker {worker_id + 1} added project root to path: {project_root}"
            })
            
            # Import required modules (inside worker process)
            try:
                from scraper.playwright_logic import fetch_department_list_from_site_playwright
                from scraper.logic import run_scraping_logic, fetch_department_list_from_site_v2
                from scraper.driver_manager import setup_driver, safe_quit_driver
                from tender_store import TenderDataStore
                import os
                
                result_queue.put({
                    "type": "log",
                    "message": f"[DEBUG] Worker {worker_id + 1} imported modules successfully"
                })
            except Exception as import_error:
                result_queue.put({
                    "type": "log",
                    "message": f"Worker {worker_id + 1} IMPORT ERROR: {str(import_error)}"
                })
                result_queue.put(None)  # Signal worker completion
                return
            
            result_queue.put({
                "type": "log",
                "message": f"Worker {worker_id + 1} initialized (PID: {os.getpid()})"
            })
            
            # Process tasks until poison pill
            while True:
                try:
                    # Get next portal to scrape
                    portal_config = task_queue.get(timeout=2)
                    
                    if portal_config is None:
                        # Poison pill - worker is done
                        result_queue.put({
                            "type": "log",
                            "message": f"Worker {worker_id + 1} shutting down"
                        })
                        result_queue.put(None)  # Signal worker completion
                        break
                    
                    # Scrape this portal
                    ScrapingWorkerManager._scrape_portal_worker(
                        worker_id,
                        portal_config,
                        result_queue,
                        project_root_path
                    )
                
                except queue.Empty:
                    # No tasks available yet
                    continue
                except Exception as e:
                    result_queue.put({
                        "type": "log",
                        "message": f"Worker {worker_id + 1} ERROR: {str(e)}"
                    })
        
        except Exception as e:
            result_queue.put({
                "type": "log",
                "message": f"Worker {worker_id + 1} FATAL ERROR: {str(e)}"
            })
    
    @staticmethod
    def _scrape_portal_worker(worker_id: int, portal_config: Dict, result_queue: mp.Queue, project_root: Path):
        """Scrape a single portal (runs in worker process)."""
        driver = None
        portal_name = portal_config.get('Name', 'Unknown') if portal_config else 'Unknown'
        safe_quit_driver = None
        log_callback = lambda msg: None
        
        try:
            from scraper.playwright_logic import fetch_department_list_from_site_playwright
            from scraper.logic import run_scraping_logic
            from scraper.driver_manager import setup_driver, safe_quit_driver
            from tender_store import TenderDataStore
            import os
            
            base_url = portal_config.get('BaseURL', '')
            resume_data = portal_config.get("_resume_data", {}) if isinstance(portal_config, dict) else {}

            processed_department_names: Set[str] = {
                str(name).strip().lower()
                for name in (resume_data.get("processed_departments") or [])
                if str(name).strip()
            }

            db_known_tender_ids: Set[str] = set()
            db_tender_snapshot: Dict[str, Dict[str, str]] = {}
            try:
                db_path = project_root / "database" / "blackforest_tenders.sqlite3"
                store = TenderDataStore(str(db_path))
                db_known_tender_ids = set(store.get_existing_tender_ids_for_portal(portal_name) or [])
                db_tender_snapshot = dict(store.get_existing_tender_snapshot_for_portal(portal_name) or {})
            except Exception as known_ids_err:
                result_queue.put({
                    "type": "log",
                    "message": f"Worker {worker_id + 1}: WARNING could not load existing tender IDs for resume: {known_ids_err}"
                })

            resume_dept_count = len(processed_department_names)
            
            result_queue.put({
                "type": "worker_status",
                "worker_id": worker_id,
                "status": "running",
                "portal_name": portal_name,
                "current_department": "Fetching departments..." if resume_dept_count == 0 else f"Resuming: {resume_dept_count} department(s) already completed",
                "tenders_found": 0,
                "expected_tenders": 0,
                "expected_departments": 0,
                "tender_percent": 0,
                "progress_percent": 10,
            })
            
            result_queue.put({
                "type": "log",
                "message": f"Worker {worker_id + 1}: Starting portal '{portal_name}'"
            })
            
            # Fetch department list using Playwright (faster)
            def log_callback(msg):
                result_queue.put({
                    "type": "log",
                    "message": f"Worker {worker_id + 1}: {msg}"
                })
            
            org_list_url = portal_config.get('OrgListURL', base_url)
            departments, total_count = fetch_department_list_from_site_playwright(
                org_list_url,
                log_callback=log_callback
            )
            
            if not departments:
                result_queue.put({
                    "type": "log",
                    "message": f"Worker {worker_id + 1}: No departments found for '{portal_name}'"
                })
                result_queue.put({
                    "type": "portal_complete",
                    "worker_id": worker_id,
                    "portal_name": portal_name,
                    "tenders_found": 0,
                    "departments_processed": 0,
                })
                return
            
            result_queue.put({
                "type": "log",
                "message": f"Worker {worker_id + 1}: Found {len(departments)} departments (expected {total_count} tenders)"
            })
            
            result_queue.put({
                "type": "worker_status",
                "worker_id": worker_id,
                "status": "running",
                "portal_name": portal_name,
                "current_department": f"Processing {len(departments)} departments...",
                "tenders_found": 0,
                "expected_tenders": int(total_count or 0),
                "expected_departments": len(departments),
                "tender_percent": 0,
                "progress_percent": 30,
            })

            if resume_dept_count > 0:
                result_queue.put({
                    "type": "log",
                    "message": f"Worker {worker_id + 1}: Resume enabled for '{portal_name}' with {resume_dept_count} checkpointed department(s)"
                })
            
            # Setup WebDriver for scraping
            download_dir = project_root / "Tender_Downloads" / portal_name
            download_dir.mkdir(parents=True, exist_ok=True)
            
            driver = setup_driver(str(download_dir))
            
            # Setup database
            db_path = project_root / "database" / "blackforest_tenders.sqlite3"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Callbacks for progress updates
            def progress_callback(*args, **kwargs):
                """Enhanced progress callback with detailed department and tender info.
                Handles two different callback patterns from scraper.logic:
                1. (current, total, status_msg, dept_name, skipped, tenders_scraped, pending_depts) - 7 args
                2. (current, total, status_msg, extra_info) - 4 args where extra_info is a dict
                """
                if len(args) < 3:
                    return  # Not enough arguments
                
                current, total, status_msg = args[0], args[1], args[2]
                
                # Initialize defaults
                dept_name = ""
                tenders_scraped = 0
                pending_depts = 0
                
                checkpoint_department_completed = ""

                # Parse based on number of arguments
                if len(args) == 7:
                    # Pattern 1: (current, total, status_msg, dept_name, skipped, tenders_scraped, pending_depts)
                    dept_name = args[3] if isinstance(args[3], str) else str(args[3])
                    tenders_scraped = args[5]
                    pending_depts = args[6]
                elif len(args) >= 4:
                    # Pattern 2: (current, total, status_msg, extra_info)
                    extra_info = args[3]
                    if isinstance(extra_info, dict):
                        dept_name = extra_info.get("dept_name", "")
                        tenders_scraped = extra_info.get("total_tenders", 0)
                        pending_depts = extra_info.get("pending_depts", 0)
                        if dept_name:
                            normalized_dept = str(dept_name).strip().lower()
                            if normalized_dept:
                                processed_department_names.add(normalized_dept)
                                checkpoint_department_completed = normalized_dept
                
                if total > 0:
                    percent = int((current / total) * 100)
                    expected_tenders = int(total_count or 0)
                    tender_percent = 0
                    if expected_tenders > 0:
                        tender_percent = min(100, int((tenders_scraped / expected_tenders) * 100))
                    
                    # Format detailed status message
                    dept_display = dept_name[:40] if dept_name else "Processing..."
                    detailed_status = f"Dept {current}/{total}: {dept_display}"
                    
                    result_queue.put({
                        "type": "worker_status",
                        "worker_id": worker_id,
                        "status": "running",
                        "portal_name": portal_name,
                        "current_department": detailed_status,
                        "department_name": dept_name or "",
                        "dept_current": current,
                        "dept_total": total,
                        "tenders_found": tenders_scraped,
                        "expected_tenders": expected_tenders,
                        "expected_departments": total,
                        "tender_percent": tender_percent,
                        "pending_depts": pending_depts,
                        "progress_percent": percent,
                        "checkpoint_department_completed": checkpoint_department_completed,
                    })
                    
                    # Also send totals update
                    result_queue.put({
                        "type": "totals",
                        "total_tenders": tenders_scraped,
                        "total_departments": current,
                        "portals_completed": 0,
                    })
            
            tenders_found = [0]  # Use list to allow modification in nested function
            
            def status_callback(msg):
                # Extract tender count from status messages
                if "Total tenders extracted:" in msg:
                    try:
                        count_str = msg.split("Total tenders extracted:")[1].strip()
                        tenders_found[0] = int(count_str)
                        result_queue.put({
                            "type": "worker_status",
                            "worker_id": worker_id,
                            "tenders_found": tenders_found[0],
                        })
                    except:
                        pass
            
            # Run scraping logic (imported from existing code)
            summary = run_scraping_logic(
                departments_to_scrape=departments,
                base_url_config={
                    'Name': portal_name,
                    'BaseURL': base_url,
                    'OrgListURL': org_list_url,
                },
                download_dir=str(download_dir),
                log_callback=log_callback,
                progress_callback=progress_callback,
                status_callback=status_callback,
                driver=driver,
                deep_scrape=False,  # Only listing page for now
                existing_tender_ids=db_known_tender_ids,
                existing_tender_snapshot=db_tender_snapshot,
                existing_department_names=processed_department_names,
                sqlite_db_path=str(db_path),
                export_policy="always",
            )
            
            # Extract results
            final_tender_count = summary.get('extracted_total_tenders', 0)
            departments_processed = summary.get('processed_departments', 0)
            summary_processed_departments = summary.get("processed_department_names", []) or []
            skipped_existing_total = int(summary.get("skipped_existing_total", 0) or 0)
            closing_date_reprocessed_total = int(summary.get("closing_date_reprocessed_total", 0) or 0)
            normalized_summary_departments = {
                str(name).strip().lower()
                for name in summary_processed_departments
                if str(name).strip()
            }
            processed_department_names.update(normalized_summary_departments)
            
            result_queue.put({
                "type": "worker_status",
                "worker_id": worker_id,
                "status": "completed",
                "portal_name": portal_name,
                "dept_current": departments_processed,
                "dept_total": max(departments_processed, len(departments)),
                "expected_departments": max(departments_processed, len(departments)),
                "tenders_found": final_tender_count,
                "expected_tenders": int(total_count or final_tender_count),
                "tender_percent": 100,
                "progress_percent": 100,
                "checkpoint_processed_departments": sorted(processed_department_names),
            })
            
            result_queue.put({
                "type": "portal_complete",
                "worker_id": worker_id,
                "portal_name": portal_name,
                "tenders_found": final_tender_count,
                "departments_processed": departments_processed,
                "skipped_existing_total": skipped_existing_total,
                "closing_date_reprocessed_total": closing_date_reprocessed_total,
                "checkpoint_processed_departments": sorted(processed_department_names),
            })
        
        except Exception as e:
            result_queue.put({
                "type": "log",
                "message": f"Worker {worker_id + 1} ERROR scraping '{portal_name}': {str(e)}"
            })
            
            result_queue.put({
                "type": "worker_status",
                "worker_id": worker_id,
                "status": "failed",
                "portal_name": portal_name,
            })
        
        finally:
            # Cleanup WebDriver
            if driver and safe_quit_driver:
                try:
                    safe_quit_driver(driver, log_callback or (lambda *_: None))
                except:
                    pass
