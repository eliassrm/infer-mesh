"""Canonical telemetry and run metadata schema helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import SCHEMA_VERSION
from .timeutils import format_timestamp, parse_timestamp, utc_now


ALLOWED_EVENT_LABELS = {
    "baseline",
    "degradation",
    "recovery",
    "adaptation",
    "failure",
    "route_new",
    "route_lost",
    "route_change",
    "policy_decision",
    "phase_start",
    "phase_end",
}
ALLOWED_POLICY_MODES = {"static", "adaptive", "dry-run", "manual"}
REQUIRED_METADATA_FIELDS = {
    "experiment_id",
    "scenario",
    "policy_mode",
    "topology_revision",
}
REQUIRED_RECORD_FIELDS = {"timestamp", "node_id", "experiment_id", "event_label", "policy_mode"}
NUMERIC_FIELDS = {
    "rssi_dbm",
    "noise_dbm",
    "tx_rate_mbps",
    "rx_rate_mbps",
    "latency_ms",
    "latency_min_ms",
    "latency_max_ms",
    "packet_loss",
    "batman_tq",
    "throughput_mbps",
    "sent_mbps",
    "received_mbps",
    "retransmits",
    "route_churn",
    "last_seen_s",
    "clock_offset_ms",
    "duration_s",
    "parallel_streams",
    "port",
    "transmitted",
    "received",
}
BOOLEAN_FIELDS = {"connected", "selected", "reverse", "peer_available", "dry_run", "valid"}


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str
    severity: str = "error"

    def as_dict(self) -> dict[str, str]:
        return {"field": self.field, "message": self.message, "severity": self.severity}


def empty_to_none(value: Any) -> Any:
    if value == "":
        return None
    return value


def coerce_bool(value: Any) -> bool | None:
    value = empty_to_none(value)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    raise ValueError(f"cannot coerce {value!r} to bool")


def coerce_number(value: Any) -> float | int | None:
    value = empty_to_none(value)
    if value is None or isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        number = float(stripped)
        return int(number) if number.is_integer() else number
    raise ValueError(f"cannot coerce {value!r} to number")


def validate_metadata(metadata: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for field in sorted(REQUIRED_METADATA_FIELDS):
        if not metadata.get(field):
            issues.append(ValidationIssue(field, "required run metadata is missing"))
    policy_mode = metadata.get("policy_mode")
    if policy_mode and policy_mode not in ALLOWED_POLICY_MODES:
        issues.append(
            ValidationIssue(
                "policy_mode",
                f"must be one of {', '.join(sorted(ALLOWED_POLICY_MODES))}",
            )
        )
    if "expected_interval_s" in metadata:
        try:
            interval = float(metadata["expected_interval_s"])
            if interval <= 0:
                raise ValueError
        except (TypeError, ValueError):
            issues.append(ValidationIssue("expected_interval_s", "must be a positive number"))
    return issues


def normalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(metadata)
    normalized.setdefault("schema_version", SCHEMA_VERSION)
    normalized.setdefault("created_at", utc_now())
    if "policy_mode" in normalized and isinstance(normalized["policy_mode"], str):
        normalized["policy_mode"] = normalized["policy_mode"].lower()
    return normalized


def normalize_record(
    record: dict[str, Any],
    metadata: dict[str, Any],
    source: str,
    default_event_label: str | None = None,
) -> tuple[dict[str, Any], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    normalized: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "ingested_at": utc_now(),
    }
    normalized.update(record)

    for field in ("experiment_id", "scenario", "policy_mode", "topology_revision"):
        if not normalized.get(field) and metadata.get(field):
            normalized[field] = metadata[field]
    if not normalized.get("event_label"):
        normalized["event_label"] = default_event_label or metadata.get("event_label") or "baseline"

    for field in list(normalized):
        normalized[field] = empty_to_none(normalized[field])

    try:
        normalized["timestamp"] = format_timestamp(parse_timestamp(normalized.get("timestamp")))
    except ValueError as exc:
        issues.append(ValidationIssue("timestamp", str(exc)))

    for field in NUMERIC_FIELDS & set(normalized):
        try:
            normalized[field] = coerce_number(normalized[field])
        except ValueError as exc:
            issues.append(ValidationIssue(field, str(exc)))
    for field in BOOLEAN_FIELDS & set(normalized):
        try:
            normalized[field] = coerce_bool(normalized[field])
        except ValueError as exc:
            issues.append(ValidationIssue(field, str(exc)))

    if isinstance(normalized.get("policy_mode"), str):
        normalized["policy_mode"] = normalized["policy_mode"].lower()
    if isinstance(normalized.get("event_label"), str):
        normalized["event_label"] = normalized["event_label"].lower()

    for field in sorted(REQUIRED_RECORD_FIELDS):
        if normalized.get(field) in (None, ""):
            issues.append(ValidationIssue(field, "required telemetry field is missing"))
    if normalized.get("event_label") not in ALLOWED_EVENT_LABELS:
        issues.append(
            ValidationIssue(
                "event_label",
                f"must be one of {', '.join(sorted(ALLOWED_EVENT_LABELS))}",
            )
        )
    if normalized.get("policy_mode") not in ALLOWED_POLICY_MODES:
        issues.append(
            ValidationIssue(
                "policy_mode",
                f"must be one of {', '.join(sorted(ALLOWED_POLICY_MODES))}",
            )
        )
    return normalized, issues

