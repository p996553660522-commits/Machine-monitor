# Development and validation

## Run local tests

Requirements: Python 3.11+ and Node.js with `node:test` support. The publication environment used Python 3.14 and Node.js; no running Home Assistant is required for these tests.

From the repository root:

```sh
cd custom_components/machine_monitor
python -m unittest discover -s tests -p 'test_*.py'
node --check frontend/machine_monitor_card.js
node --test tests/frontend.test.cjs tests/v6_frontend.test.cjs tests/localization.test.cjs
```

The Python tests provide minimal Home Assistant boundary stubs. Frontend tests use a minimal DOM harness. Passing these tests does not claim full compatibility with every HA release or hardware configuration.

## Required regressions

- Concurrent physical inputs survive semantic priority resolution.
- ON → OFF closes at the observed timestamp.
- ON → unavailable → available/ON creates two physical intervals and an OFFLINE gap.
- OFF → unavailable → available/OFF creates no false ON interval.
- OFFLINE is retained historically and excluded from ordinary work/idle productivity.
- Manual row order survives validation.
- Persistence, restart reconciliation, retention and backward schema loading.
- Names and colors reach API/UI from the canonical profile.
- Event-driven updates, debounce, fallback polling, subscription cleanup.
- Filters, navigator, standalone card, editor, reports and localization.

## Hardware validation checklist

1. Record board model, Arduino ESP32 core, PubSubClient and HA versions.
2. Compile/flash the supplied sketch and configure Wi-Fi/MQTT.
3. Verify all four GPIO channels against actual source entities.
4. Turn two inputs on simultaneously and compare physical tracks with semantic state.
5. Disconnect/reconnect the module while ON and while OFF; verify honest gaps.
6. Restart HA and verify persistent history/startup reconciliation.
7. Test HA birth and MQTT reconnect; check republished current states.
8. Test retention and reports using known short periods before a long deployment.

Do not test by issuing commands to start/stop industrial equipment through Machine Monitor: no such control interface exists.

## Contribution scope

Read `AGENTS.md` before making changes. Preserve firmware/MQTT protocol and physical/semantic separation unless the owner explicitly requests a redesign. Include a reproduction and behavioral test for fixes. Do not add production credentials, `.storage`, complete HA configuration, compiled artifacts or private logs to Git.

A distribution license has not been selected; contact the owner before reuse beyond GitHub's applicable platform permissions.
