#define MyAppName "Video to MP3 Converter"
#define MyAppVersion "1.1.0"
#define MyAppExeName "VideoToMP3.exe"

[Setup]
AppId={{4FDDA98D-8BCD-4BB9-9D47-4DBB72191F2A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\VideoToMP3
DefaultGroupName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename=VideoToMP3-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

[Files]
Source: "dist\VideoToMP3.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
