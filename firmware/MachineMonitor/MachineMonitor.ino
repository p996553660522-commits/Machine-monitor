#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <ESPmDNS.h>
#include <PubSubClient.h>

// ============================================================
// MACHINE MONITOR ESP32
// ESP32 + 4x PC817 + WiFi recovery + MQTT + Home Assistant
// ============================================================

// -------------------------
// INPUTS
// -------------------------

const uint8_t INPUT_PINS[4] = {
  32,
  33,
  25,
  26
};

const char* INPUT_NAMES[4] = {
  "Input 1",
  "Input 2",
  "Input 3",
  "Input 4"
};

const unsigned long DEBOUNCE_MS = 50;

// -------------------------
// NETWORK
// -------------------------

const char* AP_PASSWORD = "12345687";

const char* MQTT_BROKER_NAME = "homeassistant.local";
const uint16_t MQTT_PORT = 1883;

const char* MQTT_CLIENT_PREFIX = "MachineMonitor-";

// How often to retry WiFi while disconnected
const unsigned long WIFI_RECONNECT_INTERVAL = 10000;

// How long to try STA before enabling fallback AP
const unsigned long WIFI_AP_FALLBACK_DELAY = 20000;

// MQTT retry interval
const unsigned long MQTT_RECONNECT_INTERVAL = 5000;

// -------------------------
// OBJECTS
// -------------------------

Preferences preferences;
WebServer server(80);

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// -------------------------
// DEVICE INFO
// -------------------------

String deviceId;
String deviceName;
String hostname;

// -------------------------
// WIFI SETTINGS
// -------------------------

String wifiSSID;
String wifiPassword;

bool apActive = false;
bool wifiWasConnected = false;
bool mdnsStarted = false;

unsigned long lastWiFiAttempt = 0;
unsigned long wifiDisconnectedSince = 0;

// -------------------------
// MQTT SETTINGS
// -------------------------

String mqttUser;
String mqttPassword;

bool mqttConnected = false;
unsigned long lastMQTTAttempt = 0;

// -------------------------
// INPUT STATE
// -------------------------

bool rawState[4] = {
  false, false, false, false
};

bool stableState[4] = {
  false, false, false, false
};

unsigned long lastChangeTime[4] = {
  0, 0, 0, 0
};

// ============================================================
// HELPERS
// ============================================================

String makeDeviceId()
{
  uint64_t chipId = ESP.getEfuseMac();

  char buffer[20];

  snprintf(
    buffer,
    sizeof(buffer),
    "%04X%08X",
    (uint16_t)(chipId >> 32),
    (uint32_t)chipId
  );

  return String(buffer);
}

String makeShortDeviceId()
{
  uint64_t chipId = ESP.getEfuseMac();

  char buffer[10];

  snprintf(
    buffer,
    sizeof(buffer),
    "%06X",
    (uint32_t)(chipId & 0xFFFFFF)
  );

  return String(buffer);
}

String sanitizeHostname(String value)
{
  value.toLowerCase();

  String result = "";

  for (uint16_t i = 0; i < value.length(); i++)
  {
    char c = value[i];

    if (
      (c >= 'a' && c <= 'z') ||
      (c >= '0' && c <= '9') ||
      c == '-'
    )
    {
      result += c;
    }
  }

  if (result.length() == 0)
  {
    result = "machinemonitor";
  }

  return result;
}

// ============================================================
// SETTINGS
// ============================================================

void loadSettings()
{
  preferences.begin("machine", true);

  deviceName = preferences.getString(
    "name",
    "MachineMonitor-" + makeShortDeviceId()
  );

  wifiSSID = preferences.getString(
    "wifi_ssid",
    ""
  );

  wifiPassword = preferences.getString(
    "wifi_pass",
    ""
  );

  mqttUser = preferences.getString(
    "mqtt_user",
    ""
  );

  mqttPassword = preferences.getString(
    "mqtt_pass",
    ""
  );

  preferences.end();

  hostname = sanitizeHostname(deviceName);
}

void saveSettings(
  const String& newName,
  const String& newSSID,
  const String& newWifiPassword,
  const String& newMQTTUser,
  const String& newMQTTPassword
)
{
  preferences.begin("machine", false);

  preferences.putString("name", newName);
  preferences.putString("wifi_ssid", newSSID);
  preferences.putString("wifi_pass", newWifiPassword);
  preferences.putString("mqtt_user", newMQTTUser);
  preferences.putString("mqtt_pass", newMQTTPassword);

  preferences.end();
}

// ============================================================
// WIFI
// ============================================================

void beginWiFiConnection()
{
  if (wifiSSID.length() == 0)
  {
    return;
  }

  Serial.println();
  Serial.println("Trying WiFi...");
  Serial.print("SSID: ");
  Serial.println(wifiSSID);

  // If fallback AP is running, keep it alive while STA connects.
  if (apActive)
  {
    WiFi.mode(WIFI_AP_STA);
  }
  else
  {
    WiFi.mode(WIFI_STA);
  }

  WiFi.setHostname(hostname.c_str());

  WiFi.begin(
    wifiSSID.c_str(),
    wifiPassword.c_str()
  );

  lastWiFiAttempt = millis();
}

// ============================================================
// ACCESS POINT
// ============================================================

void startConfigAP()
{
  if (apActive)
  {
    return;
  }

  Serial.println();
  Serial.println("================================");
  Serial.println("STARTING CONFIGURATION AP");
  Serial.println("================================");

  // Important: AP + STA.
  // This allows us to keep looking for the saved WiFi network.
  WiFi.mode(WIFI_AP_STA);

  bool result = WiFi.softAP(
    deviceName.c_str(),
    AP_PASSWORD
  );

  if (!result)
  {
    Serial.println("Failed to start configuration AP!");
    return;
  }

  apActive = true;

  IPAddress ip = WiFi.softAPIP();

  Serial.print("AP SSID: ");
  Serial.println(deviceName);

  Serial.print("AP password: ");
  Serial.println(AP_PASSWORD);

  Serial.print("AP IP: ");
  Serial.println(ip);

  Serial.println("Configuration page:");
  Serial.print("http://");
  Serial.print(ip);
  Serial.println("/");
}

void stopConfigAP()
{
  if (!apActive)
  {
    return;
  }

  Serial.println();
  Serial.println("WiFi recovered.");
  Serial.println("Stopping configuration AP...");

  WiFi.softAPdisconnect(true);

  apActive = false;

  // Remain in station mode only.
  WiFi.mode(WIFI_STA);

  Serial.println("Configuration AP stopped.");
}

// ============================================================
// MDNS
// ============================================================

void startMDNS()
{
  if (mdnsStarted)
  {
    MDNS.end();
    mdnsStarted = false;
  }

  if (MDNS.begin(hostname.c_str()))
  {
    mdnsStarted = true;

    Serial.println("mDNS started.");

    Serial.print("Hostname: http://");
    Serial.print(hostname);
    Serial.println(".local/");
  }
  else
  {
    Serial.println("mDNS start FAILED.");
  }
}

// ============================================================
// WIFI MAINTENANCE
// ============================================================

void wifiLoop()
{
  bool connected =
    WiFi.status() == WL_CONNECTED;

  // ----------------------------------------------------------
  // CONNECTED
  // ----------------------------------------------------------

  if (connected)
  {
    if (!wifiWasConnected)
    {
      wifiWasConnected = true;
      wifiDisconnectedSince = 0;

      Serial.println();
      Serial.println("================================");
      Serial.println("WIFI CONNECTED");
      Serial.println("================================");

      Serial.print("ESP32 IP: ");
      Serial.println(WiFi.localIP());

      Serial.print("Gateway: ");
      Serial.println(WiFi.gatewayIP());

      Serial.print("RSSI: ");
      Serial.print(WiFi.RSSI());
      Serial.println(" dBm");

      // Stop fallback AP after successful STA recovery.
      if (apActive)
      {
        stopConfigAP();
      }

      startMDNS();

      // Allow MQTT reconnect immediately.
      lastMQTTAttempt = 0;
    }

    return;
  }

  // ----------------------------------------------------------
  // DISCONNECTED
  // ----------------------------------------------------------

  if (wifiWasConnected)
  {
    wifiWasConnected = false;

    Serial.println();
    Serial.println("================================");
    Serial.println("WIFI LOST");
    Serial.println("================================");

    mqttConnected = false;

    if (mqttClient.connected())
    {
      mqttClient.disconnect();
    }

    wifiDisconnectedSince = millis();

    // Permit an immediate reconnect attempt.
    lastWiFiAttempt = 0;
  }

  if (wifiDisconnectedSince == 0)
  {
    wifiDisconnectedSince = millis();
  }

  // ----------------------------------------------------------
  // Start fallback AP after prolonged WiFi loss
  // ----------------------------------------------------------

  if (
    !apActive &&
    millis() - wifiDisconnectedSince >= WIFI_AP_FALLBACK_DELAY
  )
  {
    startConfigAP();
  }

  // ----------------------------------------------------------
  // Retry saved WiFi
  // ----------------------------------------------------------

  if (
    wifiSSID.length() > 0 &&
    (
      lastWiFiAttempt == 0 ||
      millis() - lastWiFiAttempt >= WIFI_RECONNECT_INTERVAL
    )
  )
  {
    beginWiFiConnection();
  }
}

// ============================================================
// MQTT BROKER DISCOVERY
// ============================================================

bool resolveMQTTBroker(IPAddress& brokerIP)
{
  Serial.println();
  Serial.println("Resolving MQTT broker...");

  Serial.print("Hostname: ");
  Serial.println(MQTT_BROKER_NAME);

  if (
    WiFi.hostByName(
      MQTT_BROKER_NAME,
      brokerIP
    )
  )
  {
    Serial.print("MQTT broker found: ");
    Serial.println(brokerIP);

    return true;
  }

  Serial.println("MQTT broker NOT found!");

  return false;
}

// ============================================================
// MQTT TOPICS
// ============================================================

String mqttBaseTopic()
{
  return "machine_monitor/" + deviceId;
}

String mqttStateTopic(uint8_t channel)
{
  return mqttBaseTopic() +
         "/state/input" +
         String(channel + 1);
}

String mqttEventTopic()
{
  return mqttBaseTopic() + "/event";
}

String mqttAvailabilityTopic()
{
  return mqttBaseTopic() + "/availability";
}

String mqttDiscoveryTopic(uint8_t channel)
{
  return "homeassistant/binary_sensor/" +
         deviceId +
         "/input" +
         String(channel + 1) +
         "/config";
}

// ============================================================
// MQTT DISCOVERY
// ============================================================

void publishDiscovery(uint8_t channel)
{
  String topic = mqttDiscoveryTopic(channel);

  String payload;

  payload += "{";

  payload += "\"name\":\"";
  payload += deviceName;
  payload += " - ";
  payload += INPUT_NAMES[channel];
  payload += "\",";

  payload += "\"unique_id\":\"";
  payload += deviceId;
  payload += "_input";
  payload += String(channel + 1);
  payload += "\",";

  payload += "\"state_topic\":\"";
  payload += mqttStateTopic(channel);
  payload += "\",";

  payload += "\"availability_topic\":\"";
  payload += mqttAvailabilityTopic();
  payload += "\",";

  payload += "\"payload_on\":\"ON\",";
  payload += "\"payload_off\":\"OFF\",";

  payload += "\"device_class\":\"running\",";

  payload += "\"device\":{";

  payload += "\"identifiers\":[\"";
  payload += deviceId;
  payload += "\"],";

  payload += "\"name\":\"";
  payload += deviceName;
  payload += "\",";

  payload += "\"manufacturer\":\"DIY\",";
  payload += "\"model\":\"ESP32 Machine Monitor\",";
  payload += "\"sw_version\":\"1.1\"";

  payload += "}";

  payload += "}";

  mqttClient.publish(
    topic.c_str(),
    payload.c_str(),
    true
  );

  Serial.print("Discovery published: ");
  Serial.println(topic);
}

void publishAllDiscovery()
{
  for (uint8_t i = 0; i < 4; i++)
  {
    publishDiscovery(i);
  }
}

// ============================================================
// MQTT STATES
// ============================================================

void publishInputState(uint8_t channel)
{
  const char* state =
    stableState[channel]
      ? "ON"
      : "OFF";

  String topic = mqttStateTopic(channel);

  mqttClient.publish(
    topic.c_str(),
    state,
    true
  );

  Serial.print("MQTT ");
  Serial.print(INPUT_NAMES[channel]);
  Serial.print(" = ");
  Serial.println(state);
}

void publishAllStates()
{
  for (uint8_t i = 0; i < 4; i++)
  {
    publishInputState(i);
  }
}

// ============================================================
// MQTT EVENT
// ============================================================

void publishEvent(
  uint8_t channel,
  bool state
)
{
  String payload;

  payload += "{";

  payload += "\"input\":";
  payload += String(channel + 1);
  payload += ",";

  payload += "\"state\":\"";
  payload += state ? "ON" : "OFF";
  payload += "\",";

  payload += "\"millis\":";
  payload += String(millis());

  payload += "}";

  mqttClient.publish(
    mqttEventTopic().c_str(),
    payload.c_str(),
    false
  );
}

// ============================================================
// MQTT CALLBACK
// ============================================================

void mqttCallback(
  char* topic,
  byte* payload,
  unsigned int length
)
{
  String message;

  for (unsigned int i = 0; i < length; i++)
  {
    message += (char)payload[i];
  }

  Serial.println();
  Serial.println("MQTT message received:");

  Serial.print("Topic: ");
  Serial.println(topic);

  Serial.print("Payload: ");
  Serial.println(message);

  if (
    String(topic) ==
    "homeassistant/status"
  )
  {
    if (message == "online")
    {
      Serial.println("Home Assistant is ONLINE.");

      publishAllDiscovery();
      publishAllStates();
    }
  }
}

// ============================================================
// MQTT CONNECT
// ============================================================

bool connectMQTT()
{
  if (WiFi.status() != WL_CONNECTED)
  {
    return false;
  }

  IPAddress brokerIP;

  if (!resolveMQTTBroker(brokerIP))
  {
    return false;
  }

  mqttClient.setServer(
    brokerIP,
    MQTT_PORT
  );

  mqttClient.setCallback(
    mqttCallback
  );

  String clientId =
    MQTT_CLIENT_PREFIX +
    deviceId;

  Serial.println();
  Serial.println("================================");
  Serial.println("CONNECTING TO MQTT");
  Serial.println("================================");

  Serial.print("Broker: ");
  Serial.println(brokerIP);

  Serial.print("Port: ");
  Serial.println(MQTT_PORT);

  Serial.print("Client ID: ");
  Serial.println(clientId);

  bool connected = false;

  if (mqttUser.length() > 0)
  {
    connected = mqttClient.connect(
      clientId.c_str(),

      mqttUser.c_str(),
      mqttPassword.c_str(),

      mqttAvailabilityTopic().c_str(),
      0,
      true,
      "offline"
    );
  }
  else
  {
    connected = mqttClient.connect(
      clientId.c_str(),

      mqttAvailabilityTopic().c_str(),
      0,
      true,
      "offline"
    );
  }

  if (!connected)
  {
    Serial.print("MQTT connection FAILED. State = ");
    Serial.println(mqttClient.state());

    return false;
  }

  Serial.println("MQTT connected!");

  mqttConnected = true;

  // ----------------------------------------------------------
  // Availability
  // ----------------------------------------------------------

  mqttClient.publish(
    mqttAvailabilityTopic().c_str(),
    "online",
    true
  );

  // ----------------------------------------------------------
  // HA birth
  // ----------------------------------------------------------

  mqttClient.subscribe(
    "homeassistant/status"
  );

  // ----------------------------------------------------------
  // Republish everything after reconnect
  // ----------------------------------------------------------

  publishAllDiscovery();
  publishAllStates();

  return true;
}

// ============================================================
// MQTT MAINTENANCE
// ============================================================

void mqttLoop()
{
  if (WiFi.status() != WL_CONNECTED)
  {
    mqttConnected = false;
    return;
  }

  if (mqttClient.connected())
  {
    mqttConnected = true;

    mqttClient.loop();

    return;
  }

  mqttConnected = false;

  if (
    lastMQTTAttempt != 0 &&
    millis() - lastMQTTAttempt <
    MQTT_RECONNECT_INTERVAL
  )
  {
    return;
  }

  lastMQTTAttempt = millis();

  connectMQTT();
}

// ============================================================
// INPUTS
// ============================================================

void initInputs()
{
  for (uint8_t i = 0; i < 4; i++)
  {
    pinMode(
      INPUT_PINS[i],
      INPUT_PULLUP
    );

    // PC817 active = LOW
    rawState[i] =
      digitalRead(INPUT_PINS[i]) == LOW;

    stableState[i] =
      rawState[i];

    lastChangeTime[i] =
      millis();
  }

  Serial.println("Inputs initialized.");
}

void updateInputs()
{
  for (uint8_t i = 0; i < 4; i++)
  {
    bool current =
      digitalRead(INPUT_PINS[i]) == LOW;

    if (current != rawState[i])
    {
      rawState[i] = current;
      lastChangeTime[i] = millis();
    }

    if (
      rawState[i] != stableState[i] &&
      millis() - lastChangeTime[i] >= DEBOUNCE_MS
    )
    {
      stableState[i] =
        rawState[i];

      Serial.print("INPUT CHANGE: ");
      Serial.print(INPUT_NAMES[i]);
      Serial.print(" -> ");
      Serial.println(
        stableState[i]
          ? "ON"
          : "OFF"
      );

      if (mqttClient.connected())
      {
        publishInputState(i);

        publishEvent(
          i,
          stableState[i]
        );
      }
    }
  }
}

// ============================================================
// WEB PAGE
// ============================================================

String htmlPage()
{
  String html;

  html += "<!DOCTYPE html>";
  html += "<html>";
  html += "<head>";

  html += "<meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";

  html += "<title>Machine Monitor</title>";

  html += "<style>";

  html += "body{font-family:Arial;margin:20px;max-width:700px}";
  html += "input{width:100%;padding:10px;margin:5px 0 15px;box-sizing:border-box}";
  html += "button{padding:12px 20px;font-size:16px}";
  html += ".state{padding:10px;margin:5px 0;background:#eee}";
  html += ".on{background:#cfc}";
  html += ".off{background:#eee}";

  html += "</style>";

  html += "</head>";
  html += "<body>";

  html += "<h1>Machine Monitor</h1>";

  html += "<h2>Device</h2>";

  html += "<p><b>Name:</b> ";
  html += deviceName;
  html += "</p>";

  html += "<p><b>Device ID:</b> ";
  html += deviceId;
  html += "</p>";

  html += "<p><b>Hostname:</b> ";
  html += hostname;
  html += "</p>";

  html += "<hr>";

  html += "<h2>Inputs</h2>";

  for (uint8_t i = 0; i < 4; i++)
  {
    html += "<div class='state ";
    html += stableState[i] ? "on" : "off";
    html += "'>";

    html += INPUT_NAMES[i];
    html += ": <b>";

    html += stableState[i]
      ? "ON"
      : "OFF";

    html += "</b></div>";
  }

  html += "<hr>";

  html += "<h2>Wi-Fi / MQTT</h2>";

  html += "<form method='POST' action='/save'>";

  html += "<label>Device name</label>";
  html += "<input name='name' value='";
  html += deviceName;
  html += "'>";

  html += "<label>Wi-Fi SSID</label>";
  html += "<input name='ssid' value='";
  html += wifiSSID;
  html += "'>";

  html += "<label>Wi-Fi password</label>";
  html += "<input type='password' name='wifipass' value='";
  html += wifiPassword;
  html += "'>";

  html += "<label>MQTT username</label>";
  html += "<input name='mqttuser' value='";
  html += mqttUser;
  html += "'>";

  html += "<label>MQTT password</label>";
  html += "<input type='password' name='mqttpass' value='";
  html += mqttPassword;
  html += "'>";

  html += "<p><b>MQTT broker:</b> ";
  html += MQTT_BROKER_NAME;
  html += ":";
  html += String(MQTT_PORT);
  html += "</p>";

  html += "<button type='submit'>";
  html += "Save and reboot";
  html += "</button>";

  html += "</form>";

  html += "<hr>";

  html += "<h2>Status</h2>";

  html += "<p><b>Wi-Fi:</b> ";

  if (WiFi.status() == WL_CONNECTED)
  {
    html += "CONNECTED";
  }
  else
  {
    html += "NOT CONNECTED";
  }

  html += "</p>";

  if (WiFi.status() == WL_CONNECTED)
  {
    html += "<p><b>ESP32 IP:</b> ";
    html += WiFi.localIP().toString();
    html += "</p>";

    html += "<p><b>RSSI:</b> ";
    html += String(WiFi.RSSI());
    html += " dBm</p>";
  }

  html += "<p><b>Configuration AP:</b> ";
  html += apActive ? "ACTIVE" : "OFF";
  html += "</p>";

  if (apActive)
  {
    html += "<p><b>AP IP:</b> ";
    html += WiFi.softAPIP().toString();
    html += "</p>";
  }

  html += "<p><b>MQTT:</b> ";

  html += mqttClient.connected()
    ? "CONNECTED"
    : "NOT CONNECTED";

  html += "</p>";

  html += "</body>";
  html += "</html>";

  return html;
}

// ============================================================
// WEB SERVER
// ============================================================

void setupWebServer()
{
  server.on(
    "/",
    HTTP_GET,
    []()
    {
      server.send(
        200,
        "text/html; charset=utf-8",
        htmlPage()
      );
    }
  );

  server.on(
    "/save",
    HTTP_POST,
    []()
    {
      String newName =
        server.arg("name");

      String newSSID =
        server.arg("ssid");

      String newWifiPassword =
        server.arg("wifipass");

      String newMQTTUser =
        server.arg("mqttuser");

      String newMQTTPassword =
        server.arg("mqttpass");

      if (newName.length() == 0)
      {
        newName =
          "MachineMonitor-" +
          makeShortDeviceId();
      }

      saveSettings(
        newName,
        newSSID,
        newWifiPassword,
        newMQTTUser,
        newMQTTPassword
      );

      server.send(
        200,
        "text/html; charset=utf-8",
        "<html><body>"
        "<h1>Saved!</h1>"
        "<p>ESP32 will reboot in 2 seconds.</p>"
        "</body></html>"
      );

      delay(2000);

      ESP.restart();
    }
  );

  server.begin();

  Serial.println("Web server started.");
}

// ============================================================
// SETUP
// ============================================================

void setup()
{
  Serial.begin(115200);

  delay(1000);

  Serial.println();
  Serial.println("================================");
  Serial.println("      MACHINE MONITOR ESP32");
  Serial.println("================================");

  deviceId =
    makeDeviceId();

  Serial.print("Device ID: ");
  Serial.println(deviceId);

  loadSettings();

  Serial.println();
  Serial.println("===== SETTINGS =====");

  Serial.print("Device name: ");
  Serial.println(deviceName);

  Serial.print("Hostname: ");
  Serial.println(hostname);

  Serial.print("WiFi SSID: ");

  if (wifiSSID.length() > 0)
  {
    Serial.println(wifiSSID);
  }
  else
  {
    Serial.println("<not configured>");
  }

  Serial.print("MQTT broker: ");
  Serial.println(MQTT_BROKER_NAME);

  Serial.print("MQTT user: ");

  if (mqttUser.length() > 0)
  {
    Serial.println(mqttUser);
  }
  else
  {
    Serial.println("<not configured>");
  }

  Serial.println("====================");

  // ----------------------------------------------------------
  // Inputs
  // ----------------------------------------------------------

  initInputs();

  // ----------------------------------------------------------
  // MQTT
  // ----------------------------------------------------------

  mqttClient.setBufferSize(1024);

  // ----------------------------------------------------------
  // Web server
  // ----------------------------------------------------------

  setupWebServer();

  // ----------------------------------------------------------
  // Start WiFi recovery system
  // ----------------------------------------------------------

  wifiDisconnectedSince = millis();

  if (wifiSSID.length() > 0)
  {
    beginWiFiConnection();
  }
  else
  {
    // No saved WiFi at all.
    startConfigAP();
  }

  Serial.println();
  Serial.println("================================");
  Serial.println("SYSTEM READY");
  Serial.println("================================");
}

// ============================================================
// LOOP
// ============================================================

void loop()
{
  // Inputs are always processed, even without network.
  updateInputs();

  // Maintain/recover WiFi.
  wifiLoop();

  // Maintain/recover MQTT.
  mqttLoop();

  // Configuration/status web page.
  server.handleClient();

  delay(2);
}