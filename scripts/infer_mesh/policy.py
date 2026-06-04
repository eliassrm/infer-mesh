"""Adaptive policy selection for mesh experiments."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any

from .timeutils import parse_timestamp, utc_now


DEFAULT_WEIGHTS = {
    "loss": 4.0,
    "latency": 1.5,
    "tq_deficit": 1.5,
    "throughput_deficit": 1.0,
    "route_churn": 1.0,
    "uncertainty": 0.8,
    "action_cost": 1.0,
}
DEFAULT_TARGETS = {
    "packet_loss": 0.05,
    "latency_ms": 50.0,
    "throughput_mbps": 10.0,
    "batman_tq": 150.0,
}
DEFAULT_ACTIONS = [
    {
        "id": "keep_state",
        "description": "Keep the current mesh configuration.",
        "cost": 0.0,
        "effects": {},
    },
    {
        "id": "reduce_test_load",
        "description": "Reduce authorized test traffic load until the next evaluation window.",
        "cost": 0.15,
        "effects": {"packet_loss": -0.04, "latency_factor": 0.85, "throughput_factor": 0.9},
    },
    {
        "id": "prefer_stronger_path",
        "description": "Shift approved test flow or mesh weighting toward the strongest observed path.",
        "cost": 0.35,
        "effects": {"packet_loss": -0.025, "latency_factor": 0.9, "batman_tq": 25, "route_churn": 1.0},
    },
    {
        "id": "restore_defaults",
        "description": "Return reversible test changes to the configured baseline state.",
        "cost": 0.2,
        "effects": {"route_churn": 0.5},
        "prefer_during": ["recovery"],
    },
]


@dataclass(frozen=True)
class ObservationSummary:
    count: int
    condition: str
    confidence: float
    packet_loss: float | None
    latency_ms: float | None
    throughput_mbps: float | None
    batman_tq: float | None
    route_churn: float
    event_label: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "condition": self.condition,
            "confidence": self.confidence,
            "packet_loss": self.packet_loss,
            "latency_ms": self.latency_ms,
            "throughput_mbps": self.throughput_mbps,
            "batman_tq": self.batman_tq,
            "route_churn": self.route_churn,
            "event_label": self.event_label,
        }


def _numbers(records: list[dict[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for record in records:
        value = record.get(field)
        if isinstance(value, (int, float)):
            values.append(float(value))
        elif isinstance(value, str) and value.strip():
            try:
                values.append(float(value))
            except ValueError:
                continue
    return values


def recent_window(records: list[dict[str, Any]], window_s: float) -> list[dict[str, Any]]:
    if not records:
        return []
    ordered = sorted(records, key=lambda record: parse_timestamp(record["timestamp"]))
    latest = parse_timestamp(ordered[-1]["timestamp"])
    return [
        record
        for record in ordered
        if (latest - parse_timestamp(record["timestamp"])).total_seconds() <= window_s
    ]


def summarize_observations(records: list[dict[str, Any]], targets: dict[str, float]) -> ObservationSummary:
    losses = _numbers(records, "packet_loss")
    latencies = _numbers(records, "latency_ms")
    throughputs = _numbers(records, "throughput_mbps") + _numbers(records, "received_mbps")
    tqs = _numbers(records, "batman_tq")
    labels = [record.get("event_label") for record in records if isinstance(record.get("event_label"), str)]
    route_churn = sum(1 for record in records if record.get("event_label") in {"route_change", "route_lost"})

    packet_loss = mean(losses) if losses else None
    latency_ms = mean(latencies) if latencies else None
    throughput_mbps = mean(throughputs) if throughputs else None
    batman_tq = mean(tqs) if tqs else None
    missing_metric_groups = sum(
        metric is None for metric in (packet_loss, latency_ms, throughput_mbps, batman_tq)
    )
    variability = 0.0
    if len(losses) > 1:
        variability += pstdev(losses)
    if len(latencies) > 1 and targets["latency_ms"] > 0:
        variability += min(1.0, pstdev(latencies) / targets["latency_ms"])
    confidence = max(0.05, min(1.0, 1.0 - (missing_metric_groups * 0.18) - (variability * 0.2)))

    condition = "stable"
    if packet_loss is not None and packet_loss >= 0.95:
        condition = "node_failed"
    elif batman_tq is not None and batman_tq < targets["batman_tq"]:
        condition = "weak_link"
    elif latency_ms is not None and latency_ms > targets["latency_ms"]:
        condition = "congested"
    elif packet_loss is not None and packet_loss > targets["packet_loss"]:
        condition = "congested"
    if labels and labels[-1] == "recovery" and condition == "stable":
        condition = "recovering"

    return ObservationSummary(
        count=len(records),
        condition=condition,
        confidence=round(confidence, 4),
        packet_loss=round(packet_loss, 6) if packet_loss is not None else None,
        latency_ms=round(latency_ms, 3) if latency_ms is not None else None,
        throughput_mbps=round(throughput_mbps, 3) if throughput_mbps is not None else None,
        batman_tq=round(batman_tq, 3) if batman_tq is not None else None,
        route_churn=float(route_churn),
        event_label=labels[-1] if labels else None,
    )


def load_policy_config(config: dict[str, Any] | None) -> dict[str, Any]:
    config = config or {}
    weights = dict(DEFAULT_WEIGHTS)
    weights.update(config.get("weights", {}))
    targets = dict(DEFAULT_TARGETS)
    targets.update(config.get("targets", {}))
    actions = config.get("actions") or DEFAULT_ACTIONS
    return {"weights": weights, "targets": targets, "actions": actions}


def _bounded_loss(value: float | None) -> float:
    return min(1.0, max(0.0, 0.0 if value is None else value))


def _bounded_positive(value: float | None) -> float:
    return max(0.0, 0.0 if value is None else value)


def predict_after_action(summary: ObservationSummary, action: dict[str, Any]) -> dict[str, float]:
    effects = action.get("effects", {}) if isinstance(action.get("effects"), dict) else {}
    packet_loss = _bounded_loss(summary.packet_loss)
    latency_ms = _bounded_positive(summary.latency_ms)
    throughput_mbps = _bounded_positive(summary.throughput_mbps)
    batman_tq = _bounded_positive(summary.batman_tq)
    route_churn = _bounded_positive(summary.route_churn)

    packet_loss = _bounded_loss(packet_loss + float(effects.get("packet_loss", 0.0)))
    latency_ms = latency_ms * float(effects.get("latency_factor", 1.0)) + float(effects.get("latency_ms", 0.0))
    throughput_mbps = throughput_mbps * float(effects.get("throughput_factor", 1.0)) + float(
        effects.get("throughput_mbps", 0.0)
    )
    batman_tq = max(0.0, min(255.0, batman_tq + float(effects.get("batman_tq", 0.0))))
    route_churn = route_churn + float(effects.get("route_churn", 0.0))
    return {
        "packet_loss": round(packet_loss, 6),
        "latency_ms": round(max(0.0, latency_ms), 3),
        "throughput_mbps": round(max(0.0, throughput_mbps), 3),
        "batman_tq": round(batman_tq, 3),
        "route_churn": round(max(0.0, route_churn), 3),
    }


def score_action(
    summary: ObservationSummary,
    action: dict[str, Any],
    weights: dict[str, float],
    targets: dict[str, float],
) -> dict[str, Any]:
    prediction = predict_after_action(summary, action)
    loss_term = prediction["packet_loss"]
    latency_term = prediction["latency_ms"] / targets["latency_ms"] if targets["latency_ms"] else 0.0
    tq_term = max(0.0, (targets["batman_tq"] - prediction["batman_tq"]) / targets["batman_tq"])
    throughput_term = max(
        0.0,
        (targets["throughput_mbps"] - prediction["throughput_mbps"]) / targets["throughput_mbps"],
    )
    churn_term = prediction["route_churn"]
    uncertainty_term = 1.0 - summary.confidence
    action_cost = float(action.get("cost", 0.0))
    if action.get("prefer_during") and summary.event_label not in action.get("prefer_during", []):
        action_cost += 0.5

    risk = (
        weights["loss"] * loss_term
        + weights["latency"] * latency_term
        + weights["tq_deficit"] * tq_term
        + weights["throughput_deficit"] * throughput_term
    )
    uncertainty = weights["uncertainty"] * uncertainty_term
    cost = weights["route_churn"] * churn_term + weights["action_cost"] * action_cost
    return {
        "action_id": action["id"],
        "score": round(risk + uncertainty + cost, 6),
        "risk": round(risk, 6),
        "uncertainty": round(uncertainty, 6),
        "action_cost": round(cost, 6),
        "prediction": prediction,
        "description": action.get("description", ""),
    }


def choose_action(
    records: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
    allowed_actions: set[str] | None = None,
    window_s: float = 60.0,
) -> dict[str, Any]:
    policy_config = load_policy_config(config)
    window = recent_window(records, window_s)
    summary = summarize_observations(window, policy_config["targets"])
    actions = [
        action
        for action in policy_config["actions"]
        if isinstance(action, dict)
        and action.get("id")
        and (allowed_actions is None or action["id"] in allowed_actions)
    ]
    if not actions:
        actions = [DEFAULT_ACTIONS[0]]
    scores = [
        score_action(summary, action, policy_config["weights"], policy_config["targets"])
        for action in actions
    ]
    selected = min(scores, key=lambda item: item["score"])
    reason = (
        f"{selected['action_id']} has the lowest expected free energy score "
        f"under {summary.condition} observations"
    )
    if summary.condition == "stable" and selected["action_id"] != "keep_state":
        keep = next((score for score in scores if score["action_id"] == "keep_state"), None)
        if keep and (selected["score"] + 0.25) >= keep["score"]:
            selected = keep
            reason = "keep_state is preferred because observations are stable and intervention margin is small"
    return {
        "timestamp": utc_now(),
        "event_label": "policy_decision",
        "summary": summary.as_dict(),
        "selected_action": selected["action_id"],
        "reason": reason,
        "scores": sorted(scores, key=lambda item: item["score"]),
    }
