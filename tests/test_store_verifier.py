from datetime import UTC, datetime, timedelta
from pathlib import Path

from autonomousdev.config import VerificationConfig
from autonomousdev.store import JsonRunStore
from autonomousdev.types import Budget, Event, Evidence, RunOutcome, RunRecord, RunState
from autonomousdev.verifier import Verifier


def test_json_store_round_trip_and_events(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    record = RunRecord(
        "abc",
        "fix it",
        str(tmp_path),
        RunState.DISCOVER,
        RunOutcome.RUNNING,
        now.isoformat(),
        now.isoformat(),
        (now + timedelta(minutes=1)).isoformat(),
        Budget(),
    )
    store = JsonRunStore(tmp_path / "state")
    store.save(record)
    store.append_event("abc", Event(1, now.isoformat(), "DISCOVER", "test", "created"))

    assert store.load("abc").task == "fix it"
    assert store.events("abc")[0]["type"] == "test"


def test_verifier_fails_closed_for_skipped_required_check(tmp_path: Path) -> None:
    config = VerificationConfig(require_tests=True, required_files=["required.txt"])
    (tmp_path / "required.txt").write_text("ok", encoding="utf-8")
    verifier = Verifier(
        tmp_path,
        config,
        lambda operation: Evidence(operation, True, "not configured", metadata={"skipped": True}),
    )

    passed, evidence = verifier.verify(["solution.py"], [])

    assert not passed
    assert next(item for item in evidence if item.kind == "test").passed is False


def test_verifier_rejects_forbidden_change(tmp_path: Path) -> None:
    config = VerificationConfig(require_tests=False)
    passed, evidence = Verifier(tmp_path, config, lambda operation: None).verify([".env"], [])
    assert not passed
    assert evidence[0].metadata["unauthorized"] == [".env"]
