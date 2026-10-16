"""MQTT configuration source guards and compiled C++ validator regressions."""
from pathlib import Path
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
SOURCE = (ROOT / "MachineMonitor/MachineMonitor.ino").read_text(encoding="utf-8")
PRESERVED = {'beginWiFiConnection': 'beb7f90489c8d9e3fe20d68028bc084c33a5c7a1098445ed7d54124c6b75e955', 'startConfigAP': '9429733a9f90a60ccbf4a40292ac42b4b5aa0ae87322c97484cfd92c29eb6f03', 'stopConfigAP': '0ce45866fc37d37a014119fe94961f0ff98d3a55f83a7f97e82b3ffcfe4f47b4', 'wifiLoop': '02ff722195dfa949bc0de018b78c86ba7a9c28967e0c6b052755412aa6deecb0', 'mqttLoop': 'a84eecab4ddc4a6ef0481d38b1551a5b8067b8438b9709ddcf5a25b023965db4', 'initInputs': 'f7ba0e26bdd15b9da9bf9a5761b32dd911d4e6b9c44cafeb0c4a94b2a8ad3900', 'updateInputs': '0dcac44014a2812cda78bc7d10eb8adfcdfb731ee70c9dd73e0bd7b45e39fd36', 'publishInputConfiguration': 'b66d0693387ae7d120ea816da9511a2766265c403185efe3e6ffd7464bcfefb0', 'publishInputAvailability': 'f44a0dd084beb20bc21444eb3f559fe70426e42bfa6fde1d1d5c06306370adb2', 'publishAllStates': 'a685096bfb115081b04bc799fee752f3f4231d57f402336039f9791750e42c27', 'publishInputState': '8536a485877bef2a2bbfa89c7fb92ae2a69f6b3337cc8902910bfa5c266bb22d', 'mqttCallback': '6649a8dc9b02ea2cdd84733c5718eaf6ddf748fc930d14125580354dac7c76e5', 'mqttStateTopic': '8e5aecf98f66cf194cb30e403c9a98472d7acfb16b61da3e0dc1b9029e9a184b', 'mqttEventTopic': '667038de7cbda10abc879059c23e6c6d24ea0bf40f820aefe7c10f572f565a25', 'mqttAvailabilityTopic': 'bebf249f428bd4e66c039505d4d0f6be9d2d137c692ff9b78ade8a1d9b3cab16', 'mqttInputAvailabilityTopic': '1886fd44c1d9ad504e8afb59d4824c6a38f4861fcab4cc3171b1d5f047a77c49', 'mqttInputConfigTopic': 'd63e9c62615403dc444b86a563d1a7a7453d572924ef95238f49bd102e5f6575', 'mqttDiscoveryTopic': '3a37056aff89441c1b4495d348c8ab87906b4c7f82f61f26c4eb3e7c25ef3707', 'connectMQTT': 'c04e32d8a10130d9806d4bc5d16524f25e1941ecef503d188a75c24e937e8d5a'}


def function_body(source, name):
    match = re.search(r"\b" + name + r"\s*\([^;]*?\)\s*\{", source)
    start = source.index("{", match.start())
    depth, end = 1, start + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


class BrokerSettingsTests(unittest.TestCase):
    def test_existing_acquisition_recovery_and_mqtt_protocol_unchanged(self):
        self.assertEqual(len(PRESERVED), 19)
        for name, digest in PRESERVED.items():
            with self.subTest(function=name):
                self.assertEqual(hashlib.sha256(function_body(SOURCE, name).encode()).hexdigest(), digest)

    def test_old_nvs_defaults_and_new_address_survive_reload(self):
        load = function_body(SOURCE, "loadSettings")
        save = function_body(SOURCE, "saveSettings")
        self.assertIn('preferences.getString("mqtt_host", MQTT_BROKER_NAME)', load)
        self.assertIn("mqttBrokerHost.trim()", load)
        self.assertIn("validMqttBrokerAddress(mqttBrokerHost.c_str())", load)
        self.assertIn("mqttBrokerHost = MQTT_BROKER_NAME", load)
        self.assertIn('preferences.putString("mqtt_host", newMQTTHost)', save)
        for key in ["name", "wifi_ssid", "wifi_pass", "mqtt_user", "mqtt_pass"]:
            self.assertIn('preferences.putString("' + key + '",', save)
        self.assertNotIn("preferences.clear", SOURCE)

    def test_invalid_form_cannot_save_or_restart(self):
        web = function_body(SOURCE, "setupWebServer")
        validation = web.index("if (!validMqttBrokerAddress(newMQTTHost.c_str()))")
        saving = web.index("saveSettings(")
        self.assertLess(validation, saving)
        rejected = web[validation:saving]
        self.assertIn("server.send(400,", rejected)
        self.assertIn("return;", rejected)
        self.assertIn("newMQTTHost.length() == 0) newMQTTHost = MQTT_BROKER_NAME", web)
        self.assertIn('server.arg("mqtthost") : mqttBrokerHost', web)
        self.assertIn("newMQTTPassword,\n        newMQTTHost", web)

    def test_new_field_is_displayed_and_used_for_resolution(self):
        self.assertIn("<input name='mqtthost'", function_body(SOURCE, "htmlPage"))
        resolve = function_body(SOURCE, "resolveMQTTBroker")
        self.assertIn("brokerIP.fromString(mqttBrokerHost.c_str())", resolve)
        self.assertIn("WiFi.hostByName(mqttBrokerHost.c_str(), brokerIP)", resolve)
        self.assertIn("resolved == 1 && brokerIP != IPAddress(0, 0, 0, 0)", resolve)
        self.assertLess(resolve.index("brokerIP.fromString"), resolve.index("WiFi.hostByName"))

    def test_compiled_real_cpp_validator_cases(self):
        compiler = os.environ.get("MM_FIRMWARE_CXX") or shutil.which("c++") or shutil.which("g++")
        if not compiler:
            if os.environ.get("CI"):
                self.fail("CI needs a C++ compiler for firmware validation")
            self.skipTest("Set MM_FIRMWARE_CXX or install a C++ compiler")
        with tempfile.TemporaryDirectory(prefix="mm-broker-tests-") as tmp:
            result = subprocess.run([compiler, "-std=c++17", "-c", str(ROOT / "tests/BrokerAddressTests.cpp"),
                                     "-o", str(Path(tmp) / "checks.o")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
