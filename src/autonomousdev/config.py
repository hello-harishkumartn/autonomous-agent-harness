from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .types import Budget


@dataclass(slots=True)
class SandboxConfig:
    docker_binary: str = "docker"
    cpu_limit: float = 1.0
    memory: str = "1g"
    pids_limit: int = 128
    timeout_seconds: int = 300
    output_limit_bytes: int = 200_000
    network: str = "none"
    container_repository_root: str | None = None
    host_repository_root: str | None = None
    images: dict[str, str] = field(
        default_factory=lambda: {
            "python": "autonomousdev-python-sandbox:0.1",
            "node": "autonomousdev-node-sandbox:0.1",
        }
    )


@dataclass(slots=True)
class VerificationConfig:
    require_tests: bool = True
    require_lint: bool = False
    require_build: bool = False
    required_files: list[str] = field(default_factory=list)
    allowed_change_globs: list[str] = field(default_factory=lambda: ["**"])
    forbidden_change_globs: list[str] = field(
        default_factory=lambda: [
            ".git/**",
            ".git",
            ".adev-data",
            ".adev-data/**",
            ".env",
            ".env.*",
            "*.pem",
            "**/*.pem",
            "*.key",
            "**/*.key",
        ]
    )


@dataclass(slots=True)
class HarnessConfig:
    state_dir: Path
    context_token_budget: int = 12_000
    max_file_bytes: int = 300_000
    max_repository_files: int = 20_000
    budget: Budget = field(default_factory=Budget)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    verification: VerificationConfig = field(default_factory=VerificationConfig)

    @classmethod
    def from_environment(cls) -> HarnessConfig:
        state_dir = Path(os.getenv("ADEV_STATE_DIR", ".adev-data")).expanduser().resolve()
        config = cls(state_dir=state_dir)
        config.sandbox.container_repository_root = os.getenv("ADEV_CONTAINER_REPOSITORY_ROOT")
        config.sandbox.host_repository_root = os.getenv("ADEV_HOST_REPOSITORY_ROOT")
        return config
