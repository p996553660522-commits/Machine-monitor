"""Binary sensor platform for Machine Monitor.

One binary sensor is created per configured physical input. These entities are
the diagnostic layer: they show the raw physical signal together with the
semantic meaning the operator assigned to it.

The system logic never depends on the entity names `input_1` ... `input_4`
but only on the semantic state configured for the slot.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_INPUT_KEY,
    ATTR_MACHINE_ID,
    ATTR_PRIORITY,
    ATTR_SEMANTIC_STATE,
    ATTR_SOURCE_ENTITY,
    ATTR_STATE,
    ATTR_STATE_ICON,
    DOMAIN,
    INPUT_SLOTS,
    STATE_ALARM,
)
from .coordinator import MachineMonitorCoordinator
from .sensor import _machine_slug

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Machine Monitor binary sensors."""
    coordinator: MachineMonitorCoordinator = hass.data[DOMAIN][
        "coordinator"
    ]
    runtime = coordinator.runtime_for(entry.entry_id)
    if runtime is None:
        return

    machine_id = entry.entry_id
    slug = _machine_slug(runtime.name)
    machine_name = runtime.name

    entities: list[BinarySensorEntity] = []
    for slot in INPUT_SLOTS:
        cfg = runtime.profile.input_for(slot)
        if cfg is None or not cfg.entity_id:
            continue
        entities.append(
            MachineInputBinarySensor(
                coordinator=coordinator,
                machine_id=machine_id,
                slug=slug,
                machine_name=machine_name,
                slot=slot,
                entity_id=cfg.entity_id,
            )
        )
    async_add_entities(entities)


class MachineInputBinarySensor(
    CoordinatorEntity[MachineMonitorCoordinator], BinarySensorEntity
):
    """Expose one physical machine input."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MachineMonitorCoordinator,
        machine_id: str,
        slug: str,
        machine_name: str,
        slot: str,
        entity_id: str,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator)
        self._machine_id = machine_id
        self._slot = slot
        self._entity_id = entity_id
        self._attr_unique_id = f"{machine_id}_{slot}"
        self._attr_translation_key = slot
        self._attr_device_info = {
            "identifiers": {(DOMAIN, machine_id)},
            "name": machine_name,
            "manufacturer": "Machine Monitor",
            "model": "4-channel MQTT monitor",
        }
        cfg = coordinator.runtime_for(machine_id)
        if cfg is not None:
            profile_cfg = cfg.profile.input_for(slot)
            if profile_cfg is not None:
                self._attr_name = profile_cfg.display_name
                self._attr_icon = profile_cfg.effective_icon
                if profile_cfg.semantic_state == STATE_ALARM:
                    self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def _runtime(self):
        """Return the runtime."""
        return self.coordinator.runtime_for(self._machine_id)

    @property
    def _cfg(self):
        """Return the input configuration."""
        runtime = self._runtime
        if runtime is None:
            return None
        return runtime.profile.input_for(self._slot)

    @property
    def name(self) -> str | None:
        """Use the current profile even before an options-triggered reload."""
        return self._cfg.display_name if self._cfg else None

    @property
    def icon(self) -> str | None:
        return self._cfg.effective_icon if self._cfg else None

    @property
    def device_class(self):
        return BinarySensorDeviceClass.PROBLEM if self._cfg and self._cfg.semantic_state == STATE_ALARM else None

    @property
    def is_on(self) -> bool | None:
        """Return the raw physical state."""
        runtime = self._runtime
        if runtime is None:
            return None
        return runtime.engine.async_snapshot().active_inputs.get(self._slot)

    @property
    def available(self) -> bool:
        """Return False when the source entity is not reachable."""
        runtime = self._runtime
        if runtime is None:
            return False
        cfg = self._cfg
        if cfg is None:
            return False
        return runtime.snapshot().active_inputs.get(self._slot) is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the semantic meaning of the physical signal."""
        cfg = self._cfg
        runtime = self._runtime
        attributes: dict[str, Any] = {
            ATTR_MACHINE_ID: self._machine_id,
            ATTR_INPUT_KEY: self._slot,
            ATTR_SOURCE_ENTITY: cfg.entity_id if cfg else self._entity_id,
        }
        if cfg is not None:
            attributes[ATTR_SEMANTIC_STATE] = cfg.semantic_state
            attributes["semantic_label"] = cfg.semantic_state.replace(
                "_", " "
            ).title()
            attributes[ATTR_PRIORITY] = cfg.effective_priority
            attributes["color"] = cfg.effective_color
            attributes["description"] = cfg.input_description
            attributes["enabled"] = cfg.enabled
            attributes["show_in_timeline"] = cfg.show_in_timeline
            attributes["include_in_statistics"] = cfg.include_in_statistics
        if runtime is not None:
            diagnostics = next((row for row in runtime.engine.source_diagnostics()
                                if row["slot"] == self._slot), {})
            attributes.update({"source_ha_state": diagnostics.get("ha_state"),
                               "source_available": diagnostics.get("available"),
                               "source_last_changed": diagnostics.get("last_changed"),
                               "source_error": diagnostics.get("source_error")})
            snapshot = runtime.snapshot()
            attributes[ATTR_STATE] = snapshot.state
            attributes["is_current_state_source"] = (
                snapshot.source_input == self._slot
            )
        return attributes
