# Architecture

## Logical Topology

The laptop controller starts experiments, provisions OpenWrt nodes, and retrieves exported
datasets. The Home&Life WD300 acts as the telemetry collector and MongoDB gateway.

SHG3060, SHG3000, and TL-WR841ND form the mesh backbone. SHG2500 is a controlled degradation
node used to produce observable link or traffic stress inside the lab network.

```text
                     management / experiment control
   Laptop controller -------------------------------- WD300 collector
          |                                              |
          | SSH / Ansible                       MongoDB / exports
          v                                              |
   SHG3060  <~~~~ 802.11s + batman-adv ~~~~>  SHG3000   |
       \                                             /    |
        \~~~~~~~~~~~~~~> TL-WR841ND <~~~~~~~~~~~~~~/     |
                         ^
                         |
                 SHG2500 degradation node
```

## Network Layers

| Layer | Function | Example observables |
|---|---|---|
| Physical/RF | Link quality, attenuation, channel noise | RSSI, noise floor |
| MAC | 802.11s peering | station/peer availability |
| Mesh routing | batman-adv forwarding decisions | originator, next hop, TQ |
| Transport/test load | Repeatable reachability and capacity probes | ping, iperf3 |
| Telemetry | Collection and event annotation | Python agents, timestamps |
| Storage | Experiment record persistence | MongoDB, CSV exports |
| Control | Provisioning and experiment sequencing | Ansible, controller scripts |
| Policy | Adaptive action selection | expected-free-energy score |

## Node Roles

### Mesh Node

Runs OpenWrt, an 802.11s mesh interface, batman-adv, and lightweight telemetry commands. A
mesh node forwards traffic while periodically reporting radio, routing, and probe metrics.

### Collector Node

Receives telemetry from nodes, stores experiment documents, and provides exports for analysis.
Collection must continue independently from adaptive decisions so comparisons remain auditable.

### Degradation Node

Introduces controlled degradation through test traffic, packet-loss shaping, link withdrawal,
or physical attenuation in an authorized environment. It must not intentionally interfere with
unrelated wireless networks.

## Proposed Addressing

The starter inventory reserves a management subnet and a batman-adv interface address space.
Replace addresses to match the isolated lab before running provisioning.

| Node | Management address | Mesh/BAT interface address |
|---|---:|---:|
| WD300 collector | `192.168.50.20` | `10.10.0.20` |
| SHG3060 | `192.168.50.11` | `10.10.0.11` |
| SHG3000 | `192.168.50.12` | `10.10.0.12` |
| SHG2500 | `192.168.50.13` | `10.10.0.13` |
| TL-WR841ND | `192.168.50.14` | `10.10.0.14` |

## Data Flow

1. The controller records an experiment identifier and event schedule.
2. Nodes collect local radio and batman-adv observations.
3. Probe utilities measure latency, loss, and throughput against defined endpoints.
4. Telemetry is sent to or exported through the collector.
5. Analysis calculates degradation and recovery outcomes for baseline and adaptive runs.
