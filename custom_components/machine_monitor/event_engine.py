"""Event engine for Machine Monitor.

The engine keeps two strictly separated data layers:

* **physical input history** - an independent ON/OFF timeline for every
  physical input. Nothing is lost to the priority resolution.
* **semantic machine state** - the highest priority active input decides the
  machine state used by current status, statistics and downtime analysis.

An unavailable source entity never counts as idle: when any enabled source entity of
a machine is unreachable the machine goes ``offline`` and offline time is not
accounted as work or idle.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Callable

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    EXCLUDED_STATES,
    INPUT_ON,
    STATE_OFFLINE,
    VISIBLE_IN_TIMELINE,
)
from .models import (
    ActiveInput,
    Interval,
    MachineProfile,
    MachineSnapshot,
)
from .storage import HistoryStore
from .source_validation import is_own_source

_LOGGER = logging.getLogger(__name__)

EVENT_MACHINE_STATE_CHANGED = "machine_monitor_state_changed"


def _is_truthy(state: str | None) -> bool:
    """Return True when a Home Assistant state string means active."""
    return state == "on"


class EventEngine:
    """Track one machine and maintain both of its timelines."""

    def __init__(
        self,
        hass: HomeAssistant,
        machine_id: str,
        profile: MachineProfile,
        history: HistoryStore,
    ) -> None:
        """Initialise the engine."""
        self.hass = hass
        self.machine_id = machine_id
        self.profile = profile
        self.history = history

        self._state: str = STATE_OFFLINE
        self._state_since: datetime = datetime.now().astimezone()
        self._source_input: str | None = None
        self._source_entity: str | None = None
        self._priority: int = -1
        self._last_seen: datetime | None = None
        self._offline_since: datetime | None = None
        self._recovered_at: datetime | None = None
        self._inputs: dict[str, ActiveInput] = {}
        self._unsub = None
        self._dirty: bool = False
        self._running = False
        self._on_update: Callable[[], None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def async_start(self, *, load_history: bool = True) -> None:
        """Load both timelines from storage and start listening."""
        if load_history:
            await self.history.async_load()
        self._last_seen = self.history.last_seen
        self.history.set_retention(self.profile.retention_days)

        now = datetime.now().astimezone()
        self.history.async_repair_open_interval(now)
        self.history.async_repair_open_input_intervals(now)
        self.history.async_record_observation_gap(now)
        self._read_entity_states()
        self._evaluate(initial=True, now=now)
        if any(a.is_available and a.config.enabled for a in self._inputs.values()):
            self._last_seen = now

        # Only confirmed states open fresh intervals after an unknown gap.
        for slot, active in self._inputs.items():
            if self.profile.enabled and active.config.enabled and active.is_on and active.is_available:
                self.history.async_open_input_interval(slot, now)
                _LOGGER.debug("Machine %s input %s source %s physical interval opened at startup %s",
                              self.machine_id, slot, active.entity_id, now.isoformat())
        self._running = True
        self.history.mark_observed(now)
        self.history.last_seen = self._last_seen

        entity_ids = self.profile.entity_ids()
        if entity_ids:
            self._unsub = async_track_state_change_event(
                self.hass, entity_ids, self._async_on_state_change
            )
            _LOGGER.info(
                "Machine Monitor: machine %s (%s) listening to %s",
                self.profile.name,
                self.machine_id,
                entity_ids,
            )
        await self.history.async_prune_due(now, force=True)
        await self.history.async_flush_if_dirty()
        self.hass.bus.async_fire(EVENT_MACHINE_STATE_CHANGED, {
            "machine_id": self.machine_id, "type": "startup", "machine_state": self._state,
        })
        self._notify()

    async def async_stop(self) -> None:
        """Stop listening and flush both timelines."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        if self._running:
            now = datetime.now().astimezone()
            self.history.async_close_interval(now)
            for slot in self._inputs:
                self.history.async_close_input_interval(slot, now)
            self.history.mark_observed(now)
            self.history.last_seen = self._last_seen
            self._running = False
        await self.history.async_flush_if_dirty()
        self._on_update = None

    @callback
    def update_input_names(self, profile: MachineProfile) -> None:
        """Apply profile labels without interrupting current observations."""
        self.profile = profile
        for slot, active in self._inputs.items():
            active.config = profile.inputs[slot]
        self.hass.bus.async_fire(EVENT_MACHINE_STATE_CHANGED, {
            "machine_id": self.machine_id, "type": "profile",
        })
        self._notify()

    async def async_apply_profile(self, profile: MachineProfile) -> None:
        """Close the old mapping before subscribing to the new one."""
        update = self._on_update
        await self.async_stop()
        self.profile = profile
        self._on_update = update
        await self.async_start(load_history=False)
        self.hass.bus.async_fire(EVENT_MACHINE_STATE_CHANGED, {"machine_id": self.machine_id, "type": "profile"})
        self._notify()

    async def async_clear_history(self) -> None:
        """Clear both layers and immediately resume current observations."""
        self.history.async_clear()
        now = datetime.now().astimezone()
        self._evaluate(initial=True, now=now)
        for slot, active in self._inputs.items():
            if self.profile.enabled and active.config.enabled and active.is_available and active.is_on:
                self.history.async_open_input_interval(slot, now)
        self.history.mark_observed(now)
        self.history.last_seen = self._last_seen
        await self.history.async_flush_if_dirty()
        self.hass.bus.async_fire(EVENT_MACHINE_STATE_CHANGED, {"machine_id": self.machine_id, "type": "clear"})
        self._notify()

    # ------------------------------------------------------------------
    # Reading physical states
    # ------------------------------------------------------------------
    def _read_entity_states(self) -> None:
        """Read the current state of every configured entity."""
        self._inputs = {}
        for slot, cfg in self.profile.inputs.items():
            state = self.hass.states.get(cfg.entity_id)
            raw_state = state.state if state else None
            source_error = "own_entity" if is_own_source(self.hass, cfg.entity_id) else None
            available = raw_state in ("on", "off") and source_error is None
            self._inputs[slot] = ActiveInput(
                slot=slot,
                entity_id=cfg.entity_id,
                is_on=_is_truthy(raw_state) and available,
                is_available=available,
                config=cfg,
                raw_state=raw_state,
                last_changed=getattr(state, "last_changed", None),
                source_error=source_error,
            )
            _LOGGER.debug("Machine %s input %s source %s initial HA state=%s available=%s on=%s error=%s",
                          self.machine_id, slot, cfg.entity_id, raw_state, available,
                          self._inputs[slot].is_on, source_error)

    @callback
    def _async_on_state_change(self, event: Event) -> None:
        """Handle a state change of one of the source entities."""
        if not self._running:
            return
        data = event.data
        entity_id = data["entity_id"]
        state_obj = data["new_state"]
        new_state = state_obj.state if state_obj else None
        now = event.time_fired
        changed_inputs = []
        for slot, active in self._inputs.items():
            if active.entity_id != entity_id:
                continue
            source_error = "own_entity" if is_own_source(self.hass, entity_id) else None
            available = new_state in ("on", "off") and source_error is None
            was_available, was_on = active.is_available, active.is_on
            old_raw, old_error = active.raw_state, active.source_error
            active.raw_state = new_state
            active.source_error = source_error
            active.last_changed = getattr(state_obj, "last_changed", None) or (
                now if old_raw != new_state else active.last_changed
            )
            active.is_on = _is_truthy(new_state) and available
            active.is_available = available
            if (available or was_available) and active.config.enabled:
                self._last_seen = now
            if (was_on, was_available, old_raw, old_error) == (active.is_on, available, new_state, source_error):
                continue
            _LOGGER.debug("Machine %s input %s source %s HA state=%s available=%s on=%s previous=(%s,%s,%s) error=%s",
                          self.machine_id, slot, entity_id, new_state, available, active.is_on,
                          old_raw, was_available, was_on, source_error)
            changed_inputs.append({"input": slot, "on": active.is_on if available else None, "available": available})
            if self.profile.enabled and active.config.enabled:
                if not available or not active.is_on:
                    closed = self.history.async_close_input_interval(slot, now)
                    if closed:
                        _LOGGER.debug("Machine %s input %s source %s physical interval closed at %s",
                                      self.machine_id, slot, entity_id, now.isoformat())
                elif not was_available or not was_on:
                    self.history.async_open_input_interval(slot, now)
                    _LOGGER.debug("Machine %s input %s source %s physical interval opened at %s",
                                  self.machine_id, slot, entity_id, now.isoformat())
        if not changed_inputs:
            return
        # Do not reread hass.states: later queued events may already be there.
        self._evaluate(now=now)
        self.history.mark_observed(now)
        self.history.last_seen = self._last_seen
        self._dirty = True
        self.hass.bus.async_fire(EVENT_MACHINE_STATE_CHANGED, {
            "machine_id": self.machine_id, "machine_name": self.profile.name,
            "type": "input", "entity_id": entity_id, "machine_state": self._state,
            **changed_inputs[0], "inputs": changed_inputs,
        })
        self._notify()

    # ------------------------------------------------------------------
    # Semantic state resolution
    # ------------------------------------------------------------------
    def _evaluate(self, initial: bool = False, now: datetime | None = None) -> None:
        """Resolve the semantic machine state and update its timeline."""
        now = now or datetime.now().astimezone()
        considered = [
            item for item in self._inputs.values() if item.config.enabled
        ]

        if not self.profile.enabled or not considered or not all(
            item.is_available for item in considered
        ):
            new_state = STATE_OFFLINE
            source_input = None
            source_entity = None
            priority = -1
        else:
            available_active = [
                item
                for item in considered
                if item.is_available and item.is_on
            ]
            if available_active:
                winner = max(
                    available_active,
                    key=lambda item: (
                        item.config.effective_priority,
                        item.slot,
                    ),
                )
                new_state = winner.semantic_state
                source_input = winner.slot
                source_entity = winner.entity_id
                priority = winner.config.effective_priority
            else:
                new_state = self.profile.no_active_state
                source_input = None
                source_entity = None
                priority = -1

        if not initial and (new_state, source_input, source_entity, priority) == (
            self._state, self._source_input, self._source_entity, self._priority
        ):
            return
        _LOGGER.debug("Machine %s semantic %s -> %s initial=%s offline_reason=%s",
                      self.machine_id, self._state, new_state, initial, self.offline_reason())
        state_changed = new_state != self._state

        if initial:
            self._state = new_state
            self._state_since = now
            self._source_input = source_input
            self._source_entity = source_entity
            self._priority = priority
            self._offline_since = now if new_state == STATE_OFFLINE else None
            # OFFLINE is a real historical period: store it so the Real Flow
            # can show the connection loss. It stays excluded from the
            # productivity statistics (EXCLUDED_STATES is only consulted by
            # the statistics layer, never here).
            if new_state in VISIBLE_IN_TIMELINE:
                self.history.async_open_interval(
                    start=now,
                    state=new_state,
                    source_input=source_input,
                    source_entity=source_entity,
                )
                self._dirty = True
            return

        previous = self._state
        self.history.async_close_interval(now)

        if new_state in VISIBLE_IN_TIMELINE:
            self.history.async_open_interval(
                start=now,
                state=new_state,
                source_input=source_input,
                source_entity=source_entity,
            )

        self._state = new_state
        if state_changed:
            self._state_since = now
        self._source_input = source_input
        self._source_entity = source_entity
        self._priority = priority
        self._dirty = True

        if new_state == STATE_OFFLINE and previous != STATE_OFFLINE:
            self._offline_since = now
        elif previous == STATE_OFFLINE and new_state != STATE_OFFLINE:
            self._recovered_at = now
            self._offline_since = None

        _LOGGER.info(
            "Machine Monitor: %s state %s -> %s",
            self.profile.name,
            previous,
            new_state,
        )
        # Caller sends one update after all physical slots are processed.

    def _notify(self) -> None:
        """Notify the coordinator that data changed."""
        if self._on_update is not None:
            self._on_update()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_update_callback(self, callback_fn: Callable[[], None]) -> None:
        """Register a callback invoked on every change."""
        self._on_update = callback_fn

    @property
    def state(self) -> str:
        """Current semantic state."""
        return self._state

    @property
    def state_since(self) -> datetime:
        """When the current semantic state started."""
        return self._state_since

    @property
    def is_offline(self) -> bool:
        """True when configured source information cannot determine machine state."""
        return self._state == STATE_OFFLINE

    @property
    def last_seen(self) -> datetime | None:
        """Last time any entity of this machine was reachable."""
        return self._last_seen

    @property
    def offline_since(self) -> datetime | None:
        """When the machine went offline, if it is offline."""
        return self._offline_since

    @property
    def recovered_at(self) -> datetime | None:
        """When the machine recovered from the last offline period."""
        return self._recovered_at

    def current_state_duration(self, now: datetime | None = None) -> float:
        """Seconds spent in the current semantic state."""
        end = now or datetime.now().astimezone()
        return max(0.0, (end - self._state_since).total_seconds())

    def source_diagnostics(self) -> list[dict[str, Any]]:
        """Event-consistent raw sources; absence and unknown never mean OFF."""
        return [{
            "slot": slot, "entity_id": a.entity_id, "name": a.config.display_name,
            "semantic_state": a.semantic_state, "enabled": a.config.enabled,
            "show_in_timeline": a.config.show_in_timeline,
            "ha_state": a.raw_state, "available": a.is_available,
            "physical_on": a.is_on if a.is_available else None,
            "last_changed": a.last_changed.isoformat() if a.last_changed else None,
            "source_error": a.source_error,
        } for slot, a in self._inputs.items()]

    def offline_reason(self) -> dict[str, Any]:
        """Explain availability using the same inputs as semantic resolution."""
        unavailable = [row for row in self.source_diagnostics()
                       if row["enabled"] and not row["available"]]
        if not self.profile.enabled:
            code = "monitoring_disabled"
        elif not any(a.config.enabled for a in self._inputs.values()):
            code = "no_enabled_inputs"
        elif unavailable:
            code = "unavailable_sources"
        else:
            code = None
        return {"code": code, "sources": unavailable}

    def async_snapshot(self) -> MachineSnapshot:
        """Return a point in time snapshot of the machine."""
        return MachineSnapshot(
            machine_id=self.machine_id,
            name=self.profile.name,
            state=self._state,
            state_since=self._state_since,
            source_input=self._source_input,
            source_entity=self._source_entity,
            priority=self._priority,
            active_inputs={
                slot: item.is_on if item.is_available else None
                for slot, item in self._inputs.items()
            },
            inputs_available=self.profile.enabled and any(
                item.config.enabled for item in self._inputs.values()
            ) and all(item.is_available for item in self._inputs.values() if item.config.enabled),
            last_seen=self._last_seen,
            offline_since=self._offline_since,
            recovered_at=self._recovered_at,
        )

    # -- physical input layer ------------------------------------------
    def async_input_intervals(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        slot: str | None = None,
    ) -> dict[str, list[Interval]]:
        """Return the physical input intervals, optionally limited."""
        slots = [slot] if slot else self.history.input_slots()
        return {key: self.history.query(self.history.input_intervals(key), start, end) for key in slots}

    # -- semantic timeline ---------------------------------------------
    def async_intervals(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Interval]:
        """Return the semantic timeline, optionally limited to a range."""
        return self.history.query(self.history.intervals, start, end)

    def async_timeline(
        self,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Return semantic timeline slices clipped to a window."""
        now = datetime.now().astimezone()
        window = max(1.0, (end - start).total_seconds())
        slices: list[dict[str, Any]] = []
        for item in self.history.query(self.history.intervals, start, end):
            cfg = self.profile.input_for(item.source_input or "")
            if cfg is not None and not (
                cfg.enabled and cfg.show_in_timeline
            ):
                continue
            raw_end = item.end or now
            if raw_end <= start or item.start >= end:
                continue
            clipped_start = max(item.start, start)
            clipped_end = min(raw_end, end)
            offset = (clipped_start - start).total_seconds()
            length = max(
                0.0, (clipped_end - clipped_start).total_seconds()
            )
            if length <= 0:
                continue
            slices.append(
                {
                    "state": item.state,
                    "input": item.source_input,
                    "input_name": cfg.display_name if cfg else None,
                    "entity": item.source_entity,
                    "icon": cfg.effective_icon if cfg else None,
                    "color": cfg.effective_color if cfg else None,
                    "start": clipped_start.isoformat(),
                    "end": clipped_end.isoformat(),
                    "duration": length,
                    "offset": offset,
                    "ratio": min(1.0, length / window),
                }
            )
        return slices

    async def async_flush(self, *, force=True) -> None:
        """Persist pending timeline changes."""
        if self._running:
            now = datetime.now().astimezone()
            if self._state != STATE_OFFLINE:
                self._last_seen = now
            self.history.mark_observed(now)
            self.history.last_seen = self._last_seen
        await self.history.async_prune_due(datetime.now().astimezone())
        await self.history.async_flush_if_dirty(force=force)

    async def async_prune_history(self, days: int) -> int:
        """Drop history older than ``days`` days."""
        cutoff = datetime.now().astimezone() - timedelta(days=days)
        removed = self.history.async_prune(cutoff)
        if removed:
            await self.history.async_flush()
        return removed
