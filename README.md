# VozaraApp

Aplicativo Windows para transcrever áudio e vídeo em português usando **Whisper medium** localmente. Depois da primeira configuração, os arquivos do usuário não são enviados para a internet.

**feito no ódio por [@deimersonmoreira](https://instagram.com/deimersonmoreira)**

> Importante: a primeira configuração precisa de internet para baixar dependências Python, PyTorch e o modelo Whisper medium (~1,5 GB). A transcrição em si roda localmente.

## Uso para o usuário final

1. Instale pelo arquivo `Instalar - VozaraApp.exe`.
2. Abra o atalho criado na Área de Trabalho ou no Menu Iniciar.
3. Na primeira abertura, aguarde o assistente configurar o app.
4. Clique em **Adicionar Arquivos** e selecione áudio ou vídeo.
5. Confira a pasta de saída em **Salvar em**.
6. Clique em **Iniciar Transcrição**.

As transcrições são salvas por padrão em:

```text
C:\Users\<usuario>\Documents\VozaraApp
```

Para cada arquivo, o app gera:

- `.txt` com texto puro.
- `.srt` com legenda e timestamps.

O app não move nem apaga os arquivos originais.

## Funcionalidades

- Transcrição local após a instalação inicial.
- Modo GPU NVIDIA com fallback automático para CPU.
- Modo CPU para qualquer computador compatível.
- Geração de `.txt` e `.srt`.
- Estimativa de duração e tempo de transcrição por arquivo.
- Progresso por segmento de áudio/vídeo.
- Pausar, continuar e cancelar transcrição.
- Repetir apenas arquivos que deram erro.
- Evita sobrescrever saídas existentes: cria `nome (2).txt`, `nome (3).txt`, etc.
- Configuração persistida entre aberturas.
- Log técnico e botão **Copiar diagnóstico** para suporte.

## Formatos suportados

| Tipo | Extensões |
| --- | --- |
| Áudio | `.ogg` `.opus` `.mp3` `.m4a` `.wav` `.aac` |
| Vídeo | `.mp4` `.mkv` `.avi` `.webm` `.mov` |

## Requisitos

### CPU

- Windows 10 ou 11 de 64 bits.
- 8 GB de RAM recomendado.
- 8 GB livres em disco para dependências, cache e modelo.

### GPU NVIDIA

- Windows 10 ou 11 de 64 bits.
- GPU NVIDIA dedicada com 4 GB ou mais de VRAM.
- Driver NVIDIA atualizado.
- 8 GB livres em disco.

Placas NVIDIA MX tambem podem ser detectadas, mas muitas tem 2 GB de VRAM. Nesses casos o VozaraApp recomenda CPU; o modo GPU pode ser tentado, mas pode falhar por falta de memoria com o Whisper medium.

## Onde o app grava arquivos

| Conteúdo | Pasta |
| --- | --- |
| Programa instalado | `%LOCALAPPDATA%\VozaraApp` |
| Ambiente Python do app | `%LOCALAPPDATA%\VozaraApp\.venv` |
| Configuração | `%LOCALAPPDATA%\VozaraApp\config.json` |
| Log técnico | `%LOCALAPPDATA%\VozaraApp\transcrever.log` |
| Cache/modelo Whisper | `%LOCALAPPDATA%\VozaraApp\huggingface` |
| Transcrições | `Documents\VozaraApp` |

Essa organização evita erros de permissão em `Program Files` e não exige administrador.

## Configurações do modelo

| Parâmetro | Valor |
| --- | --- |
| Modelo | Whisper `medium` |
| Idioma | Português (`pt`) |
| Tarefa | `transcribe` |
| Beam size | `5` |
| VAD filter | ativado |
| Silêncio mínimo | `500ms` |
| Contexto acumulado | desativado |

## Modos de execução

| Modo | `device` | `compute_type` | Estimativa |
| --- | --- | --- | --- |
| GPU NVIDIA | `cuda` | `float16` | 1-3 min por hora de áudio |
| CPU | `cpu` | `int8` | 10-30 min por hora de áudio |

Se o app tentar abrir em GPU e falhar, ele registra o erro e tenta CPU automaticamente.

## Estrutura do projeto

```text
main.py                     Entrada principal
paths.py                    Pastas do usuário, runtime e ambiente
core.py                     Motor Whisper, detecção de GPU, FFmpeg e progresso
app.py                      Interface principal
first_run.py                Assistente de primeira configuração
uninstall.py                Limpeza no desinstalador
launcher.bat                Atalho sem terminal
launcher.vbs                Launcher invisível usado pelos atalhos do Windows
build.iss                   Script Inno Setup
requirements-base.txt       Dependências Python fixadas
requirements-cpu.txt        PyTorch CPU fixado
requirements-gpu.txt        PyTorch CUDA fixado
requirements-nvidia.txt     Bibliotecas NVIDIA fixadas
scripts/prepare_distribution.ps1
assets/                     Logo, ícone e wordmark
assets/icon.ico             Ícone do atalho e instalador
```

## Gerar instalador distribuível

1. Instale o Inno Setup 6.
2. No PowerShell, dentro da pasta do projeto, rode:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\prepare_distribution.ps1
```

Esse script baixa/prepara:

- Python interno para o aplicativo.
- `ffmpeg.exe` e `ffprobe.exe` para serem empacotados junto do app.

3. Compile o `build.iss` manualmente pelo Inno Setup em **Build > Compile**.

O arquivo final será:

```text
Instalar - VozaraApp.exe
```

## Publicar no GitHub

Suba o código-fonte no repositório e publique o instalador final em **Releases**. Não versionar `.venv`, `vendor`, transcrições, instaladores ou caches.

## Assinatura digital

Para evitar aviso de “editor desconhecido” e reduzir alertas do SmartScreen:

```powershell
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a "Instalar - VozaraApp.exe"
signtool verify /pa /v "Instalar - VozaraApp.exe"
```

Mesmo assinado, o SmartScreen pode precisar de reputação conforme o app for baixado e usado.

## Desinstalação

Ao remover pelo Windows, o app:

1. Remove o ambiente Python local em `%LOCALAPPDATA%\VozaraApp\.venv`.
2. Pergunta se deseja remover o modelo Whisper.
3. Pergunta se deseja remover `Documents\VozaraApp`.
4. Remove a configuração local.
