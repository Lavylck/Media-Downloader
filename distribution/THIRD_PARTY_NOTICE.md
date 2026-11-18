# Componentes redistribuídos

O pacote onedir contém bibliotecas dinâmicas Qt/PySide6, Python, yt-dlp/EJS e suas
dependências. Os avisos e licenças encontrados nas distribuições instaladas
acompanham este arquivo em subpastas. `build-manifest.json` registra versões
e SHA256 dos executáveis externos efetivamente incluídos.

- Python: PSF license; https://www.python.org/downloads/source/
- Qt/PySide6/shiboken6: licenças LGPLv3/GPLv3 e componentes de terceiros nos
  avisos distribuídos. Fontes: https://download.qt.io/official_releases/QtForPython/
  e https://download.qt.io/official_releases/qt/
  As DLLs permanecem separadas e substituíveis. É permitida engenharia reversa
  para depurar modificações dos componentes LGPL.
- yt-dlp/EJS: Unlicense e avisos incorporados de dependências;
  https://github.com/yt-dlp/yt-dlp e https://github.com/yt-dlp/ejs
- Node.js: licença MIT e avisos de dependências em NODE-LICENSE.txt.
  Fonte da versão incluída: https://nodejs.org/dist/v26.13.1/node-v26.13.1.tar.xz
- FFmpeg/FFprobe: executáveis independentes, build Gyan **GPLv3**. Não são
  vinculados ao processo Python. FFMPEG-LICENSE e FFMPEG-README.txt preservam
  licença, configuração e referência exata ao fonte do fornecedor.
  Build: https://www.gyan.dev/ffmpeg/builds/
  Fonte FFmpeg deste build: https://github.com/FFmpeg/FFmpeg/commit/946fcce07b

Não remova estes avisos ao redistribuir. Para distribuição dos binários GPL,
disponibilize também o código-fonte correspondente e os materiais de build/
dependências nos termos da GPLv3; um pacote binário não substitui essa obrigação.
Esta entrega local preserva a proveniência; não contém um espelho completo
dos fontes de todas as dependências do build estático Gyan.

O compilador Inno Setup é ferramenta de build, não é instalado com o aplicativo.
Sua própria licença permanece na extração portátil em `.build-tools/InnoSetup`.
Nenhuma licença/cessão de direitos do código do aplicativo é inferida deste aviso.
