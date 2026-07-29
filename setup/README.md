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

### 3. Customize Configuration

Review `.eng/config.yaml` and adjust as needed:
- `artifact_root` — where artifacts are stored
- `log_root` — where process logs go
- `constraints` — per-stage iteration limits
- `hardware` — context window, parallel agents, timeouts
- `lessons` — confirm threshold, file paths

### 4. Start Using the Loop

Load `ORCHESTRATOR.md` and provide a work item. The orchestrator will:
1. Detect framework and project roots automatically
2. Load config (template defaults + project overrides)
3. Initialize state from template
4. Run the full loop with Essence gates

## What the Install Script Does

1. Copies `config-template.yaml` → `config.yaml` (if not exists)
2. Copies `state-template.json` → `state.json` (if not exists)
3. Creates `artifacts/` directory structure
4. Creates `.gitignore` (ignores project files inside submodule)
5. Creates `_bmad-output/process-logs/` (if not exists)

## Updating the Framework

```bash
git submodule update --remote
```

This pulls the latest stages, skills, and references from the framework repository.

## File Structure (After Installation)

```
my-project/
├── .eng/                          # git submodule
│   ├── ORCHESTRATOR.md            # ← framework (read-only)
│   ├── CORE.md
│   ├── config-template.yaml       # ← framework defaults
│   ├── state-template.json        # ← framework template
│   ├── stages/                    # ← framework (read-only)
│   ├── skills/                    # ← framework (read-only)
│   ├── references/                # ← framework (read-only)
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
| `{framework-root}` | `.eng/` | stages/, skills/, references/ (read-only) |
| `{loop-root}` | `.eng/` | config.yaml, state.json, STATE.md, artifacts/ |
| `{project-root}` | `cwd` | source code, tests, _bmad-output/ |
| `{artifact-root}` | `.eng/artifacts/` | all runtime artifacts |
| `{log-root}` | `_bmad-output/process-logs/` | process logs |

## Troubleshooting

### "config.yaml not found"

Run the install script. If you already have a custom config.yaml, ensure it exists at `.eng/config.yaml`.

### "state.json not found"

Run the install script. The orchestrator will also auto-create it from the template on first run.

### Submodule not updating

```bash
git submodule update --init --recursive
git submodule update --remote
```

### Config conflicts

The orchestrator merges `config-template.yaml` (defaults) with `config.yaml` (overrides). If a key exists in both, the project value wins.
