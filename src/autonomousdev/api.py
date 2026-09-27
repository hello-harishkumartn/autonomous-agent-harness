from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import HarnessConfig
from .factory import create_provider
from .orchestrator import Orchestrator
from .store import JsonRunStore, PostgresRunStore, RunStore


class RunRequest(BaseModel):
    repository: str
    task: str = Field(min_length=3, max_length=20_000)
    provider: str = "gemini"
    model: str | None = None
    base_url: str | None = None
    require_lint: bool = False
    require_build: bool = False
    required_files: list[str] = Field(default_factory=list)
    allowed_change_globs: list[str] = Field(default_factory=lambda: ["**"])


def _store(config: HarnessConfig) -> RunStore:
    database_url = os.getenv("DATABASE_URL")
    return PostgresRunStore(database_url) if database_url else JsonRunStore(config.state_dir)


config = HarnessConfig.from_environment()
store = _store(config)
app = FastAPI(title="AutonomousDev Harness", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("ADEV_UI_ORIGIN", "http://localhost:3000")],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/runs")
def list_runs() -> list[dict[str, Any]]:
    return [record.to_dict() for record in store.list_runs()]


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    try:
        record = store.load(run_id)
    except FileNotFoundError as error:
        raise HTTPException(404, "run not found") from error
    return {**record.to_dict(), "events": store.events(run_id)}


@app.post("/api/runs")
def create_run(request: RunRequest) -> dict[str, Any]:
    repository = Path(request.repository).resolve(strict=False)
    allowed_root = os.getenv("ADEV_REPOSITORY_ROOT")
    if allowed_root:
        try:
            repository.relative_to(Path(allowed_root).resolve(strict=True))
        except ValueError as error:
            raise HTTPException(403, "repository is outside ADEV_REPOSITORY_ROOT") from error
    if not repository.is_dir():
        raise HTTPException(400, "repository does not exist")
    run_config = HarnessConfig.from_environment()
    run_config.verification.require_lint = request.require_lint
    run_config.verification.require_build = request.require_build
    run_config.verification.required_files = request.required_files
    run_config.verification.allowed_change_globs = request.allowed_change_globs
    provider = create_provider(request.provider, model=request.model, base_url=request.base_url)
    record = Orchestrator(run_config, provider, store).run(repository, request.task)
    return record.to_dict()
