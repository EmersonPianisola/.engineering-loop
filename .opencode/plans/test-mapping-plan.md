# PLANO DE MAPEAMENTO DE TESTES — Engineering Loop v11

> Executar gradualmente, fase por fase. Cada fase deve passar 100% antes de avançar.
>
> Status legend: `⬜` pendente | `🟡` em progresso | `✅` completo | `❌` falhou

---

## FASE 0 — Infraestrutura e Pré-requisitos

Objetivo: garantir que o ambiente de testes está funcional.

| # | Teste | Comando | Status |
|---|-------|---------|--------|
| 0.1 | Instalar dependências dev | `pip install -e "eng_loop/[dev]"` | ⬜ |
| 0.2 | Suite completa roda sem erro de import | `pytest eng_loop/tests -v --tb=short` | ⬜ |
| 0.3 | Lint passa | `ruff check eng_loop/src eng_loop/tests` | ⬜ |
| 0.4 | Format passa | `ruff format eng_loop/src eng_loop/tests --check` | ⬜ |
| 0.5 | CLI entry point disponível | `eng-loop --help` | ⬜ |

---

## FASE 1 — Nós do Grafo (26 Node Handlers)

Objetivo: validar que cada um dos 26 nós processa state corretamente isoladamente.

### 1A — Registry e Metadata (coberto: `test_nodes.py`, `test_dynamic_graph.py`)

| # | Teste | Arquivo | Status |
|---|-------|---------|--------|
| 1.1 | Registry cria 26 NodeSpecs | `test_dynamic_graph.py::test_registry_builds` | ✅ |
| 1.2 | Todos handlers são callable | `test_nodes.py::test_all_handlers_callable` | ✅ |
| 1.3 | Todos specs têm description e phase | `test_nodes.py` | ✅ |
| 1.4 | Node name conversion (dots → hyphens) | `test_nodes.py::test_node_name_conversion` | ✅ |
| 1.5 | Complexity thresholds corretos | `test_nodes.py::test_complexity_thresholds` | ✅ |
| 1.6 | UI-required nodes (e2e, smoke) | `test_nodes.py::test_ui_required_nodes` | ✅ |
| 1.7 | Parallel groups (QA) | `test_nodes.py::test_parallel_group` | ✅ |
| 1.8 | Excluded work types | `test_nodes.py::test_excluded_work_types` | ✅ |
| 1.9 | Filter por complexity: small | `test_dynamic_graph.py::test_registry_filter_small` | ✅ |
| 1.10 | Filter por complexity: medium | `test_dynamic_graph.py::test_registry_filter_medium` | ✅ |
| 1.11 | Filter por complexity: large + UI | `test_dynamic_graph.py::test_registry_filter_large_ui` | ✅ |
| 1.12 | Filter por complexity: complex + UI | `test_dynamic_graph.py::test_registry_filter_complex` | ✅ |
| 1.13 | Phase grouping (init=4, design=6, qa=3) | `test_dynamic_graph.py::test_registry_phase_grouping` | ✅ |

### 1B — Handlers Isolados (coberto: `test_nodes.py`)

Cada handler recebe um state válido e retorna dict/Command.

| # | Node | Teste Existente | Status |
|---|------|-----------------|--------|
| 1.14 | `init` | `test_init_node_receives_state` | ✅ |
| 1.15 | `init.ideate` | `test_init_ideate_node` | ✅ |
| 1.16 | `init.refine` | `test_init_refine_node` | ✅ |
| 1.17 | `impl.design` | `test_impl_design_node` | ✅ |
| 1.18 | `impl.code` | `test_impl_code_node` | ✅ |
| 1.19 | `doc.update` | `test_doc_update_node` | ✅ |
| 1.20 | `verify` | `test_verify_node` | ✅ |
| 1.21 | `qa.security` | `test_qa_security_node` | ✅ |
| 1.22 | `qa.api-contract` | `test_qa_api_contract_node` | ✅ |
| 1.23 | `deploy.prepare` | `test_deploy_prepare_node` | ✅ |
| 1.24 | `doc.decisions` | `test_doc_decisions_node` | ✅ |
| 1.25 | `doc.project` | `test_doc_project_node` | ✅ |
| 1.26 | `post` | `test_post_node` | ✅ |

### 1C — Handlers NÃO Cobertos (FALHAS CRÍTICAS)

| # | Node | Problema | Ação |
|---|------|----------|------|
| 1.27 | `init.bdd` | Sem teste isolado | Criar teste |
| 1.28 | `design.user-research` | Sem teste isolado | Criar teste |
| 1.29 | `design.personas` | Sem teste isolado | Criar teste |
| 1.30 | `design.info-arch` | Sem teste isolado | Criar teste |
| 1.31 | `design.interaction` | Sem teste isolado | Criar teste |
| 1.32 | `design.design-system` | Sem teste isolado | Criar teste |
| 1.33 | `design.visual-design` | Sem teste isolado | Criar teste |
| 1.34 | `arch.requirements` | Sem teste isolado | Criar teste |
| 1.35 | `arch.solution` | Sem teste isolado | Criar teste |
| 1.36 | `arch.review` | Sem teste isolado | Criar teste |
| 1.37 | `e2e.execute` | Sem teste isolado | Criar teste |
| 1.38 | `qa.performance` | Sem teste isolado | Criar teste |
| 1.39 | `smoke.test` | Sem teste isolado | Criar teste |

### 1D — Testes de Handler com State Realista

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 1.40 | Handler retorna LangGraph Command | Verificar `goto` e `update` em resultado | ⬜ |
| 1.41 | Handler com work_item vazio | Behavior com state mínimo | ⬜ |
| 1.42 | Handler com paths inválidos | Graceful degradation | ⬜ |
| 1.43 | Handler com config ausente | Defaults aplicados | ⬜ |

---

## FASE 2 — Geração Dinâmica de Grafos

Objetivo: validar que o grafo muda adequadamente para cada contexto.

### 2A — GraphBuilder (coberto: `test_dynamic_graph.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 2.1 | Small complexity grafo | Nodes < total, sem design/arch/QA | ✅ |
| 2.2 | Complex + UI grafo | Todos 26 nodes ativos | ✅ |
| 2.3 | Topology serialização (dict + JSON) | `test_graph_topology_serialization` | ✅ |
| 2.4 | Graph compila sem erro | `test_graph_compiles` | ✅ |
| 2.5 | Topology markdown generation | `test_topology_markdown_generation` | ✅ |

### 2B — Edge Rules e Bypass (coberto: `test_routing.py`, `test_dynamic_graph.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 2.6 | Edge rules engine: add fixed/conditional/loopback | `test_routing.py` | ✅ |
| 2.7 | Resolve filtra por active nodes | `test_routing.py` | ✅ |
| 2.8 | get_next_nodes funciona | `test_routing.py` | ✅ |
| 2.9 | Entry point (__start__ → init) | `test_routing.py` | ✅ |
| 2.10 | Init tem 2 paths (ideate + __end__) | `test_routing.py` | ✅ |
| 2.11 | Post → __end__ | `test_routing.py` | ✅ |
| 2.12 | Verify loopback para impl-code | `test_routing.py` | ✅ |
| 2.13 | Parallel QA flag | `test_routing.py` | ✅ |
| 2.14 | Bypass de nodes inativos | `test_routing.py::test_bypass_inactive_nodes` | ✅ |

### 2C — Routing Scenarios (coberto: `test_routing.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 2.15 | Small complexity flow | init → impl → verify → deploy → post | ✅ |
| 2.16 | Medium complexity flow | init → arch → impl → verify → QA → deploy | ✅ |
| 2.17 | Blocked → terminate | `test_blocked_terminates` | ✅ |
| 2.18 | Complex complexity flow | arch.review ativo | ✅ |

### 2D — Routing Scenarios NÃO Cobertos (FALHAS)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 2.19 | Large + UI flow completo | design → arch → impl → verify → e2e → QA → deploy → smoke → doc → post | ⬜ |
| 2.20 | Verify FAIL → loopback impl.code | State com verify.done=false, attempts>0 | ⬜ |
| 2.21 | E2E FAIL → loopback impl.code | State com e2e.done=false | ⬜ |
| 2.22 | QA FAIL → loopback impl.code | State com qa.done=false | ⬜ |
| 2.23 | Deploy FAIL → loopback impl.code | State com deploy.done=false | ⬜ |
| 2.24 | Smoke FAIL → loopback impl.code | State com smoke.done=false | ⬜ |
| 2.25 | Work type = documentation | Apenas init → impl.code → post | ⬜ |
| 2.26 | Work type = operational | Skips impl/design/arch | ⬜ |
| 2.27 | Work type = bugfix | Skips design stages | ⬜ |
| 2.28 | Graph com bypass múltiplo | init-ideate → (bypass init-bdd) → init-refine | ⬜ |

---

## FASE 3 — Gerenciamento de Contexto

Objetivo: validar handoffs, context tiers, context slice e consolidator.

### 3A — Context Slice e Tiers

| # | Teste | Arquivo/Descrição | Status |
|---|-------|-------------------|--------|
| 3.1 | `context_slice.py` — slice por tier | Criar teste | ⬜ |
| 3.2 | `context_tier.py` — tier assignment | Criar teste | ⬜ |
| 3.3 | `context_consolidator.py` — merge context | Criar teste | ⬜ |
| 3.4 | Handoffs entre stages | state.json com handoffs populados | ⬜ |
| 3.5 | context_tiers no PipelineState | `test_state.py` — verificar campos | ⬜ |

### 3B — ProjectMap e Tool Cache (coberto: `test_context_optimization.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 3.6 | ProjectMap build em dir vazio | `test_build_on_empty_dir` | ✅ |
| 3.7 | ProjectMap detecta Python/TS files | ✅ | ✅ |
| 3.8 | ProjectMap detecta config files | ✅ | ✅ |
| 3.9 | ProjectMap detecta entry points | ✅ | ✅ |
| 3.10 | ProjectMap detecta test dirs | ✅ | ✅ |
| 3.11 | ProjectMap exclui node_modules/.git | ✅ | ✅ |
| 3.12 | ProjectMap tree ASCII-only | ✅ | ✅ |
| 3.13 | ProjectMap serialization roundtrip | ✅ | ✅ |
| 3.14 | ProjectMap prompt section | ✅ | ✅ |
| 3.15 | ToolResultCache: cache read | ✅ | ✅ |
| 3.16 | ToolResultCache: invalidation on edit/write | ✅ | ✅ |
| 3.17 | ToolResultCache: bash invalida tudo | ✅ | ✅ |
| 3.18 | ToolResultCache: edit preserva outros files | ✅ | ✅ |
| 3.19 | CACHABLE_TOOLS / INVALIDATING_TOOLS | ✅ | ✅ |

### 3C — Agent Runner (coberto: `test_agent_runner.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 3.20 | AgentResult creation | ✅ | ✅ |
| 3.21 | Build agent prompt: tools, instructions, JSON | ✅ | ✅ |
| 3.22 | Execute tool: success, not found, truncate, exception | ✅ | ✅ |
| 3.23 | Execute tool cached | ✅ | ✅ |
| 3.24 | Compact messages | ✅ | ✅ |
| 3.25 | Error detection: traceback, test failure, syntax | ✅ | ✅ |
| 3.26 | Summarize error | ✅ | ✅ |
| 3.27 | Extract from text: JSON, markdown, fallback | ✅ | ✅ |
| 3.28 | Extract best effort from messages | ✅ | ✅ |
| 3.29 | Last AI message | ✅ | ✅ |

---

## FASE 4 — Tools da LLM

Objetivo: validar as 6 tools usadas pela LLM (read, write, edit, bash, glob, grep).

### 4A — Read Tool (coberto: `test_tools.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 4.1 | Read file | ✅ | ✅ |
| 4.2 | Read com offset/limit | ✅ | ✅ |
| 4.3 | Read paginação | ✅ | ✅ |
| 4.4 | Read directory | ✅ | ✅ |
| 4.5 | Read nonexistent | ✅ | ✅ |
| 4.6 | Read linhas longas (truncado) | ✅ | ✅ |
| 4.7 | Read tool metadata | ✅ | ✅ |

### 4B — Write Tool (coberto: `test_tools.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 4.8 | Write file | ✅ | ✅ |
| 4.9 | Write cria parent dirs | ✅ | ✅ |
| 4.10 | Write overwrites | ✅ | ✅ |
| 4.11 | Write tool metadata | ✅ | ✅ |

### 4C — Edit Tool (coberto: `test_tools.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 4.12 | Edit replace string | ✅ | ✅ |
| 4.13 | Edit file not found | ✅ | ✅ |
| 4.14 | Edit old string not found | ✅ | ✅ |
| 4.15 | Edit múltiplas occurrences | ✅ | ✅ |
| 4.16 | Edit strings idênticas | ✅ | ✅ |
| 4.17 | Edit tool metadata | ✅ | ✅ |

### 4D — Bash Tool (coberto: `test_tools.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 4.18 | Bash success | ✅ | ✅ |
| 4.19 | Bash failure | ✅ | ✅ |
| 4.20 | Bash workdir inexistente | ✅ | ✅ |
| 4.21 | Bash timeout | ✅ | ✅ |
| 4.22 | Bash pwd | ✅ | ✅ |
| 4.23 | Bash no output | ✅ | ✅ |
| 4.24 | Bash stderr | ✅ | ✅ |
| 4.25 | Bash tool metadata | ✅ | ✅ |

### 4E — Glob Tool (coberto: `test_tools.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 4.26 | Glob finds files | ✅ | ✅ |
| 4.27 | Glob recursive | ✅ | ✅ |
| 4.28 | Glob no matches | ✅ | ✅ |
| 4.29 | Glob nonexistent dir | ✅ | ✅ |
| 4.30 | Glob many files (250) | ✅ | ✅ |
| 4.31 | Glob tool metadata | ✅ | ✅ |

### 4F — Grep Tool (coberto: `test_tools.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 4.32 | Grep finds pattern | ✅ | ✅ |
| 4.33 | Grep include filter | ✅ | ✅ |
| 4.34 | Grep no matches | ✅ | ✅ |
| 4.35 | Grep invalid regex | ✅ | ✅ |
| 4.36 | Grep skips binary | ✅ | ✅ |
| 4.37 | Grep line numbers | ✅ | ✅ |
| 4.38 | Grep tool metadata | ✅ | ✅ |

### 4G — Stage Tools Configuration (coberto: `test_tools.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 4.39 | impl.code = full toolkit (6 tools) | ✅ | ✅ |
| 4.40 | init = readonly (read, glob, grep) | ✅ | ✅ |
| 4.41 | verify tem bash | ✅ | ✅ |
| 4.42 | deploy tem bash | ✅ | ✅ |
| 4.43 | get_tools retorna count correto | ✅ | ✅ |
| 4.44 | get_essence_tools = read + glob | ✅ | ✅ |
| 4.45 | Unknown stage defaults to read | ✅ | ✅ |
| 4.46 | All stages have tool definitions | ✅ | ✅ |

---

## FASE 5 — HUD e UI

Objetivo: validar HUDRenderer, ExecutionState, EventNormalizer, e progress rendering.

### 5A — HUD Helpers e Mappings (coberto: `test_hud.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 5.1 | ActionLog append + render | ✅ | ✅ |
| 5.2 | ActionLog max_lines enforced | ✅ | ✅ |
| 5.3 | ActionLog log levels | ✅ | ✅ |
| 5.4 | ActionLog thread safety | ✅ | ✅ |
| 5.5 | All stages have class mapping | ✅ | ✅ |
| 5.6 | All classes have icons | ✅ | ✅ |
| 5.7 | Phase order, labels, colors | ✅ | ✅ |
| 5.8 | stage_to_node / node_to_stage | ✅ | ✅ |
| 5.9 | get_phase | ✅ | ✅ |
| 5.10 | draw_bar (full, empty, zero max) | ✅ | ✅ |
| 5.11 | format_duration (s, m, h) | ✅ | ✅ |

### 5B — HUDRenderer (coberto: `test_hud.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 5.12 | Renderer creation | ✅ | ✅ |
| 5.13 | Log message | ✅ | ✅ |
| 5.14 | set/clear current stage | ✅ | ✅ |
| 5.15 | Role lookup (WARRIOR, MAGE, etc.) | ✅ | ✅ |
| 5.16 | Color lookup | ✅ | ✅ |
| 5.17 | Quest status style | ✅ | ✅ |
| 5.18 | Node status mark (completed, active, failed) | ✅ | ✅ |
| 5.19 | HP bar | ✅ | ✅ |
| 5.20 | format_time | ✅ | ✅ |
| 5.21 | class_for_stage | ✅ | ✅ |
| 5.22 | Unknown stage → NPC | ✅ | ✅ |

### 5C — ExecutionState (coberto: `test_execution_state.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 5.23 | ThreatEvaluator: LOW/MEDIUM/HIGH/CRITICAL | ✅ | ✅ |
| 5.24 | ThreatEvaluator: zero max, context ratio | ✅ | ✅ |
| 5.25 | Initial state (PENDING) | ✅ | ✅ |
| 5.26 | Node started → RUNNING | ✅ | ✅ |
| 5.27 | Node completed | ✅ | ✅ |
| 5.28 | Quest completed/failed/cancelled | ✅ | ✅ |
| 5.29 | Active party (during/after) | ✅ | ✅ |
| 5.30 | Topology | ✅ | ✅ |
| 5.31 | Snapshot | ✅ | ✅ |
| 5.32 | Quest summary | ✅ | ✅ |
| 5.33 | Resource consumed | ✅ | ✅ |
| 5.34 | Agent action | ✅ | ✅ |
| 5.35 | Tool started/failed | ✅ | ✅ |

### 5D — EventNormalizer (coberto: `test_execution_state.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 5.36 | Node entered (exec_id, attempt) | ✅ | ✅ |
| 5.37 | Node completed | ✅ | ✅ |
| 5.38 | Attempt counter increments | ✅ | ✅ |
| 5.39 | Agent action via normalizer | ✅ | ✅ |
| 5.40 | Tool lifecycle | ✅ | ✅ |
| 5.41 | Tokens consumed | ✅ | ✅ |
| 5.42 | Quest lifecycle | ✅ | ✅ |
| 5.43 | HUDTelemetryCallback: extract node name | ✅ | ✅ |

### 5E — Progress e UIManager (PARCIALMENTE coberto)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 5.44 | UIManager render_topology | Criar teste | ⬜ |
| 5.45 | UIManager render_progress_bar | Criar teste | ⬜ |
| 5.46 | UIManager render_result | Criar teste | ⬜ |
| 5.47 | UIManager render_evidence_gate | Criar teste | ⬜ |
| 5.48 | UIManager show_breakpoint_menu | `test_interactive.py` | ⬜ |
| 5.49 | StageSpinner start/stop/update | Criar teste | ⬜ |
| 5.50 | stage_context manager | Criar teste | ⬜ |
| 5.51 | trace_node decorator | Criar teste | ⬜ |
| 5.52 | log_stage_enter/done/complete/fail/retry | Criar teste | ⬜ |
| 5.53 | HUD start/stop/update lifecycle | Criar teste | ⬜ |
| 5.54 | HUD legacy rendering (sem execution_state) | Criar teste | ⬜ |
| 5.55 | HUD snapshot-based rendering | Criar teste | ⬜ |

---

## FASE 6 — State Management

Objetivo: validar PipelineState, reducers, snapshots, e history.

### 6A — State Core (coberto: `test_state.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 6.1 | STAGE_ORDER = 26 stages | ✅ | ✅ |
| 6.2 | make_initial_state | ✅ | ✅ |
| 6.3 | get_active_stages: small/medium/large/complex | ✅ | ✅ |
| 6.4 | next_incomplete_stage | ✅ | ✅ |
| 6.5 | all_active_stages_done | ✅ | ✅ |
| 6.6 | get_max_attempts | ✅ | ✅ |

### 6B — State History e Snapshots (coberto: `test_state_history.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 6.7 | Save snapshot | Verificar `test_state_history.py` | ⬜ |
| 6.8 | List snapshots | Verificar `test_state_history.py` | ⬜ |
| 6.9 | Rollback to snapshot | Verificar `test_state_history.py` | ⬜ |
| 6.10 | restore_snapshot function | `state.py::restore_snapshot` | ⬜ |
| 6.11 | Snapshot merge com defaults | Campos novos adicionados | ⬜ |

### 6C — Schemas Pydantic (coberto: `test_schemas.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 6.12 | All 26 stages have schema | Verificar `test_schemas.py` | ⬜ |
| 6.13 | Schema validation: valid data | ⬜ |
| 6.14 | Schema validation: invalid data | ⬜ |
| 6.15 | STAGE_SCHEMA mapping completo | ⬜ |
| 6.16 | get_schema returns correct type | ⬜ |

### 6D — Config (coberto: `test_config.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 6.17 | load_config: merge template + project | Verificar `test_config.py` | ⬜ |
| 6.18 | resolve_paths | ⬜ |
| 6.19 | ensure_directories | ⬜ |
| 6.20 | Deep merge behavior | ⬜ |

---

## FASE 7 — Auto-sizing e Classificação

Objetivo: validar classify_complexity, classify_work_type, detect_ui_project.

### 7A — Complexity Classification

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 7.21 | Small work item | "Fix typo in README" | ⬜ |
| 7.22 | Medium work item | "Add API endpoint" | ⬜ |
| 7.23 | Large work item | "Implement auth with oauth" | ⬜ |
| 7.24 | Complex work item | ML/AI + integration + ambiguity | ⬜ |
| 7.25 | _estimate_files | ⬜ |
| 7.26 | _estimate_tasks | ⬜ |
| 7.27 | _has_new_domains | ⬜ |
| 7.28 | _has_integrations | ⬜ |
| 7.29 | _has_ambiguity | ⬜ |

### 7B — Work Type Classification

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 7.30 | Documentation work | "Write project summary" | ⬜ |
| 7.31 | Operational work | "Run tests" | ⬜ |
| 7.32 | Bugfix work | "Fix broken login" | ⬜ |
| 7.33 | Feature work (default) | "Implement new feature" | ⬜ |
| 7.34 | Tier 1 vs Tier 2 scoring | ⬜ |
| 7.35 | Portuguese keywords | "Escrever resumo do projeto" | ⬜ |
| 7.36 | DOCUMENTATION_EXCLUDED_STAGES | ⬜ |
| 7.37 | OPERATIONAL_EXCLUDED_STAGES | ⬜ |
| 7.38 | deactivate_for_work_type | ⬜ |

### 7C — UI Detection

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 7.39 | detect_ui_project: package.json | ⬜ |
| 7.40 | detect_ui_project: vite.config.ts | ⬜ |
| 7.41 | detect_ui_project: next.config.js | ⬜ |
| 7.42 | detect_ui_project: sem indicators | ⬜ |

### 7D — Deactivation

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 7.43 | deactivate_inactive_stages: complexity | ⬜ |
| 7.44 | deactivate_inactive_stages: ui_project | ⬜ |

---

## FASE 8 — Recursos Adicionais

### 8A — Evidence Gate (coberto: `test_evidence_gate.py`)

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 8.45 | Evidence gate validation | Verificar `test_evidence_gate.py` | ⬜ |
| 8.46 | Per-AC evidence matching | ⬜ |
| 8.47 | Discrimination sensor | ⬜ |
| 8.48 | Coverage audit | ⬜ |

### 8B — Stall Detector

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 8.49 | Stall detection: timeout | Criar teste | ⬜ |
| 8.50 | Stall detection: no progress | Criar teste | ⬜ |
| 8.51 | Stall report generation | Criar teste | ⬜ |

### 8C — Timing

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 8.52 | TimingTracker record_stage | Criar teste | ⬜ |
| 8.53 | TimingTracker get_summary | Criar teste | ⬜ |
| 8.54 | TimingTracker get_loop_elapsed | Criar teste | ⬜ |
| 8.55 | format_time utility | Criar teste | ⬜ |

### 8D — Decisions

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 8.56 | Decision logging | Criar teste | ⬜ |
| 8.57 | Decision AD-NNN format | Criar teste | ⬜ |

### 8E — Lessons

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 8.58 | Lessons load/save | `test_lessons.py` | ⬜ |
| 8.59 | Lessons apply to prompt | ⬜ |

### 8F — Topology Compliance

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 8.60 | Compliance check: valid transition | `test_topology_compliance.py` | ⬜ |
| 8.61 | Compliance check: invalid transition | ⬜ |
| 8.62 | Compliance check: skipped stage | ⬜ |

### 8G — Interactive / Breakpoint

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 8.63 | Breakpoint menu | `test_interactive.py` | ⬜ |
| 8.64 | edit_state_in_editor | ⬜ |
| 8.65 | Interrupt and resume | ⬜ |

### 8H — Graphify

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 8.66 | Graphify tools | Criar teste | ⬜ |
| 8.67 | Graphify main function | Criar teste | ⬜ |

### 8I — Prompt Builder

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 8.68 | Prompt builder: stage prompt | `test_prompt_builder.py` | ⬜ |
| 8.69 | Prompt builder: context injection | ⬜ |
| 8.70 | Prompt builder: project map inclusion | ⬜ |

### 8J — JSON Parse

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 8.71 | JSON parse: valid | Criar teste | ⬜ |
| 8.72 | JSON parse: markdown code block | Criar teste | ⬜ |
| 8.73 | JSON parse: malformed, fallback | Criar teste | ⬜ |

### 8K — File Ops

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 8.74 | save_json | Criar teste | ⬜ |
| 8.75 | write_file | Criar teste | ⬜ |
| 8.76 | read_file | Criar teste | ⬜ |

### 8L — Node Helpers

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 8.77 | stage_runner | Criar teste | ⬜ |
| 8.78 | next_active | Criar teste | ⬜ |

---

## FASE 9 — Integração CLI

Objetivo: validar comandos CLI e fluxo end-to-end.

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 9.1 | `eng-loop --help` | ⬜ |
| 9.2 | `eng-loop --dry-run` | Config válido, sem executar | ⬜ |
| 9.3 | `eng-loop --check-model` | Conectividade model | ⬜ |
| 9.4 | `eng-loop --build-topology` | Topology markdown + JSON | ⬜ |
| 9.5 | `eng-loop --dynamic-graph --build-topology` | Dynamic topology | ⬜ |
| 9.6 | `eng-loop run-node <stage>` | Execução isolada | ⬜ |
| 9.7 | `eng-loop clear-state <stage>` | Reset stage | ⬜ |
| 9.8 | `eng-loop skip-node <stage>` | Mark done | ⬜ |
| 9.9 | `eng-loop history` | List snapshots | ⬜ |
| 9.10 | `eng-loop rollback <stage>` | Restore snapshot | ⬜ |
| 9.11 | `eng-loop --check-compliance --requested-stage` | Validate transition | ⬜ |
| 9.12 | `eng-loop --pause-at` | Breakpoint | ⬜ |
| 9.13 | `eng-loop --interactive` | HUD TUI | ⬜ |
| 9.14 | `eng-loop --opencode-agent` | Hybrid mode | ⬜ |
| 9.15 | `eng-loop --parallel-qa` | Parallel QA | ⬜ |

---

## FASE 10 — Testes de Integração End-to-End

Objetivo: validar fluxos completos com mock de LLM.

| # | Teste | Descrição | Status |
|---|-------|-----------|--------|
| 10.1 | Small feature: init → impl → verify → deploy → post | Mock LLM | ⬜ |
| 10.2 | Medium feature: com arch + QA | Mock LLM | ⬜ |
| 10.3 | Documentation work: init → impl.code → post | Mock LLM | ⬜ |
| 10.4 | Operational work: init → tests | Mock LLM | ⬜ |
| 10.5 | Loopback: verify FAIL → retry impl.code | Mock LLM | ⬜ |
| 10.6 | Blocked: max attempts exceeded → terminate | Mock LLM | ⬜ |
| 10.7 | Graph bypass: small complexity, init-bdd skipped | ⬜ |
| 10.8 | State persistence: save/resume | ⬜ |
| 10.9 | HUD integration: events flow to renderer | Mock HUD | ⬜ |
| 10.10 | Context handoff: data flows between stages | ⬜ |

---

## RESUMO DE GAPS CRÍTICOS

### Testes que precisam ser criados (prioridade alta):

1. **13 node handlers sem teste isolado** (FASE 1C): init.bdd, 6 design stages, 3 arch stages, e2e, qa.performance, smoke.test
2. **Routing scenarios de loopback** (FASE 2D): verify/e2e/QA/deploy/smoke FAIL → retry
3. **Work type routing** (FASE 2D): documentation, operational, bugfix
4. **Context slice/tier/consolidator** (FASE 3A): zero cobertura
5. **UIManager/progress rendering** (FASE 5E): zero cobertura
6. **State history/rollback** (FASE 6B): precisa verificação
7. **Auto-sizing classification** (FASE 7): zero cobertura
8. **Stall detector** (FASE 8B): zero cobertura
9. **Timing tracker** (FASE 8C): zero cobertura
10. **JSON parse** (FASE 8J): zero cobertura
11. **File ops** (FASE 8K): zero cobertura
12. **CLI integration** (FASE 9): zero cobertura
13. **End-to-end integration** (FASE 10): zero cobertura

### Total de testes existentes: ~180
### Total de testes planejados: ~220
### Novos testes necessários: ~40

---

## ORDEM DE EXECUÇÃO RECOMENDADA

```
FASE 0  → Infraestrutura (5 min)
FASE 1  → Nodes (criar 13 handlers + 4 testes state) (30 min)
FASE 7  → Auto-sizing (15 testes) (20 min)
FASE 2  → Routing gaps (10 testes loopback + work_type) (20 min)
FASE 3  → Context (4 testes slice/tier/consolidator) (20 min)
FASE 5  → HUD gaps (12 testes UIManager/progress) (20 min)
FASE 6  → State gaps (schemas, config, history) (15 min)
FASE 8  → Recursos adicionais (30+ testes) (45 min)
FASE 9  → CLI integration (15 testes) (30 min)
FASE 10 → End-to-end (10 testes com mock) (45 min)
```
