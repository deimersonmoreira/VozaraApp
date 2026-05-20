# Fluxo de upgrade para Express GPU

Este fluxo permite instalar o VozaraApp primeiro em CPU e migrar depois para Express GPU pela tela principal do app.

## Rota feliz

1. Usuario instala em **Transcricao Rapida (CPU)** no wizard.
2. `first_run.py` salva `preferred_mode = cpu` em `config.json`.
3. `app.py` abre e mostra o botao **Ativar Express GPU** quando uma NVIDIA e detectada.
4. Usuario confirma o alerta.
5. `app.py` instala `requirements-gpu.txt`.
6. `app.py` instala `requirements-nvidia.txt`.
7. `app.py` valida `torch.cuda.is_available()`.
8. Somente se CUDA estiver disponivel, `app.py` salva `preferred_mode = gpu`.
9. As proximas transcricoes usam `core.detect_device("gpu")` e tentam `cuda/float16`.

## Rota de falha segura

Se qualquer etapa falhar:

- `preferred_mode` volta para `cpu`.
- O app continua funcionando em CPU.
- A janela de upgrade mostra o log da etapa que falhou.
- A transcricao principal nao e iniciada durante o upgrade.
- O usuario nao consegue iniciar dois upgrades ao mesmo tempo.

## Arquivos obrigatorios no instalador

- `app.py`
- `core.py`
- `hardware.py`
- `paths.py`
- `requirements-gpu.txt`
- `requirements-nvidia.txt`
- `requirements-cpu.txt`
- `requirements-base.txt`

Esses arquivos precisam estar incluidos no `build.iss`, que e o instalador oficial.
