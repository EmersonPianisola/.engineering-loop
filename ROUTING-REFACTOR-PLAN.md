# ROUTING-REFACTOR-PLAN — Roteamento estrito por edges do LangGraph

> Plano de implementação (a executar em sessão futura).
> Decisão do usuário (24/08/2026): **após o grafo e as edges serem gerados, eles devem ser
> seguidos rigorosamente pelo LangGraph. Durante a execução não deve haver mudança de rota.
> Se a proposta é `[init → init.ideate → init.refine → impl.code → post]`, é isso que executa.**

---

## 1. Diagnóstico (evidências)

### 1.1 Falha fatal — run de 24/08 no projeto Cars (`../Cars`)

Work item: "Escreva uma receita de bolo de chocolate em receitas/bolo-chocolate.md".
Evidências: `Cars/artifacts/trace-20260824-091347.jsonl`, `Cars/state.json`,
`Cars/.eng/history/state_after_impl-design_20260824_091930_*.json`.

Sequência:
1. Complexity → `small`. Arquiteto LLM propôs e a policy firewall autorizou a topologia
   `[init, init.ideate, init.refine, impl.code, post]` (correta p/ documentação).
2. Grafo compilado com exatamente esses nós (+ `init-setup`, `dynamic-architect`, `meta-executor`).
3. Pipeline executou `init → init.ideate → init.refine` normalmente (09:15:21–09:19:30).
4. `init_refine_node` terminou e calculou o próximo nó via `_next_phase_node()` →
   `resolve_next("impl-design", state)` (`nodes/init.py:550`).
5. `resolve_next`/`next_incomplete_stage` (`tools/next_active.py:57`, `state.py:406`) usam a
   **tabela global `STAGE_ORDER` + heurísticas de complexity/ui/work_type** — ignoram a
   topologia aprovada. Para `small`, `impl.design` é "ativo" globalmente →
   `Command(goto="impl-design")`.
6. O nó `impl-design` **não existe no grafo compilado**.
7. **O LangGraph descarta silenciosamente** `Command(goto=...)` para nó desconhecido
   (verificado empiricamente: log `"wrote to unknown channel branch:to:impl-design, ignoring it"`
   e o grafo termina normalmente). Sem exceção, sem evento de erro.
8. Estado final: `status: "running"`, `current_stage: "impl-design"`, `impl.code: attempts=0`,
   `receitas/` nunca foi criado. O usuário viu o run "terminar" sem resultado e sem erro.

**Raiz:** o runtime NÃO executa a topologia compilada. Cada handler carrega sua própria tabela
de roteamento hardcoded (`resolve_next`, `_next_phase_node`, `_post_verify`, `_resolve_next_qa`,
`DESIGN_NEXT_MAP`, `ARCH_NEXT_MAP`, ...) que conflita com a topologia aprovada. O invariante
"LLM propõe → Policy autoriza → Builder compila → Runtime executa" está quebrado na última etapa.

### 1.2 Erros de visualização/comunicação observados

| # | Bug | Localização | Evidência |
|---|-----|-------------|-----------|
| C1 | `ENTER` duplo por stage (iter=1 e iter=0, inconsistente) | `tools/event_bus.py:17` + `tools/progress.py:1442` ambos chamam `_trace.stage_enter` | trace seq 22/23, 25/26, 40/41, 54/55, 67/68 |
| C2 | `PIPELINE_END status=running` + `current_stage=""` no fim — o `finally` lê o `state` local original (nunca atualizado in-place), reporta estado obsoleto como se fosse o final | `cli.py:930-932` | última linha do trace |
| C3 | `ask_user` com pergunta trivial ("Não há mais nada a confirmar... Posso prosseguir?") → stall de 118s; tool calls interceptados não aparecem como eventos TOOL no trace | `tools/agent_runner.py:528-566` (interceptação sem trace), `tools/ask_user_tool.py` | trace seq 78→79 (gap 09:17:04→09:19:02) |
| C4 | Dois `state.json` divergentes para o mesmo projeto: `Cars/.eng/state.json` (work item Firebase, `halted`, erro obsoleto de 22/08) e `Cars/state.json` (cake, `running`). `--framework-root/--loop-root/--project-root` defaultizam para `.` → tudo depende do CWD; `resume` carrega o estado errado. Também existe `Cars/.eng/.eng/.eng` (install executado dentro do `.eng`) | `cli.py:264-268`, `config.py:71-78` | filesystem |
| C5 | `graph_topology.edges` persistido incompleto: só fixed edges de nós não-command são gravadas → estado mostra 1 edge para topologia de 5 estágios | `graph_builder.py:342-354` (só o branch `fixed` fora de command-routed faz `.append`) | snapshot 09:19 |
| C6 | Junk no consumer: `Cars/nul` (out de `dir /b /s ... > nul` — comando Windows rodado em bash) e `Cars/C:Usersemers...state.txt` (backslash tratado como separador → nome de arquivo) | instruções de stages/agentes | filesystem |
| C7 | Erro `'EdgeRule' object has no attribute 'name'` no `.eng/state.json` é **resíduo do run de 22/08** — bug `rule.name` no `_route`, corrigido em d9f559a. Estado `halted` velho nunca foi limpo; metadata pip em 12.2.0 (repo em 12.4.0) | `Cars/.eng/artifacts/trace-20260822-173457.jsonl` seq 59; `git show d9f559a` | trace 22/08 |

### 1.3 Inconsistências de semântica de falha entre handlers (a padronizar)

| Handler | Esgotou tentativas | Obs. |
|---|---|---|
| `init` (validação inválida) | `blocked` + `__end__` | ok |
| `init_ideate` | `blocked` + `__end__` | ok |
| `init_bdd` / `init_refine` | `done=True`, **sem** blocked, **avança** | aceitável (avanço) |
| `design.*` / `arch.*` | `blocked` + **avança** (`goto=next_node`) | **bug**: status vaza; o próximo stage termina na hora via terminal edge — o "avanço" é ilusório |
| `impl.design` / `impl.code` / `verify` | `blocked` + `__end__` | ok |
| `doc.update` | `done=True`, sem blocked, **avança** | aceitável (docs não bloqueiam pipeline) |
| `e2e` pre-flight | `blocked` + `__end__` | ok |
| `deploy.prepare` esgotou | `done=True` + `impl.code.done=False` + `goto impl-code` | loop de volta sem `fix_tasks` — risco de loop infinito |

---

## 2. Arquitetura alvo

**Princípio:** o grafo compilado é a única fonte de rota. Handlers retornam **apenas updates de
estado (dict, ou None)**; todas as transições (avanço, retry, rollback, término) são edges
declaradas no `StateGraph`. Nenhum `Command(goto=...)` permanece (nem no parallel QA — ver 4.7).

Fluxo:
```
LLM propõe topologia → policy firewall autoriza → GraphBuilder compila:
  • edges de avanço (da proposta OU das regras determinísticas pré-resolvidas)
  • edges de retry/rollback/terminal (injetadas, uniformes)
→ Runtime executa seguindo APENAS essas edges.
```

### 2.1 Semântica unificada de edges (por nó de stage)

Para cada nó de stage registrado, o builder registra estas edges (nesta ordem de prioridade):

| Prioridade | Edge | Condição (runtime) | Destino |
|---|---|---|---|
| 20 | terminal | `status in ("blocked", "waiting_for_input")` | `__end__` |
| 10 | rollback | `stages[stage].verdict == "FAIL"` | failure target (padrão `impl-code`; `arch.review` → `arch-requirements`) |
| 10 | self-retry | `not stages[stage].done and stages[stage].verdict != "FAIL"` | o próprio nó |
| 0 | forward | `stages[stage].done` | forward target (da topologia) |

Regras de precedência (mutuamente exclusivas por construção):
- `blocked` → terminal ganha (20 > tudo).
- `verdict == "FAIL"` → rollback (10) — vale com ou sem `done` (cobre esgotamento-deploy).
- `not done and verdict != "FAIL"` → self-retry (10).
- `done` (e nada acima) → forward (0).

**Marcadores de estado (contrato handler → edge):**
- Sucesso: `stages[stage].done = True`, `verdict = "PASS"` (ou `""` p/ stages sem verdict).
- Falha com rollback: `stages[stage].verdict = "FAIL"` (+ `fix_tasks` quando aplicável;
  `rollback_to_stage` quando aplicável).
- Retry (erro de agent/evidence, tentativas restantes): `done` fica `False`, `verdict` não
  vira `FAIL`.
- Esgotamento: `status = "blocked"` + `blocking_condition` (terminal edge encerra) — exceto
  `init_bdd`/`init_refine`/`doc.update`, que marcam `done=True` e avançam (mantido).

O teto de tentativas continua nos handlers (eles decidem quando esgotar e setam `blocked`/`FAIL`);
as edges só reagem aos marcadores. **Nenhuma edge depende de `attempts < max`** (evita
dependência de config no routing).

### 2.2 Origem do forward target

- **Caminho proposal** (arquiteto LLM autorizado): a edge de avanço de cada stage é a edge
  proposta (a proposta exige exatamente uma saída por stage). `post` → `__end__`.
- **Caminho determinístico** (fallback): as rules de `build_edge_rules()` são **pré-resolvidas
  em tempo de compilação** — como `complexity`/`ui_project`/`work_type` são conhecidos no build,
  cada regra condicional de avanço é avaliada uma vez (estado sintético: todos os stages
  `done=True`, `status="running"`) e só o edge cujo resultado é `True` é registrado, como edge
  de avanço do nó. Ex.: `small` → `init-refine → impl-design`; `medium+` →
  `init-refine → arch-requirements`. `resolve_with_bypass` continua resolvendo nós inativos
  intermediários (ex.: `init-ideate → init-bdd → init-refine` vira `init-ideate → init-refine`).
- **Parallel QA ativo**: o forward de `verify`/`e2e-execute` vira `qa-dispatcher` (decisão de
  build).
- Se nenhum forward target for resolvido para um nó (defensivo): o builder **falha a compilação
  com erro explícito** (nunca compila grafo com nó sem saída, exceto `post`/`__end__`).

### 2.3 Nós meta (sem semântica de stage)

| Nó | Edges registradas |
|---|---|
| `init-setup` | fixed `→ dynamic-architect` (handler vira no-op que faz o trabalho determinístico) |
| `dynamic-architect` | condicional `→ meta-executor` (`dynamic_plan.trigger=="augment" and steps`); condicional `→ init` (senão) |
| `meta-executor` | self `→ meta-executor` (`dynamic_runtime.status=="running"`); `→ init` (`=="completed"`); `→ __end__` (`=="blocked"` ou `status=="blocked"`) |
| `post` | condicional `→ __end__` (`not blocked`); terminal padrão (`blocked` → `__end__`) |
| `qa-dispatcher` | **fan-out estático em tempo de build**: fixed edges `→` cada QA worker ativo (complexity conhecida no build); se nenhum worker ativo, fixed `→ deploy-prepare` |
| `qa-join` | condicional `→ __end__` (join decision `blocked`/`status blocked`); condicional `→ impl-code` (decision `rollback`); condicional `→ deploy-prepare` (decision `pass`) |

### 2.4 Parallel QA sem Command (fan-out/fan-in estático)

- O dispatcher deixa de ser nó de decisão: o **builder registra as edges de fan-out**
  (múltiplas fixed edges do `qa-dispatcher` para os workers ativos — comportamento nativo de
  fan-out do Pregel) e o dispatcher vira handler trivial.
- Workers: fixed `→ qa-join` (sempre; sem self-retry em fan-out — comportamento atual mantido).
- `qa-join_node`: calcula a agregação (verdicts, friction, fix_tasks) como hoje, mas **escreve a
  decisão em `state["qa_results"]["join"] = {"decision": "pass|rollback|blocked", ...}`** e
  retorna dict sem goto. As edges do join consomem essa decisão.
- `Send` é eliminado.

### 2.5 `current_stage` e `iteration`

- O wrapper `trace_node` (`tools/progress.py`) centraliza: merge
  `{"current_stage": stage_id, "iteration": state.iteration + 1}` no dict retornado pelo handler.
- Handlers **não** escrevem mais `current_stage` nem `iteration`.
- Efeito colateral positivo: snapshots de history passam a se chamar `state_after_<stage que
  completou>` (hoje se chamam pelo próximo stage — foi assim que nasceu o enganador
  `state_after_impl-design` para um stage que nunca rodou).

### 2.6 Contract gate e essence gate (middleware de estado)

- **`essence_gate`** (`tools/essence_gate.py:86`): em vez de `Command(goto="__end__")`, retorna
  dict `{"status": "blocked"/"waiting_for_input", "blocking_condition": ..., ...}` — a terminal
  edge roteia.
- **`contract_gate`** (`tools/contract_gate.py`): vira middleware que roda **após** o handler:
  - assina `with_contract_gate(source_node, forward_target)` — o **builder passa o forward
    target conhecido no build** (hoje o middleware lia `handler_result.goto`).
  - `proceed` → update passa intacto.
  - `retry_source` → o middleware reseta `stages[stage].done = False` no update (+ erro) → a
    self-retry edge dispara.
  - `block` → middleware seta `status="blocked"` → terminal edge dispara.
  - `check_contract`/`CONTRACT_RULES` inalterados.

---

## 3. Mudanças por arquivo

### 3.1 `eng_loop/src/eng_loop/graph_builder.py` (núcleo)

- **`_add_edges` — reescrito.** Para cada nó registrado:
  - resolve o forward target (2.2) e o failure target (2.1; tabela de failure routing em 3.2);
  - registra as 4 edges unificadas (terminal/rollback/self-retry/forward) via
    `add_conditional_edges` com o evaluator `_route_unified(rules_do_nó, state)` (ordenação por
    prioridade, como o `_route` atual); nodes sem stage (meta) recebem as edges específicas (2.3);
  - **persiste o edge list completo resolvido em `topology.edges`** (C5) — incluindo edges
    condicionais, com `type` (`forward|retry|rollback|terminal|fixed`).
- **`_build_from_proposal`**: usa as edges propostas como forward targets (hoje recria um
  `temp_proposal` só para as rules — simplificar para mapear `authorized_edges` direto).
- **`_build_deterministic`**: pré-resolve as rules de avanço (2.2) + `resolve_with_bypass`.
- **`compile`**: mantém set de `state.config.dynamic_graph.parallel_qa`.
- **Guardefalha de compilação**: nó sem forward target → `TopologyCompilationError` com mensagem
  explícita (inclui node e stage).
- Fan-out paralelo: `_add_parallel_qa` registra as fixed edges do dispatcher e as fixed
  worker→join (2.4); mantém `qa-dispatcher`/`qa-join` registrados como nós.
- `NodeSpec.routing`: o campo perde o papel de "quem roteia"; manter p/ compatibilidade mas o
  builder trata todos os nós uniformemente (edges).

### 3.2 `eng_loop/src/eng_loop/edge_rules.py`

- **`_inject_failure_routing` — generalizado**: hoje injeta loopback/terminal só para
  verify/e2e/deploy/smoke/qa-*. Passa a ser a fonte da **tabela de failure targets**:
  ```python
  FAILURE_ROUTES = {
      "verify": "impl.code", "e2e.execute": "impl.code",
      "qa.*": "impl.code",            # todos os qa
      "deploy.prepare": "impl.code", "smoke.test": "impl.code",
      "arch.review": "arch.requirements",
  }
  ```
  (stages de init/design/impl: sem failure route — só self-retry + terminal.)
  Execution policies da proposta podem sobrescrever (`policy.failure_route`) — mecanismo existe.
- `_get_condition_predicate` mantido (condições declaradas da proposta p/ edges condicionais).
- `build_edge_rules` (determinístico) mantido como fonte de **avanço**; as loopbacks que ele
  contém (verify→impl-code etc.) deixam de ser usadas p/ retry — a injeção unificada (3.1)
  substitui. Manter a função p/ compatibilidade com `topology_compliance.py`.

### 3.3 Handlers — padrão de conversão (todos em `nodes/`)

Para cada handler, a conversão é mecânica:
```python
# ANTES
return Command(goto=next_node, update={"stages": stages, ..., "current_stage": next_node, "iteration": ...+1})
# DEPOIS
return {"stages": stages, ...}   # current_stage/iteration ficam por conta do trace_node
```
- Remover todos os `from langgraph.types import Command` (exceto `qa_parallel.py` — que perde
  `Send`/`Command` também, ver 3.6) e todos os usos de `resolve_next`/`_next_phase_node`/
  `_post_verify`/`_post_e2e`/`_resolve_next_qa`/`_post_deploy`/`DESIGN_NEXT_MAP`/`ARCH_NEXT_MAP`
  no caminho de roteamento.
- **`nodes/init.py`**: `init_node` (invalid → `blocked` dict), `init_ideate_node`,
  `init_bdd_node` (esgotou → `done=True`, avança — mantido), `init_refine_node` (idem).
  Apagar `_next_phase_node` (a edge de avanço de `init-refine` vem da topologia).
- **`nodes/design.py` / `nodes/architecture.py`**: esgotou → `done=True` + `status="blocked"`
  (terminal edge encerra — corrige o "avanço ilusório" do §1.3). `arch.review` com critical
  findings → `stages["arch.review"]["verdict"]="FAIL"` (rollback edge → `arch-requirements`).
- **`nodes/implementation.py`**: `impl_design`/`impl_code` — retry = dict sem `done`/`FAIL`;
  esgotou = `blocked`; sucesso = `done+PASS`; `impl.code` mantém clear de `fix_tasks`/
  `rollback_target` no sucesso.
- **`nodes/verification.py`**: `verify` FAIL → `verdict="FAIL"` + `fix_tasks` +
  `rollback_to_stage` (rollback edge → impl-code); retry = dict. `e2e` idem; esgotou →
  `verdict="FAIL"` + fix_tasks (rollback — mantido); pre-flight → `blocked`.
- **`nodes/qa.py`**: remover branching de `parallel_mode` no routing (edges decidem).
  FAIL/critical → `verdict="FAIL"` (+ `impl.code.done=False`); BLOCKED verdict → retry até
  esgotar → `status="blocked"` (global) → terminal; "continue" action → `done=True,
  verdict="PASS"` (avança).
- **`nodes/deploy.py`**: FAIL → `verdict="FAIL"` (rollback → impl-code, mantido); **esgotou →
  `verdict="FAIL"` + `fix_tasks` com a razão** (rollback → impl-code — preserva o loop atual,
  agora com contexto para o impl agent; ver §5).
- **`nodes/documentation.py`**: como design (esgotou → `blocked` + terminal).
- **`nodes/post.py`**: sucesso/falha → `done`/`blocked`; a edge `post → __end__` fecha.
- **`nodes/init_setup.py` / `dynamic_architect.py` / `meta_executor.py`**: retornar dict; as
  condições de roteamento são as edges de 2.3 (o `dynamic_architect_node` continua criando o
  `dynamic_plan`; o `meta_executor` continua o cursor).

### 3.4 `eng_loop/src/eng_loop/tools/`

- **`progress.py:trace_node`**: merge `{"current_stage": stage_id, "iteration": +1}` no retorno
  (3.2.5 do plano); se o handler retornar `None` → `{}`.
- **`event_bus.py:17`**: **remover** `_trace.stage_enter` (dedup C1) — o `trace_node` é a fonte
  canônica de ENTER.
- **`agent_runner.py` (ask_user, linhas 528-566)**: logar a interceptação como evento TOOL no
  trace (pergunta, resposta, latência) — C3.
- **`ask_user_tool.py`** + prompts dos stages `init*`: instrução explícita "NÃO pergunte
  confirmações triviais; só pergunte quando existir decisão real que não pode ser inferida" (C3).
- **`contract_gate.py`**: conversão de 2.6.
- **`essence_gate.py`**: conversão de 2.6.
- **`next_active.py`**: manter `resolve_next` apenas para o fallback determinístico de avanço
  pré-resolvido (build time); documentar que **runtime não usa**.

### 3.5 `eng_loop/src/eng_loop/cli.py` (P2 — falha barulhenta)

- **`finally` (linhas 930-932)**: usar o `final_state` retornado por
  `_run_loop_with_recovery` (hoje lê o `state` local obsoleto → `PIPELINE_END status=running`
  enganoso — C2).
- **Validação pós-stream** (novidade): se o stream terminou com `status == "running"` e há
  stages ativos pendentes (`next_incomplete_stage` sobre `active_nodes` do build) →
  `status = "halted"`,
  `blocking_condition = f"pipeline ended unexpectedly at {current_stage} — stages pending: [...]"`,
  evento `PIPELINE_ERROR` + painel vermelho. (Isso transforma o modo de falha silencioso do
  §1.1 em falha explícita, mesmo que algum bug de routing volte a existir.)
- Handler de exceção (915-929): manter, mas o painel deve incluir dica de diagnóstico
  (trace file + state file).

### 3.6 `eng_loop/src/eng_loop/nodes/qa_parallel.py`

- `qa_dispatcher_node` → handler trivial (o fan-out é edge estática do builder).
- `qa_join_node` → calcula e escreve `qa_results.join.decision` (2.4); retorna dict.
- Apagar `Command`/`Send`.

### 3.7 `eng_loop/src/eng_loop/routing.py`

- As funções `route_*` deixam de ser usadas pelo grafo dinâmico. O grafo **legado estático**
  (`graph.py:build_graph`) já usa edges declaradas com essas funções e **passa a funcionar
  corretamente** com handlers que retornam dict (hoje há conflito latente Command×edges).
  Manter as funções; marcar no docstring que são exclusivas do modo estático legado.
- `route_check_loop`/`all_active_stages_done`: manter (usados no estático e na validação
  pós-stream do CLI — que deve usar `active_nodes` do build, ver 3.5).

---

## 4. Mudanças de comportamento (explícitas, aprováveis)

| # | Antes | Depois | Justificativa |
|---|---|---|---|
| B1 | `design.*`/`arch.*` esgotam → "avançam" com status=blocked vazando (encerram no próximo stage) | esgotam → terminal edge encerra na hora | o avanço era ilusório (o pipeline morria no próximo stage de qualquer forma) |
| B2 | `deploy.prepare` esgota → volta ao impl-code sem contexto | volta ao impl-code **com** `fix_tasks` contendo a razão | preserva o loop, dá contexto ao agente de impl |
| B3 | `arch.review` critical findings → goto `arch-requirements` | idem, via rollback edge (verdict `FAIL`) | equivalência; se requirements já está `done`, o ciclo degenerado é o mesmo de hoje |
| B4 | Snapshot de history nomeado pelo **próximo** stage | nomeado pelo stage **que completou** | corrige `state_after_impl-design` p/ stage que nunca rodou |
| B5 | `PIPELINE_END` reporta estado obsoleto | reporta o estado final real; término anômalo vira `halted` + erro | elimina o "fim silencioso" |
| B6 | Handlers podem rotear para nós fora do grafo (silenciosamente) | impossível por construção (só existem as edges compiladas) | o invariante do topo |

---

## 5. P4 — Limpeza do projeto Cars

1. Definir state canônico: **`{project}/.eng/state.json`**. Documentar no AGENTS.md do
   framework o uso correto de `-f/-l/-p` (ou melhor: resolver `loop_root` automaticamente
   detectando `.eng/` a partir do CWD — item separado, fora deste plano).
2. Apagar: `Cars/.eng/state.json` (halted obsoleto de 22/08), `Cars/state.json` (cake,
   status "running" fantasma), `Cars/nul`, `Cars/C:UsersemersAppDataLocalTempopencodestate.txt`,
   `Cars/.eng/.eng/` (aninhado).
3. Reinstalar: `pip install -e "eng_loop/[dev]"` (metadata 12.2.0 → 12.4.0) e atualizar o
   submodule do Cars após o merge (`git submodule update --remote`).

---

## 6. P5 — Testes

### 6.1 Novos
- **`test_strict_routing_invariant.py`** (o teste-chave): para cada nó × cada combinação
  (complexity × ui × work_type) × {topologia proposta, topologia determinística}:
  compilar o grafo e **assertar que todo destino de edge é nó registrado no grafo compilado**
  (ou `__end__`). Este teste é impossível de passar hoje com o modelo Command — ele codifica
  o invariante.
- **`test_cake_scenario_regression.py`**: cenário real do bug — proposta
  `[init, init.ideate, init.refine, impl.code, post]` (sem `impl.design`), dry-run com agent
  fake → assertar: `impl.code` executou, arquivo do work item foi criado, `status == "done"`,
  nenhuma edge referenciou `impl-design`.
- **Cenário `PROPOSAL_STRICT` no `scripts/dry_run_simulator.py`**: mesma regressão via
  simulator.
- **Teste de falha barulhenta**: simular término com `status=="running"` e stages pendentes →
  assertar `halted` + `blocking_condition` preenchido + evento `PIPELINE_ERROR`.
- **Teste de retry/rollback/terminal** por classe de stage (init, impl, verify, qa, deploy):
  cada transição do §2.1 coberta (blocked→end, FAIL→rollback, retry→self, done→forward).

### 6.2 Atualizar existentes
- `test_node_handlers.py`, `test_integration.py`, `test_utils.py`, `test_routing*.py`,
  `test_f1_routing_invariant.py`, `test_topology_proposal.py`, `test_dynamic_graph.py`:
  handlers agora retornam dict (não Command); asserts de `Command.goto` viram asserts de
  estado (done/verdict/blocked) + asserts de edges compiladas.
- `test_graph.py` (estático legado): deve continuar passando — valida que o modo estático
  funciona com handlers-dict.

### 6.3 Verificação final (checklist)
```bash
ruff check eng_loop/src eng_loop/tests
ruff format eng_loop/src eng_loop/tests
pytest eng_loop/tests
pytest eng_loop/tests -k "strict_routing or cake_scenario" -v
python scripts/dry_run_simulator.py --scenario ALL
```

---

## 7. Ordem de implementação (lotes com verificação incremental)

| Lote | Conteúdo | Verificação |
|---|---|---|
| **L1** | `graph_builder._add_edges` novo + `_route_unified` + injeção de failure routing (3.1, 3.2) + persistência de edges completas | build de topologias proposta/determinística para todas as complexidades; `pytest -k graph or topology` |
| **L2** | Handlers `init_setup`, `dynamic_architect`, `meta_executor`, `init*` (3.3) + `trace_node`/`event_bus` (3.4) | `pytest -k "init or setup or architect or meta"` |
| **L3** | Handlers `design`, `architecture`, `implementation`, `contract_gate`, `essence_gate` | `pytest -k "design or arch or impl or contract or essence"` |
| **L4** | Handlers `verification`, `qa`, `qa_parallel`, `deploy`, `documentation`, `post` | `pytest -k "verify or qa or deploy or doc or post"` |
| **L5** | CLI: `finally`/`final_state` + validação pós-stream + painel (3.5) | `pytest -k "cli or pipeline_end"` |
| **L6** | Testes novos (6.1) + dry-run simulator + ruff/pytest FULL | checklist do §6.3 |
| **L7** | Limpeza Cars (P4) + submodule + reinstalação | run real no Cars com o work item do bolo (reprodução do cenário) |

**Risco principal:** ~30 handlers mudam o tipo de retorno; mitigado pelos invariant tests do
§6.1 rodando a cada lote e pelo dry-run simulator no fim de cada lote de nodes.

---

## 8. Referências de código (mapa rápido)

- Bug de roteamento: `nodes/init.py:550-554` (`_next_phase_node`), `tools/next_active.py:57`,
  `state.py:406-416` (`next_incomplete_stage`), `routing.py:94-98`.
- Descarte silencioso do LangGraph: `Command(goto=<nó inexistente>)` → log
  `"wrote to unknown channel branch:to:X, ignoring it"` e término normal (reproduzível com
  StateGraph mínimo — ver sessão 24/08).
- ENTER duplo: `tools/event_bus.py:17` + `tools/progress.py:1441-1442`.
- PIPELINE_END obsoleto: `cli.py:930-932`.
- Edges incompletas persistidas: `graph_builder.py:342-354`.
- Contract gate Command-based: `tools/contract_gate.py:301-354`.
- Essence gate Command-based: `tools/essence_gate.py:86-144`.
- Parallel QA com Send: `nodes/qa_parallel.py:48-75`.
- Bug antigo `EdgeRule.name` (corrigido, referência): commit d9f559a, `graph_builder._route`.
- Evidências do run: `../Cars/artifacts/trace-20260824-091347.jsonl`, `../Cars/state.json`,
  `../Cars/.eng/state.json`, `../Cars/.eng/history/`,
  `../Cars/.eng/artifacts/trace-20260822-173457.jsonl`.
