from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .config import SandboxConfig
from .types import Evidence


class SandboxUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CommandProfile:
    ecosystem: str
    image: str
    operations: dict[str, tuple[str, ...]]


class DockerSandbox:
    """Runs only named, administrator-defined commands in a constrained container."""

    def __init__(self, root: Path, config: SandboxConfig):
        self.root = root.resolve(strict=True)
        self.config = config
        self.profile = self._detect_profile()

    def run(self, operation: str) -> Evidence:
        if operation not in {"test", "lint", "build"}:
            raise ValueError(f"unsupported sandbox operation: {operation}")
        if operation not in self.profile.operations:
            return Evidence(
                operation,
                True,
                f"{operation} not configured; check not required",
                metadata={"skipped": True},
            )
        if shutil.which(self.config.docker_binary) is None:
            raise SandboxUnavailable(
                "Docker is required; generated code was not executed on the host"
            )
        command = self.profile.operations[operation]
        volume_source = self._volume_source()
        container_name = f"adev-{uuid.uuid4().hex[:12]}"
        argv = [
            self.config.docker_binary,
            "run",
            "--rm",
            "--name",
            container_name,
            "--network",
            self.config.network,
            "--cpus",
            str(self.config.cpu_limit),
            "--memory",
            self.config.memory,
            "--pids-limit",
            str(self.config.pids_limit),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=128m,mode=1777",  # noqa: S108 -- container tmpfs
            "--tmpfs",
            "/workspace:rw,exec,nosuid,size=512m,mode=1777",
            "--user",
            "65534:65534",
            "--env",
            "HOME=/tmp",
            "--env",
            "CI=1",
            "--volume",
            f"{volume_source}:/input:ro",
            "--workdir",
            "/workspace",
            self.profile.image,
            "sh",
            "-c",
            'cp -R /input/. /workspace && exec "$@"',
            "adev-sandbox",
            *command,
        ]
        started = time.monotonic()
        captured = bytearray()
        truncated = False

        def drain(stream) -> None:
            nonlocal truncated
            while chunk := stream.read(8192):
                remaining = self.config.output_limit_bytes - len(captured)
                if remaining > 0:
                    captured.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    truncated = True

        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env={"PATH": os.environ.get("PATH", "")},
            )
            if process.stdout is None:
                raise SandboxUnavailable("Docker output pipe was not created")
            reader = threading.Thread(target=drain, args=(process.stdout,), daemon=True)
            reader.start()
            return_code = process.wait(timeout=self.config.timeout_seconds)
            reader.join(timeout=5)
            decoded = captured.decode("utf-8", errors="replace")
            return Evidence(
                kind=operation,
                passed=return_code == 0,
                summary=f"{operation} exited with {return_code}",
                command=list(command),
                exit_code=return_code,
                duration_ms=int((time.monotonic() - started) * 1000),
                output=decoded,
                metadata={
                    "sandbox": "docker",
                    "image": self.profile.image,
                    "network": self.config.network,
                    "filesystem": "read-only-input-copy-on-tmpfs",
                    "output_truncated": truncated,
                },
            )
        except subprocess.TimeoutExpired:
            subprocess.run(
                [self.config.docker_binary, "rm", "-f", container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
                env={"PATH": os.environ.get("PATH", "")},
            )
            if process is not None:
                process.kill()
                process.wait(timeout=5)
            return Evidence(
                kind=operation,
                passed=False,
                summary=f"{operation} timed out after {self.config.timeout_seconds}s",
                command=list(command),
                duration_ms=int((time.monotonic() - started) * 1000),
                output=captured.decode("utf-8", errors="replace"),
                metadata={"sandbox": "docker", "timeout": True, "output_truncated": truncated},
            )

    def _detect_profile(self) -> CommandProfile:
        images = self.config.images
        if (self.root / "pyproject.toml").exists():
            return CommandProfile(
                "python",
                images["python"],
                {
                    "test": ("python", "-m", "pytest", "-q"),
                    "lint": ("python", "-m", "ruff", "check", "."),
                    "build": ("python", "-m", "build", "--no-isolation"),
                },
            )
        if (self.root / "package.json").exists():
            return CommandProfile(
                "node",
                images["node"],
                {
                    "test": ("npm", "test", "--", "--runInBand"),
                    "lint": ("npm", "run", "lint"),
                    "build": ("npm", "run", "build"),
                },
            )
        if list(self.root.glob("test*.py")) or (self.root / "tests").exists():
            return CommandProfile(
                "python",
                images["python"],
                {"test": ("python", "-m", "unittest", "discover", "-v")},
            )
        return CommandProfile("unknown", images["python"], {})

    def _volume_source(self) -> Path:
        container_root = self.config.container_repository_root
        host_root = self.config.host_repository_root
        if not container_root and not host_root:
            return self.root
        if not container_root or not host_root:
            raise SandboxUnavailable(
                "both container_repository_root and host_repository_root are required for sibling Docker"
            )
        try:
            relative = self.root.relative_to(Path(container_root).resolve())
        except ValueError as error:
            raise SandboxUnavailable(
                "repository is outside the configured container repository root"
            ) from error
        host_root_path = Path(host_root)
        if not host_root_path.is_absolute():
            raise SandboxUnavailable("host repository root must be absolute")
        source = (host_root_path / relative).resolve()
        return source
