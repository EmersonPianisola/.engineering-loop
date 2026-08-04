#!/bin/bash
# Engineering Loop — Project Installation Script
# Usage: bash .eng/setup/install.sh
# Purpose: Initialize project-specific files inside the submodule

set -e

# Detect paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOOP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$LOOP_ROOT/.." && pwd)"

echo "============================================"
echo "  Engineering Loop — Project Setup"
echo "============================================"
echo ""
echo "  Framework: $LOOP_ROOT"
echo "  Project:   $PROJECT_ROOT"
echo ""

# 1. Copy config template
if [ -f "$LOOP_ROOT/config.yaml" ]; then
    echo "  [skip] config.yaml already exists"
else
    cp "$LOOP_ROOT/config-template.yaml" "$LOOP_ROOT/config.yaml"
    echo "  [ok]   config.yaml created from template"
fi

# 2. Copy state template
if [ -f "$LOOP_ROOT/state.json" ]; then
    echo "  [skip] state.json already exists"
else
    cp "$LOOP_ROOT/state-template.json" "$LOOP_ROOT/state.json"
    echo "  [ok]   state.json created from template"
fi

# 3. Create artifacts directory structure
ARTIFACT_DIR="$LOOP_ROOT/artifacts"
if [ -d "$ARTIFACT_DIR" ]; then
    echo "  [skip] artifacts/ already exists"
else
    mkdir -p "$ARTIFACT_DIR"/{architectures,blueprints,bdd-journeys,design,test-plans}
    echo "  [ok]   artifacts/ created with subdirectories"
fi

# 4. Create .gitignore inside submodule
GITIGNORE="$LOOP_ROOT/.gitignore"
if [ -f "$GITIGNORE" ]; then
    echo "  [skip] .gitignore already exists"
else
    cat > "$GITIGNORE" << 'EOF'
# Project-specific files (generated per project)
config.yaml
state.json
STATE.md
context.md

# Project artifacts
artifacts/
EOF
    echo "  [ok]   .gitignore created"
fi

# 5. Create log directory
LOG_DIR="$PROJECT_ROOT/_bmad-output/process-logs"
if [ -d "$LOG_DIR" ]; then
    echo "  [skip] _bmad-output/process-logs/ already exists"
else
    mkdir -p "$LOG_DIR"
    echo "  [ok]   _bmad-output/process-logs/ created"
fi

echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
# 6. Install eng_loop Python package
ENG_LOOP_DIR="$LOOP_ROOT/eng_loop"
if [ -d "$ENG_LOOP_DIR" ]; then
    echo "  [info] Installing eng_loop package..."
    pip install -e "$ENG_LOOP_DIR" 2>/dev/null || {
        echo "  [warn] pip install failed — ensure Python 3.10+ and pip are available"
        echo "  [warn] Manual install: pip install -e $ENG_LOOP_DIR"
    }
else
    echo "  [warn] eng_loop/ not found — LangGraph orchestrator unavailable"
fi

echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
echo "  Next steps:"
echo "    1. Review .eng/config.yaml and customize as needed"
echo "    2. Commit your project (submodule ref + .gitignore)"
echo "    3. Run: eng-loop --work-item \"your task description\""
echo "    4. (Legacy) Load ORCHESTRATOR.md for prompt-based mode"
echo ""
