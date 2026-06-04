#!/usr/bin/env python3
"""Compare static and adaptive telemetry runs and generate a results report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from infer_mesh.io import iter_records, write_json
from infer_mesh.stats import markdown_report, paired_summary, run_metrics


def _records(path: str) -> list[dict[str, object]]:
    return list(iter_records(path))


def _parse_pair(value: str) -> tuple[str, str]:
    if ":" not in value:
        raise argparse.ArgumentTypeError("pairs must use STATIC:ADAPTIVE")
    static, adaptive = value.split(":", 1)
    if not static or not adaptive:
        raise argparse.ArgumentTypeError("pairs must include both STATIC and ADAPTIVE paths")
    return static, adaptive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static", help="Static baseline CSV/JSONL telemetry.")
    parser.add_argument("--adaptive", help="Adaptive policy CSV/JSONL telemetry.")
    parser.add_argument(
        "--pair",
        action="append",
        type=_parse_pair,
        help="Paired STATIC:ADAPTIVE run paths; repeat for statistics.",
    )
    parser.add_argument("--experiment-id", default="paired-analysis")
    parser.add_argument("--scenario", default="policy_comparison")
    parser.add_argument("--output", default="docs/results-template.md", help="Markdown report path.")
    parser.add_argument("--json-output", help="Optional machine-readable analysis JSON path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    pairs = args.pair or []
    if args.static or args.adaptive:
        if not (args.static and args.adaptive):
            print("paired_analysis: provide both --static and --adaptive", file=sys.stderr)
            return 2
        pairs.insert(0, (args.static, args.adaptive))
    if not pairs:
        print("paired_analysis: provide --static/--adaptive or at least one --pair", file=sys.stderr)
        return 2

    try:
        metric_pairs = [
            (run_metrics(_records(static_path)), run_metrics(_records(adaptive_path)))
            for static_path, adaptive_path in pairs
        ]
        static_metrics, adaptive_metrics = metric_pairs[0]
        summary = paired_summary(metric_pairs)
        report = markdown_report(
            args.experiment_id,
            args.scenario,
            static_metrics,
            adaptive_metrics,
            summary,
        )
        Path(args.output).write_text(report, encoding="utf-8")
        if args.json_output:
            write_json(
                args.json_output,
                {
                    "experiment_id": args.experiment_id,
                    "scenario": args.scenario,
                    "pairs": len(metric_pairs),
                    "static_metrics": static_metrics,
                    "adaptive_metrics": adaptive_metrics,
                    "paired_summary": summary,
                },
            )
    except Exception as exc:
        print(f"paired_analysis: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

