# Media Downloader V3 — Cyberpunk Edition

Aplicativo desktop Windows para analisar mídias suportadas pelo yt-dlp e baixar
**MP4** ou extrair **MP3**, com interface PySide6 em português.

Esta evolução está na branch local **`feature/v3`**. V1 e V2 validadas manualmente
permanecem em `master` e `feature/v2`. A V3 não foi publicada no GitHub.

## Recursos

- Interface escura roxo neon, CTA grande centralizado e tema QSS local.
- Prévia assíncrona sem corte, mantendo a proporção da miniatura; cache de até 50 MiB.
- Fila sequencial com progresso por item, cancelar, remover e tentar novamente.
  Uma falha não bloqueia os itens seguintes. Análise de outro link pode ocorrer
  enquanto a fila baixa; cada item conserva formato, qualidade e destino.
- Playlists com seleção explícita, páginas de 100 itens e limites de qualidade
  por item. Nenhuma playlist começa a baixar sem seleção.
- Histórico SQLite com pesquisa, filtros, páginas de 25 registros, abrir arquivo/
  pasta, repetir e remover registro sem apagar a mídia.
- Cole uma URL ou pare de digitar: análise automática após **600 ms**.
  **Analisar** e Enter continuam disponíveis para antecipar ou forçar atualização.
- Análise, transferência e processamento em segundo plano.
- Título, duração quando informada pela fonte e qualidades realmente disponíveis.
- Melhor qualidade selecionada automaticamente; seleção de resolução/bitrate
  da fonte inferior quando disponível.
- Vídeo e áudio combinados; MP4 por remux sem recodificação quando possível,
  conversão com FFmpeg quando necessária. MP3 VBR de alta qualidade.
- Pasta de destino, progresso, erros, cancelamento e fechamento seguro.
- Nomes compatíveis com Windows; arquivo existente de mesma mídia/seleção
  preservado. Uma transferência por vez e uma instância por diretório de dados.
- Trocar o link durante análise invalida o resultado anterior, solicita
  cancelamento e analisa apenas o link mais recente após a limpeza da tarefa.
- Mesmo link, inclusive com espaços externos diferentes, não é reanalisado
  automaticamente. Depois de erro/cancelamento, use Analisar para tentar de novo.
- Botão Baixar só fica disponível com análise atual, qualidade e pasta informada.

Conversões não aumentam a qualidade original. O bitrate exibido para MP3 é o
da **fonte**, não uma promessa de bitrate final.

## Windows: executável e instalador

- Instalador: `dist/installer/MediaDownloader-3.0.0-Setup-x64.exe`.
- Portátil: `dist/MediaDownloader/MediaDownloader.exe`; mantenha toda a pasta
  e seu subdiretório `_internal`.
- Incluem Python, Qt, yt-dlp/EJS, Node, FFmpeg e FFprobe.
- Instalação por usuário, sem administrador, em
  `%LOCALAPPDATA%\Programs\MediaDownloader`. Atalho no menu Iniciar e opção de
  atalho na área de trabalho.
- Histórico, preferências, logs e cache: `%LOCALAPPDATA%\MediaDownloader`.
  Desinstalar preserva esses dados e os downloads.
- O ícone temporário preexistente foi mantido. **Integração do ícone oficial pendente.**
- Build local sem assinatura digital. Detalhes em `distribution/README_WINDOWS.md`.

## Execução pelo código-fonte (PowerShell, na raiz)

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

1. Cole a URL HTTP/HTTPS de uma mídia individual e aguarde a análise automática.
2. Confira as informações; escolha MP4 ou MP3 e a qualidade da fonte.
3. Escolha a pasta e clique **Baixar**.
4. A conclusão exibe o caminho real do arquivo final.

Você pode substituir o link durante a análise e configurar a próxima mídia
durante um download. O botão **+** aceita um link por linha, com melhor qualidade
no formato atual. Duplicatas ativas com URL/destino/formato/qualidade iguais são
ignoradas. Na aba **Fila**, acompanhe ou cancele cada item.

Para um link que contém vídeo e playlist, o padrão é analisar só o vídeo.
Escolha **Playlist — selecionar itens** para abrir a lista completa. Links que
retornam apenas uma playlist também mostram a seleção. **Selecionar todos**
carrega as páginas restantes; **Parar carregamento** conserva o que já foi
carregado. Após erro de página, **Carregar mais** permite tentar novamente.

Cancelar na aba Mídia cancela a análise atual ou, sem análise, o download atual.
Para cancelar todos os downloads, use **Cancelar toda a fila**. Fechar cancela
a fila e aguarda a limpeza segura. Após encerramento inesperado, itens persistidos
ativos aparecem como **Interrompido**, sem reinício automático.

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
Os casos incluem Ctrl+V real, digitação com debounce, respostas obsoletas,
troca/cancelamento do link, ausência de reanálises redundantes, CTA e layout
em janela pequena, fila, paginação real de playlists, SQLite, miniaturas HTTP
e recuperação de erros. Resultados e tempos estão em `PROGRESS.md`.

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

O smoke usa colagem automática por padrão; `--manual` testa o botão.
`--screenshot test-artifacts/tela.png` salva a janela após a análise.

## Limites atuais

- Sem transmissões ao vivo, DRM ou captura automática de cookies.
- Disponibilidade, restrições de acesso, geolocalização e alterações dos sites
  dependem da fonte/yt-dlp. Não é garantido suporte a todos os sites.
- Algumas URLs diretas não fornecem duração ou resolução na análise; nesses
  casos a UI informa a ausência em vez de inventar metadados.
- Cancelamento é cooperativo. Uma chamada de rede aguarda seu timeout; FFmpeg
  já iniciado termina a etapa atual antes de encerrar. A janela permanece
  responsiva e aberta até a limpeza segura. Parciais podem ser retomados.
- Preservação de duplicatas usa o nome final (ID, seleção e formato);
  não verifica o conteúdo de um arquivo já existente não vazio.
- O download revalida metadados na fonte para evitar reutilizar URLs de mídia
  expiradas. URLs reconhecidas como assinadas/com credenciais não são persistidas;
  para repetir esses downloads, forneça um link novo.
- Recuperação da fila mostra até 1.000 itens interrompidos; os demais continuam
  pesquisáveis no histórico. Itens privados/indisponíveis podem falhar na fonte.
- O debounce evita disparos a cada tecla; uma pausa longa em um prefixo que já
  seja uma URL válida pode iniciar análise. Continue digitando para substituí-la.

### Validação visual curta

1. Inicie normalmente e cole um link: a barra/CTA devem indicar análise sem clique.
2. Mova/redimensione a janela; troque o link durante análise e confira que só o
   último resultado aparece. Cole o mesmo link pronto: não deve reanalisar.
3. Use Analisar/Enter para atualizar. Limpe a pasta: Baixar deve desabilitar.
4. Escolha pasta, qualidade e baixe MP4/MP3; confira hover/foco e mensagem final.
5. Experimente Cancelar e fechar durante uma tarefa; reproduza os arquivos.
6. Selecione uma playlist, pare/retome a paginação e escolha alguns itens.
7. Confira fila, filtros do histórico, repetição e reabertura do aplicativo.

Em telas pequenas há scroll vertical. V1 e V2 receberam aceite manual do usuário;
a experiência V3 ainda requer sua avaliação. A automação verifica eventos e arquivos,
sem substituir percepção visual/auditiva humana.

## Gerar e validar o pacote

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe scripts/build_windows.py --installer
.\.venv\Scripts\python.exe scripts/validate_windows.py --installer
```

O build usa ferramentas locais, coleta licenças/proveniência e obtém o compilador
Inno oficial em `.build-tools`, conferindo SHA256. A validação cria mídia sintética,
executa o pacote com PATH restrito, inspeciona arquivos com o FFprobe incluído e
testa instalação/reinstalação/desinstalação e preservação de dados. Não substitui
instalação/atalho preexistente do usuário. Relatórios ficam em `test-artifacts/`.
Não execute junto com outra suíte gráfica nativa.

## Continuidade e GitHub

`AUDIT.md`: diagnóstico inicial e recuperação.
`PROGRESS.md`: evidências e estado real.
`AGENTS.md`: regras específicas deste aplicativo.
`LESSONS_LEARNED.md`: incidentes reais, causas/evidências e prevenção.
`GLOBAL_AGENT_TEMPLATE.md`: instruções gerais adaptáveis para Qwen, Gemma e outros.
`PROJECT_BOOTSTRAP_CHECKLIST.md`: roteiro reutilizável de início, retomada e entrega.

O remoto privado existente é `Lavylck/Media-Downloader`. A etapa atual tem
apenas commits locais em `feature/v3`; push/merge exigem nova autorização.
