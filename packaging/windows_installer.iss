; Inno Setup script for the BIDSHub Windows installer.
; Build on Windows after `pyinstaller packaging\bidshub.spec` produces
; dist\BIDSHub\ (onedir).  Compile with:  iscc packaging\windows_installer.iss
; Output: dist\BIDSHub-Setup.exe
;
; Runtime requirement: pywebview uses the Microsoft Edge WebView2 runtime
; (preinstalled on Win11 / current Win10). The [Code] section below detects it
; and silently installs the Evergreen runtime if missing, so the app window
; opens on a clean machine.

#define AppName "BIDSHub"
#define AppVersion "3.1.4"
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

[Code]
// The app's window needs the Edge WebView2 runtime. Detect it and, if absent,
// download + silently install the Evergreen bootstrapper from Microsoft.
function IsWebView2Installed(): Boolean;
var
  v: String;
begin
  Result :=
    (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v) and (v <> '') and (v <> '0.0.0.0'))
    or (RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v) and (v <> '') and (v <> '0.0.0.0'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if (CurStep = ssPostInstall) and (not IsWebView2Installed()) then
  begin
    try
      // Inno 6.1+ built-in download (no plugins). Microsoft Evergreen bootstrapper.
      DownloadTemporaryFile('https://go.microsoft.com/fwlink/p/?LinkId=2124703',
        'MicrosoftEdgeWebview2Setup.exe', '', nil);
      Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'),
        '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    except
      // Offline / blocked: the app still installs; the user can install WebView2
      // manually (see the README) and relaunch.
    end;
  end;
end;
