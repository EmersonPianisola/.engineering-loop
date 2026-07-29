# Engineering Loop — Project Installation Script
# Usage: powershell -ExecutionPolicy Bypass -File .eng\setup\install.ps1
# Purpose: Initialize project-specific files inside the submodule

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$LoopRoot = Split-Path -Parent $ScriptDir
$ProjectRoot = Split-Path -Parent $LoopRoot

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Engineering Loop — Project Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Framework: $LoopRoot" -ForegroundColor Gray
Write-Host "  Project:   $ProjectRoot" -ForegroundColor Gray
Write-Host ""

# 1. Copy config template
$configPath = Join-Path $LoopRoot "config.yaml"
$templatePath = Join-Path $LoopRoot "config-template.yaml"
if (Test-Path $configPath) {
    Write-Host "  [skip] config.yaml already exists" -ForegroundColor Yellow
} else {
    Copy-Item $templatePath $configPath
    Write-Host "  [ok]   config.yaml created from template" -ForegroundColor Green
}

# 2. Copy state template
$statePath = Join-Path $LoopRoot "state.json"
$stateTemplate = Join-Path $LoopRoot "state-template.json"
if (Test-Path $statePath) {
    Write-Host "  [skip] state.json already exists" -ForegroundColor Yellow
} else {
    Copy-Item $stateTemplate $statePath
    Write-Host "  [ok]   state.json created from template" -ForegroundColor Green
}

# 3. Create artifacts directory structure
$ArtifactDir = Join-Path $LoopRoot "artifacts"
if (Test-Path $ArtifactDir) {
    Write-Host "  [skip] artifacts/ already exists" -ForegroundColor Yellow
} else {
    New-Item -ItemType Directory -Force -Path (Join-Path $ArtifactDir "architectures") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $ArtifactDir "blueprints") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $ArtifactDir "bdd-journeys") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $ArtifactDir "design") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $ArtifactDir "test-plans") | Out-Null
    Write-Host "  [ok]   artifacts/ created with subdirectories" -ForegroundColor Green
}

# 4. Create .gitignore inside submodule
$GitignorePath = Join-Path $LoopRoot ".gitignore"
if (Test-Path $GitignorePath) {
    Write-Host "  [skip] .gitignore already exists" -ForegroundColor Yellow
} else {
    $gitignoreContent = @"
# Project-specific files (generated per project)
config.yaml
state.json
STATE.md
context.md

# Project artifacts
artifacts/
"@
    Set-Content -Path $GitignorePath -Value $gitignoreContent -Encoding UTF8
    Write-Host "  [ok]   .gitignore created" -ForegroundColor Green
}

# 5. Create log directory
$LogDir = Join-Path $ProjectRoot "_bmad-output\process-logs"
if (Test-Path $LogDir) {
    Write-Host "  [skip] _bmad-output\process-logs\ already exists" -ForegroundColor Yellow
} else {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    Write-Host "  [ok]   _bmad-output\process-logs\ created" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Setup complete!" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "    1. Review .eng\config.yaml and customize as needed" -ForegroundColor Gray
Write-Host "    2. Commit your project (submodule ref + .gitignore)" -ForegroundColor Gray
Write-Host "    3. Load ORCHESTRATOR.md and provide a work item" -ForegroundColor Gray
Write-Host ""
