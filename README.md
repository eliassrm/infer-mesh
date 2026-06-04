# INFER-MESH

Active-inference testbed for resilient OpenWrt mesh networks using reclaimed ISP CPE routers.

## Objective

Evaluate how heterogeneous low-cost mesh nodes behave under degraded RF conditions, packet
loss, route instability, and node failure. Compare baseline mesh behavior against adaptive
autonomous policies inspired by active inference.

## Hardware

| Device | Role |
|---|---|
| Vodafone SHG3060 | Mesh node A |
| Vodafone SHG3000 | Mesh node B |
| Vodafone SHG2500 | Adversarial / degraded-link node |
| Home&Life WD300 | Telemetry collector / edge controller |
| TP-Link TL-WR841ND | Legacy mesh / edge node |
| Laptop | Experiment controller |

## Software Stack

- OpenWrt
- 802.11s
- batman-adv
- Python 3
- Ansible
- MongoDB
- iperf3
- tcpdump
- `iw` / `iwinfo`

## Metrics

- RSSI and noise floor
- Latency and packet loss
- Throughput
- Route churn and mesh peer availability
- batman-adv transmission quality (TQ)
- Recovery time after disruption

## Research Question

Can active-inference-inspired policy selection improve mesh resilience by choosing actions that
minimize expected uncertainty under degraded network conditions?

## Experiment Classes

1. Baseline mesh with stable links
2. Mesh under packet loss
3. Mesh under node failure
4. Mesh under route instability
5. Mesh under controlled adversarial degradation
6. Adaptive policy versus static configuration

## Repository Layout

| Path | Purpose |
|---|---|
| `docs/` | Architecture, experimental method, model, risks, and reporting template |
| `ansible/` | Starter inventory and OpenWrt/telemetry provisioning playbooks |
| `scripts/` | Standalone metric collectors, ingestion, policy, orchestration, and analysis utilities |
| `data/` | Example experiment record format |
| `notebooks/` | Analysis starting point for resilience metrics |
| `diagrams/` | Editable topology diagram |

## Getting Started

1. Record device firmware, radios, and management addresses in
   `docs/hardware-inventory.md` and `ansible/inventory.ini`. Opt capable nodes into the
   `telemetry_nodes` group only after checking capacity for Python.
2. Confirm OpenWrt and package compatibility on each device before provisioning.
3. Review mesh parameters in `ansible/openwrt-mesh.yml`, then apply them from the controller:

   ```bash
   ansible-playbook -i ansible/inventory.ini ansible/openwrt-mesh.yml
   ansible-playbook -i ansible/inventory.ini ansible/telemetry-agent.yml
   ```

4. Run collectors on a node or the collector host:

   ```bash
   python3 scripts/collect_iw_metrics.py --node-id shg3060 --interface mesh0 --format csv
   python3 scripts/latency_probe.py --node-id shg3060 --target 192.168.50.12 --format csv
   python3 scripts/iperf_sweep.py --node-id shg3060 --server 192.168.50.20
   ```

5. Ingest collector output into a run-level dataset with metadata, validation, quality checks,
   and optional HMAC signing:

   ```bash
   python3 scripts/telemetry_ingest.py \
     --metadata data/run-metadata.example.json \
     --input data/sample_experiment.csv \
     --output-dir data/runs
   ```

6. Run a controller scenario in dry-run mode first. Add `--execute` and a matching
   `--approval-token` only for reviewed lab actions:

   ```bash
   python3 scripts/experiment_orchestrator.py \
     --scenario data/scenarios/packet_loss_recovery.json \
     --output-dir data/runs
   ```

7. Generate a paired static/adaptive report:

   ```bash
   python3 scripts/paired_analysis.py \
     --static data/sample_experiment.csv \
     --adaptive data/sample_experiment.csv \
     --output docs/results-template.md
   ```

8. Use `data/sample_experiment.csv` and
   `notebooks/mesh_resilience_analysis.ipynb` as the starting analysis contract.

## Safety Boundary

Degradation experiments are intended for an isolated lab mesh owned or authorized by the
operator. Do not create RF interference or disruptive traffic on third-party networks. The
project threat and safety assumptions are documented in `docs/threat-model.md`.

## Status

Initial topology design, provisioning scaffold, telemetry instrumentation, adaptive policy
scoring, experiment orchestration, ingestion, quality checks, and paired-run reporting.
