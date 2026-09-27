import subprocess
from pathlib import Path

from autonomousdev.config import HarnessConfig
from autonomousdev.orchestrator import Orchestrator
from autonomousdev.providers import ScriptedProvider
from autonomousdev.types import Evidence, RunOutcome


class FakeSandbox:
    def __init__(self, root, config):
        self.root = root

    def run(self, operation: str) -> Evidence:
        return Evidence(
            operation, True, f"{operation} passed", exit_code=0, metadata={"sandbox": "fake"}
        )


def test_vertical_slice_reaches_verified_complete(tmp_path: Path, monkeypatch) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "solution.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "base",
        ],
        cwd=repository,
        check=True,
    )
    monkeypatch.setattr("autonomousdev.orchestrator.DockerSandbox", FakeSandbox)
    provider = ScriptedProvider(
        [
            {
                "summary": "Fix answer",
                "steps": ["Update return value"],
                "acceptance_checks": ["tests pass"],
            },
            {
                "summary": "Corrected value",
                "tool_calls": [
                    {
                        "name": "apply_patch",
                        "arguments": {"path": "solution.py", "search": "41", "replace": "42"},
                        "rationale": "Correct the off-by-one value",
                    }
                ],
            },
            {"findings": []},
        ]
    )
    config = HarnessConfig(state_dir=tmp_path / "state")

    record = Orchestrator(config, provider).run(repository, "return the correct answer")

    assert record.outcome == RunOutcome.VERIFIED_COMPLETE
    assert record.state == "COMPLETE"
    assert record.changed_files == ["solution.py"]
    assert "+    return 42" in record.final_patch
    assert "Verification evidence" in record.pr_description
