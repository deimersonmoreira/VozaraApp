; build-online.iss - Inno Setup 6
; Variante experimental: instalador menor, baixa dependencias na primeira configuracao.
; Use o build.iss principal para releases estaveis.

#define AppName       "VozaraApp"
#define AppVersion    "1.1.0"
#define AppDir        "VozaraApp"

[Setup]
AppId={{B7C4A2D1-F3E8-4A90-BC12-8D5E3F1A9C07-ONLINE}
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
OutputBaseFilename=Instalar - VozaraApp Online
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
Source: "hardware.py";              DestDir: "{app}"; Flags: ignoreversion
Source: "app.py";                   DestDir: "{app}"; Flags: ignoreversion
Source: "first_run.py";             DestDir: "{app}"; Flags: ignoreversion
Source: "main.py";                  DestDir: "{app}"; Flags: ignoreversion
Source: "paths.py";                 DestDir: "{app}"; Flags: ignoreversion
Source: "uninstall.py";             DestDir: "{app}"; Flags: ignoreversion
Source: "launcher.bat";             DestDir: "{app}"; Flags: ignoreversion
Source: "launcher.vbs";             DestDir: "{app}"; Flags: ignoreversion
Source: "README.md";                DestDir: "{app}"; Flags: ignoreversion
Source: "BRANDING.md";              DestDir: "{app}"; Flags: ignoreversion
Source: "assets\*.svg";             DestDir: "{app}\assets"; Flags: ignoreversion
Source: "assets\*.ico";             DestDir: "{app}\assets"; Flags: ignoreversion
Source: "requirements-base.txt";    DestDir: "{app}"; Flags: ignoreversion
Source: "requirements-cpu.txt";     DestDir: "{app}"; Flags: ignoreversion
Source: "requirements-gpu.txt";     DestDir: "{app}"; Flags: ignoreversion
Source: "requirements-nvidia.txt";  DestDir: "{app}"; Flags: ignoreversion
Source: "vendor\python\python-3.11.9-amd64.exe"; DestDir: "{app}\vendor\python"; Flags: ignoreversion
Source: "vendor\ffmpeg\bin\ffmpeg.exe";          DestDir: "{app}\vendor\ffmpeg\bin"; Flags: ignoreversion
Source: "vendor\ffmpeg\bin\ffprobe.exe";         DestDir: "{app}\vendor\ffmpeg\bin"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";       Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"
Name: "{userdesktop}\{#AppName}"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon.ico"

[UninstallRun]
Filename: "{app}\runtime\python\pythonw.exe"; \
    Parameters: """{app}\uninstall.py"""; \
    Flags: waituntilterminated; \
    Check: FileExists(ExpandConstant('{app}\runtime\python\pythonw.exe')); \
    RunOnceId: "RemoveDeps"

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\{#AppDir}\.venv"
