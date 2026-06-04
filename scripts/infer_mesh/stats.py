"""Reproducible run metrics and paired analysis utilities."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from statistics import median
from typing import Any

from .timeutils import parse_timestamp


DEFAULT_SUCCESS = {
    "packet_loss": 0.05,
    "latency_ms": 50.0,
    "throughput_mbps": 10.0,
    "stable_samples": 3,
}


def number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _values(records: list[dict[str, Any]], field: str) -> list[float]:
    return [value for record in records if (value := number(record.get(field))) is not None]


def _success(record: dict[str, Any], thresholds: dict[str, float]) -> bool:
    loss = number(record.get("packet_loss"))
    latency = number(record.get("latency_ms"))
    throughput = number(record.get("throughput_mbps") or record.get("received_mbps"))
    if loss is not None and loss > thresholds["packet_loss"]:
        return False
    if latency is not None and latency > thresholds["latency_ms"]:
        return False
    if throughput is not None and throughput < thresholds["throughput_mbps"]:
        return False
    return any(value is not None for value in (loss, latency, throughput))


def route_transition_count(records: list[dict[str, Any]]) -> int:
    explicit = sum(
        1
        for record in records
        if record.get("event_label") in {"route_change", "route_lost", "route_new"}
    )
    by_node_originator: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("next_hop"):
            by_node_originator[(str(record.get("node_id")), str(record.get("originator", "")))].append(record)
    inferred = 0
    for group in by_node_originator.values():
        ordered = sorted(group, key=lambda item: parse_timestamp(item["timestamp"]))
        previous = None
        for record in ordered:
            hop = record.get("next_hop")
            if previous is not None and hop != previous:
                inferred += 1
            previous = hop
    return max(explicit, inferred)


def recovery_time_s(records: list[dict[str, Any]], thresholds: dict[str, float]) -> float | None:
    ordered = sorted(records, key=lambda item: parse_timestamp(item["timestamp"]))
    recovery_start = next(
        (parse_timestamp(record["timestamp"]) for record in ordered if record.get("event_label") == "recovery"),
        None,
    )
    if recovery_start is None:
        return None
    needed = int(thresholds.get("stable_samples", 3))
    streak = 0
    for record in ordered:
        timestamp = parse_timestamp(record["timestamp"])
        if timestamp < recovery_start:
            continue
        if _success(record, thresholds):
            streak += 1
            if streak >= needed:
                return (timestamp - recovery_start).total_seconds()
        else:
            streak = 0
    return None


def run_metrics(records: list[dict[str, Any]], thresholds: dict[str, float] | None = None) -> dict[str, Any]:
    thresholds = {**DEFAULT_SUCCESS, **(thresholds or {})}
    availability_samples = [record for record in records if _success(record, thresholds)]
    measurable_samples = [
        record
        for record in records
        if any(
            number(record.get(field)) is not None
            for field in ("packet_loss", "latency_ms", "throughput_mbps", "received_mbps")
        )
    ]
    latency_values = _values(records, "latency_ms")
    throughput_values = _values(records, "throughput_mbps") + _values(records, "received_mbps")
    loss_values = _values(records, "packet_loss")
    return {
        "sample_count": len(records),
        "availability": round(len(availability_samples) / len(measurable_samples), 6)
        if measurable_samples
        else None,
        "median_latency_ms": round(median(latency_values), 6) if latency_values else None,
        "median_throughput_mbps": round(median(throughput_values), 6) if throughput_values else None,
        "median_packet_loss": round(median(loss_values), 6) if loss_values else None,
        "route_transitions": route_transition_count(records),
        "recovery_time_s": recovery_time_s(records, thresholds),
        "policy_actions": sum(
            1
            for record in records
            if record.get("event_label") in {"adaptation", "policy_decision"}
            or record.get("selected_action")
        ),
    }


def _metric_difference(static: Any, adaptive: Any, higher_is_better: bool) -> float | None:
    if static is None or adaptive is None:
        return None
    diff = float(adaptive) - float(static)
    return diff if higher_is_better else -diff


def paired_differences(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, list[float]]:
    directions = {
        "availability": True,
        "median_latency_ms": False,
        "median_throughput_mbps": True,
        "median_packet_loss": False,
        "route_transitions": False,
        "recovery_time_s": False,
        "policy_actions": False,
    }
    output: dict[str, list[float]] = {metric: [] for metric in directions}
    for static, adaptive in pairs:
        for metric, higher_is_better in directions.items():
            value = _metric_difference(static.get(metric), adaptive.get(metric), higher_is_better)
            if value is not None:
                output[metric].append(value)
    return output


def bootstrap_ci(values: list[float], iterations: int = 2000, seed: int = 7) -> dict[str, float] | None:
    if not values:
        return None
    if len(values) == 1:
        return {"low": values[0], "high": values[0], "mean": values[0]}
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(iterations):
        draw = [values[rng.randrange(len(values))] for _ in values]
        samples.append(sum(draw) / len(draw))
    samples.sort()
    low_index = max(0, math.floor(0.025 * len(samples)) - 1)
    high_index = min(len(samples) - 1, math.ceil(0.975 * len(samples)) - 1)
    return {
        "low": round(samples[low_index], 6),
        "high": round(samples[high_index], 6),
        "mean": round(sum(values) / len(values), 6),
    }


def sign_test_p_value(values: list[float]) -> float | None:
    non_zero = [value for value in values if value != 0]
    n = len(non_zero)
    if n == 0:
        return None
    positives = sum(1 for value in non_zero if value > 0)
    tail = min(positives, n - positives)
    probability = sum(math.comb(n, k) for k in range(tail + 1)) / (2**n)
    return round(min(1.0, 2.0 * probability), 6)


def paired_summary(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    differences = paired_differences(pairs)
    return {
        metric: {
            "n": len(values),
            "benefit_mean": bootstrap_ci(values)["mean"] if values else None,
            "benefit_ci95": bootstrap_ci(values),
            "sign_test_p": sign_test_p_value(values),
        }
        for metric, values in differences.items()
    }


def markdown_report(
    experiment_id: str,
    scenario: str,
    static_metrics: dict[str, Any],
    adaptive_metrics: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    def cell(value: Any) -> str:
        return "" if value is None else str(value)

    rows = []
    for label, key, higher_is_better in [
        ("Availability", "availability", True),
        ("Median latency (ms)", "median_latency_ms", False),
        ("Median throughput (Mbps)", "median_throughput_mbps", True),
        ("Median packet loss", "median_packet_loss", False),
        ("Route transitions", "route_transitions", False),
        ("Recovery time (s)", "recovery_time_s", False),
        ("Policy actions", "policy_actions", False),
    ]:
        static = static_metrics.get(key)
        adaptive = adaptive_metrics.get(key)
        diff = _metric_difference(static, adaptive, higher_is_better)
        interpretation = "positive favors adaptive" if diff is not None else "insufficient data"
        rows.append(f"| {label} | {cell(static)} | {cell(adaptive)} | {cell(diff)} | {interpretation} |")

    stats_rows = [
        "| Metric | N | Mean normalized benefit | 95% CI | Sign-test p |",
        "|---|---:|---:|---|---:|",
    ]
    for metric, payload in summary.items():
        ci = payload.get("benefit_ci95")
        ci_text = "" if not ci else f"[{ci['low']}, {ci['high']}]"
        stats_rows.append(
            f"| {metric} | {payload.get('n', 0)} | {cell(payload.get('benefit_mean'))} | {ci_text} | {cell(payload.get('sign_test_p'))} |"
        )

    return "\n".join(
        [
            f"# Experiment Results: `{experiment_id}`",
            "",
            "## Metadata",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Scenario | {scenario} |",
            "| Policy mode | Static / Adaptive |",
            "",
            "## Results",
            "",
            "| Outcome | Static baseline | Adaptive policy | Difference | Interpretation |",
            "|---|---:|---:|---:|---|",
            *rows,
            "",
            "## Paired Statistics",
            "",
            *stats_rows,
            "",
            "## Anomalies and Exclusions",
            "",
            "Document missing telemetry, unintended interference, failed nodes, invalid runs, and all exclusion criteria applied to observations.",
            "",
            "## Conclusion",
            "",
            "Summarize whether the evidence supports the hypothesis and which follow-up experiment is required.",
            "",
        ]
    )

