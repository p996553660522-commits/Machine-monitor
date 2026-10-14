"""Source-level startup guards; board boot still needs physical validation.

Run: python -m unittest discover -s firmware/tests -v
"""
from pathlib import Path
import unittest

SOURCE = (Path(__file__).parents[1] / "MachineMonitor/MachineMonitor.ino").read_text(encoding="utf-8")

def body(name):
    start = SOURCE.index("{", SOURCE.index("void " + name + "("))
    depth = 1
    end = start + 1
    while depth:
        depth += (SOURCE[end] == "{") - (SOURCE[end] == "}")
        end += 1
    return SOURCE[start:end]

class StartupTests(unittest.TestCase):
    def test_both_boot_paths_initialize_network_before_web_server(self):
        setup = body("setup")
        self.assertEqual(setup.count("setupWebServer();"), 1)
        server = setup.index("setupWebServer();")
        self.assertLess(setup.index("beginWiFiConnection();"), server)
        self.assertLess(setup.index("startConfigAP();"), server)
        self.assertLess(setup.index("wifiDisconnectedSince = millis();"), server)
        self.assertLess(setup.index("setupWebServer();"), setup.index('Serial.println("SYSTEM READY")'))

    def test_network_helpers_initialize_wifi_before_using_interface(self):
        sta = body("beginWiFiConnection")
        self.assertLess(sta.index("WiFi.mode(WIFI_STA)"), sta.index("WiFi.begin("))
        self.assertLess(sta.index("WiFi.mode(WIFI_AP_STA)"), sta.index("WiFi.begin("))
        ap = body("startConfigAP")
        self.assertLess(ap.index("WiFi.mode(WIFI_AP_STA)"), ap.index("WiFi.softAP("))
