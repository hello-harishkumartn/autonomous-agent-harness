from __future__ import annotations

import re
from typing import Any

from .providers import ModelProvider, ProviderError
from .types import ReviewFinding

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*[\"'][^\"']{8,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


class ReadOnlyReviewer:
    """Reviewer has no tool gateway and therefore cannot mutate the repository."""

    def __init__(self, provider: ModelProvider):
        self.provider = provider
        self.last_usage = (0, 0)

    def review(self, task: str, plan: dict[str, Any], diff: str) -> list[ReviewFinding]:
        self.last_usage = (0, 0)
        findings = self._static_findings(diff)
        try:
            response = self.provider.generate_json(
                "review",
                {
                    "task": task,
                    "plan": plan,
                    "diff": diff,
                    "required_output": {
                        "findings": [
                            {
                                "severity": "blocking|warning|note",
                                "category": "correctness|security|tests|maintainability|requirements",
                                "message": "concise finding",
                                "path": "optional path",
                                "line": "optional integer",
                            }
                        ]
                    },
                    "capabilities": {"read_only": True, "tools": []},
                },
            )
        except ProviderError as error:
            findings.append(ReviewFinding("blocking", "review", f"reviewer unavailable: {error}"))
            return findings
        self.last_usage = (response.input_tokens, response.output_tokens)
        raw_findings = response.data.get("findings", [])
        if not isinstance(raw_findings, list):
            findings.append(
                ReviewFinding("blocking", "review", "reviewer returned malformed findings")
            )
            return findings
        for item in raw_findings[:100]:
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity", "warning")).lower()
            if severity not in {"blocking", "warning", "note"}:
                severity = "warning"
            line = item.get("line")
            findings.append(
                ReviewFinding(
                    severity,
                    str(item.get("category", "maintainability")),
                    str(item.get("message", "unspecified finding"))[:2_000],
                    str(item["path"]) if item.get("path") else None,
                    int(line) if isinstance(line, int | float) else None,
                )
            )
        return findings

    @staticmethod
    def _static_findings(diff: str) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        for pattern in SECRET_PATTERNS:
            if pattern.search(diff):
                findings.append(
                    ReviewFinding("blocking", "security", "possible secret introduced in patch")
                )
                break
        if not diff.strip():
            findings.append(
                ReviewFinding("blocking", "requirements", "implementation produced no patch")
            )
        if len(diff.encode()) > 1_000_000:
            findings.append(ReviewFinding("warning", "maintainability", "patch exceeds 1 MB"))
        return findings
