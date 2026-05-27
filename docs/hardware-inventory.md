# Hardware Inventory

Complete the unknown fields after physically verifying device revisions, OpenWrt support, and
flash/RAM constraints. ISP-branded hardware frequently varies by hardware revision.

| ID | Device | Intended role | OpenWrt target/version | Radio/interfaces | Management IP | Status |
|---|---|---|---|---|---|---|
| `shg3060` | Vodafone SHG3060 | Mesh node A | To verify | To verify | `192.168.50.11` | Planned |
| `shg3000` | Vodafone SHG3000 | Mesh node B | To verify | To verify | `192.168.50.12` | Planned |
| `shg2500` | Vodafone SHG2500 | Degradation node | To verify | To verify | `192.168.50.13` | Planned |
| `wd300` | Home&Life WD300 | Collector / gateway | To verify | To verify | `192.168.50.20` | Planned |
| `tl-wr841nd` | TP-Link TL-WR841ND | Legacy mesh / edge | Revision required | To verify | `192.168.50.14` | Planned |
| `controller` | Laptop | Experiment controller | Host OS | Ethernet/Wi-Fi | Operator set | Available |

## Verification Checklist

| Check | Record |
|---|---|
| Hardware revision and board label | Required before flashing |
| Existing firmware backup and recovery method | Required before modification |
| OpenWrt device page, target, and supported release | Required before installing images |
| RAM/flash availability for `batman-adv`, Python, and tooling | Determine node capability |
| Radio bands, driver, supported 802.11s mode, and antenna placement | Determine RF design |
| Ethernet recovery/management connection | Preserve out-of-band access |
| Power supply rating and physical condition | Remove unreliable hardware |

## Package Expectations

Mesh nodes require packages equivalent to `wpad-mesh-mbedtls`, `kmod-batman-adv`, and
`batctl`, where supported by their OpenWrt release. Telemetry commands use `iw`, `ping`, and
optionally `iperf3`. Low-flash nodes may collect raw command output while the WD300 or laptop
runs Python and database ingestion.

## Notes Log

| Date | Node | Observation | Action |
|---|---|---|---|
| YYYY-MM-DD | `node_id` | Hardware or firmware observation | Follow-up |
