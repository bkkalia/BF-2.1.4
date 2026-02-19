#!/usr/bin/env python3
"""
CLI Runner for Black Forest Tender Scraper
Handles department scraping operations via command line
"""

import sys
import os
import logging
import time
import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime
import pandas as pd


def _configure_utf8_stdio():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if not stream:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_configure_utf8_stdio()

# Add project root to path
script_dir = Path(__file__).parent
project_root = script_dir
if project_root not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from cli_parser import CLIParser, validate_paths
    from config import APP_VERSION
    from scraper.logic import fetch_department_list_from_site_v2, run_scraping_logic
    from scraper.playwright_logic import fetch_department_list_from_site_playwright
    from scraper.driver_manager import setup_driver, safe_quit_driver
    from app_settings import load_settings
    from tender_store import TenderDataStore
    from utils import get_website_keyword_from_url
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

class CLIRunner:
    """Handles CLI operations for tender scraping."""

    def __init__(self, args):
        self.args = args
        self.paths = validate_paths(args)
        self.driver = None
        # Initialize logger early
        self.logger = logging.getLogger(__name__)
        self.setup_logging()
        self.load_configuration()

    def _emit_event(self, event_type, **payload):
        if not getattr(self.args, 'json_events', False):
            return
        event_data = {
            'type': str(event_type),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'schema_version': '1.0',
            'job_id': str(getattr(self.args, 'job_id', '') or ''),
        }
        event_data.update(payload)
        try:
            print(json.dumps(event_data, ensure_ascii=False), flush=True)
        except Exception:
            pass

    def setup_logging(self):
        """Setup logging for CLI operations."""
        log_level = logging.DEBUG if self.args.verbose else logging.INFO
        log_format = '%(asctime)s - %(levelname)s - %(message)s'

        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=[]
        )

        # Create logger for this module
        self.logger = logging.getLogger(__name__)

        # Add console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(console_handler)

        # Add file handler if log file specified
        if self.paths['log_file']:
            try:
                self.paths['log_file'].parent.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(self.paths['log_file'], encoding='utf-8')
                file_handler.setLevel(log_level)
                file_handler.setFormatter(logging.Formatter(log_format))
                logging.getLogger().addHandler(file_handler)
                self.logger.info(f"Logging to file: {self.paths['log_file']}")
            except Exception as e:
                print(f"Failed to setup file logging: {e}")  # Use print before logger is fully set up

        # Suppress selenium logs unless verbose
        if not self.args.verbose:
            logging.getLogger('selenium').setLevel(logging.WARNING)
            logging.getLogger('urllib3').setLevel(logging.WARNING)

    def load_configuration(self):
        """Load configuration from settings file."""
        try:
            # Provide default download directory for load_settings function
            default_download_dir = str(self.paths['output_dir'])
            self.settings = load_settings(str(self.paths['config_file']), default_download_dir)
            self.logger.info(f"Loaded configuration from {self.paths['config_file']}")
        except Exception as e:
            self.logger.warning(f"Could not load config file: {e}. Using defaults.")
            self.settings = {}

        # Override with CLI arguments
        if self.args.output:
            self.settings['download_directory'] = str(self.paths['output_dir'])

    def _normalize_department_key(self, value):
        text = str(value or '').strip().lower()
        return re.sub(r"\s+", " ", text)

    def _build_valid_departments(self, departments):
        valid_departments = []
        expected_total = 0
        for dept in departments or []:
            s_no = str(dept.get('s_no', '')).strip().lower()
            dept_name = str(dept.get('name', '')).strip().lower()
            count_text = str(dept.get('count_text', '')).strip()
            if s_no.isdigit() and dept_name not in ['organisation name', 'department name', 'organization', 'organization name']:
                valid_departments.append(dept)
                if count_text.isdigit():
                    expected_total += int(count_text)
        return valid_departments, expected_total

    def _build_department_snapshot(self, departments):
        snapshot = {}
        for dept in departments or []:
            name = str(dept.get('name', '')).strip()
            key = self._normalize_department_key(name)
            if not key:
                continue
            count_text = str(dept.get('count_text', '')).strip()
            try:
                count_val = int(count_text) if count_text.isdigit() else 0
            except Exception:
                count_val = 0
            snapshot[key] = {
                'name': name,
                'count': max(0, count_val),
                'department': dept,
            }
        return snapshot

    def _plan_quick_delta_departments(self, baseline_departments, latest_departments):
        baseline_snapshot = self._build_department_snapshot(baseline_departments)
        latest_snapshot = self._build_department_snapshot(latest_departments)

        baseline_keys = set(baseline_snapshot.keys())
        latest_keys = set(latest_snapshot.keys())

        added_keys = sorted(latest_keys - baseline_keys)
        removed_keys = sorted(baseline_keys - latest_keys)
        common_keys = sorted(latest_keys.intersection(baseline_keys))

        changed_keys = []
        count_changed = 0
        for key in common_keys:
            old_count = int(baseline_snapshot[key].get('count', 0))
            new_count = int(latest_snapshot[key].get('count', 0))
            if old_count != new_count:
                changed_keys.append(key)
                count_changed += 1

        targeted_keys = set(added_keys + changed_keys)
        targeted_departments = [latest_snapshot[key]['department'] for key in sorted(targeted_keys) if key in latest_snapshot]

        stats = {
            'baseline_departments': len(baseline_keys),
            'latest_departments': len(latest_keys),
            'added_departments': len(added_keys),
            'removed_departments': len(removed_keys),
            'count_changed_departments': count_changed,
            'targeted_departments': len(targeted_departments),
        }
        return targeted_departments, stats

    def _manifest_path(self):
        path = str(getattr(self.args, 'manifest_path', '') or '').strip()
        if not path:
            path = str(project_root / 'batch_tender_manifest.json')
        return path

    def _load_manifest(self):
        path = self._manifest_path()
        if not os.path.exists(path):
            return {'portals': {}}
        try:
            with open(path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                return {'portals': {}}
            data.setdefault('portals', {})
            if not isinstance(data.get('portals'), dict):
                data['portals'] = {}
            return data
        except Exception:
            return {'portals': {}}

    def _save_manifest(self, data):
        path = self._manifest_path()
        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
        except Exception as err:
            self.logger.warning(f"Failed to save manifest: {err}")

    def _get_sqlite_known_ids_for_portal(self, portal_name, portal_config):
        config_dir = str(self.paths['config_file'].parent)
        sqlite_db_path = str(self.settings.get('central_sqlite_db_path') or '').strip()
        if sqlite_db_path and not os.path.isabs(sqlite_db_path):
            sqlite_db_path = str(Path(config_dir) / sqlite_db_path)
        if not sqlite_db_path or not os.path.exists(sqlite_db_path):
            return set()

        base_url = str(portal_config.get('BaseURL') or '').strip()
        keyword = str(portal_config.get('Keyword') or '').strip()
        keyword_from_url = ''
        try:
            from utils import get_website_keyword_from_url
            keyword_from_url = str(get_website_keyword_from_url(base_url) or '').strip()
        except Exception:
            keyword_from_url = ''

        candidates_raw = {
            str(portal_name or '').strip(),
            keyword,
            keyword_from_url,
            keyword.replace('.', '_').replace('-', '_'),
            keyword_from_url.replace('.', '_').replace('-', '_'),
        }
        portal_candidates = sorted({item.lower() for item in candidates_raw if item})
        if not portal_candidates:
            return set()

        placeholders = ','.join(['?'] * len(portal_candidates))
        query = (
            "SELECT DISTINCT trim(tender_id_extracted) "
            "FROM tenders "
            "WHERE trim(coalesce(tender_id_extracted, '')) <> '' "
            f"AND lower(trim(coalesce(portal_name, ''))) IN ({placeholders})"
        )

        try:
            conn = sqlite3.connect(sqlite_db_path)
            try:
                rows = conn.execute(query, portal_candidates).fetchall()
            finally:
                conn.close()
        except Exception as err:
            self.logger.warning(f"SQLite known-id seed failed for '{portal_name}': {err}")
            return set()

        return {
            str(row[0]).strip()
            for row in rows
            if row and str(row[0]).strip()
        }

    def _get_known_from_manifest(self, portal_name, portal_config):
        manifest = self._load_manifest()
        portal_data = manifest.setdefault('portals', {}).setdefault(portal_name, {})

        known_ids = {
            str(item).strip()
            for item in portal_data.get('tender_ids', [])
            if str(item).strip()
        }
        known_departments = {
            str(name).strip().lower()
            for name in portal_data.get('processed_departments', [])
            if str(name).strip()
        }

        sqlite_ids = self._get_sqlite_known_ids_for_portal(portal_name, portal_config)
        if sqlite_ids:
            known_ids.update(sqlite_ids)

        return manifest, portal_data, known_ids, known_departments

    def _update_manifest_for_portal(self, manifest, portal_name, summary):
        portals = manifest.setdefault('portals', {})
        portal_data = portals.setdefault(portal_name, {})

        known = {
            str(item).strip()
            for item in portal_data.get('tender_ids', [])
            if str(item).strip()
        }
        known.update({
            str(item).strip()
            for item in summary.get('extracted_tender_ids', [])
            if str(item).strip()
        })

        known_departments = {
            str(name).strip().lower()
            for name in portal_data.get('processed_departments', [])
            if str(name).strip()
        }
        known_departments.update({
            str(name).strip().lower()
            for name in summary.get('processed_department_names', [])
            if str(name).strip()
        })

        portal_data['tender_ids'] = sorted(known)
        portal_data['processed_departments'] = sorted(known_departments)
        portal_data['last_run'] = datetime.now().isoformat(timespec='seconds')
        portal_data['last_expected'] = int(summary.get('expected_total_tenders', 0) or 0)
        portal_data['last_extracted'] = int(summary.get('extracted_total_tenders', 0) or 0)

        self._save_manifest(manifest)
        return len(known)

    def _merge_pass_summaries(self, first_summary, delta_summary):
        combined_ids = sorted(set(first_summary.get('extracted_tender_ids', [])).union(delta_summary.get('extracted_tender_ids', [])))
        combined_departments = sorted(set(first_summary.get('processed_department_names', [])).union(delta_summary.get('processed_department_names', [])))
        combined_source_departments = []
        seen_dept_keys = set()
        for dept in list(first_summary.get('source_departments', []) or []) + list(delta_summary.get('source_departments', []) or []):
            if not isinstance(dept, dict):
                continue
            dept_name = str(dept.get('name', '')).strip()
            dept_key = self._normalize_department_key(dept_name)
            if not dept_key or dept_key in seen_dept_keys:
                continue
            seen_dept_keys.add(dept_key)
            combined_source_departments.append(dept)

        merged = {
            'status': first_summary.get('status', 'Scraping completed'),
            'processed_departments': int(first_summary.get('processed_departments', 0)) + int(delta_summary.get('processed_departments', 0)),
            'expected_total_tenders': int(first_summary.get('expected_total_tenders', 0)),
            'extracted_total_tenders': int(first_summary.get('extracted_total_tenders', 0)) + int(delta_summary.get('extracted_total_tenders', 0)),
            'skipped_existing_total': int(first_summary.get('skipped_existing_total', 0)) + int(delta_summary.get('skipped_existing_total', 0)),
            'skipped_resume_departments': int(first_summary.get('skipped_resume_departments', 0)) + int(delta_summary.get('skipped_resume_departments', 0)),
            'department_summaries': list(first_summary.get('department_summaries', [])) + list(delta_summary.get('department_summaries', [])),
            'extracted_tender_ids': combined_ids,
            'processed_department_names': combined_departments,
            'output_file_path': delta_summary.get('output_file_path') or first_summary.get('output_file_path'),
            'output_file_type': delta_summary.get('output_file_type') or first_summary.get('output_file_type'),
            'sqlite_db_path': delta_summary.get('sqlite_db_path') or first_summary.get('sqlite_db_path'),
            'sqlite_run_id': delta_summary.get('sqlite_run_id') or first_summary.get('sqlite_run_id'),
            'partial_saved': bool(first_summary.get('partial_saved') or delta_summary.get('partial_saved')),
            'delta_sweep_extracted': int(delta_summary.get('extracted_total_tenders', 0)),
            'delta_mode': delta_summary.get('delta_mode') or first_summary.get('delta_mode') or 'quick',
            'delta_quick_stats': delta_summary.get('delta_quick_stats', {}),
            'source_departments': combined_source_departments,
        }
        if 'error' in str(first_summary.get('status', '')).lower() or 'error' in str(delta_summary.get('status', '')).lower():
            merged['status'] = 'Error during scraping'
        return merged

    def get_portal_config(self, portal_name=None):
        """Get portal configuration from base_urls.csv."""
        try:
            base_urls_file = self.paths['base_urls_file']
            if not base_urls_file.exists():
                raise FileNotFoundError(f"Base URLs file not found: {base_urls_file}")

            # Read CSV
            df = pd.read_csv(base_urls_file)

            # If no portal specified, default to HP Tenders
            if not portal_name:
                portal_name = 'HP Tenders'

            # Try exact name match first
            portal_row = df[df['Name'].str.lower() == portal_name.lower()]

            if portal_row.empty:
                # Try partial match
                portal_row = df[df['Name'].str.contains(portal_name, case=False)]

            if portal_row.empty:
                # List available portals
                available = df['Name'].tolist()
                self.logger.error(f"Portal '{portal_name}' not found in base_urls.csv")
                self.logger.info(f"Available portals: {', '.join(available)}")
                raise ValueError(f"Portal '{portal_name}' not found. Available: {available}")

            config = portal_row.iloc[0].to_dict()
            self.logger.info(f"Using {config['Name']} configuration: {config['BaseURL']}")
            return config

        except Exception as e:
            self.logger.error(f"Error loading portal config: {e}")
            # Fallback to HP Tenders
            return {
                'Name': 'HP Tenders',
                'BaseURL': 'https://hptenders.gov.in/nicgep/app',
                'Keyword': 'HP Tenders'
            }

    def list_available_portals(self):
        """List all available portals from base_urls.csv with serial numbers for selection."""
        try:
            base_urls_file = self.paths['base_urls_file']
            if not base_urls_file.exists():
                self.logger.error(f"Base URLs file not found: {base_urls_file}")
                return

            df = pd.read_csv(base_urls_file)
            print("\n📋 Available Portals:")
            print("=" * 80)
            print(f"{'Sr.No':<5} {'Portal Name':<30} {'Base URL':<40} {'Keyword'}")
            print("=" * 80)
            for sr_no, (idx, row) in enumerate(df.iterrows(), 1):
                name = str(row.get('Name', 'Unknown')).strip()
                base_url = str(row.get('BaseURL', '')).strip()
                keyword = str(row.get('Keyword', '')).strip()
                print(f"{sr_no:<5} {name:<30} {base_url:<40} {keyword}")
            print("=" * 80)
            print(f"Total: {len(df)} portals available")
            print("\nUsage Examples:")
            print("  python main.py --url 'HP Tenders' department --all")
            print("  python main.py --url '2' department --all  (using serial number)")
            print("  python main.py urls  (shows this list)")

        except Exception as e:
            self.logger.error(f"Error reading portals: {e}")

    def _resolve_sqlite_db_path(self):
        config_dir = str(self.paths['config_file'].parent)
        sqlite_db_path = str(self.settings.get('central_sqlite_db_path') or '').strip()
        if sqlite_db_path and not os.path.isabs(sqlite_db_path):
            sqlite_db_path = str(Path(config_dir) / sqlite_db_path)
        if not sqlite_db_path:
            sqlite_db_path = str(project_root / 'data' / 'blackforest_tenders.sqlite3')
        return sqlite_db_path

    def _get_data_store(self):
        sqlite_db_path = self._resolve_sqlite_db_path()
        return TenderDataStore(sqlite_db_path), sqlite_db_path

    def show_status(self):
        try:
            portal_filter = str(getattr(self.args, 'portal', '') or '').strip() or None
            data_store, sqlite_db_path = self._get_data_store()
            snapshot = data_store.get_portal_status_snapshot(portal_name=portal_filter)

            policy = str(self.settings.get('excel_export_policy', 'on_demand') or 'on_demand').strip().lower()
            try:
                interval_days = max(1, int(self.settings.get('excel_export_interval_days', 2) or 2))
            except Exception:
                interval_days = 2

            print("\n📊 Scrape/Export Status")
            print("=" * 70)
            print(f"SQLite DB: {sqlite_db_path}")
            print(f"Portal Filter: {portal_filter or 'ALL'}")
            print(f"Export Policy: {policy}")
            print(f"Export Interval Days: {interval_days}")

            last_run = snapshot.get('last_run') or {}
            print("-" * 70)
            print(f"Last Run Completed: {last_run.get('completed_at') or 'N/A'}")
            print(f"Last Run Status: {last_run.get('status') or 'N/A'}")
            print(f"Last Run Scope: {last_run.get('scope_mode') or 'N/A'}")
            print(f"Last Full Scrape: {snapshot.get('last_full_scrape_at') or 'N/A'}")
            print(f"Last Excel Export: {snapshot.get('last_excel_export_at') or 'N/A'}")
            print(f"Last Excel Path: {snapshot.get('last_excel_export_path') or 'N/A'}")

            if policy == 'alternate_days' and snapshot.get('last_excel_export_at'):
                try:
                    last_export_at = datetime.fromisoformat(str(snapshot.get('last_excel_export_at')))
                    next_due = last_export_at + pd.Timedelta(days=interval_days)
                    print(f"Next Export Due: {next_due.isoformat(timespec='seconds')}")
                except Exception:
                    pass
            print("=" * 70)
        except Exception as err:
            self.logger.error(f"Failed to show status: {err}")
            raise

    def export_latest(self):
        try:
            portal_name = str(getattr(self.args, 'portal', '') or getattr(self.args, 'url', '') or 'HP Tenders').strip()
            full_only = bool(getattr(self.args, 'full_only', False))
            portal_config = self.get_portal_config(portal_name)
            resolved_portal_name = str(portal_config.get('Name') or portal_name).strip()

            data_store, _sqlite_db_path = self._get_data_store()
            run_id = data_store.get_latest_completed_run_id(portal_name=resolved_portal_name, full_only=full_only)
            if not run_id:
                print("No completed run found to export.")
                return

            website_keyword = get_website_keyword_from_url(str(portal_config.get('BaseURL') or ''))
            output_dir = str(self.paths['output_dir'])
            export_path, export_type = data_store.export_run(
                run_id=run_id,
                output_dir=output_dir,
                website_keyword=website_keyword,
                mark_partial=False,
            )
            if not export_path:
                print("No tenders found in latest run for export.")
                return

            print(f"\n✅ Manual export completed")
            print(f"Run ID: {run_id}")
            print(f"Type: {str(export_type or '').upper()}")
            print(f"Path: {export_path}")
        except Exception as err:
            self.logger.error(f"Manual export failed: {err}")
            raise

    def show_banner(self):
        """Show CLI banner."""
        if not self.args.quiet:
            print(f"""
╔══════════════════════════════════════════════════════════════╗
║              Black Forest Tender Scraper v{APP_VERSION}              ║
║                       CLI Mode - Department Scraping                 ║
╚══════════════════════════════════════════════════════════════╝
""")

    def run_department_scraping(self):
        """Run department scraping operation."""
        try:
            self.show_banner()
            self._emit_event('start', command='department', portal=getattr(self.args, 'url', None) or 'HP Tenders')
            selected_engine = str(getattr(self.args, 'engine', 'selenium') or 'selenium').strip().lower()
            if selected_engine not in ('selenium', 'playwright'):
                selected_engine = 'selenium'
            self.logger.info(f"Selected engine: {selected_engine}")
            self._emit_event('engine', engine=selected_engine)

            if self.args.dry_run:
                self.logger.info("DRY RUN MODE - No actual scraping will be performed")
                print("🔍 DRY RUN: Would scrape departments from HP Tenders")
                self._emit_event('dry_run', command='department')
                return

            # Get portal configuration (supports multiple portals)
            portal_name = getattr(self.args, 'url', None)
            portal_config = self.get_portal_config(portal_name)
            self._emit_event(
                'portal',
                name=portal_config.get('Name', ''),
                base_url=portal_config.get('BaseURL', ''),
            )

            # Setup WebDriver
            self.logger.info("Setting up WebDriver...")
            self.driver = setup_driver(initial_download_dir=str(self.paths['output_dir']))

            # Create base URLs config for the scraper
            base_urls_config = {
                'BaseURL': portal_config['BaseURL'],
                'OrgListURL': f"{portal_config['BaseURL']}?page=FrontEndTendersByOrganisation&service=page",
                'Name': portal_config['Name']
            }

            # Determine which departments to scrape
            if self.args.all or not self.args.departments:
                # Scrape all departments
                self.logger.info("Fetching department list from portal...")
                if selected_engine == 'playwright':
                    departments, total_tenders = fetch_department_list_from_site_playwright(
                        base_urls_config['OrgListURL'],
                        self.logger.info
                    )
                    if not departments:
                        self.logger.warning("Playwright department fetch returned no rows; falling back to Selenium fetch")
                        departments, total_tenders = fetch_department_list_from_site_v2(
                            base_urls_config['OrgListURL'],
                            self.logger.info
                        )
                else:
                    departments, total_tenders = fetch_department_list_from_site_v2(
                        base_urls_config['OrgListURL'],
                        self.logger.info
                    )

                if not departments:
                    self.logger.error("No departments found!")
                    return

                # Apply filters if specified
                if self.args.filter:
                    departments = [d for d in departments if self.args.filter.lower() in d['name'].lower()]
                    self.logger.info(f"Filtered to {len(departments)} departments matching '{self.args.filter}'")

                if self.args.max_departments:
                    departments = departments[:self.args.max_departments]
                    self.logger.info(f"Limited to first {len(departments)} departments")

                self.logger.info(f"Found {len(departments)} departments to process")
                self._emit_event(
                    'departments_loaded',
                    total_departments=len(departments),
                    estimated_total_tenders=int(total_tenders or 0),
                )
                if not self.args.quiet:
                    for dept in departments[:5]:  # Show first 5
                        print(f"  • {dept['name']} ({dept['count_text']} tenders)")
                    if len(departments) > 5:
                        print(f"  ... and {len(departments) - 5} more")

            else:
                # Scrape specific departments
                department_names = self.args.departments
                self.logger.info(f"Will attempt to scrape {len(department_names)} specific departments:")
                for name in department_names:
                    print(f"  • {name}")

                # For specific departments, we'd need to fetch the full list and filter
                # This is a simplified version - in practice you'd want to match against actual department names
                self.logger.warning("Specific department scraping requires department list lookup")
                self.logger.warning("Falling back to 'all departments' mode")
                if selected_engine == 'playwright':
                    departments, total_tenders = fetch_department_list_from_site_playwright(
                        base_urls_config['OrgListURL'],
                        self.logger.info
                    )
                    if not departments:
                        self.logger.warning("Playwright department fetch returned no rows; falling back to Selenium fetch")
                        departments, total_tenders = fetch_department_list_from_site_v2(
                            base_urls_config['OrgListURL'],
                            self.logger.info
                        )
                else:
                    departments, total_tenders = fetch_department_list_from_site_v2(
                        base_urls_config['OrgListURL'],
                        self.logger.info
                    )

                if department_names:
                    # Filter to requested departments (case-insensitive partial match)
                    filtered_depts = []
                    for dept in departments:
                        for req_name in department_names:
                            if req_name.lower() in dept['name'].lower():
                                filtered_depts.append(dept)
                                break
                    departments = filtered_depts
                    self.logger.info(f"Matched {len(departments)} departments from request")
                    self._emit_event(
                        'departments_loaded',
                        total_departments=len(departments),
                        estimated_total_tenders=int(total_tenders or 0),
                        filtered=True,
                    )

            if not departments:
                self.logger.error("No departments to process!")
                return

            # Run the scraping
            self.logger.info(f"Starting scraping of {len(departments)} departments...")
            start_time = time.time()

            # Prepare progress callback for CLI
            def progress_callback(current, total, details, *args):
                percent = (current / total * 100) if total > 0 else 0
                scraped_tenders = 0
                if args:
                    try:
                        scraped_tenders = int(args[0] or 0)
                    except Exception:
                        scraped_tenders = 0
                self._emit_event(
                    'progress',
                    current=int(current or 0),
                    total=int(total or 0),
                    percent=round(float(percent), 2),
                    details=str(details or ''),
                    scraped_tenders=int(scraped_tenders),
                )
                if not self.args.quiet:
                    print(f"Progress: {current}/{total} ({percent:.1f}%) - {details}")

            def status_callback(message):
                text = str(message or '').strip()
                if text:
                    self.logger.info(f"STATUS: {text}")
                    self._emit_event('status', message=text)

            # Run scraping logic
            config_dir = str(self.paths['config_file'].parent)
            sqlite_db_path = str(self.settings.get('central_sqlite_db_path') or '').strip()
            if sqlite_db_path and not os.path.isabs(sqlite_db_path):
                sqlite_db_path = str(Path(config_dir) / sqlite_db_path)

            sqlite_backup_dir = str(self.settings.get('sqlite_backup_directory') or '').strip()
            if sqlite_backup_dir and not os.path.isabs(sqlite_backup_dir):
                sqlite_backup_dir = str(Path(config_dir) / sqlite_backup_dir)

            export_policy = str(getattr(self.args, 'export_policy', '') or self.settings.get('excel_export_policy', 'on_demand') or 'on_demand').strip().lower()
            if export_policy not in ('on_demand', 'always', 'alternate_days'):
                export_policy = 'on_demand'
            try:
                export_interval_days = max(1, int(self.settings.get('excel_export_interval_days', 2) or 2))
            except Exception:
                export_interval_days = 2
            force_excel_export = bool(getattr(self.args, 'export_now', False))
            self.logger.info(f"Excel export policy: {export_policy} | interval_days={export_interval_days} | force={force_excel_export}")

            dept_workers = self.args.dept_workers
            if dept_workers is None:
                try:
                    dept_workers = int(self.settings.get('department_parallel_workers', 1) or 1)
                except (TypeError, ValueError):
                    dept_workers = 1
            dept_workers = max(1, min(5, int(dept_workers)))
            self.logger.info(f"Department browser workers: {dept_workers}")

            valid_departments, expected_total = self._build_valid_departments(departments)
            if valid_departments:
                departments = valid_departments

            known_ids = set()
            known_departments = set()
            manifest = {'portals': {}}
            portal_manifest_data = {}
            only_new = bool(getattr(self.args, 'only_new', False))
            delta_mode = str(getattr(self.args, 'delta_mode', 'quick') or 'quick').strip().lower()
            if delta_mode not in ('quick', 'full'):
                delta_mode = 'quick'

            if only_new:
                manifest, portal_manifest_data, known_ids, known_departments = self._get_known_from_manifest(
                    portal_config.get('Name', 'Unknown'),
                    portal_config,
                )
                self.logger.info(f"Only-new mode: known IDs={len(known_ids)}, known departments={len(known_departments)}, delta={delta_mode}")
                self._emit_event(
                    'only_new_seed',
                    known_ids=len(known_ids),
                    known_departments=len(known_departments),
                    delta_mode=delta_mode,
                    manifest_path=self._manifest_path(),
                )

            summary = run_scraping_logic(
                departments_to_scrape=departments,
                base_url_config=base_urls_config,
                download_dir=str(self.paths['output_dir']),
                log_callback=self.logger.info,
                progress_callback=progress_callback,
                status_callback=status_callback,
                stop_event=None,  # CLI mode doesn't have stop events
                driver=self.driver,
                deep_scrape=False,  # Keep it simple for CLI
                existing_tender_ids=known_ids if only_new else None,
                existing_department_names=known_departments if only_new else None,
                sqlite_db_path=sqlite_db_path or None,
                sqlite_backup_dir=sqlite_backup_dir or None,
                sqlite_backup_retention_days=int(self.settings.get('sqlite_backup_retention_days', 30) or 30),
                department_parallel_workers=dept_workers,
                export_policy=export_policy,
                export_interval_days=export_interval_days,
                force_excel_export=force_excel_export,
            )

            if not isinstance(summary, dict):
                summary = {}
            summary.setdefault('expected_total_tenders', int(expected_total or 0))
            summary.setdefault('extracted_total_tenders', 0)
            summary.setdefault('skipped_existing_total', 0)
            summary.setdefault('processed_departments', 0)
            summary.setdefault('skipped_resume_departments', 0)
            summary.setdefault('extracted_tender_ids', [])
            summary.setdefault('processed_department_names', [])
            summary.setdefault('department_summaries', [])
            summary.setdefault('output_file_path', None)
            summary.setdefault('output_file_type', None)
            summary.setdefault('sqlite_db_path', sqlite_db_path or None)
            summary.setdefault('sqlite_run_id', None)
            summary.setdefault('partial_saved', False)
            summary.setdefault('source_departments', list(departments))

            if only_new and 'error' not in str(summary.get('status', '')).lower():
                first_pass_summary = dict(summary)
                first_ids = {
                    str(item).strip()
                    for item in first_pass_summary.get('extracted_tender_ids', [])
                    if str(item).strip()
                }

                delta_summary = None
                if delta_mode == 'full':
                    self._emit_event('delta_start', mode='full', strategy='all_departments')
                    delta_summary = run_scraping_logic(
                        departments_to_scrape=departments,
                        base_url_config=base_urls_config,
                        download_dir=str(self.paths['output_dir']),
                        log_callback=self.logger.info,
                        progress_callback=progress_callback,
                        status_callback=status_callback,
                        stop_event=None,
                        driver=self.driver,
                        deep_scrape=False,
                        existing_tender_ids=set(known_ids).union(first_ids),
                        existing_department_names=set(),
                        sqlite_db_path=sqlite_db_path or None,
                        sqlite_backup_dir=sqlite_backup_dir or None,
                        sqlite_backup_retention_days=int(self.settings.get('sqlite_backup_retention_days', 30) or 30),
                        department_parallel_workers=dept_workers,
                        export_policy=export_policy,
                        export_interval_days=export_interval_days,
                        force_excel_export=force_excel_export,
                    )
                else:
                    self._emit_event('delta_start', mode='quick', strategy='changed_departments')
                    latest_departments, _ = fetch_department_list_from_site_v2(
                        base_urls_config['OrgListURL'],
                        self.logger.info,
                    )
                    latest_valid, _latest_expected = self._build_valid_departments(latest_departments or [])
                    delta_departments, quick_stats = self._plan_quick_delta_departments(
                        first_pass_summary.get('source_departments', []),
                        latest_valid,
                    )
                    self._emit_event('delta_quick_compare', **quick_stats)

                    if delta_departments:
                        delta_summary = run_scraping_logic(
                            departments_to_scrape=delta_departments,
                            base_url_config=base_urls_config,
                            download_dir=str(self.paths['output_dir']),
                            log_callback=self.logger.info,
                            progress_callback=progress_callback,
                            status_callback=status_callback,
                            stop_event=None,
                            driver=self.driver,
                            deep_scrape=False,
                            existing_tender_ids=set(known_ids).union(first_ids),
                            existing_department_names=set(),
                            sqlite_db_path=sqlite_db_path or None,
                            sqlite_backup_dir=sqlite_backup_dir or None,
                            sqlite_backup_retention_days=int(self.settings.get('sqlite_backup_retention_days', 30) or 30),
                            department_parallel_workers=dept_workers,
                            export_policy=export_policy,
                            export_interval_days=export_interval_days,
                            force_excel_export=force_excel_export,
                        )
                    else:
                        delta_summary = {
                            'status': 'Quick delta: no changed departments',
                            'processed_departments': 0,
                            'expected_total_tenders': int(first_pass_summary.get('expected_total_tenders', 0)),
                            'extracted_total_tenders': 0,
                            'skipped_existing_total': 0,
                            'skipped_resume_departments': 0,
                            'department_summaries': [],
                            'extracted_tender_ids': [],
                            'processed_department_names': [],
                            'output_file_path': first_pass_summary.get('output_file_path'),
                            'output_file_type': first_pass_summary.get('output_file_type'),
                            'sqlite_db_path': first_pass_summary.get('sqlite_db_path'),
                            'sqlite_run_id': first_pass_summary.get('sqlite_run_id'),
                            'partial_saved': bool(first_pass_summary.get('partial_saved', False)),
                            'source_departments': [],
                            'delta_quick_stats': quick_stats,
                        }

                if not isinstance(delta_summary, dict):
                    delta_summary = {}
                delta_summary.setdefault('delta_mode', delta_mode)
                summary = self._merge_pass_summaries(first_pass_summary, delta_summary)

            known_total = 0
            if only_new:
                known_total = self._update_manifest_for_portal(manifest, portal_config.get('Name', 'Unknown'), summary)
                self._emit_event('manifest_updated', known_total=int(known_total), manifest_path=self._manifest_path())

            elapsed = time.time() - start_time
            self.logger.info(f"Scraping completed in {elapsed:.1f} seconds")
            self._emit_event(
                'completed',
                elapsed_seconds=round(float(elapsed), 2),
                output_dir=str(self.paths['output_dir']),
                total_departments=len(departments),
                expected_total_tenders=int(summary.get('expected_total_tenders', 0) or 0),
                extracted_total_tenders=int(summary.get('extracted_total_tenders', 0) or 0),
                skipped_existing_total=int(summary.get('skipped_existing_total', 0) or 0),
                processed_departments=int(summary.get('processed_departments', 0) or 0),
                output_file_path=str(summary.get('output_file_path') or ''),
                output_file_type=str(summary.get('output_file_type') or ''),
                sqlite_db_path=str(summary.get('sqlite_db_path') or ''),
                sqlite_run_id=summary.get('sqlite_run_id'),
                partial_saved=bool(summary.get('partial_saved', False)),
                only_new=only_new,
                delta_mode=delta_mode if only_new else '',
                known_total=int(known_total),
            )
            if not self.args.quiet:
                print(f"\n✅ Scraping completed successfully in {elapsed:.1f} seconds!")
                print(f"📁 Output directory: {self.paths['output_dir']}")

        except KeyboardInterrupt:
            self.logger.info("Operation cancelled by user")
            self._emit_event('cancelled', reason='keyboard_interrupt')
        except Exception as e:
            self.logger.error(f"Error during department scraping: {e}")
            self._emit_event('error', message=str(e))
            if self.args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)
        finally:
            if self.driver:
                safe_quit_driver(self.driver, self.logger.info)

def main():
    """Main CLI entry point."""
    parser = CLIParser()

    # Parse arguments
    try:
        args = parser.parse_args()
    except SystemExit:
        # argparse handles --help and errors
        return

    # Handle help command
    if args.command == 'help':
        parser.show_help(args.topic)
        return

    # Handle URLs command
    if args.command == 'urls':
        runner = CLIRunner(args)
        runner.show_banner()
        runner.list_available_portals()
        return

    if args.command == 'status':
        runner = CLIRunner(args)
        runner.show_status()
        return

    if args.command == 'export':
        runner = CLIRunner(args)
        runner.export_latest()
        return

    # Handle department command
    if args.command == 'department':
        runner = CLIRunner(args)
        runner.run_department_scraping()
    else:
        # No command specified, show help
        parser.parser.print_help()

if __name__ == '__main__':
    main()
