---
name: engineering-loop-start
type: entry-point
description: 'Start the engineering loop — quick reference for CLI and prompt mode.'
---

# Engineering Loop v12.2.1 — Start Here

## Iniciar o Loop

### CLI — Modo Python (Determinístico)

```bash
# Grafo dinâmico (v11, recomendado)
eng-loop --dynamic-graph -w "descrição do trabalho" -f .eng -l .eng -p .

# Com paralelismo QA
eng-loop --dynamic-graph --parallel-qa -w "descrição do trabalho" -f .eng -l .eng -p .

# Com breakpoints (v11.2) — pausa antes de stages específicas
eng-loop --dynamic-graph --pause-at "impl.code" verify -w "descrição do trabalho" -f .eng -l .eng -p .

# Grafo estático (legacy, default)
eng-loop -w "descrição do trabalho" -f .eng -l .eng -p .
```

### CLI — Modo Cirúrgico (v11.2)

Comandos para intervencao cirúrgica no estado do loop:

```bash
# Time Travel — restaura estado antes de uma stage
eng-loop rollback "impl.code"

# Single-Step Replay — executa um nó isoladamente
eng-loop run-node "impl.code" --from-state state.json

# Reset Attempts — zera contagem de tentativas de uma stage
eng-loop clear-state "qa.security" --reset-attempts

# Force Skip — marca stage como concluída
eng-loop skip-node "arch.review"

# Listar snapshots de estado
eng-loop history
```

### CLI — Modo Hibrido (Python controla grafo, OpenCode executa stages)

```bash
# Flag --opencode-agent: Python controla grafo/routing/state, OpenCode executa com tools nativas
eng-loop --dynamic-graph --opencode-agent -w "descrição do trabalho" -f .eng -l .eng -p .

# Ou via config.yaml:
# agent:
#   backend: "opencode"
```

Python (LangGraph) controla **grafo, routing, state, evidence gates**. OpenCode executa cada stage com **tools nativas** (read, write, edit, bash, glob, grep), **session context** e **permission sandbox**.

### CLI — Gerar Topology (para modo LLM)

```bash
eng-loop --build-topology -w "descrição do trabalho" -f .eng -l .eng -p .
```

Gera `artifacts/graph-topology.md` com o plano de execução (stages ativas, regras de roteamento, constraints).

### Modo LLM (Topology-Enforced)

Carregue `ORCHESTRATOR.md` na sessão do seu AI agent. O orquestrador instrui a LLM a:
1. Rodar `eng-loop --build-topology -w "work item"` — Python gera o grafo dinâmico
2. Ler `artifacts/graph-topology.md` — o plano de execução
3. **Antes de cada stage:** rodar `eng-loop --check-compliance --requested-stage <stage>` — valida transição
4. Seguir o plano exatamente — stages ativas, roteamento, constraints

---

## Flags do CLI

| Flag | Para que |
|------|----------|
| `--dynamic-graph` | Ativa grafo dinâmico (v11) — só nós necessários |
| `--parallel-qa` | QA stages em paralelo (fan-out/fan-in) |
| `--opencode-agent` | Modo hibrido: Python controla grafo, OpenCode executa stages com tools nativas |
| `--build-topology` | Gera topology markdown para modo LLM |
| `--check-compliance` | Valida transição de stage (modo LLM, obrigatorio) |
| `--pause-at <stage>` | Pausa execucao antes de stages (v11.2) |
| `--interactive` | Dashboard TUI fullscreen (experimental, v11.2) |
| `--check-model` | Verifica conectividade do modelo |
| `--dry-run` | Valida configuração e sai |
| `-w, --work-item` | Descrição do trabalho |
| `-f, --framework-root` | Raiz do framework (default: .) |
| `-l, --loop-root` | Raiz do loop (default: .) |
| `-p, --project-root` | Raiz do projeto (default: .) |

---

## Direcionar o Trabalho

### Work Item Completo

```bash
eng-loop --dynamic-graph -w "Add user authentication with JWT tokens" -f .eng -l .eng -p .
```

O loop executa automaticamente:
1. **Classifica complexidade** — small / medium / large / complex
2. **Classifica tipo de trabalho** — feature / bugfix / operational
3. **Constrói grafo dinâmico** — só stages ativas para essa complexidade + tipo
4. **INIT** — valida entrada, auto-size, skills
5. **Stages ativas** — design, arquitetura, impl, verify, QA, deploy, doc
6. **POST-LOOP** — finaliza, compartilha lições

### Stage Específica (Focus Directive)

Pedir "just implement" ou "run verify" é um **focus directive**, não um skip directive. Todas as stages ativas anteriores são executadas primeiro.

### Essence — Lens 4 (Scope Clarification)

Se o work item tem escopo muito amplo para a complexidade atual, o Essence Gate pergunta antes de bloquear:

```
Lens 4: scope exceeds complexity classification.
How would you like to proceed?
  (a) Narrow scope: Focus on the most critical flows first
  (b) Accept full scope: Proceed with all stages (will take longer)
  (c) Redefine: Provide a more specific work item
```

O bloqueio terminal s ocorre se `max_clarification_attempts` (default: 3) for exaurido.

### Visibilidade — Wall Clock Timer

O timer global `wall:HH:MM:SS` mostra o tempo total desde o incio do CLI, persistindo atravse de recovery attempts:

- **Progress bar**: `[████░░░░] 2/5 impl.code [00:15:32]`
- **Spinner**: `impl.code R read (5 tools, 120s, wall:00:15:32)`
- **Recovery**: `Recovery attempt 1/3 [wall: 00:10:45]`
- **Heartbeat**: `[impl.code] ... 300s (wall: 00:15:32)`
- **Stage Timing table**: `Total 00:45:00 (wall: 00:52:10)`

### Verificar Conectividade do Modelo

```bash
eng-loop --check-model -f .eng -l .eng -p .
```

### Dry Run (Validar Config)

```bash
eng-loop --dry-run -f .eng -l .eng -p .
```

### Dry-Run Simulator (v11.4) — Valida Grafos Sem LLM

```bash
# Roda todos os 4 cenários
python scripts/dry_run_simulator.py --scenario ALL

# Cenário específico
python scripts/dry_run_simulator.py --scenario VERIFY_ROLLBACK
```

Valida topologia, transições de estado e roteamento do grafo **sem chamadas LLM**. 4 cenários: HAPPY_PATH, CONTRACT_VIOLATION, VERIFY_ROLLBACK, QA_FANOUT_FAIL.

---

## Context Budget Manager (P0, v12.2.0)

Protecao de runtime para modelos locais. Janela de contexto é um recurso operacional limitado — como RAM, VRAM, CPU.

### Como Funciona

Antes de cada chamada LLM, o sistema verifica:

```
input_tokens + reserved_output + safety_margin <= context_window?
  Sim → prossegue
  Não → compacta (se auto) → re-verifica → se ainda não cabe → bloqueia
```

**O criterio de bloqueio NÃO é porcentagem.** É:

```
input + reserved_output + safety_margin > context_window → BLOQUEIA
```

### Estados de Pressão

| Estado | Uso | Comportamento |
|--------|-----|---------------|
| **SAFE** | < 70% | Execucao normal |
| **WATCH** | 70-85% | Monitoramento |
| **PRESSURE** | 85-95% | Auto-compacta |
| **EXHAUSTED** | > 95% ou sem budget seguro | Bloqueia chamada |

### Display no CLI

Durante execucao:

```
● impl.code                                      01:24

Context  24.8k / 32.8k  ████████████░░░░  75.7%  WATCH
Safe     5.9k remaining   ·  3 tool calls · 7.9k tokens
```

### Configuracao

```yaml
hardware:
  context_budget:
    enabled: true
    safety_margin_tokens: 2048
    compaction:
      mode: auto          # auto | suggest | disabled
    thresholds:
      safe: 0.70
      watch: 0.85
      pressure: 0.95
    reserved_output:
      default: 4096
      mode: fixed         # fixed | adaptive
```

### Compactacao

Rule-based, message-level. Preserva:
- SystemMessage (sempre)
- Primeiro HumanMessage (objetivo/work item)
- Respostas do Essence Gate / decisoes confirmadas
- Ultimas N trocas de ferramentas (default: 15)

Reduz:
- ToolMessage antigos → resumo compacto
- Resultados de ferramentas grandes (>2000 chars) → truncamento head/tail
- Outputs redundantes

Toda compactacao emite um `CompactionRecord` para auditoria. Nunca descarta contexto silenciosamente.

### Tokenizer

Tokenizer real, nao estimativa de 4 chars/token. Prioridade:

```
1. tiktoken (endpoints compatíveis OpenAI)
2. Tokenizer nativo do modelo
3. Fallback: 4 chars/token (estimado)
```

## Otimizações de Contexto (v11.3)

O loop agora pré-computa o contexto estrutural do projeto, eliminando tool-calls exploratórios repetidos.

### ProjectMap — Mapa Estrutural Pré-computado

No stage `init`, o Python escaneia o projeto e gera um mapa compacto:

```
## PROJECT MAP
### File Structure
myproject/
|-- src/
|   |-- api/routes.ts
|   `-- components/Login.tsx
|-- tests/
`-- package.json

### Config Files: package.json, tsconfig.json
### Entry Points: src/index.ts, src/main.py
### Languages: typescript: 42, python: 8
### Stats: total_files: 59
```

O mapa é injetado no prompt de **todas** as stages via `SystemPrefix`, eliminando 3-8 chamadas `glob`/`read` exploratórias por stage.

### Tool Cache — Cache de Resultados de Ferramentas

Dentro do micro-loop de cada stage, resultados de `read`, `glob` e `grep` são cacheados em memória:

- **Leitura repetida**: `read("package.json")` na iteração 1 → cache; iteração 2 → hit (sem I/O)
- **Invalidação direcionada**: `edit("src/auth.ts")` → invalida só o cache de `src/auth.ts`
- **Invalidação total**: `bash("npm test")` → limpa cache inteiro (pode modificar qualquer coisa)

Stats de hits/misses logados ao final de cada stage.

---

## Grafo Dinâmico — Stages por Complexidade

O grafo é construído baseado na complexidade e tipo de trabalho do work item:

| Nível | Stages Ativas | Design | Arch | QA | Exemplo |
|-------|--------------|--------|------|----|---------|
| **Small** | ~9/34 | Skip | Skip | Skip | Bug fix, 1-3 arquivos |
| **Medium** | ~20/34 | Inline | Requirements + Solution | Security + API contract | Feature clara, <8 tarefas |
| **Large** | ~24/34 | 6 stages formais | + Review | Full | Multi-componente, novas APIs |
| **Complex** | 34/34 | Formal + Discuss | Full + Review | Full + Performance | Novo domínio, ambiguidade |

### Tipos de Trabalho (v11.1)

O tipo de trabalho determina quais fases sao ativas:

| Tipo | O que faz | Stages desativadas |
|------|-----------|-------------------|
| **feature** | Nova funcionalidade | Nenhuma (loop completo) |
| **bugfix** | Corrigir comportamento | Design stages (6 stages) |
| **documentation** | Escrever/gerar documentos | design, verify, deploy, arch |
| **operational** | Rodar codigo existente (testes, deploy) | impl, design, arch, verify |

Exemplo: `"Execute todos os testes E2E contra Firebase"` → `operational` → 7 stages (init → e2e → deploy → smoke → post)

---

## Configuração

Edite `.eng/config.yaml` (gerado pelo install script):

| Setting | Default | Para que |
|---------|---------|----------|
| `model.base_url` | `http://localhost:8000` | Endpoint do modelo local |
| `model.model` | `qwable-v2` | Nome do modelo |
| `dynamic_graph.enabled` | `false` | Ativa grafo dinâmico |
| `dynamic_graph.parallel_qa` | `false` | QA stages em paralelo |
| `compliance.enabled` | `true` | Ativa gate de compliance entre stages |
| `compliance.mode` | `gate` | `gate` (bloqueia) ou `advisory` (avisa) |
| `state_history.enabled` | `true` | Salva snapshot apos cada stage (v11.2) |
| `state_history.retention_per_stage` | `5` | Max snapshots por stage (v11.2) |
| `constraints` | (veja template) | Limites de iteração por stage |
| `hardware` | (veja template) | Janela de contexto, timeouts |

---

## Referências

| Arquivo | Para que |
|---------|----------|
| `README.md` | Documentação completa |
| `CORE.md` | Registry de stages, skills, references |
| `ORCHESTRATOR.md` | Instruções do orquestrador (modo LLM) |
| `skill-index.md` | Registry de skills |
| `config.yaml` | Configuração do projeto (editável) |
| `state.json` | Estado do loop (gerado automaticamente) |
| `.eng/history/` | Snapshots de estado para time travel (v11.2) |
| `artifacts/graph-topology.md` | Plano de execução gerado (modo LLM) |
| `eng_loop/src/eng_loop/tools/contract_gate.py` | Middleware de contratos entre stages (v11.4) |
| `eng_loop/src/eng_loop/nodes/qa_parallel.py` | Fan-out/fan-in QA + rollback (v11.4) |
| `scripts/dry_run_simulator.py` | Simulador de dry-run (v11.4) |

---

## Versão

| Arquivo | Versão |
|---------|--------|
| Framework | v12.2.1 |
| Context Budget | Tokenizer real, budget por chamada, auto-compaction, prevencao overflow (P0) |
| Contract Gate | Middleware valida contratos entre stages (blueprint→code, code→verify) |
| Parallel QA | Fan-out/fan-in com qa-dispatcher + qa-join, rollback para impl.code |
| Causal Rollback | Reducer rollback_to_stage reset causal chain (impl.code → verify) |
| Fix Mode | impl.code executa com fix_tasks estruturados do verifier/QA |
| Dry-Run Simulator | 4 cenários validados: HAPPY_PATH, CONTRACT_VIOLATION, VERIFY_ROLLBACK, QA_FANOUT_FAIL |
| Deterministic Setup | init-setup separa classificação determinística do LLM |
| State Reducers | _merge_dict, _overwrite (clear fields), rollback_to_stage |
| Context Optimization | ProjectMap + ToolResultCache |
| Essence Lens 4 | Scope clarification antes de bloqueio (narrow/accept/redefine) |
| Wall Clock | Timer global persiste atravse de recovery attempts |
| Tests | 138 tests passing (essence, progress, recovery, fix_applier) |
