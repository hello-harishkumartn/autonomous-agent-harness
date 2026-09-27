from pathlib import Path

import pytest

from autonomousdev.config import SandboxConfig
from autonomousdev.sandbox import DockerSandbox, SandboxUnavailable


def test_missing_docker_fails_closed_without_host_fallback(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    sandbox = DockerSandbox(tmp_path, SandboxConfig())
    monkeypatch.setattr("autonomousdev.sandbox.shutil.which", lambda executable: None)

    with pytest.raises(SandboxUnavailable, match="not executed on the host"):
        sandbox.run("test")
