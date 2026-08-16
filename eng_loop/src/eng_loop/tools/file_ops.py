from __future__ import annotations

from pathlib import Path


def read_file(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path: str | Path, content: str) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return str(p)


def append_file(path: str | Path, content: str) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(content)
    return str(p)


def file_exists(path: str | Path) -> bool:
    return Path(path).exists()


def list_dir(path: str | Path, pattern: str | None = None) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    if pattern:
        return [str(f) for f in p.glob(pattern)]
    return [str(f) for f in p.iterdir()]


def save_json(path: str | Path, data: dict | list) -> str:
    import json

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return str(p)


def load_json(path: str | Path) -> dict | list:
    import json

    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)
