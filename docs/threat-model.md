# Threat Model

## Assets

- Continued management access to reclaimed routers
- Valid experimental telemetry and time synchronization
- Isolation of the laboratory mesh from unrelated networks
- Firmware images, configuration backups, and device recovery paths
- Stored MongoDB records and exported results

## Trust Boundaries

| Boundary | Risk | Control |
|---|---|---|
| Controller to OpenWrt nodes | Credential exposure or unintended reconfiguration | Dedicated lab credentials, SSH keys, reviewed inventory |
| Node to collector | Missing or falsified metrics | Timestamp checks, raw exports, cross-check probes |
| Wireless mesh medium | Uncontrolled interference or observation | Isolated tests, record background conditions, avoid sensitive data |
| Experiment policy to network | Excessive/disruptive actions | Bounded actions, rollback access, action logs |
| Storage/export pipeline | Data loss or silent alteration | Raw retention, access controls, checksums/backups |

## Failure and Adversary Cases

| Case | Impact | Mitigation |
|---|---|---|
| Node reboot, power loss, or flash failure | Lost path or inaccessible device | Ethernet recovery path and configuration backup |
| Collector outage | Telemetry gap | Local buffering where feasible and gap annotation |
| Clock drift | Incorrect recovery/churn analysis | NTP synchronization and recorded offsets |
| External RF interference | Confounded results | Channel survey and repeated trials |
| Malformed or spoofed telemetry | Incorrect policy decision | Authenticated management path and sanity checks |
| Policy oscillation | Self-induced route instability | Hysteresis, action cost, minimum observation window |

## Safety Constraints

- Run traffic impairment, packet generation, and node disruptions only on equipment and networks
  explicitly authorized for the experiment.
- Do not intentionally jam radio spectrum or exceed local regulatory transmit-power/channel
  requirements.
- Preserve a wired or recovery route before testing autonomous changes.
- Treat ISP-supplied firmware extraction and flashing according to applicable ownership,
  contract, and device-support constraints.
- Exclude personal or third-party network payload data from captures and stored results.

## Out of Scope

This initial testbed does not aim to defend production networks, detect sophisticated firmware
compromise, or perform offensive wireless testing. Its adversarial scenarios are repeatable,
controlled degradation experiments inside a lab environment.
