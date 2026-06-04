"""File I/O helpers for telemetry records."""

from __future__ import annotations

import csv
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, TextIO


@contextmanager
def output_stream(path: str | Path) -> Iterator[TextIO]:
    if str(path) == "-":
        import sys

        yield sys.stdout
        return
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        yield stream


def read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(path: str | Path, payload: Any) -> None:
    with Path(path).open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def iter_records(path: str | Path) -> Iterator[dict[str, Any]]:
    source = Path(path)
    if source.suffix.lower() == ".csv":
        with source.open("r", encoding="utf-8", newline="") as stream:
            yield from csv.DictReader(stream)
        return
    with source.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{source}:{line_number}: invalid JSON line: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"{source}:{line_number}: JSON line must decode to an object")
            yield payload


def write_jsonl(path: str | Path, records: list[dict[str, Any]]) -> None:
    with Path(path).open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":"), default=str))
            stream.write("\n")

