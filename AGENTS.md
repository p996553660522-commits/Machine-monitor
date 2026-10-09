# Machine Monitor — Project Instructions for Coding Agents

## 1. Purpose of this file

This file is the persistent engineering specification for the **Machine Monitor** project.

Read it before changing the project. Treat it as the architectural source of truth unless the user explicitly gives a newer instruction.

The goal is not merely to make the code compile. The goal is to build a reliable, reusable equipment-monitoring system for real workshop machines using ESP32 input modules, MQTT and Home Assistant.

When implementation details conflict with the intent described here, preserve the intent and fix the implementation.

Do not rewrite working subsystems without a concrete reason. Prefer small, testable changes. Before large refactors, inspect the existing implementation and preserve compatible functionality.

---

# 2. Product goal

Machine Monitor is a universal monitoring system for industrial/workshop equipment.

A machine has an ESP32 monitor connected to existing machine signals through optocouplers. The monitor observes signals only. It does not control the machine.

The complete conceptual chain is:

```text
Physical machine signals
        ↓
Optocouplers
        ↓
ESP32
        ↓
MQTT
        ↓
Home Assistant MQTT entities
        ↓
Machine Monitor integration
        ├── Physical Input History
        ├── Semantic State Engine
        ├── Statistics
        ├── Event History
        └── Machine Profile
        ↓
Universal Machine Monitor UI
```

The final product should let a workshop user understand:

- what a machine is doing now;
- how long the current condition has lasted;
- which physical signals were active and when;
- how much time was spent working, idle, preparing, cooling, heating, waiting, etc.;
- when the monitoring module or machine data became unavailable;
- how activity changed over a selected period;
- where downtime occurred;
- how multiple machines compare.

It should feel like a dedicated equipment-monitoring product, not a collection of manually assembled Home Assistant cards.

---

# 3. Current hardware and upstream system

The current physical monitor uses:

- ESP32 DevKit / classic ESP32-WROOM-32 class hardware;
- 4-channel PC817 optocoupler board;
- XL4015E power converter;
- four digital inputs.

Current confirmed ESP32 input mapping:

```text
Input 1 → GPIO32
Input 2 → GPIO33
Input 3 → GPIO25
Input 4 → GPIO26
```

Inputs use `INPUT_PULLUP`.

Optocoupler semantics:

```text
GPIO LOW  = physical signal active
GPIO HIGH = physical signal inactive
```

All four channels have already been physically tested.

Do not redesign the ESP32 firmware unless explicitly requested.

In particular, do not move Machine Monitor semantics into the ESP32. The ESP32 is intentionally a raw physical acquisition layer.

---

# 4. MQTT architecture

The ESP32 publishes four raw binary states.

Current topic pattern:

```text
machine_monitor/<deviceId>/state/input1
machine_monitor/<deviceId>/state/input2
machine_monitor/<deviceId>/state/input3
machine_monitor/<deviceId>/state/input4
```

Availability:

```text
machine_monitor/<deviceId>/availability
```

Home Assistant MQTT Discovery is used.

The MQTT → Home Assistant chain is already proven to work in real hardware.

Machine Monitor should consume Home Assistant entities rather than tightly coupling itself to one hard-coded MQTT device implementation.

This allows future machines and acquisition devices to reuse the same integration.

---

# 5. Fundamental architecture rule: physical history and semantic history are different

This is the most important architectural rule in the project.

There are TWO separate concepts:

```text
A. Physical Input History
B. Semantic Machine State
```

They must never be collapsed into one data stream.

## 5.1 Physical Input History

Each configured physical input has an independent ON/OFF history.

Example:

```text
Input 1 — Heating
Input 2 — Work
Input 3 — Cooling
Input 4 — Idle
```

If Heating and Work are ON simultaneously, BOTH physical histories must preserve that fact.

Example:

```text
             10:00      10:10      10:20      10:30

Heating      ███████████████████
Work                    ███████████████████
```

Physical history is used primarily by:

- Real Flow;
- per-input activity statistics;
- activation counts;
- physical diagnostics;
- historical investigation.

## 5.2 Semantic Machine State

The semantic state answers a different question:

> What is the machine considered to be doing right now?

Multiple physical inputs may be active simultaneously, so semantic state is resolved using configurable priorities.

Example:

```text
Heating priority = 60
Work priority    = 100
```

If both are active:

```text
Physical history:
Heating = ON
Work    = ON

Semantic state:
WORK
```

This is correct.

Semantic priority must NEVER delete or hide concurrent physical input history.

---

# 6. Machine profiles

Each monitored machine should have a configurable Machine Profile.

A profile maps raw Home Assistant binary sensors to machine-specific meanings.

Example painting chamber:

```text
Input 1 = Heating
Input 2 = Work
Input 3 = Cooling
Input 4 = Idle
```

Example laser machine:

```text
Input 1 = Source
Input 2 = Idle
Input 3 = Setup
Input 4 = Work
```

Per-input configuration should support, where applicable:

- name;
- description;
- semantic state/category;
- priority;
- icon;
- color;
- enabled/disabled;
- visible/hidden;
- include in statistics;
- include in Real Flow;
- counts as productive work;
- counts as idle;
- row order.

Do not assume the four inputs mean the same thing on every machine.

---

# 7. Semantic states

The current architecture includes semantic states such as:

- work;
- idle;
- preparation;
- waiting;
- technical;
- cooling;
- heating;
- alarm;
- other;
- offline.

Do not add more semantic states merely because it is easy to do so. New states should solve a real machine-monitoring need.

Priority resolution should remain deterministic.

Example conceptual priorities:

```text
work        100
alarm        90
cooling      80
heating      60
idle         10
```

Exact values are profile/configuration concerns.

---

# 8. OFFLINE semantics — critical rule

`OFFLINE` is not `IDLE`.

This distinction is essential.

## IDLE

The monitoring system is online and has valid input information, but the machine is not performing productive work according to its configured state logic.

## OFFLINE

The system cannot reliably determine machine state because the configured source entities/module are unavailable.

Offline time is UNKNOWN machine activity, not idle machine activity.

Never silently convert offline time into idle time.

---

# 9. OFFLINE history

Offline must be represented as a real historical interval.

Example:

```text
10:20 module becomes unavailable
10:45 module becomes available
```

History must preserve:

```text
10:20 ─────────────── 10:45
          OFFLINE
```

Offline periods should be visible in Real Flow using a visually distinct neutral representation.

They should support:

- offline duration;
- last-seen information;
- historical inspection;
- downtime analysis where appropriate.

However, offline time must not be incorrectly counted as productive work or normal idle time.

Keep timeline visibility and productivity-statistics inclusion as separate concepts.

---

# 10. Physical inputs across OFFLINE periods

A physical ON interval must not continue through an unavailable period.

Example:

```text
10:00 Input 1 ON
10:20 module unavailable
10:45 module available
10:45 Input 1 observed ON again
```

Correct physical history:

```text
Input 1
10:00 ─────── 10:20

OFFLINE
10:20 ─────── 10:45

Input 1
10:45 ───────>
```

Incorrect:

```text
Input 1
10:00 ───────────────── 10:45
```

During offline time, physical input state is unknown.

Therefore:

### available → unavailable

If an input has an open ON interval:

- close it at the availability-loss timestamp.

### unavailable → available

After current entity state is known:

- if input is ON, open a NEW interval;
- if input is OFF, do not open an interval.

Never reconstruct unknown activity during the offline gap unless a future data source explicitly provides authoritative buffered history.

---

# 11. Persistent history

History must survive Home Assistant restarts.

The integration currently uses Home Assistant persistent storage / `Store` architecture.

Preserve backward compatibility where practical.

If a storage schema changes:

1. define a version;
2. provide migration or safe compatibility handling;
3. do not silently destroy existing machine history;
4. test loading old data.

Physical input intervals and semantic intervals should remain logically separate.

---

# 12. Real Flow — primary visualization

Real Flow is one of the central product features.

It is NOT a semantic-state-only graph.

Its primary detailed view should show all configured physical inputs against ONE COMMON horizontal time axis.

Example:

```text
             08:00      09:00      10:00      11:00

Heating      ███████████
Work                  ███████████████████
Cooling                             ███████
Idle                                      █████████
```

Requirements:

- one shared X/time axis;
- one row per physical input in detailed mode;
- independent physical intervals;
- simultaneous signals must remain visible simultaneously;
- each input visually distinguishable;
- offline periods clearly visible;
- current-time/NOW indication where useful;
- useful tooltips;
- responsive layout;
- historical periods selectable.

Do not derive Real Flow exclusively from semantic winner intervals.

---

# 13. Real Flow filters

Users must be able to independently show/hide physical inputs.

Examples:

```text
☑ Heating
☑ Work
☐ Cooling
☐ Idle
```

Supported combinations must include:

- one visible input;
- any two inputs;
- any three inputs;
- all inputs;
- convenient All / None actions where useful.

Filtering is a display concern and must not destroy stored history.

---

# 14. Real Flow row ordering

The UI should support meaningful row ordering.

Possible modes:

- custom/manual;
- name;
- activity duration;
- activation count;
- last activity.

Manual/custom ordering must preserve the user's exact order.

If stored order is:

```text
input_3
input_1
input_4
input_2
```

it must not be normalized back to:

```text
input_1
input_2
input_3
input_4
```

When validating row order:

- preserve valid user ordering;
- remove duplicates;
- ignore unknown entries;
- append missing valid inputs at the end.

A graphical drag-and-drop editor is desirable but is not required for every patch unless explicitly requested.

---

# 15. Real Flow periods and navigation

The user should be able to inspect useful time windows such as:

- 1 hour;
- 6 hours;
- 12 hours;
- today;
- yesterday;
- this week;
- last week;
- this month;
- last 7 days;
- last 30 days;
- custom range.

Zoom/pan may be provided where practical.

All rows must stay synchronized to the same time range.

---

# 16. Real Flow tooltip

A physical interval tooltip should provide useful operational information, for example:

```text
Heating
ON
Start: 10:03:12
End: 10:24:48
Duration: 21m 36s
```

For an open interval:

```text
End: NOW
```

Offline tooltip should clearly say OFFLINE/unavailable rather than implying a physical input state.

---

# 17. Compact mode

A compact overview mode may coexist with the detailed physical-input rows.

Compact mode can combine information into a smaller visualization, but it must not replace the detailed view or cause loss of physical history.

The detailed view remains the authoritative diagnostic view.

---

# 18. Statistics

Statistics should help answer practical workshop questions rather than simply expose every stored number.

Useful concepts include:

- productive/work duration;
- idle duration;
- preparation duration;
- waiting duration;
- technical/downtime duration;
- per-input active duration;
- activation count;
- percentages;
- current-state duration;
- offline duration;
- offline percentage;
- period comparison;
- downtime analysis.

Offline must be handled carefully.

Do not let offline time silently distort work/idle productivity percentages.

If productivity is defined only over known machine time, make that denominator explicit and consistent.

---

# 19. Event history

Machine Monitor should maintain useful historical events/intervals for investigation.

Event history should not become a noisy raw Home Assistant state dump.

Prefer meaningful machine/input events with:

- start;
- end;
- duration;
- state/input;
- relevant source information.

---

# 20. Current status

The UI should prominently show:

- machine name;
- current semantic state;
- duration of current state;
- online/offline condition;
- last seen when offline.

The duration display should update locally without requiring a heavy backend request every second.

---

# 21. UI update latency

Machine monitoring should feel live.

The old implementation relied heavily on a 15-second refresh and was too slow.

The preferred architecture is event-driven:

```text
HA source entity changes
        ↓
Machine Monitor event engine
        ↓
Machine Monitor change event / update signal
        ↓
frontend refresh
```

Target visual response is approximately 1–2 seconds or better under normal conditions.

A fallback polling refresh around 5 seconds is acceptable for resilience, but it should not be the primary mechanism.

Avoid redundant full WebSocket fetches for bursts of related events. Debounce/coalesce where useful.

A local one-second UI timer may update displayed elapsed duration without re-fetching complete history.

---

# 22. Home Assistant integration philosophy

Machine Monitor should behave like a coherent custom integration/product.

Prefer graphical configuration and options flows over requiring users to manually edit YAML.

The user should not need to hand-build a different Lovelace dashboard for every machine.

The integration should manage machine profiles and expose a reusable universal frontend/card.

Keep compatibility with current Home Assistant APIs and patterns.

Do not use deprecated APIs when a current supported equivalent exists.

---

# 23. Multi-machine support

The architecture must support multiple machines.

Each machine may have:

- different input meanings;
- different priorities;
- different colors/icons;
- different statistics;
- different row order;
- different enabled inputs.

Eventually the UI should support a useful overview of all monitored machines.

Do not hard-code behavior for the current painting chamber.

The painting chamber is a real test machine, not the product definition.

---

# 24. Existing project components

The project has used components/files including:

```text
__init__.py
config_flow.py
const.py
models.py
storage.py
event_engine.py
stats.py
machine.py
coordinator.py
sensor.py
binary_sensor.py
websocket_api.py
services.yaml
translations/
frontend/machine_monitor_card.js
dashboard.yaml
```

Names may evolve, but before adding parallel implementations inspect whether the required responsibility already exists.

Avoid duplicate engines, duplicate history stores, duplicate frontend render paths, or two competing definitions of the same state.

---

# 25. Current known historical implementation lesson

An earlier implementation stored only the highest-priority semantic winner in history.

Conceptually it did this:

```python
available_active = [input for input in considered if input.is_available and input.is_on]
winner = max(available_active, key=priority)
new_state = winner.semantic_state
history.open_interval(state=new_state)
```

That is valid for semantic state history but INVALID as the only source for Real Flow.

It loses concurrent physical activity.

Never reintroduce this architecture mistake.

---

# 26. Frontend quality rules

Before considering frontend changes complete:

- ensure there is one coherent render path;
- remove dead duplicated fragments;
- ensure newly created controls are actually inserted into the active UI;
- ensure event listeners are cleaned up when appropriate;
- avoid accidental duplicate subscriptions;
- avoid unnecessary full rerenders where local updates suffice;
- verify browser-compatible JavaScript syntax.

Always run a JavaScript syntax check where Node is available:

```bash
node --check frontend/machine_monitor_card.js
```

Do not claim frontend work is complete if this fails.

---

# 27. Python quality rules

For changed Python files:

- syntax-check them;
- run available tests;
- preserve Home Assistant async conventions;
- do not block the HA event loop;
- avoid unnecessary polling;
- keep entity/state listeners properly cleaned up;
- preserve config-entry unload behavior;
- log useful failures without flooding logs.

Use the project's available test/lint tooling rather than inventing a second toolchain unnecessarily.

---

# 28. Required behavioral tests

At minimum, preserve tests for these scenarios.

## 28.1 Independent concurrent inputs

```text
Input 1 ON
Input 2 ON
```

Both physical histories must contain intervals.

## 28.2 Semantic priority

If Input 1 and Input 2 are ON simultaneously, semantic state chooses the configured higher priority.

Physical history still contains both.

## 28.3 ON → OFF

The physical interval closes at the correct timestamp.

## 28.4 ON → unavailable → available + ON

Expected:

```text
ON interval #1
OFFLINE interval
ON interval #2
```

There must not be one continuous ON interval across the offline gap.

## 28.5 OFF → unavailable → available + OFF

No false ON interval may appear.

## 28.6 OFFLINE history

Offline interval exists and can be returned to the frontend.

## 28.7 OFFLINE statistics

Offline does not become normal idle or productive work.

## 28.8 Row order

Input:

```text
input_3, input_1, input_4, input_2
```

Output order must remain:

```text
input_3, input_1, input_4, input_2
```

## 28.9 Restart persistence

Persisted history reloads correctly after integration/Home Assistant restart.

## 28.10 Frontend syntax

`machine_monitor_card.js` must pass syntax validation.

---

# 29. Data integrity over pretty graphs

Never fabricate or interpolate machine activity simply to make a graph look continuous.

Examples:

- offline gap = unknown, not idle;
- unavailable input = unknown, not automatically OFF;
- missing history must not be guessed;
- a semantic winner does not mean other physical signals were inactive.

For industrial monitoring, an honest gap is better than false precision.

---

# 30. Performance philosophy

The system should remain practical on a Home Assistant Raspberry Pi-class installation.

Avoid:

- rereading all historical data on every minor state change;
- rebuilding huge timelines every second;
- unbounded in-memory history;
- excessive HA bus events;
- unnecessary duplicate WebSocket calls.

Prefer:

- event-driven updates;
- bounded queries by selected period;
- efficient interval representation;
- cached/aggregated statistics where justified;
- frontend-local elapsed timers;
- incremental updates where complexity remains reasonable.

Correctness comes before micro-optimization, but avoid obviously wasteful architecture.

---

# 31. UX philosophy

The primary user is a technically capable workshop operator/engineer, not a Home Assistant developer.

The interface should make machine behavior obvious at a glance.

Prioritize:

1. current condition;
2. timeline/Real Flow;
3. work/idle/offline proportions;
4. useful filters;
5. downtime investigation;
6. deeper diagnostics.

Avoid forcing users to understand internal entity IDs or MQTT topics during normal use after initial machine setup.

---

# 32. Scope boundaries

Unless explicitly requested, DO NOT modify or add:

- ESP32 firmware;
- MQTT topic protocol;
- SD-card buffering;
- machine control outputs;
- CSV export;
- PDF export;
- unrelated Home Assistant configuration;
- unrelated dashboards;
- new external cloud dependencies.

These may be future features, but they are not permission to expand the current task.

---

# 33. Safety / control boundary

Machine Monitor is currently observational.

Do not add commands that start, stop or otherwise control industrial machinery without an explicit separate design and safety review.

Monitoring logic must never be mistaken for a safety interlock.

---

# 34. How to approach a requested change

Before editing:

1. inspect the relevant existing files;
2. identify the actual data flow;
3. determine whether the problem is backend, storage, frontend or a combination;
4. avoid solving a backend data-loss problem only with JavaScript;
5. preserve existing working behavior;
6. make the smallest coherent architectural change;
7. test the behavior, not merely syntax.

For substantial changes, trace the complete chain:

```text
source entity
→ event engine
→ storage/runtime
→ websocket/coordinator
→ frontend
```

---

# 35. Definition of done

A task is not done merely because code was generated.

Before reporting completion:

1. changed files must parse/compile;
2. relevant automated tests must pass;
3. new behavior must have a test where practical;
4. old important behavior must remain intact;
5. frontend controls must actually be connected to the active render path;
6. persistent-data changes must be safe;
7. known failures must be reported honestly.

Final implementation reports should contain:

```text
CHANGED FILES
- ...

FIXED / IMPLEMENTED
- ...

TESTS RUN
- ...

RESULTS
- ...

REMAINING KNOWN ISSUES
- ...
```

Do not report "complete" when tests are failing or a requested behavior is still knowingly missing.

---

# 36. Current immediate repair priorities

When working on the current Machine Monitor 1.1 branch/version, verify these known areas first because they were identified during review:

1. `frontend/machine_monitor_card.js` must contain no duplicated code outside methods and must pass `node --check`.
2. `_renderInputFilters(d)` must actually be connected to the active machine render path.
3. OFFLINE must be stored as historical information visible to the timeline without corrupting productivity statistics.
4. Physical ON intervals must close when an input becomes unavailable and reopen only after availability returns with a confirmed ON state.
5. Custom `row_order` must preserve the user's exact valid order.
6. Real Flow must consume independent physical input history rather than only semantic winner history.
7. Event-driven UI updates must remain the primary refresh mechanism; fallback polling is secondary.

Fix these surgically. Do not use them as an excuse for an unrelated rewrite.

---

# 37. Longer-term product direction

After the current foundation is stable, desirable future evolution includes:

- polished multi-machine overview;
- easier graphical profile editor;
- drag-and-drop input row ordering;
- stronger downtime analysis;
- comparisons between shifts/days/weeks;
- better long-period aggregation;
- configurable production KPIs;
- richer machine-specific profiles;
- optional export/reporting.

These are direction, not current mandatory scope.

The priority remains:

> trustworthy data first, useful visualization second, additional features third.

---

# 38. Final architectural summary

Always preserve this mental model:

```text
                    MACHINE MONITOR

Raw HA inputs
     │
     ├───────────────┐
     │               │
     ▼               ▼
Physical history   Semantic engine
     │               │
     │               └── priority → current machine state
     │
     ├── Real Flow
     ├── input statistics
     └── diagnostics

Availability
     │
     ├── OFFLINE history
     ├── last seen
     └── closes uncertain physical intervals

All layers
     │
     ▼
Persistent storage → statistics → WebSocket/API → universal UI
```

Never collapse these layers into a single winner-state timeline.

The system should ultimately let the user look at a machine's page and understand, with minimal interpretation:

> What did this machine actually do, when did it do it, which physical signals prove it, how much useful work occurred, and where was information unavailable?
