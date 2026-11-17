# Template reutilizável de instruções para agentes de programação

**Escopo: regras gerais, independentes do Media Downloader.** Copie/adapte este
arquivo como `AGENTS.md` de um novo projeto. Preencha o contrato abaixo usando
evidências locais; não invente caminhos, comandos, versões ou testes aprovados.
Se não houver suporte a AGENTS no agente local, forneça este conteúdo como
instrução inicial junto com o checkpoint. Não exige um modelo específico.

## 1. Contrato do projeto — preencher antes de implementar

| Campo | Como obter / o que registrar |
|---|---|
| Objetivo da etapa | Resultado observável solicitado pelo usuário |
| Escopo excluído | Funcionalidades futuras que não fazem parte da etapa |
| Diretório e SO | Diretório real, sistema, shell e permissões disponíveis |
| Stack e interpretador | Manifestos + executáveis realmente utilizados |
| Entrada da aplicação | Comando executado com sucesso, não apenas citado no README |
| Mapa de responsabilidades | Interface, domínio, I/O, persistência e testes existentes |
| Branch base / checkpoint | SHA de referência; branch de trabalho autorizada |
| Comandos de teste | Descobertos no projeto e executados; indicar se dependem de rede |
| Critérios de aceite | Comportamentos a verificar e artefatos de saída |
| Publicação | Remoto/visibilidade e autorização vigente, ou “não autorizada” |

Campos desconhecidos devem dizer **“não verificado”**, acompanhados da menor
ação necessária para verificá-los. O template não deve ficar como documento
fictício concluído com valores de exemplo.

## 2. Fluxo de execução

1. Ler instruções do projeto e o resumo atual de progresso.
2. Inspecionar árvore, ponto de entrada, módulos relacionados e testes.
3. Executar `git status`, `git diff`, log e remotos. Tratar alterações desconhecidas
   como trabalho do usuário; nunca sobrescrever para “limpar” o ambiente.
4. Executar a baseline relevante antes de alterar comportamento. Guardar
   comando, resultado e limitações; um erro pré-existente não é regressão nova.
5. Criar checkpoint/branch autorizada. Não reinicializar Git existente.
6. Implementar mudança coerente e mínima que resolva o requisito completo.
7. Validar comportamento e investigar falhas até corrigir ou demonstrar bloqueio.
8. Revisar diff, atualizar progresso e fazer commits locais descritivos.
9. Publicar somente quando autorizado; permissão passada para outra entrega
   não significa permissão para a etapa atual.

Não interromper a tarefa apenas para oferecer sugestões quando houver ferramentas
disponíveis. Perguntar sobre decisão relevante ou autorização necessária,
não sobre escolhas triviais de nomes/estilo consistentes com o código.

## 3. Disciplina de evidência

- Separar **observado**, **confirmado**, **hipótese** e **limitação** no relatório.
- Verificar contrato/API na versão instalada antes de copiar exemplo de memória.
- Encontrar quem chama, em qual thread/processo e como o erro é propagado.
- Não esconder warnings/erros para obter uma execução aparentemente limpa.
- Reproduzir com teste pequeno útil; depois provar o fluxo completo relevante.
- Não criar mock que replica a implementação equivocada. Validar também a
  fronteira real quando houver protocolo, serviço ou ferramenta externa.
- Usar timeouts para testes externos e registrar falha sem inventar aprovação.
- Evitar novo framework/refatoração ampla se uma correção localizada atende
  ao objetivo e permite verificação.
- Otimização exige métrica apropriada: chamadas, latência do loop, I/O, memória
  ou tempo controlado. Não confundir “menos código” com “mais rápido”.

## 4. Trabalho em Windows / PowerShell

Aplicar quando o projeto realmente usar essa plataforma:

```powershell
Get-Location
git status --short --branch
git diff --stat
git log -5 --oneline
git remote -v
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip check
```

- Reutilizar a venv existente; chamar seu Python explicitamente evita depender
  da ativação e de ExecutionPolicy.
- Descobrir executáveis com `Get-Command`. Pacote Python e binário externo
  são dependências diferentes.
- Citar caminhos com espaços. Preferir `subprocess.run([exe, argumento, ...])`
  a comando concatenado com `shell=True`; definir `cwd` e timeout.
- Escrever fontes em UTF-8. Windows PowerShell pode produzir UTF-16 com
  redirecionamento/Out-File; inspecionar BOM e não remover zeros cegamente.
- Não assumir Bash, `/tmp`, `source`, `export`, `rm -rf` ou `&&` em PowerShell
  antigo. Evitar comandos encadeados que escondam o exit code da etapa anterior.
- Não instalar componentes globais nem alterar políticas de segurança por
  conveniência. Preferir os mecanismos oficiais locais ao projeto.

## 5. Aplicações assíncronas e GUI — aplicar se relevante

- Rede, CPU pesada, disco lento e subprocessos fora da thread da interface.
- Atualizar widgets na thread correta via mecanismos do framework.
- Separar resultado da operação de encerramento/destruição do worker.
- Projetar explicitamente sucesso, erro, cancelamento e fechamento em atividade.
- Cancelamento cooperativo não garante interrupção imediata de biblioteca de
  terceiros; manter event loop vivo e informar o estado real.
- Debounce reduz disparos; IDs de requisição impedem resultados obsoletos.
  Definir política de “última entrada vence” e de tentativa manual.
- Limitar frequência de progresso para não inundar a fila de eventos.
- Não usar espera bloqueante no caminho da GUI nem destruição forçada de threads.

Para **PySide6**, conferir afinidade QObject/QThread e slots `@Slot`. Instrumentar
com observadores QObject independentes. Uma solução específica como consulta
`wait(0)` pode ser adequada, mas não transplantar automaticamente o ciclo de
vida de outro projeto: validar a plataforma/versão e manter referências válidas.

## 6. Organização recomendada

Adapte à estrutura existente; não mova tudo só para ficar igual a este desenho:

```text
raiz/
  AGENTS.md                     # Contrato e regras específicas
  PROGRESS.md                   # Estado atual + evidências + próximo passo
  LESSONS_LEARNED.md             # Incidentes confirmados e prevenção
  README.md                     # Instalação, execução e limites para usuários
  .gitignore
  manifesto de dependências
  pacote/
    entrada
    domínio ou serviços/
    adaptadores de I/O/
    interface/                  # Somente se houver GUI
    recursos locais/
  testes/                       # Ou diretório já usado pelo projeto
```

Separar templates gerais do contrato do aplicativo. Documentar decisões por
razão e consequência; não criar arquivos vazios apenas para preencher a árvore.

## 7. Testes e conclusão

Escolher testes proporcionais ao comportamento alterado:

- Unitários para regras/validação/seleção.
- Integração para caminhos, protocolos, ferramentas externas e formatos reais.
- GUI para eventos, botões, teclado, estados, concorrência e fechamento.
- Smoke real opt-in para serviços públicos; não depender deles em toda execução.
- Verificação visual quando geometria, contraste, DPI ou estados mudarem.

Passar em compilação não prova execução. Passar em mock não prova download.
Skipped não equivale a aprovado. Teste visual automatizado não comprova percepção
humana nem reprodução auditiva. Registrar exatamente o que foi exercitado.

## 8. Continuidade para Qwen, Gemma e outros agentes locais

- Começar pela seção atual do progresso e diff, não por histórico exportado
  inteiro. Ler módulos por responsabilidade e localizar símbolos antes de editar.
- Manter um checkpoint curto: branch/SHA, arquivos em andamento, invariantes,
  último comando/resultado, falha aberta e próxima ação concreta.
- Se o contexto terminar, registrar o estado incompleto antes de parar quando
  possível. O próximo agente deve verificar o código, não confiar só no resumo.
- Ferramenta indisponível não autoriza simular execução. Dizer o bloqueio exato
  e a menor intervenção necessária; preservar alterações.
- Não publicar prompts privados, logs sensíveis, credenciais ou sessões de agentes.

Formato recomendado para a entrega: objetivo atingido, mudanças, testes reais,
limites, comando de execução e situação de Git/publicação.
