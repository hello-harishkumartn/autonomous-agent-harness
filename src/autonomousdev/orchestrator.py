from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .config import HarnessConfig
from .context import ContextEngine
from .providers import ModelProvider, ProviderError
from .repository import RepositoryMapper
from .reviewer import ReadOnlyReviewer
from .sandbox import DockerSandbox
from .store import JsonRunStore, RunStore
from .tools import ControlledTools
from .types import Event, Plan, RunOutcome, RunRecord, RunState, ToolRequest
from .verifier import Verifier

TRANSITIONS = {
    RunState.DISCOVER: {RunState.PLAN, RunState.ESCALATE},
    RunState.PLAN: {RunState.IMPLEMENT, RunState.ESCALATE},
    RunState.IMPLEMENT: {RunState.TEST, RunState.ESCALATE},
    RunState.TEST: {RunState.ANALYZE_FAILURE, RunState.REVIEW, RunState.VERIFY, RunState.ESCALATE},
    RunState.ANALYZE_FAILURE: {RunState.REPAIR, RunState.ESCALATE},
    RunState.REPAIR: {RunState.TEST, RunState.ESCALATE},
    RunState.REVIEW: {RunState.REPAIR, RunState.VERIFY, RunState.ESCALATE},
    RunState.VERIFY: {RunState.ANALYZE_FAILURE, RunState.COMPLETE, RunState.ESCALATE},
    RunState.COMPLETE: set(),
    RunState.ESCALATE: set(),
}


class Orchestrator:
    def __init__(
        self,
        config: HarnessConfig,
        provider: ModelProvider,
        store: RunStore | None = None,
        strategy: str = "full",
    ):
        if strategy not in {"simple", "context", "full"}:
            raise ValueError(f"unknown harness strategy: {strategy}")
        self.config = config
        self.provider = provider
        self.store = store or JsonRunStore(config.state_dir)
        self.strategy = strategy
        self._event_sequence = 0

    def run(self, repository: Path, task: str) -> RunRecord:
        repository = repository.resolve(strict=True)
        now = datetime.now(UTC)
        record = RunRecord(
            id=uuid.uuid4().hex[:12],
            task=task.strip(),
            repository=str(repository),
            state=RunState.DISCOVER,
            outcome=RunOutcome.RUNNING,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            deadline_at=(now + timedelta(seconds=self.config.budget.max_wall_seconds)).isoformat(),
            budget=self.config.budget,
        )
        self.store.save(record)
        self._event(record, "run.created", "Run accepted", {"task": record.task})
        try:
            return self._execute(record, repository)
        except Exception as error:
            return self._escalate(record, f"{type(error).__name__}: {error}")

    def _execute(self, record: RunRecord, repository: Path) -> RunRecord:
        mapper = RepositoryMapper(self.config.max_repository_files, self.config.max_file_bytes)
        index = mapper.map(repository)
        self._event(record, "repository.indexed", "Repository index built", index.to_dict())
        self._transition(record, RunState.PLAN, "Repository discovery complete")

        context_engine = ContextEngine(self.config.context_token_budget)
        context = context_engine.select(record.task if self.strategy != "simple" else "", index)
        self._event(
            record,
            "context.selected",
            "Exact planning context recorded",
            context.to_dict(),
        )
        response = self._model(
            record,
            "plan",
            {
                "task": record.task,
                "repository_summary": {
                    "languages": index.languages,
                    "manifests": index.manifests,
                    "dependencies": index.dependencies,
                    "tests": index.tests,
                    "recent_history": index.recent_history,
                },
                "context": context.to_dict(),
                "required_output": {
                    "summary": "string",
                    "steps": ["actionable step"],
                    "acceptance_checks": ["machine-checkable check"],
                    "likely_files": ["relative path"],
                },
            },
        )
        record.plan = self._parse_plan(response)
        self._event(record, "plan.created", record.plan.summary, asdict(record.plan))

        sandbox = DockerSandbox(repository, self.config.sandbox)
        tools = ControlledTools(repository, index, sandbox.run, self.config.max_file_bytes)
        reviewer = ReadOnlyReviewer(self.provider)
        verifier = Verifier(repository, self.config.verification, sandbox.run)
        failure_summary = ""
        target_state = RunState.IMPLEMENT

        while True:
            attempt_limit = record.budget.max_attempts if self.strategy == "full" else 1
            if record.usage.attempts >= attempt_limit:
                return self._escalate(record, "attempt budget exceeded")
            self._enforce_budgets(record)
            self._transition(record, target_state, f"Starting attempt {record.usage.attempts + 1}")
            record.usage.attempts += 1
            stage = "implement" if target_state == RunState.IMPLEMENT else "repair"

            refreshed_index = mapper.map(repository)
            tools.index = refreshed_index
            changed = tools.changed_files()
            context = context_engine.select(
                record.task if self.strategy != "simple" else "",
                refreshed_index,
                changed_paths=changed,
                previous_errors=[failure_summary] if failure_summary else [],
            )
            self._event(
                record,
                "context.refreshed",
                f"Exact {stage} context recorded",
                context.to_dict(),
            )
            decision = self._model(
                record,
                stage,
                {
                    "task": record.task,
                    "plan": asdict(record.plan),
                    "previous_failure": failure_summary,
                    "context": context.to_dict(),
                    "tool_policy": json.loads(tools.to_model_schema()),
                    "required_output": {
                        "summary": "concise action summary",
                        "tool_calls": [
                            {
                                "name": "one allowed tool",
                                "arguments": "object",
                                "rationale": "concise, observable rationale",
                            }
                        ],
                    },
                },
            )
            self._apply_decision(record, tools, decision)
            record.changed_files = tools.changed_files()
            patch = tools.get_git_diff()
            patch_hash = hashlib.sha256(patch.encode()).hexdigest()
            if not patch.strip():
                return self._escalate(record, "implementation produced no Git diff")
            if patch_hash in record.patch_fingerprints:
                duplicates = record.patch_fingerprints.count(patch_hash) + 1
                if duplicates > self.config.budget.max_stagnant_loops:
                    return self._escalate(record, "stagnation detected: duplicate patch repeated")
            record.patch_fingerprints.append(patch_hash)
            self._event(
                record,
                "implementation.changed",
                "Implementation tools completed",
                {"changed_files": record.changed_files, "patch_sha256": patch_hash},
            )

            self._transition(record, RunState.TEST, "Running sandbox checks")
            test_evidence = sandbox.run("test")
            record.evidence.append(test_evidence)
            self._event(record, "sandbox.result", test_evidence.summary, asdict(test_evidence))
            if not test_evidence.passed or test_evidence.metadata.get("skipped"):
                if self.strategy != "full":
                    return self._escalate(record, "initial test attempt failed")
                failure_summary = self._failure(record, [test_evidence])
                target_state = RunState.REPAIR
                continue

            if self.strategy == "full":
                self._transition(record, RunState.REVIEW, "Tests passed; reviewing diff")
                findings = reviewer.review(record.task, asdict(record.plan), patch)
                review_input_tokens, review_output_tokens = reviewer.last_usage
                record.usage.input_tokens += review_input_tokens
                record.usage.output_tokens += review_output_tokens
                self._event(
                    record,
                    "model.completed",
                    "Model completed review",
                    {
                        "stage": "review",
                        "input_tokens": review_input_tokens,
                        "output_tokens": review_output_tokens,
                    },
                )
                record.findings = findings
                self._event(
                    record,
                    "review.completed",
                    f"Reviewer produced {len(findings)} findings",
                    {"findings": [asdict(item) for item in findings]},
                )
                blocking = [item for item in findings if item.severity == "blocking"]
                if blocking:
                    failure_summary = "; ".join(item.message for item in blocking)
                    self._event(
                        record,
                        "failure.analyzed",
                        "Blocking review findings require repair",
                        {"failure": failure_summary},
                    )
                    target_state = RunState.REPAIR
                    continue

            self._transition(record, RunState.VERIFY, "Running independent acceptance checks")
            verified, evidence = verifier.verify(record.changed_files, record.findings)
            record.evidence.extend(evidence)
            self._event(
                record,
                "verification.completed",
                "All acceptance checks passed" if verified else "Acceptance checks failed",
                {"evidence": [asdict(item) for item in evidence]},
            )
            if not verified:
                if self.strategy != "full":
                    return self._escalate(record, "independent verification failed")
                failure_summary = self._failure(
                    record, [item for item in evidence if not item.passed]
                )
                target_state = RunState.REPAIR
                continue

            self._transition(
                record, RunState.COMPLETE, "Machine-verifiable exit conditions satisfied"
            )
            record.outcome = RunOutcome.VERIFIED_COMPLETE
            record.final_patch = tools.get_git_diff()
            record.pr_description = self._pr_description(record)
            self._event(
                record,
                "run.completed",
                "Run reached VERIFIED_COMPLETE",
                {"changed_files": record.changed_files},
            )
            self._save(record)
            return record

    def _apply_decision(
        self, record: RunRecord, tools: ControlledTools, decision: dict[str, Any]
    ) -> None:
        calls = decision.get("tool_calls", [])
        if not isinstance(calls, list) or not calls:
            raise ProviderError("implementation response must contain non-empty tool_calls")
        for raw in calls:
            self._enforce_budgets(record)
            if not isinstance(raw, dict) or not isinstance(raw.get("arguments", {}), dict):
                raise ProviderError("malformed tool call")
            request = ToolRequest(
                str(raw.get("name", "")),
                raw.get("arguments", {}),
                str(raw.get("rationale", ""))[:1_000],
            )
            result = tools.execute(request)
            record.usage.tool_calls += 1
            safe_result = self._summarize_tool_result(result)
            self._event(
                record,
                "tool.completed",
                f"{request.name}: {request.rationale}",
                {
                    "tool": request.name,
                    "arguments": self._safe_tool_arguments(raw.get("arguments", {})),
                    "result": safe_result,
                },
            )

    def _failure(self, record: RunRecord, evidence: list[Any]) -> str:
        summary = " | ".join(
            f"{item.kind}: {item.summary}\n{item.output[-4_000:]}" for item in evidence
        )
        fingerprint = hashlib.sha256(summary.encode()).hexdigest()
        record.failure_fingerprints.append(fingerprint)
        repeated = record.failure_fingerprints.count(fingerprint)
        self._transition(record, RunState.ANALYZE_FAILURE, "Analyzing failed evidence")
        self._event(
            record,
            "failure.analyzed",
            "Failure evidence normalized",
            {"fingerprint": fingerprint, "repeated": repeated, "summary": summary},
        )
        if repeated > self.config.budget.max_repeated_failures:
            raise ValueError("repeated failure threshold exceeded")
        record.usage.loops += 1
        return summary

    def _model(self, record: RunRecord, stage: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.provider.generate_json(stage, payload)
        record.usage.input_tokens += response.input_tokens
        record.usage.output_tokens += response.output_tokens
        self._event(
            record,
            "model.completed",
            f"Model completed {stage}",
            {
                "stage": stage,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
            },
        )
        self._enforce_budgets(record)
        return response.data

    @staticmethod
    def _parse_plan(data: dict[str, Any]) -> Plan:
        steps = data.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ProviderError("plan must contain at least one step")
        acceptance_checks = data.get("acceptance_checks", [])
        likely_files = data.get("likely_files", [])
        if not isinstance(acceptance_checks, list) or not isinstance(likely_files, list):
            raise ProviderError("plan list fields must be arrays")
        return Plan(
            str(data.get("summary", "Implementation plan"))[:2_000],
            [str(step)[:1_000] for step in steps[:50]],
            [str(item)[:1_000] for item in acceptance_checks[:50]],
            [str(item)[:500] for item in likely_files[:100]],
        )

    def _enforce_budgets(self, record: RunRecord) -> None:
        now = datetime.now(UTC)
        if now >= datetime.fromisoformat(record.deadline_at):
            raise ValueError("wall-clock budget exceeded")
        if record.usage.tool_calls >= record.budget.max_tool_calls:
            raise ValueError("tool-call budget exceeded")
        if record.usage.total_tokens > record.budget.max_tokens:
            raise ValueError("token budget exceeded")

    def _transition(self, record: RunRecord, target: RunState, message: str) -> None:
        current = RunState(record.state)
        if target not in TRANSITIONS[current]:
            raise ValueError(f"invalid state transition: {current} -> {target}")
        record.state = target
        self._event(
            record,
            "state.transition",
            message,
            {"from": current, "to": target, "what_changed": message, "what_next": target},
        )
        self._save(record)

    def _escalate(self, record: RunRecord, reason: str) -> RunRecord:
        if RunState(record.state) not in {RunState.COMPLETE, RunState.ESCALATE}:
            record.state = RunState.ESCALATE
        record.outcome = RunOutcome.ESCALATED
        record.escalation_reason = reason
        self._event(record, "run.escalated", reason, {"reason": reason})
        self._save(record)
        return record

    def _event(
        self, record: RunRecord, event_type: str, message: str, data: dict[str, Any]
    ) -> None:
        self._event_sequence += 1
        event = Event(
            self._event_sequence,
            datetime.now(UTC).isoformat(),
            str(record.state),
            event_type,
            message,
            data,
        )
        self.store.append_event(record.id, event)

    def _save(self, record: RunRecord) -> None:
        record.updated_at = datetime.now(UTC).isoformat()
        self.store.save(record)

    @staticmethod
    def _summarize_tool_result(result: Any) -> Any:
        if isinstance(result, str) and len(result) > 8_000:
            return result[:4_000] + "\n...[tool output truncated]...\n" + result[-4_000:]
        return result

    @staticmethod
    def _safe_tool_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
        safe = dict(arguments)
        for field in ("content", "replace"):
            value = safe.get(field)
            if isinstance(value, str):
                safe[field] = {
                    "bytes": len(value.encode()),
                    "sha256": hashlib.sha256(value.encode()).hexdigest(),
                }
        return safe

    @staticmethod
    def _pr_description(record: RunRecord) -> str:
        checks = [
            f"- {'PASS' if item.passed else 'FAIL'}: {item.kind} — {item.summary}"
            for item in record.evidence[-10:]
        ]
        return "\n".join(
            [
                f"## {record.plan.summary if record.plan else record.task}",
                "",
                "### Task",
                record.task,
                "",
                "### Changed files",
                *[f"- `{path}`" for path in record.changed_files],
                "",
                "### Verification evidence",
                *checks,
                "",
                f"Harness run: `{record.id}` ({record.outcome})",
            ]
        )
