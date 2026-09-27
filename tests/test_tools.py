import subprocess
from pathlib import Path

import pytest

from autonomousdev.repository import RepositoryMapper
from autonomousdev.tools import ControlledTools, PathPolicy, ToolPolicyError


def _git(repository: Path, *arguments: str) -> None:
    subprocess.run(["git", *arguments], cwd=repository, check=True, capture_output=True)


def test_path_policy_rejects_traversal_and_protected_files(tmp_path: Path) -> None:
    policy = PathPolicy(tmp_path)
    with pytest.raises(ToolPolicyError):
        policy.resolve("../secret")
    with pytest.raises(ToolPolicyError):
        policy.resolve(".env", write=True)
    with pytest.raises(ToolPolicyError):
        policy.resolve("/absolute", write=True)


def test_atomic_write_exact_patch_and_untracked_diff(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "app.py").write_text("answer = 41\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(
        tmp_path,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-qm",
        "base",
    )
    tools = ControlledTools(tmp_path, RepositoryMapper().map(tmp_path), lambda operation: None)

    tools.apply_patch("app.py", "41", "42")
    tools.write_file("new.py", "enabled = True\n")
    diff = tools.get_git_diff()

    assert "+answer = 42" in diff
    assert "b/new.py" in diff
    with pytest.raises(ToolPolicyError, match="exactly once"):
        tools.apply_patch("app.py", "missing", "x")
