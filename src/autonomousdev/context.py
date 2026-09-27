from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .repository import FileEntry, RepositoryIndex


@dataclass(slots=True)
class ContextItem:
    path: str
    score: float
    reason: list[str]
    content: str
    content_sha256: str
    start_line: int
    end_line: int
    estimated_tokens: int


@dataclass(slots=True)
class ContextBundle:
    task: str
    token_budget: int
    estimated_tokens: int
    items: list[ContextItem]
    omitted_candidates: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "token_budget": self.token_budget,
            "estimated_tokens": self.estimated_tokens,
            "items": [asdict(item) for item in self.items],
            "omitted_candidates": self.omitted_candidates,
        }


class ContextEngine:
    """Deterministic retrieval and packing; no full-repository prompt path exists."""

    def __init__(self, token_budget: int = 12_000, max_chars_per_file: int = 16_000):
        self.token_budget = token_budget
        self.max_chars_per_file = max_chars_per_file

    def select(
        self,
        task: str,
        index: RepositoryIndex,
        *,
        changed_paths: list[str] | None = None,
        previous_errors: list[str] | None = None,
    ) -> ContextBundle:
        terms = self._terms(task + " " + " ".join(previous_errors or []))
        changed = set(changed_paths or [])
        ranked = sorted(
            ((self._score(entry, terms, changed), entry) for entry in index.files),
            key=lambda pair: (-pair[0][0], pair[1].path),
        )
        items: list[ContextItem] = []
        used = 0
        seen_hashes: set[str] = set()
        for (score, reasons), entry in ranked:
            if score <= 0 and items:
                continue
            item = self._read_item(Path(index.root), entry, score, reasons)
            if item is None or item.content_sha256 in seen_hashes:
                continue
            if used + item.estimated_tokens > self.token_budget:
                continue
            items.append(item)
            used += item.estimated_tokens
            seen_hashes.add(item.content_sha256)
        return ContextBundle(task, self.token_budget, used, items, len(ranked) - len(items))

    def _score(
        self, entry: FileEntry, terms: set[str], changed: set[str]
    ) -> tuple[float, list[str]]:
        searchable = self._terms(" ".join([entry.path, *entry.symbols, *entry.imports]))
        overlap = terms & searchable
        score = float(len(overlap) * 5)
        reasons = [f"term:{term}" for term in sorted(overlap)[:8]]
        path_terms = self._terms(entry.path)
        exact_path_overlap = terms & path_terms
        score += len(exact_path_overlap) * 2
        if entry.path in changed:
            score += 20
            reasons.append("changed-file")
        if entry.role == "test" and {"test", "tests", "failing", "failure"} & terms:
            score += 6
            reasons.append("test-role")
        if entry.role == "config" and {"config", "dependency", "build"} & terms:
            score += 5
            reasons.append("config-role")
        score += 1 / (1 + math.log2(max(entry.size, 1)))
        return score, reasons or ["repository-overview"]

    def _read_item(
        self, root: Path, entry: FileEntry, score: float, reasons: list[str]
    ) -> ContextItem | None:
        absolute = (root / entry.path).resolve()
        try:
            absolute.relative_to(root)
        except ValueError:
            return None
        raw = absolute.read_bytes()
        if b"\x00" in raw:
            return None
        text = raw.decode("utf-8", errors="replace")
        content = self._compress(text)
        lines = content.count("\n") + 1
        return ContextItem(
            path=entry.path,
            score=round(score, 3),
            reason=reasons,
            content=content,
            content_sha256=hashlib.sha256(content.encode()).hexdigest(),
            start_line=1,
            end_line=lines,
            estimated_tokens=max(1, (len(content) + 3) // 4),
        )

    def _compress(self, text: str) -> str:
        if len(text) <= self.max_chars_per_file:
            return text
        half = self.max_chars_per_file // 2
        return text[:half] + "\n\n... [middle omitted by context budget] ...\n\n" + text[-half:]

    @staticmethod
    def _terms(text: str) -> set[str]:
        normalized = re.sub(r"[_-]+", " ", text.lower())
        return {
            term
            for term in re.findall(r"[a-z][a-z0-9]{1,}", normalized)
            if term not in {"the", "and", "for", "with", "from", "that", "this", "into", "add"}
        }
