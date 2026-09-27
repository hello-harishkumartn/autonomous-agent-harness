# Delivery checklist

Updated as implementation progresses. `[~]` means implemented but not executable in the current workstation because the required runtime is unavailable.

## Foundation

- [x] Capture requirements
- [x] Define architecture and trust boundaries
- [x] Define implementation plan
- [x] Package and configuration
- [x] Persistent run/event model

## Core harness

- [x] Repository mapper
- [x] Context ranking, packing, compression and audit log
- [x] Controlled file and inspection tools
- [x] Docker-only test/lint/build sandbox
- [x] Explicit state machine and recovery policies
- [x] Read-only reviewer
- [x] Independent machine verifier
- [x] Patch and PR-description output

## Interfaces

- [x] CLI: `run`, `status`, `eval`
- [x] FastAPI service
- [x] Next.js observability UI
- [x] Optional GitHub adapter boundary
- [x] Gemini, Ollama and OpenAI-compatible providers

## Evaluation and delivery

- [x] 30-task benchmark dataset
- [x] Three-configuration evaluation runner
- [ ] Reproducible raw results — blocked locally because Docker and a configured model provider are absent; evaluator records `not_run`
- [x] Unit/integration/security tests — 14 tests pass; frontend build and static analysis pass
- [~] Docker Compose and GitHub Actions — implemented; Docker runtime unavailable locally
- [x] Architecture, harness, loop, context, sandbox, security, evaluation, benchmark, demo and resume docs
