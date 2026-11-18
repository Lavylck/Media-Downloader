#define AppVersion "3.0.0"
[Setup]
AppId={{E0899E09-1DE4-4305-A491-53299A937351}
AppName=Media Downloader Cyberpunk Edition
AppVersion={#AppVersion}
AppPublisher=Media Downloader
DefaultDirName={localappdata}\Programs\MediaDownloader
DefaultGroupName=Media Downloader
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=MediaDownloader-{#AppVersion}-Setup-x64
SetupIconFile=..\build\icon.ico
UninstallDisplayIcon={app}\MediaDownloader.exe
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no
InfoBeforeFile=README_WINDOWS.md

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Files]
Source: "..\dist\MediaDownloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Media Downloader"; Filename: "{app}\MediaDownloader.exe"; WorkingDir: "{app}"; AppUserModelID: "MediaDownloader.Cyberpunk.3"
Name: "{userdesktop}\Media Downloader"; Filename: "{app}\MediaDownloader.exe"; WorkingDir: "{app}"; Tasks: desktopicon; AppUserModelID: "MediaDownloader.Cyberpunk.3"

[Run]
Filename: "{app}\MediaDownloader.exe"; Description: "Abrir Media Downloader"; Flags: nowait postinstall skipifsilent

; User data is deliberately outside {app}. Uninstallation preserves downloads,
; history, settings and cache. No UninstallDelete rule removes those files.
