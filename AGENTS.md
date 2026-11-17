# Continuidade — Media Downloader V1

## Arquitetura

- Windows 11, Python 3.13, PySide6, yt-dlp + EJS; FFmpeg/FFprobe e Node >=22
  (ou Deno >=2.3) são executáveis externos no PATH.
- Entrada: `python -m media_downloader.main`, **a partir da raiz**.
- `downloader/yt_dlp_wrapper.py`: operações síncronas de rede/FFmpeg,
  validação, seleção de formatos, nomes seguros e confirmação do arquivo final.
- `ui/analysis_worker.py` / `ui/download_worker.py`: QObject com sinais;
  rodam em QThread gerenciada por `ui/main_window.py`.
- `downloader/worker.py` é apenas import de compatibilidade, não outro worker.
- Uma única operação ativa. Alterar URL invalida formatos anteriores.

## Invariantes importantes

- Nenhum trabalho de rede, download ou FFmpeg na GUI. Slots de GUI com `@Slot`
  e conexões queued explícitas. Testes devem observar sinais com QObject/slots,
  sem sobrescrever slots Qt herdados para instrumentação.
- Não usar `terminate()`, esperas bloqueantes ou fechar a janela destruindo
  QThreads ativas. Cancelamento usa `threading.Event`, nunca slot queued
  esperando executar no worker ocupado.
- `QThread.finished` precede a limpeza nativa/thread-local. `_stopped` mantém
  referências e faz **somente `wait(0)`**, consulta não bloqueante, reagendada
  por QTimer até a thread realmente terminar. Não trocar por `wait()` sem
  timeout: recria o congelamento. Não liberar os wrappers antes desse ponto:
  houve abortos intermitentes de processo durante os testes no Windows.
- Cancelamento/fechamento aguarda a próxima fronteira segura; um FFmpeg já
  executando termina a etapa atual. A GUI deve continuar processando eventos.
- Hook yt-dlp recebe **um dicionário**; 100% apenas após pós-processamento e
  arquivo final verificado. Propagar erros; nunca `ignoreerrors=True`.
- Qualidades vêm da fonte. Não inventar resoluções ou dizer que MP3/MP4 melhora
  a qualidade. Combinar vídeo+áudio; remux MP4 antes de recorrer a transcode.
- Não adicionar DRM, cookies automáticos, playlists ou filas à V1.

## Trabalho e validação

Use o Python local sem ativação de shell:

```powershell
.\.venv\Scripts\python.exe -m media_downloader.diagnostics
.\.venv\Scripts\python.exe -m unittest discover -s media_downloader/tests -v
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

A suíte usa Qt offscreen, servidor HTTP local, mídia sintética e binários
FFmpeg/FFprobe reais. Testes de integração são skipped se esses binários
faltarem; isso não autoriza afirmar que MP4/MP3 foram validados.

Para interface nativa, definir `$env:QT_QPA_PLATFORM = 'windows'` antes da suíte.
Validação externa opcional: `python -m media_downloader.tests.public_smoke`.
Os testes externos dependem da disponibilidade do site e não pertencem à suíte
determinística. Consulte README/PROGRESS antes de alterar o fluxo.

- Arquivos UTF-8, estilo Python com quatro espaços, mudanças localizadas.
- Não criar testes que apenas repitam implementação; provar comportamento,
  responsividade, falhas, limpeza e arquivos reais.
- Preservar trabalho do usuário; inspecionar Git antes de editar/commitar.
- Atualizar `PROGRESS.md` com comandos e resultados efetivamente executados.
- Nunca versionar `.venv`, cookies, credenciais, downloads, backups ou históricos
  de agentes. `AUDIT.md` documenta o backup e o estado inicial.
- Não fazer push nem criar remoto sem autorização explícita do usuário.
- Commits de manutenção podem usar identidade local `OpenCode
  <opencode@localhost>` quando não houver identidade configurada; não alterar
  configuração global nem presumir identidade do usuário.
