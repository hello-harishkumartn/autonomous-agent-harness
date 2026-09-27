from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import HarnessConfig
from .factory import create_provider
from .orchestrator import Orchestrator
from .store import JsonRunStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="adev", description="AutonomousDev engineering harness")
    parser.add_argument("--state-dir", type=Path, help="run state directory (outside target repo)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run a software-engineering task")
    run.add_argument("repository", type=Path)
    run.add_argument("--task", required=True)
    run.add_argument(
        "--provider", choices=["gemini", "ollama", "openai-compatible"], default="gemini"
    )
    run.add_argument("--model")
    run.add_argument("--base-url")
    run.add_argument("--api-key")
    run.add_argument("--require-lint", action="store_true")
    run.add_argument("--require-build", action="store_true")
    run.add_argument("--required-file", action="append", default=[])
    run.add_argument("--allow-change", action="append", default=[])

    status = subparsers.add_parser("status", help="show a persisted run")
    status.add_argument("run_id")
    status.add_argument("--events", action="store_true")

    evaluate = subparsers.add_parser("eval", help="run benchmark evaluation")
    evaluate.add_argument("--dataset", type=Path, default=Path("benchmark/tasks.json"))
    evaluate.add_argument("--output", type=Path, default=Path("benchmark/results"))
    evaluate.add_argument("--configuration", choices=["simple", "context", "full"], action="append")
    evaluate.add_argument("--limit", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = HarnessConfig.from_environment()
    if args.state_dir:
        config.state_dir = args.state_dir.expanduser().resolve()
    store = JsonRunStore(config.state_dir)

    if args.command == "status":
        try:
            record = store.load(args.run_id)
        except FileNotFoundError:
            print(f"run not found: {args.run_id}", file=sys.stderr)
            return 2
        output = record.to_dict()
        if args.events:
            output["events"] = store.events(args.run_id)
        print(json.dumps(output, indent=2))
        return 0

    if args.command == "eval":
        from .evaluation import evaluate_dataset

        result = evaluate_dataset(
            args.dataset,
            args.output,
            configurations=args.configuration or ["simple", "context", "full"],
            limit=args.limit,
        )
        print(json.dumps(result, indent=2))
        return 0

    config.verification.require_lint = args.require_lint
    config.verification.require_build = args.require_build
    config.verification.required_files = args.required_file
    if args.allow_change:
        config.verification.allowed_change_globs = args.allow_change
    provider = create_provider(
        args.provider, model=args.model, base_url=args.base_url, api_key=args.api_key
    )
    record = Orchestrator(config, provider, store).run(args.repository, args.task)
    print(json.dumps(record.to_dict(), indent=2))
    return 0 if record.outcome == "VERIFIED_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
