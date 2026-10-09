"""Data update coordinator for Machine Monitor."""

from __future__ import annotations

import logging
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.storage import Store
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ENABLED,
    CONF_INPUTS,
    DEFAULT_INPUT_NAME,
    INPUT_SLOTS,
    CONF_MACHINE_ID,
    CONF_NAME,
    CONF_NO_ACTIVE_STATE,
    CONF_DESCRIPTION,
    DOMAIN,
    DOWNTIME_THRESHOLD_KEY,
    CONF_HISTORY_LIMIT,
    CONF_DOWNTIME_THRESHOLD,
    SCAN_INTERVAL_SECONDS,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)
from .machine import (
    MachineRuntime,
    build_profile_from_entry_data,
    create_runtime,
)
from .models import MachineProfile
from .stats import period_bounds
from .source_validation import is_own_source

_LOGGER = logging.getLogger(__name__)

PROFILE_KEY = f"{STORAGE_KEY_PREFIX}.profiles"


class MachineMonitorCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Aggregates every configured machine."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
            config_entry=None,
            request_refresh_debouncer=Debouncer(hass, _LOGGER, cooldown=0.25, immediate=False),
        )
        self.machines: dict[str, MachineRuntime] = {}
        self._profile_lock = asyncio.Lock()
        self._profile_store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, PROFILE_KEY, atomic_writes=True, serialize_in_event_loop=False
        )

    # ------------------------------------------------------------------
    # Profiles
    # ------------------------------------------------------------------
    async def async_load_profiles(self) -> dict[str, dict[str, Any]]:
        """Load all stored machine profiles."""
        data: dict[str, Any] | None = None
        try:
            data = await self._profile_store.async_load()
        except Exception:  # noqa: BLE001 - never break startup
            _LOGGER.exception("Machine Monitor: could not load profiles")
            raise
        return (data or {}).get("profiles", {})

    async def async_save_profiles(self, profiles: dict[str, dict]) -> None:
        """Persist all machine profiles."""
        try:
            await self._profile_store.async_save({"profiles": profiles})
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Machine Monitor: could not save profiles")
            raise

    async def async_profile_for(
        self, entry: ConfigEntry
    ) -> MachineProfile:
        """Return the profile of a config entry, creating it if needed."""
        async with self._profile_lock:
            machine_id = entry.entry_id
            stored = await self.async_load_profiles()
            raw = stored.get(machine_id)
            profile = MachineProfile.from_dict(raw) if raw else None
            if profile is None or profile.machine_id != machine_id:
                profile = build_profile_from_entry_data(machine_id, entry.title, dict(entry.data))
            migrated = not (raw or {}).get("input_names_profile_owned")
            if migrated:
                # Older versions let HA rename diagnostic entities independently.
                # Import explicit user overrides once, preserving real profile names.
                for slot, entity in self._input_entities(machine_id).items():
                    cfg = profile.input_for(slot)
                    if cfg and cfg.display_name == DEFAULT_INPUT_NAME:
                        if entity.name is not None:
                            cfg.input_name = entity.name
                await self._async_store_profile(stored, profile)
            if migrated or machine_id not in self.machines:
                self._mirror_input_names(profile)
            return profile

    def _input_entities(self, machine_id: str) -> dict[str, Any]:
        """Match our diagnostic entities by stable unique ID, never friendly name."""
        result = {}
        for entity in er.async_get(self.hass).entities.values():
            if entity.platform != DOMAIN or getattr(entity, "config_entry_id", None) != machine_id:
                continue
            for slot in INPUT_SLOTS:
                if getattr(entity, "unique_id", None) == f"{machine_id}_{slot}":
                    result[slot] = entity
        return result

    async def _async_store_profile(self, stored, profile) -> None:
        raw = profile.to_dict()
        raw["input_names_profile_owned"] = True
        stored[profile.machine_id] = raw
        await self.async_save_profiles(stored)

    def _mirror_input_names(self, profile, *, pending_names=None) -> None:
        """HA names are a projection of the persisted canonical Machine Profile."""
        registry = er.async_get(self.hass)
        for slot, entity in self._input_entities(profile.machine_id).items():
            cfg = profile.input_for(slot)
            if cfg is None:
                continue
            # Do not overwrite another user rename arriving during a storage await.
            if pending_names is not None and (slot not in pending_names or entity.name != pending_names[slot]):
                continue
            if entity.name != cfg.display_name:
                registry.async_update_entity(entity.entity_id, name=cfg.display_name)

    def async_listen_input_names(self, entry) -> None:
        """Treat renaming our HA input entities as an edit of the machine profile."""
        @callback
        def changed(event):
            if event.data.get("action") != "update" or "name" not in event.data.get("changes", {}):
                return
            entity = er.async_get(self.hass).async_get(event.data["entity_id"])
            if entity is None or entity.platform != DOMAIN or entity.config_entry_id != entry.entry_id:
                return
            runtime = self.runtime_for(entry.entry_id)
            if runtime is None:
                return
            for slot, candidate in self._input_entities(entry.entry_id).items():
                cfg = runtime.profile.input_for(slot)
                if candidate.entity_id == entity.entity_id and cfg and (
                    entity.name or DEFAULT_INPUT_NAME
                ) != cfg.display_name:
                    self.hass.async_create_task(self._async_update_input_name(entry.entry_id, slot))
                    break
        entry.async_on_unload(self.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, changed))

    async def _async_update_input_name(self, machine_id, slot) -> None:
        async with self._profile_lock:
            runtime = self.runtime_for(machine_id)
            if runtime is None:
                return
            entities = self._input_entities(machine_id)
            entity = entities.get(slot)
            if entity is None or runtime.profile.input_for(slot) is None:
                return
            profile = deepcopy(runtime.profile)
            profile.inputs[slot].input_name = entity.name or DEFAULT_INPUT_NAME
            stored = await self.async_load_profiles()
            observed_names = {slot: entity.name}
            await self._async_store_profile(stored, profile)
            await runtime.async_apply_profile(profile)
            self._mirror_input_names(profile, pending_names=observed_names)
            await self.async_request_refresh()

    async def async_update_profile(
        self, machine_id: str, profile: MachineProfile
    ) -> None:
        """Persist a changed profile and apply it to the runtime."""
        if any(is_own_source(self.hass, cfg.entity_id) for cfg in profile.inputs.values()):
            raise ValueError("Machine Monitor diagnostic entities cannot be source inputs")
        async with self._profile_lock:
            stored = await self.async_load_profiles()
            await self._async_store_profile(stored, profile)
            runtime = self.machines.get(machine_id)
            if runtime is not None:
                await runtime.async_apply_profile(profile)
                await self.async_request_refresh()
            self._mirror_input_names(profile)

    # ------------------------------------------------------------------
    # Machine management
    # ------------------------------------------------------------------
    async def async_add_machine(self, entry: ConfigEntry) -> MachineRuntime:
        """Create and start the runtime for a config entry."""
        profile = await self.async_profile_for(entry)
        runtime = create_runtime(self.hass, entry.entry_id, profile)
        runtime.engine.set_update_callback(self._schedule_refresh)
        await runtime.async_start()
        self.machines[entry.entry_id] = runtime
        await self.async_request_refresh()
        _LOGGER.info(
            "Machine Monitor: machine %s added with %s inputs",
            profile.name,
            len(profile.inputs),
        )
        return runtime

    async def async_remove_machine(self, entry_id: str) -> None:
        """Stop and forget a machine."""
        runtime = self.machines.pop(entry_id, None)
        if runtime is not None:
            await runtime.async_stop()
            await self.async_request_refresh()

    def async_reload_machine(self, entry: ConfigEntry) -> None:
        """Mark a machine for restart after its configuration changed."""
        self.hass.async_create_task(
            self.async_reload_machine_task(entry), "machine_monitor_reload"
        )

    async def async_reload_machine_task(self, entry: ConfigEntry) -> None:
        """Restart a single machine runtime."""
        await self.async_remove_machine(entry.entry_id)
        await self.async_add_machine(entry)

    @callback
    def _schedule_refresh(self) -> None:
        """Bridge a synchronous input callback to the HA coroutine."""
        self.hass.async_create_task(self.async_request_refresh())

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        """Persist pending history and build the machine summary."""
        for runtime in list(self.machines.values()):
            try:
                await runtime.async_flush(force=False)
            except Exception:  # noqa: BLE001
                _LOGGER.exception(
                    "Machine Monitor: flush failed for %s",
                    runtime.machine_id,
                )
        return await self.async_machine_summaries()

    async def async_machine_summaries(self) -> dict[str, Any]:
        now = datetime.now().astimezone()
        start, end = period_bounds(now, "today")
        snapshots = {key: runtime.query_snapshot(start, end) for key, runtime in self.machines.items()}
        return await self.hass.async_add_executor_job(self.machine_summaries, snapshots, now)

    def machine_summaries(self, machines=None, now=None) -> dict[str, Any]:
        """Return a compact summary of every machine for the overview."""
        now = now or datetime.now().astimezone()
        summary: dict[str, Any] = {}
        for machine_id, runtime in (self.machines if machines is None else machines).items():
            snapshot = runtime.snapshot()
            stats = runtime.stats("today", now=now)
            summary[machine_id] = {
                "machine_id": machine_id,
                "name": runtime.name,
                "description": runtime.profile.description,
                "state": snapshot.state,
                "state_label": snapshot.state_label,
                "state_icon": snapshot.to_dict()["state_icon"],
                "state_color": snapshot.to_dict()["state_color"],
                "state_since": snapshot.state_since.isoformat(),
                "state_duration": round(
                    runtime.engine.current_state_duration(now), 1
                ),
                "work_seconds": round(stats.work_seconds, 1),
                "idle_seconds": round(stats.idle_seconds, 1),
                "work_percent": stats.work_percent,
                "idle_percent": stats.idle_percent,
                "downtime_count": stats.downtime.count,
                "offline": runtime.engine.is_offline,
                "offline_reason": runtime.engine.offline_reason(),
                "last_seen": (
                    snapshot.last_seen.isoformat()
                    if snapshot.last_seen
                    else None
                ),
                "active_inputs": snapshot.active_inputs,
                "inputs": {
                    entry["slot"]: {
                        "on": entry["on"],
                        "on_seconds": entry["on_seconds"],
                        "activations": entry["activations"],
                    }
                    for entry in runtime.input_summary("today", now=now)
                },
            }
        return summary

    def runtime_for(self, machine_id: str) -> MachineRuntime | None:
        """Return the runtime of a machine."""
        return self.machines.get(machine_id)

    # ------------------------------------------------------------------
    # Domain data access
    # ------------------------------------------------------------------
    @property
    def domain_data(self) -> dict[str, Any]:
        """Return hass.data payload."""
        return self.hass.data.setdefault(DOMAIN, {})

    @staticmethod
    def coordinator_for(hass: HomeAssistant) -> MachineMonitorCoordinator:
        """Return the shared coordinator instance."""
        return hass.data[DOMAIN]["coordinator"]

