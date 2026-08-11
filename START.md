---
name: engineering-loop-start
type: entry-point
description: 'Start the engineering loop — quick reference for CLI and prompt mode.'
---

# Engineering Loop v11 — Start Here

## Iniciar o Loop

### CLI — Modo Python (Determinístico)

```bash
# Grafo dinâmico (v11, recomendado)
eng-loop --dynamic-graph -w "descrição do trabalho" -f .eng -l .eng -p .

# Com paralelismo QA
eng-loop --dynamic-graph --parallel-qa -w "descrição do trabalho" -f .eng -l .eng -p .

# Grafo estático (legacy, default)
eng-loop -w "descrição do trabalho" -f .eng -l .eng -p .
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
3. Seguir o plano exatamente — stages ativas, roteamento, constraints

---

## Flags do CLI

| Flag | Para que |
|------|----------|
| `--dynamic-graph` | Ativa grafo dinâmico (v11) — só nós necessários |
| `--parallel-qa` | QA stages em paralelo (fan-out/fan-in) |
| `--opencode-agent` | Modo hibrido: Python controla grafo, OpenCode executa stages com tools nativas |
| `--build-topology` | Gera topology markdown para modo LLM |
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
2. **Constrói grafo dinâmico** — só stages ativas para essa complexidade
3. **INIT** — valida entrada, auto-size, skills
4. **Stages ativas** — design, arquitetura, impl, verify, QA, deploy, doc
5. **POST-LOOP** — finaliza, compartilha lições

### Stage Específica (Focus Directive)

Pedir "just implement" ou "run verify" é um **focus directive**, não um skip directive. Todas as stages ativas anteriores são executadas primeiro.

### Verificar Conectividade do Modelo

```bash
eng-loop --check-model -f .eng -l .eng -p .
```

### Dry Run (Validar Config)

```bash
eng-loop --dry-run -f .eng -l .eng -p .
```

---

## Grafo Dinâmico — Stages por Complexidade

O grafo é construído baseado na complexidade do work item:

| Nível | Stages Ativas | Design | Arch | QA | Exemplo |
|-------|--------------|--------|------|----|---------|
| **Small** | ~9/26 | Skip | Skip | Skip | Bug fix, 1-3 arquivos |
| **Medium** | ~20/26 | Inline | Requirements + Solution | Security + API contract | Feature clara, <8 tarefas |
| **Large** | ~24/26 | 6 stages formais | + Review | Full | Multi-componente, novas APIs |
| **Complex** | 26/26 | Formal + Discuss | Full + Review | Full + Performance | Novo domínio, ambiguidade |

---

## Configuração

Edite `.eng/config.yaml` (gerado pelo install script):

| Setting | Default | Para que |
|---------|---------|----------|
| `model.base_url` | `http://localhost:8000` | Endpoint do modelo local |
| `model.model` | `qwable-v2` | Nome do modelo |
| `dynamic_graph.enabled` | `false` | Ativa grafo dinâmico |
| `dynamic_graph.parallel_qa` | `false` | QA stages em paralelo |
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
| `artifacts/graph-topology.md` | Plano de execução gerado (modo LLM) |
