#!/usr/bin/env python3
"""
Black Forest Tender Scraper - Build Script
Creates hybrid launcher EXE + Python files for optimal distribution
"""

import os
import subprocess
import shutil
import sys
from pathlib import Path

# Set encoding to handle Unicode
os.environ['PYTHONIOENCODING'] = 'utf-8'

def create_launcher():
    """Create the launcher script that will be converted to EXE"""
    launcher_code = '''#!/usr/bin/env python3
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
            print("ERROR: main.py not found in " + str(launcher_dir))
            print("Please ensure all files are in the same directory as the launcher.")
            input("Press Enter to exit...")
            sys.exit(1)

        # Prepare command to run main.py
        python_exe = 'python'  # Use Python interpreter
        cmd = [python_exe, str(main_script)] + sys.argv[1:]

        # Run the main application
        result = subprocess.run(cmd)

        # Exit with the same code as the main application
        sys.exit(result.returncode)

    except KeyboardInterrupt:
        print("\\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == '__main__':
    main()
'''

    with open('blackforest_launcher.py', 'w', encoding='utf-8') as f:
        f.write(launcher_code)

    print("Created launcher script: blackforest_launcher.py")

def build_hybrid():
    """Build hybrid launcher EXE + Python files"""
    print("Building Hybrid Windowed GUI Application")
    print("=" * 50)

    # Ensure we're in the correct directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # Create dist directory
    dist_dir = script_dir / 'dist'
    dist_dir.mkdir(exist_ok=True)

    # Clean previous builds
    build_dir = script_dir / 'build'
    if build_dir.exists():
        # Retry cleanup in case files are locked
        import time
        max_retries = 5
        for attempt in range(max_retries):
            try:
                shutil.rmtree(build_dir)
                break
            except PermissionError as e:
                if attempt < max_retries - 1:
                    print(f"Build directory locked, retrying cleanup in 2 seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(2)
                else:
                    print(f"Failed to clean build directory after {max_retries} attempts: {e}")
                    return False

    spec_file = script_dir / 'BlackForest.spec'
    if spec_file.exists():
        spec_file.unlink()

    # Step 1: Create small launcher script
    print("\\n1. Creating launcher script...")
    create_launcher()

    # Step 2: Build small launcher EXE (not the main app)
    print("\\n2. Building small launcher EXE...")
    launcher_cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=BlackForest',
        '--onefile',  # Single small EXE
        '--windowed',  # Windowed mode - no console for launcher
        '--clean',
        '--noconfirm',
        'blackforest_launcher.py'  # Build the launcher, not main.py
    ]

    try:
        subprocess.run(launcher_cmd, check=True)
        print("Small launcher EXE built successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error building launcher: {e}")
        return False

    # Step 3: Copy built launcher EXE to dist
    launcher_exe = script_dir / 'dist' / 'BlackForest.exe'
    if launcher_exe.exists():
        final_exe = dist_dir / 'BlackForest.exe'
        # Retry copy operation in case file is locked by another process
        import time
        max_retries = 5
        for attempt in range(max_retries):
            try:
                shutil.copy2(launcher_exe, final_exe)
                print(f"Copied launcher to: {final_exe}")
                break
            except PermissionError as e:
                if attempt < max_retries - 1:
                    print(f"File locked, retrying in 2 seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(2)
                else:
                    print(f"Failed to copy after {max_retries} attempts: {e}")
                    return False

    # Step 3: Copy additional Python files and resources (for CLI functionality)
    print("\\n2. Copying additional application files...")

    files_to_copy = [
        # Core files (for CLI and additional functionality)
        'main.py',
        'cli_parser.py',
        'cli_runner.py',
        'config.py',
        'app_settings.py',
        'utils.py',

        # Configuration files
        'base_urls.csv',
        'settings.json',

        # Documentation
        'CLI_HELP.md',
        'README.md',
        'requirements.txt',

        # Batch files
        'run_hp_tenders.bat',
    ]

    # Directories to copy
    dirs_to_copy = [
        'scraper',
        'gui',
        'resources',
    ]

    copied_files = 0

    # Copy individual files
    for file in files_to_copy:
        src = script_dir / file
        if src.exists():
            shutil.copy2(src, dist_dir / file)
            copied_files += 1
            print(f"  {file}")

    # Copy directories
    for dir_name in dirs_to_copy:
        src_dir = script_dir / dir_name
        if src_dir.exists():
            dst_dir = dist_dir / dir_name
            if dst_dir.exists():
                shutil.rmtree(dst_dir)
            shutil.copytree(src_dir, dst_dir)
            # Count files in directory
            file_count = sum(1 for _ in dst_dir.rglob('*') if _.is_file())
            copied_files += file_count
            print(f"  {dir_name}/ ({file_count} files)")

    # Step 4: Create README for distribution
    create_distribution_readme(dist_dir)

    # Step 5: Clean up temporary files
    print("\\n3. Cleaning up...")
    # Remove PyInstaller temp directories
    if build_dir.exists():
        shutil.rmtree(build_dir)

    if (script_dir / 'dist' / 'BlackForest.exe').exists():
        (script_dir / 'dist' / 'BlackForest.exe').unlink()

    if (script_dir / 'BlackForest.spec').exists():
        (script_dir / 'BlackForest.spec').unlink()

    print("\\n" + "=" * 50)
    print("WINDOWED GUI BUILD COMPLETED SUCCESSFULLY!")
    print("=" * 50)
    print(f"Distribution directory: {dist_dir}")
    print(f"Files copied: {copied_files}")
    print(f"Estimated size: {get_dir_size(dist_dir):.1f} MB")
    print("\\nUsage:")
    print("  Double-click BlackForest.exe (GUI mode)")
    print("  BlackForest.exe department --all (CLI mode)")
    print("  BlackForest.exe urls (CLI mode)")
    print("\\nFor Windows Task Scheduler:")
    print("  Use BlackForest.exe in batch files or scheduled tasks")

    return True

def create_distribution_readme(dist_dir):
    """Create README for the distribution package"""
    readme_content = '''# Black Forest Tender Scraper

## Installation
1. Extract all files to a folder (e.g., C:\\Program Files\\Black Forest)
2. Ensure Python 3.7+ is installed on your system
3. Install required packages: pip install -r requirements.txt

## Usage

### GUI Mode (Default)
Double-click `BlackForest.exe` or run:
```
BlackForest.exe
```

### CLI Mode
```
# Scrape all departments from HP Tenders
BlackForest.exe department --all

# List available portals
BlackForest.exe urls

# Scrape from specific portal
BlackForest.exe --url "etenders" department --all

# With custom output
BlackForest.exe department --all --output "C:\\Tenders"

# With logging
BlackForest.exe department --all --log "C:\\Logs\\tenders.log"
```

### Windows Task Scheduler
Create a batch file with:
```
@echo off
cd /d "C:\\Path\\To\\BlackForest"
BlackForest.exe department --all --output "C:\\Tenders\\HP" --log "C:\\Logs\\tenders.log"
```

## Requirements
- Python 3.7 or higher
- Google Chrome browser
- Internet connection

## File Structure
```
BlackForest/
├── BlackForest.exe          # Launcher executable
├── main.py                  # Main application
├── cli_parser.py           # CLI argument parser
├── cli_runner.py           # CLI execution logic
├── base_urls.csv           # Portal configurations
├── settings.json           # Application settings
├── scraper/                # Scraping modules
├── gui/                    # GUI modules
├── CLI_HELP.md            # Detailed help
└── run_hp_tenders.bat     # Windows batch file
```

## Support
Run `BlackForest.exe --help` for command-line options
See `CLI_HELP.md` for detailed usage instructions
'''

    readme_file = dist_dir / 'README.md'
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print("  README.md (distribution guide)")

def get_dir_size(path):
    """Get directory size in MB"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            total_size += os.path.getsize(filepath)
    return total_size / (1024 * 1024)

def build_portable():
    """Build portable directory version (alternative)"""
    print("Building Portable Directory Version")
    print("=" * 50)

    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    dist_dir = script_dir / 'dist_portable'
    dist_dir.mkdir(exist_ok=True)

    # Build with --onedir for portable directory
    pyinstaller_cmd = [
        'pyinstaller',
        '--name=BlackForest',
        '--onedir',  # Directory instead of single file
        '--windowed',
        '--add-data=base_urls.csv;.',
        '--add-data=settings.json;.',
        '--hidden-import=cli_parser',
        '--hidden-import=cli_runner',
        '--hidden-import=scraper.logic',
        '--hidden-import=scraper.driver_manager',
        '--hidden-import=app_settings',
        'main.py'
    ]

    try:
        subprocess.run(pyinstaller_cmd, check=True)
        print("Portable build completed")

        # Copy additional files
        portable_dir = script_dir / 'dist' / 'BlackForest'
        if portable_dir.exists():
            # Copy batch file and documentation
            shutil.copy2('run_hp_tenders.bat', portable_dir)
            shutil.copy2('CLI_HELP.md', portable_dir)

            final_dir = dist_dir / 'BlackForest_Portable'
            if final_dir.exists():
                shutil.rmtree(final_dir)
            shutil.copytree(portable_dir, final_dir)

            size_mb = get_dir_size(final_dir)
            print(f"Portable directory: {final_dir}")
            print(f"Size: {size_mb:.1f} MB")
            print("\\nUsage:")
            print("  BlackForest_Portable\\BlackForest.exe department --all")

    except subprocess.CalledProcessError as e:
        print(f"Error building portable: {e}")

def build_gui():
    """Build GUI-only EXE (--windowed, no console)"""
    print("Building GUI EXE (--windowed)")
    print("=" * 50)

    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    dist_dir = script_dir / 'dist_gui'
    dist_dir.mkdir(exist_ok=True)

    # Clean previous builds
    build_dir = script_dir / 'build'
    if build_dir.exists():
        shutil.rmtree(build_dir)

    spec_file = script_dir / 'BlackForest_GUI.spec'
    if spec_file.exists():
        spec_file.unlink()

    # Build GUI EXE
    pyinstaller_cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=BlackForest_GUI',
        '--onefile',
        '--windowed',  # No console window
        '--clean',
        '--noconfirm',
        '--add-data=base_urls.csv;.',
        '--add-data=settings.json;.',
        '--hidden-import=cli_parser',
        '--hidden-import=cli_runner',
        '--hidden-import=scraper.logic',
        '--hidden-import=scraper.driver_manager',
        '--hidden-import=scraper.actions',
        '--hidden-import=scraper.captcha_handler',
        '--hidden-import=scraper.ocr_helper',
        '--hidden-import=scraper.sound_helper',
        '--hidden-import=scraper.webdriver_manager',
        '--hidden-import=gui.main_window',
        '--hidden-import=gui.tab_department',
        '--hidden-import=gui.tab_id_search',
        '--hidden-import=gui.tab_url_process',
        '--hidden-import=gui.tab_settings',
        '--hidden-import=gui.tab_help',
        '--hidden-import=gui.global_panel',
        '--hidden-import=gui.gui_utils',
        '--hidden-import=app_settings',
        '--hidden-import=config',
        '--hidden-import=utils',
        'main.py'
    ]

    try:
        subprocess.run(pyinstaller_cmd, check=True)
        print("GUI EXE built successfully")

        # Copy to dist_gui
        src_exe = script_dir / 'dist' / 'BlackForest_GUI.exe'
        dst_exe = dist_dir / 'BlackForest_GUI.exe'
        if src_exe.exists():
            shutil.copy2(src_exe, dst_exe)
            size_mb = src_exe.stat().st_size / (1024 * 1024)
            print(f"GUI EXE: {dst_exe}")
            print(f"Size: {size_mb:.1f} MB")
            print("\nUsage:")
            print("  Double-click BlackForest_GUI.exe (GUI mode)")
        else:
            print("Error: GUI EXE not found after build")

    except subprocess.CalledProcessError as e:
        print(f"Error building GUI EXE: {e}")

    # Cleanup
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if (script_dir / 'dist').exists():
        shutil.rmtree(script_dir / 'dist')
    if spec_file.exists():
        spec_file.unlink()

def build_cli():
    """Build CLI-only EXE (--console, shows console)"""
    print("Building CLI EXE (--console)")
    print("=" * 50)

    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    dist_dir = script_dir / 'dist_cli'
    dist_dir.mkdir(exist_ok=True)

    # Clean previous builds
    build_dir = script_dir / 'build'
    if build_dir.exists():
        shutil.rmtree(build_dir)

    spec_file = script_dir / 'BlackForest_CLI.spec'
    if spec_file.exists():
        spec_file.unlink()

    # Build CLI EXE
    pyinstaller_cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=BlackForest_CLI',
        '--onefile',
        '--console',  # Show console window
        '--clean',
        '--noconfirm',
        '--add-data=base_urls.csv;.',
        '--add-data=settings.json;.',
        '--hidden-import=cli_parser',
        '--hidden-import=cli_runner',
        '--hidden-import=scraper.logic',
        '--hidden-import=scraper.driver_manager',
        '--hidden-import=scraper.actions',
        '--hidden-import=scraper.captcha_handler',
        '--hidden-import=scraper.ocr_helper',
        '--hidden-import=scraper.sound_helper',
        '--hidden-import=scraper.webdriver_manager',
        '--hidden-import=gui.main_window',
        '--hidden-import=gui.tab_department',
        '--hidden-import=gui.tab_id_search',
        '--hidden-import=gui.tab_url_process',
        '--hidden-import=gui.tab_settings',
        '--hidden-import=gui.tab_help',
        '--hidden-import=gui.global_panel',
        '--hidden-import=gui.gui_utils',
        '--hidden-import=app_settings',
        '--hidden-import=config',
        '--hidden-import=utils',
        'main.py'
    ]

    try:
        subprocess.run(pyinstaller_cmd, check=True)
        print("CLI EXE built successfully")

        # Copy to dist_cli
        src_exe = script_dir / 'dist' / 'BlackForest_CLI.exe'
        dst_exe = dist_dir / 'BlackForest_CLI.exe'
        if src_exe.exists():
            shutil.copy2(src_exe, dst_exe)
            size_mb = src_exe.stat().st_size / (1024 * 1024)
            print(f"CLI EXE: {dst_exe}")
            print(f"Size: {size_mb:.1f} MB")
            print("\nUsage:")
            print("  BlackForest_CLI.exe department --all")
            print("  BlackForest_CLI.exe urls")
        else:
            print("Error: CLI EXE not found after build")

    except subprocess.CalledProcessError as e:
        print(f"Error building CLI EXE: {e}")

    # Cleanup
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if (script_dir / 'dist').exists():
        shutil.rmtree(script_dir / 'dist')
    if spec_file.exists():
        spec_file.unlink()

def build_separate():
    """Build both GUI and CLI EXEs separately"""
    print("Building Separate GUI and CLI EXEs")
    print("=" * 50)

    build_gui()
    print()
    build_cli()

    print("\n" + "=" * 50)
    print("SEPARATE BUILDS COMPLETED!")
    print("=" * 50)
    print("Files created:")
    gui_exe = Path(__file__).parent / 'dist_gui' / 'BlackForest_GUI.exe'
    cli_exe = Path(__file__).parent / 'dist_cli' / 'BlackForest_CLI.exe'
    if gui_exe.exists():
        size_mb = gui_exe.stat().st_size / (1024 * 1024)
        print(f"  {gui_exe} ({size_mb:.1f} MB) - GUI mode")
    if cli_exe.exists():
        size_mb = cli_exe.stat().st_size / (1024 * 1024)
        print(f"  {cli_exe} ({size_mb:.1f} MB) - CLI mode")
    print("\nUsage:")
    print("  GUI: Double-click BlackForest_GUI.exe")
    print("  CLI: BlackForest_CLI.exe department --all")

def main():
    """Main build function"""
    if len(sys.argv) > 1:
        if sys.argv[1] == 'portable':
            build_portable()
        elif sys.argv[1] == 'hybrid':
            build_hybrid()
        elif sys.argv[1] == 'gui':
            build_gui()
        elif sys.argv[1] == 'cli':
            build_cli()
        elif sys.argv[1] == 'separate':
            build_separate()
        else:
            print("Usage: python build_exe.py [hybrid|portable|gui|cli|separate]")
            print("  hybrid   - Small EXE launcher + Python files (recommended)")
            print("  portable - Self-contained directory")
            print("  gui      - GUI-only EXE (--windowed)")
            print("  cli      - CLI-only EXE (--console)")
            print("  separate - Both GUI and CLI EXEs")
    else:
        # Default to hybrid build
        build_hybrid()

if __name__ == "__main__":
    main()
