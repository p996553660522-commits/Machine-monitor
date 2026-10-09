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
