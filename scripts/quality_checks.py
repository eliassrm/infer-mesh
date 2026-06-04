#!/usr/bin/env python3
"""Run clock-skew, missing-sample, and probe-health checks on telemetry."""

from __future__ import annotations

import argparse
import json
import sys

from infer_mesh.io import iter_records, read_json
from infer_mesh.quality import run_quality_checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Telemetry CSV/JSONL input.")
    parser.add_argument("--metadata", required=True, help="Run metadata JSON.")
    parser.add_argument("--output", default="-", help="Quality report JSON path or '-' for stdout.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = run_quality_checks(list(iter_records(args.input)), read_json(args.metadata))
    except Exception as exc:
        print(f"quality_checks: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output == "-":
        print(payload)
    else:
        with open(args.output, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.write("\n")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

