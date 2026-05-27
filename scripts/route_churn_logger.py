#!/usr/bin/env python3
"""Poll batman-adv originators and emit changes in selected forwarding paths."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any

from collect_batman_metrics import collect as collect_originators


FIELDS = [
    "timestamp",
    "node_id",
    "originator",
    "previous_next_hop",
    "next_hop",
    "batman_tq",
    "event_label",
]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def routes_by_originator(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    selected = [record for record in records if record["selected"]]
    source = selected or records
    return {record["originator"]: record for record in source}


def route_events(
    node_id: str,
    previous: dict[str, dict[str, Any]],
    current: dict[str, dict[str, Any]],
    include_new: bool,
) -> list[dict[str, Any]]:
    timestamp = utc_timestamp()
    events: list[dict[str, Any]] = []
    for originator in sorted(set(previous) | set(current)):
        before = previous.get(originator)
        after = current.get(originator)
        if before is None and after is not None:
            if include_new:
                events.append(
                    {
                        "timestamp": timestamp,
                        "node_id": node_id,
                        "originator": originator,
                        "previous_next_hop": None,
                        "next_hop": after["next_hop"],
                        "batman_tq": after["batman_tq"],
                        "event_label": "route_new",
                    }
                )
            continue
        if before is not None and after is None:
            events.append(
                {
                    "timestamp": timestamp,
                    "node_id": node_id,
                    "originator": originator,
                    "previous_next_hop": before["next_hop"],
                    "next_hop": None,
                    "batman_tq": None,
                    "event_label": "route_lost",
                }
            )
        elif before is not None and after is not None and before["next_hop"] != after["next_hop"]:
            events.append(
                {
                    "timestamp": timestamp,
                    "node_id": node_id,
                    "originator": originator,
                    "previous_next_hop": before["next_hop"],
                    "next_hop": after["next_hop"],
                    "batman_tq": after["batman_tq"],
                    "event_label": "route_change",
                }
            )
    return events


def emit(records: list[dict[str, Any]], output_format: str, writer: csv.DictWriter | None) -> None:
    if output_format == "json":
        for record in records:
            print(json.dumps(record, separators=(",", ":")), flush=True)
        return
    assert writer is not None
    writer.writerows(records)
    sys.stdout.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-id", required=True, help="Stable node identifier used in exports.")
    parser.add_argument("--mesh-interface", default="bat0", help="batman-adv soft interface.")
    parser.add_argument("--batctl-command", default="batctl", help="Path or name of batctl.")
    parser.add_argument("--duration", type=float, default=60.0, help="Logging duration in seconds.")
    parser.add_argument("--interval", type=float, default=5.0, help="Poll interval in seconds.")
    parser.add_argument(
        "--emit-initial",
        action="store_true",
        help="Emit routes found in the initial snapshot as route_new events.",
    )
    parser.add_argument("--format", choices=("csv", "json"), default="json")
    parser.add_argument("--no-header", action="store_true", help="Omit CSV header for appends.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.duration < 0 or args.interval <= 0:
        print("route_churn_logger: duration must be non-negative and interval positive", file=sys.stderr)
        return 2

    writer: csv.DictWriter | None = None
    if args.format == "csv":
        writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator="\n")
        if not args.no_header:
            writer.writeheader()

    deadline = time.monotonic() + args.duration
    previous: dict[str, dict[str, Any]] | None = None
    try:
        while True:
            current = routes_by_originator(
                collect_originators(args.batctl_command, args.node_id, args.mesh_interface)
            )
            if previous is None:
                events = route_events(args.node_id, {}, current, args.emit_initial)
            else:
                events = route_events(args.node_id, previous, current, include_new=True)
            emit(events, args.format, writer)
            previous = current

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(args.interval, remaining))
    except RuntimeError as exc:
        print(f"route_churn_logger: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
