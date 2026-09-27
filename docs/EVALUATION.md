# Evaluation methodology

`adev eval` materializes each task into a clean temporary Git repository, runs one configuration, saves the agent patch, then adds acceptance tests that were absent from agent context and reruns tests in Docker.

The compared configurations are:

1. `simple`: naive repository context, one implementation attempt, machine acceptance check.
2. `context`: ranked budgeted context, one implementation attempt, machine acceptance check.
3. `full`: ranked refreshed context plus repair loops, read-only review and independent verification.

All configurations use the same provider/model, task order, sandbox image and hidden tests. Temperature is held at 0.1, but provider nondeterminism remains; credible publication should run multiple seeds/replicates and report confidence intervals.

Metrics are computed from raw rows: tasks attempted/successful, pass@1, eventual completion rate, mean repair loops, tool calls, reported tokens, wall latency and failure-category counts. Success requires both `VERIFIED_COMPLETE` and hidden tests passing.

```bash
export ADEV_EVAL_PROVIDER=gemini
export GEMINI_API_KEY=...
adev eval
```

Timestamped JSON and partial checkpoint files go to `benchmark/results/`. If provider configuration or Docker is missing, the evaluator writes `status: not_run`, `tasks_attempted: 0`, and no outcome metrics. This is deliberate protection against fabricated or ambiguous zero results.

Limitations: the current suite is small, Python-only and function-oriented. It is useful for harness ablations and regressions, not a claim of general software-engineering capability. Add larger multi-file tasks and independent human audit before publishing broad conclusions.
