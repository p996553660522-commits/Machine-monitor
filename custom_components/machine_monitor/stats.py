"""Statistics for Machine Monitor.

All calculations are pure functions over a list of :class:Interval objects so
they can be unit tested and reused by both the sensors and the dashboard.

Offline time is never counted as work or idle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable

from homeassistant.util import dt as dt_util

from .const import (
    EXCLUDED_STATES,
    SEMANTIC_STATES,
    STATE_OTHER,
    STATE_PRIORITY,
    WORK_STATES,
)
from .models import Interval, default_state_color, default_state_icon


def input_statistics(
    intervals_by_slot: dict[str, list[Interval]],
    start: datetime,
    end: datetime,
) -> dict[str, dict[str, Any]]:
    """Compute the physical ON statistics of every input for a period.

    This layer is completely independent of the semantic machine states:
    it answers the questions "how long was signal X actually high" and
    "how many times did it activate", no matter which semantic state wins
    the priority resolution at any moment.
    """
    window = max(1.0, (end - start).total_seconds())
    result: dict[str, dict[str, Any]] = {}
    now = datetime.now().astimezone()

    for slot, intervals in intervals_by_slot.items():
        on_seconds = 0.0
        longest = 0.0
        activations = 0
        last_end: datetime | None = None
        for item, seconds in clip_intervals(intervals, start, end):
            on_seconds += seconds
            longest = max(longest, seconds)
            if item.start >= start:
                activations += 1
            raw_end = item.end or now
            if last_end is None or raw_end > last_end:
                last_end = raw_end
        result[slot] = {
            "on_seconds": round(on_seconds, 1),
            "on_percent": round(on_seconds / window * 100, 1),
            "activations": activations,
            "longest_on": round(longest, 1),
            "last_activity": (
                last_end.isoformat() if last_end is not None else None
            ),
            "window": round(window, 1),
        }
    return result



def merge_adjacent(intervals: Iterable[Interval]) -> list[Interval]:
    """Merge neighbouring intervals that share the same semantic state."""
    merged: list[Interval] = []
    for item in sorted(intervals, key=lambda i: i.start):
        if item.is_open:
            continue
        if (
            merged
            and merged[-1].state == item.state
            and merged[-1].source_input == item.source_input
            and merged[-1].end is not None
            and abs((merged[-1].end - item.start).total_seconds()) < 1.0
        ):
            merged[-1].end = item.end
            continue
        merged.append(item)
    return merged


def clip_intervals(
    intervals: Iterable[Interval],
    start: datetime,
    end: datetime,
) -> list[tuple[Interval, float]]:
    """Return intervals clipped to `[start, end]` with their overlap seconds."""
    result: list[tuple[Interval, float]] = []
    for item in intervals:
        raw_end = item.end or min(end, datetime.now().astimezone())
        if raw_end <= start or item.start >= end:
            continue
        overlap_start = max(item.start, start)
        overlap_end = min(raw_end, end)
        seconds = (overlap_end - overlap_start).total_seconds()
        if seconds <= 0:
            continue
        result.append((item, seconds))
    return result


@dataclass(slots=True)
class StateSummary:
    """Aggregated time for one semantic state."""

    state: str
    seconds: float = 0.0

    @property
    def label(self) -> str:
        """Display label of the state."""
        return self.state.replace("_", " ").title()

    @property
    def icon(self) -> str:
        """Icon of the state."""
        return default_state_icon(self.state)

    @property
    def color(self) -> str:
        """Colour of the state."""
        return default_state_color(self.state)

    def to_dict(self) -> dict[str, Any]:
        """Serialise for the API."""
        return {
            "state": self.state,
            "label": self.label,
            "icon": self.icon,
            "color": self.color,
            "seconds": round(self.seconds, 1),
        }


@dataclass(slots=True)
class DowntimeInfo:
    """Analysis of the downtime periods of a machine."""

    threshold_minutes: int = 10
    count: int = 0
    total_seconds: float = 0.0
    average_seconds: float = 0.0
    longest_seconds: float = 0.0
    periods: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise for the API."""
        return {
            "threshold_minutes": self.threshold_minutes,
            "count": self.count,
            "total_seconds": round(self.total_seconds, 1),
            "average_seconds": round(self.average_seconds, 1),
            "longest_seconds": round(self.longest_seconds, 1),
            "periods": self.periods,
        }


@dataclass(slots=True)
class PeriodStats:
    """Complete statistics for one machine in one period."""

    start: datetime
    end: datetime
    states: list[StateSummary] = field(default_factory=list)
    work_seconds: float = 0.0
    idle_seconds: float = 0.0
    offline_seconds: float = 0.0
    monitored_seconds: float = 0.0
    downtime: DowntimeInfo = field(default_factory=DowntimeInfo)

    def seconds_for(self, state: str) -> float:
        """Return the seconds recorded for one state."""
        for item in self.states:
            if item.state == state:
                return item.seconds
        return 0.0

    @property
    def total_seconds(self) -> float:
        """Total accounted seconds excluding offline."""
        return self.work_seconds + self.idle_seconds

    def percent(self, state: str) -> float:
        """Percentage of the accounted time spent in a state.

        Offline time is intentionally excluded from the accounting, therefore
        an offline state never reports a percentage.
        """
        if state in EXCLUDED_STATES:
            return 0.0
        if self.total_seconds <= 0:
            return 0.0
        return round(self.seconds_for(state) / self.total_seconds * 100, 1)

    @property
    def work_percent(self) -> float:
        """Percentage of productive time."""
        return round(self.work_seconds / self.total_seconds * 100, 1) if self.total_seconds else 0.0

    @property
    def idle_percent(self) -> float:
        """Percentage of non productive, non offline time."""
        return round(100 - self.work_percent, 1) if self.total_seconds else 0.0

    @property
    def offline_percent(self) -> float:
        """Share of the whole window during which the machine was offline.

        Deliberately measured against the full window and not against the
        accounted time: offline time is never redistributed into the
        work/idle percentages.
        """
        window = (self.end - self.start).total_seconds()
        if window <= 0:
            return 0.0
        return round(self.offline_seconds / window * 100, 1)

    def to_dict(self) -> dict[str, Any]:
        """Serialise for the API."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "states": [item.to_dict() for item in self.states],
            "work_seconds": round(self.work_seconds, 1),
            "idle_seconds": round(self.idle_seconds, 1),
            "offline_seconds": round(self.offline_seconds, 1),
            "monitored_seconds": round(self.monitored_seconds, 1),
            "work_percent": self.work_percent,
            "idle_percent": self.idle_percent,
            "offline_percent": self.offline_percent,
            "downtime": self.downtime.to_dict(),
        }


def _first(states: tuple[str, ...]) -> str:
    """Return the first element of a state tuple."""
    return states[0] if states else STATE_OTHER


def compute_period_stats(
    intervals: Iterable[Interval],
    start: datetime,
    end: datetime,
    *,
    downtime_states: Iterable[str] | None = None,
    downtime_threshold_minutes: int = 10,
    include_states: dict[str, bool] | None = None,
    include_inputs: dict[str, bool] | None = None,
) -> PeriodStats:
    """Compute the statistics of one machine for a period."""
    intervals = list(intervals)
    idle_like = set(
        downtime_states
        or (
            "idle",
            "waiting",
            "preparation",
            "cooling",
            "heating",
            "other",
            "technical",
        )
    )
    stats = PeriodStats(start=start, end=end)

    buckets: dict[str, float] = {}
    for item, seconds in clip_intervals(intervals, start, end):
        if item.state in EXCLUDED_STATES:
            buckets[item.state] = buckets.get(item.state, 0.0) + seconds
            stats.offline_seconds += seconds
            continue
        if include_inputs is not None and not include_inputs.get(item.source_input, True):
            continue
        if include_states is not None and not include_states.get(
            item.state, True
        ):
            continue
        buckets[item.state] = buckets.get(item.state, 0.0) + seconds
        stats.monitored_seconds += seconds
        if item.state in WORK_STATES:
            stats.work_seconds += seconds
        else:
            stats.idle_seconds += seconds

    for state in SEMANTIC_STATES:
        seconds = buckets.get(state, 0.0)
        if seconds <= 0:
            continue
        stats.states.append(StateSummary(state=state, seconds=seconds))

    stats.states.sort(
        key=lambda item: (STATE_PRIORITY.get(item.state, 0), item.state),
        reverse=True,
    )
    stats.downtime = analyse_downtime(
        intervals,
        start,
        end,
        states=idle_like - set(EXCLUDED_STATES),
        include_inputs=include_inputs,
        threshold_minutes=downtime_threshold_minutes,
    )
    return stats


def analyse_downtime(
    intervals: Iterable[Interval],
    start: datetime,
    end: datetime,
    *,
    states: Iterable[str],
    threshold_minutes: int = 10,
    include_inputs: dict[str, bool] | None = None,
) -> DowntimeInfo:
    """Find downtime periods longer than the configured threshold."""
    target = set(states)
    info = DowntimeInfo(threshold_minutes=threshold_minutes)
    threshold_seconds = max(0.0, float(threshold_minutes) * 60)

    candidates: list[tuple[datetime, datetime, str | None]] = []
    for item, _seconds in clip_intervals(intervals, start, end):
        if item.state in target and item.state not in EXCLUDED_STATES:
            if include_inputs is not None and not include_inputs.get(item.source_input, True):
                continue
            candidates.append((max(item.start, start), min(item.end or datetime.now().astimezone(), end), item.source_input))

    candidates.sort(key=lambda entry: entry[0])

    runs: list[list] = []
    for begin, finish, source in candidates:
        if runs and begin <= runs[-1][1]:
            runs[-1][1] = max(runs[-1][1], finish)
            runs[-1][2].add(source)
            continue
        runs.append([begin, finish, {source}])

    for run in runs:
        begin, finish, sources = run[0], run[1], run[2]
        length = (finish - begin).total_seconds()
        if length < threshold_seconds:
            continue
        info.count += 1
        info.total_seconds += length
        info.longest_seconds = max(info.longest_seconds, length)
        info.periods.append(
            {
                "start": begin.isoformat(),
                "end": finish.isoformat(),
                "duration": round(length, 1),
                "inputs": sorted(item for item in sources if item),
            }
        )

    if info.count:
        info.average_seconds = info.total_seconds / info.count
    info.periods.sort(key=lambda entry: entry["start"], reverse=True)
    return info


def period_bounds(
    now: datetime,
    period: str,
) -> tuple[datetime, datetime]:
    """Return the `(start, end)` of a named period."""
    now = dt_util.as_local(now)
    period = (period or "today").lower()
    end = now
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "yesterday":
        start = (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = start + timedelta(days=1)
    elif period == "week":
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif period == "last_week":
        start = (now - timedelta(days=now.weekday() + 7)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = start + timedelta(days=7)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "last_month":
        first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start = (first - timedelta(days=1)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        end = first
    else:
        hours = {"1h": 1, "6h": 6, "12h": 12, "24h": 24, "7d": 24 * 7, "30d": 24 * 30, "60d": 24 * 60, "90d": 24 * 90, "180d": 24 * 180, "365d": 24 * 365}.get(
            period, 24
        )
        start = now - timedelta(hours=hours)
    return start, end


def previous_bounds(
    start: datetime,
    end: datetime,
) -> tuple[datetime, datetime]:
    """Return the previous period of the same length."""
    span = end - start
    return start - span, start


def compare_periods(
    current: PeriodStats,
    previous: PeriodStats,
) -> dict[str, Any]:
    """Compare two periods of the same length."""
    delta_work = current.work_seconds - previous.work_seconds
    return {
        "work_delta": round(delta_work, 1),
        "work_delta_percent": (
            round(delta_work / previous.work_seconds * 100, 1)
            if previous.work_seconds
            else 0.0
        ),
        "idle_delta": round(current.idle_seconds - previous.idle_seconds, 1),
        "downtime_delta": current.downtime.count - previous.downtime.count,
    }
