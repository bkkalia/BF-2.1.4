#!/usr/bin/env python3
"""
CLI Parser for Black Forest Tender Scraper
Focused on HP Tenders department scraping (90% use case)
"""

import argparse
import sys
import os
from pathlib import Path

class CLIParser:
    """Command line interface for tender scraping operations."""

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description='Black Forest Tender Scraper - CLI Mode',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Scrape all departments from HP Tenders (most common use case)
  python main.py department --all

  # Scrape specific departments
  python main.py department "PWD" "Highways" "Irrigation"

  # Scrape with custom output directory
  python main.py department --all --output "C:\\Tenders\\HP"

  # Scrape with detailed logging
  python main.py department --all --log "C:\\Logs\\tenders.log" --verbose

  # Dry run to see what would be scraped
  python main.py department --all --dry-run

For Windows Task Scheduler, use the batch file: run_hp_tenders.bat
            """
        )

        # Global options
        self.parser.add_argument(
            '--config',
            type=str,
            help='Path to configuration file (default: settings.json)'
        )

        self.parser.add_argument(
            '--url',
            type=str,
            help='Portal name from base_urls.csv (default: HP Tenders)'
        )

        self.parser.add_argument(
            '--log',
            type=str,
            help='Path to log file (default: console output)'
        )

        self.parser.add_argument(
            '--output', '-o',
            type=str,
            help='Output directory for downloads (default: Tender_Downloads)'
        )

        self.parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Enable verbose logging'
        )

        self.parser.add_argument(
            '--quiet', '-q',
            action='store_true',
            help='Suppress non-essential output'
        )

        self.parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without executing'
        )

        self.parser.add_argument(
            '--engine',
            type=str,
            choices=['selenium', 'playwright'],
            default='playwright',
            help='Automation engine for portal navigation (default: playwright)'
        )

        self.parser.add_argument(
            '--json-events',
            action='store_true',
            help='Emit structured JSON events to stdout for GUI subprocess monitoring'
        )

        self.parser.add_argument(
            '--job-id',
            type=str,
            help='Optional job identifier propagated in JSON events for supervisor correlation'
        )

        # Subcommands
        subparsers = self.parser.add_subparsers(dest='command', help='Available commands')

        # Department command (main use case)
        dept_parser = subparsers.add_parser(
            'department',
            help='Scrape tenders by department from HP Tenders'
        )

        dept_parser.add_argument(
            '--all',
            action='store_true',
            help='Scrape all departments (default behavior)'
        )

        dept_parser.add_argument(
            '--filter',
            type=str,
            help='Filter departments by name pattern'
        )

        dept_parser.add_argument(
            '--max-departments',
            type=int,
            help='Limit number of departments to process'
        )

        dept_parser.add_argument(
            '--dept-workers',
            type=int,
            choices=[1, 2, 3, 4, 5],
            help='Number of parallel browser workers per portal department run (1-5)'
        )

        dept_parser.add_argument(
            '--only-new',
            action='store_true',
            help='Skip already known tenders using DB (default behaviour — kept for back-compat)'
        )

        dept_parser.add_argument(
            '--full-rescrape',
            action='store_true',
            help='Re-scrape ALL tenders ignoring existing DB records (overrides default only-new)'
        )

        dept_parser.add_argument(
            '--delta-mode',
            type=str,
            choices=['quick', 'full'],
            default='quick',
            help='Delta strategy for --only-new: quick (changed departments) or full (all departments)'
        )

        dept_parser.add_argument(
            '--manifest-path',
            type=str,
            help='Path to batch manifest JSON (default: batch_tender_manifest.json in project root)'
        )

        dept_parser.add_argument(
            '--export-policy',
            type=str,
            choices=['on_demand', 'always', 'alternate_days'],
            help='Excel export policy for this run (default from settings, recommended: on_demand)'
        )

        dept_parser.add_argument(
            '--export-now',
            action='store_true',
            help='Force Excel export for this run even if policy is on_demand'
        )

        dept_parser.add_argument(
            'departments',
            nargs='*',
            help='Specific department names to scrape (if not using --all)'
        )

        # URLs command to list available portals
        urls_parser = subparsers.add_parser(
            'urls',
            help='List available tender portals'
        )

        status_parser = subparsers.add_parser(
            'status',
            help='Show last scrape/export status from SQLite datastore'
        )

        status_parser.add_argument(
            '--portal',
            type=str,
            help='Portal name to filter status (default: all portals)'
        )

        export_parser = subparsers.add_parser(
            'export',
            help='Manually export latest completed portal scrape to Excel'
        )

        export_parser.add_argument(
            '--portal',
            type=str,
            help='Portal name to export (default: selected --url or HP Tenders)'
        )

        export_parser.add_argument(
            '--full-only',
            action='store_true',
            help='Export only from latest full-scope scrape (scope=all)'
        )

        # Help command
        help_parser = subparsers.add_parser(
            'help',
            help='Show detailed help information'
        )

        help_parser.add_argument(
            'topic',
            nargs='?',
            choices=['department', 'scheduling', 'examples', 'urls'],
            help='Help topic to show'
        )

    def parse_args(self, args=None):
        """Parse command line arguments."""
        return self.parser.parse_args(args)

    def show_help(self, topic=None):
        """Show help information."""
        if topic == 'department':
            print("""
DEPARTMENT SCRAPING HELP
========================

This is the primary use case - scraping all departments from HP Tenders.

BASIC USAGE:
  python main.py department --all

SPECIFIC DEPARTMENTS:
  python main.py department "PWD" "Highways" "Irrigation"

FILTERING:
  python main.py department --all --filter "PWD"

LIMIT RESULTS:
  python main.py department --all --max-departments 5

OUTPUT CONTROL:
  python main.py department --all --output "C:\\Tenders\\HP"

LOGGING:
  python main.py department --all --log "C:\\Logs\\tenders.log" --verbose

DRY RUN:
  python main.py department --all --dry-run

WINDOWS TASK SCHEDULER:
  Use run_hp_tenders.bat for automated scheduling
            """)
        elif topic == 'scheduling':
            print("""
SCHEDULING HELP
===============

WINDOWS TASK SCHEDULER SETUP:
1. Create a new task
2. Action: Start a program
3. Program: C:\\Path\\To\\run_hp_tenders.bat
4. Add arguments: (leave empty for default)
5. Triggers: Set your desired schedule

BATCH FILE LOCATION:
  run_hp_tenders.bat should be in the same directory as main.py

LOG FILES:
  Check the logs directory for execution logs
  Use --log option to specify custom log location
            """)
        elif topic == 'examples':
            print("""
EXAMPLES
========

DAILY SCRAPING:
  python main.py department --all --output "C:\\Daily\\HP"

WEEKLY REPORT:
  python main.py department --all --output "C:\\Weekly\\HP" --log "C:\\Logs\\weekly.log"

SPECIFIC DEPARTMENTS:
  python main.py department "Public Works" "Highways" "Water Supply"

FILTERED SCRAPING:
  python main.py department --all --filter "PWD" --max-departments 10

QUIET MODE (for automation):
  python main.py department --all --quiet --log "C:\\Logs\\auto.log"
            """)
        else:
            self.parser.print_help()

def get_default_config():
    """Get default configuration values."""
    script_dir = Path(__file__).parent
    return {
        'config_file': script_dir / 'settings.json',
        'output_dir': script_dir / 'Tender_Downloads',
        'log_file': None,  # Console output by default
        'base_urls_file': script_dir / 'base_urls.csv'
    }

def validate_paths(args):
    """Validate and resolve file paths."""
    config = get_default_config()

    # Resolve output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = config['output_dir']

    output_dir = output_dir.resolve()

    # Resolve log file
    log_file = None
    if args.log:
        log_file = Path(args.log).resolve()

    # Resolve config file
    if args.config:
        config_file = Path(args.config).resolve()
    else:
        config_file = config['config_file']

    return {
        'output_dir': output_dir,
        'log_file': log_file,
        'config_file': config_file,
        'base_urls_file': config['base_urls_file']
    }

if __name__ == '__main__':
    # Test the parser
    parser = CLIParser()
    args = parser.parse_args()
    print(f"Parsed command: {args.command}")
    print(f"Arguments: {args}")
