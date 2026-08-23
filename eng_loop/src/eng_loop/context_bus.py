from __future__ import annotations

import json
import logging
import string
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Entry types ───────────────────────────────────────────────────────

ENTRY_TYPES = frozenset(
    {
        "clarification",
        "intent_refinement",
        "critical_finding",
        "architect_decision",
    }
)


# ── Single immutable entry ───────────────────────────────────────────


@dataclass(frozen=True)
class BusEntry:
    """One append-only context entry."""

    entry_type: str
    content: dict[str, Any]
    source_stage: str = ""
    timestamp: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_type", self.entry_type.lower())
        if self.entry_type not in ENTRY_TYPES:
            raise ValueError(f"Unknown entry type: {self.entry_type!r}")


# ── The Bus ──────────────────────────────────────────────────────────


class ContextBus:
    """Append-only, versioned context carrier.

    Lives in-memory during execution, flushes to disk at each node
    transition.  Provides O(1) membership test for "was finding X
    already addressed?" and a lossless snapshot for cross-stage
    propagation.
    """

    # Cross-lingual synonym map (PT ←→ EN high-frequency domain words)
    _SYNONYM_MAP: dict[str, set[str]] = {
        "laranja": {"orange"},
        "orange": {"laranja"},
        "bolo": {"cake"},
        "cake": {"bolo"},
        "chocolate": {"chocolate", "chocolates"},
        "chocolates": {"chocolate"},
        "receita": {"recipe"},
        "recipe": {"receita"},
        "formato": {"format"},
        "format": {"formato"},
        "arquivo": {"file"},
        "file": {"arquivo"},
        "gluten": {"gluten"},
        "markdown": {"md"},
        "md": {"markdown"},
    }

    def __init__(
        self,
        max_entries: int = 200,
        flush_path: str | None = None,
        cross_session: bool = False,
    ) -> None:
        self._entries: list[BusEntry] = []
        self._max_entries = max_entries
        self._version = 0
        self._flush_path = flush_path
        self._cross_session = cross_session

        if cross_session and flush_path:
            self._load_from_disk()

    # ── Core API ─────────────────────────────────────────────────

    @property
    def version(self) -> int:
        return self._version

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def append(
        self,
        entry_type: str,
        content: dict[str, Any],
        source_stage: str = "",
    ) -> int:
        """Append an entry. Returns the new version."""
        if len(self._entries) >= self._max_entries:
            self._entries = self._entries[-self._max_entries // 2 :]
        self._entries.append(BusEntry(entry_type, content, source_stage))
        self._version += 1
        return self._version

    def is_resolved(self, finding_text: str, threshold: float = 0.25) -> bool:
        """Four-layer semantic check: exact → Jaccard → keyword → synonym.

        Returns True if any entry in the bus semantically covers *finding_text*.
        """
        if not finding_text:
            return False

        # Layer 1: exact substring (fast path)
        finding_lower = finding_text.lower()
        for entry in self._entries:
            content_str = _content_to_string(entry.content)
            if finding_lower in content_str.lower():
                return True

        # Prepare finding tokens (normalized + synonym-expanded)
        finding_tokens = _normalize(finding_text)
        if not finding_tokens:
            return False
        finding_expanded = self._expand_synonyms(finding_tokens)

        for entry in self._entries:
            content_str = _content_to_string(entry.content)
            content_tokens = _normalize(content_str)
            if not content_tokens:
                continue
            content_expanded = self._expand_synonyms(content_tokens)

            # Layer 2: Jaccard on expanded token sets
            overlap = finding_expanded & content_expanded
            union = finding_expanded | content_expanded
            if union and len(overlap) / len(union) >= threshold:
                return True

            # Layer 3: significant keyword overlap (length-filtered)
            sig_finding = {w for w in finding_expanded if len(w) > 2}
            sig_content = {w for w in content_expanded if len(w) > 2}
            if sig_finding and sig_content:
                common = sig_finding & sig_content
                if len(common) / max(len(sig_finding), 1) >= 0.3:
                    return True

        return False

    @staticmethod
    def _expand_synonyms(tokens: set[str]) -> set[str]:
        """Expand tokens with known cross-lingual synonyms."""
        expanded = set(tokens)
        for tok in tokens:
            if tok in ContextBus._SYNONYM_MAP:
                expanded |= ContextBus._SYNONYM_MAP[tok]
        return expanded

    # ── Snapshot / Restore ───────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """Lossless serializable snapshot for cross-stage propagation."""
        return {
            "version": self._version,
            "entries": [
                {
                    "type": e.entry_type,
                    "content": e.content,
                    "source": e.source_stage,
                    "ts": e.timestamp,
                }
                for e in self._entries
            ],
        }

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> ContextBus:
        bus = cls()
        bus._version = data.get("version", 0)
        for e in data.get("entries", []):
            bus._entries.append(
                BusEntry(
                    entry_type=e["type"],
                    content=e["content"],
                    source_stage=e.get("source", ""),
                    timestamp=e.get("ts", 0.0),
                )
            )
        return bus

    # ── Disk flush ───────────────────────────────────────────────

    def flush(self) -> None:
        """Append uncommitted entries to the JSONL file."""
        if not self._flush_path or not self._entries:
            return
        path = Path(self._flush_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                for entry in self._entries:
                    line = json.dumps(
                        {
                            "v": self._version,
                            "t": entry.entry_type,
                            "c": entry.content,
                            "s": entry.source_stage,
                            "ts": entry.timestamp,
                        },
                        ensure_ascii=False,
                    )
                    f.write(line + "\n")
            self._entries.clear()
        except OSError as exc:
            logger.warning("ContextBus flush failed (will retry): %s", exc)

    def _load_from_disk(self) -> None:
        if not self._flush_path:
            return
        path = Path(self._flush_path)
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    obj = json.loads(line)
                    self._entries.append(
                        BusEntry(
                            entry_type=obj["t"],
                            content=obj["c"],
                            source_stage=obj.get("s", ""),
                            timestamp=obj.get("ts", 0.0),
                        )
                    )
                    self._version = obj.get("v", self._version)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("ContextBus load failed (starting fresh): %s", exc)

    # ── Rotation ─────────────────────────────────────────────────

    @staticmethod
    def rotate(flush_path: str, keep: int = 50) -> None:
        """Keep only the last *keep* flush files."""
        import glob as _glob

        base = Path(flush_path).stem
        parent = Path(flush_path).parent
        pattern = str(parent / f"{base}-*.jsonl")
        files = sorted(_glob.glob(pattern), reverse=True)
        for old in files[keep:]:
            try:
                Path(old).unlink()
            except OSError:
                pass


# ── Helpers ──────────────────────────────────────────────────────────

# Punctuation table: map every punct char to None for fast stripping
_PUNCT_TABLE = str.maketrans("", "", string.punctuation + '{"}:,[]')


def _content_to_string(content: dict[str, Any]) -> str:
    """Extract just the meaningful values from a content dict.

    Avoids JSON structural noise (keys like 'q', 'a', braces, etc.)
    that dilutes semantic similarity scores.
    """
    parts = []
    for v in content.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (list, dict)):
            parts.append(json.dumps(v, ensure_ascii=False))
        else:
            parts.append(str(v))
    return " ".join(parts)


def _normalize(text: str) -> set[str]:
    """Lowercase → strip diacritics → strip punctuation → tokenize."""
    text = text.lower()
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    no_punct = ascii_only.translate(_PUNCT_TABLE)
    return set(no_punct.split())
