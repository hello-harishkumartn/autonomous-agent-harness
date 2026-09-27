# AutonomousDev benchmark

This benchmark contains 30 small, deterministic software-engineering tasks across bug fixes, features, refactors, test creation, API changes, validation, performance and configuration.

`tasks.json` is the versioned task manifest. `cases.py` contains the auditable fixture sources and acceptance tests. `materialize.py` creates a clean repository for one task. Hidden tests are absent from the repository while the agent works and are inserted only by the evaluator afterward. They are visible in this open-source benchmark so results can be reproduced and challenged.

The tasks are intentionally fast; they measure loop behavior and configuration deltas rather than broad real-world coverage. See `docs/BENCHMARK.md` for limitations and extension guidance.
