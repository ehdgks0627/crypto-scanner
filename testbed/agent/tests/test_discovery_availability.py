import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from discovery.runner import summarize_availability  # noqa: E402


class DiscoveryAvailabilityTests(unittest.TestCase):
    def test_summarize_availability_reports_tls_handshake_checks(self):
        report = summarize_availability(
            [
                {
                    "host": "web.testbed.local",
                    "port": 443,
                    "transport": "TCP",
                    "detected_protocol": "TLS",
                    "suggested_protocol_hint": "TLS",
                    "availability_metrics": {
                        "sample_count": 3,
                        "handshake_ms": {"p50": 10.0, "p95": 12.0, "samples": 3},
                        "tcp_connect_ms": {"p50": 1.0, "p95": 2.0, "samples": 3},
                        "failure_rate": 0.0,
                        "timeout_rate": 0.0,
                        "handshake_bytes_sent": 1800,
                        "handshake_bytes_received": 3200,
                    },
                },
                {
                    "host": "ssh.testbed.local",
                    "port": 22,
                    "transport": "TCP",
                    "detected_protocol": "SSH",
                    "suggested_protocol_hint": "SSH",
                },
            ]
        )

        self.assertEqual(report["measured_endpoint_count"], 1)
        self.assertEqual(report["tls_endpoint_count"], 1)
        self.assertEqual(report["sample_count"], 3)
        self.assertEqual(report["averages"]["handshake_p95_ms"], 12.0)
        self.assertEqual(report["handshake_bytes"]["received"], 3200.0)


if __name__ == "__main__":
    unittest.main()
