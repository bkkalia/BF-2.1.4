# Inno Setup Guide for Black Forest Tender Scraper

## Overview

This guide explains how to create a professional Windows installer for the Black Forest Tender Scraper using Inno Setup. The installer will include the hybrid distribution package with both CLI and GUI functionality.

## Prerequisites

### 1. Download and Install Inno Setup
1. **Download**: Visit https://jrsoftware.org/isinfo.php
2. **Install**: Run the installer and follow the default options
3. **Verify**: Inno Setup Compiler should be available in Start Menu

### 2. Prepare Distribution Package
Ensure you have built the hybrid distribution package:
```bash
# Build the hybrid package (if not already done)
python build_exe.py hybrid

# Verify dist directory contents
dir dist\
```

## Using the Inno Setup Script

### Method 1: Using Inno Setup Compiler GUI

1. **Launch Inno Setup Compiler**
   - Open from Start Menu or desktop shortcut

2. **Open the Script**
   - File → Open
   - Navigate to your project directory
   - Select `setup.iss`

3. **Compile the Installer**
   - Click the **Compile** button (green play icon)
   - Or press **F9**

4. **Find the Output**
   - The installer will be created in `installer_output\` directory
   - Filename: `BlackForest_Tender_Scraper_2.1.4_Setup.exe`

### Method 2: Command Line Compilation

```bash
# Navigate to project directory
cd "d:\Dev84\BF 2.1.4"

# Compile using command line
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" setup.iss

# Or if Inno Setup is in PATH
iscc setup.iss
```

## What the Installer Does

### Installation Features

#### ✅ Files Included:
- **BlackForest.exe** - Small launcher executable
- **All Python files** - Complete application code
- **Configuration files** - base_urls.csv, settings.json
- **Documentation** - CLI_HELP.md, GUI_HELP.md, README.md
- **Batch files** - run_hp_tenders.bat for Task Scheduler
- **Modules** - scraper/, gui/, resources/ directories

#### ✅ Shortcuts Created:
- **Start Menu**: Black Forest Tender Scraper group
  - Black Forest Tender Scraper (main app)
  - Black Forest Tender Scraper CLI (with --help)
  - GUI Help and CLI Help documents
  - Uninstall option

- **Desktop Icon** (optional during installation)
- **Quick Launch** (optional during installation)

#### ✅ Directories Created:
- **Program Files**: Main application directory
- **Tender_Downloads**: Default output directory
- **logs**: Application logs directory
- **config**: User configuration directory

#### ✅ Python Integration:
- **Automatic detection** of Python 3.7+ installation
- **Dependency installation** attempt during setup
- **Clear error messages** if Python is missing

### Post-Installation

#### Automatic Setup:
- Creates necessary directories with proper permissions
- Attempts to install Python dependencies automatically
- Sets up file associations and shortcuts

#### Manual Setup (if needed):
```bash
# Navigate to installation directory
cd "C:\Program Files\Black Forest Tender Scraper"

# Install dependencies manually
pip install -r requirements.txt
```

## Customizing the Installer

### Basic Customizations

#### 1. Change Application Details:
```iss
#define MyAppName "Your Custom App Name"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Your Company"
#define MyAppURL "https://your-website.com"
```

#### 2. Change Installation Directory:
```iss
DefaultDirName={pf}\YourCustomDirectory
```

#### 3. Change Output Filename:
```iss
OutputBaseFilename=YourCustomInstallerName
```

### Advanced Customizations

#### 1. Add Custom Icons:
```iss
SetupIconFile=your_icon.ico
```

#### 2. Add License File:
```iss
LicenseFile=YOUR_LICENSE.txt
```

#### 3. Modify File Associations:
```iss
[Registry]
Root: HKCR; Subkey: ".csv"; ValueType: string; ValueName: ""; ValueData: "YourApp.CSV"; Flags: uninsdeletevalue; Tasks: associatefiles
```

#### 4. Add Custom Installation Steps:
```iss
[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Your custom post-installation code
    MsgBox('Installation completed successfully!', mbInformation, MB_OK);
  end;
end;
```

## Testing the Installer

### 1. Test Installation
```bash
# Run the installer
BlackForest_Tender_Scraper_2.1.4_Setup.exe

# Follow installation wizard
# Choose installation options
# Complete installation
```

### 2. Test Application
```bash
# Navigate to installation directory
cd "C:\Program Files\Black Forest Tender Scraper"

# Test GUI mode
BlackForest.exe

# Test CLI mode
BlackForest.exe --help

# Test department scraping
BlackForest.exe department --all --dry-run
```

### 3. Test Shortcuts
- Check Start Menu shortcuts
- Test desktop icon (if created)
- Verify uninstaller works

### 4. Test Task Scheduler Integration
```batch
# Test the batch file
"C:\Program Files\Black Forest Tender Scraper\run_hp_tenders.bat"
```

## Distribution

### Creating Distribution Package

1. **Build the hybrid package:**
   ```bash
   python build_exe.py hybrid
   ```

2. **Compile the installer:**
   ```bash
   iscc setup.iss
   ```

3. **Package for distribution:**
   ```
   installer_output/
   ├── BlackForest_Tender_Scraper_2.1.4_Setup.exe  # Main installer
   ├── CLI_HELP.md                                 # CLI documentation
   ├── GUI_HELP.md                                 # GUI documentation
   └── README.md                                   # Installation guide
   ```

### Distribution Checklist

#### ✅ Before Distribution:
- [ ] Test installer on clean Windows system
- [ ] Verify all shortcuts work
- [ ] Test CLI and GUI modes
- [ ] Confirm Python dependency installation
- [ ] Test Task Scheduler integration
- [ ] Verify uninstaller works properly

#### ✅ Documentation:
- [ ] Include CLI_HELP.md
- [ ] Include GUI_HELP.md
- [ ] Include installation instructions
- [ ] Include system requirements

#### ✅ File Structure:
```
Your_Distribution_Package/
├── BlackForest_Tender_Scraper_2.1.4_Setup.exe
├── CLI_HELP.md
├── GUI_HELP.md
├── README.md
└── System_Requirements.txt
```

## Troubleshooting

### Common Issues

#### 1. "Inno Setup not found"
**Solution:**
```bash
# Download from https://jrsoftware.org/isinfo.php
# Install Inno Setup
# Add to PATH or use full path
```

#### 2. "File not found" errors
**Solution:**
- Ensure `dist\` directory exists with all files
- Check file paths in `setup.iss`
- Verify all source files exist

#### 3. "Python not detected"
**Solution:**
- Modify the Python detection code in `setup.iss`
- Update registry keys for different Python versions
- Add fallback detection methods

#### 4. Compilation errors
**Solution:**
- Check Inno Setup log for specific errors
- Verify file permissions
- Ensure all referenced files exist

### Advanced Troubleshooting

#### Custom Python Detection:
```iss
[Code]
function IsPythonInstalled(): Boolean;
var
  PythonPath: String;
begin
  // Try to find python.exe in PATH
  if Exec('where', 'python', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := True;
  end
  else
  begin
    // Check common installation paths
    PythonPath := ExpandConstant('{pf}\Python*\python.exe');
    Result := FileExists(PythonPath);
  end;
end;
```

#### Debug Compilation:
```bash
# Enable verbose output
iscc /V setup.iss

# Check for specific errors
iscc /O- setup.iss
```

## Alternative Inno Setup Tools

### 1. Inno Setup Studio
- Visual IDE for Inno Setup scripts
- Drag-and-drop interface
- Advanced customization options

### 2. ISTool
- GUI tool for creating Inno Setup scripts
- Template-based script generation
- Built-in file browser

### 3. Inno Script Studio
- Modern IDE for Inno Setup
- Syntax highlighting
- Integrated compiler

## Best Practices

### 1. Version Management
- Update version numbers in both `setup.iss` and application
- Use semantic versioning (Major.Minor.Patch)
- Keep version numbers synchronized

### 2. File Organization
- Use consistent directory structure
- Include all necessary dependencies
- Separate user data from program files

### 3. User Experience
- Provide clear installation instructions
- Include uninstaller
- Offer optional components
- Show progress during installation

### 4. Security
- Sign the installer with code signing certificate
- Verify file integrity
- Include license agreement
- Follow Windows installer guidelines

## Support

### Getting Help
- **Inno Setup Documentation**: https://jrsoftware.org/ishelp/
- **Community Forums**: https://jrsoftware.org/forums.php
- **Script Examples**: https://jrsoftware.org/isfaq.php

### Common Resources
- **Pascal Scripting**: For advanced customization
- **Preprocessor**: For conditional compilation
- **Command Line**: For automated builds

---

**Last Updated**: September 22, 2025
**Inno Setup Version**: 6.x recommended
**Compatibility**: Windows 7 SP1 and later
