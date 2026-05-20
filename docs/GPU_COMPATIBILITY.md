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
| 4 GB ou mais | Permite GPU, mas CPU segue como recomendacao inicial |
| Desconhecida | Permite GPU |
| Menos de 4 GB | Recomenda CPU, mas permite tentar GPU |

Placas MX costumam ter 2 GB de VRAM. Elas podem ser detectadas, mas o Whisper medium pode falhar por falta de memoria. Nesse caso, use CPU.

## Tempo de instalacao do modo GPU

O modo CPU e o recomendado para a maioria dos usuarios: instala mais rapido, tem menos chance de erro e funciona em mais computadores.

O modo GPU e opcional. Ele funciona como uma Transcricao Express depois de configurado, mas a primeira instalacao baixa PyTorch CUDA e bibliotecas NVIDIA grandes. Em conexoes lentas, computadores com disco lento ou antivirus ativo, essa etapa pode levar horas, parecer parada e apresentar mais erros de compatibilidade.

Oriente o usuario a escolher GPU apenas quando puder esperar. Se a prioridade for instalar rapido e testar o app sem risco, use CPU. Depois de instalado, o modo GPU nao precisa baixar esses pacotes novamente e a transcricao tende a ser bem mais rapida.

O usuario tambem pode instalar primeiro em CPU e ativar o Express GPU depois pela tela principal do app. Esse upgrade instala as dependencias CUDA/NVIDIA, valida `torch.cuda.is_available()` e so muda a configuracao para GPU se a validacao passar. Se falhar, o modo CPU permanece ativo.

## Dependencias baixadas na primeira configuracao

Na primeira configuracao, o app baixa:

- `faster-whisper`
- `torch` CPU ou CUDA
- `nvidia-cublas-cu12` e `nvidia-cudnn-cu12`, no modo GPU
- modelo Whisper medium

Isso reduz o que precisa estar pre-instalado no computador, mas exige internet na primeira configuracao.

## Instalador atual

- `build.iss`: instalador oficial, inclui Python interno e FFmpeg.
- O instalador online experimental foi removido por enquanto para evitar confusao e builds inconsistentes.
