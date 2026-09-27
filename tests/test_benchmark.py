import json
from pathlib import Path

from benchmark.cases import CASES
from benchmark.materialize import add_hidden, materialize


def test_dataset_has_30_complete_unique_tasks() -> None:
    manifest = json.loads(Path("benchmark/tasks.json").read_text(encoding="utf-8"))
    tasks = manifest["tasks"]
    ids = [task["id"] for task in tasks]
    categories = {task["category"] for task in tasks}
    assert len(tasks) == 30
    assert len(set(ids)) == 30
    assert set(ids) == set(CASES)
    assert categories == {
        "bug_fix",
        "feature",
        "refactor",
        "test_creation",
        "api_modification",
        "validation",
        "performance_issue",
        "configuration",
    }


def test_hidden_tests_are_added_only_after_agent_phase(tmp_path: Path) -> None:
    materialize("bug-001", tmp_path)
    assert not (tmp_path / "tests" / "test_hidden.py").exists()
    add_hidden("bug-001", tmp_path)
    assert (tmp_path / "tests" / "test_hidden.py").exists()


def test_all_fixture_sources_and_tests_compile() -> None:
    for task_id, case in CASES.items():
        compile(case.source, f"{task_id}/solution.py", "exec")
        compile(case.public_test, f"{task_id}/tests/test_public.py", "exec")
        compile(case.hidden_test, f"{task_id}/tests/test_hidden.py", "exec")
