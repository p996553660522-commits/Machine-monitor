"""Persistent storage for Machine Monitor.

History must survive a Home Assistant restart, so it is kept in the Home
Assistant `.storage` folder using :class:homeassistant.helpers.storage.Store
instead of plain in-memory state.

Two independent layers are stored for every machine:

* ``intervals``        - the semantic machine state timeline (work, idle, ...);
* ``input_intervals``  - the ON intervals of every physical input, kept
  independently of the semantic priority resolution.
"""

from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timedelta
from dataclasses import replace
from bisect import bisect_left, bisect_right
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import INPUT_ON, STORAGE_KEY_PREFIX, STORAGE_VERSION
from .models import Interval

_LOGGER = logging.getLogger(__name__)


class HistoryStore:
    """Load and persist the timelines of a single machine."""

    def __init__(
        self,
        hass: HomeAssistant,
        machine_id: str,
        history_limit: int = 5000,
    ) -> None:
        """Initialise the store for one machine."""
        self.hass = hass
        self.machine_id = machine_id
        self._history_limit = history_limit
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}.{machine_id}",
            atomic_writes=True, serialize_in_event_loop=False,
        )
        self._intervals: list[Interval] = []
        self._input_intervals: dict[str, list[Interval]] = {}
        self._save_lock = asyncio.Lock()
        self._prune_lock = asyncio.Lock()
        self._dirty = False
        self._observed_at: datetime | None = None
        self.last_seen: datetime | None = None
        self.retention_days = 30
        self._last_cleanup = None
        self._last_saved_at = None
        self._size_bytes = None
        self._metadata_override = None

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    async def async_load(self) -> list[Interval]:
        """Load the persisted timelines."""
        data: dict[str, Any] | None = None
        try:
            data = await self._store.async_load()
        except Exception:  # noqa: BLE001 - storage must never break startup
            _LOGGER.exception(
                "Machine Monitor: could not load history for %s",
                self.machine_id,
            )
            raise

        if (data or {}).get("history_schema_version", 1) > 3:
            raise ValueError("Unsupported future Machine Monitor history schema")
        result = await self.hass.async_add_executor_job(self._decode, data)
        self._size_bytes = await self.hass.async_add_executor_job(self._file_size)
        return result

    def _decode(self, data):
        """Parse a potentially long history in HA's executor during startup."""
        seen = (data or {}).get("last_seen")
        self.last_seen = datetime.fromisoformat(seen) if seen else None
        observed = (data or {}).get("observed_at")
        self._observed_at = datetime.fromisoformat(observed) if observed else None
        intervals: list[Interval] = []
        for raw in (data or {}).get("intervals", []):
            try:
                intervals.append(Interval.from_dict(raw))
            except (KeyError, TypeError, ValueError):
                _LOGGER.warning(
                    "Machine Monitor: skipping malformed interval for %s",
                    self.machine_id,
                )
        intervals.sort(key=lambda item: item.start)
        self._intervals = intervals

        # Migration: storage written before the physical input layer does not
        # contain input_intervals at all. The semantic history is kept as is
        # and the input history simply starts collecting from now on.
        raw_inputs: dict[str, Any] = (data or {}).get("input_intervals")
        if raw_inputs is None:
            if data:
                _LOGGER.info(
                    "Machine Monitor: storage of %s migrated, "
                    "physical input history starts collecting now",
                    self.machine_id,
                )
            raw_inputs = {}

        input_intervals: dict[str, list[Interval]] = {}
        for slot, entries in raw_inputs.items():
            parsed: list[Interval] = []
            for raw_entry in entries or []:
                try:
                    parsed.append(Interval.from_dict(raw_entry))
                except (KeyError, TypeError, ValueError):
                    _LOGGER.warning(
                        "Machine Monitor: skipping malformed input "
                        "interval %s for %s",
                        slot,
                        self.machine_id,
                    )
            input_intervals[slot] = sorted(parsed, key=lambda item: item.start)
        self._input_intervals = input_intervals

        _LOGGER.debug(
            "Machine Monitor: loaded %s semantic and %s input intervals "
            "for machine %s",
            len(self._intervals),
            sum(len(v) for v in self._input_intervals.values()),
            self.machine_id,
        )
        return self._intervals

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------
    @property
    def intervals(self) -> list[Interval]:
        """Return the semantic timeline."""
        return self._intervals

    def input_intervals(self, slot: str | None = None) -> list[Interval] | dict[str, list[Interval]]:
        """Return the physical input timeline of one slot or of all slots."""
        if slot is None:
            return self._input_intervals
        return self._input_intervals.get(slot, [])

    def input_slots(self) -> list[str]:
        """Return every slot that has recorded intervals."""
        return sorted(self._input_intervals)

    def set_history_limit(self, limit: int) -> None:
        """Update the maximum number of persisted intervals."""
        self._history_limit = max(10, int(limit))
        self._trim()

    # ------------------------------------------------------------------
    # Semantic timeline
    # ------------------------------------------------------------------
    def async_repair_open_interval(self, now: datetime) -> Interval | None:
        """Close a semantic interval left open by a restart.

        Close at the persisted observation checkpoint, never at restart time.
        Legacy stores without a checkpoint retain the interval but cannot
        establish its duration beyond its start. The gap stays unknown.
        """
        if not self._intervals:
            return None
        last = self._intervals[-1]
        if not last.is_open:
            return None

        last.end = max(last.start, min(self._observed_at or last.start, now))
        _LOGGER.info(
            "Machine Monitor: closed interrupted semantic interval "
            "for %s at %s",
            self.machine_id,
            last.end.isoformat(),
        )
        self._dirty = True
        return last

    def async_record_observation_gap(self, now: datetime) -> None:
        """Monitoring was unavailable after the last persisted observation."""
        if self._observed_at is None or self._observed_at >= now:
            return
        start = self._observed_at
        if self._intervals and self._intervals[-1].end is not None:
            start = max(start, self._intervals[-1].end)
        if start < now:
            self.async_open_interval(start, "offline")
            self.async_close_interval(now)

    def async_open_interval(
        self,
        start: datetime,
        state: str,
        source_input: str | None = None,
        source_entity: str | None = None,
    ) -> Interval:
        """Append a new open semantic interval."""
        interval = Interval(
            start=start,
            end=None,
            state=state,
            source_input=source_input,
            source_entity=source_entity,
        )
        self._intervals.append(interval)
        self._trim()
        self._dirty = True
        return interval

    def async_close_interval(self, end: datetime) -> Interval | None:
        """Close the currently open semantic interval."""
        if not self._intervals:
            return None
        last = self._intervals[-1]
        if not last.is_open:
            return None
        if end <= last.start:
            end = last.start + timedelta(milliseconds=1)
        last.end = end
        self._dirty = True
        return last

    def async_prune(self, older_than: datetime) -> int:
        """Drop closed intervals entirely before the retained window."""
        before = len(self._intervals)
        self._intervals = [
            item for item in self._intervals if item.end is None or item.end > older_than
        ]
        removed = before - len(self._intervals)

        before_inputs = sum(len(v) for v in self._input_intervals.values())
        for slot in list(self._input_intervals):
            self._input_intervals[slot] = [
                item
                for item in self._input_intervals[slot]
                if item.end is None or item.end > older_than
            ]
            if not self._input_intervals[slot]:
                del self._input_intervals[slot]
        removed += before_inputs - sum(
            len(v) for v in self._input_intervals.values()
        )

        if removed:
            self._dirty = True
            _LOGGER.info(
                "Machine Monitor: pruned %s old intervals for %s",
                removed,
                self.machine_id,
            )
        return removed

    def async_clear(self) -> None:
        """Remove both timelines."""
        self._intervals = []
        self._input_intervals = {}
        self._dirty = True

    def _trim(self) -> None:
        """V6 retains by age. A transition-count cap silently loses recent days."""

    def set_retention(self, days: int) -> None:
        days = max(1, min(365, int(days)))
        if self.retention_days != days:
            self.retention_days = days
            self._last_cleanup = None

    async def async_prune_due(self, now: datetime, *, force=False) -> int:
        """Prepare retained lists and release expired records off the HA loop.

        Existing records are stable except the current tail. Transitions appended
        while the executor runs are carried over before swapping list references.
        """
        async with self._prune_lock:
            if not force and self._last_cleanup and now - self._last_cleanup < timedelta(days=1):
                return 0
            groups = [(None, self._intervals, len(self._intervals))]
            groups.extend((slot, items, len(items)) for slot, items in self._input_intervals.items())
            prepared = await self.hass.async_add_executor_job(
                self._retained_groups, groups, now - timedelta(days=self.retention_days))
            removed = 0
            for slot, original, length, index, retained in prepared:
                current = self._intervals if slot is None else self._input_intervals.get(slot)
                if index and current is original:
                    retained.extend(original[length:])
                    if slot is None:
                        self._intervals = retained
                    else:
                        self._input_intervals[slot] = retained
                    removed += index
            self._last_cleanup = now
            if removed:
                self._dirty = True
            # Do not leave the final reference to a large discarded list on-loop.
            current = original = retained = None
            groups.clear()
            await self.hass.async_add_executor_job(prepared.clear)
            return removed

    @staticmethod
    def _retained_groups(groups, cutoff):
        result = []
        for slot, entries, length in groups:
            index = bisect_right(entries, cutoff.timestamp(), hi=length,
                                 key=lambda iv: iv.end.timestamp() if iv.end else float("inf"))
            result.append((slot, entries, length, index, entries[index:length] if index else None))
        return result

    @staticmethod
    def query(entries, start=None, end=None, *, include_previous=False):
        """Closed intervals are ordered and disjoint within each history."""
        first = bisect_right(entries, start.timestamp(), key=lambda iv: iv.end.timestamp() if iv.end else float("inf")) if start else 0
        if include_previous:
            first = max(0, first - 1)
        last = bisect_left(entries, end.timestamp(), key=lambda iv: iv.start.timestamp()) if end else len(entries)
        return entries[first:last]

    @staticmethod
    def freeze(entries):
        """Closed records are immutable; only the tail may still be changing."""
        result = list(entries)
        if result and result[-1].is_open:
            result[-1] = replace(result[-1])
        return result

    def _file_size(self):
        try:
            return Path(self._store.path).stat().st_size
        except (OSError, AttributeError):
            return None

    def metadata(self, now=None):
        if self._metadata_override is not None:
            return self._metadata_override
        now = now or datetime.now().astimezone()
        groups = [entries for entries in [self._intervals, *self._input_intervals.values()] if entries]
        oldest = min((entries[0].start for entries in groups), default=None)
        newest = max((entries[-1].end or now for entries in groups), default=None)
        available = max(oldest, now - timedelta(days=self.retention_days)) if oldest else None
        return {"retention_days": self.retention_days, "size_bytes": self._size_bytes,
                "size_basis": "persistent_file", "oldest_record": oldest.isoformat() if oldest else None,
                "newest_record": newest.isoformat() if newest else None,
                "available_from": available.isoformat() if available else None,
                "physical_intervals": sum(len(items) for items in self._input_intervals.values()),
                "semantic_intervals": len(self._intervals), "schema_version": 3,
                "last_saved": self._last_saved_at.isoformat() if self._last_saved_at else None}

    # ------------------------------------------------------------------
    # Physical input timeline
    # ------------------------------------------------------------------
    def async_open_input_interval(
        self,
        slot: str,
        start: datetime,
    ) -> Interval:
        """Open the ON interval of one physical input.

        A stray open interval is closed first so the timeline always stays
        consistent.
        """
        self._close_input_interval_internal(slot, start)
        interval = Interval(
            start=start,
            end=None,
            state=INPUT_ON,
            source_input=slot,
        )
        self._input_intervals.setdefault(slot, []).append(interval)
        self._trim()
        self._dirty = True
        return interval

    def async_close_input_interval(
        self,
        slot: str,
        end: datetime,
    ) -> Interval | None:
        """Close the open ON interval of one physical input."""
        interval = self._close_input_interval_internal(slot, end)
        if interval is not None:
            self._dirty = True
        return interval

    def _close_input_interval_internal(
        self,
        slot: str,
        end: datetime,
    ) -> Interval | None:
        """Close an open input interval without touching the dirty flag."""
        entries = self._input_intervals.get(slot)
        if not entries:
            return None
        last = entries[-1]
        if not last.is_open:
            return None
        if end <= last.start:
            end = last.start + timedelta(milliseconds=1)
        last.end = end
        self._dirty = True
        return last

    def async_repair_open_input_intervals(self, now: datetime) -> int:
        """Close input intervals left open by a restart.

        Close at the last persisted observation. No activity is inferred
        during the unobserved gap; a confirmed ON opens a fresh interval.
        """
        repaired = 0
        for slot in list(self._input_intervals):
            entries = self._input_intervals.get(slot) or []
            if not entries:
                continue
            last = entries[-1]
            if not last.is_open:
                continue
            last.end = max(last.start, min(self._observed_at or last.start, now))
            repaired += 1
            self._dirty = True
            _LOGGER.debug(
                "Machine Monitor: repaired open input interval %s of %s",
                slot,
                self.machine_id,
            )
        return repaired

    def async_input_slices(
        self,
        slot: str,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Return ON slices of one input clipped to a window."""
        now = datetime.now().astimezone()
        result: list[dict[str, Any]] = []
        for item in self._input_intervals.get(slot, []):
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
                    "state": INPUT_ON,
                }
            )
        return result

    # ------------------------------------------------------------------
    # Persisting
    # ------------------------------------------------------------------
    def mark_observed(self, now: datetime) -> None:
        """Checkpoint the last time the running engine knew its inputs."""
        self._observed_at = now
        self._dirty = True

    async def async_flush(self) -> bool:
        """Serialize writes so an older save cannot overwrite a newer one."""
        async with self._save_lock:
            return await self._async_save()

    async def _async_save(self) -> bool:
        """Write both timelines to disk; additive schema remains v1-loadable."""
        semantic = self.freeze(self._intervals)
        physical = {slot: self.freeze(items) for slot, items in self._input_intervals.items()}
        seen, observed = self.last_seen, self._observed_at
        # Changes may arrive while async_save yields. Retain their dirty flag.
        self._dirty = False
        try:
            payload = await self.hass.async_add_executor_job(self._encode, semantic, physical, seen, observed)
            await self._store.async_save(payload)
            self._last_saved_at = datetime.now().astimezone()
            self._size_bytes = await self.hass.async_add_executor_job(self._file_size)
            return True
        except Exception:  # noqa: BLE001 - never break the event loop
            self._dirty = True
            _LOGGER.exception(
                "Machine Monitor: could not save history for %s",
                self.machine_id,
            )
            return False

    def _encode(self, semantic, physical, seen, observed):
        return {"history_schema_version": 3, "machine_id": self.machine_id,
                "last_seen": seen.isoformat() if seen else None,
                "observed_at": observed.isoformat() if observed else None,
                "intervals": [item.to_dict() for item in semantic],
                "input_intervals": {slot: [item.to_dict() for item in items] for slot, items in physical.items()}}

    async def async_flush_if_dirty(self, *, force=True) -> None:
        """Batch event-driven refresh writes; lifecycle calls force a flush."""
        if not force and self._last_saved_at and datetime.now().astimezone() - self._last_saved_at < timedelta(seconds=30):
            return
        if self._dirty:
            await self.async_flush()


def store_key(machine_id: str) -> str:
    """Return the storage key used for a machine."""
    return f"{STORAGE_KEY_PREFIX}.{machine_id}"


__all__ = ["HistoryStore", "store_key", "INPUT_ON"]
