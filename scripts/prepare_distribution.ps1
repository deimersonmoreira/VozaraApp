param(
    [string]$PythonVersion = "3.11.9",
    [switch]$CompileInstaller
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Vendor = Join-Path $Root "vendor"
$PythonDir = Join-Path $Vendor "python"
$RuntimePythonDir = Join-Path $Root "runtime\python"
$FfmpegDir = Join-Path $Vendor "ffmpeg"
$FfmpegBin = Join-Path $FfmpegDir "bin"
$Temp = Join-Path $Root ".dist-tmp"

New-Item -ItemType Directory -Force -Path $PythonDir, $RuntimePythonDir, $FfmpegBin, $Temp | Out-Null

Write-Host "Gerando icone do aplicativo..."
python (Join-Path $Root "scripts\create_icon.py")

$pythonInstaller = Join-Path $PythonDir "python-$PythonVersion-amd64.exe"
$pythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
if (-not (Test-Path $pythonInstaller)) {
    Write-Host "Baixando Python $PythonVersion..."
    Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonInstaller
}

if (-not (Test-Path (Join-Path $RuntimePythonDir "python.exe")) -or -not (Test-Path (Join-Path $RuntimePythonDir "pythonw.exe"))) {
    Write-Host "Preparando Python interno em runtime\python..."
    $args = @(
        "/quiet",
        "InstallAllUsers=0",
        "TargetDir=$RuntimePythonDir",
        "Include_launcher=0",
        "PrependPath=0",
        "Include_pip=1",
        "Include_tcltk=1",
        "Include_test=0",
        "Shortcuts=0",
        "AssociateFiles=0"
    )
    $proc = Start-Process -FilePath $pythonInstaller -ArgumentList $args -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        throw "Falha ao preparar Python interno. Codigo: $($proc.ExitCode)"
    }
    if (-not (Test-Path (Join-Path $RuntimePythonDir "python.exe")) -or -not (Test-Path (Join-Path $RuntimePythonDir "pythonw.exe"))) {
        Write-Host "Instalador do Python nao criou TargetDir. Copiando Python local instalado..."
        $localPythonRoot = python -c "import sys; print(sys.base_prefix)"
        if (-not $localPythonRoot -or -not (Test-Path (Join-Path $localPythonRoot "python.exe"))) {
            throw "Python interno nao foi criado e nao foi possivel localizar Python local para copiar."
        }
        Get-ChildItem -LiteralPath $localPythonRoot -Force | Copy-Item -Destination $RuntimePythonDir -Recurse -Force
    }
    if (-not (Test-Path (Join-Path $RuntimePythonDir "python.exe")) -or -not (Test-Path (Join-Path $RuntimePythonDir "pythonw.exe"))) {
        throw "Python interno nao foi criado em $RuntimePythonDir."
    }
}

$ffmpegZip = Join-Path $Temp "ffmpeg-release-essentials.zip"
if (-not (Test-Path (Join-Path $FfmpegBin "ffmpeg.exe")) -or -not (Test-Path (Join-Path $FfmpegBin "ffprobe.exe"))) {
    Write-Host "Baixando FFmpeg..."
    Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $ffmpegZip

    $extract = Join-Path $Temp "ffmpeg"
    if (Test-Path $extract) {
        Remove-Item -LiteralPath $extract -Recurse -Force
    }
    Expand-Archive -Path $ffmpegZip -DestinationPath $extract -Force

    $ffmpegExe = Get-ChildItem -Path $extract -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    $ffprobeExe = Get-ChildItem -Path $extract -Recurse -Filter "ffprobe.exe" | Select-Object -First 1

    if (-not $ffmpegExe -or -not $ffprobeExe) {
        throw "Nao foi possivel localizar ffmpeg.exe e ffprobe.exe no pacote baixado."
    }

    Copy-Item -LiteralPath $ffmpegExe.FullName -Destination (Join-Path $FfmpegBin "ffmpeg.exe") -Force
    Copy-Item -LiteralPath $ffprobeExe.FullName -Destination (Join-Path $FfmpegBin "ffprobe.exe") -Force
}

Write-Host "Arquivos de distribuicao preparados:"
Write-Host " - $pythonInstaller"
Write-Host " - $(Join-Path $RuntimePythonDir 'python.exe')"
Write-Host " - $(Join-Path $FfmpegBin 'ffmpeg.exe')"
Write-Host " - $(Join-Path $FfmpegBin 'ffprobe.exe')"
Write-Host " - $(Join-Path $Root 'assets\icon.ico')"

if ($CompileInstaller) {
    $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $iscc)) {
        $iscc = "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
    }
    if (-not (Test-Path $iscc)) {
        $iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    }
    if (-not (Test-Path $iscc)) {
        throw "ISCC.exe nao encontrado. Instale o Inno Setup 6 ou compile build.iss manualmente."
    }
    & $iscc (Join-Path $Root "build.iss")
}
