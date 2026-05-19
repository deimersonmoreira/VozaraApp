import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Callable

from paths import apply_runtime_environment

apply_runtime_environment()

logger = logging.getLogger("transcrever")


def _run_text(cmd: list[str], timeout: int = 10) -> str:
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=creationflags)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def detect_gpu_info() -> dict:
    info = {
        "vendor": "none",
        "name": "Nenhuma GPU NVIDIA detectada",
        "vram_mb": 0,
    }

    out = _run_text([
        "nvidia-smi",
        "--query-gpu=name,memory.total",
        "--format=csv,noheader,nounits",
    ])
    if out:
        first = out.splitlines()[0]
        parts = [p.strip() for p in first.split(",")]
        info["vendor"] = "nvidia"
        info["name"] = parts[0]
        if len(parts) > 1:
            try:
                info["vram_mb"] = int(float(parts[1]))
            except ValueError:
                info["vram_mb"] = 0
        return info

    out = _run_text(["wmic", "path", "win32_VideoController", "get", "name"])
    for line in out.splitlines():
        name = line.strip()
        if not name or name.lower() == "name":
            continue
        upper = name.upper()
        if "NVIDIA" in upper:
            info.update(vendor="nvidia", name=name)
            return info
        if "AMD" in upper or "RADEON" in upper:
            info.update(vendor="amd", name=name)
            return info
        if "INTEL" in upper and ("ARC" in upper or "IRIS" in upper):
            info.update(vendor="intel", name=name)
            return info

    return info


def detect_device(preferred_mode: str = "auto") -> tuple[str, str, str]:
    """Returns (device, compute_type, label)."""
    if preferred_mode == "cpu":
        return "cpu", "int8", "CPU · modo escolhido"

    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            return "cuda", "float16", f"GPU · {name}"
    except Exception as exc:
        logger.exception("Falha ao detectar CUDA: %s", exc)

    return "cpu", "int8", "CPU · sem GPU NVIDIA disponível"


def media_duration_seconds(path: Path) -> float:
    out = _run_text([
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ], timeout=20)
    if not out:
        return 0.0
    try:
        data = json.loads(out)
        return max(0.0, float(data.get("format", {}).get("duration", 0) or 0))
    except Exception:
        return 0.0


def estimate_transcription_seconds(duration: float, device: str) -> float:
    if duration <= 0:
        return 0.0
    factor = 0.035 if device == "cuda" else 0.33
    return max(8.0, duration * factor)


def format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "tempo desconhecido"
    seconds = int(round(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}h {m:02}min"
    if m:
        return f"{m}min {s:02}s"
    return f"{s}s"


def tempo_srt(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sc = int(s % 60)
    ms = int((s - int(s)) * 1000)
    return f"{h:02}:{m:02}:{sc:02},{ms:03}"


class Transcriber:
    def __init__(self, device: str, compute_type: str):
        from faster_whisper import WhisperModel

        self.device = device
        self.compute_type = compute_type
        self.model = WhisperModel("medium", device=device, compute_type=compute_type)

    def transcribe(
        self,
        audio: Path,
        on_segment: Callable[[float, str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
        wait_if_paused: Callable[[], None] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Returns (txt_lines, srt_lines)."""
        segments, _ = self.model.transcribe(
            str(audio),
            language="pt",
            task="transcribe",
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            condition_on_previous_text=False,
        )

        txt: list[str] = []
        srt: list[str] = []
        n = 1

        for seg in segments:
            if wait_if_paused:
                wait_if_paused()
            if should_cancel and should_cancel():
                raise RuntimeError("Transcrição cancelada pelo usuário.")

            frase = seg.text.strip()
            if not frase:
                continue
            txt.append(frase)
            srt += [str(n), f"{tempo_srt(seg.start)} --> {tempo_srt(seg.end)}", frase, ""]
            if on_segment:
                on_segment(float(seg.end), frase)
            n += 1

        return txt, srt
