#!/usr/bin/env python3
"""
Black Forest Tender Scraper Launcher
Small EXE that launches the main Python application
"""

import sys
import os
import subprocess
from pathlib import Path

def main():
    """Launch the main application with arguments"""
    try:
        # Get the directory where the launcher EXE is located
        if getattr(sys, 'frozen', False):
            # Running as compiled EXE
            launcher_dir = Path(sys.executable).parent
        else:
            # Running as script
            launcher_dir = Path(__file__).parent

        # Change to launcher directory
        os.chdir(launcher_dir)

        # Check if main.py exists
        main_script = launcher_dir / 'main.py'
        if not main_script.exists():
            print(f"ERROR: main.py not found in {launcher_dir}")
            print("Please ensure all files are in the same directory as the launcher.")
            input("Press Enter to exit...")
            sys.exit(1)

        # Prepare command to run main.py
        python_exe = sys.executable  # Use same Python that launched this script
        cmd = [python_exe, str(main_script)] + sys.argv[1:]

        print("Black Forest Tender Scraper"        print(f"Launcher directory: {launcher_dir}")
        print(f"Command: {' '.join(cmd)}")
        print("-" * 50)

        # Run the main application
        result = subprocess.run(cmd)

        # Exit with the same code as the main application
        sys.exit(result.returncode)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == '__main__':
    main()
