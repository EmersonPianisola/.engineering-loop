#!/usr/bin/env python3
"""sync-global-skills.py — Manage global skills between repo and ~/.agents/skills/

Usage:
    python scripts/sync-global-skills.py pull          # Deploy: repo -> ~/.agents/skills/
    python scripts/sync-global-skills.py push [name]   # Add skill: ~/.agents/skills/ -> repo
    python scripts/sync-global-skills.py status        # Show diff between repo and ~/.agents/skills/
    python scripts/sync-global-skills.py list          # List versioned skills
    python scripts/sync-global-skills.py init          # Initialize global-skills directory

Config:
    AGENTS_SKILLS_DIR environment variable overrides ~/.agents/skills/
"""

import json
import os
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
REPO_SKILLS_DIR = SCRIPT_DIR / "global-skills"
SKILLS_DIR = Path(os.environ.get("AGENTS_SKILLS_DIR", str(Path.home() / ".agents" / "skills")))
REGISTRY_FILE = SCRIPT_DIR / "global-skills-registry.json"


def ensure_dirs():
    REPO_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)


def load_registry():
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"skills": {}}


def save_registry(registry):
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def list_versioned_skills():
    registry = load_registry()
    return list(registry["skills"].keys())


def get_skill_version(skill_name):
    skill_dir = REPO_SKILLS_DIR / skill_name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return "unknown"
    try:
        content = skill_md.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "unknown"
    for line in content.split("\n"):
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def pull():
    """Deploy skills from repo to ~/.agents/skills/"""
    ensure_dirs()
    registry = load_registry()
    skills = list_versioned_skills()

    if not skills:
        print("No versioned skills in global-skills/")
        return

    print(f"Pulling {len(skills)} skills from repo -> {SKILLS_DIR}")
    deployed = []
    errors = []

    for name in skills:
        src = REPO_SKILLS_DIR / name
        dst = SKILLS_DIR / name
        if not src.exists():
            errors.append(f"[SKIP] {name}: not found in repo")
            continue

        try:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)

            meta = registry["skills"].get(name, {})
            registry["skills"][name]["status"] = "synced"
            registry["skills"][name]["version"] = get_skill_version(name)
            deployed.append(name)
        except Exception as e:
            errors.append(f"[ERROR] {name}: {e}")

    save_registry(registry)

    print(f"\nDeployed: {len(deployed)} skills")
    if errors:
        print(f"Errors:")
        for err in errors:
            print(f"  {err}")


def push(skill_name=None):
    """Add/update skill from ~/.agents/skills/ to repo"""
    ensure_dirs()
    registry = load_registry()

    if skill_name:
        sources = [skill_name]
    else:
        sources = [d.name for d in SKILLS_DIR.iterdir() if d.is_dir()]

    print(f"Checking skills in {SKILLS_DIR}")
    added = []
    updated = []
    skipped = []
    errors = []

    for name in sources:
        src = SKILLS_DIR / name
        dst = REPO_SKILLS_DIR / name

        if not (src / "SKILL.md").exists():
            skipped.append(f"[SKIP] {name}: no SKILL.md")
            continue

        try:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)

            version = get_skill_version(name)
            was_versioned = name in registry["skills"]

            registry["skills"][name] = {
                "version": version,
                "status": "synced",
            }

            if was_versioned:
                updated.append(name)
            else:
                added.append(name)

        except Exception as e:
            errors.append(f"[ERROR] {name}: {e}")

    save_registry(registry)

    print(f"\nAdded: {len(added)}")
    for name in added:
        print(f"  + {name}")
    print(f"Updated: {len(updated)}")
    for name in updated:
        print(f"  ~ {name}")
    if skipped:
        print(f"Skipped: {len(skipped)}")
        for s in skipped:
            print(f"  {s}")
    if errors:
        print(f"Errors: {len(errors)}")
        for err in errors:
            print(f"  {err}")


def status():
    """Show diff between repo and ~/.agents/skills/"""
    ensure_dirs()
    registry = load_registry()

    repo_skills = set(d.name for d in REPO_SKILLS_DIR.iterdir() if d.is_dir()) if REPO_SKILLS_DIR.exists() else set()
    local_skills = set(d.name for d in SKILLS_DIR.iterdir() if d.is_dir()) if SKILLS_DIR.exists() else set()

    only_in_repo = repo_skills - local_skills
    only_in_local = local_skills - repo_skills
    in_both = repo_skills & local_skills

    print(f"Repo skills directory: {REPO_SKILLS_DIR}")
    print(f"Local skills directory: {SKILLS_DIR}")
    print()

    if only_in_repo:
        print(f"Only in repo (need pull -> local): {len(only_in_repo)}")
        for name in sorted(only_in_repo):
            ver = registry["skills"].get(name, {}).get("version", "unknown")
            print(f"  {name} (v{ver})")

    if only_in_local:
        print(f"\nOnly in local (need push -> repo): {len(only_in_local)}")
        for name in sorted(only_in_local):
            skill_dir = SKILLS_DIR / name
            has_skill_md = (skill_dir / "SKILL.md").exists()
            marker = "✓" if has_skill_md else "?"
            print(f"  {marker} {name}")

    if in_both:
        print(f"\nIn both (synced): {len(in_both)}")
        for name in sorted(in_both):
            ver = registry["skills"].get(name, {}).get("version", "unknown")
            print(f"  {name} (v{ver})")

    print(f"\nSummary:")
    print(f"  Versioned: {len(repo_skills)}")
    print(f"  Local only: {len(only_in_local)}")
    print(f"  Repo only: {len(only_in_repo)}")


def list_skills():
    """List all versioned skills with metadata"""
    registry = load_registry()
    skills = list_versioned_skills()

    if not skills:
        print("No versioned skills.")
        return

    print(f"Versioned global skills ({len(skills)}):")
    print()

    for name in sorted(skills):
        meta = registry["skills"].get(name, {})
        ver = meta.get("version", "unknown")
        status_val = meta.get("status", "unknown")
        print(f"  {name:<35} v{ver:<10} [{status_val}]")


def init():
    """Initialize global-skills directory from ~/.agents/skills/"""
    ensure_dirs()

    if list_versioned_skills():
        print("global-skills/ already has skills. Use 'push' instead.")
        return

    print(f"Initializing global-skills/ from {SKILLS_DIR}")
    print("Copying all skills from local directory...")

    registry = load_registry()
    added = []

    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir():
            continue
        if not (skill_dir / "SKILL.md").exists():
            continue

        name = skill_dir.name
        dst = REPO_SKILLS_DIR / name
        shutil.copytree(skill_dir, dst)

        version = get_skill_version(name)
        registry["skills"][name] = {
            "version": version,
            "status": "initialized",
        }
        added.append(name)

    save_registry(registry)
    print(f"\nInitialized {len(added)} skills in global-skills/")
    print("Run 'git add global-skills/ global-skills-registry.json' to version them.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()
    arg = sys.argv[2] if len(sys.argv) > 2 else None

    commands = {
        "pull": pull,
        "push": lambda: push(arg),
        "status": status,
        "list": list_skills,
        "init": init,
    }

    if command not in commands:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)

    commands[command]()


if __name__ == "__main__":
    main()
