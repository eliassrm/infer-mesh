#!/usr/bin/env python3
"""Collect batman-adv originator and selected next-hop observations."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any


FIELDS = [
    "timestamp",
    "node_id",
    "mesh_interface",
    "originator",
    "next_hop",
    "outgoing_interface",
    "batman_tq",
    "last_seen_s",
    "selected",
]
ORIGINATOR_PATTERN = re.compile(
    r"(?P<originator>[0-9a-f:]{17})\s+"
    r"(?P<last_seen>\d+(?:\.\d+)?)s\s+"
    r"\(\s*(?P<tq>\d+)\)\s+"
    r"(?P<next_hop>[0-9a-f:]{17})\s+"
    r"\[(?P<outgoing>[^\]]+)\]",
    re.IGNORECASE,
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_originators(output: str, node_id: str, mesh_interface: str) -> list[dict[str, Any]]:
    timestamp = utc_timestamp()
    records: list[dict[str, Any]] = []
    for line in output.splitlines():
        match = ORIGINATOR_PATTERN.search(line)
        if not match:
            continue
        prefix = line[: match.start("originator")]
        records.append(
            {
                "timestamp": timestamp,
                "node_id": node_id,
                "mesh_interface": mesh_interface,
                "originator": match.group("originator").lower(),
                "next_hop": match.group("next_hop").lower(),
                "outgoing_interface": match.group("outgoing"),
                "batman_tq": int(match.group("tq")),
                "last_seen_s": float(match.group("last_seen")),
                "selected": "*" in prefix,
            }
        )
    return records


def collect(batctl_command: str, node_id: str, mesh_interface: str) -> list[dict[str, Any]]:
    command = [batctl_command, "meshif", mesh_interface, "originators"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise RuntimeError(f"required command not found: {batctl_command}") from None
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown command failure"
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return parse_originators(result.stdout, node_id, mesh_interface)


def emit(records: list[dict[str, Any]], output_format: str, include_header: bool) -> None:
    if output_format == "json":
        for record in records:
            print(json.dumps(record, separators=(",", ":")))
        return

    writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator="\n")
    if include_header:
        writer.writeheader()
    writer.writerows(records)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-id", required=True, help="Stable node identifier used in exports.")
    parser.add_argument("--mesh-interface", default="bat0", help="batman-adv soft interface.")
    parser.add_argument("--batctl-command", default="batctl", help="Path or name of batctl.")
    parser.add_argument("--format", choices=("csv", "json"), default="json")
    parser.add_argument("--no-header", action="store_true", help="Omit CSV header for appends.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        records = collect(args.batctl_command, args.node_id, args.mesh_interface)
    except RuntimeError as exc:
        print(f"collect_batman_metrics: {exc}", file=sys.stderr)
        return 1
    emit(records, args.format, include_header=not args.no_header)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
