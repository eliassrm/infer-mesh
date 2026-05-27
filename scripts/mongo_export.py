#!/usr/bin/env python3
"""Export experiment telemetry documents from MongoDB as CSV or JSON Lines."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator, TextIO


DEFAULT_FIELDS = [
    "timestamp",
    "node_id",
    "rssi_dbm",
    "noise_dbm",
    "tx_rate_mbps",
    "rx_rate_mbps",
    "latency_ms",
    "packet_loss",
    "batman_tq",
    "next_hop",
    "throughput_mbps",
    "event_label",
]


def lookup(document: dict[str, Any], dotted_field: str) -> Any:
    value: Any = document
    for part in dotted_field.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


@contextmanager
def output_stream(path: str) -> Iterator[TextIO]:
    if path == "-":
        yield sys.stdout
        return
    with open(path, "w", newline="", encoding="utf-8") as stream:
        yield stream


def csv_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), default=str)
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--uri",
        default=os.environ.get("MONGO_URI", "mongodb://localhost:27017"),
        help="MongoDB URI; defaults to MONGO_URI or local MongoDB.",
    )
    parser.add_argument("--database", default="infer_mesh")
    parser.add_argument("--collection", default="telemetry")
    parser.add_argument("--query", default="{}", help="MongoDB filter as JSON.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum records; zero exports all.")
    parser.add_argument("--format", choices=("csv", "json"), default="csv")
    parser.add_argument("--output", default="-", help="Output filename or '-' for standard output.")
    parser.add_argument(
        "--fields",
        default=",".join(DEFAULT_FIELDS),
        help="Comma-separated CSV fields; dotted document paths are supported.",
    )
    parser.add_argument("--timeout-ms", type=int, default=5000, help="MongoDB connection timeout.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.limit < 0 or args.timeout_ms < 1:
        print("mongo_export: --limit must be non-negative and timeout must be positive", file=sys.stderr)
        return 2
    try:
        query = json.loads(args.query)
    except json.JSONDecodeError as exc:
        print(f"mongo_export: invalid --query JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(query, dict):
        print("mongo_export: --query must decode to a JSON object", file=sys.stderr)
        return 2

    try:
        from bson import json_util
        from pymongo import MongoClient
    except ImportError:
        print("mongo_export: install pymongo to use MongoDB export functionality", file=sys.stderr)
        return 1

    fields = [field.strip() for field in args.fields.split(",") if field.strip()]
    try:
        with MongoClient(args.uri, serverSelectionTimeoutMS=args.timeout_ms) as client:
            client.admin.command("ping")
            cursor = client[args.database][args.collection].find(query).sort("timestamp", 1)
            if args.limit:
                cursor = cursor.limit(args.limit)
            with output_stream(args.output) as stream:
                if args.format == "json":
                    for document in cursor:
                        stream.write(json_util.dumps(document) + "\n")
                else:
                    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
                    writer.writeheader()
                    for document in cursor:
                        writer.writerow(
                            {field: csv_value(lookup(document, field)) for field in fields}
                        )
    except Exception as exc:
        print(f"mongo_export: export failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
