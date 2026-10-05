; ---------------------------------------------------------------------------
;  Inno Setup script for "AnyDesk Timer Removal"
;
;  Build with:
;    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
;
;  The script packages dist\AnyDesk Timer Removal.exe (produced by
;  build_exe.bat / PyInstaller) into a standard Setup.exe.
; ---------------------------------------------------------------------------

#define MyAppName "AnyDesk Timer Removal"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Personal Use"
#define MyAppExeName "AnyDesk Timer Removal.exe"

[Setup]
; A stable AppId keeps upgrades/uninstall working across versions.
AppId={{641F7577-57A8-4E49-9410-955492FA478C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion=1.0.0.0
VersionInfoDescription=AnyDesk Timer Removal - Setup
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=1.0.0.0

; Install per-user by default (no UAC needed to install). The user may pick
; "install for all users" from the privileges dialog.
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes

OutputDir=dist_installer
OutputBaseFilename=AnyDesk Timer Removal Setup
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The whole onedir folder is installed - it stays a valid portable copy too.
Source: "dist\{#MyAppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Unchecked by default so the installer never surprises you with a UAC prompt.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent unchecked
