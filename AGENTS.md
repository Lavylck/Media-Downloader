# Media Downloader — instruções específicas para agentes

**Escopo deste arquivo: este aplicativo.** Para iniciar outro projeto, adapte
`GLOBAL_AGENT_TEMPLATE.md` e siga `PROJECT_BOOTSTRAP_CHECKLIST.md`. Não copie
IDs de commits, branches ou decisões de mídia como se fossem regras universais.
`LESSONS_LEARNED.md` contém os incidentes e a evidência que os sustenta.

## 1. Continuidade e autorização

- Leia este arquivo e o início de `PROGRESS.md`, depois execute `git status`
  e `git diff`. Uma interrupção de execução não autoriza reiniciar implementações.
- V1 manualmente validada pelo usuário, preservada em `master`:
  `948ef054d82bdc87ba1327205ea24464d6c27a1f`.
- V2 validada manualmente, preservada em `feature/v2` (`a04ebf1`) e no tag local
  `checkpoint/v2-validated`. Evolução atual em **`feature/v3`**, sem publicação.
- O remoto privado `Lavylck/Media-Downloader` já existe. Não criar outro,
  não modificar `master`, não fazer merge/push sem nova autorização explícita.
- Não apagar arquivos desconhecidos, backups ou históricos do usuário.
  `.gitignore` não remove arquivos já rastreados: revisar também o histórico
  antes de qualquer publicação autorizada.
- Escopo autorizado V3: preview, fila sequencial, playlists explícitas, SQLite,
  executável PyInstaller e instalador por usuário. Lives, DRM e cookies
  automáticos permanecem fora do escopo. Preserve MP4/MP3 e a base assíncrona.

## 2. Ambiente e mapa do código

- Windows 11 / PowerShell, Python 3.13 na `.venv`; PySide6 6.12.0,
  yt-dlp 2026.10.26 + EJS 0.8.0, dependências fixadas em requirements.
- Executáveis no PATH: FFmpeg **e FFprobe**; Node >=22 ou Deno >=2.3.
  Node compatível dispensa instalar Deno. `ffmpeg-python` não é usado.
- Entrada: `.\.venv\Scripts\python.exe -m media_downloader.main`, na raiz.

| Caminho | Responsabilidade |
|---|---|
| `media_downloader/ui/main_window.py` | Widgets, estados, debounce, seleção e ciclo de vida das QThreads |
| `ui/analysis_worker.py` | Análise síncrona no worker; sinais com ID de requisição |
| `ui/download_worker.py` | Transferência/conversão no worker; progresso limitado a aproximadamente 10 Hz |
| `queue.py` | Fila sequencial, snapshot por item, cancelamento e cleanup nativo |
| `history.py` | SQLite em thread dedicada, preferências, recuperação e sanitização |
| `ui/preview.py` | Miniaturas via QtNetwork, cache limitado e descarte de respostas antigas |
| `ui/playlist_panel.py`, `ui/queue_panel.py`, `ui/history_panel.py` | Seleção/paginação e apresentação |
| `ui/theme.py`, `ui/themes/` | QSS, estado visual e SVG local; sem recursos externos |
| `downloader/yt_dlp_wrapper.py` | Rede, formatos reais, FFmpeg, destino e confirmação do arquivo final |
| `downloader/worker.py` | Apenas alias de compatibilidade; não criar outro worker |
| `diagnostics.py` | Diagnóstico explícito de imports/versões/executáveis |
| `tests/` | Regressão Qt, integração HTTP/FFmpeg local e smoke externo opt-in |

Os caminhos da tabela após a primeira linha são relativos a `media_downloader/`.

## 3. Contrato da análise automática

- `textChanged` normaliza somente espaços externos e agenda **600 ms**.
  Não modificar query string, IDs ou URLs assinadas para tentar deduplicar.
- `_url_revision` identifica alterações de entrada. `_attempted_revision`
  impede repetir automaticamente a mesma entrada após sucesso, erro ou cancelamento.
- `_request_serial` gera ID único **por tentativa**, inclusive reanálise manual.
  `_active_request_id` + `_analysis_revision` filtram resultado, erro, status e
  cancelamento antigos. Apenas comparar strings de URL não resolve A→B→A.
- `_auto_pending` representa só o link mais recente pronto para analisar.
  Nunca iniciar outra thread enquanto a anterior ainda existir.
- Durante análise a URL permanece editável; mudança invalida imediatamente a
  mídia e solicita cancelamento por Event. A próxima tarefa aguarda a limpeza.
- Botão **Analisar** e Enter antecipam o debounce/forçam nova tentativa quando
  ocioso. Cancelar/fechar param o timer e eliminam a intenção pendente.
- Botão Baixar exige mídia da URL atual, qualidade disponível e destino não vazio.
  Destino inválido/inacessível é tratado pelo worker, sem consultas de rede
  para validar pastas a cada tecla. Na V3, URL/seleções podem configurar outro item
  durante download: a fila mantém snapshot independente da seleção/destino.

## 4. Invariantes de Qt e processamento

- Rede/FFmpeg nunca em slots da GUI. Slots recebem `@Slot` e conexões queued
  explícitas para atualizar widgets. Observar sinais em testes com QObject
  separado; não sobrescrever slots Qt herdados para instrumentação.
- Cancelamento usa `threading.Event`: slot queued em worker ocupado não executa
  até a operação acabar. Não usar `QThread.terminate()`.
- `worker.finished → thread.quit`; `thread.finished → worker.deleteLater`.
  `_stopped` conserva referências até **`wait(0)` não bloqueante** confirmar
  término nativo; QTimer reagenda a consulta. Nunca substituir por `wait()`.
  Houve abortos intermitentes com liberação antecipada no ambiente Windows.
- Análise e fila são independentes; apenas uma transferência e uma análise da
  GUI por vez. Retry não pode alterar o item atual antes do cleanup nativo.
- QTimer.singleShot de instância usa contexto QObject para não executar depois
  da destruição. Fechamento aguarda também o flush/cleanup da thread SQLite.
- Fechar durante tarefa mantém event loop/janela vivos até cleanup.
  Uma chamada de rede ou etapa FFmpeg já iniciada pode precisar terminar.
- Hook yt-dlp recebe **um dicionário**. Progresso é por transferência;
  100% somente após pós-processamento e arquivo final não vazio verificado.
- Não ignorar erros de yt-dlp. Selecionar qualidade real e combinar vídeo/áudio.
  MP4: remux antes de conversão; MP3: melhor fonte, sem alegar ganho de qualidade.
- Não persistir metadados com URLs temporárias/assinadas. A seleção da GUI é
  reaproveitada, mas o download atualiza a extração; isso protege contra expiração.

## 5. UI e desempenho

- Estilo centralizado em `neon.qss`; assets resolvidos a partir de `__file__`.
  Não duplicar estilos inline, baixar fontes ou adicionar animação pesada.
- QSS carregado uma vez por processo. Reaplicar propriedades visuais apenas
  quando o estado muda, não a cada tick de progresso.
- Manter contraste, navegação por teclado, texto puro para títulos externos,
  nomes acessíveis, quebra de linhas e scroll em janelas pequenas/DPI elevado.
- Medir ganho por comportamento: número de análises e timers Qt durante rede.
  Não prometer redução de tempo do servidor sem comparação controlada.

## 6. Validação obrigatória antes de concluir

```powershell
.\.venv\Scripts\python.exe -m media_downloader.diagnostics
.\.venv\Scripts\python.exe -X faulthandler -m unittest discover -s media_downloader/tests -v
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Para alterações de UI/threads, repetir com backend Windows:

```powershell
$env:QT_QPA_PLATFORM = 'windows'
.\.venv\Scripts\python.exe -X faulthandler -m unittest discover -s media_downloader/tests -v
Remove-Item Env:QT_QPA_PLATFORM
```

- Testes locais geram mídia sintética/HTTP e executam FFmpeg/FFprobe reais.
  Se houver skips por falta de binários, não afirmar validação de conversão.
- `test_auto_analysis.py`: colagem Ctrl+V, debounce, stale results, exclusão
  de tarefas, cancelamento, reanálise manual, CTA e layout pequeno.
- Smoke externo: `python -m media_downloader.tests.public_smoke`; padrão é
  colagem automática. `--manual` exercita o botão; `--screenshot` salva captura.
  Acesso externo falho não equivale automaticamente a regressão.
- Não rodar dois testes **nativos** de clipboard/cursor ao mesmo tempo.
- Registrar comandos, resultados, limitações e intervenção manual em PROGRESS.
  V1/V2 validadas pelo usuário não significam aceite humano da V3.
- Build: `python scripts/build_windows.py --installer`; validação real do pacote:
  `python scripts/validate_windows.py --installer`. Artefatos são locais/ignorados.
- Preservar o ícone temporário existente. Integração do ícone oficial exige
  solicitação futura; não usar `--icon` nesta etapa.

## 7. Commits

Inspecionar diff, manter commits por mudança coerente e não versionar artefatos.
Identidade técnica local permitida na ausência de configuração:
`git -c user.name=OpenCode -c user.email=opencode@localhost commit ...`.
Não alterar configuração global nem se atribuir identidade do proprietário.
