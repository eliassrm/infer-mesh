#!/usr/bin/env python3
"""Collect wireless peer observations from an OpenWrt mesh interface."""

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
    "interface",
    "peer_mac",
    "connected",
    "rssi_dbm",
    "noise_dbm",
    "tx_rate_mbps",
    "rx_rate_mbps",
]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def find_float(pattern: str, output: str) -> float | None:
    match = re.search(pattern, output, re.IGNORECASE)
    return float(match.group(1)) if match else None


def parse_link_output(output: str) -> dict[str, Any]:
    peer = re.search(r"Connected to\s+([0-9a-f:]{17})", output, re.IGNORECASE)
    connected = peer is not None and "Not connected" not in output
    return {
        "peer_mac": peer.group(1).lower() if peer else None,
        "connected": connected,
        "rssi_dbm": find_float(r"\bsignal:\s*(-?\d+(?:\.\d+)?)\s*dBm", output),
        "tx_rate_mbps": find_float(r"\btx bitrate:\s*(\d+(?:\.\d+)?)\s*MBit/s", output),
        "rx_rate_mbps": find_float(r"\brx bitrate:\s*(\d+(?:\.\d+)?)\s*MBit/s", output),
    }


def parse_station_output(output: str) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    matches = list(re.finditer(r"^Station\s+([0-9a-f:]{17})", output, re.IGNORECASE | re.MULTILINE))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(output)
        block = output[match.start() : end]
        observations.append(
            {
                "peer_mac": match.group(1).lower(),
                "connected": True,
                "rssi_dbm": find_float(r"\bsignal:\s*(-?\d+(?:\.\d+)?)\s*dBm", block),
                "tx_rate_mbps": find_float(r"\btx bitrate:\s*(\d+(?:\.\d+)?)\s*MBit/s", block),
                "rx_rate_mbps": find_float(r"\brx bitrate:\s*(\d+(?:\.\d+)?)\s*MBit/s", block),
            }
        )
    return observations


def parse_noise_output(output: str) -> float | None:
    return find_float(r"\bNoise:\s*(-?\d+(?:\.\d+)?)\s*dBm", output)


def run_command(command: list[str], optional: bool = False) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        if optional:
            return ""
        raise RuntimeError(f"required command not found: {command[0]}") from None

    if result.returncode != 0:
        if optional:
            return ""
        detail = result.stderr.strip() or result.stdout.strip() or "unknown command failure"
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return result.stdout


def collect(
    node_id: str, interface: str, iw_command: str, iwinfo_command: str
) -> list[dict[str, Any]]:
    station_output = run_command([iw_command, "dev", interface, "station", "dump"], optional=True)
    observations = parse_station_output(station_output)
    if not observations:
        observations = [parse_link_output(run_command([iw_command, "dev", interface, "link"]))]
    noise_output = run_command([iwinfo_command, interface, "info"], optional=True)
    timestamp = utc_timestamp()
    noise = parse_noise_output(noise_output)
    return [
        {
            "timestamp": timestamp,
            "node_id": node_id,
            "interface": interface,
            **observation,
            "noise_dbm": noise,
        }
        for observation in observations
    ]


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
    parser.add_argument("--interface", default="mesh0", help="Wireless mesh interface to inspect.")
    parser.add_argument("--iw-command", default="iw", help="Path or name of the iw executable.")
    parser.add_argument(
        "--iwinfo-command",
        default="iwinfo",
        help="Path or name of optional iwinfo executable used for noise readings.",
    )
    parser.add_argument("--format", choices=("csv", "json"), default="json")
    parser.add_argument("--no-header", action="store_true", help="Omit CSV header for appends.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        records = collect(args.node_id, args.interface, args.iw_command, args.iwinfo_command)
    except RuntimeError as exc:
        print(f"collect_iw_metrics: {exc}", file=sys.stderr)
        return 1
    emit(records, args.format, include_header=not args.no_header)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
