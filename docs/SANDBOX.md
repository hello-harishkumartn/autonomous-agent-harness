# Docker sandbox

Generated code is never executed by a host subprocess. `DockerSandbox` accepts only `test`, `lint`, or `build` and maps each name to administrator-defined argv selected from repository manifests.

Default controls:

- network namespace `none`;
- CPU, memory and process limits;
- dropped Linux capabilities and `no-new-privileges`;
- read-only container root;
- repository mounted read-only at `/input` and copied into a fresh writable tmpfs;
- small `noexec,nosuid` temporary filesystem;
- unprivileged numeric user;
- bounded duration and captured output;
- no inherited secrets or host environment.

Build the purpose-specific images before running tasks:

```bash
docker build -f sandbox/python.Dockerfile -t autonomousdev-python-sandbox:0.1 .
docker build -f sandbox/node.Dockerfile -t autonomousdev-node-sandbox:0.1 .
```

Tags are convenient for local development. Production must pin reviewed image digests, scan images, make the worktree copy-on-write, and run sandboxes on isolated workers. Docker socket access is effectively root-equivalent; the local Compose socket mount is not suitable for untrusted tenants.

Dependency installation is deliberately not an agent tool. Prepare project-specific sandbox images with dependencies installed and network disabled at run time. Missing Docker causes escalation; there is no host fallback.
