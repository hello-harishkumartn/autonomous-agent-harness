from __future__ import annotations

import difflib
import fnmatch
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .repository import RepositoryIndex
from .types import ToolRequest


class ToolPolicyError(RuntimeError):
    pass


class PathPolicy:
    def __init__(self, root: Path, protected_globs: list[str] | None = None):
        self.root = root.resolve(strict=True)
        self.protected_globs = protected_globs or [
            ".git",
            ".git/**",
            ".adev-data",
            ".adev-data/**",
            ".env",
            ".env.*",
            "*.pem",
            "**/*.pem",
            "*.key",
            "**/*.key",
        ]

    def resolve(self, relative: str, *, write: bool = False) -> Path:
        candidate_input = Path(relative)
        if candidate_input.is_absolute() or ".." in candidate_input.parts:
            raise ToolPolicyError(f"path traversal rejected: {relative}")
        normalized = candidate_input.as_posix()
        while normalized.startswith("./"):
            normalized = normalized[2:]
        if not normalized:
            raise ToolPolicyError("empty path rejected")
        if write and any(fnmatch.fnmatch(normalized, pattern) for pattern in self.protected_globs):
            raise ToolPolicyError(f"protected path rejected: {normalized}")
        lexical = self.root / candidate_input
        candidate = lexical.resolve(strict=False)
        try:
            candidate.relative_to(self.root)
        except ValueError as error:
            raise ToolPolicyError(f"path escapes repository: {relative}") from error
        current = lexical
        while current != self.root:
            if current.exists() and current.is_symlink():
                raise ToolPolicyError(f"symlink path rejected: {relative}")
            if current.parent == current:
                raise ToolPolicyError(f"path does not descend from repository: {relative}")
            current = current.parent
        return candidate


class ControlledTools:
    """Typed model-facing capabilities. There is deliberately no shell method."""

    def __init__(
        self,
        root: Path,
        index: RepositoryIndex,
        sandbox_runner: Callable[[str], Any],
        max_read_bytes: int = 300_000,
    ):
        self.root = root.resolve(strict=True)
        self.index = index
        self.paths = PathPolicy(self.root)
        self.sandbox_runner = sandbox_runner
        self.max_read_bytes = max_read_bytes
        self.last_failure: dict[str, Any] | None = None
        self._dispatch: dict[str, Callable[..., Any]] = {
            "list_files": self.list_files,
            "read_file": self.read_file,
            "search_code": self.search_code,
            "find_symbol": self.find_symbol,
            "write_file": self.write_file,
            "apply_patch": self.apply_patch,
            "run_tests": lambda: self._run("test"),
            "run_linter": lambda: self._run("lint"),
            "run_build": lambda: self._run("build"),
            "get_git_diff": self.get_git_diff,
            "get_test_failure": self.get_test_failure,
            "inspect_dependency": self.inspect_dependency,
        }

    @property
    def names(self) -> list[str]:
        return sorted(self._dispatch)

    def execute(self, request: ToolRequest) -> Any:
        if request.name not in self._dispatch:
            raise ToolPolicyError(f"unknown tool: {request.name}")
        try:
            return self._dispatch[request.name](**request.arguments)
        except TypeError as error:
            raise ToolPolicyError(f"invalid arguments for {request.name}: {error}") from error

    def list_files(self, glob: str = "**", limit: int = 500) -> list[str]:
        safe_limit = min(max(limit, 1), 2_000)
        return [entry.path for entry in self.index.files if fnmatch.fnmatch(entry.path, glob)][
            :safe_limit
        ]

    def read_file(self, path: str, start_line: int = 1, end_line: int | None = None) -> str:
        target = self.paths.resolve(path)
        if not target.is_file():
            raise ToolPolicyError(f"file not found: {path}")
        if target.stat().st_size > self.max_read_bytes:
            raise ToolPolicyError(f"file exceeds read limit: {path}")
        content = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, start_line)
        end = min(len(content), end_line or len(content))
        if end < start:
            return ""
        return "\n".join(content[start - 1 : end])

    def search_code(self, query: str, glob: str = "**", limit: int = 100) -> list[dict[str, Any]]:
        if not query or len(query) > 500:
            raise ToolPolicyError("query must contain 1-500 characters")
        matcher = re.compile(re.escape(query), re.IGNORECASE)
        matches: list[dict[str, Any]] = []
        for path in self.list_files(glob, 2_000):
            try:
                text = self.read_file(path)
            except (ToolPolicyError, UnicodeError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if matcher.search(line):
                    matches.append({"path": path, "line": number, "text": line[:500]})
                    if len(matches) >= min(limit, 500):
                        return matches
        return matches

    def find_symbol(self, name: str) -> list[dict[str, Any]]:
        lowered = name.lower()
        return [
            {
                "path": entry.path,
                "symbols": [symbol for symbol in entry.symbols if lowered in symbol.lower()],
            }
            for entry in self.index.files
            if any(lowered in symbol.lower() for symbol in entry.symbols)
        ]

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        target = self.paths.resolve(path, write=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = content.encode("utf-8")
        if len(encoded) > self.max_read_bytes:
            raise ToolPolicyError(f"write exceeds {self.max_read_bytes} byte limit: {path}")
        existing_mode = target.stat().st_mode if target.exists() else None
        fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            if existing_mode is not None:
                os.chmod(temporary, existing_mode)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {"path": path, "bytes": len(encoded)}

    def apply_patch(self, path: str, search: str, replace: str) -> dict[str, Any]:
        """Apply one exact replacement; ambiguity is a policy error."""
        if not search:
            raise ToolPolicyError("empty patch search rejected; use write_file for new files")
        target = self.paths.resolve(path, write=True)
        if not target.is_file() or target.stat().st_size > self.max_read_bytes:
            raise ToolPolicyError(f"file unavailable for patch: {path}")
        original = target.read_text(encoding="utf-8", errors="replace")
        occurrences = original.count(search)
        if occurrences != 1:
            raise ToolPolicyError(f"patch search must match exactly once; found {occurrences}")
        updated = original.replace(search, replace, 1)
        result = self.write_file(path, updated)
        result["replaced_characters"] = len(search)
        return result

    def get_git_diff(self) -> str:
        result = self._git(["diff", "--no-ext-diff", "--binary", "--", "."], timeout=20)
        patch = result.stdout
        status = self._git(["status", "--porcelain=v1", "-z", "--untracked-files=all"], timeout=10)
        for chunk in status.stdout.split("\0"):
            if not chunk or not chunk.startswith("?? "):
                continue
            relative = chunk[3:].replace("\\", "/")
            target = self.paths.resolve(relative)
            if not target.is_file() or target.stat().st_size > self.max_read_bytes:
                continue
            raw = target.read_bytes()
            if b"\x00" in raw:
                patch += f"\ndiff --git a/{relative} b/{relative}\nnew binary file\n"
                continue
            content = raw.decode("utf-8", errors="replace").splitlines(keepends=True)
            patch += f"diff --git a/{relative} b/{relative}\nnew file mode 100644\n"
            patch += "".join(
                difflib.unified_diff(
                    [], content, fromfile=f"a/{relative}", tofile=f"b/{relative}", lineterm="\n"
                )
            )
        if len(patch.encode()) > 2_000_000:
            raise ToolPolicyError("Git diff exceeds 2 MB policy limit")
        return patch

    def changed_files(self) -> list[str]:
        result = self._git(["status", "--porcelain=v1", "-z", "--untracked-files=all"], timeout=10)
        paths: list[str] = []
        chunks = result.stdout.split("\0")
        index = 0
        while index < len(chunks):
            chunk = chunks[index]
            if not chunk:
                break
            status, path = chunk[:2], chunk[3:]
            if status[0] in {"R", "C"}:
                index += 1
                if index < len(chunks):
                    path = chunks[index]
            paths.append(path.replace("\\", "/"))
            index += 1
        return sorted(set(paths))

    def get_test_failure(self) -> dict[str, Any] | None:
        return self.last_failure

    def inspect_dependency(self, name: str) -> list[dict[str, str]]:
        if not name or len(name) > 200:
            raise ToolPolicyError("invalid dependency name")
        results: list[dict[str, str]] = []
        for manifest in self.index.manifests:
            text = self.read_file(manifest)
            for number, line in enumerate(text.splitlines(), 1):
                if name.lower() in line.lower():
                    results.append(
                        {"path": manifest, "line": str(number), "declaration": line[:500]}
                    )
        return results

    def _run(self, operation: str) -> Any:
        result = self.sandbox_runner(operation)
        data = asdict(result) if hasattr(result, "__dataclass_fields__") else result
        if not data.get("passed", False):
            self.last_failure = data
        return data

    def _git(self, arguments: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), *arguments],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env={"PATH": os.environ.get("PATH", ""), "GIT_CONFIG_NOSYSTEM": "1"},
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ToolPolicyError(f"fixed git operation failed: {error}") from error
        if result.returncode not in {0, 1}:
            raise ToolPolicyError(result.stderr.strip() or "git operation failed")
        return result

    def to_model_schema(self) -> str:
        return json.dumps({"allowed_tools": self.names, "shell_available": False})
