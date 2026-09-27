from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, ClassVar

LANGUAGES = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C/C++",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
}
IGNORED_DIRS = {
    ".git",
    ".adev-data",
    "node_modules",
    ".next",
    "dist",
    "build",
    "target",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
}
MANIFESTS = {
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "Gemfile",
}


@dataclass(slots=True)
class FileEntry:
    path: str
    size: int
    sha256: str
    language: str
    role: str
    symbols: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RepositoryIndex:
    root: str
    files: list[FileEntry]
    languages: dict[str, int]
    manifests: list[str]
    dependencies: dict[str, list[str]]
    tests: list[str]
    configuration: list[str]
    recent_history: list[str]
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "file_count": len(self.files),
        }


class RepositoryMapper:
    _symbol_patterns: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)", re.MULTILINE),
        re.compile(
            r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|type)\s+([A-Za-z_$][\w$]*)",
            re.MULTILINE,
        ),
        re.compile(r"^\s*(?:pub\s+)?(?:fn|struct|enum|trait)\s+([A-Za-z_]\w*)", re.MULTILINE),
    ]
    _import_patterns: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.MULTILINE),
        re.compile(r"(?:from\s+|require\()[\"']([^\"']+)", re.MULTILINE),
    ]

    def __init__(self, max_files: int = 20_000, max_file_bytes: int = 300_000):
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes

    def map(self, root: Path) -> RepositoryIndex:
        root = root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError(f"repository is not a directory: {root}")
        files: list[FileEntry] = []
        languages: dict[str, int] = {}
        manifests: list[str] = []
        dependencies: dict[str, list[str]] = {}
        tests: list[str] = []
        configuration: list[str] = []
        truncated = False

        for current, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = sorted(name for name in dirnames if name not in IGNORED_DIRS)
            for name in sorted(filenames):
                if len(files) >= self.max_files:
                    truncated = True
                    break
                absolute = Path(current) / name
                if absolute.is_symlink() or not absolute.is_file():
                    continue
                relative = absolute.relative_to(root).as_posix()
                size = absolute.stat().st_size
                language = LANGUAGES.get(absolute.suffix.lower(), "Other")
                role = self._role(relative)
                content = b""
                text = ""
                if size <= self.max_file_bytes:
                    content = absolute.read_bytes()
                    if b"\x00" not in content:
                        text = content.decode("utf-8", errors="replace")
                digest = hashlib.sha256(
                    content if content else f"{size}:{relative}".encode()
                ).hexdigest()
                symbols = self._symbols(text)
                imports = self._imports(text)
                files.append(FileEntry(relative, size, digest, language, role, symbols, imports))
                languages[language] = languages.get(language, 0) + 1
                if name in MANIFESTS:
                    manifests.append(relative)
                    dependencies[relative] = self._dependencies(name, text)
                if role == "test":
                    tests.append(relative)
                if role == "config":
                    configuration.append(relative)
            if truncated:
                break
        return RepositoryIndex(
            root=str(root),
            files=files,
            languages=dict(sorted(languages.items())),
            manifests=manifests,
            dependencies=dependencies,
            tests=tests,
            configuration=configuration,
            recent_history=self._history(root),
            truncated=truncated,
        )

    @staticmethod
    def _role(path: str) -> str:
        lowered = path.lower()
        name = Path(path).name.lower()
        if "test" in name or "/tests/" in f"/{lowered}/" or "/spec/" in f"/{lowered}/":
            return "test"
        if (
            name in MANIFESTS
            or "config" in name
            or name.startswith(".")
            or Path(path).suffix.lower() in {".toml", ".yaml", ".yml", ".ini"}
        ):
            return "config"
        if Path(path).suffix.lower() in {".md", ".rst"}:
            return "documentation"
        return "source"

    def _symbols(self, text: str) -> list[str]:
        found: list[str] = []
        for pattern in self._symbol_patterns:
            found.extend(match.group(1) for match in pattern.finditer(text))
        return list(dict.fromkeys(found))[:200]

    def _imports(self, text: str) -> list[str]:
        found: list[str] = []
        for pattern in self._import_patterns:
            for match in pattern.finditer(text):
                found.append(next(group for group in match.groups() if group))
        return list(dict.fromkeys(found))[:200]

    @staticmethod
    def _dependencies(name: str, text: str) -> list[str]:
        try:
            if name == "package.json":
                package = json.loads(text)
                groups = (
                    "dependencies",
                    "devDependencies",
                    "peerDependencies",
                    "optionalDependencies",
                )
                return sorted({key for group in groups for key in package.get(group, {})})[:1_000]
            if name == "requirements.txt":
                return [
                    match.group(1)
                    for line in text.splitlines()
                    if (match := re.match(r"\s*([A-Za-z0-9_.-]+)", line))
                    and not line.lstrip().startswith(("#", "-"))
                ][:1_000]
            if name in {"pyproject.toml", "Cargo.toml"}:
                document = tomllib.loads(text)
                found: set[str] = set()
                project = document.get("project", {})
                for item in project.get("dependencies", []):
                    if match := re.match(r"([A-Za-z0-9_.-]+)", item):
                        found.add(match.group(1))
                for values in project.get("optional-dependencies", {}).values():
                    for item in values:
                        if match := re.match(r"([A-Za-z0-9_.-]+)", item):
                            found.add(match.group(1))
                found.update(document.get("dependencies", {}).keys())
                found.update(document.get("dev-dependencies", {}).keys())
                return sorted(found)[:1_000]
            if name == "go.mod":
                return list(
                    dict.fromkeys(
                        match.group(1)
                        for match in re.finditer(
                            r"^\s*(?:require\s+)?([\w.-]+/[\w./-]+)\s+v", text, re.MULTILINE
                        )
                    )
                )[:1_000]
            if name == "pom.xml":
                return list(dict.fromkeys(re.findall(r"<artifactId>([^<]+)</artifactId>", text)))[
                    :1_000
                ]
            if name == "Gemfile":
                return list(
                    dict.fromkeys(re.findall(r"^\s*gem\s+['\"]([^'\"]+)", text, re.MULTILINE))
                )[:1_000]
            if name == "build.gradle":
                return list(
                    dict.fromkeys(
                        re.findall(
                            r"(?:implementation|api|testImplementation)\s*\(?['\"]([^:'\"]+:[^:'\"]+)",
                            text,
                        )
                    )
                )[:1_000]
        except (json.JSONDecodeError, tomllib.TOMLDecodeError, AttributeError, TypeError):
            return []
        return []

    @staticmethod
    def _history(root: Path) -> list[str]:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "log", "-20", "--pretty=format:%h%x09%s"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                env={"PATH": os.environ.get("PATH", "")},
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        return result.stdout.splitlines() if result.returncode == 0 else []
