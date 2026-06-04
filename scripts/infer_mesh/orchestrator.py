"""Experiment orchestration primitives for controller-side runs."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from .io import write_json
from .policy import choose_action
from .schema import normalize_metadata, normalize_record
from .security import validate_command_vector
from .timeutils import utc_now


class SafetyError(RuntimeError):
    """Raised when a scenario action violates controller guardrails."""


def load_scenario(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError("scenario file must contain a JSON object")
    return payload


def validate_scenario(scenario: dict[str, Any]) -> None:
    for field in ("experiment_id", "scenario", "policy_mode", "topology_revision", "phases"):
        if not scenario.get(field):
            raise ValueError(f"scenario is missing required field {field!r}")
    if scenario["policy_mode"] not in {"static", "adaptive", "dry-run", "manual"}:
        raise ValueError("policy_mode must be static, adaptive, dry-run, or manual")
    if not isinstance(scenario["phases"], list) or not scenario["phases"]:
        raise ValueError("scenario phases must be a non-empty list")
    for phase in scenario["phases"]:
        if phase.get("label") not in {"baseline", "degradation", "recovery"}:
            raise ValueError("phase labels must be baseline, degradation, or recovery")
        if float(phase.get("duration_s", 0)) < 0:
            raise ValueError("phase duration_s must be non-negative")


def _render(value: str, context: dict[str, Any]) -> str:
    return value.format(**{key: str(item) for key, item in context.items()})


def _render_command(command: list[str], context: dict[str, Any]) -> list[str]:
    return [_render(part, context) for part in command]


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True, separators=(",", ":"), default=str))
        stream.write("\n")


def _event(metadata: dict[str, Any], label: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "timestamp": utc_now(),
        "node_id": "controller",
        "event_label": label,
        "experiment_id": metadata["experiment_id"],
        "scenario": metadata["scenario"],
        "policy_mode": metadata["policy_mode"],
        "topology_revision": metadata["topology_revision"],
        "source": "experiment_orchestrator",
    }
    if details:
        payload.update(details)
    return payload


def _ensure_action_allowed(
    action: dict[str, Any],
    scenario: dict[str, Any],
    execute: bool,
    approval_token: str | None,
) -> None:
    action_id = action.get("id")
    allowed = set(scenario.get("allowed_interventions", [])) | set(scenario.get("allowed_policy_actions", []))
    if action_id and allowed and action_id not in allowed:
        raise SafetyError(f"action {action_id!r} is not in the scenario allowlist")
    if execute and action.get("requires_approval", True):
        expected = scenario.get("safety", {}).get("approval_token")
        if not expected or approval_token != expected:
            raise SafetyError(f"action {action_id!r} requires a matching approval token")
    if "command" in action:
        validate_command_vector(action["command"])


class ExperimentOrchestrator:
    def __init__(
        self,
        scenario: dict[str, Any],
        output_dir: str | Path,
        execute: bool = False,
        approval_token: str | None = None,
    ) -> None:
        validate_scenario(scenario)
        self.scenario = scenario
        self.metadata = normalize_metadata(
            {
                key: scenario[key]
                for key in (
                    "experiment_id",
                    "scenario",
                    "policy_mode",
                    "topology_revision",
                    "operator",
                    "expected_interval_s",
                    "nodes",
                    "quality_thresholds",
                )
                if key in scenario
            }
        )
        self.execute = execute
        self.approval_token = approval_token
        self.run_dir = Path(output_dir) / str(scenario["experiment_id"])
        self.telemetry_path = self.run_dir / "telemetry.jsonl"
        self.events_path = self.run_dir / "events.jsonl"
        self.commands_path = self.run_dir / "commands.jsonl"

    def run(self) -> dict[str, Any]:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        write_json(self.run_dir / "scenario.json", self.scenario)
        write_json(self.run_dir / "run_metadata.json", self.metadata)
        _append_jsonl(self.events_path, _event(self.metadata, "phase_start", {"phase": "run"}))
        for phase in self.scenario["phases"]:
            self._run_phase(phase)
        _append_jsonl(self.events_path, _event(self.metadata, "phase_end", {"phase": "run"}))
        manifest = {
            "experiment_id": self.metadata["experiment_id"],
            "execute": self.execute,
            "run_dir": str(self.run_dir),
            "telemetry_path": str(self.telemetry_path),
            "events_path": str(self.events_path),
            "commands_path": str(self.commands_path),
        }
        write_json(self.run_dir / "orchestrator_manifest.json", manifest)
        return manifest

    def _run_phase(self, phase: dict[str, Any]) -> None:
        label = phase["label"]
        context = {
            **self.metadata,
            **phase,
            "phase": label,
            "event_label": label,
            "run_dir": str(self.run_dir),
        }
        _append_jsonl(self.events_path, _event(self.metadata, "phase_start", {"phase": label}))
        for intervention in phase.get("start_interventions", []) + phase.get("interventions", []):
            self._run_action(intervention, context, action_type="intervention")

        duration_s = 0.0 if not self.execute else float(phase.get("duration_s", 0))
        interval_s = float(phase.get("collector_interval_s", self.scenario.get("expected_interval_s", 5)))
        deadline = time.monotonic() + duration_s
        first = True
        while first or time.monotonic() < deadline:
            first = False
            for collector in phase.get("collectors", self.scenario.get("collectors", [])):
                self._run_collector(collector, context)
            if self.scenario["policy_mode"] == "adaptive" and phase.get("policy_enabled", True):
                self._run_policy(context)
            remaining = deadline - time.monotonic()
            if remaining <= 0 or duration_s == 0:
                break
            time.sleep(min(interval_s, remaining))

        for intervention in phase.get("end_interventions", []):
            self._run_action(intervention, context, action_type="intervention")
        _append_jsonl(self.events_path, _event(self.metadata, "phase_end", {"phase": label}))

    def _run_action(self, action: dict[str, Any], context: dict[str, Any], action_type: str) -> None:
        _ensure_action_allowed(action, self.scenario, self.execute, self.approval_token)
        command = action.get("command")
        rendered = _render_command(command, context) if command else None
        command_record = _event(
            self.metadata,
            "adaptation" if action_type == "policy" else context["event_label"],
            {
                "action_type": action_type,
                "action_id": action.get("id"),
                "dry_run": not self.execute,
                "command": rendered,
            },
        )
        if rendered and self.execute:
            result = subprocess.run(rendered, capture_output=True, text=True, check=False)
            command_record.update(
                {
                    "returncode": result.returncode,
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                }
            )
            if result.returncode != 0:
                command_record["event_label"] = "failure"
        _append_jsonl(self.commands_path, command_record)
        _append_jsonl(self.events_path, command_record)

    def _run_collector(self, collector: dict[str, Any], context: dict[str, Any]) -> None:
        command = validate_command_vector(collector.get("command"))
        rendered = _render_command(command, context)
        record = _event(
            self.metadata,
            context["event_label"],
            {
                "collector": collector.get("name", rendered[0]),
                "dry_run": not self.execute,
                "command": rendered,
            },
        )
        if not self.execute:
            _append_jsonl(self.events_path, record)
            return
        result = subprocess.run(rendered, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            record.update({"event_label": "failure", "returncode": result.returncode, "stderr": result.stderr.strip()})
            _append_jsonl(self.events_path, record)
            return
        for line_index, line in enumerate(result.stdout.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                _append_jsonl(
                    self.events_path,
                    {
                        **record,
                        "event_label": "failure",
                        "line": line_index,
                        "error": "collector emitted non-JSON output",
                    },
                )
                continue
            normalized, issues = normalize_record(
                payload,
                self.metadata,
                source=str(collector.get("name", rendered[0])),
                default_event_label=context["event_label"],
            )
            if issues:
                _append_jsonl(
                    self.events_path,
                    {
                        **record,
                        "event_label": "failure",
                        "line": line_index,
                        "issues": [issue.as_dict() for issue in issues],
                    },
                )
                continue
            _append_jsonl(self.telemetry_path, normalized)

    def _run_policy(self, context: dict[str, Any]) -> None:
        if not self.telemetry_path.exists():
            return
        records: list[dict[str, Any]] = []
        with self.telemetry_path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    records.append(json.loads(line))
        if not records:
            return
        policy = self.scenario.get("policy", {})
        allowed = set(self.scenario.get("allowed_policy_actions", [])) or None
        decision = choose_action(
            records,
            config=policy,
            allowed_actions=allowed,
            window_s=float(policy.get("window_s", 60.0)),
        )
        decision_record = {
            **_event(self.metadata, "policy_decision", {"phase": context["phase"]}),
            **decision,
        }
        _append_jsonl(self.telemetry_path, decision_record)
        _append_jsonl(self.events_path, decision_record)
        selected = decision["selected_action"]
        action = next(
            (
                candidate
                for candidate in self.scenario.get("policy_actions", [])
                if candidate.get("id") == selected and candidate.get("command")
            ),
            None,
        )
        if action and selected != "keep_state":
            self._run_action(action, context, action_type="policy")
