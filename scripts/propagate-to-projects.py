#!/usr/bin/env python3
"""
Propagate FF protocol changes to consumer projects.

Usage:
    python scripts/propagate-to-projects.py list          # List projects with .eng/ submodule
    python scripts/propagate-to-projects.py check         # Check which projects need updates
    python scripts/propagate-to-projects.py update [path] # Update one project or all
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent  # .engineering-loop
ENGINEERING_LOOP = ROOT

# Framework-owned opencode files copied into every consumer project (overwritten when stale):
# the /ff command and the ff-executor agent the planner dispatches (FF v14).
OPENCODE_FILES = [
    Path(".opencode") / "commands" / "ff.md",
    Path(".opencode") / "agents" / "ff-executor.md",
]

# Projects are siblings of .engineering-loop in the same parent directory
PROJECTS_BASE = ROOT.parent  # C:\Users\emers\Documents\Claude\Projects


def get_current_commit():
    """Get current commit of engineering-loop."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ENGINEERING_LOOP,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def get_submodule_commit(project_path):
    """Get the commit that a project's .eng/ submodule points to."""
    eng = Path(project_path) / ".eng"
    if not eng.exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(eng), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def has_ff_directory(project_path):
    """Check if project has .ff/ directory."""
    return (Path(project_path) / ".ff").exists()


def has_ff_command(project_path):
    """Check if project has .opencode/commands/ff.md."""
    return (Path(project_path) / ".opencode" / "commands" / "ff.md").exists()


def gitignore_has_pattern(project_path, pattern):
    """Check if .gitignore contains pattern."""
    gi = Path(project_path) / ".gitignore"
    if not gi.exists():
        return False
    return any(pattern in line for line in gi.read_text().splitlines())


def find_projects(base_path=None):
    """Find directories that have .eng/ as a submodule."""
    base = Path(base_path or PROJECTS_BASE)
    projects = []
    for entry in base.iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            eng = entry / ".eng"
            if eng.exists() and (eng / ".git").exists():
                projects.append(entry)
    return projects


def list_projects():
    """List all consumer projects."""
    projects = find_projects()
    if not projects:
        print("No consumer projects found with .eng/ submodule in", PROJECTS_BASE)
        return
    for p in sorted(projects):
        print(f"  {p.name}")


def check_projects():
    """Check which projects need updates."""
    current = get_current_commit()
    projects = find_projects()

    if not projects:
        print("No consumer projects found.")
        return

    print(f"\nCurrent engineering-loop commit: {current[:8]}")
    print("-" * 60)

    for p in sorted(projects):
        sub_commit = get_submodule_commit(p)
        ff_dir = has_ff_directory(p)
        ff_cmd = has_ff_command(p)
        ignore_ff = gitignore_has_pattern(p, ".ff/")
        ignore_opencode = gitignore_has_pattern(p, ".opencode/")

        status = "OK" if (
            sub_commit == current and ff_dir and ff_cmd and ignore_ff and ignore_opencode
        ) else "NEEDS UPDATE"

        print(f"\n{p.name} [{status}]")
        sub_status = "+" if sub_commit == current else "- " + (sub_commit[:8] if sub_commit else "N/A")
        print(f"  Submodule:  {sub_status}")
        print(f"  .ff/:      {'+' if ff_dir else '-'}")
        print(f"  /ff cmd:   {'+' if ff_cmd else '-'}")
        print(f"  .gitignore: .ff/ {'+' if ignore_ff else '-'} .opencode/ {'+' if ignore_opencode else '-'}")


def update_project(project_path, force=False):
    """Update a single consumer project."""
    p = Path(project_path)
    print(f"\nUpdating {p.name}...")

    # Update submodule
    result = subprocess.run(
        ["git", "submodule", "update", "--remote", ".eng"],
        cwd=p,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ✗ Failed to update submodule: {result.stderr.strip()}")
        return False
    print(f"  ✓ Submodule updated")

    # Sync skills
    sync_script = p / ".eng" / "scripts" / "sync-global-skills.py"
    if sync_script.exists():
        result = subprocess.run(
            ["python", str(sync_script), "pull"],
            cwd=p,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  ⚠ Skills sync issue: {result.stderr.strip()}")
        else:
            print(f"  ✓ Skills synced")

    # Create .ff/ directory
    ff_dir = p / ".ff"
    if not ff_dir.exists():
        ff_dir.mkdir(parents=True)
        (ff_dir / "traces").mkdir(exist_ok=True)

        (ff_dir / "lessons.json").write_text("[]")
        (ff_dir / "changelog.md").write_text("# FF Changelog\n\nSession history for this project.\n")
        (ff_dir / "README.md").write_text(
            "# FF Workspace\n\nSession traces and state for FF protocol.\nGitignored — working artifacts only.\n"
        )
        print(f"  ✓ .ff/ directory created")

    # Create or refresh the framework-owned opencode files (/ff command, ff-executor agent)
    for line in sync_opencode_files(p):
        print(line)

    # Update .gitignore
    gi = p / ".gitignore"
    gi_content = gi.read_text() if gi.exists() else ""

    patterns_added = []
    if ".ff/" not in gi_content:
        patterns_added.append(".ff/")
    if ".opencode/" not in gi_content:
        patterns_added.append(".opencode/")

    if patterns_added:
        if gi_content and not gi_content.endswith("\n"):
            gi_content += "\n"
        gi_content += "\n# FF workspace\n.ff/\n\n# OpenCode local config\n.opencode/\n"
        gi.write_text(gi_content)
        print(f"  ✓ .gitignore updated: {', '.join(patterns_added)}")

    # Stage changes
    result = subprocess.run(
        ["git", "add", ".eng", ".gitignore"] + [rel.as_posix() for rel in OPENCODE_FILES],
        cwd=p,
        capture_output=True,
        text=True,
    )
    print(f"  ✓ Changes staged (run 'git commit' to finalize)")

    return True


def sync_opencode_files(project_path):
    """Copy every framework-owned opencode file into the project; overwrite when stale.

    Returns one status line per file created or updated (empty when all are current).
    """
    p = Path(project_path)
    lines = []
    for rel in OPENCODE_FILES:
        source = ROOT / rel
        if not source.exists():
            continue
        source_text = source.read_text(encoding="utf-8")
        target = p / rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source_text, encoding="utf-8")
            lines.append(f"  ✓ {rel.as_posix()} created")
        elif target.read_text(encoding="utf-8") != source_text:
            target.write_text(source_text, encoding="utf-8")
            lines.append(f"  ✓ {rel.as_posix()} updated (was stale)")
    return lines


def push_to_origin():
    """Push engineering-loop to origin."""
    result = subprocess.run(
        ["git", "push", "origin", "master"],
        cwd=ENGINEERING_LOOP,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ✗ Push failed: {result.stderr.strip()}")
        return False
    print(f"  ✓ Pushed to origin/master")
    return True


def update_all():
    """Update all consumer projects."""
    current = get_current_commit()
    projects = find_projects()

    if not projects:
        print("No consumer projects found.")
        return

    # Push engineering-loop first so submodules can update from remote
    print(f"\nPushing engineering-loop to origin...")
    if not push_to_origin():
        print("Push failed. Submodules may not update correctly.")
        response = input("Continue anyway? (y/N): ").strip().lower()
        if response != "y":
            return

    print(f"\nUpdating all projects to engineering-loop commit {current[:8]}...")
    results = []
    for p in sorted(projects):
        ok = update_project(p)
        results.append((p.name, ok))

    print(f"\n{'=' * 40}")
    print(f"Updated: {sum(1 for _, ok in results if ok)}/{len(results)}")
    for name, ok in results:
        print(f"  [{'+' if ok else '-'}] {name}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "list":
        list_projects()
    elif cmd == "check":
        check_projects()
    elif cmd == "update":
        path = sys.argv[2] if len(sys.argv) > 2 else None
        if path:
            update_project(path)
        else:
            update_all()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
