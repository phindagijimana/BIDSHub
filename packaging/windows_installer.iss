; Inno Setup script for the BIDSHub Windows installer.
; Build on Windows after `pyinstaller packaging\bidshub.spec` produces
; dist\BIDSHub\ (onedir).  Compile with:  iscc packaging\windows_installer.iss
; Output: dist\BIDSHub-Setup.exe

#define AppName "BIDSHub"
#define AppVersion "3.1.1"
#define AppPublisher "BIDSHub"
#define AppExe "BIDSHub.exe"

[Setup]
AppId={{B1D54B00-0000-4000-8000-000000000001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename={#AppName}-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=icons\BIDSHub.ico
UninstallDisplayIcon={app}\{#AppExe}
; Per-user data (the DB) lives under %APPDATA%\BIDSHub via app_paths — not here.

[Files]
Source: "..\dist\BIDSHub\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
