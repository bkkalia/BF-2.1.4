import os
import subprocess
import shutil
import sys
# git test
def build_exe():
    """Build executable using PyInstaller"""
    print("Starting build process...")
    
    # Ensure we're in the correct directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Create dist directory if it doesn't exist
    if not os.path.exists('dist'):
        os.makedirs('dist')
    
    # Clean previous builds
    if os.path.exists('build'):
        shutil.rmtree('build')
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    if os.path.exists('BlackForest.spec'):
        os.remove('BlackForest.spec')
    
    # Define PyInstaller command
    pyinstaller_command = [
        'pyinstaller',
        '--name=BlackForest',
        '--onefile',
        '--windowed',
        '--icon=resources/app_icon.ico',  # You'll need to create this
        '--add-data=base_urls.csv;.',
        '--hidden-import=PIL._tkinter_finder',
        '--hidden-import=selenium',
        '--hidden-import=undetected_chromedriver',
        '--hidden-import=PyPDF2',
        '--hidden-import=pandas',
        '--hidden-import=pytesseract',
        'main.py'
    ]
    
    # Run PyInstaller
    try:
        subprocess.run(pyinstaller_command, check=True)
        print("\nBuild completed successfully!")
        
        # Copy necessary files to dist
        files_to_copy = [
            'base_urls.csv',
            'settings.json',
            'README.md',
            'requirements.txt'
        ]
        
        for file in files_to_copy:
            if os.path.exists(file):
                shutil.copy2(file, f'dist/{file}')
                print(f"Copied {file} to dist folder")
        
        print("\nExecutable created at: dist/BlackForest.exe")
        print("\nMake sure to:")
        print("1. Install Tesseract OCR on the target system")
        print("2. Have Chrome browser installed")
        print("3. Copy the entire 'dist' folder to use the application")
        
    except subprocess.CalledProcessError as e:
        print(f"Error during build: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_exe()
