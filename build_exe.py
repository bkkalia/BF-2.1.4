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
            print(f"ERROR: main.py not found in {launcher_dir}")
            print("Please ensure all files are in the same directory as the launcher.")
            input("Press Enter to exit...")
            sys.exit(1)

        # Prepare command to run main.py
        python_exe = sys.executable  # Use same Python that launched this script
        cmd = [python_exe, str(main_script)] + sys.argv[1:]

print("Black Forest Tender Scraper")
print(f"Launcher directory: {launcher_dir}")
        print(f"Command: {' '.join(cmd)}")
        print("-" * 50)

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

    print("✅ Created launcher script: blackforest_launcher.py")

def build_hybrid():
    """Build hybrid launcher EXE + Python files"""
    print("🔨 Building Hybrid Launcher (Option 4)")
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
        shutil.rmtree(build_dir)

    spec_file = script_dir / 'BlackForest_Launcher.spec'
    if spec_file.exists():
        spec_file.unlink()

    # Step 1: Create launcher script
    print("\\n1. Creating launcher script...")
    create_launcher()

    # Step 2: Build small launcher EXE
    print("\\n2. Building launcher EXE...")
    pyinstaller_cmd = [
        sys.executable, '-m', 'PyInstaller',  # Use Python module
        '--name=BlackForest_Launcher',
        '--onefile',  # Small single EXE
        '--console',  # Console mode for CLI
        '--clean',    # Clean cache
        '--noconfirm', # Don't ask for confirmation
        'blackforest_launcher.py'
    ]

    try:
        result = subprocess.run(pyinstaller_cmd, check=True, capture_output=True, text=True)
        print("✅ Launcher EXE built successfully")
        if result.stdout:
            print(f"Build output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error building launcher: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False

    # Step 3: Copy launcher to dist
    launcher_exe = script_dir / 'dist' / 'BlackForest_Launcher.exe'
    if launcher_exe.exists():
        final_exe = dist_dir / 'BlackForest.exe'
        shutil.copy2(launcher_exe, final_exe)
        print(f"✅ Copied launcher to: {final_exe}")

    # Step 4: Copy all Python files and resources
    print("\\n3. Copying application files...")

    files_to_copy = [
        # Core files
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
            print(f"  📄 {file}")

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
            print(f"  📁 {dir_name}/ ({file_count} files)")

    # Step 5: Create README for distribution
    create_distribution_readme(dist_dir)

    # Step 6: Clean up temporary files
    print("\\n4. Cleaning up...")
    if (script_dir / 'blackforest_launcher.py').exists():
        (script_dir / 'blackforest_launcher.py').unlink()

    if (script_dir / 'BlackForest_Launcher.spec').exists():
        (script_dir / 'BlackForest_Launcher.spec').unlink()

    # Remove PyInstaller temp directories
    if build_dir.exists():
        shutil.rmtree(build_dir)

    if (script_dir / 'dist' / 'BlackForest_Launcher.exe').exists():
        (script_dir / 'dist' / 'BlackForest_Launcher.exe').unlink()

    print("\\n" + "=" * 50)
    print("🎉 HYBRID BUILD COMPLETED SUCCESSFULLY!")
    print("=" * 50)
    print(f"📁 Distribution directory: {dist_dir}")
    print(f"📊 Files copied: {copied_files}")
    print(f"💾 Estimated size: {get_dir_size(dist_dir):.1f} MB")
    print("\\n🚀 Usage:")
    print("  BlackForest.exe department --all")
    print("  BlackForest.exe urls")
    print("  BlackForest.exe --url 'etenders' department --all")
    print("\\n📋 For Windows Task Scheduler:")
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

    print("  📄 README.md (distribution guide)")

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
    print("🔨 Building Portable Directory Version")
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
        print("✅ Portable build completed")

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
            print(f"📁 Portable directory: {final_dir}")
            print(f"💾 Size: {size_mb:.1f} MB")
            print("\\n🚀 Usage:")
            print("  BlackForest_Portable\\BlackForest.exe department --all")

    except subprocess.CalledProcessError as e:
        print(f"❌ Error building portable: {e}")

def main():
    """Main build function"""
    if len(sys.argv) > 1:
        if sys.argv[1] == 'portable':
            build_portable()
        elif sys.argv[1] == 'hybrid':
            build_hybrid()
        else:
            print("Usage: python build_exe.py [hybrid|portable]")
            print("  hybrid  - Small EXE launcher + Python files (recommended)")
            print("  portable - Self-contained directory")
    else:
        # Default to hybrid build
        build_hybrid()

if __name__ == "__main__":
    main()
