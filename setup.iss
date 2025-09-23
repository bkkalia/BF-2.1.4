; Inno Setup Script for Black Forest Tender Scraper
; This script creates a complete installer for the hybrid distribution package

#define MyAppName "Black Forest Tender Scraper"
#define MyAppVersion "2.1.5"
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
; SetupIconFile=dist\resources\app_icon.ico
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UsePreviousAppDir=yes
Uninstallable=yes
CreateUninstallRegKey=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Core executable and Python files
Source: "dist\BlackForest.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\main.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\cli_main.py"; DestDir: "{app}"; Flags: ignoreversion
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
  ExistingVersion: String;
  ExistingInstallDir: String;
  UpgradeMode: Boolean;

function GetInstalledVersion(): String;
var
  Version: String;
begin
  if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{12345678-1234-1234-ABCD-123456789ABC}_is1', 'DisplayVersion', Version) then
  begin
    Result := Version;
  end
  else
  begin
    Result := '';
  end;
end;

function GetInstalledDir(): String;
var
  InstallDir: String;
begin
  if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{12345678-1234-1234-ABCD-123456789ABC}_is1', 'InstallLocation', InstallDir) then
  begin
    Result := InstallDir;
  end
  else
  begin
    Result := '';
  end;
end;

function SplitString(Input: String; Delimiter: String): array of String;
var
  Parts: array of String;
  i, StartPos, DelimPos: Integer;
  CurrentPart: String;
begin
  SetArrayLength(Parts, 0);
  StartPos := 1;

  while True do
  begin
    DelimPos := Pos(Delimiter, Copy(Input, StartPos, Length(Input) - StartPos + 1));
    if DelimPos = 0 then
    begin
      // No more delimiters, add remaining part
      CurrentPart := Copy(Input, StartPos, Length(Input) - StartPos + 1);
      SetArrayLength(Parts, GetArrayLength(Parts) + 1);
      Parts[GetArrayLength(Parts) - 1] := CurrentPart;
      Break;
    end
    else
    begin
      // Extract part before delimiter
      CurrentPart := Copy(Input, StartPos, DelimPos - 1);
      SetArrayLength(Parts, GetArrayLength(Parts) + 1);
      Parts[GetArrayLength(Parts) - 1] := CurrentPart;
      StartPos := StartPos + DelimPos;
    end;
  end;

  Result := Parts;
end;

function Min(A, B: Integer): Integer;
begin
  if A < B then
    Result := A
  else
    Result := B;
end;

function CompareVersions(Version1, Version2: String): Integer;
var
  V1Parts, V2Parts: array of String;
  i, V1Num, V2Num: Integer;
begin
  V1Parts := SplitString(Version1, '.');
  V2Parts := SplitString(Version2, '.');

  for i := 0 to Min(GetArrayLength(V1Parts), GetArrayLength(V2Parts)) - 1 do
  begin
    V1Num := StrToIntDef(V1Parts[i], 0);
    V2Num := StrToIntDef(V2Parts[i], 0);

    if V1Num > V2Num then
    begin
      Result := 1;
      Exit;
    end
    else if V1Num < V2Num then
    begin
      Result := -1;
      Exit;
    end;
  end;

  Result := 0;
end;

function InitializeSetup(): Boolean;
var
  Response: Integer;
begin
  // Check for Python installation first
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
    Exit;
  end;

  // Check for existing installation
  ExistingVersion := GetInstalledVersion();
  ExistingInstallDir := GetInstalledDir();

  if ExistingVersion <> '' then
  begin
    if CompareVersions('{#MyAppVersion}', ExistingVersion) > 0 then
    begin
      // Newer version - offer upgrade
      Response := MsgBox('A previous version (' + ExistingVersion + ') of {#MyAppName} is already installed.' + #13#10 +
                        'Would you like to upgrade to version {#MyAppVersion}?' + #13#10#13#10 +
                        'The old version will be uninstalled first.',
                        mbConfirmation, MB_YESNO);

      if Response = IDYES then
      begin
        UpgradeMode := True;
        Result := True;
      end
      else
      begin
        Result := False;
      end;
    end
    else if CompareVersions('{#MyAppVersion}', ExistingVersion) = 0 then
    begin
      // Same version - offer repair or uninstall
      Response := MsgBox('{#MyAppName} version {#MyAppVersion} is already installed.' + #13#10#13#10 +
                        'Choose an option:' + #13#10 +
                        '  Yes - Repair the existing installation' + #13#10 +
                        '  No - Uninstall and reinstall' + #13#10 +
                        '  Cancel - Abort installation',
                        mbConfirmation, MB_YESNOCANCEL);

      case Response of
        IDYES: begin
          // Repair mode - don't uninstall
          UpgradeMode := False;
          Result := True;
        end;
        IDNO: begin
          // Uninstall and reinstall
          UpgradeMode := True;
          Result := True;
        end;
        IDCANCEL: begin
          Result := False;
        end;
      end;
    end
    else
    begin
      // Older version being installed - warn user
      Response := MsgBox('You are installing an older version ({#MyAppVersion}) than what is currently installed (' + ExistingVersion + ').' + #13#10 +
                        'This may cause issues. Continue anyway?',
                        mbConfirmation, MB_YESNO);

      if Response = IDYES then
      begin
        UpgradeMode := False; // Don't uninstall newer version
        Result := True;
      end
      else
      begin
        Result := False;
      end;
    end;
  end
  else
  begin
    // No existing installation
    UpgradeMode := False;
    Result := True;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  UninstallString: String;
begin
  if CurStep = ssInstall then
  begin
    // Perform uninstallation if upgrading
    if UpgradeMode and (ExistingInstallDir <> '') then
    begin
      Log('Upgrading: Uninstalling previous version from: ' + ExistingInstallDir);

      // Get uninstall string from registry
      if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{12345678-1234-1234-ABCD-123456789ABC}_is1', 'UninstallString', UninstallString) then
      begin
        // Run the uninstaller silently
        if Exec(UninstallString, '/VERYSILENT /NORESTART', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
        begin
          if ResultCode = 0 then
          begin
            Log('Previous version uninstalled successfully');
          end
          else
          begin
            Log('Warning: Previous version uninstall may have failed (exit code: ' + IntToStr(ResultCode) + ')');
          end;
        end
        else
        begin
          Log('Warning: Could not execute uninstaller for previous version');
        end;
      end
      else
      begin
        Log('Warning: Could not find uninstall string for previous version');
      end;
    end;
  end
  else if CurStep = ssPostInstall then
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
