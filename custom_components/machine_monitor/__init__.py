"""Machine Monitor integration.

Machine Monitor turns the physical signals of an ESP32 node into a real
industrial monitoring system:

    physical inputs -> machine profile -> event engine
                    -> statistics -> timeline -> dashboard

The ESP32 firmware, the MQTT broker and the Home Assistant MQTT integration are
untouched. This integration only consumes entities that already exist.

Importing this package MUST never fail, otherwise Home Assistant refuses to
register the config flow handler and the frontend reports ``Invalid handler
specified``. Therefore every Home Assistant component that is not strictly
required to import the package is imported lazily inside the setup functions.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    MANUFACTURER,
    MODEL,
    SERVICE_CLEAR_HISTORY,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor"]

# NOTE: there is deliberately no CONFIG_SCHEMA here.
#
# The integration is configured exclusively through the UI. Exposing a
# ``config_entry_only_config_schema`` would execute a Home Assistant helper at
# import time that does not exist on every supported release. If the import of
# this package fails the config flow handler is never registered and the user
# only sees a generic ``Invalid handler specified`` error.


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Machine Monitor integration (YAML is not supported)."""
    hass.data.setdefault(DOMAIN, {})

    # The dashboard card is served straight from the integration folder so the
    # user does not have to copy anything into the www folder. A failure here
    # is not fatal, the entities keep working without the card.
    await _async_register_card(hass)

    # Same for the websocket API: the dashboard needs it, the entities do not.
    await _async_setup_websocket_api(hass)

    _async_register_services(hass)
    _async_register_shutdown_listener(hass)

    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve and register the bundled module and Machine Monitor dashboard."""
    try:
        from .frontend_setup import async_setup_frontend

        await async_setup_frontend(hass)
    except Exception:  # UI failures must not stop the observational backend.
        _LOGGER.exception("Machine Monitor: could not register the bundled UI")


async def _async_setup_websocket_api(hass: HomeAssistant) -> None:
    """Register the websocket API used by the dashboard card."""
    try:
        from .websocket_api import async_setup as ws_async_setup

        await ws_async_setup(hass)
    except Exception:  # noqa: BLE001 - never break the setup for the card
        _LOGGER.exception(
            "Machine Monitor: websocket API unavailable, the dashboard card "
            "will not be able to load data"
        )


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the integration services."""

    async def _handle_clear_history(call: ServiceCall) -> None:
        """Handle the clear_history service."""
        coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
        if coordinator is None:
            _LOGGER.warning(
                "Machine Monitor: clear_history called without any machine"
            )
            return

        entry_id = call.data.get("entry_id")
        for machine_id, runtime in list(coordinator.machines.items()):
            if entry_id and machine_id != entry_id:
                continue
            await runtime.engine.async_clear_history()
            _LOGGER.info(
                "Machine Monitor: history cleared for %s", runtime.name
            )
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_HISTORY, _handle_clear_history
    )


def _async_register_shutdown_listener(hass: HomeAssistant) -> None:
    """Persist the timeline when Home Assistant shuts down."""

    async def _async_stop(event: Any) -> None:
        try:
            coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
            if coordinator is None:
                return
            for runtime in list(coordinator.machines.values()):
                try:
                    await runtime.async_stop()
                except Exception:  # noqa: BLE001 - shutdown must not fail
                    _LOGGER.exception(
                        "Machine Monitor: could not flush history for %s",
                        runtime.machine_id,
                    )
        except Exception:  # noqa: BLE001 - shutdown must not fail
            _LOGGER.exception("Machine Monitor: error during shutdown flush")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one machine from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # The coordinator imports the event engine and the storage layer, so it is
    # loaded here instead of at package import time.
    from .coordinator import MachineMonitorCoordinator

    coordinator: MachineMonitorCoordinator | None = hass.data[DOMAIN].get(
        "coordinator"
    )
    if coordinator is None:
        coordinator = MachineMonitorCoordinator(hass)
        await coordinator.async_refresh()
        await coordinator.async_register_shutdown()
        hass.data[DOMAIN]["coordinator"] = coordinator

    # Build or load the machine profile before the device is registered so the
    # name matches the profile.
    profile = await coordinator.async_profile_for(entry)

    # Stable device registration. The identifier is derived from the config
    # entry id, therefore restarting Home Assistant never creates duplicates.
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer=MANUFACTURER,
        model=MODEL,
    )

    runtime = await coordinator.async_add_machine(entry)
    hass.data[DOMAIN].setdefault("entries", {})[entry.entry_id] = runtime

    coordinator.async_listen_input_names(entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await coordinator.async_request_refresh()

    _LOGGER.info(
        "Machine Monitor: %s ready with inputs %s",
        profile.name,
        list(profile.inputs),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if not unloaded:
        return False

    coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
    if coordinator is not None:
        await coordinator.async_remove_machine(entry.entry_id)
    hass.data.get(DOMAIN, {}).get("entries", {}).pop(entry.entry_id, None)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a machine when its configuration changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow deleting the device together with the config entry."""
    return True
