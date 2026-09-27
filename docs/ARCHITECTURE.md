# Architecture deep dive

The root [architecture summary](../ARCHITECTURE.md) defines the component graph and trust boundaries. This document maps those boundaries to code.

| Responsibility | Owner | Implementation |
|---|---|---|
| Repository structure and relationships | Harness | `repository.py` |
| Prompt input selection | Harness | `context.py` |
| Plan/action proposal | Replaceable model | `providers.py` protocol/adapters |
| Filesystem and inspection capabilities | Harness policy | `tools.py` |
| Generated-code execution | Docker boundary | `sandbox.py` |
| State, retries and stopping | Harness | `orchestrator.py` |
| Diff critique | Read-only reviewer role | `reviewer.py` |
| Completion | Machine verifier | `verifier.py` |
| Audit/history | Local JSON or PostgreSQL | `store.py` |

The API and CLI are ingress adapters. Neither contains agent logic. The UI reads persisted state and events, so closing a browser cannot affect a run.

Provider adapters accept the same stage/payload contract. Provider-specific HTTP formats and token counters stop at that boundary. A provider cannot receive credentials other than its own configured key, and sandbox processes receive neither provider credentials nor host environment.

Persistence uses full run snapshots plus append-only event records. Snapshots make status reads cheap; events preserve why a transition occurred and the evidence available at that moment. Local JSON uses write–fsync–replace. The Compose service uses JSONB rows in PostgreSQL.

The initial release runs one orchestration call synchronously. A production deployment should put run IDs on a durable queue, enforce per-tenant repository roots, and use a remote sandbox service rather than mounting the Docker socket.
