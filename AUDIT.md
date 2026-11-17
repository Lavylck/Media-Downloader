# Auditoria inicial — 2026-11-17

## Estado recebido (antes das correções)

- Git existente, branch `master`, **nenhum commit e nenhum remoto**. Todos os
  arquivos estavam sem rastreamento. Identidade de commit local não configurada.
- Entrada: `python -m media_downloader.main`.
- Python da `.venv`: 3.13.17; PySide6 6.12.0; yt-dlp 2026.10.26;
  `pip check` sem conflitos. `ffmpeg-python` instalado mas não utilizado.
- Binários reais FFmpeg/FFprobe 9.0.2 encontrados no PATH via WinGet.
- Node 26.13.1 disponível; Deno ausente; `yt-dlp-ejs` ausente.
- GitHub CLI autenticado; nenhuma publicação autorizada ou realizada.

## Causas confirmadas no código

1. `main_window.py`: `wait()` em slots da GUI, thread de análise sem `quit()`
   no sucesso, workers sem `deleteLater()`, ausência de tratamento de fechamento.
   A causa exata do congelamento histórico não pode ser reconstruída só pelo relato.
2. Download antes de análise acessa `best_format` inexistente; análise/download
   podem sobrepor-se; URL editável deixa formatos de uma URL associados a outra.
3. Hook de progresso espera quatro argumentos, mas yt-dlp fornece um dicionário.
4. `ignoreerrors=True` e retorno do template em vez do arquivo real permitem
   falso sucesso. `exists(outtmpl)` verifica texto com placeholders, não o destino.
5. Melhor formato isolado pode ser vídeo sem áudio. MP4 não força combinação ou
   conversão. MP3 reutiliza seleção de vídeo. Não existe seletor de qualidade.
6. `downloader/worker.py` duplica o worker e usa `QThread.terminate()` inseguro.
7. Opções de runtime JavaScript ausentes; só Deno é habilitado por padrão no
   yt-dlp. Node >=22 pode ser habilitado explicitamente. EJS é necessário.
8. `.gitignore` interno contém `\\n` literais e não funciona como pretendido.
9. Python ativo sem bytes nulos. `import_test.py` tem erro de sintaxe por escapes
   literais. Backups `.bak` e README interno estão em UTF-16; não são módulos
   Python executáveis. Logs UTF-16 também contêm zeros, sem relação com imports.
10. Scripts de teste da UI têm loops sem espera temporal adequada, criam
    QApplication ao importar, alguns chamam `sys.exit()` ao importar e não
    garantem limpeza de threads.

## Baseline executada

- `python -m unittest discover -s media_downloader/tests -v`: **4/4 passaram**,
  exclusivamente mocks/seleção, sem validar GUI nem downloads reais.
- Scripts isolados com `QT_QPA_PLATFORM=offscreen`:
  - `test_simple`, `test_app_loop`: saída 0.
  - `test_download_worker`: saída 0, mas mock usa a mesma assinatura incorreta.
  - `test_analysis_worker`, `test_analysis_v2`: saída Windows **3221226505**.
  - `test_ui_responsiveness`: **timeout de 8 segundos**, subprocesso encerrado.

## Recuperação

Backup privado completo dos arquivos recebidos (exceto `.venv`, `.git` e caches):
`C:\Users\lavyl\AppData\Local\Temp\opencode\Media-Downloader-before-v1-20261117-103745.zip`

SHA256: `b49a8fb7f270f36788b064420178ae6620874ea67aea886eef5914f2e44574f6`.

Backups, históricos e arquivos do usuário preservados localmente. Consulte
`PROGRESS.md` para as correções e evidências posteriores.
