from __future__ import annotations

import json
from pathlib import Path

try:
    from .cases import CASES
except ImportError:  # direct script execution
    from cases import CASES


def load_tasks(dataset: Path) -> list[dict]:
    data = json.loads(dataset.read_text(encoding="utf-8"))
    tasks = data["tasks"]
    missing = {task["id"] for task in tasks} - CASES.keys()
    if missing:
        raise ValueError(f"fixtures missing for: {sorted(missing)}")
    return tasks


def materialize(task_id: str, destination: Path, *, include_hidden: bool = False) -> None:
    case = CASES[task_id]
    destination.mkdir(parents=True, exist_ok=True)
    tests = destination / "tests"
    tests.mkdir(exist_ok=True)
    (destination / "solution.py").write_text(case.source, encoding="utf-8")
    (tests / "test_public.py").write_text(case.public_test, encoding="utf-8")
    (destination / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths=['tests']\naddopts='-q'\n", encoding="utf-8"
    )
    if include_hidden:
        (tests / "test_hidden.py").write_text(case.hidden_test, encoding="utf-8")


def add_hidden(task_id: str, destination: Path) -> None:
    tests = destination / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "test_hidden.py").write_text(CASES[task_id].hidden_test, encoding="utf-8")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("task_id", choices=sorted(CASES))
    parser.add_argument("destination", type=Path)
    parser.add_argument("--include-hidden", action="store_true")
    args = parser.parse_args()
    materialize(args.task_id, args.destination, include_hidden=args.include_hidden)
