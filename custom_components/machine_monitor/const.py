"""Constants for the Machine Monitor integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "machine_monitor"
INTEGRATION_NAME: Final = "Machine Monitor"
MANUFACTURER: Final = "Machine Monitor"
MODEL: Final = "4-channel MQTT monitor"

# --------------------------------------------------------------------------
# Physical layer
# --------------------------------------------------------------------------

# Physical input slots of the ESP32 node. These are pure signal names.
# They carry NO business meaning by themselves.
INPUT_SLOTS: Final = ("input_1", "input_2", "input_3", "input_4")

# --------------------------------------------------------------------------
# Semantic machine states
# --------------------------------------------------------------------------

STATE_OFFLINE: Final = "offline"
STATE_WORK: Final = "work"
STATE_IDLE: Final = "idle"
STATE_PREPARATION: Final = "preparation"
STATE_WAITING: Final = "waiting"
STATE_TECHNICAL: Final = "technical"
STATE_COOLING: Final = "cooling"
STATE_HEATING: Final = "heating"
STATE_ALARM: Final = "alarm"
STATE_OTHER: Final = "other"

#: Every semantic state the system understands.
SEMANTIC_STATES: Final = (
    STATE_OFFLINE,
    STATE_ALARM,
    STATE_TECHNICAL,
    STATE_WORK,
    STATE_PREPARATION,
    STATE_COOLING,
    STATE_HEATING,
    STATE_WAITING,
    STATE_IDLE,
    STATE_OTHER,
)

#: States that represent productive machine time.
WORK_STATES: Final = (STATE_WORK,)

#: States that represent the machine being available but not productive.
IDLE_STATES: Final = (STATE_IDLE, STATE_WAITING, STATE_PREPARATION, STATE_COOLING, STATE_HEATING)

#: States excluded from the productive/idle accounting.
#: Note: exclusion from productivity does NOT mean exclusion from history.
EXCLUDED_STATES: Final = (STATE_OFFLINE,)

#: Alias making the intent explicit at the call sites that must keep offline
#: out of the work/idle percentages.
EXCLUDED_FROM_PRODUCTIVITY: Final = EXCLUDED_STATES

#: Every semantic state that is drawn on the Real Flow. OFFLINE is included:
#: a connection loss is a real historical period and must be visible, while
#: remaining excluded from the productivity statistics.
VISIBLE_IN_TIMELINE: Final = SEMANTIC_STATES

#: Default priority per state. Higher wins when several inputs are active.
STATE_PRIORITY: Final = {
    STATE_OFFLINE: -1,
    STATE_ALARM: 1000,
    STATE_TECHNICAL: 900,
    STATE_WORK: 800,
    STATE_PREPARATION: 700,
    STATE_COOLING: 600,
    STATE_HEATING: 500,
    STATE_WAITING: 400,
    STATE_IDLE: 100,
    STATE_OTHER: 50,
}

#: Default colour per state, used by the dashboard and entities.
STATE_COLOR: Final = {
    STATE_OFFLINE: "#9e9e9e",
    STATE_ALARM: "#e53935",
    STATE_TECHNICAL: "#8e24aa",
    STATE_WORK: "#2e7d32",
    STATE_PREPARATION: "#fb8c00",
    STATE_COOLING: "#039be5",
    STATE_HEATING: "#f4511e",
    STATE_WAITING: "#fdd835",
    STATE_IDLE: "#757575",
    STATE_OTHER: "#bdbdbd",
}

#: Default icon per state.
STATE_ICON: Final = {
    STATE_OFFLINE: "mdi:lan-disconnect",
    STATE_ALARM: "mdi:alert-octagon",
    STATE_TECHNICAL: "mdi:wrench",
    STATE_WORK: "mdi:play-circle",
    STATE_PREPARATION: "mdi:tools",
    STATE_COOLING: "mdi:snowflake",
    STATE_HEATING: "mdi:fire",
    STATE_WAITING: "mdi:timer-sand",
    STATE_IDLE: "mdi:pause-circle",
    STATE_OTHER: "mdi:help-circle",
}

# --------------------------------------------------------------------------
# Config entry / options keys
# --------------------------------------------------------------------------

CONF_MACHINE_ID: Final = "machine_id"
CONF_INPUTS: Final = "inputs"
CONF_NAME: Final = "name"
CONF_DESCRIPTION: Final = "description"
CONF_ENABLED: Final = "enabled"
CONF_ENTITY_ID: Final = "entity_id"
CONF_INPUT_NAME: Final = "input_name"
CONF_INPUT_DESCRIPTION: Final = "input_description"
CONF_ICON: Final = "icon"
CONF_COLOR: Final = "color"
CONF_SEMANTIC_STATE: Final = "semantic_state"
CONF_PRIORITY: Final = "priority"
CONF_SHOW_IN_TIMELINE: Final = "show_in_timeline"
CONF_INCLUDE_IN_STATISTICS: Final = "include_in_statistics"
CONF_NO_ACTIVE_STATE: Final = "no_active_state"
CONF_DOWNTIME_THRESHOLD: Final = "downtime_threshold"
CONF_HISTORY_LIMIT: Final = "history_limit"

DEFAULT_NAME: Final = "Machine"
DEFAULT_INPUT_NAME: Final = "Input"
DEFAULT_NO_ACTIVE_STATE: Final = STATE_IDLE
DEFAULT_DOWNTIME_THRESHOLD: Final = 10
DEFAULT_HISTORY_LIMIT: Final = 5000

#: When restoring an interval that was still open during a restart, it is
#: closed at most this many seconds after its start so a restart never
#: fabricates a huge bogus interval.
MAX_RESTORE_GAP_SECONDS: Final = 300

# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------

STORAGE_VERSION: Final = 1
STORAGE_KEY_PREFIX: Final = "machine_monitor"

# --------------------------------------------------------------------------
# Entity / attribute keys
# --------------------------------------------------------------------------

ATTR_MACHINE_ID: Final = "machine_id"
ATTR_STATE: Final = "state"
ATTR_STATE_LABEL: Final = "state_label"
ATTR_STATE_ICON: Final = "state_icon"
ATTR_STATE_COLOR: Final = "state_color"
ATTR_SINCE: Final = "since"
ATTR_DURATION_SECONDS: Final = "duration_seconds"
ATTR_SEMANTIC_STATE: Final = "semantic_state"
ATTR_INPUT_KEY: Final = "input_key"
ATTR_SOURCE_ENTITY: Final = "source_entity"
ATTR_PRIORITY: Final = "priority"
ATTR_ACTIVE: Final = "active"

#: Services
SERVICE_CLEAR_HISTORY: Final = "clear_history"
SERVICE_ADD_MARKER: Final = "add_marker"
ATTR_NOTE: Final = "note"
ATTR_MARKERS: Final = "markers"

#: Default polling interval for the coordinator.
SCAN_INTERVAL_SECONDS: Final = 30

# --------------------------------------------------------------------------
# Additional defaults referenced by the models
# --------------------------------------------------------------------------

DEFAULT_COLOR: Final = "#4caf50"
DEFAULT_ICON: Final = "mdi:ray-start"
DOWNTIME_THRESHOLD_KEY: Final = CONF_DOWNTIME_THRESHOLD

# --------------------------------------------------------------------------
# Real Flow / physical input layer
# --------------------------------------------------------------------------

#: Profile key holding the manual order of the Real Flow input rows.
CONF_ROW_ORDER: Final = "row_order"

#: State value stored for a physical input interval that is active.
INPUT_ON: Final = "on"
INPUT_OFF: Final = "off"

#: Neutral colour used to render offline periods on the Real Flow.
OFFLINE_COLOR: Final = "#9e9e9e"

#: Attributes exposed for the offline state.
ATTR_OFFLINE: Final = "offline"
ATTR_LAST_SEEN: Final = "last_seen"
ATTR_OFFLINE_FOR: Final = "offline_for_seconds"
ATTR_RECOVERED_AT: Final = "recovered_at"

# V6 per-machine historical retention (days), independent of transition count.
RETENTION_DAYS = (7, 14, 30, 60, 90, 180, 365)
DEFAULT_RETENTION_DAYS = 30
INPUT_COLORS = ("#f57c00", "#43a047", "#039be5", "#ab47bc")
