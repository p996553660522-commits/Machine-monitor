"""Sensor platform for Machine Monitor.

For every configured machine the following sensors are created:

* `current_state`        - the active semantic state
* `state_duration`       - seconds spent in the current state
* `work_time_today`      - productive time today
* `idle_time_today`      - non productive time today
* `work_percent_today`   - productive share today
* `idle_percent_today`   - non productive share today
* `downtime_count_today` - number of long downtime periods today
* `last_change`          - when the state last changed

All sensors are keyed by the stable machine id so renaming a machine never
breaks history.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DURATION_SECONDS,
    ATTR_MACHINE_ID,
    ATTR_PRIORITY,
    ATTR_SINCE,
    ATTR_SOURCE_ENTITY,
    ATTR_STATE,
    ATTR_STATE_COLOR,
    ATTR_STATE_ICON,
    ATTR_STATE_LABEL,
    DOMAIN,
    SEMANTIC_STATES,
)
from .coordinator import MachineMonitorCoordinator
from .models import default_state_color, default_state_icon

_LOGGER = logging.getLogger(__name__)


def _machine_slug(name: str) -> str:
    """Return a slug usable inside an entity id."""
    out = []
    for char in name.strip().lower():
        if char.isalnum():
            out.append(char)
        elif char in " -_":
            out.append("_")
    slug = "".join(out).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "machine"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Machine Monitor sensors."""
    coordinator: MachineMonitorCoordinator = hass.data[DOMAIN][
        "coordinator"
    ]
    runtime = coordinator.runtime_for(entry.entry_id)
    if runtime is None:
        return

    machine_id = entry.entry_id
    slug = _machine_slug(runtime.name)
    name = runtime.name

    entities: list[SensorEntity] = [
        MachineStateSensor(coordinator, machine_id, slug, name),
        StateDurationSensor(coordinator, machine_id, slug, name),
        WorkTimeSensor(coordinator, machine_id, slug, name),
        IdleTimeSensor(coordinator, machine_id, slug, name),
        WorkPercentSensor(coordinator, machine_id, slug, name),
        IdlePercentSensor(coordinator, machine_id, slug, name),
        DowntimeCountSensor(coordinator, machine_id, slug, name),
        LastChangeSensor(coordinator, machine_id, slug, name),
    ]
    async_add_entities(entities)


class MachineSensorBase(CoordinatorEntity[MachineMonitorCoordinator]):
    """Common base class for all machine sensors."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MachineMonitorCoordinator,
        machine_id: str,
        slug: str,
        machine_name: str,
        suffix: str,
        translation_key: str,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._machine_id = machine_id
        self._slug = slug
        self._machine_name = machine_name
        self._attr_unique_id = f"{machine_id}_{suffix}"
        self._attr_translation_key = translation_key
        self._attr_device_info = {
            "identifiers": {(DOMAIN, machine_id)},
            "name": machine_name,
            "manufacturer": "Machine Monitor",
            "model": "4-channel MQTT monitor",
            "configuration_url": None,
        }
        self._attr_extra_state_attributes = {
            ATTR_MACHINE_ID: machine_id
        }

    @property
    def _runtime(self):
        """Return the machine runtime."""
        return self.coordinator.runtime_for(self._machine_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the base attributes of every machine sensor."""
        return dict(self._attr_extra_state_attributes or {})

    @property
    def available(self) -> bool:
        """Sensors stay available while the runtime exists."""
        return self._runtime is not None

    def _now(self) -> datetime:
        """Return the current local time."""
        return datetime.now().astimezone()


class MachineStateSensor(MachineSensorBase):
    """The active semantic state of the machine."""

    def __init__(self, coordinator, machine_id, slug, name) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, machine_id, slug, name, "current_state", "current_state")
        self._attr_icon = "mdi:state-machine"

    @property
    def native_value(self) -> str | None:
        """Return the current semantic state."""
        runtime = self._runtime
        if runtime is None:
            return None
        return runtime.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the rich state attributes."""
        base = dict(self._attr_extra_state_attributes)
        runtime = self._runtime
        if runtime is None:
            return base
        snapshot = runtime.snapshot()
        now = self._now()
        base.update(
            {
                ATTR_STATE: snapshot.state,
                ATTR_STATE_LABEL: snapshot.state_label,
                ATTR_STATE_ICON: default_state_icon(snapshot.state),
                ATTR_STATE_COLOR: default_state_color(snapshot.state),
                ATTR_SINCE: snapshot.state_since.isoformat(),
                ATTR_DURATION_SECONDS: round(
                    runtime.engine.current_state_duration(now), 1
                ),
                ATTR_SOURCE_ENTITY: snapshot.source_entity,
                ATTR_PRIORITY: snapshot.priority,
                "active_inputs": snapshot.active_inputs,
                "last_seen": (
                    snapshot.last_seen.isoformat()
                    if snapshot.last_seen
                    else None
                ),
                "offline": snapshot.state == "offline",
            }
        )
        return base

    @property
    def available(self) -> bool:
        """Always available so operators see offline explicitly."""
        return self._runtime is not None


class StateDurationSensor(MachineSensorBase):
    """Seconds spent in the current state."""

    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator, machine_id, slug, name) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, machine_id, slug, name, "state_duration", "state_duration")

    @property
    def native_value(self) -> int | None:
        """Return the duration in seconds."""
        runtime = self._runtime
        if runtime is None:
            return None
        return int(runtime.engine.current_state_duration(self._now()))

    @property
    def available(self) -> bool:
        """Always available."""
        return self._runtime is not None


class _PeriodTimeSensor(MachineSensorBase):
    """Base class for the today work/idle time sensors."""

    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2

    _state_key = "work"

    @property
    def native_value(self) -> float | None:
        """Return the accumulated hours."""
        runtime = self._runtime
        if runtime is None:
            return None
        stats = runtime.stats("today", now=self._now())
        seconds = (
            stats.work_seconds
            if self._state_key == "work"
            else stats.idle_seconds
        )
        return round(seconds / 3600, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the raw seconds as well."""
        base = dict(self._attr_extra_state_attributes)
        runtime = self._runtime
        if runtime is None:
            return base
        stats = runtime.stats("today", now=self._now())
        seconds = (
            stats.work_seconds
            if self._state_key == "work"
            else stats.idle_seconds
        )
        base["seconds"] = round(seconds, 1)
        base["human"] = _humanise(seconds)
        return base


class WorkTimeSensor(_PeriodTimeSensor):
    """Productive hours today."""

    _state_key = "work"
    _attr_icon = "mdi:play-box-outline"

    def __init__(self, coordinator, machine_id, slug, name) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, machine_id, slug, name, "work_time_today", "work_time_today")


class IdleTimeSensor(_PeriodTimeSensor):
    """Non productive hours today."""

    _state_key = "idle"
    _attr_icon = "mdi:pause-box-outline"

    def __init__(self, coordinator, machine_id, slug, name) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, machine_id, slug, name, "idle_time_today", "idle_time_today")


class _PercentSensor(MachineSensorBase):
    """Base class for the percentage sensors."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:percent"

    _use_work = True

    @property
    def native_value(self) -> float | None:
        """Return the percentage."""
        runtime = self._runtime
        if runtime is None:
            return None
        stats = runtime.stats("today", now=self._now())
        return stats.work_percent if self._use_work else stats.idle_percent

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the comparison with the previous day."""
        base = dict(self._attr_extra_state_attributes)
        runtime = self._runtime
        if runtime is None:
            return base
        payload = runtime.stats_with_comparison("today", now=self._now())
        base["comparison"] = payload["comparison"]
        base["previous"] = payload["previous"]
        return base


class WorkPercentSensor(_PercentSensor):
    """Productive share today."""

    _use_work = True

    def __init__(self, coordinator, machine_id, slug, name) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, machine_id, slug, name, "work_percent_today", "work_percent_today")


class IdlePercentSensor(_PercentSensor):
    """Non productive share today."""

    _use_work = False

    def __init__(self, coordinator, machine_id, slug, name) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, machine_id, slug, name, "idle_percent_today", "idle_percent_today")


class DowntimeCountSensor(MachineSensorBase):
    """Number of downtime periods longer than the threshold."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:timer-alert-outline"

    def __init__(self, coordinator, machine_id, slug, name) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, machine_id, slug, name, "downtime_count_today", "downtime_count_today")

    @property
    def native_value(self) -> int | None:
        """Return the downtime count."""
        runtime = self._runtime
        if runtime is None:
            return None
        return runtime.stats("today", now=self._now()).downtime.count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return downtime details."""
        base = dict(self._attr_extra_state_attributes)
        runtime = self._runtime
        if runtime is None:
            return base
        info = runtime.downtime("today", now=self._now())
        base.update(
            {
                "threshold_minutes": info["threshold_minutes"],
                "total_seconds": info["total_seconds"],
                "average_seconds": info["average_seconds"],
                "longest_seconds": info["longest_seconds"],
                "periods": info["periods"][:20],
            }
        )
        return base


class LastChangeSensor(MachineSensorBase):
    """Timestamp of the last state change."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:history"

    def __init__(self, coordinator, machine_id, slug, name) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, machine_id, slug, name, "last_change", "last_change")

    @property
    def native_value(self) -> datetime | None:
        """Return the last change timestamp."""
        runtime = self._runtime
        if runtime is None:
            return None
        return runtime.snapshot().state_since


def _humanise(seconds: float) -> str:
    """Format seconds as `1h 02m 03s`."""
    total = int(max(0.0, seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"
