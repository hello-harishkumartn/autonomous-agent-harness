# AutonomousDev Harness requirements

## Product goal

AutonomousDev Harness accepts a software-engineering task and a local Git repository, builds a bounded view of that repository, plans and applies changes through controlled tools, tests untrusted code in Docker, repairs failures, reviews the resulting diff, and completes only after independent machine checks pass.

The product is a harness around replaceable language models. It is not a chat interface and no provider may bypass harness policy.

## Functional requirements

1. Map directory structure, languages, dependency manifests, symbols, imports, tests, configuration and recent Git history into a lightweight index.
2. Rank task-relevant files and snippets within a configurable token budget. Deduplicate, compress and refresh context after edits. Persist the exact selected context metadata.
3. Expose only typed tools: `list_files`, `read_file`, `search_code`, `find_symbol`, `write_file`, `apply_patch`, `run_tests`, `run_linter`, `run_build`, `get_git_diff`, `get_test_failure`, and `inspect_dependency`.
4. Execute generated code only in Docker with CPU, memory, process, time, filesystem and network controls.
5. Run a persisted state machine through `DISCOVER`, `PLAN`, `IMPLEMENT`, `TEST`, `ANALYZE_FAILURE`, `REPAIR`, `REVIEW`, `VERIFY`, `COMPLETE`, or `ESCALATE`.
6. Enforce attempt, token, tool-call and wall-clock budgets; detect duplicate patches, repeated failures and stagnant iterations.
7. Require configured, machine-verifiable exit checks. A model response can never mark a run complete.
8. Keep the reviewer read-only and emit structured severity-ranked findings.
9. Verify acceptance criteria independently from implementation prompts where practical.
10. Support Gemini, Ollama and OpenAI-compatible HTTP APIs behind one provider protocol. No paid provider is required.
11. Provide a FastAPI API, independent `adev` CLI, Next.js observability UI, PostgreSQL-ready persistence, and local Docker Compose stack.
12. Provide 30 benchmark tasks and compare a simple agent, context-enabled agent and full harness without inventing results.

## Security requirements

- Treat repositories, task text, model output and generated code as untrusted.
- Resolve and validate every path against the repository root; reject traversal, symlink escape and protected harness paths.
- Do not expose a general shell to agents. Map test/build/lint operations to administrator-defined argv allowlists.
- Do not pass host environment variables or credentials into sandboxes or model prompts.
- Default sandbox networking to disabled and root filesystem to read-only, with explicit writable workspace and temporary mounts.
- Bound output bytes, subprocess duration, CPU, memory and process count.
- Record policy denials without leaking secrets.

## Completion contract

A run reaches `VERIFIED_COMPLETE` only when every required check is evidenced as passing, required files exist, changed paths are authorized, reviewer blocking findings are absent, and budgets have not been exceeded. Otherwise it repairs, or escalates with a structured reason.

## Non-goals for the first release

- Training or fine-tuning a model.
- An IDE/chat experience.
- Executing generated code directly on the host.
- Automatically pushing branches or opening pull requests.
- Claiming benchmark improvement before reproducible evaluations have run.
