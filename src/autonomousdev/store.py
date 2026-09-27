from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

from .types import Budget, Event, Evidence, Plan, ReviewFinding, RunRecord, Usage


class RunStore(Protocol):
    def save(self, record: RunRecord) -> None: ...
    def load(self, run_id: str) -> RunRecord: ...
    def append_event(self, run_id: str, event: Event) -> None: ...
    def events(self, run_id: str) -> list[dict[str, Any]]: ...
    def list_runs(self) -> list[RunRecord]: ...


def deserialize_record(data: dict[str, Any]) -> RunRecord:
    return RunRecord(
        **{
            **data,
            "budget": Budget(**data["budget"]),
            "usage": Usage(**data["usage"]),
            "plan": Plan(**data["plan"]) if data.get("plan") else None,
            "evidence": [Evidence(**item) for item in data.get("evidence", [])],
            "findings": [ReviewFinding(**item) for item in data.get("findings", [])],
        }
    )


class JsonRunStore:
    """Atomic local store with append-only JSONL events.

    PostgreSQL is used by the Compose deployment; this store keeps the CLI useful
    without infrastructure and intentionally lives outside target repositories.
    """

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.runs_dir = self.root / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def save(self, record: RunRecord) -> None:
        target = self.runs_dir / f"{record.id}.json"
        with self._lock:
            fd, temporary = tempfile.mkstemp(dir=self.runs_dir, prefix=f".{record.id}-")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(record.to_dict(), handle, indent=2, sort_keys=True)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)

    def load(self, run_id: str) -> RunRecord:
        data = json.loads((self.runs_dir / f"{run_id}.json").read_text(encoding="utf-8"))
        return deserialize_record(data)

    def append_event(self, run_id: str, event: Event) -> None:
        target = self.runs_dir / f"{run_id}.events.jsonl"
        with self._lock, target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), sort_keys=True) + "\n")

    def events(self, run_id: str) -> list[dict[str, Any]]:
        target = self.runs_dir / f"{run_id}.events.jsonl"
        if not target.exists():
            return []
        return [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]

    def list_runs(self) -> list[RunRecord]:
        return [self.load(path.stem) for path in sorted(self.runs_dir.glob("*.json"))]


class PostgresRunStore:
    """PostgreSQL event store used by the multi-service deployment."""

    def __init__(self, dsn: str):
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError("install the 'postgres' extra to use PostgreSQL") from error
        self.psycopg = psycopg
        self.dsn = dsn
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS adev_runs (
                    id text PRIMARY KEY,
                    updated_at timestamptz NOT NULL,
                    payload jsonb NOT NULL
                );
                CREATE TABLE IF NOT EXISTS adev_events (
                    run_id text NOT NULL,
                    sequence integer NOT NULL,
                    timestamp timestamptz NOT NULL,
                    payload jsonb NOT NULL,
                    PRIMARY KEY (run_id, sequence)
                );
                """
            )
            connection.commit()

    def _connect(self):
        return self.psycopg.connect(self.dsn)

    def save(self, record: RunRecord) -> None:
        payload = json.dumps(record.to_dict())
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO adev_runs (id, updated_at, payload)
                VALUES (%s, %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE
                SET updated_at = EXCLUDED.updated_at, payload = EXCLUDED.payload""",
                (record.id, record.updated_at, payload),
            )
            connection.commit()

    def load(self, run_id: str) -> RunRecord:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM adev_runs WHERE id = %s", (run_id,))
            row = cursor.fetchone()
        if row is None:
            raise FileNotFoundError(run_id)
        data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return deserialize_record(data)

    def append_event(self, run_id: str, event: Event) -> None:
        payload = json.dumps(asdict(event))
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO adev_events (run_id, sequence, timestamp, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                ON CONFLICT (run_id, sequence) DO NOTHING""",
                (run_id, event.sequence, event.timestamp, payload),
            )
            connection.commit()

    def events(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT payload FROM adev_events WHERE run_id = %s ORDER BY sequence", (run_id,)
            )
            rows = cursor.fetchall()
        return [row[0] if isinstance(row[0], dict) else json.loads(row[0]) for row in rows]

    def list_runs(self) -> list[RunRecord]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM adev_runs ORDER BY updated_at DESC LIMIT 500")
            rows = cursor.fetchall()
        return [
            deserialize_record(row[0] if isinstance(row[0], dict) else json.loads(row[0]))
            for row in rows
        ]
