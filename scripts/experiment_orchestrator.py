#!/usr/bin/env python3
"""Run an INFER-MESH experiment scenario from the controller."""

from __future__ import annotations

import argparse
import json
import sys

from infer_mesh.orchestrator import ExperimentOrchestrator, load_scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, help="Scenario JSON file.")
    parser.add_argument("--output-dir", default="data/runs", help="Directory for run outputs.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run configured collector/intervention commands. Without this flag the run is a dry run.",
    )
    parser.add_argument(
        "--approval-token",
        help="Required when an executable scenario action has requires_approval=true.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        scenario = load_scenario(args.scenario)
        manifest = ExperimentOrchestrator(
            scenario,
            output_dir=args.output_dir,
            execute=args.execute,
            approval_token=args.approval_token,
        ).run()
    except Exception as exc:
        print(f"experiment_orchestrator: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

