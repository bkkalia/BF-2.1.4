; Simple Inno Setup Script for testing
; This is a minimal version to test compilation

#define MyAppName "Black Forest Tender Scraper"
#define MyAppVersion "2.2.1"
#define MyAppExeName "BlackForest.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={pf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename=BlackForest_Simple_Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\BlackForest.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\main.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\CLI_HELP.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\GUI_HELP.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall
