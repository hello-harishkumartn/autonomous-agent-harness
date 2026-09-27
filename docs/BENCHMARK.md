# Benchmark

The 30-task dataset is versioned in `benchmark/tasks.json`. Category counts cover bug fix, feature, refactor, test creation, API modification, validation, performance and configuration work.

Fixture source, public tests and hidden acceptance tests live in `benchmark/cases.py`. “Hidden” means the tests are not materialized into the target repository until the coding run finishes. They remain visible to benchmark users for auditability. The evaluator, not the agent, owns that boundary.

Each task is fast enough to run repeatedly under Docker. Performance assertions use generous thresholds and algorithmic input sizes, but host contention can still affect them. CI should reserve consistent runners for published results.

To inspect one task:

```bash
python benchmark/materialize.py bug-001 /tmp/bug-001
python benchmark/materialize.py bug-001 /tmp/bug-001 --include-hidden
```

Dataset changes require a schema-version bump when semantics change, fixture-integrity tests, category counts and a note explaining comparability. Never replace a historical result file after changing the dataset.
