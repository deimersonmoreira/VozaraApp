import ctypes
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

from hardware import detect_gpu_info
from paths import (
    BASE,
    BUNDLED_FFMPEG_BIN,
    CONFIG_FILE,
    DEFAULT_OUTPUT_DIR,
    HF_HOME,
    LOG_FILE,
    PYTHONV,
    PYTHONW,
    REQUIREMENTS_BASE,
    REQUIREMENTS_CPU,
    REQUIREMENTS_GPU,
    REQUIREMENTS_NVIDIA,
    VENV,
    apply_runtime_environment,
    bootstrap_python,
)

apply_runtime_environment()

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger("transcrever.setup")

W, H = 620, 660
BG = "white"
BRAND_BLUE = "#16324F"
BRAND_GREEN = "#00A7A5"
BRAND_YELLOW = "#F2B84B"
BLUE = BRAND_BLUE
GREEN = BRAND_GREEN
ORANGE = "#e65100"
RED = "#c62828"
GRAY = "#777777"
DARK = "#1a1a2e"
LGRAY = "#f5f5f5"
ALERT_BG = "#ffebee"
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
ICON_FILE = BASE / "assets" / "icon.ico"


def _run(cmd: list[str], timeout: int | None = None) -> tuple[bool, str]:
    logger.info("Executando: %s", " ".join(map(str, cmd)))
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags,
        )
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        if result.returncode != 0:
            logger.error("Falha (%s): %s", result.returncode, output[-4000:])
        return result.returncode == 0, output
    except Exception as exc:
        logger.exception("Erro ao executar comando")
        return False, str(exc)


def _run_retry(cmd: list[str], attempts: int = 3, timeout: int | None = None) -> tuple[bool, str]:
    last_output = ""
    for attempt in range(1, attempts + 1):
        ok, output = _run(cmd, timeout=timeout)
        last_output = output
        if ok:
            return True, output
        logger.warning("Tentativa %s/%s falhou", attempt, attempts)
    return False, last_output


def _clean_output_line(line: str) -> str:
    return ANSI_RE.sub("", line).strip()


def _run_stream(cmd: list[str], on_output=None, timeout: int | None = None) -> tuple[bool, str]:
    logger.info("Executando com progresso: %s", " ".join(map(str, cmd)))
    output_lines: list[str] = []
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
        assert proc.stdout is not None
        pending = ""
        last_line = ""

        def emit(raw: str):
            nonlocal last_line
            line = _clean_output_line(raw)
            if not line or line == last_line:
                return
            last_line = line
            output_lines.append(line)
            logger.info("[progresso] %s", line)
            if on_output:
                on_output(line)

        while True:
            ch = proc.stdout.read(1)
            if ch == "" and proc.poll() is not None:
                break
            if ch in ("\n", "\r"):
                emit(pending)
                pending = ""
            elif ch:
                pending += ch
                if len(pending) >= 500:
                    emit(pending)
                    pending = ""
        emit(pending)

        returncode = proc.wait(timeout=timeout)
        output = "\n".join(output_lines)
        if returncode != 0:
            logger.error("Falha (%s): %s", returncode, output[-4000:])
        return returncode == 0, output
    except Exception as exc:
        logger.exception("Erro ao executar comando com progresso")
        return False, str(exc)


def _run_retry_stream(cmd: list[str], attempts: int = 3, timeout: int | None = None, on_output=None) -> tuple[bool, str]:
    last_output = ""
    for attempt in range(1, attempts + 1):
        if on_output and attempts > 1:
            on_output(f"Tentativa {attempt}/{attempts}")
        ok, output = _run_stream(cmd, on_output=on_output, timeout=timeout)
        last_output = output
        if ok:
            return True, output
        logger.warning("Tentativa %s/%s falhou", attempt, attempts)
    return False, last_output


def get_ram_gb() -> int:
    try:
        class MemStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        mem = MemStatus()
        mem.dwLength = ctypes.sizeof(mem)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
        return round(mem.ullTotalPhys / 1024 ** 3)
    except Exception:
        return 0


def detect_gpu() -> tuple[str, str, int]:
    info = detect_gpu_info()
    return info["vendor"], info["name"], info["vram_mb"]


def ffmpeg_available() -> bool:
    if (BUNDLED_FFMPEG_BIN / "ffmpeg.exe").exists() and (BUNDLED_FFMPEG_BIN / "ffprobe.exe").exists():
        return True
    ok, _ = _run(["ffmpeg", "-version"], timeout=8)
    ok_probe, _ = _run(["ffprobe", "-version"], timeout=8)
    return ok and ok_probe


def lbl(parent, text, size=11, bold=False, color=DARK, **kw):
    return tk.Label(
        parent,
        text=text,
        bg=parent["bg"],
        font=("Segoe UI", size, "bold" if bold else "normal"),
        fg=color,
        **kw,
    )


def sep(parent):
    tk.Frame(parent, bg="#e0e0e0", height=1).pack(fill="x", padx=20, pady=8)


class SetupWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VozaraApp - Configuração")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._confirm_close)
        if ICON_FILE.exists():
            try:
                self.root.iconbitmap(str(ICON_FILE))
            except Exception:
                logger.exception("Nao foi possivel carregar icone da janela")

        self.mode = "cpu"
        self.gpu_vendor = "none"
        self.gpu_name = ""
        self.gpu_vram = 0
        self.recommend_gpu = False
        self.install_failed = False
        self._last_progress = ""

        self._build_chrome()
        self._center()
        self._page_welcome()

    def _confirm_close(self):
        if messagebox.askyesno("Fechar configuração?", "A configuração ainda não terminou. Deseja fechar?"):
            self.root.destroy()

    def _build_chrome(self):
        hdr = tk.Frame(self.root, bg=BRAND_BLUE, height=78)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        mark = tk.Canvas(hdr, width=42, height=42, bg=BRAND_BLUE, bd=0, highlightthickness=0)
        mark.place(x=18, rely=0.5, anchor="w")
        mark.create_oval(3, 3, 39, 39, fill=BRAND_GREEN, outline="")
        mark.create_arc(11, 10, 31, 32, start=300, extent=240, style="arc", outline="white", width=4)
        mark.create_oval(27, 7, 35, 15, fill=BRAND_YELLOW, outline="")

        tk.Label(
            hdr,
            text="Vozara",
            font=("Segoe UI", 20, "bold"),
            bg=BRAND_BLUE,
            fg="white",
            anchor="w",
        ).place(x=70, y=19, anchor="w")
        tk.Label(
            hdr,
            text="transcrição local de áudio e vídeo",
            font=("Segoe UI", 9),
            bg=BRAND_BLUE,
            fg="#d7eef0",
            anchor="w",
        ).place(x=72, y=48, anchor="w")

        self.lbl_step = tk.Label(hdr, text="1 / 4", font=("Segoe UI", 10, "bold"), bg=BRAND_BLUE, fg=BRAND_YELLOW)
        self.lbl_step.place(relx=1, rely=0.5, anchor="e", x=-20)

        self.body = tk.Frame(self.root, bg=BG)
        self.body.pack(fill="both", expand=True)

        ftr = tk.Frame(self.root, bg=LGRAY, height=58)
        ftr.pack(fill="x")
        ftr.pack_propagate(False)

        self.btn = tk.Button(
            ftr,
            text="Próximo",
            font=("Segoe UI", 11, "bold"),
            bg=BRAND_GREEN,
            fg="white",
            relief="flat",
            activebackground="#008c8a",
            activeforeground="white",
            padx=22,
            pady=6,
            cursor="hand2",
        )
        self.btn.place(relx=0.97, rely=0.5, anchor="e")

        tk.Label(
            ftr,
            text="feito no ódio por @deimersonmoreira",
            font=("Segoe UI", 9),
            bg=LGRAY,
            fg="#536675",
        ).place(relx=0.03, rely=0.5, anchor="w")

    def _clear(self):
        for widget in self.body.winfo_children():
            widget.destroy()

    def _center(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

    def _page_welcome(self):
        self._clear()
        self.lbl_step.configure(text="1 / 4")
        f = self.body

        lbl(f, "Bem-vindo!", 16, bold=True).pack(pady=(20, 4))
        lbl(f, "A primeira configuração precisa de internet para baixar dependências e o modelo.", 10, color=GRAY).pack()
        lbl(f, "Depois disso, a transcrição roda localmente no computador.", 10, color=GRAY).pack()
        sep(f)

        info = tk.Frame(f, bg=BG)
        info.pack(fill="x", padx=24)

        rows = [
            ("Saída padrão", str(DEFAULT_OUTPUT_DIR)),
            ("Cache e logs", str(LOG_FILE.parent)),
            ("Modelo", "Whisper medium (~1,5 GB)"),
            ("FFmpeg", "Incluído no instalador final; usado para áudio e vídeo"),
        ]
        for i, (name, value) in enumerate(rows):
            tk.Label(info, text=name, bg=BG, fg=DARK, width=15, anchor="w", font=("Segoe UI", 10, "bold")).grid(row=i, column=0, pady=5, sticky="w")
            tk.Label(info, text=value, bg=BG, fg="#444", anchor="w", wraplength=360, font=("Segoe UI", 10)).grid(row=i, column=1, pady=5, sticky="w")

        sep(f)
        lbl(f, "Desempenho esperado", 11, bold=True).pack(anchor="w", padx=24)
        lbl(f, "GPU NVIDIA: cerca de 1-3 min por hora de áudio.", 10, color=BLUE).pack(anchor="w", padx=24, pady=(6, 0))
        lbl(f, "CPU: cerca de 10-30 min por hora de áudio.", 10, color=GRAY).pack(anchor="w", padx=24)

        self.btn.configure(text="Analisar sistema", state="normal", command=self._page_scan)

    def _page_scan(self):
        self._clear()
        self.lbl_step.configure(text="2 / 4")
        self.btn.configure(state="disabled", text="Analisando...")
        f = self.body

        lbl(f, "Analisando seu sistema...", 15, bold=True).pack(pady=(24, 4))
        lbl(f, "Verificando Python embutido, RAM, espaço, GPU e FFmpeg.", 10, color=GRAY).pack()
        sep(f)

        grid = tk.Frame(f, bg=BG)
        grid.pack(fill="x", padx=42, pady=8)
        self._scan_vals = {}
        for i, (key, title) in enumerate([
            ("python", "Python do app"),
            ("ram", "Memória RAM"),
            ("disk", "Espaço livre"),
            ("gpu", "Placa de vídeo"),
            ("ffmpeg", "FFmpeg"),
        ]):
            tk.Label(grid, text=title, font=("Segoe UI", 11, "bold"), bg=BG, fg=DARK, anchor="w", width=18).grid(row=i, column=0, sticky="w", pady=6)
            val = tk.Label(grid, text="verificando...", font=("Segoe UI", 11), bg=BG, fg="#aaa", anchor="w", wraplength=320)
            val.grid(row=i, column=1, sticky="w")
            self._scan_vals[key] = val

        sep(f)
        self._scan_result = lbl(f, "", 11, color=DARK, wraplength=500, justify="center")
        self._scan_result.pack(pady=4)
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _scan_update(self, key, text, color=GREEN):
        self.root.after(0, lambda: self._scan_vals[key].configure(text=text, fg=color))

    def _do_scan(self):
        py = bootstrap_python()
        self._scan_update("python", str(py), GREEN if py.exists() else ORANGE)

        ram = get_ram_gb()
        self._scan_update("ram", f"{ram} GB" + ("  mínimo recomendado: 8 GB" if ram < 8 else ""), GREEN if ram >= 8 else ORANGE)

        free = shutil.disk_usage(DEFAULT_OUTPUT_DIR.parent).free / 1024 ** 3
        self._scan_update("disk", f"{free:.1f} GB livres" + ("  mínimo: 8 GB" if free < 8 else ""), GREEN if free >= 8 else ORANGE)

        self.gpu_vendor, self.gpu_name, self.gpu_vram = detect_gpu()
        if self.gpu_vendor == "nvidia":
            vram_txt = f" ({self.gpu_vram // 1024} GB VRAM)" if self.gpu_vram else ""
            color = BLUE if self.gpu_vram == 0 or self.gpu_vram >= 4096 else ORANGE
            self._scan_update("gpu", f"{self.gpu_name}{vram_txt}", color)
        elif self.gpu_vendor in ("amd", "intel"):
            self._scan_update("gpu", f"{self.gpu_name} (sem CUDA)", ORANGE)
        else:
            self._scan_update("gpu", "Não detectada", GRAY)

        self._scan_update("ffmpeg", "Disponível" if ffmpeg_available() else "Não encontrado no pacote", GREEN if ffmpeg_available() else RED)

        def finish():
            if not ffmpeg_available():
                self._scan_result.configure(
                    text="FFmpeg não foi encontrado. Para distribuir sem erros, gere o instalador com vendor\\ffmpeg\\bin\\ffmpeg.exe e ffprobe.exe.",
                    fg=RED,
                )
                self.btn.configure(state="disabled", text="FFmpeg ausente")
                return

            if self.gpu_vendor == "nvidia":
                self.recommend_gpu = self.gpu_vram == 0 or self.gpu_vram >= 4096
                if self.recommend_gpu:
                    self._scan_result.configure(text="GPU NVIDIA detectada. CPU continua recomendado para instalar com menos erro; GPU fica como aceleração opcional.", fg=BLUE)
                else:
                    self._scan_result.configure(
                        text=(
                            "GPU NVIDIA detectada, mas a VRAM esta abaixo do recomendado para o Whisper medium. "
                            "O modo CPU e mais seguro; GPU pode falhar por falta de memoria."
                        ),
                        fg=ORANGE,
                    )
                self.btn.configure(state="normal", text="Escolher modo", command=self._page_mode)
            else:
                self.mode = "cpu"
                self._scan_result.configure(text="O aplicativo sera configurado em modo CPU.", fg=ORANGE)
                self.btn.configure(state="normal", text="Instalar", command=self._page_install)

        self.root.after(300, finish)

    def _page_mode(self):
        self._clear()
        self.lbl_step.configure(text="3 / 4")
        f = self.body

        lbl(f, "Escolha o modo de execução", 15, bold=True).pack(pady=(24, 4))
        lbl(f, f"GPU detectada: {self.gpu_name}", 10, color=BLUE).pack()
        sep(f)

        default_mode = "cpu"
        self._mode_var = tk.StringVar(value=default_mode)
        cards = tk.Frame(f, bg=BG)
        cards.pack(fill="x", padx=26, pady=6)
        self._card_frames = {}

        cpu_title = "Transcrição Rápida (CPU) - recomendado"
        cpu_desc = "Mais estável e funcional para a maioria dos usuários. Instala com menos dependências pesadas e menor chance de erro."
        gpu_title = "Transcrição Express (GPU NVIDIA) - opcional"
        gpu_desc = "Pode transcrever mais rápido depois de instalado, mas a instalação demora mais e pode apresentar mais erros de compatibilidade."

        for mode, title, desc, color, bg in [
            ("cpu", cpu_title, cpu_desc, BLUE, "#e3f2fd"),
            ("gpu", gpu_title, gpu_desc, GREEN, "#e8f5e9"),
        ]:
            outer = tk.Frame(cards, bg=color, padx=2, pady=2)
            outer.pack(fill="x", pady=(0, 12))
            inner = tk.Frame(outer, bg=bg, padx=16, pady=12, cursor="hand2")
            inner.pack(fill="x")
            header = tk.Frame(inner, bg=bg, cursor="hand2")
            header.pack(fill="x")
            rb = tk.Radiobutton(header, variable=self._mode_var, value=mode, bg=bg, command=lambda m=mode: self._sel_mode(m))
            rb.place(x=0, rely=0.5, anchor="w")
            tk.Label(
                header,
                text=title,
                bg=bg,
                fg=color,
                font=("Segoe UI", 13, "bold"),
                cursor="hand2",
                anchor="center",
            ).pack(fill="x", padx=28)
            tk.Label(
                inner,
                text=desc,
                bg=bg,
                fg="#333333",
                font=("Segoe UI", 10),
                wraplength=500,
                justify="center",
                cursor="hand2",
            ).pack(fill="x", pady=(7, 0))
            if mode == "gpu":
                tk.Label(
                    inner,
                    text="ALERTA: a instalação GPU pode levar horas, exige internet estável e pode falhar em algumas placas. Use quando puder esperar.",
                    bg=bg,
                    fg=RED,
                    font=("Segoe UI", 9, "bold"),
                    wraplength=500,
                    justify="center",
                    cursor="hand2",
                ).pack(fill="x", pady=(8, 0))
            clickable = [outer, inner]
            for child in inner.winfo_children():
                clickable.append(child)
                clickable.extend(child.winfo_children())
            for widget in clickable:
                widget.bind("<Button-1>", lambda _e, m=mode: self._sel_mode(m))
            self._card_frames[mode] = (outer, inner, color, bg)

        info_box = tk.Frame(cards, bg="#f7f8fa", padx=12, pady=10)
        info_box.pack(fill="x", pady=(0, 4))
        tk.Label(
            info_box,
            text="Você pode instalar agora a versão normal em CPU e migrar para a opção avançada Express GPU depois, pela tela principal do Vozara.",
            bg="#f7f8fa",
            fg="#536675",
            font=("Segoe UI", 10),
            wraplength=520,
            justify="center",
        ).pack(fill="x")

        self.mode = default_mode
        self.btn.configure(state="normal", text="Instalar", command=self._page_install)

    def _sel_mode(self, mode):
        self.mode = mode
        self._mode_var.set(mode)
        for m, (outer, inner, color, bg) in self._card_frames.items():
            outer.configure(bg=color if m == mode else "#e0e0e0")
            inner.configure(bg=bg if m == mode else "#fafafa")

    def _page_install(self):
        self._clear()
        self.lbl_step.configure(text="4 / 4")
        self.btn.configure(state="disabled", text="Instalando...")
        self.install_failed = False
        self._last_progress = ""
        f = self.body

        mode_txt = "GPU NVIDIA" if self.mode == "gpu" else "CPU"
        lbl(f, f"Instalando em modo {mode_txt}", 14, bold=True).pack(pady=(20, 4))
        lbl(f, "Não feche esta janela. Se a internet cair, o instalador tentará novamente.", 10, color=GRAY).pack()
        if self.mode == "gpu":
            alert = tk.Frame(f, bg=RED, padx=1, pady=1)
            alert.pack(fill="x", padx=34, pady=(8, 0))
            alert_inner = tk.Frame(alert, bg=ALERT_BG, padx=10, pady=8)
            alert_inner.pack(fill="x")
            tk.Label(
                alert_inner,
                text="ALERTA: Transcrição Express (GPU) pode demorar horas para instalar",
                font=("Segoe UI", 10, "bold"),
                bg=ALERT_BG,
                fg=RED,
            ).pack(anchor="w")
            tk.Label(
                alert_inner,
                text="Este modo baixa PyTorch CUDA e bibliotecas NVIDIA grandes. Pode apresentar mais erros de compatibilidade. Depois de instalado, a transcrição tende a ficar bem mais rápida.",
                font=("Segoe UI", 9),
                bg=ALERT_BG,
                fg=RED,
                wraplength=520,
                justify="left",
            ).pack(anchor="w", pady=(2, 0))
        sep(f)

        self._steps = [
            ("venv", "Preparar ambiente local do app"),
            ("base", "Instalar dependências fixadas"),
            ("torch", "Instalar PyTorch CUDA (pode demorar horas)" if self.mode == "gpu" else "Instalar PyTorch CPU"),
            ("nvidia", "Instalar bibliotecas NVIDIA grandes" if self.mode == "gpu" else "Validar modo CPU"),
            ("ffmpeg", "Validar FFmpeg incluído"),
            ("model", "Baixar modelo Whisper medium (~1,5 GB)"),
            ("config", "Salvar configuração"),
        ]
        self._step_widgets = {}
        box = tk.Frame(f, bg=BG)
        box.pack(fill="x", padx=40, pady=4)
        for key, text in self._steps:
            row = tk.Frame(box, bg=BG)
            row.pack(fill="x", pady=4)
            ic = tk.Label(row, text="○", font=("Segoe UI", 12), bg=BG, fg="#cccccc", width=2)
            ic.pack(side="left")
            lb = tk.Label(row, text=text, font=("Segoe UI", 11), bg=BG, fg="#aaaaaa", anchor="w")
            lb.pack(side="left", padx=6)
            self._step_widgets[key] = (ic, lb)

        self._lbl_status = lbl(f, "Iniciando...", 10, color=GRAY, wraplength=500, justify="center")
        self._lbl_status.pack(pady=(14, 0))
        progress_box = tk.Frame(f, bg="#eeeeee", padx=1, pady=1)
        progress_box.pack(fill="both", expand=True, padx=34, pady=(12, 10))
        progress_inner = tk.Frame(progress_box, bg="#fafafa")
        progress_inner.pack(fill="both", expand=True)
        tk.Label(
            progress_inner,
            text="Progresso detalhado",
            font=("Segoe UI", 9, "bold"),
            bg="#fafafa",
            fg=GRAY,
            anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 2))
        log_frame = tk.Frame(progress_inner, bg="#fafafa")
        log_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._log_text = tk.Text(
            log_frame,
            height=6,
            bg="#fafafa",
            fg="#333333",
            relief="flat",
            wrap="word",
            font=("Consolas", 9),
            state="disabled",
        )
        self._log_text.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(log_frame, command=self._log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self._log_text.configure(yscrollcommand=scrollbar.set)
        self._append_progress("Aguardando início da instalação...")
        threading.Thread(target=self._do_install, daemon=True).start()

    def _append_progress(self, text: str):
        clean = _clean_output_line(text)
        if not clean or clean == self._last_progress:
            return
        self._last_progress = clean

        def write():
            if not hasattr(self, "_log_text") or not self._log_text.winfo_exists():
                return
            self._log_text.configure(state="normal")
            self._log_text.insert("end", clean + "\n")
            lines = int(self._log_text.index("end-1c").split(".")[0])
            if lines > 140:
                self._log_text.delete("1.0", f"{lines - 140}.0")
            self._log_text.configure(state="disabled")
            self._log_text.see("end")

        self.root.after(0, write)

    def _run_with_progress(self, cmd: list[str], attempts: int = 3, timeout: int | None = None) -> tuple[bool, str]:
        return _run_retry_stream(cmd, attempts=attempts, timeout=timeout, on_output=self._append_progress)

    def _upd_step(self, key, state, status=None):
        cfg = {
            "run": ("›", BLUE, DARK),
            "ok": ("✓", GREEN, GREEN),
            "skip": ("-", GRAY, GRAY),
            "err": ("×", RED, RED),
        }
        sym, ic_c, lb_c = cfg[state]
        ic, lb = self._step_widgets[key]
        self.root.after(0, lambda: ic.configure(text=sym, fg=ic_c))
        self.root.after(0, lambda: lb.configure(fg=lb_c))
        if status:
            self.root.after(0, lambda: self._lbl_status.configure(text=status, fg=lb_c if state == "err" else GRAY))

    def _fatal(self, key, msg):
        self.install_failed = True
        self._upd_step(key, "err", f"{msg}\nLog técnico: {LOG_FILE}")
        self.root.after(0, lambda: self.btn.configure(state="normal", text="Tentar novamente", command=self._page_install))

    def _do_install(self):
        self._upd_step("venv", "run", "Criando ambiente virtual em LocalAppData...")
        self._append_progress("Preparando ambiente local do VozaraApp.")
        VENV.parent.mkdir(parents=True, exist_ok=True)
        if not PYTHONV.exists():
            ok, _ = _run_retry([str(bootstrap_python()), "-m", "venv", str(VENV)], attempts=2)
            if not ok:
                self._fatal("venv", "Não foi possível criar o ambiente local do app.")
                return
        ok, _ = self._run_with_progress([str(PYTHONV), "-m", "pip", "install", "--upgrade", "pip", "--progress-bar", "raw"], attempts=2)
        if not ok:
            self._fatal("venv", "Não foi possível atualizar o instalador de pacotes.")
            return
        self._upd_step("venv", "ok")

        self._upd_step("base", "run", "Instalando faster-whisper, CustomTkinter e dependências fixadas...")
        if REQUIREMENTS_BASE.exists():
            cmd = [str(PYTHONV), "-m", "pip", "install", "-r", str(REQUIREMENTS_BASE), "--progress-bar", "raw"]
        else:
            cmd = [str(PYTHONV), "-m", "pip", "install", "faster-whisper==1.2.1", "customtkinter==5.2.2", "--progress-bar", "raw"]
        ok, _ = self._run_with_progress(cmd, attempts=3)
        if not ok:
            self._fatal("base", "Falha ao instalar dependências principais. Verifique a internet.")
            return
        self._upd_step("base", "ok")

        torch_status = (
            "Baixando e instalando PyTorch CUDA. Esse passo pode parecer travado e pode levar horas em internet lenta; depois disso, a transcrição com GPU fica bem mais rápida."
            if self.mode == "gpu"
            else "Instalando PyTorch CPU. Esse modo costuma instalar mais rápido e funciona em mais computadores."
        )
        self._upd_step("torch", "run", torch_status)
        if self.mode == "gpu":
            torch_cmd = [str(PYTHONV), "-m", "pip", "install", "-r", str(REQUIREMENTS_GPU), "--progress-bar", "raw"]
        else:
            torch_cmd = [str(PYTHONV), "-m", "pip", "install", "-r", str(REQUIREMENTS_CPU), "--progress-bar", "raw"]
        ok, _ = self._run_with_progress(torch_cmd, attempts=3)
        if not ok:
            self._fatal("torch", "Falha ao instalar PyTorch. Verifique conexão e espaço em disco.")
            return
        self._upd_step("torch", "ok")

        if self.mode == "gpu":
            self._upd_step("nvidia", "run", "Instalando bibliotecas NVIDIA. São pacotes grandes; aguarde mesmo se parecer parado.")
            ok, _ = self._run_with_progress([str(PYTHONV), "-m", "pip", "install", "-r", str(REQUIREMENTS_NVIDIA), "--progress-bar", "raw"], attempts=3)
            if not ok:
                self._fatal("nvidia", "Falha ao instalar bibliotecas NVIDIA. Use CPU ou atualize o driver.")
                return
            self._upd_step("nvidia", "ok")
        else:
            self._upd_step("nvidia", "skip", "Modo CPU selecionado.")

        self._upd_step("ffmpeg", "run", "Validando FFmpeg...")
        if not ffmpeg_available():
            self._fatal("ffmpeg", "FFmpeg não está incluído. Rode scripts\\prepare_distribution.ps1 antes de compilar o instalador.")
            return
        self._upd_step("ffmpeg", "ok")

        self._upd_step("model", "run", "Baixando modelo Whisper medium. Esse passo pode demorar...")
        ok, _ = self._run_with_progress([
            str(PYTHONV),
            "-c",
            "print('Preparando download do modelo Whisper medium...', flush=True); from faster_whisper import WhisperModel; WhisperModel('medium', device='cpu', compute_type='int8'); print('Modelo Whisper medium pronto.', flush=True)",
        ], attempts=3, timeout=None)
        if not ok:
            self._fatal("model", "Falha ao baixar o modelo Whisper. Confira internet, antivírus e espaço livre.")
            return
        self._upd_step("model", "ok")

        self._upd_step("config", "run", "Salvando preferências...")
        config = {
            "preferred_mode": self.mode,
            "output_dir": str(DEFAULT_OUTPUT_DIR),
            "hf_home": str(HF_HOME),
            "installed_at": datetime.now().isoformat(timespec="seconds"),
            "app_dir": str(BASE),
        }
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self._upd_step("config", "ok", "Instalação concluída. Abrindo aplicativo...")
        self.root.after(1200, self._launch)

    def _launch(self):
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        subprocess.Popen([str(PYTHONW), str(BASE / "app.py")], creationflags=creationflags)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    SetupWindow().run()
