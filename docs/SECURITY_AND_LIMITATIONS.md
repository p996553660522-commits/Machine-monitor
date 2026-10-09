# Security and known limitations / Ограничения

## Monitoring only

Machine Monitor observes equipment. It is not a safety interlock, emergency stop, control PLC or command interface. Data loss does not indicate that a machine is physically safe or stopped.

## Supplied ESP32 sketch

The sketch is published as supplied, without a security redesign:

- Setup AP uses a fixed password defined in `AP_PASSWORD`. It is a public default in source, not a per-device secret. Change it before a new deployment.
- The HTTP configuration page is unauthenticated and remains reachable on the station network after Wi-Fi connects. Password fields include saved Wi-Fi/MQTT values in the returned HTML.
- `/save` can replace the device settings and restart the ESP32 without authentication.
- MQTT uses ordinary TCP port 1883 without TLS; do not expose the web page or broker directly to the Internet.
- Device name/SSID values are inserted into HTML; Discovery device names are inserted into JSON without escaping. Restrict device names to simple safe characters until this is addressed in a separate firmware update.
- No offline event buffer or UTC event timestamps are provided. Current states are republished on reconnect; missed transitions cannot be reconstructed.
- MQTT publish delivery is not an authoritative lossless historical stream. Short pulses below the 50 ms debounce are not recorded.
- LWT availability depends on broker detection/connection timeout; it is not an instantaneous electrical connectivity measurement.

Use a trusted/segmented local network. Firmware hardening is a follow-up task, not a claim made by this publication.

## Integration/UI

- No exact minimum HA release is declared yet; the local tests use boundary stubs, not an installed HA matrix.
- The firmware toolchain versions used on the author's actual board are not recorded. Compilation was not performed in the publication environment.
- This integration is not declared HACS-listed. Manual installation is documented.
- Old semantic-only data contains no recoverable physical history.
- Longer retention keeps future data longer; it cannot restore deleted or unrecorded history.
- Current UI language preference is stored per browser, not server-wide or per HA user.
- Display filters/zoom are not promised to persist after a fresh browser session.
- File size is not a performance benchmark. Long-history/multi-machine load testing remains useful.
- No CSV/PDF export, cloud dependency, OTA update or machine-control output is included.

## Publishing and reports

The repository excludes HA configuration, `.storage`, logs, NVS dumps, local attachments, credentials and compiled binaries. The only password literal in the supplied sketch is its documented setup-AP default. Configure actual Wi-Fi/MQTT credentials on the device's setup page, not in a public commit.

When reporting a problem, provide versions, an anonymized reproduction and relevant log excerpts. Do not upload your full HA backup or secret-bearing ESP32 status page. Public visibility does not substitute for a project license; none has been selected yet.
