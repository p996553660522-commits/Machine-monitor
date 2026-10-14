# Publication validation — 2026-10-09

Validated the staged repository, not just the pre-existing installed component:

- Python unittest: **88 passed**.
- Node frontend regressions: **36 passed**.
- `node --check frontend/machine_monitor_card.js`: passed.
- Python AST and JSON syntax: passed.
- Local Markdown documentation links: passed.
- Token/private-key scan: no matches in the publication files.
- Firmware text matches the supplied attachment after newline normalization.

A curated allowlist was used: integration sources, bundled UI, translations, tests, engineering specification, firmware and newly written documentation. No persistent HA history, local reports/attachments, NVS credentials, caches, binaries or full HA configuration are included. The firmware's literal default AP password is documented as a public default.

## Limits

The local Python suite uses HA boundary stubs; the Node suite uses a minimal DOM. These results are not a live HA compatibility matrix. The included firmware has not been compiled/flashed in this publication environment because an Arduino ESP32 build toolchain is not installed. No industrial machine was controlled or reconfigured during publication.

Integration version: 1.2.2. Firmware Discovery version: 1.1. No distribution license selected yet.

## Signal-line enable update — 2026-10-12

Integration 1.3.0 / firmware 1.2, checked in the installed component and repository copy:

- Python unittest: **97 passed** (9 new regression scenarios).
- Node frontend regressions: **37 passed** (disabled acquisition label with preserved history).
- `node --check frontend/machine_monitor_card.js`: passed.
- Arduino CLI build: **passed**, ESP32 Dev Module (`esp32:esp32:esp32`), Arduino ESP32 core **3.3.11**, PubSubClient **2.8**. Flash **977156 / 1310720 bytes (74%)**, globals **49816 / 327680 bytes (15%)**.
- Build uses existing installed board libraries and a temporary ctags path override; automatic downloads of CLI discovery tools returned HTTP 403, but these are not required for the successful compile. No upload command was executed.

New regressions cover one/three-input device creation, adding/removing optional bindings, missing slot options editor, three enabled + disabled unavailable fourth input at startup, attribute-only disable of ON, closing/reopening physical intervals, disable/re-enable OFF, all lines disabled, independent manual profile permission, live event notification, reload persistence and preserved work/idle/offline totals. Existing concurrency, priority, startup reconciliation, row order, filters, reports, event-driven refresh and fallback tests remain passing.

Python tests still use HA boundaries and Node uses a minimal DOM. The new firmware has **not** been flashed or tested electrically on a physical three-optocoupler device. On-device acceptance: turn off Input 4, save/reboot, verify its MQTT source is unavailable with acquisition_enabled=false, confirm Machine Monitor stays online when inputs 1–3 are valid, toggle each connected input, and inspect independent history/statistics. A reboot/real module disconnect should still produce OFFLINE for enabled sources.

## First-boot network initialization fix — 2026-10-14

Firmware 1.2.1 moves HTTP server startup after WiFi initialization in both boot branches (saved STA credentials and empty-NVS configuration AP). Installed ESP32 core source confirms NetworkServer::begin opens a TCP socket, while WiFi initialization calls Network.begin/esp_netif_init. The reported crash occurs before the old web-server startup completion log.

Two source-level regression guards pass for startup order and initialization in both WiFi helpers. These guards do not execute the sketch on hardware. Full ESP32 Dev Module compilation passed with Arduino ESP32 core 3.3.11 and PubSubClient 2.8 (977156 flash bytes, 49816 global RAM bytes); the user must confirm first boot on the actual board. No HA monitoring changes or NVS reset is required.


## Universal modes release 1.4.0 — 2026-10-14

Developed and tested in a local checkout, without using the running HA network share for development.

- Python integration tests: **104 passed**. Imports use HA boundary stubs.
- Node frontend tests: **44 passed** with a minimal DOM.
- Firmware source guards: **2 passed**; firmware remains 1.2.1, unchanged in this release.
- JavaScript syntax, Python AST/import checks, JSON and `git diff --check`: passed.
- Regression coverage: arbitrary mode labels, profile serialization, accounting snapshots and migration from schema 3, future-only accounting edits, independent physical ON during profile edits, OR-of-AND truth table, fan-dependent cooling, unknown/disabled input conditions, deterministic priority, fallback, reload persistence, mode duration, graphical rules wizard and 16-group limit.
- Browser coverage: strict <10-second gap grouping, independent rows, exact toggle, preserved offline/ON totals, Russian/local preference, mixed-offset event ordering, zoom-clipped gaps and bounded dense-burst styles. Grouping 10,000 intervals took roughly 8–12 ms on the development PC; Raspberry Pi/browser performance is not measured.
- Existing concurrency, physical OFFLINE boundaries, work/idle/offline statistics, input names, row order, filters, reports, sidebar resources and event-driven/fallback regression tests remain passing.

No new background job or backend polling was introduced. HA runtime acceptance remains a separate check after installation/restart; automated results do not assert live hardware validation.
