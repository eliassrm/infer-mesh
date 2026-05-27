# TP-Link TL-WR841ND ver 7.2 Hardware Profile

## Role in INFER-MESH

The TL-WR841ND is used as a constrained legacy mesh participant for evaluating resilience under low-memory, low-flash embedded conditions. It represents the weakest OpenWrt-class node in the testbed and is useful for observing how routing, telemetry, and control policies behave on resource-limited hardware.

## Physical Identity

- Model: TP-Link TL-WR841ND
- Hardware version: 7.2
- PCB marking: 2050500124 rev 1.0
- PCB date/silscreen: GFP2011/ 2008  
- Serial number: 12170006784
- MAC address: REDACTED
- Power input rating: 9V | 0.6A
- Antenna type: detachable external antennas

## Silicon

| Subsystem | Marking | Notes |
|---|---|---|
| SoC | Atheros AR7241-AH1A | Main router CPU / MIPS-class embedded SoC |
| Wi-Fi | Atheros AR9287-class, marking partially visible | 2.4 GHz 802.11n radio, likely ath9k-compatible |
| RAM | Winbond W9425G6JH-5 | Expected 32 MB RAM class; verify from boot log |
| Flash | TODO | Not visible/legible from top-side photo; inspect PCB bottom |

## Interfaces

- WAN: 1x Fast Ethernet
- LAN: 4x Fast Ethernet switch ports
- Wi-Fi: 2.4 GHz 802.11n
- UART: TODO
- SPI flash accessible: TODO
- JTAG pads: TODO
- Antenna connectors: TODO

## Constraints

- Very limited flash/RAM.
- Not suitable for heavy packages, LuCI-heavy builds, databases, or controller workloads.
- Best used as mesh endpoint, failure-injection subject, minimal telemetry node, or constrained policy target.

## Evidence Collected

- [X] Bottom label photo
- [X] PCB top photo
- [X] PCB bottom photo
- [X] SoC,Flash,Ram close-up
- [X] UART area close-up
- [X] RF section close-up
- [X] Power section close-up

## INFER-MESH Use

Primary role: constrained mesh node  
Secondary role: low-resource failure subject  
Telemetry priority: RSSI, noise, route state, ping RTT, packet loss, memory pressure  
Control actions: interface restart, mesh rejoin, route preference change, txpower change if supported