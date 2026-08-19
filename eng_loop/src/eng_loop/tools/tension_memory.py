from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Minimum Jaccard similarity for auto-heal to trigger
AUTO_HEAL_THRESHOLD = 0.6

# Max entries to keep (oldest evicted on record)
MAX_ENTRIES = 500


@dataclass(frozen=True)
class TensionMatch:
    """Result of a similarity query against stored tension entries."""

    entry: dict[str, Any]
    score: float


def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for hashing."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokenize(text: str) -> set[str]:
    """Split normalized text into word tokens."""
    return set(_normalize(text).split())


def _jaccard(a: str, b: str) -> float:
    """Jaccard similarity between two texts based on word token overlap."""
    tokens_a = _tokenize(a)
    tokens_b = _tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union else 0.0


def _hash(text: str) -> str:
    """SHA-256 prefix for deduplication."""
    return hashlib.sha256(_normalize(text).encode()).hexdigest()[:16]


class TensionMemory:
    """Persistent store for Lens 4 tension resolutions.

    Learns from past tension outcomes to inform future decisions:
    - `query()` returns ranked matches for a given tension text
    - `record()` stores a new resolution or increments existing count
    - Data persists to `.eng/tension-memory.json` (project-specific, gitignored)

    Invariant: query never mutates state; record always persists.
    """

    def __init__(self, storage_path: str | Path | None = None):
        self._storage_path = Path(storage_path) if storage_path else None
        self._entries: list[dict[str, Any]] = []
        self._load()

    # ── Persistence ───────────────────────────────────────────────

    def _load(self) -> None:
        """Load entries from disk. Silently ignores missing/corrupt files."""
        if not self._storage_path or not self._storage_path.exists():
            return
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                self._entries = raw
            elif isinstance(raw, dict) and "entries" in raw:
                self._entries = raw["entries"]
            logger.info("tension_memory: loaded %d entries from %s", len(self._entries), self._storage_path)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("tension_memory: failed to load %s: %s", self._storage_path, exc)
            self._entries = []

    def _save(self) -> None:
        """Write entries to disk. No-op if no storage path configured."""
        if not self._storage_path:
            return
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps({"entries": self._entries}, indent=2, ensure_ascii=False)
            self._storage_path.write_text(payload, encoding="utf-8")
        except OSError as exc:
            logger.warning("tension_memory: failed to save %s: %s", self._storage_path, exc)

    # ── Query ─────────────────────────────────────────────────────

    def query(self, tension_text: str, threshold: float = AUTO_HEAL_THRESHOLD) -> list[TensionMatch]:
        """Find stored tensions similar to the given text.

        Returns matches sorted by descending similarity score.
        Only entries above `threshold` are returned.
        """
        if not self._entries:
            return []

        scored: list[TensionMatch] = []
        for entry in self._entries:
            score = _jaccard(tension_text, entry["tension_text"])
            if score >= threshold:
                scored.append(TensionMatch(entry=entry, score=score))

        scored.sort(key=lambda m: m.score, reverse=True)
        if scored:
            logger.info(
                "tension_memory: query returned %d match(es), best score %.2f",
                len(scored),
                scored[0].score,
            )
        return scored

    # ── Record ────────────────────────────────────────────────────

    def record(
        self,
        tension_text: str,
        resolution: str,
        *,
        complexity_before: str = "",
        complexity_after: str = "",
        stage_id: str = "",
        work_type: str = "",
    ) -> None:
        """Store or update a tension resolution.

        If a near-identical entry exists (Jaccard >= 0.95), increments its
        count and updates last_resolved. Otherwise appends a new entry.
        """
        now = time.time()
        normalized = _normalize(tension_text)
        tension_hash = _hash(tension_text)

        # Check for near-duplicate to merge
        for entry in self._entries:
            if _jaccard(tension_text, entry["tension_text"]) >= 0.95 and entry["resolution"] == resolution:
                entry["count"] += 1
                entry["last_resolved"] = now
                self._save()
                logger.info(
                    "tension_memory: merged into existing entry %s (count=%d)", entry["tension_hash"], entry["count"]
                )
                return

        # New entry
        new_entry = {
            "tension_hash": tension_hash,
            "tension_text": normalized,
            "resolution": resolution,
            "complexity_before": complexity_before,
            "complexity_after": complexity_after,
            "stage_id": stage_id,
            "work_type": work_type,
            "count": 1,
            "first_seen": now,
            "last_resolved": now,
        }
        self._entries.append(new_entry)

        # Evict oldest if over limit
        if len(self._entries) > MAX_ENTRIES:
            self._entries.sort(key=lambda e: e["last_resolved"])
            self._entries = self._entries[-MAX_ENTRIES:]

        self._save()
        logger.info("tension_memory: recorded new entry %s", tension_hash)

    # ── Resolution lookup ─────────────────────────────────────────

    def get_resolution(self, tension_text: str) -> str | None:
        """Return the most common resolution for tensions similar to the input.

        Checks high-confidence matches (score >= 0.8) first, then falls back
        to the configured threshold. Returns the resolution string or None.
        """
        # High-confidence pass
        high_matches = self.query(tension_text, threshold=0.8)
        if high_matches:
            best = high_matches[0]
            resolution = best.entry["resolution"]
            logger.info(
                "tension_memory: high-confidence match (%.2f) → %s (count=%d)",
                best.score,
                resolution,
                best.entry["count"],
            )
            return resolution

        # Standard threshold pass
        matches = self.query(tension_text)
        if matches:
            best = matches[0]
            resolution = best.entry["resolution"]
            logger.info(
                "tension_memory: match (%.2f) → %s (count=%d)",
                best.score,
                resolution,
                best.entry["count"],
            )
            return resolution

        return None

    # ── Stats ─────────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self._entries)

    def summary(self) -> dict[str, Any]:
        """Aggregated statistics for observability."""
        if not self._entries:
            return {"total": 0}

        resolutions: dict[str, int] = {}
        for entry in self._entries:
            res = entry["resolution"]
            resolutions[res] = resolutions.get(res, 0) + entry["count"]

        return {
            "total": len(self._entries),
            "total_occurrences": sum(e["count"] for e in self._entries),
            "resolutions": resolutions,
        }
