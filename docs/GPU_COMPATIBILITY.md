# Compatibilidade de GPU

O VozaraApp acelera transcricoes com **NVIDIA CUDA**. AMD, Intel e GPUs integradas usam CPU.

## Familias NVIDIA aceitas

O app tenta reconhecer as seguintes familias como NVIDIA/CUDA:

- GeForce RTX
- GeForce GTX
- GeForce MX
- RTX A / RTX Ada
- Quadro
- Tesla
- T-Series
- Titan
- NVS

## Recomendacao por VRAM

| VRAM | Decisao do app |
| --- | --- |
| 4 GB ou mais | Recomenda GPU |
| Desconhecida | Permite GPU |
| Menos de 4 GB | Recomenda CPU, mas permite tentar GPU |

Placas MX costumam ter 2 GB de VRAM. Elas podem ser detectadas, mas o Whisper medium pode falhar por falta de memoria. Nesse caso, use CPU.

## Dependencias baixadas na primeira configuracao

Na primeira configuracao, o app baixa:

- `faster-whisper`
- `torch` CPU ou CUDA
- `nvidia-cublas-cu12` e `nvidia-cudnn-cu12`, no modo GPU
- modelo Whisper medium

Isso reduz o que precisa estar pre-instalado no computador, mas exige internet na primeira configuracao.

## Instalador atual vs instalador online

- `build.iss`: instalador mais robusto, inclui Python interno e FFmpeg.
- `build-online.iss`: variante experimental menor; inclui o instalador do Python e FFmpeg, mas nao inclui o Python expandido.

Use `build.iss` para releases publicas ate a variante online ser testada em Windows limpo.
