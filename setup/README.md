# Engineering Loop — Setup

Scripts to install the engineering loop framework into a consuming project.

## Quick Start

### 1. Add as Git Submodule

```bash
git submodule add <engineering-loop-url> .eng
git commit -m "Add engineering loop framework"
```

### 2. Run Installation

**Linux / Mac / WSL:**
```bash
bash .eng/setup/install.sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File .eng\setup\install.ps1
```

The install script:
1. Copies `config-template.yaml` → `config.yaml` (if not exists)
2. Copies `state-template.json` → `state.json` (if not exists)
3. Creates `artifacts/` directory structure
4. Creates `.gitignore` (ignores project files inside submodule)
5. Creates `_bmad-output/process-logs/` (if not exists)
6. **Installs `eng_loop` Python package** (`pip install -e eng_loop/`)

### 3. Customize Configuration

Review `.eng/config.yaml`:

| Setting | Default | Purpose |
|---------|---------|---------|
| `model.base_url` | `http://localhost:8000` | Local model endpoint |
| `model.model` | `qwable-v2` | Model name |
| `model.temperature` | `0.0` | Generation temperature |
| `model.max_tokens` | `128000` | Max output tokens |
| `constraints` | (see template) | Per-stage iteration limits |
| `hardware` | (see template) | Context window, timeouts |

### 4. Check Model Connectivity

```bash
eng-loop --check-model -f .eng -l .eng -p .
```

### 5. Run the Loop

```bash
eng-loop -w "Add user authentication" -f .eng -l .eng -p .
```

The orchestrator will:
1. Detect framework and project roots automatically
2. Load config (template defaults + project overrides)
3. Initialize state from template
4. Auto-size complexity
5. Execute the full LangGraph pipeline with Essence gates
6. Save state to `.eng/state.json` after each iteration

### Legacy Mode (Prompt-Based)

Load `ORCHESTRATOR.md` in your AI agent session and provide a work item. The prompt-based orchestrator still works but is deprecated.

## Updating the Framework

```bash
git submodule update --remote
pip install -e .eng/eng_loop/  # Reinstall if Python deps changed
```

This pulls the latest stages, skills, references, and orchestrator code from the framework repository.

## File Structure (After Installation)

```
my-project/
├── .eng/                          # git submodule
│   ├── ORCHESTRATOR.md            # ← framework (read-only, legacy)
│   ├── CORE.md
│   ├── config-template.yaml       # ← framework defaults
│   ├── state-template.json        # ← framework template
│   ├── stages/                    # ← prompt templates (read-only)
│   ├── skills/                    # ← skill definitions (read-only)
│   ├── references/                # ← shared references (read-only)
│   ├── eng_loop/                  # ← LangGraph orchestrator
│   │   ├── pyproject.toml
│   │   ├── src/eng_loop/
│   │   │   ├── state.py
│   │   │   ├── graph.py
│   │   │   ├── cli.py
│   │   │   ├── nodes/
│   │   │   └── tools/
│   │   └── tests/
│   ├── setup/
│   │
│   ├── config.yaml                # ← PROJECT (gitignored)
│   ├── state.json                 # ← PROJECT (gitignored)
│   ├── STATE.md                   # ← PROJECT (gitignored)
│   ├── context.md                 # ← PROJECT (gitignored)
│   ├── artifacts/                 # ← PROJECT (gitignored)
│   │   ├── architectures/
│   │   ├── blueprints/
│   │   ├── bdd-journeys/
│   │   ├── design/
│   │   ├── test-plans/
│   │   ├── lessons.json           # ← project-local lessons
│   │   ├── LESSONS.md
│   │   ├── lessons-shared.json    # ← shared lessons (committed to framework)
│   │   └── lessons-pending.json   # ← lessons ready to share
│   └── .gitignore                 # ← ignores project files
│
├── _bmad-output/
│   └── process-logs/
└── [your source code]
```

## Path Variables

| Variable | Resolves To | Used For |
|----------|------------|----------|
| `{framework-root}` | `.eng/` | stages/, skills/, references/, eng_loop/ |
| `{loop-root}` | `.eng/` | config.yaml, state.json, STATE.md, artifacts/ |
| `{project-root}` | `cwd` | source code, tests, _bmad-output/ |
| `{artifact-root}` | `.eng/artifacts/` | all runtime artifacts |
| `{log-root}` | `_bmad-output/process-logs/` | process logs |

## Troubleshooting

### "config.yaml not found"

Run the install script. If you already have a custom config.yaml, ensure it exists at `.eng/config.yaml`.

### "state.json not found"

Run the install script. The orchestrator will also auto-create it from the template on first run.

### "ModuleNotFoundError: No module named 'eng_loop'"

```bash
pip install -e .eng/eng_loop/
```

### Model connectivity failed

Ensure your local model server is running:
```bash
eng-loop --check-model -f .eng -l .eng -p .
```

Check that `model.base_url` in `config.yaml` points to your running server.

### Submodule not updating

```bash
git submodule update --init --recursive
git submodule update --remote
pip install -e .eng/eng_loop/
```

### Config conflicts

The orchestrator merges `config-template.yaml` (defaults) with `config.yaml` (overrides). If a key exists in both, the project value wins.
