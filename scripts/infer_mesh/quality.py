"""Data quality checks for run-level telemetry."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Any

from .timeutils import parse_timestamp


@dataclass(frozen=True)
class QualityThresholds:
    expected_interval_s: float = 5.0
    max_gap_multiplier: float = 3.0
    max_clock_skew_ms: float = 500.0
    max_missing_gap_rate: float = 0.05
    max_probe_error_rate: float = 0.1


def _thresholds(metadata: dict[str, Any]) -> QualityThresholds:
    quality = metadata.get("quality_thresholds", {})
    if not isinstance(quality, dict):
        quality = {}
    return QualityThresholds(
        expected_interval_s=float(metadata.get("expected_interval_s", quality.get("expected_interval_s", 5.0))),
        max_gap_multiplier=float(quality.get("max_gap_multiplier", 3.0)),
        max_clock_skew_ms=float(quality.get("max_clock_skew_ms", 500.0)),
        max_missing_gap_rate=float(quality.get("max_missing_gap_rate", 0.05)),
        max_probe_error_rate=float(quality.get("max_probe_error_rate", 0.1)),
    )


def _clock_skew_ms(record: dict[str, Any]) -> float | None:
    if record.get("clock_offset_ms") is not None:
        return abs(float(record["clock_offset_ms"]))
    if record.get("collector_timestamp"):
        return abs(
            (parse_timestamp(record["collector_timestamp"]) - parse_timestamp(record["timestamp"])).total_seconds()
            * 1000.0
        )
    return None


def run_quality_checks(records: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    thresholds = _thresholds(metadata)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[(str(record.get("node_id", "")), str(record.get("source", "")))].append(record)

    gaps: list[dict[str, Any]] = []
    comparable_intervals = 0
    max_gap_s = thresholds.expected_interval_s * thresholds.max_gap_multiplier
    for (node_id, source), group in sorted(groups.items()):
        ordered = sorted(group, key=lambda item: parse_timestamp(item["timestamp"]))
        for before, after in zip(ordered, ordered[1:]):
            comparable_intervals += 1
            delta_s = (parse_timestamp(after["timestamp"]) - parse_timestamp(before["timestamp"])).total_seconds()
            if delta_s > max_gap_s:
                gaps.append(
                    {
                        "node_id": node_id,
                        "source": source,
                        "from": before["timestamp"],
                        "to": after["timestamp"],
                        "gap_s": round(delta_s, 3),
                    }
                )

    clock_offsets = [offset for record in records if (offset := _clock_skew_ms(record)) is not None]
    clock_skew_failures = [
        {
            "timestamp": record["timestamp"],
            "node_id": record.get("node_id"),
            "clock_skew_ms": _clock_skew_ms(record),
        }
        for record in records
        if _clock_skew_ms(record) is not None and _clock_skew_ms(record) > thresholds.max_clock_skew_ms
    ]
    node_offsets = metadata.get("node_clock_offsets_ms", {})
    if isinstance(node_offsets, dict):
        for node_id, offset in node_offsets.items():
            try:
                absolute = abs(float(offset))
            except (TypeError, ValueError):
                continue
            clock_offsets.append(absolute)
            if absolute > thresholds.max_clock_skew_ms:
                clock_skew_failures.append({"node_id": node_id, "clock_skew_ms": absolute})

    error_records = [
        record
        for record in records
        if record.get("error")
        or record.get("connected") is False
        or record.get("packet_loss") == 1
        or record.get("peer_available") is False
    ]
    missing_gap_rate = len(gaps) / comparable_intervals if comparable_intervals else 0.0
    probe_error_rate = len(error_records) / len(records) if records else 1.0
    failures: list[str] = []
    if clock_skew_failures:
        failures.append("clock_skew")
    if missing_gap_rate > thresholds.max_missing_gap_rate:
        failures.append("missing_samples")
    if probe_error_rate > thresholds.max_probe_error_rate:
        failures.append("probe_health")
    if not records:
        failures.append("empty_run")

    return {
        "valid": not failures,
        "failures": failures,
        "record_count": len(records),
        "thresholds": thresholds.__dict__,
        "clock_skew": {
            "max_observed_ms": max(clock_offsets) if clock_offsets else None,
            "mean_observed_ms": round(mean(clock_offsets), 3) if clock_offsets else None,
            "failures": clock_skew_failures,
        },
        "missing_samples": {
            "expected_interval_s": thresholds.expected_interval_s,
            "gap_count": len(gaps),
            "checked_intervals": comparable_intervals,
            "gap_rate": round(missing_gap_rate, 6),
            "gaps": gaps,
        },
        "probe_health": {
            "error_records": len(error_records),
            "error_rate": round(probe_error_rate, 6),
        },
    }

