; Inno Setup Script for Black Forest Tender Scraper
; This script creates a complete installer for the hybrid distribution package

#define MyAppName "Black Forest Tender Scraper"
#define MyAppVersion "2.1.4"
#define MyAppPublisher "Cloud84"
#define MyAppURL "https://github.com/your-repo/blackforest"
#define MyAppExeName "BlackForest.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{12345678-1234-1234-ABCD-123456789ABC}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={pf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE.txt
OutputDir=installer_output
OutputBaseFilename=BlackForest_Tender_Scraper_{#MyAppVersion}_Setup
SetupIconFile=resources\app_icon.ico
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Core executable and Python files
Source: "dist\BlackForest.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\main.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\cli_parser.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\cli_runner.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\config.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\app_settings.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\utils.py"; DestDir: "{app}"; Flags: ignoreversion

; Configuration files
Source: "dist\base_urls.csv"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\settings.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion

; Documentation
Source: "dist\CLI_HELP.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\GUI_HELP.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\README.md"; DestDir: "{app}"; Flags: ignoreversion

; Batch files
Source: "dist\run_hp_tenders.bat"; DestDir: "{app}"; Flags: ignoreversion

; GUI modules
Source: "dist\gui\*"; DestDir: "{app}\gui"; Flags: ignoreversion recursesubdirs

; Scraper modules
Source: "dist\scraper\*"; DestDir: "{app}\scraper"; Flags: ignoreversion recursesubdirs

; Resources
Source: "dist\resources\*"; DestDir: "{app}\resources"; Flags: ignoreversion recursesubdirs

; Additional documentation files (if they exist)
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\Tender_Downloads"; Permissions: users-modify
Name: "{app}\logs"; Permissions: users-modify
Name: "{app}\config"; Permissions: users-modify

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\{#MyAppName} CLI"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--help"; WorkingDir: "{app}"
Name: "{group}\{#MyAppName} GUI Help"; Filename: "{app}\GUI_HELP.md"; WorkingDir: "{app}"
Name: "{group}\{#MyAppName} CLI Help"; Filename: "{app}\CLI_HELP.md"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  PythonInstalled: Boolean;
  PythonVersion: String;

function InitializeSetup(): Boolean;
begin
  // Check for Python installation
  PythonInstalled := RegKeyExists(HKLM, 'SOFTWARE\Python\PythonCore\3.7') or
                     RegKeyExists(HKLM, 'SOFTWARE\Python\PythonCore\3.8') or
                     RegKeyExists(HKLM, 'SOFTWARE\Python\PythonCore\3.9') or
                     RegKeyExists(HKLM, 'SOFTWARE\Python\PythonCore\3.10') or
                     RegKeyExists(HKLM, 'SOFTWARE\Python\PythonCore\3.11') or
                     RegKeyExists(HKLM, 'SOFTWARE\Python\PythonCore\3.12') or
                     RegKeyExists(HKLM, 'SOFTWARE\Python\PythonCore\3.13');

  if not PythonInstalled then
  begin
    MsgBox('Python 3.7 or higher is required to run this application.' + #13#10 +
           'Please install Python from https://python.org before continuing.' + #13#10 +
           'Make sure to check "Add Python to PATH" during installation.',
           mbError, MB_OK);
    Result := False;
  end
  else
    Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Create Tender_Downloads directory if it doesn't exist
    if not DirExists(ExpandConstant('{app}\Tender_Downloads')) then
      CreateDir(ExpandConstant('{app}\Tender_Downloads'));

    // Create logs directory if it doesn't exist
    if not DirExists(ExpandConstant('{app}\logs')) then
      CreateDir(ExpandConstant('{app}\logs'));

    // Optional: Try to install Python dependencies
    if Exec(ExpandConstant('{cmd}'), '/C "cd /d "{app}" && python -m pip install -r requirements.txt --quiet"', '',
            SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    begin
      if ResultCode = 0 then
        Log('Python dependencies installed successfully')
      else
        Log('Failed to install Python dependencies automatically');
    end;
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}\Tender_Downloads"
Type: filesandordirs; Name: "{app}\logs"
Type: files; Name: "{app}\settings.json"

[Messages]
SetupAppTitle={#MyAppName} Setup
SetupWindowTitle={#MyAppName} {#MyAppVersion} Setup
ConfirmUninstall=Are you sure you want to completely remove {#MyAppName} and all of its components?
UninstallStatusLabel=Removing {#MyAppName} from your computer...
UninstalledAll={#MyAppName} has been successfully removed from your computer.

[CustomMessages]
DependenciesNote=Python Dependencies%N%NThis application requires Python packages to be installed. The installer will attempt to install them automatically.%N%NIf the automatic installation fails, you can install them manually by running:%Npip install -r requirements.txt%N%Nfrom the application directory.
CreateDesktopIcon=Create a desktop icon
CreateQuickLaunchIcon=Create a Quick Launch icon
LaunchProgram=Launch {#MyAppName}
AssociateFiles=Associate .csv files with {#MyAppName}
