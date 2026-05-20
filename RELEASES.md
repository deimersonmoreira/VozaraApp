# Releases

## v0.0.4 - restauracao e Express GPU

- Remove o `build-online.iss` experimental para manter apenas o instalador oficial.
- Alinha o `build.iss` para `AppVersion 0.0.4`.
- Restaura branding Vozara no wizard e no app principal.
- Mantem CPU como modo recomendado e Express GPU como upgrade opcional posterior.
- Inclui progresso detalhado na configuracao inicial e fluxo seguro de upgrade GPU.

## v0.0.3 - novo build compilado

- Instalador normal recompilado: `Instalar - VozaraApp.exe`.
- Instalador online experimental recompilado: `Instalar - VozaraApp Online.exe`.
- Mantem o launcher sem janela de console nas chamadas normais do app.
- Mantem icone do VozaraApp no instalador e nos atalhos.
- Inclui melhorias de deteccao de GPUs NVIDIA, incluindo linhas MX compativeis quando ha CUDA disponivel.

## v0.0.2 - build inicial

- Build inicial distribuivel do VozaraApp.
- Release com instalador completo para Windows 10 e Windows 11.
