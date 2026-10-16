#include "../MachineMonitor/BrokerAddress.h"

static_assert(validMqttBrokerAddress("homeassistant.local"), "legacy default");
static_assert(validMqttBrokerAddress("192.168.0.22"), "broker across VPN");
static_assert(validMqttBrokerAddress("192.168.1.22"), "second LAN");
static_assert(validMqttBrokerAddress("broker.example.com"), "DNS");
static_assert(validMqttBrokerAddress("MQTT-Server"), "local hostname");
static_assert(validMqttBrokerAddress("a"), "one character");
static_assert(!validMqttBrokerAddress(nullptr), "missing");
static_assert(!validMqttBrokerAddress(""), "empty normalized by caller");
static_assert(!validMqttBrokerAddress("http://192.168.0.22"), "not a URL");
static_assert(!validMqttBrokerAddress("192.168.0.22:1883"), "port stays separate");
static_assert(!validMqttBrokerAddress("192.168.0.999"), "invalid IPv4");
static_assert(!validMqttBrokerAddress("192.168.0"), "incomplete IPv4");
static_assert(!validMqttBrokerAddress("0.0.0.0"), "unspecified address");
static_assert(!validMqttBrokerAddress("broker/path"), "path");
static_assert(!validMqttBrokerAddress("broker name"), "space");
static_assert(!validMqttBrokerAddress("<script>"), "HTML");
static_assert(!validMqttBrokerAddress("broker\""), "attribute escape");
static_assert(!validMqttBrokerAddress("-broker.local"), "label starts with hyphen");
static_assert(!validMqttBrokerAddress("broker-.local"), "label ends with hyphen");
static_assert(!validMqttBrokerAddress("broker..local"), "empty label");
static_assert(!validMqttBrokerAddress("broker.local."), "no trailing dot");
static_assert(validMqttBrokerAddress("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.local"), "63-byte label");
static_assert(!validMqttBrokerAddress("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.local"), "64-byte label");

static_assert(validMqttBrokerAddress("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), "253-byte hostname");
static_assert(!validMqttBrokerAddress("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), "254-byte hostname");
