# Harness engineering

AutonomousDev treats model output as a proposal. It validates the response shape, dispatches a named tool, records bounded output and chooses the next state. The provider does not see a state-transition or “complete” tool.

The tool surface is capability-based: repository reads, exact search, symbol lookup, atomic writes, exact single-match replacement, fixed Git diff, dependency inspection and named sandbox operations. A generic shell is intentionally absent. All path-bearing calls pass through one canonicalization policy.

Budgets cover attempts, tool calls, reported provider tokens and wall time. Stop policies hash patches and normalized failures to detect cycling. Policy violations and infrastructure absence escalate rather than falling back to host execution.

Events use concise observable rationale supplied with each tool request. The system does not ask for, store or render hidden chain-of-thought. Evidence includes command argv selected by the harness, exit status, duration, bounded logs and sandbox metadata.

Model replacement requires only `generate_json(stage, payload)`. Included adapters cover Gemini, Ollama and OpenAI-compatible chat-completion services. Tests use a deterministic scripted provider.
