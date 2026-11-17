# Estado da V1 — 2026-11-17

**V1 funcional e validada neste ambiente Windows, publicada em repositório
privado.** Análise, MP4, MP3, seleção de qualidade, progresso, erros e encerramento
foram exercitados. Validação humana de reprodução continua recomendada.

## Concluído e verificado

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

## Correção adicional descoberta durante validação

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

## Testes executados

### Suíte final

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

### Fontes públicas (rede externa real)

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

### Outras verificações

- Entrada `media_downloader.main.main()` executada com backend Windows;
  janela visível, captura `test-artifacts/startup-windows.png` inspecionada
  e fechamento normal, saída 0.
- `python -m media_downloader.diagnostics`: imports e dependências OK,
  runtime JavaScript compatível presente.
- `python -m pip check`: **No broken requirements found**.
- `git diff --check`: sem erros de whitespace.
- `git check-ignore`: `.venv`, backups, histórico exportado e artefatos excluídos.

## Limitações e pendências

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

## Git e publicação

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
- Nenhum desenvolvimento de V2 iniciado.
