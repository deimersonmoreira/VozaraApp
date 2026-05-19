"""
Executado pelo desinstalador antes de remover os arquivos do aplicativo.
Remove dependências locais em LocalAppData e pergunta antes de apagar modelo e transcrições.
"""
import shutil
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from paths import CONFIG_FILE, DATA_DIR, DEFAULT_OUTPUT_DIR, HF_HOME, VENV


def _remove_dir(path: Path):
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _remove_file(path: Path):
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def main():
    root = tk.Tk()
    root.withdraw()

    remove_model = False
    if HF_HOME.exists() and any(HF_HOME.rglob("*")):
        remove_model = messagebox.askyesno(
            "Remover modelo Whisper?",
            "O modelo de IA Whisper (~1,5 GB) está salvo no cache local do aplicativo.\n\n"
            "Deseja removê-lo também?\n\n"
            "Sim: libera espaço em disco.\n"
            "Não: mantém o cache para uma futura reinstalação.",
        )

    remove_output = False
    if DEFAULT_OUTPUT_DIR.exists() and any(DEFAULT_OUTPUT_DIR.iterdir()):
        remove_output = messagebox.askyesno(
            "Remover transcrições?",
            f"A pasta de saída contém arquivos transcritos:\n{DEFAULT_OUTPUT_DIR}\n\n"
            "Deseja remover essa pasta e seu conteúdo?",
        )

    root.destroy()

    _remove_dir(VENV)
    if remove_model:
        _remove_dir(HF_HOME)
    if remove_output:
        _remove_dir(DEFAULT_OUTPUT_DIR)

    _remove_file(CONFIG_FILE)

    try:
        if DATA_DIR.exists() and not any(DATA_DIR.iterdir()):
            DATA_DIR.rmdir()
    except OSError:
        pass


if __name__ == "__main__":
    main()
