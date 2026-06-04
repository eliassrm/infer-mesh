from __future__ import annotations

import json
import shutil
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from infer_mesh.orchestrator import ExperimentOrchestrator
from infer_mesh.policy import choose_action
from infer_mesh.quality import run_quality_checks
from infer_mesh.schema import normalize_record
from infer_mesh.security import validate_command_vector
from infer_mesh.stats import paired_summary, run_metrics
from telemetry_ingest import ingest


METADATA = {
    "experiment_id": "unit-run-001",
    "scenario": "packet_loss_recovery",
    "policy_mode": "adaptive",
    "topology_revision": "test-topology",
    "expected_interval_s": 5,
}


@contextmanager
def workspace_tempdir() -> Iterator[str]:
    base = ROOT / "temp" / "unit-tests"
    path = base / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


class WorkflowTests(unittest.TestCase):
    def test_normalize_record_merges_metadata(self) -> None:
        record, issues = normalize_record(
            {
                "timestamp": "2026-05-27T10:00:00Z",
                "node_id": "shg3060",
                "latency_ms": "42.5",
                "packet_loss": "0.01",
            },
            METADATA,
            source="latency",
            default_event_label="baseline",
        )
        self.assertEqual(issues, [])
        self.assertEqual(record["experiment_id"], "unit-run-001")
        self.assertEqual(record["latency_ms"], 42.5)
        self.assertEqual(record["event_label"], "baseline")

    def test_quality_detects_missing_samples(self) -> None:
        records = [
            {
                "timestamp": "2026-05-27T10:00:00Z",
                "node_id": "a",
                "source": "latency",
                "packet_loss": 0,
            },
            {
                "timestamp": "2026-05-27T10:01:00Z",
                "node_id": "a",
                "source": "latency",
                "packet_loss": 0,
            },
        ]
        report = run_quality_checks(records, METADATA)
        self.assertFalse(report["valid"])
        self.assertIn("missing_samples", report["failures"])

    def test_policy_selects_reduced_load_under_congestion(self) -> None:
        decision = choose_action(
            [
                {
                    "timestamp": "2026-05-27T10:00:00Z",
                    "node_id": "a",
                    "event_label": "degradation",
                    "packet_loss": 0.2,
                    "latency_ms": 100,
                    "throughput_mbps": 20,
                    "batman_tq": 220,
                }
            ],
            allowed_actions={"keep_state", "reduce_test_load"},
        )
        self.assertEqual(decision["selected_action"], "reduce_test_load")
        self.assertEqual(decision["summary"]["condition"], "congested")

    def test_ingest_writes_manifest_and_quality_report(self) -> None:
        with workspace_tempdir() as tmp:
            tmp_path = Path(tmp)
            metadata_path = tmp_path / "metadata.json"
            input_path = tmp_path / "telemetry.csv"
            metadata_path.write_text(json.dumps({**METADATA, "policy_mode": "static"}), encoding="utf-8")
            input_path.write_text(
                "\n".join(
                    [
                        "timestamp,node_id,latency_ms,packet_loss,event_label",
                        "2026-05-27T10:00:00Z,a,4.2,0.0,baseline",
                        "2026-05-27T10:00:05Z,a,4.3,0.0,baseline",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            manifest = ingest(metadata_path, [input_path], tmp_path / "runs")
            self.assertTrue(manifest["ok"])
            self.assertEqual(manifest["record_count"], 2)
            self.assertTrue(Path(manifest["telemetry_path"]).exists())

    def test_run_metrics_and_paired_summary(self) -> None:
        static_metrics = run_metrics(
            [
                {
                    "timestamp": "2026-05-27T10:00:00Z",
                    "node_id": "a",
                    "latency_ms": 80,
                    "packet_loss": 0.2,
                    "throughput_mbps": 8,
                    "event_label": "degradation",
                }
            ]
        )
        adaptive_metrics = run_metrics(
            [
                {
                    "timestamp": "2026-05-27T10:00:00Z",
                    "node_id": "a",
                    "latency_ms": 30,
                    "packet_loss": 0.01,
                    "throughput_mbps": 20,
                    "event_label": "degradation",
                }
            ]
        )
        summary = paired_summary([(static_metrics, adaptive_metrics)])
        self.assertGreater(summary["availability"]["benefit_mean"], 0)
        self.assertGreater(summary["median_latency_ms"]["benefit_mean"], 0)

    def test_orchestrator_dry_run_creates_manifest(self) -> None:
        scenario = {
            **METADATA,
            "collectors": [
                {
                    "name": "noop",
                    "command": ["python", "--version"],
                }
            ],
            "phases": [
                {"label": "baseline", "duration_s": 0},
                {"label": "degradation", "duration_s": 0},
                {"label": "recovery", "duration_s": 0},
            ],
        }
        with workspace_tempdir() as tmp:
            manifest = ExperimentOrchestrator(scenario, tmp).run()
            self.assertFalse(manifest["execute"])
            self.assertTrue(Path(manifest["events_path"]).exists())

    def test_command_guardrails_block_destructive_executable(self) -> None:
        with self.assertRaises(ValueError):
            validate_command_vector(["rm", "-rf", "/tmp/infer-mesh"])


if __name__ == "__main__":
    unittest.main()
