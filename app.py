import json
import logging
import os
import queue
import re
import subprocess
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from hardware import detect_gpu_info
from core import (
    Transcriber,
    detect_device,
    estimate_transcription_seconds,
    format_duration,
    media_duration_seconds,
)
from paths import BASE, CONFIG_FILE, DEFAULT_OUTPUT_DIR, LOG_FILE, PYTHONV, REQUIREMENTS_GPU, REQUIREMENTS_NVIDIA, apply_runtime_environment

apply_runtime_environment()

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger("transcrever")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
BRAND_BLUE = "#16324F"
BRAND_GREEN = "#00A7A5"
BRAND_YELLOW = "#F2B84B"
BRAND_BG = "#F7F8FA"
BRAND_TEXT = "#536675"
ICON_FILE = BASE / "assets" / "icon.ico"

EXTENSOES = (
    "*.ogg", "*.opus", "*.mp3", "*.m4a", "*.wav", "*.aac",
    "*.mp4", "*.mkv", "*.avi", "*.webm", "*.mov",
)


def _clean_output_line(line: str) -> str:
    return ANSI_RE.sub("", line).strip()


def _run_stream(cmd: list[str], on_output=None) -> tuple[bool, str]:
    logger.info("Executando upgrade Express: %s", " ".join(map(str, cmd)))
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
            logger.info("[upgrade-express] %s", line)
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
        returncode = proc.wait()
        output = "\n".join(output_lines)
        if returncode != 0:
            logger.error("Upgrade Express falhou (%s): %s", returncode, output[-4000:])
        return returncode == 0, output
    except Exception as exc:
        logger.exception("Erro no upgrade Express")
        return False, str(exc)


def _cuda_validation_cmd() -> list[str]:
    return [
        str(PYTHONV),
        "-c",
        "import torch; print('CUDA available:', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'GPU unavailable')",
    ]


def _output_has_cuda(output: str) -> bool:
    return "CUDA available: True" in output

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


def _load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config(config: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def _unique_output_path(folder: Path, stem: str, suffix: str) -> Path:
    candidate = folder / f"{stem}{suffix}"
    i = 2
    while candidate.exists():
        candidate = folder / f"{stem} ({i}){suffix}"
        i += 1
    return candidate


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("VozaraApp")
        self.geometry("900x760")
        self.minsize(820, 700)
        self.configure(fg_color=BRAND_BG)
        if ICON_FILE.exists():
            try:
                self.iconbitmap(str(ICON_FILE))
            except Exception:
                logger.exception("Nao foi possivel carregar icone da janela principal")

        self.config_data = _load_config()
        self.device = "cpu"
        self.compute_type = "int8"
        self.running = False
        self.paused = False
        self.upgrading_gpu = False
        self.gpu_info = detect_gpu_info()
        self.upgrade_window = None
        self.upgrade_log = None
        self.upgrade_progress = None
        self.upgrade_close_btn = None
        self.upgrade_finished = False

        self.audios: list[Path] = []
        self.file_rows: dict[str, dict] = {}
        self.file_meta: dict[str, dict] = {}
        self.failed_paths: list[Path] = []

        self.pasta_saida = Path(self.config_data.get("output_dir") or DEFAULT_OUTPUT_DIR)
        self.pasta_saida.mkdir(parents=True, exist_ok=True)

        self.q: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()

        self._build_ui()
        self._detect_device_async()
        self.after(100, self._poll)
        logger.info("Aplicativo iniciado")

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=BRAND_BLUE, height=92, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        mark = tk.Canvas(header, width=50, height=50, bg=BRAND_BLUE, bd=0, highlightthickness=0)
        mark.place(x=24, rely=0.5, anchor="w")
        mark.create_oval(4, 4, 46, 46, fill=BRAND_GREEN, outline="")
        mark.create_arc(14, 12, 36, 38, start=300, extent=240, style="arc", outline="white", width=5)
        mark.create_oval(33, 8, 43, 18, fill=BRAND_YELLOW, outline="")

        ctk.CTkLabel(
            header,
            text="Vozara",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="white",
        ).place(x=88, y=27, anchor="w")
        ctk.CTkLabel(
            header,
            text="transcrição local de áudio e vídeo",
            font=ctk.CTkFont(size=12),
            text_color="#d7eef0",
        ).place(x=90, y=58, anchor="w")

        self.lbl_device = ctk.CTkLabel(
            header,
            text="Detectando dispositivo...",
            font=ctk.CTkFont(size=12),
            text_color=BRAND_YELLOW,
            anchor="e",
            wraplength=360,
        )
        self.lbl_device.place(relx=1, rely=0.5, anchor="e", x=-24)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=18, pady=14)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        frame_mode = ctk.CTkFrame(main, fg_color="#ffffff", corner_radius=8)
        frame_mode.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        frame_mode.grid_columnconfigure(0, weight=1)

        self.lbl_mode_hint = ctk.CTkLabel(
            frame_mode,
            text="Modo atual: Transcrição Rápida (CPU). O Express GPU pode ser ativado depois.",
            font=ctk.CTkFont(size=12),
            text_color=BRAND_TEXT,
            wraplength=610,
            justify="left",
        )
        self.lbl_mode_hint.grid(row=0, column=0, sticky="ew", padx=14, pady=12)

        self.btn_upgrade = ctk.CTkButton(
            frame_mode,
            text="Ativar Express GPU",
            command=self._upgrade_to_express,
            width=165,
            height=34,
            fg_color=BRAND_GREEN,
            hover_color="#008c8a",
        )
        self.btn_upgrade.grid(row=0, column=1, sticky="e", padx=14, pady=12)
        self._refresh_upgrade_button()

        frame_add = ctk.CTkFrame(main, fg_color="transparent")
        frame_add.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        frame_add.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            frame_add,
            text="+  Adicionar Arquivos",
            command=self._adicionar_arquivos,
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#3d91d5",
            hover_color="#2878b9",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            frame_add,
            text="Repetir erros",
            command=self._retry_errors,
            width=120,
            height=38,
            fg_color="#546e7a",
            hover_color="#37474f",
        ).grid(row=0, column=1, padx=(0, 8))

        ctk.CTkButton(
            frame_add,
            text="Limpar",
            command=self._limpar_lista,
            width=100,
            height=38,
            fg_color="#e53935",
            hover_color="#b71c1c",
        ).grid(row=0, column=2)

        frame_lista = ctk.CTkFrame(main, fg_color="#ffffff", corner_radius=8)
        frame_lista.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        frame_lista.grid_columnconfigure(0, weight=1)
        frame_lista.grid_rowconfigure(1, weight=1)

        self.lbl_fila = ctk.CTkLabel(
            frame_lista,
            text="Nenhum arquivo adicionado",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.lbl_fila.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        self.scroll = ctk.CTkScrollableFrame(frame_lista, height=150, fg_color="#f1f3f5", corner_radius=8)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        frame_dest = ctk.CTkFrame(main, fg_color="transparent")
        frame_dest.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        frame_dest.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame_dest, text="Salvar em:", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0, 8), sticky="w")

        self.entry_destino = ctk.CTkEntry(frame_dest, font=ctk.CTkFont(size=12), state="readonly")
        self.entry_destino.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self._set_entry_destino(self.pasta_saida)

        ctk.CTkButton(
            frame_dest,
            text="Alterar",
            command=self._escolher_destino,
            width=70,
            height=30,
            fg_color="#546e7a",
            hover_color="#37474f",
        ).grid(row=0, column=2)

        frame_prog = ctk.CTkFrame(main, fg_color="transparent")
        frame_prog.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        frame_prog.grid_columnconfigure(0, weight=1)

        self.lbl_prog = ctk.CTkLabel(frame_prog, text="0 / 0 arquivos", font=ctk.CTkFont(size=12))
        self.lbl_prog.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.progressbar = ctk.CTkProgressBar(frame_prog, height=14, corner_radius=7)
        self.progressbar.grid(row=1, column=0, sticky="ew")
        self.progressbar.set(0)

        self.lbl_status = ctk.CTkLabel(
            main,
            text="Adicione arquivos para começar.",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            wraplength=820,
        )
        self.lbl_status.grid(row=5, column=0, sticky="ew", pady=(4, 8))

        frame_btns = ctk.CTkFrame(main, fg_color="transparent")
        frame_btns.grid(row=6, column=0, sticky="ew", pady=(0, 10))
        frame_btns.grid_columnconfigure(0, weight=1)

        self.btn_start = ctk.CTkButton(
            frame_btns,
            text="▶  Iniciar Transcrição",
            command=self._start,
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#3d91d5",
            hover_color="#2878b9",
        )
        self.btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.btn_pause = ctk.CTkButton(
            frame_btns,
            text="Pausar",
            command=self._toggle_pause,
            width=95,
            height=44,
            state="disabled",
            fg_color="#546e7a",
            hover_color="#37474f",
        )
        self.btn_pause.grid(row=0, column=1, padx=(0, 8))

        self.btn_cancel = ctk.CTkButton(
            frame_btns,
            text="Cancelar",
            command=self._cancel,
            width=100,
            height=44,
            state="disabled",
            fg_color="#e53935",
            hover_color="#b71c1c",
        )
        self.btn_cancel.grid(row=0, column=2, padx=(0, 8))

        ctk.CTkButton(
            frame_btns,
            text="Abrir Saída",
            command=self._abrir_saida,
            width=110,
            height=44,
            fg_color="#2e7d32",
            hover_color="#1b5e20",
        ).grid(row=0, column=3)

        footer = ctk.CTkFrame(main, fg_color="transparent")
        footer.grid(row=7, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            footer,
            text="feito no ódio por @deimersonmoreira · instagram.com/deimersonmoreira",
            font=ctk.CTkFont(size=11),
            text_color=BRAND_TEXT,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            footer,
            text="Copiar diagnóstico",
            command=self._copy_diagnostics,
            height=28,
            width=150,
            fg_color="#78909c",
            hover_color="#546e7a",
        ).grid(row=0, column=1, sticky="e")

    def _refresh_upgrade_button(self):
        if not hasattr(self, "btn_upgrade"):
            return
        if self.upgrading_gpu:
            self.btn_upgrade.configure(text="Instalando Express...", state="disabled")
            return
        if self.device == "cuda":
            self.btn_upgrade.configure(text="Express GPU ativo", state="disabled")
            self.lbl_mode_hint.configure(text="Modo atual: Transcrição Express (GPU NVIDIA). As transcrições tendem a ficar mais rápidas.")
            return
        if self.gpu_info.get("vendor") != "nvidia":
            self.btn_upgrade.configure(text="Express indisponível", state="disabled")
            self.lbl_mode_hint.configure(text="Modo atual: Transcrição Rápida (CPU). Express GPU exige placa NVIDIA compatível.")
            return
        self.btn_upgrade.configure(text="Ativar Express GPU", state="normal")
        self.lbl_mode_hint.configure(text="Modo atual: Transcrição Rápida (CPU). Você pode ativar Express GPU depois, se puder aguardar a instalação.")

    def _upgrade_to_express(self):
        if self.upgrading_gpu:
            messagebox.showinfo("Upgrade em andamento", "O Express GPU já está sendo instalado.")
            return
        if self.running:
            messagebox.showwarning("Aguarde", "Conclua ou cancele a transcrição atual antes de ativar o Express GPU.")
            return
        self.gpu_info = detect_gpu_info()
        if self.gpu_info.get("vendor") != "nvidia":
            messagebox.showwarning(
                "GPU NVIDIA não detectada",
                "O Express GPU precisa de uma placa NVIDIA compatível com CUDA.\n\nEste computador continuará usando CPU.",
            )
            self._refresh_upgrade_button()
            return
        if not PYTHONV.exists():
            messagebox.showerror("Ambiente não encontrado", "Não encontrei o Python interno do VozaraApp para instalar o Express GPU.")
            return

        name = self.gpu_info.get("name") or "GPU NVIDIA"
        ok = messagebox.askyesno(
            "Ativar Transcrição Express?",
            (
                f"GPU detectada: {name}\n\n"
                "O Express GPU baixa PyTorch CUDA e bibliotecas NVIDIA grandes. "
                "Isso pode levar horas, exigir internet estável e apresentar mais erros de compatibilidade.\n\n"
                "Se falhar, o VozaraApp continuará funcionando em CPU.\n\n"
                "Deseja iniciar o upgrade agora?"
            ),
        )
        if not ok:
            return

        self._open_upgrade_window(name)
        self.upgrading_gpu = True
        self.upgrade_finished = False
        self._refresh_upgrade_button()
        threading.Thread(target=self._upgrade_worker, daemon=True).start()

    def _open_upgrade_window(self, gpu_name: str):
        self.upgrade_window = ctk.CTkToplevel(self)
        self.upgrade_window.title("Ativar Transcrição Express")
        self.upgrade_window.geometry("620x460")
        self.upgrade_window.resizable(False, False)
        self.upgrade_window.transient(self)
        self.upgrade_window.protocol("WM_DELETE_WINDOW", self._handle_upgrade_close)

        ctk.CTkLabel(
            self.upgrade_window,
            text="Transcrição Express (GPU NVIDIA)",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(pady=(18, 4))
        ctk.CTkLabel(
            self.upgrade_window,
            text=f"GPU detectada: {gpu_name}",
            font=ctk.CTkFont(size=12),
            text_color=BRAND_TEXT,
        ).pack(pady=(0, 10))

        alert = ctk.CTkFrame(self.upgrade_window, fg_color="#ffebee", border_color="#c62828", border_width=1, corner_radius=8)
        alert.pack(fill="x", padx=22, pady=(0, 10))
        ctk.CTkLabel(
            alert,
            text="ALERTA: esta instalação pode demorar horas e parecer parada em alguns momentos.",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#c62828",
            wraplength=540,
        ).pack(padx=12, pady=(10, 2))
        ctk.CTkLabel(
            alert,
            text="Depois de concluída, a transcrição tende a ficar mais rápida. Se falhar, o app mantém o modo CPU.",
            font=ctk.CTkFont(size=11),
            text_color="#c62828",
            wraplength=540,
        ).pack(padx=12, pady=(0, 10))

        self.upgrade_progress = ctk.CTkProgressBar(self.upgrade_window, mode="indeterminate", height=12)
        self.upgrade_progress.pack(fill="x", padx=22, pady=(0, 10))
        self.upgrade_progress.start()

        self.upgrade_log = ctk.CTkTextbox(self.upgrade_window, height=210, font=ctk.CTkFont(family="Consolas", size=11))
        self.upgrade_log.pack(fill="both", expand=True, padx=22, pady=(0, 12))
        self._append_upgrade_log("Iniciando upgrade para Express GPU...")

        self.upgrade_close_btn = ctk.CTkButton(
            self.upgrade_window,
            text="Instalando...",
            state="disabled",
            command=self.upgrade_window.destroy,
            height=34,
        )
        self.upgrade_close_btn.pack(pady=(0, 14))

    def _handle_upgrade_close(self):
        if self.upgrading_gpu and not self.upgrade_finished:
            messagebox.showwarning(
                "Instalação em andamento",
                "Aguarde o upgrade Express terminar. Fechar a janela agora pode deixar a instalação incompleta.",
            )
            return
        if self.upgrade_window and self.upgrade_window.winfo_exists():
            self.upgrade_window.destroy()

    def _append_upgrade_log(self, text: str):
        line = _clean_output_line(text)
        if not line:
            return

        def write():
            if not self.upgrade_log or not self.upgrade_log.winfo_exists():
                return
            self.upgrade_log.insert("end", line + "\n")
            self.upgrade_log.see("end")

        self.after(0, write)

    def _finish_upgrade(self, ok: bool, message: str):
        def update():
            self.upgrading_gpu = False
            self.upgrade_finished = True
            if self.upgrade_progress and self.upgrade_progress.winfo_exists():
                self.upgrade_progress.stop()
            self._append_upgrade_log(message)
            if self.upgrade_close_btn and self.upgrade_close_btn.winfo_exists():
                self.upgrade_close_btn.configure(text="Fechar", state="normal")
            self.lbl_status.configure(text=message)
            if ok:
                self.config_data["preferred_mode"] = "gpu"
                _save_config(self.config_data)
                messagebox.showinfo("Express GPU ativado", "Transcrição Express ativada. As próximas transcrições tentarão usar GPU.")
            else:
                self.config_data["preferred_mode"] = "cpu"
                _save_config(self.config_data)
                messagebox.showwarning("Express GPU não ativado", f"{message}\n\nO VozaraApp continuará funcionando em CPU.")
            self._detect_device_async()
            self._refresh_upgrade_button()

        self.after(0, update)

    def _upgrade_worker(self):
        def run_step(label: str, cmd: list[str], attempts: int = 3) -> bool:
            for attempt in range(1, attempts + 1):
                self._append_upgrade_log(f"{label} · tentativa {attempt}/{attempts}")
                ok, _ = _run_stream(cmd, on_output=self._append_upgrade_log)
                if ok:
                    return True
                self._append_upgrade_log(f"{label} falhou. Tentando novamente...")
            return False

        if not REQUIREMENTS_GPU.exists() or not REQUIREMENTS_NVIDIA.exists():
            self._finish_upgrade(False, "Arquivos de dependências GPU não foram encontrados no pacote instalado.")
            return

        self._append_upgrade_log("Verificando se CUDA já está disponível...")
        ok, output = _run_stream(_cuda_validation_cmd(), on_output=self._append_upgrade_log)
        if ok and _output_has_cuda(output):
            self._finish_upgrade(True, "Transcrição Express já estava disponível e foi ativada.")
            return

        pip_base = [str(PYTHONV), "-m", "pip", "install"]
        if not run_step("Instalando PyTorch CUDA", pip_base + ["--upgrade", "-r", str(REQUIREMENTS_GPU), "--progress-bar", "raw"]):
            self._finish_upgrade(False, "Falha ao instalar PyTorch CUDA. Verifique internet, espaço em disco e antivírus.")
            return

        if not run_step("Instalando bibliotecas NVIDIA", pip_base + ["--upgrade", "-r", str(REQUIREMENTS_NVIDIA), "--progress-bar", "raw"]):
            self._finish_upgrade(False, "Falha ao instalar bibliotecas NVIDIA. O modo CPU foi mantido.")
            return

        self._append_upgrade_log("Validando CUDA...")
        ok, output = _run_stream(_cuda_validation_cmd(), on_output=self._append_upgrade_log)
        if not ok or not _output_has_cuda(output):
            self._finish_upgrade(False, "Dependências instaladas, mas CUDA não ficou disponível. Atualize o driver NVIDIA ou continue em CPU.")
            return

        self._finish_upgrade(True, "Transcrição Express ativada com sucesso.")

    def _adicionar_arquivos(self):
        if self.running:
            return
        caminhos = filedialog.askopenfilenames(
            title="Selecionar arquivos de áudio ou vídeo",
            filetypes=[
                ("Áudios e Vídeos", " ".join(EXTENSOES)),
                ("Todos os arquivos", "*.*"),
            ],
        )
        for caminho in caminhos:
            self._add_audio(Path(caminho))
        self._update_fila_label()
        self._scan_durations_async()

    def _add_audio(self, audio: Path):
        key = str(audio.resolve())
        if key in self.file_rows:
            return
        self.audios.append(audio)
        self.file_meta[key] = {"duration": 0.0, "done": 0.0, "status": "waiting"}

        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.pack(fill="x", pady=2)

        name = ctk.CTkLabel(row, text=audio.name, anchor="w", font=ctk.CTkFont(size=12))
        name.pack(side="left", fill="x", expand=True)

        detail = ctk.CTkLabel(row, text="Aguardando análise", text_color="gray", width=180, anchor="e")
        detail.pack(side="left", padx=(8, 4))

        remove = ctk.CTkButton(
            row,
            text="×",
            width=28,
            height=24,
            command=lambda p=audio: self._remove_audio(p),
            fg_color="#eceff1",
            text_color="#263238",
            hover_color="#cfd8dc",
        )
        remove.pack(side="right")

        self.file_rows[key] = {"row": row, "detail": detail, "remove": remove}

    def _remove_audio(self, audio: Path):
        if self.running:
            return
        key = str(audio.resolve())
        row = self.file_rows.pop(key, {}).get("row")
        if row:
            row.destroy()
        self.file_meta.pop(key, None)
        self.audios = [p for p in self.audios if str(p.resolve()) != key]
        self.failed_paths = [p for p in self.failed_paths if str(p.resolve()) != key]
        self._update_fila_label()

    def _limpar_lista(self):
        if self.running:
            return
        self.audios.clear()
        self.file_rows.clear()
        self.file_meta.clear()
        self.failed_paths.clear()
        for widget in self.scroll.winfo_children():
            widget.destroy()
        self.lbl_prog.configure(text="0 / 0 arquivos")
        self.progressbar.set(0)
        self._update_fila_label()
        self.lbl_status.configure(text="Adicione arquivos para começar.")

    def _retry_errors(self):
        if self.running or not self.failed_paths:
            return
        errors = list(self.failed_paths)
        self._limpar_lista()
        for audio in errors:
            if audio.exists():
                self._add_audio(audio)
        self._update_fila_label()
        self._scan_durations_async()
        self._start()

    def _update_fila_label(self):
        n = len(self.audios)
        self.lbl_fila.configure(text=(
            "Nenhum arquivo adicionado" if n == 0 else
            "1 arquivo na fila" if n == 1 else
            f"{n} arquivos na fila"
        ))
        self.lbl_prog.configure(text=f"0 / {n} arquivos")
        self.progressbar.set(0)

    def _scan_durations_async(self):
        def _run():
            for audio in list(self.audios):
                key = str(audio.resolve())
                duration = media_duration_seconds(audio)
                estimate = estimate_transcription_seconds(duration, self.device)
                self.q.put(("duration", key, duration, estimate))
        threading.Thread(target=_run, daemon=True).start()

    def _escolher_destino(self):
        if self.running:
            return
        pasta = filedialog.askdirectory(title="Escolher pasta de destino", initialdir=str(self.pasta_saida))
        if pasta:
            self.pasta_saida = Path(pasta)
            self.pasta_saida.mkdir(parents=True, exist_ok=True)
            self.config_data["output_dir"] = str(self.pasta_saida)
            _save_config(self.config_data)
            self._set_entry_destino(self.pasta_saida)

    def _set_entry_destino(self, path: Path):
        self.entry_destino.configure(state="normal")
        self.entry_destino.delete(0, "end")
        self.entry_destino.insert(0, str(path))
        self.entry_destino.configure(state="readonly")

    def _abrir_saida(self):
        import os
        os.startfile(str(self.pasta_saida))

    def _start(self):
        if self.running:
            return
        if not self.audios:
            messagebox.showwarning("Sem arquivos", "Nenhum arquivo na fila.\n\nClique em Adicionar Arquivos para selecionar.")
            return

        self.running = True
        self.paused = False
        self.cancel_event.clear()
        self.failed_paths.clear()
        self.btn_start.configure(state="disabled", text="Transcrevendo...")
        self.btn_pause.configure(state="normal", text="Pausar")
        self.btn_cancel.configure(state="normal")
        for row in self.file_rows.values():
            row["remove"].configure(state="disabled")
        threading.Thread(target=self._worker, daemon=True).start()

    def _toggle_pause(self):
        if not self.running:
            return
        self.paused = not self.paused
        self.btn_pause.configure(text="Continuar" if self.paused else "Pausar")
        self.lbl_status.configure(text="Transcrição pausada." if self.paused else "Retomando transcrição...")

    def _cancel(self):
        if self.running:
            self.cancel_event.set()
            self.lbl_status.configure(text="Cancelando assim que o segmento atual terminar...")

    def _wait_if_paused(self):
        while self.paused and not self.cancel_event.is_set():
            time.sleep(0.2)

    def _worker(self):
        self.q.put(("status", "Carregando modelo Whisper medium..."))
        try:
            try:
                engine = Transcriber(self.device, self.compute_type)
            except Exception as exc:
                if self.device == "cuda":
                    logger.exception("Falha no modo GPU. Tentando CPU: %s", exc)
                    self.q.put(("device", "Dispositivo: CPU · fallback automático após falha da GPU", "#e65100"))
                    self.device, self.compute_type = "cpu", "int8"
                    engine = Transcriber("cpu", "int8")
                else:
                    raise
        except Exception as exc:
            logger.exception("Erro ao carregar modelo")
            self.q.put(("status", f"Erro ao carregar modelo: {exc}"))
            self.q.put(("done", "erro"))
            return

        total = len(self.audios)
        total_weight = sum(max(1.0, self.file_meta.get(str(p.resolve()), {}).get("duration", 0.0)) for p in self.audios)
        completed_weight = 0.0

        for i, audio in enumerate(list(self.audios)):
            if self.cancel_event.is_set():
                break

            key = str(audio.resolve())
            duration = max(1.0, self.file_meta.get(key, {}).get("duration", 0.0))
            self.q.put(("status", f"Transcrevendo {audio.name}..."))
            self.q.put(("file", key, "Transcrevendo...", "#1565c0"))
            logger.info("Transcrevendo: %s", audio)

            def on_segment(seg_end: float, _text: str, file_key=key, file_duration=duration):
                file_done = min(file_duration, max(0.0, seg_end))
                progress = min(1.0, (completed_weight + file_done) / total_weight)
                self.q.put(("progress", progress, i + 1, total))
                self.q.put(("file", file_key, f"{int((file_done / file_duration) * 100)}%", "#1565c0"))

            try:
                txt, srt = engine.transcribe(
                    audio,
                    on_segment=on_segment,
                    should_cancel=self.cancel_event.is_set,
                    wait_if_paused=self._wait_if_paused,
                )
                txt_path = _unique_output_path(self.pasta_saida, audio.stem, ".txt")
                srt_path = _unique_output_path(self.pasta_saida, audio.stem, ".srt")
                txt_path.write_text("\n".join(txt), encoding="utf-8")
                srt_path.write_text("\n".join(srt), encoding="utf-8")
                self.q.put(("file", key, "Concluído", "#2e7d32"))
                logger.info("Concluído: %s -> %s / %s", audio, txt_path, srt_path)
            except Exception as exc:
                if self.cancel_event.is_set():
                    self.q.put(("file", key, "Cancelado", "#e65100"))
                    logger.info("Cancelado: %s", audio)
                    break
                self.failed_paths.append(audio)
                self.q.put(("file", key, "Erro", "#c62828"))
                self.q.put(("status", f"Erro em {audio.name}: {exc}"))
                logger.exception("Erro em %s", audio)

            completed_weight += duration
            self.q.put(("progress", min(1.0, completed_weight / total_weight), i + 1, total))

        if self.cancel_event.is_set():
            self.q.put(("status", "Transcrição cancelada. Arquivos concluídos foram mantidos."))
            self.q.put(("done", "cancelado"))
        elif self.failed_paths:
            self.q.put(("status", f"Concluído com {len(self.failed_paths)} erro(s). Use Repetir erros."))
            self.q.put(("done", "erro"))
        else:
            self.q.put(("status", "Tudo concluído!"))
            self.q.put(("done", "ok"))

    def _detect_device_async(self):
        def _run():
            preferred = self.config_data.get("preferred_mode", "auto")
            device, compute_type, label = detect_device(preferred)
            self.device = device
            self.compute_type = compute_type
            color = "#1565c0" if device == "cuda" else "#e65100"
            self.q.put(("device", f"Dispositivo: {label}", color))
            self._scan_durations_async()
        threading.Thread(target=_run, daemon=True).start()

    def _copy_diagnostics(self):
        text = "\n".join([
            "Diagnóstico - VozaraApp",
            f"Dispositivo: {self.device} / {self.compute_type}",
            f"Pasta de saída: {self.pasta_saida}",
            f"Configuração: {CONFIG_FILE}",
            f"Log: {LOG_FILE}",
            f"Arquivos na fila: {len(self.audios)}",
            f"Erros na última execução: {len(self.failed_paths)}",
        ])
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Diagnóstico copiado", f"Diagnóstico copiado.\n\nLog técnico:\n{LOG_FILE}")

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "device":
                    self.lbl_device.configure(text=msg[1], text_color=msg[2])
                    self._refresh_upgrade_button()
                elif kind == "duration":
                    _, key, duration, estimate = msg
                    self.file_meta.setdefault(key, {})["duration"] = duration
                    row = self.file_rows.get(key)
                    if row:
                        row["detail"].configure(
                            text=f"{format_duration(duration)} · est. {format_duration(estimate)}",
                            text_color="gray",
                        )
                elif kind == "status":
                    self.lbl_status.configure(text=msg[1])
                elif kind == "file":
                    _, key, text, color = msg
                    row = self.file_rows.get(key)
                    if row:
                        row["detail"].configure(text=text, text_color=color)
                elif kind == "progress":
                    _, val, done, total = msg
                    self.progressbar.set(val)
                    self.lbl_prog.configure(text=f"{done} / {total} arquivos")
                elif kind == "done":
                    self.running = False
                    self.paused = False
                    self.btn_start.configure(state="normal", text="▶  Iniciar Transcrição")
                    self.btn_pause.configure(state="disabled", text="Pausar")
                    self.btn_cancel.configure(state="disabled")
                    for row in self.file_rows.values():
                        row["remove"].configure(state="normal")
        except queue.Empty:
            pass
        self.after(100, self._poll)


if __name__ == "__main__":
    MainWindow().mainloop()
