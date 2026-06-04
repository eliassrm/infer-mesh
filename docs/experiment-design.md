# Experiment Design

## Goal

Measure whether an adaptive policy can retain usable mesh service and recover more quickly than
a static mesh configuration under controlled degradation.

## Comparison

Each scenario is run with two configurations:

| Configuration | Description |
|---|---|
| Static baseline | Fixed channel, transmit power, routing parameters, and probe schedule |
| Adaptive policy | Selects from approved configuration actions using current observations |

Use the same topology, traffic workload, degradation schedule, and observation interval for
each paired comparison.

## Experiment Classes

| Class | Intervention | Primary outcome |
|---|---|---|
| Stable baseline | No intentional degradation | Normal latency/throughput distribution |
| Packet loss | Traffic shaping on an owned link or node | Loss and TQ response |
| Node failure | Power down or administratively disable one forwarding node | Recovery time |
| Route instability | Controlled link toggling or metric perturbation | Route churn |
| Degraded link | Attenuation, distance, or isolated test load | RSSI/TQ/throughput relation |
| Policy comparison | Replay matched interventions in both modes | Resilience improvement |

## Run Protocol

1. Assign an `experiment_id`, scenario, topology revision, firmware versions, policy mode,
   and intervention schedule before collection begins.
2. Synchronize node clocks using NTP or record measured clock offset.
3. Collect at least five minutes of baseline telemetry.
4. Introduce one predefined intervention and annotate its exact UTC start and stop times.
5. Continue measurement through degradation and a recovery window.
6. Export raw records before cleaning or aggregating them.
7. Reset configuration and repeat sufficiently to estimate variation between runs.

The controller implementation is `scripts/experiment_orchestrator.py`. Scenario definitions live
under `data/scenarios/` and cover packet-loss recovery, multi-hop scaling, mobility/interference
replay, and cross-device benchmarking. The orchestrator is dry-run by default and records
controller events in `events.jsonl`, command attempts in `commands.jsonl`, and wrapped collector
records in `telemetry.jsonl`.

## Event Labels

Use stable event labels in collected records:

| Label | Meaning |
|---|---|
| `baseline` | Pre-intervention normal operation |
| `degradation` | Intended intervention is active |
| `recovery` | Intervention removed, network converging |
| `adaptation` | Policy action applied |
| `failure` | Unplanned outage or invalid test condition |

Controller-generated event labels also include `phase_start`, `phase_end`, and
`policy_decision`. Route churn collectors may emit `route_new`, `route_lost`, and
`route_change`.

## Controlled Actions

Adaptive experiments should initially select only reversible actions:

| Action | Bound |
|---|---|
| Select alternate path/interface weighting | Allowed values recorded in run metadata |
| Change test flow routing | No third-party destination |
| Reduce offered test load | Within isolated network |
| Change channel or transmit setting | Regulatory and device limits apply |
| Withdraw/rejoin a designated node | Recovery access retained |

Guarded degradation actions can be applied with `ansible/degradation-actions.yml`. The playbook
requires `experiment_id` and a matching `degradation_confirm` value, limits packet loss to
1-30 percent, and supports only `inspect`, `start_loss`, and `clear_loss`.

## Validity Controls

- Keep device placement, power supplies, firmware, and antenna orientation constant within paired
  runs.
- Record background channel occupancy where practical.
- Separate planned interventions from unplanned device or collector failures.
- Do not compare policy modes using unmatched degradation severity.
- Store raw time series and policy decisions so aggregate claims can be reproduced.
