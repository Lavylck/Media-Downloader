# Checklist reutilizável de início, retomada e entrega de projetos

**Escopo: geral.** Copie para o projeto novo e marque itens com evidência.
“Não aplicável” precisa de uma razão curta. Os nomes de branch, stack e caminhos
do Media Downloader não devem ser importados automaticamente.

## A. Descoberta e continuidade

- [ ] Confirmar diretório, SO/shell e instruções locais aplicáveis.
- [ ] Identificar a entrega atual e critérios de aceite observáveis.
- [ ] Ler progresso e diff antes de planejar; listar alterações preexistentes.
- [ ] Descobrir ponto de entrada e mapear entrada → processamento → saída → erro.
- [ ] Ler testes relacionados, não apenas nomes de arquivos.
- [ ] Identificar duplicações, backups e scripts com efeitos ao importar.
- [ ] Registrar o que o usuário já validou manualmente e o que ainda precisa
  de evidência nova; não extrapolar validação de uma versão para outra.

**Evidência a guardar:** diretório, branch/SHA, arquivos tocados anteriormente,
mapa de módulos e requisitos da etapa.

## B. Ambiente real

- [ ] Usar o interpretador/ambiente do projeto e conferir versão/caminho.
- [ ] Ler manifestos e verificar imports efetivos.
- [ ] Executar o verificador de dependências apropriado (`pip check` em Python).
- [ ] Verificar executáveis externos separadamente de bibliotecas.
- [ ] Executar os binários com consulta de versão, não apenas encontrá-los no PATH.
- [ ] Validar suporte da versão instalada à API/runtime necessário.
- [ ] Em Python, procurar zeros/BOM incorreto e erros sintáticos nos fontes do
  projeto, excluindo venv e backups da compilação da aplicação.
- [ ] Resolver dependências ausentes localmente por canal oficial; pedir
  autorização quando envolver instalação global/políticas do sistema.

**Exemplo PowerShell, adaptar aos binários reais:**

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip list
.\.venv\Scripts\python.exe -m pip check
Get-Command python, git -ErrorAction SilentlyContinue
```

## C. Baseline e recuperação

- [ ] Inspecionar status, diff, branches, log e remotos.
- [ ] Executar testes atuais; guardar comando, número aprovado/falhou/skipped
  e tempo quando relevante.
- [ ] Tentar inicialização real da aplicação.
- [ ] Criar checkpoint por commit/branch ou backup avaliado antes de mudanças
  significativas, preservando trabalho do usuário.
- [ ] Criar branch de trabalho autorizada e registrar SHA da versão estável.
- [ ] Conferir ignore para venv, caches, artefatos, backups, credenciais e sessões.
- [ ] Nunca confundir `.gitignore` com remoção de arquivos já commitados.

**Retomada após interrupção:** não repetir instalação, criar outro repositório
ou duplicar funcionalidades sem verificar o que já existe.

## D. Contratos e arquitetura da mudança

- [ ] Definir quem possui estado mutável e quem pode alterá-lo.
- [ ] Confirmar assinaturas de callbacks/sinais e formato dos dados reais.
- [ ] Definir sucesso verificável: arquivo, resposta, transação ou estado final.
- [ ] Definir comportamento para entrada inválida, falha externa e repetição.
- [ ] Em GUI: definir worker, comunicação, progresso, cancelamento e cleanup.
- [ ] Para entrada automática: debounce, deduplicação, ID por requisição,
  invalidação, política da última entrada e comando manual de atualização.
- [ ] Separar estado visual de resultado da operação; bloquear ações inválidas
  sem esconder o motivo.
- [ ] Evitar cache com validade indefinida de credenciais/URLs temporárias.
- [ ] Medir o gargalo antes de otimizar; preservar comportamento validado.

**Artefato útil:** pequena tabela de transições:

| Evento | Estado permitido | Efeito verificável |
|---|---|---|
| Iniciar | Ocioso e entrada válida | Exatamente uma tarefa; indicador ativo |
| Nova entrada | Análise em curso | Resultado anterior invalidado; última intenção preservada |
| Erro | Tarefa ativa | Mensagem correta; sem falso sucesso; liberação de recursos |
| Cancelar/fechar | Qualquer estado aplicável | Sem nova tarefa pendente; encerramento seguro |

Adapte a tabela ao domínio; não imponha estados de GUI em um serviço sem GUI.

## E. Implementação e verificação incremental

- [ ] Fazer mudanças pequenas o suficiente para revisar, completas o suficiente
  para cumprir uma unidade de comportamento.
- [ ] Testar caso positivo e erro relevante; não escrever teste que apenas espelha
  cada linha de implementação.
- [ ] Evitar rede pública na suíte determinística quando HTTP local/fixture
  reproduz a fronteira necessária.
- [ ] Configurar `cwd`, timeouts e diretórios temporários explícitos para ferramentas.
- [ ] Conferir artefato final com ferramenta independente quando possível.
- [ ] Não interpretar resultado de processo como lista/dicionário sem verificar API.
- [ ] Não suprimir exceções só para “fazer passar”.
- [ ] Rodar regressão proporcional à área afetada; repetir mais amplamente quando
  mudanças/falhas/riscos ainda abertos justificarem.

## F. Qualidade de interface — se houver

- [ ] Contraste e tamanhos legíveis; campo principal/CTA com hierarquia clara.
- [ ] Estados normal, hover, clique, foco, desabilitado, carregando, erro e sucesso.
- [ ] Teclado, nomes acessíveis, foco inicial e ordem de Tab.
- [ ] Títulos/caminhos longos, fonte alternativa, tamanho mínimo e DPI elevado.
- [ ] Tema e recursos centralizados e locais, sem dependência externa implícita.
- [ ] Event loop responsivo durante I/O; contar timers ou observar latência.
- [ ] Fechar durante atividade, cancelamento e operações duplicadas.
- [ ] Testes que manipulam clipboard/cursor nativos executados sem concorrência
  com outros testes nativos.
- [ ] Capturas inspecionadas; separar inspeção automatizada de aceite humano.

## G. Documentação útil e entrega

- [ ] `AGENTS.md` contém regras **específicas**, entrada, mapa, invariantes,
  testes e permissões atuais.
- [ ] `PROGRESS.md` começa pelo estado atual e registra evidências reais.
- [ ] `LESSONS_LEARNED.md` separa observação/causa/hipótese/correção/prevenção.
- [ ] README permite instalar e executar sem depender da sessão do agente.
- [ ] Templates gerais são independentes do produto e explicam como adaptá-los.
- [ ] Registrar limitações e a menor validação manual ainda necessária.
- [ ] Revisar diff e segredos/artefatos antes de commits descritivos.
- [ ] Confirmar branch estável preservada e estado local ao encerrar.

## H. Publicação — somente com autorização atual

- [ ] Confirmar conta autenticada, remoto existente e visibilidade desejada.
- [ ] Revisar arquivos **e histórico a enviar**, incluindo versões antigas.
- [ ] Excluir credenciais, venv, caches, backups e históricos privados.
- [ ] Usar o repositório existente quando houver; preservar histórico.
- [ ] Verificar privacidade antes de enviar conteúdo quando exigida.
- [ ] Depois do push, comparar SHA remoto/local e estado da branch.
- [ ] Atualizar progresso e fornecer URL.

Se a autorização não existe, encerrar com commits locais e informar isso.
Não executar comandos de publicação “só para testar”.
