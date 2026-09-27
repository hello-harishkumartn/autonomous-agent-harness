from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class GitHubIntegrationError(RuntimeError):
    pass


@dataclass(slots=True)
class GitHubConfig:
    token: str | None = None
    api_url: str = "https://api.github.com"
    allowed_clone_hosts: tuple[str, ...] = ("github.com",)


class GitHubAdapter:
    """Optional ingress/egress adapter; core local operation never imports it."""

    def __init__(self, config: GitHubConfig | None = None):
        self.config = config or GitHubConfig(token=os.getenv("GITHUB_TOKEN"))
        if urllib.parse.urlparse(self.config.api_url).scheme != "https":
            raise GitHubIntegrationError("GitHub API URL must use HTTPS")

    def read_issue(self, owner: str, repository: str, number: int) -> dict[str, Any]:
        slug = self._slug(owner, repository)
        if number < 1:
            raise GitHubIntegrationError("issue number must be positive")
        request = urllib.request.Request(  # noqa: S310 -- HTTPS enforced in constructor
            f"{self.config.api_url}/repos/{slug}/issues/{number}",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                data = json.loads(response.read(2_000_000).decode())
        except (urllib.error.URLError, json.JSONDecodeError) as error:
            raise GitHubIntegrationError(f"issue request failed: {error}") from error
        return {
            "number": data["number"],
            "title": data["title"],
            "body": data.get("body") or "",
            "html_url": data["html_url"],
            "labels": [label["name"] for label in data.get("labels", [])],
        }

    def clone(self, url: str, destination: Path) -> Path:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in self.config.allowed_clone_hosts:
            raise GitHubIntegrationError(
                "only HTTPS URLs from configured GitHub hosts may be cloned"
            )
        destination = destination.resolve(strict=False)
        if destination.exists():
            raise GitHubIntegrationError("clone destination already exists")
        result = subprocess.run(
            ["git", "clone", "--no-tags", "--", url, str(destination)],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
            env={"PATH": os.environ.get("PATH", ""), "GIT_TERMINAL_PROMPT": "0"},
        )
        if result.returncode != 0:
            raise GitHubIntegrationError(result.stderr[-2_000:] or "git clone failed")
        return destination

    def create_branch(self, repository: Path, branch: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", branch) or ".." in branch:
            raise GitHubIntegrationError("invalid branch name")
        result = subprocess.run(
            ["git", "-C", str(repository.resolve(strict=True)), "switch", "-c", branch],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            env={"PATH": os.environ.get("PATH", ""), "GIT_TERMINAL_PROMPT": "0"},
        )
        if result.returncode != 0:
            raise GitHubIntegrationError(result.stderr[-2_000:] or "branch creation failed")

    def push_or_create_pr(self, *args: Any, **kwargs: Any) -> None:
        raise GitHubIntegrationError(
            "push and PR creation are intentionally disabled; export the verified patch/description "
            "or add an authenticated deployment adapter with explicit operator approval"
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "AutonomousDev-Harness"}
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        return headers

    @staticmethod
    def _slug(owner: str, repository: str) -> str:
        pattern = r"[A-Za-z0-9_.-]+"
        if not re.fullmatch(pattern, owner) or not re.fullmatch(pattern, repository):
            raise GitHubIntegrationError("invalid repository slug")
        return f"{owner}/{repository}"
