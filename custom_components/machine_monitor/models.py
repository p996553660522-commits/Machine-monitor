"""Domain models for Machine Monitor.

The models in this module contain NO hard coded business logic about which
physical input means what. A machine profile maps a physical input slot to a
user defined *semantic state*. Everything else (events, statistics, the
dashboard) preserves independent physical history alongside semantic history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .const import (
    INPUT_COLORS,
    DEFAULT_RETENTION_DAYS,
    CONF_COLOR,
    CONF_DESCRIPTION,
    CONF_ENABLED,
    CONF_ENTITY_ID,
    CONF_HISTORY_LIMIT,
    CONF_ICON,
    CONF_INCLUDE_IN_STATISTICS,
    CONF_INPUTS,
    CONF_INPUT_DESCRIPTION,
    CONF_INPUT_NAME,
    CONF_NAME,
    CONF_NO_ACTIVE_STATE,
    CONF_PRIORITY,
    CONF_ROW_ORDER,
    CONF_SEMANTIC_STATE,
    CONF_SHOW_IN_TIMELINE,
    DEFAULT_COLOR,
    DEFAULT_DOWNTIME_THRESHOLD,
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_INPUT_NAME,
    DEFAULT_NO_ACTIVE_STATE,
    DEFAULT_NAME,
    DOWNTIME_THRESHOLD_KEY,
    EXCLUDED_STATES,
    INPUT_SLOTS,
    SEMANTIC_STATES,
    STATE_COLOR,
    STATE_ICON,
    STATE_PRIORITY,
)


def normalize_row_order(order, slots=INPUT_SLOTS) -> list[str]:
    """Keep valid user order, remove duplicates, append missing slots."""
    if isinstance(order, str):
        order = [item.strip() for item in order.split(",")]
    valid = list(slots)
    result = []
    for slot in order or []:
        if slot in valid and slot not in result:
            result.append(slot)
    return result + [slot for slot in valid if slot not in result]


def normalize_color(value):
    """HA's colour selector returns RGB; stored/frontend colours are hex."""
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return "#" + "".join(f"{max(0, min(255, int(c))):02x}" for c in value)
    return value


def default_state_color(state: str) -> str:
    """Return the default colour for a semantic state."""
    return STATE_COLOR.get(state, STATE_COLOR["other"])


def default_state_icon(state: str) -> str:
    """Return the default icon for a semantic state."""
    return STATE_ICON.get(state, STATE_ICON["other"])


def default_state_priority(state: str) -> int:
    """Return the default priority for a semantic state."""
    return STATE_PRIORITY.get(state, STATE_PRIORITY["other"])


@dataclass(slots=True)
class InputConfig:
    """Configuration of one physical input slot of a machine."""

    entity_id: str
    semantic_state: str = "other"
    input_name: str = DEFAULT_INPUT_NAME
    input_description: str = ""
    icon: str | None = None
    color: str | None = None
    enabled: bool = True
    show_in_timeline: bool = True
    include_in_statistics: bool = True
    priority: int | None = None

    def __post_init__(self) -> None:
        # Availability alone owns OFFLINE; it is never a physical ON meaning.
        if self.semantic_state not in SEMANTIC_STATES or self.semantic_state == "offline":
            self.semantic_state = "other"
        self.color = normalize_color(self.color)

    @property
    def effective_priority(self) -> int:
        """Priority used to resolve competing active inputs."""
        if self.priority is not None:
            return self.priority
        return default_state_priority(self.semantic_state)

    @property
    def effective_icon(self) -> str:
        """Icon of the input, falling back to the state icon."""
        return self.icon or default_state_icon(self.semantic_state)

    @property
    def effective_color(self) -> str:
        """Colour of the input, falling back to the state colour."""
        return self.color or default_state_color(self.semantic_state)

    @property
    def display_name(self) -> str:
        """Human readable name of the input."""
        return (self.input_name or "").strip() or DEFAULT_INPUT_NAME

    def to_dict(self) -> dict[str, Any]:
        """Serialise the input configuration for storage."""
        return {
            CONF_ENTITY_ID: self.entity_id,
            CONF_SEMANTIC_STATE: self.semantic_state,
            CONF_INPUT_NAME: self.input_name,
            CONF_INPUT_DESCRIPTION: self.input_description,
            CONF_ICON: self.icon,
            CONF_COLOR: self.color,
            CONF_ENABLED: self.enabled,
            CONF_SHOW_IN_TIMELINE: self.show_in_timeline,
            CONF_INCLUDE_IN_STATISTICS: self.include_in_statistics,
            CONF_PRIORITY: self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InputConfig:
        """Build an input configuration from stored data."""
        return cls(
            entity_id=data.get(CONF_ENTITY_ID, ""),
            semantic_state=data.get(CONF_SEMANTIC_STATE, "other"),
            input_name=data.get(CONF_INPUT_NAME, DEFAULT_INPUT_NAME),
            input_description=data.get(CONF_INPUT_DESCRIPTION, ""),
            icon=data.get(CONF_ICON),
            color=normalize_color(data.get(CONF_COLOR)),
            enabled=bool(data.get(CONF_ENABLED, True)),
            show_in_timeline=bool(data.get(CONF_SHOW_IN_TIMELINE, True)),
            include_in_statistics=bool(
                data.get(CONF_INCLUDE_IN_STATISTICS, True)
            ),
            priority=data.get(CONF_PRIORITY),
        )


def validate_shifts(shifts) -> list[dict[str, str]]:
    result, occupied, names = [], set(), set()
    for raw in shifts or []:
        name = str(raw.get("name", "")).strip()
        start = datetime.strptime(raw["start"], "%H:%M").time()
        end = datetime.strptime(raw["end"], "%H:%M").time()
        a, b = start.hour * 60 + start.minute, end.hour * 60 + end.minute
        if not name or name in names or a == b:
            raise ValueError("Use unique shift names and different start/end times")
        minutes = set(range(a, b)) if b > a else set(range(a, 1440)) | set(range(b))
        if occupied & minutes:
            raise ValueError("Shifts must not overlap")
        occupied |= minutes
        names.add(name)
        result.append({"name": name, "start": start.strftime("%H:%M"), "end": end.strftime("%H:%M")})
    return result


@dataclass(slots=True)
class MachineProfile:
    """Full description of one monitored machine."""

    machine_id: str
    name: str = DEFAULT_NAME
    description: str = ""
    enabled: bool = True
    inputs: dict[str, InputConfig] = field(default_factory=dict)
    no_active_state: str = DEFAULT_NO_ACTIVE_STATE
    downtime_threshold: int = DEFAULT_DOWNTIME_THRESHOLD
    history_limit: int = DEFAULT_HISTORY_LIMIT
    #: Manual ordering of the physical input rows on the Real Flow.
    row_order: list[str] | None = None
    retention_days: int = DEFAULT_RETENTION_DAYS
    shifts: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.retention_days = max(1, min(365, int(self.retention_days)))
        self.shifts = validate_shifts(self.shifts)
        for slot, cfg in self.inputs.items():
            if not cfg.color and slot in INPUT_SLOTS:
                cfg.color = INPUT_COLORS[INPUT_SLOTS.index(slot)]
        if self.no_active_state not in SEMANTIC_STATES or self.no_active_state == "offline":
            self.no_active_state = DEFAULT_NO_ACTIVE_STATE

    def input_for(self, slot: str) -> InputConfig | None:
        """Return the input configuration for a slot, if any."""
        return self.inputs.get(slot)

    def entity_ids(self) -> list[str]:
        """Return all source entity ids of the machine."""
        return [cfg.entity_id for cfg in self.inputs.values() if cfg.entity_id]

    def enabled_inputs(self) -> list[InputConfig]:
        """Return enabled input configurations."""
        return [cfg for cfg in self.inputs.values() if cfg.enabled]

    def to_dict(self) -> dict[str, Any]:
        """Serialise the profile for storage."""
        return {
            "machine_id": self.machine_id,
            "retention_days": self.retention_days,
            "shifts": self.shifts,
            CONF_NAME: self.name,
            CONF_DESCRIPTION: self.description,
            CONF_ENABLED: self.enabled,
            CONF_NO_ACTIVE_STATE: self.no_active_state,
            DOWNTIME_THRESHOLD_KEY: self.downtime_threshold,
            CONF_HISTORY_LIMIT: self.history_limit,
            CONF_ROW_ORDER: list(self.row_order) if self.row_order else None,
            CONF_INPUTS: {k: v.to_dict() for k, v in self.inputs.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MachineProfile:
        """Build a profile from stored data."""
        raw_inputs = data.get(CONF_INPUTS) or {}
        inputs: dict[str, InputConfig] = {}
        for slot in INPUT_SLOTS:
            if slot in raw_inputs and raw_inputs[slot]:
                inputs[slot] = InputConfig.from_dict(raw_inputs[slot])
        return cls(
            machine_id=data.get("machine_id", ""),
            retention_days=data.get("retention_days", DEFAULT_RETENTION_DAYS),
            shifts=data.get("shifts", []),
            name=data.get(CONF_NAME, DEFAULT_NAME),
            description=data.get(CONF_DESCRIPTION, ""),
            enabled=bool(data.get(CONF_ENABLED, True)),
            inputs=inputs,
            no_active_state=data.get(
                CONF_NO_ACTIVE_STATE, DEFAULT_NO_ACTIVE_STATE
            ),
            downtime_threshold=int(
                data.get(DOWNTIME_THRESHOLD_KEY, DEFAULT_DOWNTIME_THRESHOLD)
            ),
            history_limit=int(
                data.get(CONF_HISTORY_LIMIT, DEFAULT_HISTORY_LIMIT)
            ),
            row_order=normalize_row_order(data.get(CONF_ROW_ORDER), inputs),
        )


@dataclass(slots=True)
class Interval:
    """A time interval during which the machine was in one semantic state."""

    start: datetime
    end: datetime | None
    state: str
    source_input: str | None = None
    source_entity: str | None = None

    @property
    def is_open(self) -> bool:
        """Return True when the interval has not been closed yet."""
        return self.end is None

    def duration_seconds(self, now: datetime | None = None) -> float:
        """Return the duration of the interval in seconds."""
        end = self.end
        if end is None:
            end = now
        if end is None or end <= self.start:
            return 0.0
        return (end - self.start).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Serialise the interval for storage and for the websocket API."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat() if self.end else None,
            "state": self.state,
            "source_input": self.source_input,
            "source_entity": self.source_entity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Interval:
        """Build an interval from stored data."""
        end_raw = data.get("end")
        return cls(
            start=datetime.fromisoformat(data["start"]),
            end=datetime.fromisoformat(end_raw) if end_raw else None,
            state=data.get("state", "other"),
            source_input=data.get("source_input"),
            source_entity=data.get("source_entity"),
        )


@dataclass(slots=True)
class ActiveInput:
    """Snapshot of one physical input at a point in time."""

    slot: str
    entity_id: str
    is_on: bool
    is_available: bool
    config: InputConfig
    raw_state: str | None = None
    last_changed: datetime | None = None
    source_error: str | None = None

    @property
    def semantic_state(self) -> str:
        """Semantic state of this input when it is active."""
        return self.config.semantic_state


@dataclass(slots=True)
class MachineSnapshot:
    """Point in time view of a machine used by entities and the API."""

    machine_id: str
    name: str
    state: str
    state_since: datetime
    source_input: str | None
    source_entity: str | None
    priority: int
    active_inputs: dict[str, bool | None]
    inputs_available: bool
    last_seen: datetime | None
    offline_since: datetime | None = None
    recovered_at: datetime | None = None

    @property
    def state_label(self) -> str:
        """Translated-neutral label of the state."""
        return self.state.replace("_", " ").title()

    def to_dict(self) -> dict[str, Any]:
        """Serialise the snapshot for the websocket API."""
        return {
            "machine_id": self.machine_id,
            "name": self.name,
            "state": self.state,
            "state_label": self.state_label,
            "state_icon": default_state_icon(self.state),
            "state_color": default_state_color(self.state),
            "state_since": self.state_since.isoformat(),
            "source_input": self.source_input,
            "source_entity": self.source_entity,
            "priority": self.priority,
            "active_inputs": self.active_inputs,
            "inputs_available": self.inputs_available,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "offline": self.state == "offline",
            "offline_since": (
                self.offline_since.isoformat() if self.offline_since else None
            ),
            "recovered_at": (
                self.recovered_at.isoformat() if self.recovered_at else None
            ),
        }
