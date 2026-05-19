"""
Ponto de entrada único do aplicativo.
Na distribuição final, roda com o Python embutido em runtime\python.
Se o ambiente local do app já existir, abre a interface; caso contrário, mostra o wizard.
"""
import subprocess
import os

from paths import BASE, PYTHONW, apply_runtime_environment, venv_installed


if __name__ == "__main__":
    apply_runtime_environment()
    if venv_installed():
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        subprocess.Popen([str(PYTHONW), str(BASE / "app.py")], creationflags=creationflags)
    else:
        from first_run import SetupWindow

        SetupWindow().run()
