#!/usr/bin/env python3
"""Select an adaptive mesh policy action from recent telemetry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from infer_mesh.io import iter_records, read_json
from infer_mesh.policy import choose_action


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--telemetry", required=True, help="CSV or JSONL telemetry file.")
    parser.add_argument("--config", help="Optional policy config JSON.")
    parser.add_argument("--window", type=float, default=60.0, help="Sliding decision window in seconds.")
    parser.add_argument(
        "--allowed-actions",
        help="Comma-separated action ids permitted for this experiment; defaults to all configured actions.",
    )
    parser.add_argument("--output", default="-", help="Decision JSON output path or '-' for stdout.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.window <= 0:
        print("policy_engine: --window must be positive", file=sys.stderr)
        return 2
    try:
        records = list(iter_records(args.telemetry))
        config = read_json(args.config) if args.config else None
        allowed = (
            {item.strip() for item in args.allowed_actions.split(",") if item.strip()}
            if args.allowed_actions
            else None
        )
        decision = choose_action(records, config=config, allowed_actions=allowed, window_s=args.window)
    except Exception as exc:
        print(f"policy_engine: {exc}", file=sys.stderr)
        return 1

    payload = json.dumps(decision, sort_keys=True, separators=(",", ":"))
    if args.output == "-":
        print(payload)
    else:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

