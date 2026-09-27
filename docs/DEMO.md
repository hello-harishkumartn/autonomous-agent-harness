# Demo guide

1. Build both sandbox images and start Compose.
2. Open `http://localhost:3000` and keep the empty observatory visible.
3. Run a task against a disposable repository from the CLI or `POST /api/runs`.
4. Show discovery and the exact ranked context packet.
5. Use a fixture that fails once so `ANALYZE_FAILURE → REPAIR` becomes visible.
6. Show the reviewer findings and fresh verification evidence.
7. End on the generated patch and PR description, then contrast with an escalation caused by an unauthorized path.

For the README GIF, record at 1440×900, crop to the browser, keep it under 12 MB and place it at `docs/assets/demo.gif`. Replace the SVG placeholder reference only after the recording exists. Do not mock run data for the recording.

Suggested screenshots: run overview, exact context event expanded, repair evidence, and the three-configuration benchmark summary chart. Put them under `docs/assets/` with descriptive alt text.
