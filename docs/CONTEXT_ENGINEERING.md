# Context engineering

The repository mapper walks without following symlinks, skips generated/vendor directories, bounds file count and file size, and extracts lightweight language, role, symbol and import signals. Recent Git history uses a fixed, timed command.

Task and error terms are matched against paths, symbols and imports. Changed files, test intent and configuration intent receive explicit boosts. Ranked text files are compressed by retaining their head and tail, deduplicated by content hash and packed until the token estimate reaches its budget.

Selection happens before planning and again before every implementation or repair attempt. Refreshing the repository index prevents stale hashes and exposes newly created files. Previous failure summaries and the changed path set alter ranking on repair loops.

Every `ContextBundle` event includes the exact supplied content, score, reasons, line range, content hash and estimated tokens. This favors auditability; deployments handling sensitive source should encrypt the event store and configure retention. A future privacy mode may log encrypted blobs plus hashes, but it must not silently weaken the “exact context” claim.

The implementation is intentionally retrieval-only and deterministic. Embeddings or language servers can be added behind the index interface, then measured against the existing benchmark rather than assumed superior.
