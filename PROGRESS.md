# Estado do projeto — V3 concluída e validada localmente

## Auditoria e estabilização V3 — 2026-11-18

### Continuidade e estado recebido

- Branch `feature/v3`, HEAD inicialmente `a04ebf1`, mesma base de `feature/v2`
  e `checkpoint/v2-validated`. `master` preservada em `948ef05`.
- V1/V2 já têm aceite manual do usuário. **V3 ainda aguarda aceite visual humano.**
- Implementação e empacotamento V3 concluídos nesta auditoria; nenhuma regressão
  conhecida nos fluxos exercitados. Pendências deliberadas estão ao fim desta seção.
- `git status`, `git diff`, arquivos novos, documentação e todos os módulos ativos
  revisados. A V3 estava não commitada: 14 arquivos rastreados modificados, módulos
  de fila/histórico/preview, testes e scripts de distribuição novos.
- Nenhum commit posterior à V2 nem evidência que permita atribuir alterações
  específicas ao Gemma. `teste-gemma.txt` preservado e ignorado; backups e históricos
  desconhecidos não foram apagados. Nenhum merge/push/remoto novo.
- PyInstaller 6.22.3 e Pillow 13.0.0 já estavam instalados, apesar do checkpoint
  anterior dizer que o empacotamento estava pendente. Build/instalador foram
  efetivamente executados nesta auditoria.
- Baseline recebida: **66 testes, 65 aprovados e 1 falha, 21,867 s**.
  O teste HTTP de playlist herdava MP3 salvo por outro caso e esperava vídeo.

### Entrega funcional preservada e estabilizada

- MP4/MP3, qualidades reais (rótulo do extrator + dimensões), análise com debounce
  e IDs de tentativa, preview proporcional e assíncrono.
- Fila sequencial independente da análise da próxima mídia; snapshot por item,
  deduplicação de itens ativos, erro isolado, cancelar/remover/repetir e grupos.
- Playlists explícitas, páginas de 100, selecionar itens/todos, parar carregamento
  sem perder seleção, limites de qualidade por item e indicação de indisponíveis.
- SQLite em thread dedicada com WAL, pesquisa/filtros/paginação, arquivos ausentes,
  repetição, exclusão apenas do registro, preferências e recuperação de interrompidos.
- Cache de miniaturas limitado a 50 MiB, transferência limitada a 8 MiB/imagem,
  limite de pixels de decodificação e descarte de respostas obsoletas.
- Pacote onedir e instalador por usuário com Python/Qt/yt-dlp/EJS/Node/FFmpeg/FFprobe.
  Ícone temporário preexistente preservado; **ícone oficial não integrado/alterado**.

### Problemas comprovados e corrigidos

1. Isolamento de dados dos testes HTTP: preferência/histórico de um teste não
   alteram o formato esperado pelo seguinte.
2. Erro ou parada de paginação deixava `loading`/botão presos: retry manual
   disponível, seleção e páginas anteriores conservadas.
3. Retry no intervalo entre conclusão e cleanup mudava sucesso para falha:
   item atual protegido até `wait(0)` confirmar término nativo.
4. Fila encerrada ainda aceitava trabalho que nunca executaria: entrada/retry
   recusados após fechamento. Retry válido limpa caminho/tamanho/progresso antigos.
5. Preferências tardias sobrescreviam formato já alterado: escolha atual preservada.
6. URL sensível podia escapar pelo título (adicionar links) ou `sig` abreviado:
   sanitização de títulos/erros e bloqueio de URLs reconhecidas como assinadas.
   Miniaturas usam a mesma regra para desabilitar cache persistente.
7. Identificadores de miniaturas se acumulavam após término: liberados com serial
   único que mantém proteção contra resultados obsoletos.
8. Callback de fechamento podia executar depois de destruir MainWindow:
   timers agora associados ao contexto QObject. A exceção foi observada mesmo
   quando unittest imprimia OK; regressão específica captura sys.excepthook.
9. Sucesso anterior continuava no CTA após erro do próximo item: estado apresentado
   reiniciado no início de cada item, mantendo histórico anterior.
10. Cards/filtros ultrapassavam largura disponível em 620×520 e linhas podiam cortar
    texto: grades para ações/filtros e altura de linha calculada pela quebra.

### Validação automatizada

| Verificação | Resultado |
|---|---|
| Baseline recebida | 65/66; falha investigada e corrigida no isolamento do teste |
| Regressões novas antes das correções | seis casos reproduzidos; depois, dois adicionais de UI |
| Suíte final offscreen | **76 aprovados, zero skips, 25,399 s** |
| Suíte Windows nativo intermediária | 74 aprovados, zero skips, 27,530 s |
| Suíte final Windows, escala 150% | **76 aprovados, zero skips, 26,605 s** |
| Diagnóstico | Python 3.13.17, Qt 6.12.0, yt-dlp 2026.10.26/EJS 0.8.0, FFmpeg/FFprobe 9.0.2, Node 26.13.1 OK |
| `pip check` | No broken requirements found |
| `git diff --check` | Sem erros de whitespace |

Comandos executados na raiz:

```powershell
.\.venv\Scripts\python.exe -m media_downloader.diagnostics
.\.venv\Scripts\python.exe -X faulthandler -m unittest discover -s media_downloader/tests -v
$env:QT_QPA_PLATFORM = 'windows'
$env:QT_SCALE_FACTOR = '1.5'
.\.venv\Scripts\python.exe -X faulthandler -m unittest discover -s media_downloader/tests -v
Remove-Item Env:QT_QPA_PLATFORM
Remove-Item Env:QT_SCALE_FACTOR
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

HTTP/FFmpeg/FFprobe reais: MP4 com áudio, MP3, DASH separado, conversão HuffYUV,
404, destino inválido, duplicatas, playlist com falha intermediária e continuação,
103 itens em duas páginas sem repetição/omissão. Miniaturas HTTP: cache público,
URL assinada sem cache, resposta antiga ignorada, proporções variadas.
SQLite: fechamento com flush, reabertura, recuperação e remoção sem apagar mídia.
Nenhum teste nativo de clipboard/cursor executado em paralelo a outro nativo.

### Executável e instalador

```powershell
.\.venv\Scripts\python.exe scripts/build_windows.py --installer
.\.venv\Scripts\python.exe scripts/validate_windows.py --installer
.\.venv\Scripts\python.exe scripts/validate_windows.py --installer --public-url 'https://www.youtube.com/watch?v=jNQXAC9IVRw'
```

- PyInstaller onedir + Inno Setup 7.1.1 portátil, obtido com hash conferido.
- Primeiro ciclo completo aprovado:
  `test-artifacts/windows-20261118-092448/validation.json`.
- **Ciclo final completo aprovado**, incluindo fonte externa:
  `test-artifacts/windows-20261118-093045/validation.json`.
  `success=true`, instalação de teste removida, nenhum erro/traceback nos logs.
- Executável rodou fora da raiz com PATH restrito ao System32: ferramentas
  confirmadas em `_internal/bin`, sem depender do Python/FFmpeg/Node do PATH.
- MP4/MP3 e playlist executados no binário; FFprobe incluído confirmou streams,
  duração >1 s, arquivos não vazios e progresso final 100%.
- Histórico confirmado após reinício. Instalação por usuário, registro/atalho,
  download instalado, reinstalação e desinstalação exercitados.
- Hashes de banco/downloads antes/depois da desinstalação coincidiram; atalho e
  registro removidos. A instalação de teste foi desinstalada, sem tocar dados reais.
- Build final concluído após os ajustes de layout:
  `test-artifacts/v3-build-final.log`. Os dois avisos PyInstaller são sobre
  integrações opcionais `urllib3.contrib.emscripten/js` e `curl_cffi`.
- Manifesto `_internal/licenses/build-manifest.json`: versões, hashes dos três
  executáveis externos e **35 arquivos de fonte/recurso conferidos contra a árvore**.
- Instalador: `dist/installer/MediaDownloader-3.0.0-Setup-x64.exe`,
  **235.969.363 bytes**, SHA256:
  `63cd14b8ad3586087412bcf57b093262d38bc694d753e474cbe37db526100a79`.
- Executável: `dist/MediaDownloader/MediaDownloader.exe`,
  **11.761.735 bytes**, SHA256:
  `cfafb997ea45adb3508c0e388125de7cd89f6803c9e562ff232c8354cc916f1d`.
  Pasta onedir completa: 689.617.315 bytes; o EXE isolado não é portátil.
- Hashes de entrega também em `dist/SHA256SUMS.txt` (artefato local ignorado).
- **YouTube real no EXE final / PATH restrito:** “Me at the zoo”:
  MP4 **637.033 bytes**, H.264 320×240 + AAC, 19,063356 s;
  MP3 **231.650 bytes**, 19,063583 s. Dois itens concluídos, 100% e histórico
  persistido; miniaturas carregadas nos cards. Capturas de mídia, fila e
  histórico inspecionadas; não substituem aceite humano.
- Timer do smoke: 602 ticks no teste público; maior intervalo 1,0114 s.
  Nos downloads locais do pacote: 244/248 ticks, intervalos máximos
  0,3722/0,3952 s. Essas medições incluem o harness/capturas e inicialização;
  não se atribuiu uma causa isolada nem se alegou ganho de desempenho.

### Commits locais

- `210bcb1` — V3 integrada e estabilizada, com suíte/regressões.
- `08cee44` — build Windows, instalador e validador do ciclo de instalação.
- Documentação/evidências em commit separado.
- `master`, `feature/v2` e tag da V2 preservados; nenhuma publicação.

### Limitações/pendências deliberadas

- Aceite humano da interface V3 e integração futura do ícone oficial.
- Assinatura digital não configurada; pacote local não assinado.
- Validação neste Windows 11 com PATH restrito, sem VM limpa/segundo computador.
- Cancelamento aguarda a etapa de rede/FFmpeg já iniciada. Lives/DRM/cookies
  automáticos seguem fora do escopo; disponibilidade externa depende da fonte.
- Publicação/merge não autorizados. Avisos de componentes em
  `distribution/THIRD_PARTY_NOTICE.md`; pacote local não é release pública.

## Registro da V2

## Estado atual e checkpoint

- Usuário confirmou manualmente: app abre, analisa, baixa e a V1 é utilizável.
- V1 preservada em `master`, commit `948ef054d82bdc87ba1327205ea24464d6c27a1f`,
  sincronizada com `origin/master` no início desta etapa.
- Trabalho exclusivamente na branch local `feature/v2`; publicação não autorizada.
- Baseline novamente executada: **36 testes aprovados, zero skips, em 8,751 s**.
- Escopo: análise automática com debounce/invalidação, CTA principal, tema roxo
  neon, fluidez e documentação reutilizável para agentes locais.
- **Etapa V2 implementada e validada por automação e fontes reais.**
  Aceite humano do novo visual ainda pendente.
- A retomada conferiu os três arquivos modificados deixados pela interrupção;
  a implementação parcial foi continuada, sem reinicialização ou duplicação.

## Funcionalidades V2 concluídas

- Análise automática após **600 ms** da última alteração de uma URL válida,
  inclusive Ctrl+V. Botão Analisar/Enter continuam como alternativa manual.
- URL editável durante análise. Mudança invalida imediatamente a mídia anterior,
  cancela cooperativamente a tarefa e mantém apenas a última intenção pendente.
- IDs únicos por tentativa e revisão de entrada bloqueiam resultados/status/
  erros/cancelamentos obsoletos. Uma única tarefa até terminar o cleanup nativo.
- Mesma URL sem mudança significativa não provoca nova análise automática;
  espaços externos são ignorados. Erros/cancelamentos não criam retry infinito.
- Fechar ou cancelar elimina timer e intenção pendente. Reanálise manual continua
  funcionando após cancelamento.
- Tema cyberpunk discreto, escuro/roxo neon em QSS centralizado, SVG local,
  tipografia legível, cards, inputs/combos harmonizados e barra estilizada.
- CTA central, altura mínima 64 px, estados normal/hover/clique/foco/desabilitado/
  carregando. Cancelar secundário; indicação de fase e progresso textual.
- Download só habilitado para a mídia atual, qualidade disponível e destino
  informado. Destino vazio desabilita imediatamente; erros de acesso ficam
  no worker. Melhor qualidade automática preservada.
- Teclado, nomes acessíveis, títulos externos como texto puro, linhas quebradas
  e scroll vertical para janela pequena/DPI elevado.

### Fluidez e otimizações verificáveis

- Debounce e deduplicação reduzem análises redundantes. Cada smoke externo
  registrou **uma análise da GUI por colagem**, sem clique no botão.
- Rede/FFmpeg continuam nos workers. QSS é carregado uma vez por processo;
  propriedades visuais só são reaplicadas quando mudam.
- Throttle de progresso da V1 preservado; não há animação pesada ou asset remoto.
- Não foi feita promessa de acelerar servidores externos. Download continua
  reextraindo metadados para não reutilizar URLs assinadas expiradas.

## Validação executada nesta etapa

| Verificação | Resultado real |
|---|---|
| Baseline antes das mudanças | 36 testes, zero skips, 8,751 s |
| Primeira etapa, debounce | 46 testes aprovados em 14,203 s |
| Suíte final offscreen | **48 aprovados, zero skips, 16,398 s** |
| Suíte Windows nativo | **48 aprovados, zero skips, 16,146 s** |
| Suíte Windows com `QT_SCALE_FACTOR=1.5` | **48 aprovados, zero skips, 16,695 s** |
| Diagnóstico e imports | Python/venv, PySide6, yt-dlp/EJS, FFmpeg/FFprobe e Node OK |
| `pip check` | No broken requirements found |
| `git diff --check` | Sem erros |

Comando da suíte:

```powershell
.\.venv\Scripts\python.exe -X faulthandler -m unittest discover -s media_downloader/tests -v
```

Para backend nativo, definir `$env:QT_QPA_PLATFORM = 'windows'`. Na verificação
adicional foi usada escala Qt forçada de 150%, sem alterar configurações do SO.

Os 36 casos da V1 continuam na suíte; foram adicionados 12 casos de autoanálise/
UI. O fluxo real HTTP local também passou a usar Ctrl+V sem clique em Analisar.
Há testes de timers Qt, duplicatas, formato inferior, MP3, DASH combinado,
transcode real, cancelamento/fechamento, falhas e arquivos com FFprobe.

### Smokes externos por colagem automática

```powershell
.\.venv\Scripts\python.exe -m media_downloader.tests.public_smoke --output test-artifacts/v2-public
.\.venv\Scripts\python.exe -m media_downloader.tests.public_smoke --url 'https://www.youtube.com/watch?v=jNQXAC9IVRw' --video-height 144 --output test-artifacts/v2-youtube --screenshot test-artifacts/v2-ui/ready-youtube.png
```

- **W3Schools:** MP4 788.493 bytes, H.264/AAC, 10,026667 s; MP3 296.468 bytes,
  10,005333 s. 112 ticks Qt; maior intervalo observado 41 ms; uma análise da GUI.
- **YouTube, backend Windows:** “Me at the zoo”, 19 s, 25 formatos, qualidades
  reais 240p/144p. MP4 509.329 bytes, H.264/AAC, **144p confirmado pelo FFprobe**,
  19,063356 s; MP3 231.650 bytes, 19,063583 s. 432 ticks Qt; maior intervalo
  observado 42 ms; uma análise da GUI. Nenhum aviso de JavaScript.
- Os quatro arquivos terminaram com progresso 100% e foram conferidos com
  FFprobe. Essas medições são observações dos smokes, não garantias de latência.
- Capturas nativas de início e estado pronto foram inspecionadas:
  `test-artifacts/v2-ui/startup.png` e `ready-youtube.png`.
- Artefatos/downloads permanecem locais e ignorados pelo Git.

### Problemas descobertos e corrigidos nesta etapa

- Sinais da análise precisaram transportar identidade de tentativa para rejeitar
  respostas antigas; testes/observadores foram adaptados ao contrato real.
- Estado de cancelamento poderia sobreviver à próxima tentativa manual; reset
  no início do worker e teste de status final impedem mensagem falsa de cancelamento.
- Teste de janela 620×520 falhou inicialmente: conteúdo 954 px para viewport 610,
  causado por texto auxiliar sem quebra de linha sob fonte de fallback. Wrapping
  corrigido; teste passou em offscreen, Windows e escala 150%.
- CTA da base permanecia habilitado com pasta vazia; agora acompanha edição
  do destino. Nenhuma regressão conhecida nos fluxos exercitados.

## Documentação para outras IAs

- `AGENTS.md`: contrato **específico** deste aplicativo, estado assíncrono,
  sinais, tema, caminhos, branch/permissões e validação.
- `LESSONS_LEARNED.md`: incidentes reais com evidência/grau de certeza,
  correções e regras generalizáveis, sem atribuir causas não demonstradas.
- `GLOBAL_AGENT_TEMPLATE.md`: modelo **geral**, adaptável a projetos novos e
  agentes locais (Qwen/Gemma etc.), com contrato, execução, evidência e retomada.
- `PROJECT_BOOTSTRAP_CHECKLIST.md`: roteiro **geral** com entregáveis verificáveis,
  ambiente Windows, baseline, arquitetura, testes, UI, documentação e publicação.
- `README.md`: uso atualizado da autoanálise, tema e roteiro de teste manual.

## Limitações e próximos passos desta etapa

- O usuário ainda precisa avaliar o visual V2 e a experiência com seus links;
  não foi inventado aceite humano da nova interface.
- Cancelamento aguarda a chamada de rede/etapa FFmpeg atual. O próximo link só
  começa após limpeza segura, mantendo a janela responsiva.
- Fontes podem omitir duração/resolução, retirar mídia ou mudar requisitos.
  Não há suporte prometido a todas as URLs do yt-dlp.
- Permanecem fora do escopo: playlists, lives, DRM e instalador standalone.
- Deduplicação de arquivos continua por caminho/seleção, sem coordenação entre
  instâncias. Não há cache persistente de links assinados.
- Próximo passo: avaliação manual do novo visual conforme README; publicação
  ou merge somente com nova autorização do proprietário.

## Git desta etapa

- Branch ativa: **`feature/v2`**.
- `master` e `origin/master` preservadas em `948ef05`.
- Commits de implementação: `4ce7765` (análise automática) e `83277f9`
  (tema/CTA, fluxo real e regressão), mais documentação em commit separado.
- Repositório privado existente preservado. **Nenhum push, novo remoto ou
  alteração da branch master nesta etapa.**

## Histórico da entrega V1 — 2026-11-17

**V1 funcional e validada neste ambiente Windows, publicada em repositório
privado.** Análise, MP4, MP3, seleção de qualidade, progresso, erros e encerramento
foram exercitados. O registro abaixo é histórico; a confirmação manual posterior
do usuário e o estado da V2 estão descritos no topo.

### Concluído e verificado na V1

- Auditoria de todos os módulos/testes recebidos, Git e ambiente: `AUDIT.md`.
- Backup anterior às alterações e commit de recuperação `255ce01`.
- Análise e download em QObject/QThread fora da GUI, slots queued explícitos.
- Uma operação ativa; botões, URL e seleção protegidos durante tarefas.
- Indicador indeterminado para análise/processamento e percentual de transferência.
- Título, duração quando fornecida, resoluções/bitrates reais e melhor seleção padrão.
- Mudança de URL invalida análise; download antes de análise recebe erro claro.
- MP4 com faixas combinadas, remux sem perda quando possível e conversão quando
  o codec não cabe no contêiner. MP3 via extração real FFmpeg.
- Callback de progresso corrigido para dicionário; falhas propagadas; conclusão
  somente com arquivo final existente, não vazio e com extensão esperada.
- Nomes seguros para Windows, caminhos com `%`, pasta selecionada e preservação
  de arquivo já existente da mesma seleção.
- Cancelamento cooperativo e fechamento adiado com event loop ativo.
- Worker duplicado substituído por import de compatibilidade.
- Python ativo sem bytes nulos; `import_test.py` reparado. Documentos internos
  e `.gitignore` convertidos de UTF-16/escapes incorretos para UTF-8 válido.
- Testes antigos da UI agora são entradas para a suíte mantida, sem efeitos
  colaterais ao importar. Originais preservados no backup/commit inicial.
- EJS 0.8.0 instalado na `.venv` via extra oficial `yt-dlp[default]`.
  Node 26.13.1 habilitado automaticamente. Deno não foi necessário.
- FFmpeg/FFprobe 9.0.2 reais detectados. Nenhuma instalação global efetuada.

### Correção adicional descoberta durante validação da V1

As primeiras execuções ampliadas expuseram abortos intermitentes ao liberar
wrappers Python quando `QThread.finished` era emitido, antes de finalizar a
limpeza nativa/thread-local. O fechamento agora mantém referências até uma
consulta **não bloqueante `wait(0)`** confirmar o término. Se ainda estiver
finalizando, QTimer agenda nova consulta em 10 ms. Nunca há espera bloqueante
na GUI. Após a correção, três execuções consecutivas da suíte de 34 testes
passaram, seguidas da suíte final de 36 testes em offscreen e Windows nativo.

A instrumentação inicial que sobrescrevia slots herdados também foi substituída
por QObject observador com slots próprios; as verificações de thread passaram.
Essas falhas intermediárias foram investigadas, não tratadas como aprovação.

### Testes executados na V1

#### Suíte final

```powershell
.\.venv\Scripts\python.exe -X faulthandler -m unittest discover -s media_downloader/tests -v
```

**36 testes passaram, zero skips, em 8,587 s (offscreen).**

```powershell
$env:QT_QPA_PLATFORM = 'windows'
.\.venv\Scripts\python.exe -X faulthandler -m unittest discover -s media_downloader/tests -q
```

**36 testes passaram, zero skips, em 8,848 s (backend gráfico Windows).**

Cobertura comportamental:

- Inicialização, imports e integridade dos fontes.
- URLs inválidas, playlists/live/DRM rejeitados, falha de análise e nova tentativa.
- Atraso de rede, contagem de timers Qt, execução fora da GUI e slots na GUI.
- Destruição efetiva dos workers/threads após conclusão.
- Cancelamento e fechamento durante análise/download; etapa de rede simulada
  sem interrupção imediata mantém o event loop funcionando até terminar.
- Progresso conhecido/desconhecido, falhas sem falso sucesso.
- Exclusão de análises/downloads simultâneos e invalidação ao editar a URL.
- Melhor qualidade, seleção inferior, fonte de áudio e metadados nulos.
- HTTP local **real**, MP4 com áudio, extração MP3, DASH com vídeo/áudio separados,
  conversão HuffYUV→MP4 e inspeção dos codecs/duração com FFprobe.
- HTTP 404, FFmpeg ausente, destino que é arquivo, duplicata preservada sem
  nova transferência e nomes Windows em pasta com `%`.

#### Fontes públicas (rede externa real)

Executadas pelo fluxo da janela/workers via
`python -m media_downloader.tests.public_smoke`.

| Fonte | Resultado real |
|---|---|
| W3Schools `https://www.w3schools.com/html/mov_bbb.mp4` | MP4 788.493 bytes, 10,026667 s, H.264/AAC; MP3 296.468 bytes, 10,005333 s. Progresso final 100%. 136 ticks Qt; maior intervalo 45 ms. |
| YouTube `https://www.youtube.com/watch?v=jNQXAC9IVRw` | Título “Me at the zoo”, duração 19 s, 25 formatos, opções reais 240p/144p. Melhor MP4 637.033 bytes, H.264/AAC; MP3 231.650 bytes. 393 ticks Qt, maior intervalo 40 ms. Nenhum aviso JS. |
| Mesmo YouTube, `--video-height 144` | MP4 509.329 bytes, **altura 144 confirmada pelo FFprobe**, H.264/AAC, 19,063356 s; MP3 válido. 395 ticks Qt, maior intervalo 41 ms. Nenhum aviso JS. |
| Vídeo de teste antigo `BaW_jenozKc` | Fonte respondeu “This video is unavailable”; erro exibido, GUI responsiva (42 ticks). Não foi contado como download aprovado. |

Arquivos de validação preservados em `test-artifacts/` e ignorados pelo Git.
Os primeiros arquivos externos usam o nome anterior com extensão repetida;
o template final usa `[mp4-best].mp4` / `[mp3-best].mp3` / `[mp4-144].mp4`.

#### Outras verificações

- Entrada `media_downloader.main.main()` executada com backend Windows;
  janela visível, captura `test-artifacts/startup-windows.png` inspecionada
  e fechamento normal, saída 0.
- `python -m media_downloader.diagnostics`: imports e dependências OK,
  runtime JavaScript compatível presente.
- `python -m pip check`: **No broken requirements found**.
- `git diff --check`: sem erros de whitespace.
- `git check-ignore`: `.venv`, backups, histórico exportado e artefatos excluídos.

### Limitações registradas na entrega inicial

- Reprodução visual/auditiva humana não foi executada. Procedimento curto
  no README; binários foram verificados com FFprobe.
- Sites podem retirar mídias, exigir autenticação ou mudar seus extratores.
  Não há promessa de funcionamento em todas as fontes.
- Cancelar/fechar aguarda término da chamada de rede ou etapa FFmpeg atual;
  não há interrupção forçada. A janela continua responsiva.
- Fontes diretas podem omitir duração/resolução; esses dados não são inventados.
- Deduplicação é por caminho/seleção, sem coordenação entre várias instâncias.
- Playlists, lives e empacotamento standalone estão fora do escopo desta V1.
- Nenhuma pendência funcional conhecida nos fluxos efetivamente testados.

### Git e publicação da V1

- Git original preservado, branch `master`.
- Commits validados publicados: recuperação `255ce01`, implementação/testes
  `7676f6d` e documentação/organização `df27868`, preservando todo o histórico.
- Autor técnico local dos commits: `OpenCode <opencode@localhost>`;
  configuração global do usuário não alterada.
- GitHub CLI autenticado como `Lavylck`.
- Criação e push autorizados explicitamente pelo proprietário.
- Antes do push, revisados os três commits completos: 51 versões de arquivos,
  37 caminhos históricos e mensagens de commit. Nenhum caminho de credenciais,
  ambiente virtual, cache, backup ou histórico privado incluído; nenhuma
  assinatura de credencial encontrada na inspeção de conteúdo.
- Repositório: https://github.com/Lavylck/Media-Downloader
- Visibilidade **PRIVATE**, confirmada pela API do GitHub antes do push.
- `origin`: `https://github.com/Lavylck/Media-Downloader.git`.
- `git push -u origin master` concluído; branch local acompanha `origin/master`.
- Registro da publicação em commit adicional somente de documentação.
- Naquela publicação a V2 ainda não havia sido iniciada. A evolução local atual
  está registrada no início deste documento.
