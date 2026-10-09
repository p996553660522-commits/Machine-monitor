"""Runtime object for a single monitored machine."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from copy import copy, deepcopy
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_INPUTS,
    CONF_MACHINE_ID,
    CONF_NAME,
    CONF_NO_ACTIVE_STATE,
    DOWNTIME_THRESHOLD_KEY,
    CONF_HISTORY_LIMIT,
    CONF_ENABLED,
    CONF_DESCRIPTION,
    INPUT_SLOTS,
)
from .event_engine import EventEngine
from .models import InputConfig, Interval, MachineProfile, MachineSnapshot, normalize_row_order
from .stats import (
    input_statistics,
    PeriodStats,
    analyse_downtime,
    compute_period_stats,
    period_bounds,
    previous_bounds,
)
from .storage import HistoryStore

_LOGGER = logging.getLogger(__name__)


def build_profile_from_entry_data(
    machine_id: str,
    title: str,
    data: dict[str, Any],
) -> MachineProfile:
    """Build a profile from the flat config entry data.

    The flat data only binds physical slots to entities. All semantic
    information is stored separately in the machine profile and can be edited
    later through the options flow.
    """
    inputs: dict[str, InputConfig] = {}
    for slot in INPUT_SLOTS:
        entity_id = data.get(slot)
        if not entity_id:
            continue
        inputs[slot] = InputConfig(entity_id=entity_id)

    profile = MachineProfile(machine_id=machine_id, name=title, inputs=inputs)
    profile.inputs = inputs
    return profile


@dataclass(slots=True)
class MachineRuntime:
    """Everything Home Assistant knows about one machine."""

    machine_id: str
    profile: MachineProfile
    history: HistoryStore
    engine: EventEngine

    async def async_apply_profile(self, profile: MachineProfile) -> None:
        """Replace the profile and restart the engine if needed."""
        old_data, new_data = self.profile.to_dict(), profile.to_dict()
        for data in (old_data, new_data):
            for key in ("retention_days", "shifts", "row_order", "name", "description"):
                data.pop(key, None)
            for cfg in data[CONF_INPUTS].values():
                for key in ("input_name", "input_description", "color", "icon", "show_in_timeline", "include_in_statistics"):
                    cfg.pop(key, None)
        if old_data == new_data and self.profile.to_dict() != profile.to_dict():
            # Display, reporting and retention edits must not split observations.
            retention_changed = self.profile.retention_days != profile.retention_days
            self.profile = profile
            self.history.set_retention(profile.retention_days)
            if retention_changed:
                await self.history.async_prune_due(datetime.now().astimezone(), force=True)
                await self.history.async_flush_if_dirty()
            self.engine.update_input_names(profile)
            return
        old_entities = set(self.profile.entity_ids())
        self.profile = profile
        await self.engine.async_apply_profile(profile)
        self.history.set_retention(profile.retention_days)
        new_entities = set(profile.entity_ids())
        if old_entities != new_entities:
            _LOGGER.info(
                "Machine Monitor: source entities changed for %s, restarting",
                profile.name,
            )

    async def async_start(self) -> None:
        """Start the machine runtime."""
        await self.engine.async_start()

    async def async_stop(self) -> None:
        """Stop the machine runtime."""
        await self.engine.async_stop()

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        """Machine name."""
        return self.profile.name

    @property
    def state(self) -> str:
        """Current semantic state."""
        return self.engine.state

    def snapshot(self) -> MachineSnapshot:
        """Point in time snapshot."""
        return self.engine.async_snapshot()

    def intervals(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Interval]:
        """Timeline for an optional range."""
        return self.engine.async_intervals(start, end)

    def timeline(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """Timeline slices for the dashboard."""
        return self.engine.async_timeline(start, end)

    def stats(
        self,
        period: str = "today",
        *,
        now: datetime | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> PeriodStats:
        """Statistics for a named period or an explicit range."""
        reference = now or datetime.now().astimezone()
        if start is None or end is None:
            start, end = period_bounds(reference, period)
        return compute_period_stats(
            self.intervals(start, end),
            start,
            end,
            downtime_threshold_minutes=self.profile.downtime_threshold,
            include_inputs={slot: cfg.include_in_statistics for slot, cfg in self.profile.inputs.items()},
        )

    def stats_with_comparison(
        self,
        period: str = "today",
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Statistics plus comparison with the previous period."""
        reference = now or datetime.now().astimezone()
        start, end = period_bounds(reference, period)
        current = compute_period_stats(
            self.intervals(start, end),
            start,
            end,
            downtime_threshold_minutes=self.profile.downtime_threshold,
            include_inputs={slot: cfg.include_in_statistics for slot, cfg in self.profile.inputs.items()},
        )
        prev_start, prev_end = previous_bounds(start, end)
        previous = compute_period_stats(
            self.intervals(prev_start, prev_end),
            prev_start,
            prev_end,
            downtime_threshold_minutes=self.profile.downtime_threshold,
            include_inputs={slot: cfg.include_in_statistics for slot, cfg in self.profile.inputs.items()},
        )
        payload = current.to_dict()
        payload["previous"] = previous.to_dict()
        payload["comparison"] = {
            "work_delta": round(
                current.work_seconds - previous.work_seconds, 1
            ),
            "work_delta_percent": (
                round(
                    (current.work_seconds - previous.work_seconds)
                    / previous.work_seconds
                    * 100,
                    1,
                )
                if previous.work_seconds
                else 0.0
            ),
            "downtime_delta": current.downtime.count - previous.downtime.count,
        }
        return payload

    def downtime(
        self,
        period: str = "today",
        *,
        now: datetime | None = None,
        threshold_minutes: int | None = None,
    ) -> dict[str, Any]:
        """Downtime analysis for a period."""
        reference = now or datetime.now().astimezone()
        start, end = period_bounds(reference, period)
        minutes = (
            threshold_minutes
            if threshold_minutes is not None
            else self.profile.downtime_threshold
        )
        return compute_period_stats(
            self.intervals(start, end), start, end,
            downtime_threshold_minutes=minutes,
            include_inputs={slot: cfg.include_in_statistics for slot, cfg in self.profile.inputs.items()},
        ).downtime.to_dict()

    def input_timeline(
        self,
        start: datetime,
        end: datetime,
        slots: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return the physical input rows of the Real Flow.

        Every row keeps its own ON intervals clipped to the requested window.
        This layer is independent of the semantic priority resolution.
        """
        now = datetime.now().astimezone()
        window = max(1.0, (end - start).total_seconds())
        rows: list[dict[str, Any]] = []

        per_slot = self.engine.async_input_intervals(start, end)
        input_stats = input_statistics(per_slot, start, end)

        for slot, cfg in sorted(self.profile.inputs.items()):
            if slots is not None and slot not in slots:
                continue
            intervals = per_slot.get(slot, [])
            slices: list[dict[str, Any]] = []
            for item in intervals:
                raw_end = item.end or now
                if raw_end <= start or item.start >= end:
                    continue
                clipped_start = max(item.start, start)
                clipped_end = min(raw_end, end)
                seconds = (clipped_end - clipped_start).total_seconds()
                if seconds <= 0:
                    continue
                slices.append(
                    {
                        "start": clipped_start.isoformat(),
                        "end": clipped_end.isoformat(),
                        "duration": round(seconds, 1),
                        "offset": (
                            clipped_start - start
                        ).total_seconds(),
                        "state": "on",
                        "open": item.is_open,
                        "observed_start": item.start.isoformat(),
                    }
                )
            stat = input_stats.get(slot, {})
            rows.append(
                {
                    "slot": slot,
                    "name": cfg.display_name,
                    "description": cfg.input_description,
                    "entity_id": cfg.entity_id,
                    "semantic_state": cfg.semantic_state,
                    "icon": cfg.effective_icon,
                    "color": cfg.effective_color,
                    "enabled": cfg.enabled,
                    "visible": cfg.show_in_timeline,
                    "priority": cfg.effective_priority,
                    "on": self.engine.async_snapshot().active_inputs.get(slot),
                    "available": self.engine.async_snapshot().active_inputs.get(slot) is not None,
                    "include_in_statistics": cfg.include_in_statistics,
                    "on_seconds": stat.get("on_seconds", 0.0),
                    "on_percent": stat.get("on_percent", 0.0),
                    "activations": stat.get("activations", 0),
                    "longest_on": stat.get("longest_on", 0.0),
                    "last_activity": stat.get("last_activity"),
                    "intervals": slices,
                }
            )
        return {
            "rows": rows,
            "window": round(window, 1),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "row_order": normalize_row_order(self.profile.row_order, self.profile.inputs),
        }

    def offline_periods(
        self,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Return the offline periods of the machine in a window."""
        now = datetime.now().astimezone()
        result: list[dict[str, Any]] = []
        for item in self.engine.history.query(self.engine.history.intervals, start, end):
            if item.state != "offline":
                continue
            raw_end = item.end or now
            if raw_end <= start or item.start >= end:
                continue
            clipped_start = max(item.start, start)
            clipped_end = min(raw_end, end)
            seconds = (clipped_end - clipped_start).total_seconds()
            if seconds <= 0:
                continue
            result.append(
                {
                    "start": clipped_start.isoformat(),
                    "end": clipped_end.isoformat(),
                    "duration": round(seconds, 1),
                    "offset": (clipped_start - start).total_seconds(),
                    "open": item.is_open,
                }
            )
        return result

    def input_summary(
        self,
        period: str = "today",
        *,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Per input ON summary used next to the Real Flow."""
        reference = now or datetime.now().astimezone()
        start, end = period_bounds(reference, period)
        per_slot = self.engine.async_input_intervals(start, end)
        input_stats = input_statistics(per_slot, start, end)
        snapshot = self.engine.async_snapshot()
        summary: list[dict[str, Any]] = []
        for slot, cfg in sorted(self.profile.inputs.items()):
            stat = input_stats.get(slot, {})
            summary.append(
                {
                    "slot": slot,
                    "name": cfg.display_name,
                    "icon": cfg.effective_icon,
                    "color": cfg.effective_color,
                    "semantic_state": cfg.semantic_state,
                    "on": snapshot.active_inputs.get(slot),
                    "on_seconds": stat.get("on_seconds", 0.0),
                    "activations": stat.get("activations", 0),
                    "last_activity": stat.get("last_activity"),
                }
            )
        return summary

    def dashboard_payload(
        self,
        start: datetime,
        end: datetime,
        *,
        states: list[str] | None = None,
        slots: list[str] | None = None,
    ) -> dict[str, Any]:
        """Everything the dashboard needs for one machine and one range."""
        stats = self.stats(start=start, end=end)
        slices = self.timeline(start, end)
        if states is not None:
            allowed = set(states)
            slices = [
                item for item in slices if item["state"] in allowed
            ]
        events = []
        now = datetime.now().astimezone()
        for item in self.intervals(start, end):
            raw_end = item.end or now
            cfg = self.profile.input_for(item.source_input or "")
            events.append(
                {
                    "state": item.state,
                    "state_label": item.state.replace("_", " ").title(),
                    "color": cfg.effective_color if cfg else None,
                    "icon": cfg.effective_icon if cfg else None,
                    "input": item.source_input,
                    "input_name": cfg.display_name if cfg else None,
                    "entity": item.source_entity,
                    "start": max(item.start, start).isoformat(),
                    "end": min(raw_end, end).isoformat(),
                    "duration": round(
                        (min(raw_end, end) - max(item.start, start)).total_seconds(),
                        1,
                    ),
                }
            )
        events.sort(key=lambda entry: entry["start"], reverse=True)
        input_timeline = self.input_timeline(start, end, slots=slots)

        return {
            "history": self.history.metadata(),
            "machine_id": self.machine_id,
            "name": self.profile.name,
            "description": self.profile.description,
            "snapshot": {**self.snapshot().to_dict(), "offline_reason": self.engine.offline_reason()},
            "source_diagnostics": self.engine.source_diagnostics(),
            "stats": stats.to_dict(),
            "timeline": slices,
            "input_timeline": input_timeline,
            "offline_periods": self.offline_periods(start, end),
            "input_summary": [{key: row[key] for key in ("slot", "name", "color", "on", "on_seconds", "activations", "last_activity")}
                              for row in input_timeline["rows"]],
            "events": events,
            "inputs": [
                {
                    "slot": slot,
                    "entity_id": cfg.entity_id,
                    "name": cfg.display_name,
                    "description": cfg.input_description,
                    "semantic_state": cfg.semantic_state,
                    "icon": cfg.effective_icon,
                    "color": cfg.effective_color,
                    "enabled": cfg.enabled,
                    "priority": cfg.effective_priority,
                    "state": self.engine.async_snapshot().active_inputs.get(
                        slot
                    ),
                }
                for slot, cfg in sorted(self.profile.inputs.items())
            ],
            "settings": {
                "downtime_threshold": self.profile.downtime_threshold,
                "no_active_state": self.profile.no_active_state,
                "retention_days": self.profile.retention_days,
                "shifts": self.profile.shifts,
            },
        }

    def query_snapshot(self, start, end):
        """Freeze only requested records for safe computation off the HA loop."""
        result = copy(self)
        result.profile = deepcopy(self.profile)
        result.history = copy(self.history)
        result.history._metadata_override = self.history.metadata()
        result.history._intervals = self.history.freeze(self.history.query(self.history.intervals, start, end, include_previous=True))
        result.history._input_intervals = {slot: self.history.freeze(self.history.query(items, start, end))
                                           for slot, items in self.history.input_intervals().items()}
        result.engine = copy(self.engine)
        result.engine.profile = result.profile
        result.engine.history = result.history
        result.engine._inputs = deepcopy(self.engine._inputs)
        return result

    async def async_dashboard_payload(self, start, end, **kwargs):
        snapshot = self.query_snapshot(start, end)
        return await self.engine.hass.async_add_executor_job(lambda: snapshot.dashboard_payload(start, end, **kwargs))

    async def async_flush(self, *, force=True) -> None:
        """Persist pending history."""
        await self.engine.async_flush(force=force)


def create_runtime(
    hass: HomeAssistant,
    machine_id: str,
    profile: MachineProfile,
) -> MachineRuntime:
    """Create a runtime for one machine."""
    history = HistoryStore(
        hass, machine_id, history_limit=profile.history_limit
    )
    engine = EventEngine(hass, machine_id, profile, history)
    return MachineRuntime(
        machine_id=machine_id,
        profile=profile,
        history=history,
        engine=engine,
    )
