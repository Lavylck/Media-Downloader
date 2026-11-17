# Media Downloader V1

Aplicativo desktop Windows para analisar mídias suportadas pelo yt-dlp e baixar
**MP4** ou extrair **MP3**, com interface PySide6 em português.

## Recursos

- Análise, transferência e processamento em segundo plano.
- Título, duração quando informada pela fonte e qualidades realmente disponíveis.
- Melhor qualidade selecionada automaticamente; seleção de resolução/bitrate
  da fonte inferior quando disponível.
- Vídeo e áudio combinados; MP4 por remux sem recodificação quando possível,
  conversão com FFmpeg quando necessária. MP3 VBR de alta qualidade.
- Pasta de destino, progresso, erros, cancelamento e fechamento seguro.
- Nomes compatíveis com Windows; arquivo existente de mesma mídia/seleção
  preservado. Uma operação por janela; não há fila.

Conversões não aumentam a qualidade original. O bitrate exibido para MP3 é o
da **fonte**, não uma promessa de bitrate final.

## Instalação (PowerShell, na raiz do projeto)

Requisitos: Python 3.13, FFmpeg **e FFprobe** no PATH e Node >=22 ou Deno >=2.3.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m media_downloader.diagnostics
```

Se `.venv` já existe, reutilize-a e execute apenas os dois últimos comandos.
Não é necessário ativar o ambiente nem alterar ExecutionPolicy.

### Dependências externas

- [FFmpeg](https://ffmpeg.org/download.html): no Windows, builds indicados no site,
  incluindo Gyan. Adicione a pasta `bin` com `ffmpeg.exe` e `ffprobe.exe` ao PATH.
  O pacote Python `ffmpeg-python` **não instala esses executáveis e não é usado**.
- [Node](https://nodejs.org/en/download) >=22 é detectado e habilitado
  automaticamente. Alternativamente, [Deno](https://docs.deno.com/runtime/getting_started/installation/)
  >=2.3. Se Node compatível já estiver instalado, Deno é opcional.
- `yt-dlp[default]` instala EJS compatível com a versão fixada.
  Referência: [guia oficial EJS](https://github.com/yt-dlp/yt-dlp/wiki/EJS).
- Não há instalação automática global nem download de componentes em tempo
  de execução. Após instalar binários, reabra o terminal para atualizar o PATH.

Ambiente validado: Python 3.13.17, PySide6 6.12.0, yt-dlp 2026.10.26,
EJS 0.8.0, FFmpeg/FFprobe 9.0.2 e Node 26.13.1.

## Executar

```powershell
.\.venv\Scripts\python.exe -m media_downloader.main
```

1. Cole a URL HTTP/HTTPS de uma mídia individual e clique **Analisar**.
2. Confira as informações; escolha MP4 ou MP3 e a qualidade da fonte.
3. Escolha a pasta e clique **Baixar**.
4. A conclusão exibe o caminho real do arquivo final.

Durante download de faixas separadas o percentual é por transferência e pode
reiniciar ao trocar de faixa. Durante análise, tamanho desconhecido e conversão,
a barra fica indeterminada. **100% significa processamento concluído**.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s media_downloader/tests -v
.\.venv\Scripts\python.exe -m pip check
```

A suíte cobre imports, URLs inválidas, falhas, atraso de rede, timers Qt,
progresso, exclusão de operações simultâneas, limpeza/cancelamento, HTTP local
real, combinação DASH, conversão de codecs incompatíveis, MP3, duplicatas,
nomes Windows e arquivos conferidos com FFprobe.

Para executar com janelas nativas:

```powershell
$env:QT_QPA_PLATFORM = 'windows'
.\.venv\Scripts\python.exe -m unittest discover -s media_downloader/tests -v
Remove-Item Env:QT_QPA_PLATFORM
```

Validação externa opcional (baixa amostra pública e salva em `test-artifacts/`):

```powershell
.\.venv\Scripts\python.exe -m media_downloader.tests.public_smoke
.\.venv\Scripts\python.exe -m media_downloader.tests.public_smoke --url 'https://www.youtube.com/watch?v=jNQXAC9IVRw' --video-height 144
```

## Limites da V1

- URLs individuais, sem playlists, transmissões ao vivo ou DRM.
- Disponibilidade, restrições de acesso, geolocalização e alterações dos sites
  dependem da fonte/yt-dlp. Não é garantido suporte a todos os sites.
- Algumas URLs diretas não fornecem duração ou resolução na análise; nesses
  casos a UI informa a ausência em vez de inventar metadados.
- Cancelamento é cooperativo. Uma chamada de rede aguarda seu timeout; FFmpeg
  já iniciado termina a etapa atual antes de encerrar. A janela permanece
  responsiva e aberta até a limpeza segura. Parciais podem ser retomados.
- Preservação de duplicatas usa o nome final (ID, seleção e formato).
  Não há deduplicação global entre janelas nem verificação de conteúdo de um
  arquivo já existente não vazio. Evite duas instâncias na mesma pasta.
- Sem instalador/executável standalone; execução pelo ambiente Python.

### Validação visual curta

Inicie normalmente, analise uma URL acessível, mova/redimensione a janela
durante a análise, use **Escolher…**, baixe MP4 e MP3 e reproduza os arquivos.
Experimente cancelar e fechar durante uma operação. A automação verifica
widgets/eventos/arquivos, mas não substitui a avaliação visual e auditiva humana.

## Continuidade e GitHub

`AUDIT.md`: diagnóstico inicial e recuperação.
`PROGRESS.md`: evidências e estado real.
`AGENTS.md`: arquitetura e regras para futuras alterações.

O Git local foi preservado. A publicação deve ser **privada** e exige autorização
do proprietário antes de criar repositório remoto ou executar push.
