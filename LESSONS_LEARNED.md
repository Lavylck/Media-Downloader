# Lições aprendidas — Media Downloader

**Escopo:** registro concreto deste projeto. As seções “Aplicação geral”
extraem regras reutilizáveis; versões, commits e políticas de mídia pertencem
ao aplicativo. Evidências históricas: `AUDIT.md`, `PROGRESS.md` e testes.

## 1. Evidência antes de diagnóstico

| Incidente observado no projeto | Evidência / grau de certeza | Correção e prevenção |
|---|---|---|
| “Não está respondendo” na análise original | `wait()` em slots da GUI e thread sem encerramento no sucesso confirmados no código. O congelamento relatado pelo usuário não foi reproduzido exatamente no mesmo cenário histórico. | Rede em worker, sinais queued, cleanup em todos os caminhos; testes com timer Qt durante rede lenta. Não apresentar uma hipótese como causa única do relato. |
| Processo abortava em testes de threads | Abortos Windows intermitentes observados. Conservar wrappers até término nativo eliminou-os nas repetições executadas. Não houve depuração de símbolos C++ para provar um bug específico de Qt. | `wait(0)` como consulta não bloqueante e QTimer; testar fechar/cancelar/sucesso/erro e objetos efetivamente destruídos. |
| Instrumentação executava código no contexto errado | Sobrescrever slots herdados no observador de teste produziu falhas de entrega/afinidade. | QObject observador com slots próprios. Teste também pode estar errado; comparar com MainWindow real antes de culpar o produto. |
| “Download concluído” sem evidência de arquivo | Hook de quatro argumentos contrariava API de um dicionário; `ignoreerrors=True`; retorno era template. Confirmados por leitura/API e exercício real. | Propagar erro, capturar caminho após pós-processamento e validar arquivo. Mock não pode repetir a assinatura errada e ser usado como prova. |
| Vídeo podia ficar sem áudio | Escolha de um format_id de vídeo isolado sem combinação; MP3 reutilizava seleção de vídeo. | Selecionar fontes por tipo e combinar faixas. Teste DASH real + FFprobe verifica presença de áudio e vídeo. |
| Bytes nulos confundidos com corrupção geral | Fontes ativos estavam sem zeros. README/backups eram UTF-16; `import_test.py` continha escapes literais inválidos. | Inspecionar bytes/BOM, recuperar codificação correta, compilar/importar. Não remover `\\0` cegamente nem converter todo o ambiente. |
| Falta de JavaScript atribuída exclusivamente a Deno | Node compatível existia, mas não estava habilitado; EJS faltava. Documentação oficial confirmou requisitos. | Habilitar runtime existente e instalar extra EJS compatível na venv. Instalação adicional de Deno foi desnecessária. |
| FFmpeg confundido com biblioteca Python | `ffmpeg-python` estava instalado; somente busca no PATH e execução provaram os binários reais. | Verificar `ffmpeg -version` e `ffprobe -version`, depois conversão real. `pip check` não valida ferramentas externas. |
| `.gitignore` parecia existir, mas era inválido | Arquivo UTF-16 com `\\n` literais; Git inicialmente sem commits e tudo sem rastreamento. | Regras UTF-8 válidas, `git check-ignore`, revisão de `git ls-files` e versões históricas antes de publicar. |
| Primeira fixture DASH retornava 404 | FFmpeg escreveu segmentos no diretório de trabalho, separado do manifesto. Não era erro do extrator. | Definir `cwd` e saída relativa na fixture; conferir HTTP servido. Artefatos de teste foram preservados em pasta ignorada. |
| Fixture “codec incompatível” não convertia | FFmpeg 9 aceitou remux de FFV1 em MP4, contrariando a suposição do teste. | Usar HuffYUV, cuja incompatibilidade foi reproduzida. A disponibilidade de codecs muda entre versões. |
| Vídeo público antigo indisponível | YouTube respondeu “This video is unavailable”, com GUI ainda responsiva. | Registrar falha externa, usar outra amostra acessível; não burlar acesso nem contar como download aprovado. |

### Aplicação geral

Antes de mudar código, anote: **sintoma → hipótese → experimento → observação →
conclusão limitada pela evidência**. Exemplos:

- Timer Qt continua disparando + servidor retorna 404: falha de fonte, não prova
  de congelamento.
- `pip list` contém biblioteca: prova instalação Python, não binário no PATH.
- Teste mock passa: prova contrato simulado, não transferência/conversão real.
- Erro desaparece após mudar três coisas: ainda não se sabe qual era a causa.
  Isole quando possível; documente incerteza se não houver prova.
- Timeout do processo de teste: pode ser diálogo modal, teardown incorreto,
  servidor de fixture ou rede. Capture traceback e estado antes de reescrever.

## 2. Lições específicas da evolução V2

### Debounce não substitui controle de concorrência

Uma tarefa pode durar mais que 600 ms. Reiniciar o timer sozinho permitiria
duas análises ativas ou resultado antigo sobrepondo novo. A implementação usa:

1. Revisão de entrada quando a URL normalizada muda.
2. ID único em cada tentativa, inclusive reanálise manual do mesmo link.
3. Apenas uma intenção pendente, sempre a mais recente.
4. Cancelamento cooperativo; próxima tarefa aguarda destruição/cleanup.
5. Rejeição de **todos** os sinais antigos: informação, status, erro e cancelamento.

**Aplicação geral:** use identificadores de requisição em autocomplete, buscas,
previews, validação remota e outras telas onde a entrada pode mudar durante I/O.
Cancelar a operação é otimização; invalidar o resultado é requisito de correção.

### Não transformar autoanálise em loop de tentativas

Sucesso, falha ou cancelamento marcam a revisão como tentada. Colar novamente
texto idêntico ou acrescentar espaços externos não gera trabalho. O botão
manual força atualização; mudar a URL cria nova intenção.

Na revisão do código foi encontrado um flag de cancelamento pendente que
poderia sobreviver até a próxima tentativa manual. Ele é reiniciado ao iniciar
worker; o teste agora exige status de sucesso após cancelar o debounce e retomar.

**Aplicação geral:** documente transições, inclusive estados transitórios e
flags de uma operação anterior. Testar só “houve uma chamada” não valida a UI final.

### Tema também precisa de testes de layout

O primeiro teste em 620×520 encontrou conteúdo com largura 954 e viewport 610.
O texto auxiliar sem quebra de linha fixava a largura mínima; fontes de fallback
do offscreen tornaram o problema evidente. Quebra de linha corrigiu o corte.

- QSS centralizado, SVG local, métricas lógicas do Qt.
- CTA com estados hover/pressed/focus/disabled/busy, sem depender só da cor.
- Títulos externos em texto puro; longos títulos e caminhos podem ocupar linhas.
- Scroll vertical em telas menores; validar DPI real e navegação por teclado.

**Aplicação geral:** screenshot de uma tela vazia não cobre título longo, erro,
carregamento, combo aberto, fonte diferente ou escala do Windows.

### Otimizar o que é medido

O ganho verificável desta etapa é evitar análises automáticas redundantes:
smokes externos registraram **uma análise da GUI por colagem**. Timers continuaram
disparando durante rede/download. Não foi medida uma aceleração do servidor.

O download ainda reextrai metadados no worker: links de mídia assinados podem
expirar. Guardar esses links indefinidamente para economizar uma consulta
introduziria outro problema. Não alegar cache de rede que não existe.

## 3. Matriz de prevenção para manutenção

| Alteração | Evidência mínima relevante |
|---|---|
| Worker/cancelamento | Timer Qt ativo, thread de execução, sucesso/erro/cancelamento, close com rede lenta, destruição real |
| Autoanálise | Colagem Ctrl+V, digitação de prefixos válidos, A→B→último, inválido, mesmo link, cancelamento e reanálise manual |
| yt-dlp/FFmpeg | Assinaturas atuais, HTTP local real, áudio+vídeo, MP3, conversão necessária, caminho/duração/codecs finais |
| UI/QSS | Janela nativa, tamanho mínimo, título longo, destino vazio, CTA e mensagens de erro/conclusão |
| Dependências | Executável da venv, versões/imports, `pip check`, PATH e execução de binários |
| Git/publicação | Branch/status/diff, checkpoint, arquivos e histórico revisados, autorização atual, privacidade confirmada |

## 4. Retomada por outra IA

Não confundir plano com código implementado, nem documento antigo com estado
atual. A interrupção inicial da V2 deixou três arquivos modificados; a retomada
leu o diff e completou os contratos de sinais e testes, sem criar segunda
implementação de debounce. Use `GLOBAL_AGENT_TEMPLATE.md` para formalizar esse
procedimento em outros projetos.

## 5. Auditoria V3 — 2026-11-18

- A retomada encontrou V3 inteira não commitada sobre o checkpoint V2, incluindo
  scripts de build. Leitura de Git/código preservou o trabalho; não houve reinício.
- Baseline: 65/66 passaram. A falha real de playlist era contaminação entre testes:
  preferência MP3 salva por um caso anterior, mas asserção esperava vídeo.
  Diretório de dados por teste eliminou a dependência da ordem.
- Seis casos adicionais reproduziram problemas antes da correção: paginação
  travada após erro, botão desabilitado após parar, retry antes do cleanup,
  entrada de trabalho em fila fechada, preferência tardia sobrescrevendo seleção
  e URL sensível persistida por título/assinatura abreviada.
- Suíte chegou a imprimir `OK` junto com `Internal C++ object (MainWindow) already
  deleted`: callback singleShot pendente depois de deleteLater. Contexto QObject
  nos timers impede execução após destruição; regressão captura sys.excepthook.
  **Resultado verde sozinho não basta: revisar também stderr.**
- Miniaturas agora liberam os identificadores de requisições finalizadas e usam
  a mesma classificação de URL sensível do histórico para evitar cache em disco.
  HTTP real verifica cache público e duas transferências para a URL assinada.
- A revisão de telas pequenas encontrou largura mínima de card 603 px para
  viewport de 598 px e filtros do histórico com mínimo de 915 px. Ações/filtros
  em grade e altura das linhas calculada pela quebra de texto corrigiram os
  cortes. Regressão cobre as abas Fila/Histórico além da aba Mídia.
- Depois de sucesso seguido de erro, a fase/CTA ainda anunciavam o sucesso
  anterior. Limpar o resultado apresentado ao começar outro item corrigiu a
  inconsistência sem alterar registros anteriores no histórico.
