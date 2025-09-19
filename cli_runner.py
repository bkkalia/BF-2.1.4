#!/usr/bin/env python3
"""
CLI Runner for Black Forest Tender Scraper
Handles department scraping operations via command line
"""

import sys
import os
import logging
import time
from pathlib import Path
from datetime import datetime
import pandas as pd

# Add project root to path
script_dir = Path(__file__).parent
project_root = script_dir
if project_root not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from cli_parser import CLIParser, validate_paths
    from config import APP_VERSION
    from scraper.logic import fetch_department_list_from_site_v2, run_scraping_logic
    from scraper.driver_manager import setup_driver, safe_quit_driver
    from app_settings import load_settings
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
                file_handler = logging.FileHandler(self.paths['log_file'])
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
        """List all available portals from base_urls.csv."""
        try:
            base_urls_file = self.paths['base_urls_file']
            if not base_urls_file.exists():
                self.logger.error(f"Base URLs file not found: {base_urls_file}")
                return

            df = pd.read_csv(base_urls_file)
            print("\n📋 Available Portals:")
            print("=" * 50)
            for idx, row in df.iterrows():
                print("2d")
            print("=" * 50)
            print(f"Total: {len(df)} portals available")
            print("\nUsage: python main.py --url 'Portal Name' department --all")

        except Exception as e:
            self.logger.error(f"Error reading portals: {e}")

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

            if self.args.dry_run:
                self.logger.info("DRY RUN MODE - No actual scraping will be performed")
                print("🔍 DRY RUN: Would scrape departments from HP Tenders")
                return

            # Get portal configuration (supports multiple portals)
            portal_name = getattr(self.args, 'url', None)
            portal_config = self.get_portal_config(portal_name)

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
                self.logger.info("Fetching department list from HP Tenders...")
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

            if not departments:
                self.logger.error("No departments to process!")
                return

            # Run the scraping
            self.logger.info(f"Starting scraping of {len(departments)} departments...")
            start_time = time.time()

            # Prepare progress callback for CLI
            def progress_callback(current, total, details, *args):
                if not self.args.quiet:
                    percent = (current / total * 100) if total > 0 else 0
                    print(".1f")

            # Run scraping logic
            run_scraping_logic(
                departments_to_scrape=departments,
                base_url_config=base_urls_config,
                download_dir=str(self.paths['output_dir']),
                log_callback=self.logger.info,
                progress_callback=progress_callback,
                status_callback=lambda msg: self.logger.info(f"STATUS: {msg}"),
                stop_event=None,  # CLI mode doesn't have stop events
                driver=self.driver,
                deep_scrape=False  # Keep it simple for CLI
            )

            elapsed = time.time() - start_time
            self.logger.info(".1f")
            if not self.args.quiet:
                print(f"\n✅ Scraping completed successfully in {elapsed:.1f} seconds!")
                print(f"📁 Output directory: {self.paths['output_dir']}")

        except KeyboardInterrupt:
            self.logger.info("Operation cancelled by user")
        except Exception as e:
            self.logger.error(f"Error during department scraping: {e}")
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
        runner.list_available_portals()
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
