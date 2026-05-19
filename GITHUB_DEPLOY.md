# Publicação do VozaraApp no GitHub

Este projeto deve subir para o GitHub como **código-fonte**. O instalador `.exe` deve ir em **Releases**, não no repositório.

## 1. O que entra no GitHub

Arquivos esperados no repositório:

```text
.gitignore
README.md
BRANDING.md
GITHUB_DEPLOY.md
app.py
core.py
first_run.py
main.py
paths.py
uninstall.py
launcher.bat
build.iss
requirements-base.txt
requirements-cpu.txt
requirements-gpu.txt
requirements-nvidia.txt
scripts/prepare_distribution.ps1
assets/icon.svg
assets/logo.svg
assets/wordmark.svg
```

## 2. O que não entra no GitHub

Esses itens ficam fora do repositório pelo `.gitignore`:

```text
.venv/
vendor/
Transcrições/
.dist-tmp/
__pycache__/
*.exe
*.log
.claude/
```

## 3. Quando compilar

Compile o instalador **depois** que:

1. O app abrir localmente com:

```powershell
.\.venv\Scripts\python.exe app.py
```

2. O código estiver commitado no Git.
3. Você quiser gerar um instalador para teste ou release.

Para preparar dependências de build:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\prepare_distribution.ps1
```

Depois abra o `build.iss` no Inno Setup e clique em:

```text
Build > Compile
```

O instalador esperado é:

```text
Instalar - VozaraApp.exe
```

## 4. Criar repositório no GitHub

No GitHub, crie um repositório chamado:

```text
VozaraApp
```

Pode ser privado enquanto estiver em teste.

## 5. Enviar código

Depois de criar o repositório, rode:

```powershell
git remote add origin https://github.com/SEU_USUARIO/VozaraApp.git
git branch -M main
git push -u origin main
```

## 6. Publicar instalador em Releases

Depois de compilar com sucesso:

1. Abra o repositório no GitHub.
2. Vá em **Releases**.
3. Clique em **Create a new release**.
4. Tag sugerida:

```text
v1.0.0
```

5. Anexe:

```text
Instalar - VozaraApp.exe
```

6. Publique a release.

## 7. Observação importante

A primeira configuração do app ainda precisa de internet para baixar dependências Python, PyTorch e o modelo Whisper medium. Depois da configuração concluída, a transcrição roda localmente.
