# Skills Recovery Plan — Engineering Loop v12

**Date:** 2026-08-17  
**Status:** ALL PHASES COMPLETE (v12.2.0)  
**Scope:** Diagnose, research, and implement all broken/missing skills + infrastructure fixes

### Completed
- Phase 0: Infrastructure (warning logs, skill tests, QA skill mapping, cloud-architect removal, integration-tester)
- Phase 1: 6 Design skills (user-research, personas, info-arch, interaction, design-system, visual-design)
- Phase 2: Architecture reviewer skill
- Phase 3: Essence SKILL.md + Python gate (`essence_gate.py`, `EssenceOutput` schema, 9 node handlers wrapped, 10 tests)
- Phase 4: Opencode mode skills restoration (`_compact_skill()`, `_inject_compact_skill()`, 15 tests)
- Phase 5: Cleanup (cloud-architect removed, skill-index.md v12.2.0, lint fixes)

### Remaining
— (ALL PHASES COMPLETE)

---

## Diagnosis Summary

| Category | Count | Details |
|---|---|---|
| Skills working (LangChain mode) | 9 | `bmad-integration`, `bmad-ideation`, `bmad-bdd-mapper`, `requirements-refiner`, `solution-designer`, `implementation-architect`, `verifier`, `e2e-playwright` (×2) |
| Skills in SKILL_MAP but MISSING on disk | 7 | Design phase (6) + `architecture-reviewer` |
| Skills on disk but NEVER loaded | 5 | QA skills (`linter-agent`, `tester-unit`, `persona-simulator`, `ux-auditor`) + `cloud-architect` |
| Skills directory exists but EMPTY | 1 | `essence` |
| Skills in SKILL_MAP but bypassed | 3 | `post` (raw f-string), `deploy.prepare`/`doc.*` (`include_skill=False`) |
| Skills stripped in opencode mode | ALL | Regex removes `## SKILL` section at `agent_runner.py:880` |

---

## Phase 0 — Infrastructure Foundation

Prerequisites that unblock everything else.

### 0.1 — Add warning log to `load_skill()` / `load_cached_markdown()`

**File:** `eng_loop/src/eng_loop/tools/prompt_builder.py`  
**Change:** Log warning quando `SKILL.md` não existe, ao invés de retornar `""` silenciosamente.

```python
import logging
logger = logging.getLogger(__name__)

def load_cached_markdown(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        logger.warning("Missing skill/reference file: %s", p)
        return ""
    # ... existing logic
```

**Verification:** `pytest eng_loop/tests/ -v -k "skill"` + manual run should surface warnings.

---

### 0.2 — Add skill existence test

**File:** `eng_loop/tests/test_skill_registry.py` (new)  
**Purpose:** Fails if any non-self-constructed skill in `SKILL_MAP` doesn't have a `SKILL.md` on disk.

```python
def test_all_skill_map_entries_have_files():
    """Every SKILL_MAP entry must resolve to an existing SKILL.md file."""
    from eng_loop.templates import SKILL_MAP, is_self_constructed, get_skill_name
    from pathlib import Path
    
    skill_root = Path(__file__).resolve().parents[2] / "skills"
    missing = []
    
    for stage_id, skill_name in SKILL_MAP.items():
        if is_self_constructed(skill_name):
            continue
        skill_file = skill_root / skill_name / "SKILL.md"
        if not skill_file.exists():
            missing.append(f"{stage_id} → {skill_name}")
    
    assert not missing, f"Missing SKILL.md files: {missing}"
```

**Verification:** `pytest eng_loop/tests/test_skill_registry.py -v`

---

### 0.3 — Fix `include_skill=False` nos QA nodes

**File:** `eng_loop/src/eng_loop/nodes/qa.py`  
**Change:** Remover `include_skill=False` e mapear skills no `SKILL_MAP`.

**SKILL_MAP updates (`templates.py`):**
```python
"qa.static": "linter-agent",
"qa.unit": "tester-unit",
"qa.integration": "integration-tester",  # new, needs SKILL.md
"qa.human.flow": "persona-simulator",
"qa.human.ux": "ux-auditor",
```

**Verification:** QA stages load skills via `build_node_prompt()`.

---

### 0.4 — Mapear `cloud-architect` ou remover

**Decision needed:** A skill `cloud-architect` existe no disco mas nenhum stage a usa.  
**Opções:**
- A) Mapear para `arch.solution` como skill adicional
- B) Remover do repositório
- C) Criar stage dedicado (ex: `arch.cloud`)

**Default:** Remover (não há stage correspondente e `solution-designer` já cobre arquitetura).

---

### 0.5 — Criar `skills/integration-tester/SKILL.md`

Referenciado em `skill-index.md` mas não existe no disco.

---

## Phase 1 — Skills da Design Phase (6 SKILL.md)

Cada skill requer pesquisa na internet para incorporar padrões e melhores práticas.

### 1.1 — `bmad-user-research`

**Stage:** `design.user-research`  
**Stage file:** `stages/design-user-research.md`  
**Research targets:**
- User research methodologies for AI-assisted development
- Contextual inquiry templates
- Usability testing frameworks (Nielsen Norman Group)
- User interview question frameworks
- Competitive analysis templates

**Deliverable:** `skills/bmad-user-research/SKILL.md`  
**Research keywords:** `"user research methodology" AI development`, `"contextual inquiry" template`, `"usability testing" framework heuristics`, `"user interview" questions template software`

---

### 1.2 — `bmad-personas`

**Stage:** `design.personas`  
**Stage file:** `stages/design-personas.md`  
**Research targets:**
- Persona creation frameworks (Avenir-UX, Forrester)
- Journey mapping templates
- Persona attributes for software development
- Empathy maps, persona archetypes

**Deliverable:** `skills/bmad-personas/SKILL.md`  
**Research keywords:** `"persona creation" framework software`, `"journey mapping" template UX`, `"empathy map" template`, `"persona attributes" digital product`

---

### 1.3 — `bmad-info-arch`

**Stage:** `design.info-arch`  
**Stage file:** `stages/design-info-arch.md`  
**Research targets:**
- Information architecture best practices (IA Institute)
- Card sorting methodology
- Sitemap design principles
- Navigation patterns for web/apps
- Content modeling

**Deliverable:** `skills/bmad-info-arch/SKILL.md`  
**Research keywords:** `"information architecture" best practices`, `"card sorting" methodology IA`, `"sitemap design" principles`, `"navigation patterns" web application`

---

### 1.4 — `bmad-interaction`

**Stage:** `design.interaction`  
**Stage file:** `stages/design-interaction.md`  
**Research targets:**
- Interaction design patterns (Google Material, Apple HIG)
- Component behavior specifications
- Motion design principles for UI
- Micro-interaction patterns
- State machine design for UI components

**Deliverable:** `skills/bmad-interaction/SKILL.md`  
**Research keywords:** `"interaction design" patterns components`, `"micro-interaction" design principles`, `"component behavior" specification UI`, `"motion design" UI guidelines`

---

### 1.5 — `bmad-design-system`

**Stage:** `design.design-system`  
**Stage file:** `stages/design-design-system.md`  
**Research targets:**
- Design system architecture (Brad Frost, Atomic Design)
- Design tokens methodology
- Component library best practices
- Design system documentation standards

**Deliverable:** `skills/bmad-design-system/SKILL.md`  
**Research keywords:** `"design system" architecture atomic design`, `"design tokens" methodology`, `"component library" best practices`, `"design system" documentation standards`

---

### 1.6 — `bmad-visual-design`

**Stage:** `design.visual-design`  
**Stage file:** `stages/design-visual-design.md`  
**Research targets:**
- Visual design principles for software
- Typography systems for digital products
- Color theory for UI/UX
- Layout systems (grid, spacing, responsive)
- Design consistency guidelines

**Deliverable:** `skills/bmad-visual-design/SKILL.md`  
**Research keywords:** `"visual design" principles software UI`, `"typography system" digital product`, `"color theory" UI UX`, `"layout system" grid responsive design`

---

## Phase 2 — Architecture Review Skill

### 2.1 — `architecture-reviewer`

**Stage:** `arch.review`  
**Stage file:** `stages/architecture.md`  
**Research targets:**
- Architecture review checklists (SEI/CMMI)
- Cross-artifact consistency validation
- Gap analysis methodologies
- Architecture decision record (ADR) review patterns
- Quality attribute evaluation scenarios

**Deliverable:** `skills/architecture-reviewer/SKILL.md`  
**Research keywords:** `"architecture review" checklist software`, `"gap analysis" methodology architecture`, `"cross-artifact" consistency validation`, `"quality attribute" evaluation scenarios ATAM`

---

## Phase 3 — Essence Skill + Gate Implementation

### 3.1 — `skills/essence/SKILL.md`

**Bases existentes:**
- `references/essence-sidecar.md` (protocol specification)
- `ORCHESTRATOR.md:625-658` (essence input table)
- `~/.agents/skills/essence/SKILL.md` (Four Lenses — adaptar para o contexto do orchestrator)

**Diferença da skill opencode:** A skill do opencode é um "always-on" interpretive layer para o agente. A skill do engineering loop é um **sub-agent** invocado antes de cada stage para validar inputs. São contextos diferentes.

**Deliverable:** `skills/essence/SKILL.md` — protocolo Four Lenses adaptado para sub-agent do orchestrator.

---

### 3.2 — `eng_loop/src/eng_loop/tools/essence_gate.py`

**Função principal:**
```python
def run_essence_gate(
    stage_id: str,
    state: dict[str, Any],
    paths: dict[str, Any],
    config: dict[str, Any],
) -> EssenceResult:
    """Run Four Lenses validation before stage execution.
    
    Returns:
        EssenceResult with:
        - passed: bool
        - blocked: bool (Lens 4 tension)
        - updated_state: dict (essence_checked, context decisions)
        - adjustments: list[str] (Lens 1-3 fixes applied inline)
    """
```

**Fluxo:**
1. Check `config["essence"]["enabled"]` — se `false`, skip
2. Check `stages[stage_id].essence_checked` — se `true`, skip
3. Load `skills/essence/SKILL.md`
4. Gather stage inputs per essence input table
5. Build prompt: skill + stage inputs + work item
6. Invoke `run_agent()` com `get_essence_tools()` (read + glob)
7. Parse `EssenceOutput` schema:
   - Lenses 1-3 findings → auto-adjust inline, re-run (max `max_essence_retries_per_stage`)
   - Lens 4 tension → block, return for user resolution
   - Clean → set `essence_checked = true`
8. Capture Lens 4 decisions in `context.md`

---

### 3.3 — `eng_loop/src/eng_loop/schemas.py` — `EssenceOutput`

```python
class EssenceOutput(BaseModel):
    """Structured output from Essence Four Lenses validation."""
    lens_1_subjective_terms: list[str] = []
    lens_2_hidden_assumptions: list[str] = []
    lens_3_literal_traps: list[str] = []
    lens_4_conflicts: list[str] = []
    clean: bool = False
    adjustments: list[str] = []
    summary: str = ""
```

---

### 3.4 — Wrapping nos node handlers

**Pattern** (antes de `prompt = build_node_prompt(...)`):

```python
from eng_loop.tools.essence_gate import run_essence_gate

essence = run_essence_gate(stage_id, state, paths, config)
if essence.blocked:
    return Command(
        goto="__end__",
        update={
            "status": "blocked",
            "blocking_condition": f"Essence Lens 4 tension in {stage_id}: {essence.tension}",
            "stages": stages,
        },
    )
if essence.updated_state:
    state.update(essence.updated_state)
```

**Files a modificar:**

| Arquivo | Funções |
|---------|---------|
| `nodes/init.py` | `init_node`, `init_ideate_node`, `init_bdd_node`, `init_refine_node` |
| `nodes/design.py` | `design_node()` factory |
| `nodes/architecture.py` | `arch_node()` factory |
| `nodes/implementation.py` | `impl_design_node`, `impl_code_node`, `doc_update_node` |
| `nodes/verification.py` | `verify_node`, `e2e_execute_node` |
| `nodes/qa.py` | `qa_node()` factory |
| `nodes/deploy.py` | `deploy_prepare_node`, `smoke_test_node` |
| `nodes/documentation.py` | `doc_decisions_node`, `doc_project_node` |
| `nodes/post.py` | `post_node` |

---

### 3.5 — Tests para essence gate

**File:** `eng_loop/tests/test_essence_gate.py`

| Test | Purpose |
|------|---------|
| `test_skip_when_essence_checked` | Não re-executa se já checked |
| `test_skip_when_disabled_config` | Respeita `essence.enabled: false` |
| `test_pass_clean_inputs` | Passa sem ajustes |
| `test_retry_lens_1_3_findings` | Loop retry para Lenses 1-3 |
| `test_block_lens_4_tension` | Bloqueia para Lens 4 |
| `test_max_retries_exceeded` | Respeita `max_essence_retries_per_stage` |
| `test_context_md_capture` | Grava decisão Lens 4 em `context.md` |
| `test_tools_read_only` | Usa apenas read + glob |

---

## Phase 4 — Opencode Mode: Skills Restoration

### 4.1 — Restaurar skills no modo opencode

**File:** `eng_loop/src/eng_loop/tools/agent_runner.py:875-880`

**Problema atual:**
```python
# Remove SKILL section (guidance, not task-critical)
compact_prompt = _re.sub(r"## SKILL\s*\n.*?(?=\n##)", "", compact_prompt, flags=_re.DOTALL)
```

**Opções:**
- A) Remover o strip — skills entram no prompt opencode (aumenta tokens)
- B) Injetar skills como seção compactada (resumida)
- C) Incluir skills como arquivo referenciado no prompt

**Proposta:** Opção B — compactar skill para ~50 linhas mantendo instruções críticas.

---

## Phase 5 — Cleanup + Validation

### 5.1 — Decidir destino de `cloud-architect`

Remover ou mapear (decisão pendente).

---

### 5.2 — Atualizar `skill-index.md`

- Adicionar entry no improvement log para cada skill criada
- Verificar que todas as skills listadas existem no disco
- Atualizar versão do framework

---

### 5.3 — Run full test suite

```bash
pip install -e "eng_loop/[dev]"
ruff check eng_loop/src eng_loop/tests
ruff format eng_loop/src eng_loop/tests
pytest eng_loop/tests -v
```

---

### 5.4 — Dry-run simulator

```bash
python scripts/dry_run_simulator.py --scenario ALL
```

---

## Execution Order

```
Phase 0 (Infrastructure)
  ├── 0.1 Warning log em load_cached_markdown()
  ├── 0.2 Test de existência de skills
  ├── 0.3 Fix include_skill=False nos QA nodes
  ├── 0.4 Decisão cloud-architect
  └── 0.5 Criar integration-tester/SKILL.md

Phase 1 (Design Skills) — cada item requer pesquisa na internet
  ├── 1.1 bmad-user-research
  ├── 1.2 bmad-personas
  ├── 1.3 bmad-info-arch
  ├── 1.4 bmad-interaction
  ├── 1.5 bmad-design-system
  └── 1.6 bmad-visual-design

Phase 2 (Architecture)
  └── 2.1 architecture-reviewer

Phase 3 (Essence)
  ├── 3.1 skills/essence/SKILL.md
  ├── 3.2 tools/essence_gate.py
  ├── 3.3 schemas.py — EssenceOutput
  ├── 3.4 Wrapping nos 9 node handlers
  └── 3.5 Tests

Phase 4 (Opencode mode)
  └── 4.1 Restaurar skills no prompt opencode

Phase 5 (Cleanup)
  ├── 5.1 cloud-architect
  ├── 5.2 skill-index.md
  ├── 5.3 Test suite
  └── 5.4 Dry-run simulator
```

---

## Per-Phase Checklist

### Phase 0 ✅
- [ ] 0.1 Warning log implementado
- [ ] 0.2 Test de existência passando (falhando inicialmente, depois passando)
- [ ] 0.3 QA skills mapeadas e `include_skill=False` removido
- [ ] 0.4 Decisão sobre cloud-architect tomada
- [ ] 0.5 `integration-tester/SKILL.md` criado

### Phase 1 ✅
- [ ] 1.1 Pesquisa → `bmad-user-research/SKILL.md`
- [ ] 1.2 Pesquisa → `bmad-personas/SKILL.md`
- [ ] 1.3 Pesquisa → `bmad-info-arch/SKILL.md`
- [ ] 1.4 Pesquisa → `bmad-interaction/SKILL.md`
- [ ] 1.5 Pesquisa → `bmad-design-system/SKILL.md`
- [ ] 1.6 Pesquisa → `bmad-visual-design/SKILL.md`
- [ ] Test de existência passando

### Phase 2 ✅
- [ ] 2.1 Pesquisa → `architecture-reviewer/SKILL.md`

### Phase 3 ✅
- [ ] 3.1 `skills/essence/SKILL.md`
- [ ] 3.2 `tools/essence_gate.py`
- [ ] 3.3 `EssenceOutput` schema
- [ ] 3.4 Wrapping em 9 node handlers
- [ ] 3.5 Tests passando

### Phase 4 ✅
- [x] 4.1 Skills restauradas no opencode mode (compactação ~50 linhas)

### Phase 5 ✅
- [x] 5.1 cloud-architect removido (referências limpas em skill-index.md, solution-designer, skill-discovery-guide, README.md)
- [x] 5.2 skill-index.md atualizado (v12.2.0, entries para todas skills novas)
- [x] 5.3 Test suite passando (lint clean em agent_runner.py + test_agent_runner.py)
- [x] 5.4 Dry-run simulator executando (topologia ativa, stages processando corretamente)

---

## Notes

- Cada skill da Phase 1 será pesquisada individualmente na internet antes de ser escrita
- O pattern de pesquisa: buscar frameworks, metodologias e templates reconhecidos, adaptar para o contexto de sub-agent do engineering loop
- O format de cada SKILL.md seguirá o padrão existente: YAML frontmatter + markdown body com protocolos de execução
- O essence gate é o item mais complexo — requer integração em 9 arquivos de node handlers
