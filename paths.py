import os
import sys
from pathlib import Path

APP_NAME = "VozaraApp"
APP_DIR_NAME = "VozaraApp"

BASE = Path(__file__).resolve().parent

LOCAL_APPDATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
DATA_DIR = Path(os.environ.get("TRANSCRIBER_DATA_DIR", str(LOCAL_APPDATA / APP_DIR_NAME)))
VENV = DATA_DIR / ".venv"
PYTHONV = VENV / "Scripts" / "python.exe"
PYTHONW = VENV / "Scripts" / "pythonw.exe"

CONFIG_FILE = DATA_DIR / "config.json"
LOG_FILE = DATA_DIR / "transcrever.log"
HF_HOME = DATA_DIR / "huggingface"

DOCUMENTS = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents"
DEFAULT_OUTPUT_DIR = Path(os.environ.get("TRANSCRIBER_OUTPUT_DIR", str(DOCUMENTS / "VozaraApp")))

RUNTIME_PYTHON = BASE / "runtime" / "python" / "python.exe"
RUNTIME_PYTHONW = BASE / "runtime" / "python" / "pythonw.exe"
BUNDLED_FFMPEG_BIN = BASE / "vendor" / "ffmpeg" / "bin"

REQUIREMENTS_BASE = BASE / "requirements-base.txt"
REQUIREMENTS_CPU = BASE / "requirements-cpu.txt"
REQUIREMENTS_GPU = BASE / "requirements-gpu.txt"
REQUIREMENTS_NVIDIA = BASE / "requirements-nvidia.txt"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HF_HOME.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def bootstrap_python() -> Path:
    if RUNTIME_PYTHON.exists():
        return RUNTIME_PYTHON
    return Path(sys.executable)


def bootstrap_pythonw() -> Path:
    if RUNTIME_PYTHONW.exists():
        return RUNTIME_PYTHONW
    return Path(sys.executable)


def venv_installed() -> bool:
    return PYTHONW.exists() and (VENV / "Lib" / "site-packages" / "customtkinter").exists()


def apply_runtime_environment() -> None:
    ensure_dirs()
    os.environ.setdefault("HF_HOME", str(HF_HOME))
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    if (RUNTIME_PYTHON / "tcl" / "tcl8.6" / "init.tcl").exists():
        os.environ.setdefault("TCL_LIBRARY", str(RUNTIME_PYTHON / "tcl" / "tcl8.6"))
    if (RUNTIME_PYTHON / "tcl" / "tk8.6").exists():
        os.environ.setdefault("TK_LIBRARY", str(RUNTIME_PYTHON / "tcl" / "tk8.6"))

    path_parts = []
    if BUNDLED_FFMPEG_BIN.exists():
        path_parts.append(str(BUNDLED_FFMPEG_BIN))

    path_parts.extend([
        str(VENV / "Lib" / "site-packages" / "nvidia" / "cublas" / "bin"),
        str(VENV / "Lib" / "site-packages" / "nvidia" / "cudnn" / "bin"),
    ])

    current_path = os.environ.get("PATH", "")
    os.environ["PATH"] = ";".join(path_parts + [current_path])
