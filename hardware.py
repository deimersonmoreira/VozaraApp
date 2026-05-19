import json
import os
import subprocess
from pathlib import Path


def _run_text(cmd: list[str], timeout: int = 10) -> str:
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except Exception:
        return ""


def _nvidia_smi_candidates() -> list[str]:
    candidates = [
        "nvidia-smi",
        str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "nvidia-smi.exe"),
        r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
    ]
    seen = set()
    unique = []
    for item in candidates:
        key = item.lower()
        if key not in seen:
            unique.append(item)
            seen.add(key)
    return unique


def _parse_vram_mb(value) -> int:
    try:
        n = int(float(value or 0))
    except (TypeError, ValueError):
        return 0
    if n > 1024 * 1024:
        return round(n / 1024 / 1024)
    return n


def _vendor_from_name(name: str) -> str:
    upper = name.upper()
    if any(token in upper for token in ("NVIDIA", "GEFORCE", "QUADRO", "RTX", "GTX", "MX", "TESLA", "TITAN", "NVS")):
        return "nvidia"
    if "AMD" in upper or "RADEON" in upper:
        return "amd"
    if "INTEL" in upper and ("ARC" in upper or "IRIS" in upper or "XE" in upper):
        return "intel"
    return "none"


def _from_nvidia_smi() -> dict | None:
    for exe in _nvidia_smi_candidates():
        out = _run_text([
            exe,
            "--query-gpu=name,memory.total",
            "--format=csv,noheader,nounits",
        ], timeout=8)
        if not out:
            continue
        parts = [p.strip() for p in out.splitlines()[0].split(",")]
        if not parts or not parts[0]:
            continue
        return {
            "vendor": "nvidia",
            "name": parts[0],
            "vram_mb": _parse_vram_mb(parts[1] if len(parts) > 1 else 0),
            "source": "nvidia-smi",
        }
    return None


def _from_cim() -> dict | None:
    ps = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM | ConvertTo-Json -Compress"
    )
    out = _run_text(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], timeout=12)
    if not out:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        data = [data]

    first_supported = None
    for item in data:
        name = str(item.get("Name") or "").strip()
        if not name:
            continue
        vendor = _vendor_from_name(name)
        if vendor == "nvidia":
            return {
                "vendor": "nvidia",
                "name": name,
                "vram_mb": _parse_vram_mb(item.get("AdapterRAM")),
                "source": "cim",
            }
        if vendor in ("amd", "intel") and first_supported is None:
            first_supported = {
                "vendor": vendor,
                "name": name,
                "vram_mb": _parse_vram_mb(item.get("AdapterRAM")),
                "source": "cim",
            }
    return first_supported


def _from_wmic() -> dict | None:
    out = _run_text(["wmic", "path", "win32_VideoController", "get", "name,AdapterRAM"], timeout=10)
    if not out:
        return None
    first_supported = None
    for line in out.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("adapterram"):
            continue
        parts = line.split()
        adapter_ram = 0
        if parts and parts[0].isdigit():
            adapter_ram = _parse_vram_mb(parts[0])
            name = " ".join(parts[1:]).strip()
        else:
            name = line
        if not name:
            continue
        vendor = _vendor_from_name(name)
        if vendor == "nvidia":
            return {"vendor": "nvidia", "name": name, "vram_mb": adapter_ram, "source": "wmic"}
        if vendor in ("amd", "intel") and first_supported is None:
            first_supported = {"vendor": vendor, "name": name, "vram_mb": adapter_ram, "source": "wmic"}
    return first_supported


def detect_gpu_info() -> dict:
    for probe in (_from_nvidia_smi, _from_cim, _from_wmic):
        info = probe()
        if info:
            return info
    return {
        "vendor": "none",
        "name": "Nenhuma GPU dedicada detectada",
        "vram_mb": 0,
        "source": "none",
    }
