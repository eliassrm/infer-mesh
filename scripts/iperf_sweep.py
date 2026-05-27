#!/usr/bin/env python3
"""Run bounded iperf3 measurements against one or more authorized mesh endpoints."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any


FIELDS = [
    "timestamp",
    "node_id",
    "server",
    "port",
    "reverse",
    "duration_s",
    "parallel_streams",
    "sent_mbps",
    "received_mbps",
    "retransmits",
    "error",
]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def mbps(bits_per_second: float | int | None) -> float | None:
    return round(float(bits_per_second) / 1_000_000, 3) if bits_per_second is not None else None


def run_measurement(
    iperf_command: str,
    node_id: str,
    server: str,
    port: int,
    duration_s: int,
    parallel_streams: int,
    reverse: bool,
) -> dict[str, Any]:
    command = [
        iperf_command,
        "--client",
        server,
        "--port",
        str(port),
        "--time",
        str(duration_s),
        "--parallel",
        str(parallel_streams),
        "--json",
    ]
    if reverse:
        command.append("--reverse")

    record: dict[str, Any] = {
        "timestamp": utc_timestamp(),
        "node_id": node_id,
        "server": server,
        "port": port,
        "reverse": reverse,
        "duration_s": duration_s,
        "parallel_streams": parallel_streams,
        "sent_mbps": None,
        "received_mbps": None,
        "retransmits": None,
        "error": None,
    }
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        record["error"] = f"required command not found: {iperf_command}"
        return record

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}

    end = payload.get("end", {})
    sent = end.get("sum_sent", {})
    received = end.get("sum_received", {})
    record["sent_mbps"] = mbps(sent.get("bits_per_second"))
    record["received_mbps"] = mbps(received.get("bits_per_second"))
    record["retransmits"] = sent.get("retransmits")
    if payload.get("error"):
        record["error"] = payload["error"]
    elif result.returncode != 0:
        record["error"] = result.stderr.strip() or "iperf3 exited with an error"
    return record


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
    parser.add_argument("--node-id", required=True, help="Stable source node identifier.")
    parser.add_argument(
        "--server",
        action="append",
        required=True,
        help="Authorized iperf3 server address; repeat to execute a sweep.",
    )
    parser.add_argument("--port", type=int, default=5201)
    parser.add_argument("--duration", type=int, default=10, help="Measurement duration in seconds.")
    parser.add_argument("--parallel", type=int, default=1, help="Number of parallel test streams.")
    parser.add_argument("--reverse", action="store_true", help="Measure traffic from server to node.")
    parser.add_argument("--iperf-command", default="iperf3", help="Path or name of iperf3.")
    parser.add_argument("--format", choices=("csv", "json"), default="json")
    parser.add_argument("--no-header", action="store_true", help="Omit CSV header for appends.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.port < 1 or args.duration < 1 or args.parallel < 1:
        print("iperf_sweep: port, duration, and parallel values must be positive", file=sys.stderr)
        return 2
    records = [
        run_measurement(
            args.iperf_command,
            args.node_id,
            server,
            args.port,
            args.duration,
            args.parallel,
            args.reverse,
        )
        for server in args.server
    ]
    emit(records, args.format, include_header=not args.no_header)
    return 1 if any(record["error"] for record in records) else 0


if __name__ == "__main__":
    raise SystemExit(main())
