# Active-Inference Model

## Scope

This testbed uses an active-inference-inspired policy layer, not a claim that a complete
biological active inference implementation is necessary for routing. The model should be
evaluated against a static baseline using the same measured interventions.

## Variables

| Symbol | Meaning | Observed through |
|---|---|---|
| `o_t` | Observation at time `t` | RSSI, TQ, loss, latency, throughput, next hop |
| `s_t` | Latent network condition | stable, congested, weak-link, node-failed, recovering |
| `a_t` | Action | keep state, reroute, reduce load, change approved link setting |
| `pi` | Candidate policy | bounded sequence of actions |
| `C(o)` | Preferred outcomes | high availability/TQ/throughput, low loss/latency/churn |

## Observation Vector

For a node at each interval:

```text
o_t = [normalized_rssi, normalized_tq, packet_loss,
       normalized_latency, normalized_throughput, route_changed]
```

Normalization parameters must be recorded with an experiment so policy behavior can be
reproduced.

## Minimal Generative Model

Start with a discrete-state transition and observation model:

```text
P(s_t | s_(t-1), a_(t-1)) = B[a_(t-1)]
P(o_t | s_t)               = A
P(s_0)                     = D
```

`A`, `B`, and `D` may initially be estimated from baseline and controlled-degradation trials.
Later experiments can update the estimates between runs, but should not silently train on the
same test episode being reported.

## Policy Score

For candidate policy `pi`, select the lowest expected free energy score:

```text
G(pi) = risk(pi) + uncertainty(pi) + action_cost(pi)
```

Where:

- `risk(pi)` penalizes predicted outcomes inconsistent with service preferences, such as high
  packet loss or unavailable peers.
- `uncertainty(pi)` penalizes outcomes with weak evidence or highly uncertain network state.
- `action_cost(pi)` avoids needless channel, power, or path changes that themselves create
  instability.

The starter implementation in `scripts/policy_engine.py` uses documented weighted terms before
a learned probabilistic model is available:

```text
score(a) = w_loss * predicted_loss
         + w_latency * predicted_latency
         - w_tq * predicted_tq
         + w_churn * expected_route_change
         + w_action * action_cost
```

## Decision Loop

1. Ingest a sliding telemetry window.
2. Estimate current condition and observation confidence.
3. Score only actions allowed by the experiment configuration.
4. Apply one action, log its score and reason, and wait for an evaluation window.
5. Compare observations to predictions and record outcome.

`scripts/experiment_orchestrator.py` runs this loop when a scenario uses
`"policy_mode": "adaptive"`. The orchestrator writes policy decisions as `policy_decision`
records and applies configured policy commands only when `--execute` is supplied and the
scenario approval token matches.

## Evaluation

The policy is useful only if paired runs show measurable gains without unacceptable churn or
action cost. Report availability, throughput, loss, recovery time, route transitions, policy
actions per hour, and prediction error for both adaptive and static modes.
