from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from collect_batman_metrics import parse_originators
from collect_iw_metrics import parse_link_output, parse_station_output
from latency_probe import parse_ping_output


class CollectorParserTests(unittest.TestCase):
    def test_parse_iw_link_output(self) -> None:
        record = parse_link_output(
            """
            Connected to aa:bb:cc:dd:ee:ff (on mesh0)
            signal: -63 dBm
            tx bitrate: 86.7 MBit/s
            rx bitrate: 78.0 MBit/s
            """
        )
        self.assertEqual(record["peer_mac"], "aa:bb:cc:dd:ee:ff")
        self.assertTrue(record["connected"])
        self.assertEqual(record["rssi_dbm"], -63)
        self.assertEqual(record["tx_rate_mbps"], 86.7)
        self.assertEqual(record["rx_rate_mbps"], 78.0)

    def test_parse_iw_station_dump(self) -> None:
        records = parse_station_output(
            """
Station 00:11:22:33:44:55 (on mesh0)
        signal:         -51 dBm
        tx bitrate:     144.4 MBit/s
        rx bitrate:     130.0 MBit/s
Station aa:bb:cc:dd:ee:ff (on mesh0)
        signal:         -72 dBm
        tx bitrate:     43.3 MBit/s
        rx bitrate:     39.0 MBit/s
            """
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1]["peer_mac"], "aa:bb:cc:dd:ee:ff")
        self.assertEqual(records[1]["rssi_dbm"], -72)

    def test_parse_ping_output_linux(self) -> None:
        record = parse_ping_output(
            """
5 packets transmitted, 4 received, 20% packet loss, time 4008ms
rtt min/avg/max/mdev = 10.100/12.500/17.900/2.000 ms
            """,
            node_id="shg3060",
            target="10.10.0.12",
        )
        self.assertEqual(record["transmitted"], 5)
        self.assertEqual(record["received"], 4)
        self.assertEqual(record["packet_loss"], 0.2)
        self.assertEqual(record["latency_ms"], 12.5)

    def test_parse_batman_originators(self) -> None:
        records = parse_originators(
            """
  Originator        last-seen (#/255) Nexthop           [outgoingIF]
* aa:bb:cc:dd:ee:ff    0.420s   (255) 11:22:33:44:55:66 [mesh0]
            """,
            node_id="shg3060",
            mesh_interface="bat0",
        )
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["selected"])
        self.assertEqual(records[0]["batman_tq"], 255)


if __name__ == "__main__":
    unittest.main()

