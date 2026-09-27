from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class RunState(StrEnum):
    DISCOVER = "DISCOVER"
    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    TEST = "TEST"
    ANALYZE_FAILURE = "ANALYZE_FAILURE"
    REPAIR = "REPAIR"
    REVIEW = "REVIEW"
    VERIFY = "VERIFY"
    COMPLETE = "COMPLETE"
    ESCALATE = "ESCALATE"


class RunOutcome(StrEnum):
    RUNNING = "RUNNING"
    VERIFIED_COMPLETE = "VERIFIED_COMPLETE"
    ESCALATED = "ESCALATED"


@dataclass(slots=True)
class Budget:
    max_attempts: int = 6
    max_tool_calls: int = 80
    max_tokens: int = 60_000
    max_wall_seconds: int = 1_800
    max_stagnant_loops: int = 2
    max_repeated_failures: int = 2


@dataclass(slots=True)
class Usage:
    attempts: int = 0
    loops: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(slots=True)
class Evidence:
    kind: str
    passed: bool
    summary: str
    command: list[str] = field(default_factory=list)
    exit_code: int | None = None
    duration_ms: int = 0
    output: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ReviewFinding:
    severity: str
    category: str
    message: str
    path: str | None = None
    line: int | None = None


@dataclass(slots=True)
class ToolRequest:
    name: str
    arguments: dict[str, Any]
    rationale: str = ""


@dataclass(slots=True)
class Plan:
    summary: str
    steps: list[str]
    acceptance_checks: list[str] = field(default_factory=list)
    likely_files: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ModelResponse:
    data: dict[str, Any]
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(slots=True)
class Event:
    sequence: int
    timestamp: str
    state: str
    type: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RunRecord:
    id: str
    task: str
    repository: str
    state: str
    outcome: str
    created_at: str
    updated_at: str
    deadline_at: str
    budget: Budget
    usage: Usage = field(default_factory=Usage)
    plan: Plan | None = None
    evidence: list[Evidence] = field(default_factory=list)
    findings: list[ReviewFinding] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    failure_fingerprints: list[str] = field(default_factory=list)
    patch_fingerprints: list[str] = field(default_factory=list)
    escalation_reason: str | None = None
    final_patch: str = ""
    pr_description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
