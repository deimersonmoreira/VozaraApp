import json
import logging
import queue
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import (
    Transcriber,
    detect_device,
    estimate_transcription_seconds,
    format_duration,
    media_duration_seconds,
)
from paths import CONFIG_FILE, DEFAULT_OUTPUT_DIR, LOG_FILE, apply_runtime_environment

apply_runtime_environment()

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger("transcrever")

EXTENSOES = (
    "*.ogg", "*.opus", "*.mp3", "*.m4a", "*.wav", "*.aac",
    "*.mp4", "*.mkv", "*.avi", "*.webm", "*.mov",
)

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
        self.geometry("760x660")
        self.minsize(720, 620)

        self.config_data = _load_config()
        self.device = "cpu"
        self.compute_type = "int8"
        self.running = False
        self.paused = False

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
        ctk.CTkLabel(
            self,
            text="VozaraApp",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(20, 4))

        self.lbl_device = ctk.CTkLabel(
            self,
            text="Detectando dispositivo...",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.lbl_device.pack(pady=(0, 12))

        frame_add = ctk.CTkFrame(self, fg_color="transparent")
        frame_add.pack(fill="x", padx=22, pady=(0, 8))

        ctk.CTkButton(
            frame_add,
            text="+  Adicionar Arquivos",
            command=self._adicionar_arquivos,
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))

        ctk.CTkButton(
            frame_add,
            text="Repetir erros",
            command=self._retry_errors,
            width=120,
            height=38,
            fg_color="#546e7a",
            hover_color="#37474f",
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            frame_add,
            text="Limpar",
            command=self._limpar_lista,
            width=100,
            height=38,
            fg_color="#e53935",
            hover_color="#b71c1c",
        ).pack(side="left")

        frame_lista = ctk.CTkFrame(self)
        frame_lista.pack(fill="both", expand=True, padx=22, pady=(0, 10))

        self.lbl_fila = ctk.CTkLabel(
            frame_lista,
            text="Nenhum arquivo adicionado",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.lbl_fila.pack(anchor="w", padx=12, pady=(10, 4))

        self.scroll = ctk.CTkScrollableFrame(frame_lista, height=220)
        self.scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        frame_dest = ctk.CTkFrame(self, fg_color="transparent")
        frame_dest.pack(fill="x", padx=22, pady=(0, 8))

        ctk.CTkLabel(frame_dest, text="Salvar em:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))

        self.entry_destino = ctk.CTkEntry(frame_dest, font=ctk.CTkFont(size=12), state="readonly")
        self.entry_destino.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._set_entry_destino(self.pasta_saida)

        ctk.CTkButton(
            frame_dest,
            text="Alterar",
            command=self._escolher_destino,
            width=70,
            height=30,
            fg_color="#546e7a",
            hover_color="#37474f",
        ).pack(side="left")

        frame_prog = ctk.CTkFrame(self, fg_color="transparent")
        frame_prog.pack(fill="x", padx=22, pady=(0, 6))

        self.lbl_prog = ctk.CTkLabel(frame_prog, text="0 / 0 arquivos", font=ctk.CTkFont(size=12))
        self.lbl_prog.pack(anchor="w", pady=(0, 5))

        self.progressbar = ctk.CTkProgressBar(frame_prog, height=14, corner_radius=7)
        self.progressbar.pack(fill="x")
        self.progressbar.set(0)

        self.lbl_status = ctk.CTkLabel(
            self,
            text="Adicione arquivos para começar.",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            wraplength=700,
        )
        self.lbl_status.pack(pady=(8, 8))

        frame_btns = ctk.CTkFrame(self, fg_color="transparent")
        frame_btns.pack(fill="x", padx=22, pady=(0, 18))

        self.btn_start = ctk.CTkButton(
            frame_btns,
            text="▶  Iniciar Transcrição",
            command=self._start,
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 6))

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
        self.btn_pause.pack(side="left", padx=(0, 6))

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
        self.btn_cancel.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            frame_btns,
            text="Abrir Saída",
            command=self._abrir_saida,
            width=110,
            height=44,
            fg_color="#2e7d32",
            hover_color="#1b5e20",
        ).pack(side="left")

        ctk.CTkButton(
            self,
            text="Copiar diagnóstico",
            command=self._copy_diagnostics,
            height=28,
            width=150,
            fg_color="#78909c",
            hover_color="#546e7a",
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            self,
            text="feito no ódio por @deimersonmoreira · instagram.com/deimersonmoreira",
            font=ctk.CTkFont(size=11),
            text_color="#536675",
        ).pack(pady=(0, 10))

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
