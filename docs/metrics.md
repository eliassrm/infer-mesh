# Metrics

## Measurement Contract

All telemetry uses UTC ISO 8601 timestamps and stable `node_id` values from the inventory.
Measurements should also carry `experiment_id`, policy mode, and event label in stored records,
even when a lightweight CSV export omits those fields during initial testing.

## Core Metrics

| Metric | Unit | Source | Interpretation |
|---|---:|---|---|
| `rssi_dbm` | dBm | `iw dev <iface> link` | Received signal strength; less negative is stronger |
| `noise_dbm` | dBm | driver / `iwinfo` where available | RF noise estimate |
| `tx_rate_mbps` | Mbps | `iw` station/link info | Current transmit bitrate |
| `rx_rate_mbps` | Mbps | `iw` station/link info | Current receive bitrate |
| `latency_ms` | ms | `ping` | Round-trip response time |
| `packet_loss` | fraction 0-1 | `ping` | Fraction of probes not returned |
| `batman_tq` | integer 0-255 | `batctl originators` | batman-adv path transmission quality |
| `next_hop` | node/MAC | `batctl originators` | Selected forwarding neighbor |
| `throughput_mbps` | Mbps | `iperf3 --json` | Delivered application throughput |
| `route_churn` | transitions/window | route churn logger | Forwarding changes over time |
| `peer_available` | boolean | mesh station listing | Peer visibility |
| `recovery_time_s` | seconds | event analysis | Time to regain success criterion |

## CSV Starter Schema

The starter sample dataset uses:

```text
timestamp,node_id,rssi_dbm,noise_dbm,tx_rate_mbps,rx_rate_mbps,latency_ms,packet_loss,batman_tq,next_hop,throughput_mbps,event_label
```

Blank values are valid when a probe or driver does not expose the metric. Do not replace
unavailable values with zero because zero is a meaningful observation for loss and throughput.

## Derived Measures

| Measure | Definition |
|---|---|
| Availability | Fraction of samples meeting latency/loss success criteria |
| Route churn rate | Next-hop transitions divided by observation duration |
| Degradation delta | Degradation-window median minus baseline-window median |
| Recovery time | Intervention stop to first stable success window |
| Policy benefit | Matched adaptive outcome minus static outcome, with sign normalized so positive is better |

## Initial Success Criteria

These thresholds are starting assumptions and should be revised from baseline measurements:

| Criterion | Starting threshold |
|---|---:|
| Packet loss | `< 0.05` |
| Median latency | `< 50 ms` |
| Throughput | `> 10 Mbps` |
| batman-adv TQ | `> 150` |
| Stable recovery window | 3 consecutive measurement intervals |
