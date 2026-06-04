# Where To Start

Start with dry runs and sample data before touching real mesh devices. The goal is to verify the controller workflow, telemetry contract, and reports first.

## 1. Check The Repo

Run the tests:

```powershell
python -m unittest discover -s tests
```

If these pass, the local scripts are working.

## 2. Review Run Metadata

Open:

```text
data/run-metadata.example.json
```

Update it for your real run:

- `experiment_id`
- `scenario`
- `policy_mode`
- `topology_revision`
- node list
- expected telemetry interval

Keep this file accurate because ingestion, quality checks, and reports depend on it.

## 3. Dry-Run A Scenario

Start with:

```powershell
python scripts\experiment_orchestrator.py --scenario data\scenarios\packet_loss_recovery.json --output-dir data\runs
```

This does not execute device commands. It validates the scenario flow and writes controller outputs under `data/runs/<experiment_id>/`.

Inspect:

```text
events.jsonl
commands.jsonl
orchestrator_manifest.json
```

## 4. Ingest Telemetry

Test ingestion with the sample dataset:

```powershell
python scripts\telemetry_ingest.py --metadata data\run-metadata.example.json --input data\sample_experiment.csv --output-dir data\runs
```

Inspect:

```text
telemetry.jsonl
run_metadata.json
quality_report.json
invalid_records.json
ingest_manifest.json
```

Do not move to real experiments until `invalid_records.json` is empty and `quality_report.json` says the run is valid.

## 5. Try The Policy Engine

Run the adaptive policy scorer against sample telemetry:

```powershell
python scripts\policy_engine.py --telemetry data\sample_experiment.csv --allowed-actions keep_state,reduce_test_load,prefer_stronger_path
```

Check the selected action, scores, predicted metrics, and reason.

## 6. Generate A Report

Use paired analysis to produce a first report:

```powershell
python scripts\paired_analysis.py --static data\sample_experiment.csv --adaptive data\sample_experiment.csv --output docs\results-template.md
```

Later, replace the sample file with real static and adaptive run exports.

## 7. Prepare Real Hardware Runs

Before using `--execute`:

- Fill in `ansible/inventory.ini` with verified device addresses and radio names.
- Replace placeholder scenario approval tokens.
- Review every scenario command in `data/scenarios/`.
- Keep recovery access to each router.
- Confirm degradation actions are limited to the isolated lab mesh.

Use real execution only after dry-run outputs look correct:

```powershell
python scripts\experiment_orchestrator.py --scenario data\scenarios\packet_loss_recovery.json --output-dir data\runs --execute --approval-token <your-token>
```

## Recommended First Milestone

Complete one full loop using sample data:

1. Run tests.
2. Dry-run `packet_loss_recovery.json`.
3. Ingest `data/sample_experiment.csv`.
4. Run the policy engine.
5. Generate a report.

After that, replace sample data and placeholder commands with your actual lab setup.
