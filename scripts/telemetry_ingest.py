#!/usr/bin/env python3
"""Ingest collector CSV/JSONL files into a validated run-level telemetry dataset."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from infer_mesh.io import iter_records, read_json, write_json, write_jsonl
from infer_mesh.quality import run_quality_checks
from infer_mesh.schema import normalize_metadata, normalize_record, validate_metadata
from infer_mesh.security import attach_signature, verify_signature


def _source_name(path: Path) -> str:
    return path.stem.replace(".", "_")


def _secret_from_env(name: str | None) -> str | None:
    if not name:
        return None
    value = os.environ.get(name)
    if value is None:
        raise ValueError(f"environment variable {name} is not set")
    return value


def ingest(
    metadata_path: str | Path,
    input_paths: list[str | Path],
    output_dir: str | Path,
    default_event_label: str | None = None,
    sign_secret: str | None = None,
    require_signature_secret: str | None = None,
) -> dict[str, Any]:
    metadata = normalize_metadata(read_json(metadata_path))
    metadata_issues = validate_metadata(metadata)
    if metadata_issues:
        return {
            "ok": False,
            "errors": [issue.as_dict() for issue in metadata_issues],
            "output_dir": None,
        }

    normalized_records: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    signature_failures = 0
    source_counts: dict[str, int] = {}
    for raw_path in input_paths:
        path = Path(raw_path)
        source = _source_name(path)
        count = 0
        for line_index, record in enumerate(iter_records(path), start=1):
            count += 1
            if require_signature_secret and not verify_signature(record, require_signature_secret):
                signature_failures += 1
                invalid_records.append(
                    {
                        "source": source,
                        "line": line_index,
                        "issues": [{"field": "signature", "message": "signature verification failed"}],
                        "record": record,
                    }
                )
                continue
            normalized, issues = normalize_record(
                record,
                metadata,
                source=source,
                default_event_label=default_event_label,
            )
            if issues:
                invalid_records.append(
                    {
                        "source": source,
                        "line": line_index,
                        "issues": [issue.as_dict() for issue in issues],
                        "record": record,
                    }
                )
                continue
            normalized_records.append(
                attach_signature(normalized, sign_secret) if sign_secret else normalized
            )
        source_counts[source] = count

    experiment_id = str(metadata["experiment_id"])
    run_dir = Path(output_dir) / experiment_id
    run_dir.mkdir(parents=True, exist_ok=True)
    telemetry_path = run_dir / "telemetry.jsonl"
    metadata_path_out = run_dir / "run_metadata.json"
    invalid_path = run_dir / "invalid_records.json"
    quality_path = run_dir / "quality_report.json"
    manifest_path = run_dir / "ingest_manifest.json"

    quality = run_quality_checks(normalized_records, metadata)
    write_jsonl(telemetry_path, normalized_records)
    write_json(metadata_path_out, metadata)
    write_json(invalid_path, invalid_records)
    write_json(quality_path, quality)
    manifest = {
        "ok": not invalid_records and quality["valid"],
        "experiment_id": experiment_id,
        "record_count": len(normalized_records),
        "invalid_record_count": len(invalid_records),
        "signature_failures": signature_failures,
        "source_counts": source_counts,
        "telemetry_path": str(telemetry_path),
        "metadata_path": str(metadata_path_out),
        "invalid_records_path": str(invalid_path),
        "quality_report_path": str(quality_path),
        "quality_valid": quality["valid"],
        "quality_failures": quality["failures"],
    }
    write_json(manifest_path, manifest)
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", required=True, help="Run metadata JSON file.")
    parser.add_argument("--input", action="append", required=True, help="Collector CSV/JSONL input; repeatable.")
    parser.add_argument("--output-dir", default="data/runs", help="Directory for per-run outputs.")
    parser.add_argument("--event-label", help="Default event label when a source record omits one.")
    parser.add_argument(
        "--sign-output-env",
        help="Environment variable containing an HMAC secret used to sign normalized output records.",
    )
    parser.add_argument(
        "--require-signature-env",
        help="Environment variable containing an HMAC secret used to verify signed input records.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        manifest = ingest(
            metadata_path=args.metadata,
            input_paths=args.input,
            output_dir=args.output_dir,
            default_event_label=args.event_label,
            sign_secret=_secret_from_env(args.sign_output_env),
            require_signature_secret=_secret_from_env(args.require_signature_env),
        )
    except Exception as exc:
        print(f"telemetry_ingest: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, sort_keys=True))
    return 0 if manifest.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

