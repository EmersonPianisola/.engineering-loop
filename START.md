---
name: engineering-loop-start
type: entry-point
description: 'Start the engineering loop — quick reference for CLI and prompt mode.'
---

# Engineering Loop — Start Here

## Iniciar o Loop

### CLI (Recomendado)

```bash
eng-loop -w "descrição do trabalho" -f .eng -l .eng -p .
```

### Modo Prompt (Legacy)

Carregue `ORCHESTRATOR.md` na sessão do seu AI agent e forneça um work item.

---

## Direcionar o Trabalho

### Work Item Completo

```bash
eng-loop -w "Add user authentication with JWT tokens" -f .eng -l .eng -p .
```

O loop executa automaticamente:
1. **INIT** — valida entrada, auto-size classifica complexidade
2. **Stages ativas** — design, arquitetura, impl, verify, QA, deploy, doc
3. **POST-LOOP** — finaliza, compartilha lições

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

## Fluxo do Loop

```
INIT → auto-size → [Design] → [Arch] → Impl → Verify → QA → Deploy → Doc → POST
```

Complexidade determina profundidade:

| Nível | Design | Arch | QA | Exemplo |
|-------|--------|------|----|---------|
| **Small** | Skip | Skip | Skip | Bug fix, 1-3 arquivos |
| **Medium** | Inline | Requirements + Solution | Security + API contract | Feature clara, <8 tarefas |
| **Large** | 6 stages formais | + Review | Full | Multi-componente, novas APIs |
| **Complex** | Formal + Discuss | Full + Review | Full + Performance | Novo domínio, ambiguidade |

---

## Configuração

Edite `.eng/config.yaml` (gerado pelo install script):

| Setting | Default | Para que |
|---------|---------|----------|
| `model.base_url` | `http://localhost:8000` | Endpoint do modelo local |
| `model.model` | `qwable-v2` | Nome do modelo |
| `constraints` | (veja template) | Limites de iteração por stage |
| `hardware` | (veja template) | Janela de contexto, timeouts |

---

## Referências

| Arquivo | Para que |
|---------|----------|
| `README.md` | Documentação completa |
| `CORE.md` | Registry de stages, skills, references |
| `ORCHESTRATOR.md` | Instruções do orquestrador (modo prompt) |
| `skill-index.md` | Registry de skills |
| `config.yaml` | Configuração do projeto (editável) |
| `state.json` | Estado do loop (gerado automaticamente) |
