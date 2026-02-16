#!/usr/bin/env python3
"""
CLI Main Entry Point for Black Forest Tender Scraper
Separate entry point for console mode with banner
"""

import sys
import os

# Handle readline compatibility issues that can occur in CLI mode
try:
    import readline
except ImportError:
    pass
except AttributeError as e:
    if 'backend' in str(e):
        # Create dummy readline module to prevent interactive hook errors
        import types
        dummy_readline = types.ModuleType('readline')
        setattr(dummy_readline, 'backend', type('DummyBackend', (), {})())
        sys.modules['readline'] = dummy_readline
    else:
        raise

# Disable interactive hook to prevent readline setup errors
setattr(sys, '__interactivehook__', lambda: None)

import tkinter as tk
import tkinter.messagebox
import logging
import datetime
import platform
import traceback


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

# --- Calculate Absolute Paths Early ---
try:
    # Get the directory where cli_main.py resides
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # Fallback for environments where __file__ might not be defined (e.g., interactive)
    SCRIPT_DIR = os.getcwd()

# --- Add Project Root to sys.path ---
# This allows absolute imports from the project root (e.g., 'import config')
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# --- Configuration and Utility Imports ---
try:
    from config import (
        LOG_FORMAT, LOG_LEVEL, DEFAULT_APP_NAME, APP_VERSION,
        LOG_DIR_NAME, SETTINGS_FILENAME, BASE_URLS_FILENAME, DEFAULT_DOWNLOAD_DIR_NAME
    )
except ImportError as e:
    print(f"FATAL ERROR: Could not import required constants from config.py: {e}")
    # Define fallbacks for path calculation if config fails
    LOG_DIR_NAME = "logs"
    LOG_FORMAT = '%(asctime)s - %(levelname)s - [%(threadName)s:%(funcName)s] %(message)s'
    LOG_LEVEL = logging.INFO
    DEFAULT_APP_NAME = "Tender Scraper (Config Error)"
    APP_VERSION = "ERR"
    SETTINGS_FILENAME = "settings.json"
    BASE_URLS_FILENAME = "base_urls.csv"
    DEFAULT_DOWNLOAD_DIR_NAME = "Tender_Downloads"

# --- Set Absolute Paths based on Script Location ---
ABS_LOG_DIR = os.path.join(SCRIPT_DIR, LOG_DIR_NAME)
ABS_SETTINGS_FILE = os.path.join(SCRIPT_DIR, SETTINGS_FILENAME)
ABS_BASE_URLS_FILE = os.path.join(SCRIPT_DIR, BASE_URLS_FILENAME)
# Default download directory: use user's system Downloads folder by default
ABS_DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", DEFAULT_DOWNLOAD_DIR_NAME)
# Ensure the default directory exists
try:
    os.makedirs(ABS_DEFAULT_DOWNLOAD_DIR, exist_ok=True)
except Exception:
    # Fallback to script-local folder if creating in Downloads fails
    ABS_DEFAULT_DOWNLOAD_DIR = os.path.join(SCRIPT_DIR, DEFAULT_DOWNLOAD_DIR_NAME)
    os.makedirs(ABS_DEFAULT_DOWNLOAD_DIR, exist_ok=True)

# --- Early Logging Setup (Console Only) ---
def setup_logging():
    """Setup enhanced logging with better formatting and error handling."""
    try:
        # Create logs directory if it doesn't exist
        os.makedirs(ABS_LOG_DIR, exist_ok=True)

        def _cleanup_old_run_logs(prefix, keep_count=30):
            try:
                log_files = []
                for file_name in os.listdir(ABS_LOG_DIR):
                    if file_name.startswith(prefix) and file_name.endswith('.log'):
                        full_path = os.path.join(ABS_LOG_DIR, file_name)
                        log_files.append((full_path, os.path.getmtime(full_path)))

                log_files.sort(key=lambda x: x[1], reverse=True)
                for old_file, _mtime in log_files[keep_count:]:
                    try:
                        os.remove(old_file)
                    except Exception:
                        pass
            except Exception:
                pass

        run_log_file = os.path.join(
            ABS_LOG_DIR,
            f"cli_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )

        # Configure logging with both console and file output
        logging.basicConfig(
            level=LOG_LEVEL,
            format=LOG_FORMAT,
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(
                    run_log_file,
                    encoding='utf-8'
                )
            ],
            force=True
        )

        _cleanup_old_run_logs("cli_", keep_count=30)

        # Log system information
        logging.info(f"--- {DEFAULT_APP_NAME} CLI v{APP_VERSION} Starting ---")
        logging.info(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
        logging.info(f"Python: {sys.version}")
        logging.info(f"Script Directory: {SCRIPT_DIR}")
        logging.info(f"Working Directory: {os.getcwd()}")

        return True
    except Exception as log_setup_err:
        print(f"FATAL ERROR setting up logging: {log_setup_err}")
        # Fallback to basic console logging
        logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT, stream=sys.stdout)
        return False

setup_logging()

# --- Enhanced Package Availability Checks ---
REQUIRED_PACKAGES = {
    'selenium': 'selenium>=4.0.0',
    'pandas': 'pandas>=1.3.0',
    'openpyxl': 'openpyxl>=3.0.0',
    'requests': 'requests>=2.25.0',
    'pytesseract': 'pytesseract>=0.3.10',  # Added pytesseract to required packages
}

OPTIONAL_PACKAGES = {
    'undetected_chromedriver': 'undetected-chromedriver',
    'webdriver_manager': 'webdriver-manager'
}

def check_package_versions():
    """Check package availability and versions with detailed reporting."""
    missing_packages = []
    outdated_packages = []

    for package, requirement in REQUIRED_PACKAGES.items():
        try:
            imported_module = __import__(package)
            version = getattr(imported_module, '__version__', 'unknown')
            logging.info(f"[OK] {package} {version} is available")
        except ImportError:
            missing_packages.append((package, requirement))
            logging.error(f"[MISSING] {package} is not installed")

    # Check optional packages
    for package, requirement in OPTIONAL_PACKAGES.items():
        try:
            imported_module = __import__(package)
            version = getattr(imported_module, '__version__', 'unknown')
            logging.info(f"[OK] {package} {version} (optional) is available")
        except ImportError:
            logging.warning(f"[WARN] {package} (optional) is not installed")

    return missing_packages, outdated_packages

missing_packages, outdated_packages = check_package_versions()

if missing_packages:
    error_msg = "Missing required packages:\n\n"
    for package, requirement in missing_packages:
        error_msg += f"pip install {requirement}\n"

    if outdated_packages:
        error_msg += "\nOutdated packages (recommended to upgrade):\n"
        for package, requirement in outdated_packages:
            error_msg += f"pip install --upgrade {requirement}\n"

    logging.error(error_msg)
    print(error_msg)

    try:
        root_err = tk.Tk()
        root_err.withdraw()
        tkinter.messagebox.showerror(
            "Missing Dependencies",
            "Required packages are missing. Check console for details.\n\n" +
            "Install missing packages and restart the application."
        )
        root_err.destroy()
    except Exception as gui_err:
        logging.error(f"Could not show GUI error: {gui_err}")
    sys.exit(1)

# --- Import CLI Components ---
def import_cli_components():
    """Import CLI components with detailed error reporting."""
    try:
        logging.info("Importing CLI components...")

        # Import CLI components
        from cli_parser import CLIParser
        from cli_runner import CLIRunner

        logging.info("CLI components imported successfully")
        return CLIParser, CLIRunner

    except ImportError as e:
        logging.error(f"CLI import error: {e}", exc_info=True)
        error_message = f"Failed to import required CLI components.\n\nError: {str(e)}\n\nCheck that all files are present and Python path is correct."
        raise ImportError(error_message)
    except Exception as e:
        logging.error(f"Unexpected CLI import error: {e}", exc_info=True)
        error_message = f"Unexpected error during CLI import.\n\nError: {str(e)}\n\nCheck console output for details."
        raise ImportError(error_message)

try:
    CLIParser, CLIRunner = import_cli_components()
except ImportError as e:
    error_message = str(e)
    print(f"FATAL ERROR: {error_message}")
    try:
        root_err = tk.Tk()
        root_err.withdraw()
        tkinter.messagebox.showerror("CLI Import Error", error_message)
        root_err.destroy()
    except Exception as msg_err:
        logging.error(f"Could not display CLI error message: {msg_err}")
    sys.exit(1)

def show_interactive_banner():
    """Show interactive CLI banner with large, stylish ASCII art."""
    from config import APP_VERSION
    print(r"""
: "
########################################################################
#                                                                      #
# .______    __           ___        ______  __  ___                   #
# |   _  \  |  |         /   \      /      ||  |/  /                   #
# |  |_)  | |  |        /  ^  \    |  ,----'|  '  /                    #
# |   _  <  |  |       /  /_\  \   |  |     |    <                     #
# |  |_)  | |  `----. /  _____  \  |  `----.|  .  \                    #
# |______/  |_______|/__/     \__\  \______||__|\__\                   #
#                                                                      #
#  _______   ______   .______       _______      _______..___________. #
# |   ____| /  __  \  |   _  \     |   ____|    /       ||           | #
# |  |__   |  |  |  | |  |_)  |    |  |__      |   (----``---|  |----` #
# |   __|  |  |  |  | |      /     |   __|      \   \        |  |      #
# |  |     |  `--'  | |  |\  \----.|  |____ .----)   |       |  |      #
# |__|      \______/  | _| `._____||_______||_______/        |__|      #
#                                                                      #
########################################################################
"
""")

# --- CLI Mode Handler ---
def run_cli_mode():
    """Run application in CLI mode."""
    try:
        logging.info("Starting CLI mode...")

        # Check if any arguments were provided
        args = sys.argv[1:]  # Skip script name

        if not args:
            # Interactive mode - show banner and wait for commands
            show_interactive_banner()
            print("\nType 'help' for available commands, or 'exit' to quit.")
            print("Example: department --all")
            print("-" * 60)

            # Import CLI components
            parser = CLIParser()
            while True:
                try:
                    # Get user input
                    user_input = input("\nBlackForest> ").strip()
                    if not user_input:
                        continue

                    if user_input.lower() in ['exit', 'quit', 'q']:
                        print("Goodbye!")
                        break

                    if user_input.lower() in ['help', 'h', '?']:
                        print("\nAvailable commands:")
                        print("  department --all              - Scrape all departments")
                        print("  department --filter 'term'    - Scrape departments matching filter")
                        print("  urls                          - List available portals")
                        print("  status [--portal 'name']      - Show last scrape/export status")
                        print("  export [--portal 'name']      - Manual Excel export from latest run")
                        print("  help                          - Show this help")
                        print("  exit                          - Exit CLI mode")
                        continue

                    # Parse and execute command
                    try:
                        # Split input into arguments
                        cmd_args = user_input.split()
                        parsed_args = parser.parse_args(cmd_args)

                        # Execute command
                        runner = CLIRunner(parsed_args)

                        if parsed_args.command == 'urls':
                            runner.list_available_portals()
                        elif parsed_args.command == 'status':
                            runner.show_status()
                        elif parsed_args.command == 'export':
                            runner.export_latest()
                        elif parsed_args.command == 'department':
                            runner.run_department_scraping()
                        else:
                            print(f"Unknown command: {parsed_args.command}")

                    except SystemExit:
                        # argparse error, continue
                        pass
                    except Exception as cmd_err:
                        print(f"Command error: {cmd_err}")

                except KeyboardInterrupt:
                    print("\nGoodbye!")
                    break
                except EOFError:
                    print("\nGoodbye!")
                    break

        else:
            # Command mode - execute provided arguments
            from cli_runner import main as cli_main
            cli_main()

    except Exception as cli_err:
        logging.error(f"CLI mode error: {cli_err}", exc_info=True)
        print(f"CLI Error: {cli_err}")
        sys.exit(1)

# --- Main Execution Block ---
if __name__ == "__main__":
    run_cli_mode()
