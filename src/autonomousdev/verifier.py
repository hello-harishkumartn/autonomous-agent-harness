from __future__ import annotations

import fnmatch
from pathlib import Path

from .config import VerificationConfig
from .types import Evidence, ReviewFinding


class Verifier:
    """Independent machine checks; no implementation rationale is accepted as evidence."""

    def __init__(self, root: Path, config: VerificationConfig, sandbox_runner):
        self.root = root.resolve(strict=True)
        self.config = config
        self.sandbox_runner = sandbox_runner

    def verify(
        self, changed_files: list[str], findings: list[ReviewFinding]
    ) -> tuple[bool, list[Evidence]]:
        evidence: list[Evidence] = []
        evidence.append(self._verify_paths(changed_files))
        evidence.append(self._verify_required_files())
        evidence.append(
            Evidence(
                "review",
                not any(finding.severity == "blocking" for finding in findings),
                "no blocking reviewer findings"
                if not any(finding.severity == "blocking" for finding in findings)
                else "blocking reviewer findings remain",
            )
        )
        requested = [
            ("test", self.config.require_tests),
            ("lint", self.config.require_lint),
            ("build", self.config.require_build),
        ]
        for operation, required in requested:
            if not required:
                continue
            result = self.sandbox_runner(operation)
            if result.metadata.get("skipped"):
                result.passed = False
                result.summary = f"required {operation} check has no configured command"
            result.metadata["verification_run"] = True
            evidence.append(result)
        return all(item.passed for item in evidence), evidence

    def _verify_paths(self, changed_files: list[str]) -> Evidence:
        unauthorized = []
        for path in changed_files:
            allowed = any(
                fnmatch.fnmatch(path, pattern) for pattern in self.config.allowed_change_globs
            )
            forbidden = any(
                fnmatch.fnmatch(path, pattern) for pattern in self.config.forbidden_change_globs
            )
            if not allowed or forbidden:
                unauthorized.append(path)
        return Evidence(
            "authorized_changes",
            not unauthorized,
            "all changed paths are authorized"
            if not unauthorized
            else "unauthorized paths changed",
            metadata={"changed_files": changed_files, "unauthorized": unauthorized},
        )

    def _verify_required_files(self) -> Evidence:
        missing = []
        for relative in self.config.required_files:
            candidate = (self.root / relative).resolve(strict=False)
            try:
                candidate.relative_to(self.root)
            except ValueError:
                missing.append(relative)
                continue
            if not candidate.is_file():
                missing.append(relative)
        return Evidence(
            "required_files",
            not missing,
            "all required files exist" if not missing else "required files are missing",
            metadata={"required": self.config.required_files, "missing": missing},
        )
