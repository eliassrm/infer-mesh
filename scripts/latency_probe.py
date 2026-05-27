#!/usr/bin/env python3
"""Measure round-trip latency and packet loss with a bounded ping probe."""

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
    "target",
    "transmitted",
    "received",
    "packet_loss",
    "latency_min_ms",
    "latency_ms",
    "latency_max_ms",
]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_ping_output(output: str, node_id: str, target: str) -> dict[str, Any]:
    linux_packets = re.search(
        r"(\d+)\s+packets transmitted,\s*(\d+)(?:\s+packets)?\s+received.*?(\d+(?:\.\d+)?)%\s+packet loss",
        output,
        re.IGNORECASE,
    )
    windows_packets = re.search(
        r"Sent = (\d+), Received = (\d+), Lost = \d+ \((\d+(?:\.\d+)?)% loss\)",
        output,
        re.IGNORECASE,
    )
    packets = linux_packets or windows_packets
    if not packets:
        raise RuntimeError("unable to parse packet-loss summary from ping output")

    timing = re.search(
        r"(?:round-trip|rtt)[^=]*=\s*(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)",
        output,
        re.IGNORECASE,
    )
    windows_timing = re.search(
        r"Minimum = (\d+(?:\.\d+)?)ms, Maximum = (\d+(?:\.\d+)?)ms, Average = (\d+(?:\.\d+)?)ms",
        output,
        re.IGNORECASE,
    )
    minimum = float(timing.group(1)) if timing else (
        float(windows_timing.group(1)) if windows_timing else None
    )
    average = float(timing.group(2)) if timing else (
        float(windows_timing.group(3)) if windows_timing else None
    )
    maximum = float(timing.group(3)) if timing else (
        float(windows_timing.group(2)) if windows_timing else None
    )

    return {
        "timestamp": utc_timestamp(),
        "node_id": node_id,
        "target": target,
        "transmitted": int(packets.group(1)),
        "received": int(packets.group(2)),
        "packet_loss": float(packets.group(3)) / 100.0,
        "latency_min_ms": minimum,
        "latency_ms": average,
        "latency_max_ms": maximum,
    }


def probe(
    node_id: str,
    target: str,
    count: int,
    timeout_s: int,
    ping_command: str,
    ping_style: str,
) -> dict[str, Any]:
    if ping_style == "windows":
        command = [ping_command, "-n", str(count), "-w", str(timeout_s * 1000), target]
    else:
        command = [ping_command, "-c", str(count), "-W", str(timeout_s), target]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise RuntimeError(f"required command not found: {ping_command}") from None
    output = "\n".join((result.stdout, result.stderr))
    return parse_ping_output(output, node_id, target)


def emit(record: dict[str, Any], output_format: str, include_header: bool) -> None:
    if output_format == "json":
        print(json.dumps(record, separators=(",", ":")))
        return
    writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator="\n")
    if include_header:
        writer.writeheader()
    writer.writerow(record)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-id", required=True, help="Stable node identifier used in exports.")
    parser.add_argument("--target", required=True, help="Authorized probe destination.")
    parser.add_argument("--count", type=int, default=5, help="Number of ICMP probes.")
    parser.add_argument("--timeout", type=int, default=2, help="Per-packet timeout in seconds.")
    parser.add_argument("--ping-command", default="ping", help="Path or name of ping.")
    parser.add_argument(
        "--ping-style",
        choices=("openwrt", "windows"),
        default="openwrt",
        help="Command-line style for the local ping implementation.",
    )
    parser.add_argument("--format", choices=("csv", "json"), default="json")
    parser.add_argument("--no-header", action="store_true", help="Omit CSV header for appends.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.count < 1 or args.timeout < 1:
        print("latency_probe: --count and --timeout must be positive", file=sys.stderr)
        return 2
    try:
        record = probe(
            args.node_id,
            args.target,
            args.count,
            args.timeout,
            args.ping_command,
            args.ping_style,
        )
    except RuntimeError as exc:
        print(f"latency_probe: {exc}", file=sys.stderr)
        return 1
    emit(record, args.format, include_header=not args.no_header)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
