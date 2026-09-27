from __future__ import annotations

import importlib.util
import json
import os
import shutil
import statistics
import subprocess
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from .config import HarnessConfig
from .factory import create_provider
from .orchestrator import Orchestrator
from .sandbox import DockerSandbox
from .store import JsonRunStore


def _load_materializer(dataset: Path) -> ModuleType:
    script = dataset.parent / "materialize.py"
    if not script.is_file():
        raise FileNotFoundError(f"benchmark materializer not found: {script}")
    spec = importlib.util.spec_from_file_location("adev_benchmark_materialize", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load benchmark materializer")
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.path.insert(0, str(dataset.parent))
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def evaluate_dataset(
    dataset: Path,
    output: Path,
    *,
    configurations: list[str],
    limit: int | None = None,
) -> dict[str, Any]:
    dataset = dataset.resolve(strict=True)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(dataset.read_text(encoding="utf-8"))
    tasks = manifest["tasks"][:limit]
    materializer = _load_materializer(dataset)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    try:
        dataset_label = dataset.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        dataset_label = str(dataset)
    report: dict[str, Any] = {
        "schema_version": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "dataset": dataset_label,
        "dataset_schema_version": manifest.get("schema_version"),
        "configurations": configurations,
        "environment": {
            "provider": os.getenv("ADEV_EVAL_PROVIDER"),
            "model": os.getenv("ADEV_EVAL_MODEL"),
            "docker_available": shutil.which("docker") is not None,
        },
        "results": [],
        "status": "running",
    }

    provider_name = os.getenv("ADEV_EVAL_PROVIDER")
    if shutil.which("docker") is None or not provider_name:
        reasons = []
        if shutil.which("docker") is None:
            reasons.append("Docker executable not found")
        if not provider_name:
            reasons.append("ADEV_EVAL_PROVIDER is not set")
        report.update(
            {
                "status": "not_run",
                "reason": "; ".join(reasons),
                "tasks_attempted": 0,
                "note": "No benchmark outcome metrics were generated.",
            }
        )
        _write_report(output / f"evaluation-{timestamp}.json", report)
        return report

    provider = create_provider(
        provider_name,
        model=os.getenv("ADEV_EVAL_MODEL"),
        base_url=os.getenv("ADEV_EVAL_BASE_URL"),
    )
    report["environment"]["resolved_model"] = getattr(provider, "model", None)
    report["environment"]["sandbox_images"] = HarnessConfig(
        state_dir=output / "state"
    ).sandbox.images
    for configuration in configurations:
        for task in tasks:
            started = time.monotonic()
            with tempfile.TemporaryDirectory(prefix=f"adev-{task['id']}-") as temporary:
                repository = Path(temporary) / "repository"
                materializer.materialize(task["id"], repository)
                _initialize_git(repository)
                state_dir = output / "state" / timestamp / configuration / task["id"]
                config = HarnessConfig(state_dir=state_dir)
                config.verification.require_tests = True
                run = Orchestrator(
                    config,
                    provider,
                    JsonRunStore(state_dir),
                    strategy=configuration,
                ).run(repository, task["task"])
                patch = run.final_patch
                materializer.add_hidden(task["id"], repository)
                try:
                    hidden = DockerSandbox(repository, config.sandbox).run("test")
                    hidden_passed = hidden.passed
                    hidden_summary = hidden.summary
                    hidden_output = hidden.output[-8_000:]
                except (
                    Exception
                ) as error:  # benchmark continues and records infrastructure failures
                    hidden_passed = False
                    hidden_summary = f"{type(error).__name__}: {error}"
                    hidden_output = ""
                success = run.outcome == "VERIFIED_COMPLETE" and hidden_passed
                report["results"].append(
                    {
                        "task_id": task["id"],
                        "category": task["category"],
                        "configuration": configuration,
                        "success": success,
                        "harness_outcome": run.outcome,
                        "attempts": run.usage.attempts,
                        "loops": run.usage.loops,
                        "tool_calls": run.usage.tool_calls,
                        "tokens": run.usage.total_tokens,
                        "latency_seconds": round(time.monotonic() - started, 3),
                        "hidden_tests_passed": hidden_passed,
                        "hidden_test_summary": hidden_summary,
                        "hidden_test_output": hidden_output,
                        "failure_category": _failure_category(
                            run.outcome, hidden_passed, run.escalation_reason
                        ),
                        "escalation_reason": run.escalation_reason,
                        "patch": patch,
                    }
                )
            _write_report(output / f"evaluation-{timestamp}.partial.json", report)

    report["status"] = "complete"
    report["completed_at"] = datetime.now(UTC).isoformat()
    report["summary"] = _summarize(report["results"], configurations)
    final_path = output / f"evaluation-{timestamp}.json"
    _write_report(final_path, report)
    partial = output / f"evaluation-{timestamp}.partial.json"
    if partial.exists():
        partial.unlink()
    return report


def _initialize_git(repository: Path) -> None:
    commands = [
        ["git", "init", "-q"],
        ["git", "config", "user.email", "benchmark@local.invalid"],
        ["git", "config", "user.name", "AutonomousDev Benchmark"],
        ["git", "add", "."],
        ["git", "commit", "-q", "-m", "benchmark baseline"],
    ]
    for command in commands:
        subprocess.run(command, cwd=repository, check=True, capture_output=True, timeout=20)


def _failure_category(outcome: str, hidden_passed: bool, reason: str | None) -> str | None:
    if outcome != "VERIFIED_COMPLETE":
        if reason and "budget" in reason:
            return "budget_exhausted"
        if reason and "Docker" in reason:
            return "infrastructure"
        if reason and "Provider" in reason:
            return "provider"
        return "harness_escalated"
    if not hidden_passed:
        return "hidden_acceptance_failure"
    return None


def _summarize(results: list[dict[str, Any]], configurations: list[str]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for configuration in configurations:
        rows = [row for row in results if row["configuration"] == configuration]
        successes = [row for row in rows if row["success"]]
        first_pass = [row for row in successes if row["attempts"] == 1]
        summary[configuration] = {
            "tasks_attempted": len(rows),
            "tasks_successfully_completed": len(successes),
            "pass_at_1": len(first_pass) / len(rows) if rows else 0.0,
            "eventual_completion_rate": len(successes) / len(rows) if rows else 0.0,
            "average_loops": _mean(rows, "loops"),
            "average_tool_calls": _mean(rows, "tool_calls"),
            "average_token_usage": _mean(rows, "tokens"),
            "average_latency_seconds": _mean(rows, "latency_seconds"),
            "failure_categories": dict(
                Counter(row["failure_category"] for row in rows if row["failure_category"])
            ),
        }
    return summary


def _mean(rows: list[dict[str, Any]], field: str) -> float:
    return round(statistics.fmean(row[field] for row in rows), 3) if rows else 0.0


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
