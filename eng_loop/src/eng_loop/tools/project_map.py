from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ============================================================
# PROJECT MAP — Structural overview of the codebase
# ============================================================
# Runs once at init, cached in state, injected into every stage prompt.
# Eliminates 3-8 exploratory glob/read tool-calls per stage.
# ============================================================

# Extensions by language category
LANG_EXTENSIONS: dict[str, list[str]] = {
    "typescript": [".ts", ".tsx"],
    "javascript": [".js", ".jsx"],
    "python": [".py"],
    "rust": [".rs"],
    "go": [".go"],
    "java": [".java"],
    "csharp": [".cs"],
    "ruby": [".rb"],
    "php": [".php"],
    "other": [".vue", ".svelte", ".astro", ".elm"],
}

# Config files that define project structure
CONFIG_PATTERNS = [
    "package.json",
    "tsconfig.json",
    "jsconfig.json",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "Pipfile",
    "poetry.lock",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Gemfile",
    "composer.json",
    "mix.exs",
    "deno.json",
    "bun.lock",
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    ".eslintrc*",
    ".prettierrc*",
    "tailwind.config.*",
    "next.config.*",
    "nuxt.config.*",
    "vite.config.*",
    "webpack.config.*",
    "jest.config.*",
    "vitest.config.*",
    "playwright.config.*",
    "pyrightconfig.json",
    ".python-version",
    "Makefile",
    "Dockerfile",
    "docker-compose.*",
    ".env.example",
    "tsup.config.*",
    "turbo.json",
]

# Directories that indicate test infrastructure
TEST_DIR_PATTERNS = ["test", "tests", "__tests__", "spec", "specs", "e2e", "integration"]

# Directories to exclude from the tree
EXCLUDED_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".next",
    ".nuxt",
    ".svelte-kit",
    "dist",
    "build",
    "out",
    ".turbo",
    ".cache",
    "coverage",
    ".pytest_cache",
    ".tox",
    ".mypy_cache",
    "graphify-out",
    ".eng",
    "artifacts",
    ".ruff_cache",
    ".ipynb_checkpoints",
}

EXCLUDED_SUFFIXES = {".egg-info"}

# Max tree depth and width
MAX_TREE_DEPTH = 6
MAX_TREE_ENTRIES_PER_DIR = 30
MAX_TREE_CHARS = 8000


class ProjectMap:
    """Pre-computed structural map of a project."""

    def __init__(self):
        self.tree: str = ""
        self.entry_points: list[str] = []
        self.config_files: list[str] = []
        self.module_boundaries: list[str] = []
        self.test_dirs: list[str] = []
        self.languages: dict[str, int] = {}
        self.stats: dict[str, int] = {}
        self.routes: list[str] = []
        self.components: list[str] = []
        self.raw_data: dict[str, Any] = {}

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    @staticmethod
    def build(project_root: str) -> ProjectMap:
        """Build the project map. Returns a ProjectMap instance."""
        pm = ProjectMap()
        root = Path(project_root)
        if not root.exists():
            return pm

        pm._scan(root)
        pm._build_tree(root)
        pm._detect_entry_points(root)
        pm._detect_config_files(root)
        pm._detect_module_boundaries(root)
        pm._detect_test_dirs(root)
        pm._count_languages(root)
        pm._detect_routes(root)
        pm._detect_components(root)
        pm._compute_stats()

        return pm

    @staticmethod
    def update(existing: dict[str, Any], project_root: str, new_files: list[str]) -> ProjectMap:
        """Incremental update: rebuild map, but note new files."""
        pm = ProjectMap.build(project_root)
        pm.raw_data["updated_from_existing"] = True
        pm.raw_data["new_files"] = new_files
        return pm

    def to_prompt_section(self, include_details: bool = True) -> str:
        """Render the map as a markdown section for prompt injection."""
        parts = ["## PROJECT MAP"]

        if self.tree:
            parts.append("### File Structure")
            parts.append("```")
            parts.append(self.tree)
            parts.append("```")

        if self.config_files:
            parts.append(f"\n### Config Files ({len(self.config_files)})")
            for cf in self.config_files[:15]:
                parts.append(f"- `{cf}`")

        if self.entry_points:
            parts.append(f"\n### Entry Points ({len(self.entry_points)})")
            for ep in self.entry_points[:8]:
                parts.append(f"- `{ep}`")

        if self.languages:
            parts.append("\n### Languages")
            for lang, count in sorted(self.languages.items(), key=lambda x: -x[1]):
                parts.append(f"- {lang}: {count} files")

        if self.module_boundaries:
            parts.append(f"\n### Module Boundaries ({len(self.module_boundaries)})")
            for mb in self.module_boundaries[:12]:
                parts.append(f"- `{mb}`")

        if self.test_dirs:
            parts.append(f"\n### Test Directories ({len(self.test_dirs)})")
            for td in self.test_dirs[:8]:
                parts.append(f"- `{td}`")

        if self.routes:
            parts.append(f"\n### Routes ({len(self.routes)})")
            for r in self.routes[:15]:
                parts.append(f"- `{r}`")

        if self.components:
            parts.append(f"\n### Components ({len(self.components)})")
            for c in self.components[:15]:
                parts.append(f"- `{c}`")

        if self.stats:
            parts.append("\n### Stats")
            for k, v in self.stats.items():
                parts.append(f"- {k}: {v}")

        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for state persistence."""
        return {
            "tree": self.tree,
            "entry_points": self.entry_points,
            "config_files": self.config_files,
            "module_boundaries": self.module_boundaries,
            "test_dirs": self.test_dirs,
            "languages": self.languages,
            "stats": self.stats,
            "routes": self.routes,
            "components": self.components,
            **self.raw_data,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ProjectMap:
        """Deserialize from state."""
        pm = ProjectMap()
        pm.tree = data.get("tree", "")
        pm.entry_points = data.get("entry_points", [])
        pm.config_files = data.get("config_files", [])
        pm.module_boundaries = data.get("module_boundaries", [])
        pm.test_dirs = data.get("test_dirs", [])
        pm.languages = data.get("languages", {})
        pm.stats = data.get("stats", {})
        pm.routes = data.get("routes", [])
        pm.components = data.get("components", [])
        pm.raw_data = {
            k: v
            for k, v in data.items()
            if k
            not in {
                "tree",
                "entry_points",
                "config_files",
                "module_boundaries",
                "test_dirs",
                "languages",
                "stats",
                "routes",
                "components",
            }
        }
        return pm

    # ----------------------------------------------------------
    # Internal scanning
    # ----------------------------------------------------------

    def _scan(self, root: Path):
        """Collect all files, excluding known noise."""
        all_files = []
        for dirpath, dirnames, filenames in os_walk_filtered(root, EXCLUDED_DIRS):
            dp = Path(dirpath)
            for fname in filenames:
                full = dp / fname
                rel = str(full.relative_to(root))
                all_files.append(rel)
        self.raw_data["_all_files"] = all_files

    def _build_tree(self, root: Path):
        """Build a compact ASCII tree of the project structure."""
        lines = [root.name + "/"]
        _render_tree(
            root,
            "",
            lines,
            depth=0,
            max_depth=MAX_TREE_DEPTH,
            max_entries=MAX_TREE_ENTRIES_PER_DIR,
            excluded=EXCLUDED_DIRS,
        )
        raw = "\n".join(lines)
        if len(raw) > MAX_TREE_CHARS:
            self.tree = raw[:MAX_TREE_CHARS] + "\n... [truncated]"
        else:
            self.tree = raw

    def _detect_entry_points(self, root: Path):
        """Detect project entry points."""
        candidates = [
            "index.ts",
            "index.tsx",
            "index.js",
            "index.jsx",
            "main.ts",
            "main.js",
            "main.py",
            "main.rs",
            "main.go",
            "app.tsx",
            "app.ts",
            "app.jsx",
            "app.js",
            "app.py",
            "server.ts",
            "server.js",
            "server.py",
            "program.ts",
            "program.js",
            "src/index.ts",
            "src/index.tsx",
            "src/main.ts",
            "src/main.py",
            "src/app.tsx",
            "src/app.py",
            "src/server.ts",
            "bin/www",
            "bin/server",
        ]
        for c in candidates:
            if (root / c).exists():
                self.entry_points.append(c)

    def _detect_config_files(self, root: Path):
        """Detect configuration files."""
        for pattern in CONFIG_PATTERNS:
            if "*" in pattern:
                matched = list(root.glob(pattern))
                for m in matched:
                    rel = str(m.relative_to(root))
                    if rel not in self.config_files:
                        self.config_files.append(rel)
            else:
                if (root / pattern).exists():
                    self.config_files.append(pattern)

    def _detect_module_boundaries(self, root: Path):
        """Detect top-level module directories."""
        try:
            for entry in sorted(root.iterdir()):
                if entry.is_dir() and entry.name not in EXCLUDED_DIRS:
                    if not entry.name.startswith(".") or entry.name in ("src", "lib", "packages", "apps", "modules"):
                        self.module_boundaries.append(entry.name + "/")
        except OSError:
            pass

    def _detect_test_dirs(self, root: Path):
        """Detect test infrastructure directories."""
        try:
            for entry in sorted(root.iterdir()):
                if entry.is_dir() and entry.name.lower() in TEST_DIR_PATTERNS:
                    self.test_dirs.append(entry.name + "/")
        except OSError:
            pass

    def _count_languages(self, root: Path):
        """Count files by language."""
        counts: dict[str, int] = {}
        all_files = self.raw_data.get("_all_files", [])
        for f in all_files:
            suffix = Path(f).suffix.lower()
            matched = False
            for lang, exts in LANG_EXTENSIONS.items():
                if suffix in exts:
                    counts[lang] = counts.get(lang, 0) + 1
                    matched = True
                    break
            if not matched and suffix:
                counts["other"] = counts.get("other", 0) + 1
        self.languages = counts

    def _detect_routes(self, root: Path):
        """Detect route definitions (Next.js, Express, FastAPI, etc.)."""
        route_patterns = [
            "src/app/**/page.*",
            "app/**/page.*",
            "src/pages/**/*.*",
            "pages/**/*.*",
            "src/routes/**/*.*",
            "routes/**/*.*",
            "src/api/**/*.*",
        ]
        for pattern in route_patterns:
            for match in root.glob(pattern):
                rel = str(match.relative_to(root))
                if rel not in self.routes:
                    self.routes.append(rel)
            if len(self.routes) >= 20:
                break

    def _detect_components(self, root: Path):
        """Detect UI components."""
        comp_patterns = [
            "src/components/**/*.*",
            "components/**/*.*",
            "src/ui/**/*.*",
            "ui/**/*.*",
        ]
        for pattern in comp_patterns:
            for match in root.glob(pattern):
                rel = str(match.relative_to(root))
                if rel not in self.components:
                    self.components.append(rel)
            if len(self.components) >= 20:
                break

    def _compute_stats(self):
        all_files = self.raw_data.get("_all_files", [])
        self.stats = {
            "total_files": len(all_files),
        }


def _is_excluded(name: str, excluded: set[str]) -> bool:
    """Check if a directory name should be excluded."""
    if name in excluded or name.startswith("."):
        return True
    for suffix in EXCLUDED_SUFFIXES:
        if name.endswith(suffix):
            return True
    return False


def os_walk_filtered(root: Path, excluded: set[str]):
    """Like os.walk but prunes excluded directories."""
    for dirpath, dirnames, filenames in __import__("os").walk(root):
        dirnames[:] = [d for d in dirnames if not _is_excluded(d, excluded)]
        yield dirpath, dirnames, filenames


def _render_tree(
    dirpath: Path, prefix: str, lines: list[str], depth: int, max_depth: int, max_entries: int, excluded: set[str]
):
    """Recursively render a compact directory tree (ASCII-only for cross-platform compatibility)."""
    try:
        entries = sorted(dirpath.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except OSError:
        return

    entries = [e for e in entries if not _is_excluded(e.name, excluded)]
    dirs = [e for e in entries if e.is_dir()]
    files = [e for e in entries if e.is_file()]

    # Show dirs first, then files, with depth limit
    all_shown = []
    for d in dirs[: max_entries // 2]:
        all_shown.append((d, True))
    for f in files[: max_entries - len(all_shown)]:
        all_shown.append((f, False))

    total = len(all_shown)
    for i, (entry, is_dir) in enumerate(all_shown):
        is_last = i == total - 1
        connector = "`-- " if is_last else "|-- "
        suffix = "/" if is_dir else ""
        lines.append(f"{prefix}{connector}{entry.name}{suffix}")

        if is_dir and depth < max_depth:
            extension = "    " if is_last else "|   "
            _render_tree(entry, prefix + extension, lines, depth + 1, max_depth, max(3, max_entries // 3), excluded)

    if not all_shown and depth == 0:
        lines.append(dirpath.name + "/ (empty or excluded)")


def get_project_map(state: dict[str, Any]) -> ProjectMap | None:
    """Retrieve ProjectMap from state. Returns None if not built."""
    pm_data = state.get("project_map")
    if not pm_data:
        return None
    return ProjectMap.from_dict(pm_data)


def get_project_map_prompt_section(state: dict[str, Any]) -> str:
    """Get the prompt section for the current project map. Returns empty string if not available."""
    pm = get_project_map(state)
    if not pm or not pm.tree:
        return ""
    return pm.to_prompt_section()
