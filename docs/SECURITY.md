# Threat model

## Assets and adversaries

Protected assets include host files, credentials, provider keys, source confidentiality, Git integrity, compute availability and audit records. Adversarial input may come from task text, repository files (including prompt injection), dependency behavior, model output or generated code.

## Controls

| Threat | Control |
|---|---|
| Prompt asks model to bypass policy | System boundary plus server-side typed dispatch; prompts cannot add tools |
| Path traversal or symlink escape | Absolute/traversal rejection, canonical root containment and symlink-parent checks |
| Arbitrary host command | No shell tool; fixed Git argv; generated execution only in Docker |
| Secret read/exfiltration | protected paths, minimal provider payload, no sandbox env inheritance, network disabled |
| Resource exhaustion | time, CPU, memory, PID, output, file-count, token and attempt limits |
| False completion | fresh machine verifier; model cannot set outcome |
| Self-approval | reviewer receives no write tools; verifier excludes implementation rationale |
| Loop/cost runaway | deadlines, counters, repeated-failure and duplicate-patch fingerprints |
| Malicious event content | structured rendering; UI uses React escaping; bounded tool logs |

## Residual risk

The local Compose topology mounts the Docker socket and a repository root into the trusted API container. Compromise of that control plane can control Docker. Production should use a narrow remote sandbox API on separate nodes, admission policy, per-run disposable volumes, seccomp/AppArmor, egress proxies, tenant isolation and centralized secret brokering.

Static secret detection is defense-in-depth, not a secret scanner. Git diff and event storage may contain proprietary code. Encrypt storage, restrict UI access, define retention and use an enterprise secret scanner before external publication.

Optional GitHub integration must use least-scope credentials. Branch creation, pushing and PR creation remain disabled until an operator explicitly enables and authenticates them.
