; build.iss - Inno Setup 6
; Antes de compilar, rode:
; powershell -ExecutionPolicy Bypass -File scripts\prepare_distribution.ps1

#define AppName       "VozaraApp"
#define AppVersion    "1.1.0"
#define AppDir        "VozaraApp"

[Setup]
AppId={{B7C4A2D1-F3E8-4A90-BC12-8D5E3F1A9C07}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Deime
DefaultDirName={localappdata}\{#AppDir}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\assets\icon.ico
OutputDir=.
OutputBaseFilename=Instalar - VozaraApp
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "core.py";                  DestDir: "{app}"; Flags: ignoreversion
Source: "app.py";                   DestDir: "{app}"; Flags: ignoreversion
Source: "first_run.py";             DestDir: "{app}"; Flags: ignoreversion
Source: "main.py";                  DestDir: "{app}"; Flags: ignoreversion
Source: "paths.py";                 DestDir: "{app}"; Flags: ignoreversion
Source: "uninstall.py";             DestDir: "{app}"; Flags: ignoreversion
Source: "launcher.bat";             DestDir: "{app}"; Flags: ignoreversion
Source: "README.md";                DestDir: "{app}"; Flags: ignoreversion
Source: "BRANDING.md";              DestDir: "{app}"; Flags: ignoreversion
Source: "assets\*.svg";             DestDir: "{app}\assets"; Flags: ignoreversion
Source: "assets\*.ico";             DestDir: "{app}\assets"; Flags: ignoreversion
Source: "requirements-base.txt";    DestDir: "{app}"; Flags: ignoreversion
Source: "requirements-cpu.txt";     DestDir: "{app}"; Flags: ignoreversion
Source: "requirements-gpu.txt";     DestDir: "{app}"; Flags: ignoreversion
Source: "requirements-nvidia.txt";  DestDir: "{app}"; Flags: ignoreversion
Source: "vendor\ffmpeg\bin\ffmpeg.exe";  DestDir: "{app}\vendor\ffmpeg\bin"; Flags: ignoreversion
Source: "vendor\ffmpeg\bin\ffprobe.exe"; DestDir: "{app}\vendor\ffmpeg\bin"; Flags: ignoreversion
Source: "vendor\runtime\python\*"; DestDir: "{app}\runtime\python"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";       Filename: "{app}\launcher.bat"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\launcher.bat"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"

[UninstallRun]
Filename: "{cmd}"; \
    Parameters: "/c if exist ""{localappdata}\{#AppDir}\.venv\Scripts\pythonw.exe"" (""{localappdata}\{#AppDir}\.venv\Scripts\pythonw.exe"" ""{app}\uninstall.py"") else if exist ""{app}\runtime\python\pythonw.exe"" (""{app}\runtime\python\pythonw.exe"" ""{app}\uninstall.py"")"; \
    Flags: waituntilterminated; \
    RunOnceId: "RemoveDeps"

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\{#AppDir}\.venv"
