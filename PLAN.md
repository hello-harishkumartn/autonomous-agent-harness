# Implementation plan

## Stage 1: executable vertical slice

1. Define typed configuration, state, evidence and provider contracts.
2. Implement repository mapping and budgeted context selection.
3. Implement path-safe file tools and locked-down Docker operations.
4. Implement the persisted orchestration loop, reviewer and independent verifier.
5. Expose the loop through `adev run`, `adev status` and a FastAPI API.
6. Validate with unit and integration tests using a scripted provider and fake sandbox boundary; keep real generated-code execution Docker-only.

## Stage 2: visibility and providers

1. Add Gemini, Ollama and OpenAI-compatible provider adapters.
2. Add append-only observability events and a Next.js run dashboard.
3. Add Compose services for API, UI and PostgreSQL.

## Stage 3: evidence

1. Create a versioned 30-task benchmark dataset with hidden-test layout.
2. Implement the three requested evaluation configurations and aggregate metrics.
3. Run the locally feasible smoke evaluation; store raw, timestamped results and clearly mark anything not run.
4. Add CI, security documentation and demo assets/instructions.

## Release gates

- Unit tests and static checks pass.
- Container definitions validate in CI.
- No generated-code host execution path exists.
- Documentation matches implemented behavior.
- Benchmark summaries are generated from raw results and never hand-authored.
