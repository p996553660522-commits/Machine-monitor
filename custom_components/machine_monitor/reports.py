"""Exact backend reports over independent physical and semantic histories."""
from datetime import datetime, time, timedelta, timezone
from bisect import bisect_left
from zoneinfo import ZoneInfo

from .const import SEMANTIC_STATES, WORK_STATES
from .stats import compute_period_stats, input_statistics
from .storage import HistoryStore


def period_report(profile, semantic, physical, start, end, now):
    start, end, now = (v.astimezone(timezone.utc) for v in (start, end, now))
    end = min(end, now)
    if end <= start:
        raise ValueError("Choose a past start and an end after it")
    entries = HistoryStore.query(semantic, start, end)
    includes = {slot: cfg.include_in_statistics for slot, cfg in profile.inputs.items()}
    stats = compute_period_stats(entries, start, end, include_inputs=includes,
                                 downtime_threshold_minutes=profile.downtime_threshold)
    known = sum((min(iv.end or now, end) - max(iv.start, start)).total_seconds()
                for iv in entries if iv.state != "offline" and min(iv.end or now, end) > max(iv.start, start))
    durations = {state: stats.seconds_for(state) for state in SEMANTIC_STATES if state != "offline"}
    runs = []
    for iv in entries:
        if iv.state not in WORK_STATES or not includes.get(iv.source_input, True):
            continue
        begin, finish = max(start, iv.start), min(end, iv.end or now)
        if finish <= begin:
            continue
        if runs and begin <= runs[-1][1]:
            runs[-1][1] = max(runs[-1][1], finish)
        else:
            index = bisect_left(semantic, iv.start, key=lambda item: item.start)
            previous = semantic[index - 1] if index else None
            continuation = previous is not None and previous.end == iv.start and previous.state in WORK_STATES and includes.get(previous.source_input, True)
            runs.append([begin, finish, iv.start >= start and not continuation])
    idle_runs = []
    for iv in entries:
        if iv.state != "idle" or not includes.get(iv.source_input, True):
            continue
        begin, finish = max(start, iv.start), min(end, iv.end or now)
        if finish <= begin:
            continue
        if idle_runs and begin <= idle_runs[-1][1]:
            idle_runs[-1][1] = max(idle_runs[-1][1], finish)
        else:
            idle_runs.append([begin, finish])
    inputs = input_statistics({slot: HistoryStore.query(items, start, end) for slot, items in physical.items()}, start, end)
    total = (end - start).total_seconds()
    denominator = stats.monitored_seconds
    return {"start": start.isoformat(), "end": end.isoformat(), "total_seconds": total,
            "known_seconds": known, "included_known_seconds": denominator,
            "offline_seconds": stats.offline_seconds,
            "unrecorded_seconds": max(0, total - known - stats.offline_seconds),
            "work_seconds": stats.work_seconds, "idle_seconds": durations.get("idle", 0),
            "non_productive_seconds": stats.idle_seconds, "states": durations,
            "work_percent": round(stats.work_seconds / denominator * 100, 2) if denominator else 0,
            "idle_percent": round(durations.get("idle", 0) / denominator * 100, 2) if denominator else 0,
            "offline_percent": round(stats.offline_seconds / total * 100, 2),
            "percentage_basis": "included_known_time; offline percentage uses total period",
            "work_cycles": sum(bool(run[2]) for run in runs),
            "longest_work_seconds": max(((r[1] - r[0]).total_seconds() for r in runs), default=0),
            "longest_idle_seconds": max(((r[1] - r[0]).total_seconds() for r in idle_runs), default=0),
            "downtime_count": stats.downtime.count,
            "longest_downtime_seconds": stats.downtime.longest_seconds,
            "inputs": [{"slot": slot, "name": cfg.display_name, "color": cfg.effective_color,
                        **inputs.get(slot, {"on_seconds": 0, "activations": 0})}
                       for slot, cfg in profile.inputs.items()]}


def compare_reports(a, b):
    """B minus A: relative change for quantities, percentage points for shares."""
    metrics = ("work_seconds", "idle_seconds", "offline_seconds", "known_seconds", "work_percent",
               "idle_percent", "offline_percent", "downtime_count", "work_cycles")
    return [{"metric": key, "a": a[key], "b": b[key], "delta": b[key] - a[key],
             "change": round(b[key] - a[key], 2) if key.endswith("percent") else
                       (round((b[key] - a[key]) / a[key] * 100, 2) if a[key] else None),
             "unit": "pp" if key.endswith("percent") else "%"} for key in metrics]


def shift_windows(shifts, start, end, zone):
    """Wall-clock shifts in HA timezone, including the previous day's night shift.

    DST: nonexistent local boundary advances through the gap; ambiguous boundary
    uses the first occurrence. Each boundary is converted to UTC before duration math.
    """
    tz = ZoneInfo(zone)
    day = start.astimezone(tz).date() - timedelta(days=1)
    final = end.astimezone(tz).date()
    while day <= final:
        for shift in shifts:
            a, b = time.fromisoformat(shift["start"]), time.fromisoformat(shift["end"])
            begin = datetime.combine(day, a, tzinfo=tz).astimezone(timezone.utc)
            finish = datetime.combine(day + timedelta(days=b <= a), b, tzinfo=tz).astimezone(timezone.utc)
            lo, hi = max(start, begin), min(end, finish)
            if hi > lo:
                yield shift["name"], lo, hi
        day += timedelta(days=1)


def shift_reports(profile, semantic, physical, start, end, now, zone):
    results = {s["name"]: {"name": s["name"], "total_seconds": 0, "known_seconds": 0,
               "included_known_seconds": 0, "work_seconds": 0, "idle_seconds": 0,
               "offline_seconds": 0, "downtime_count": 0} for s in profile.shifts}
    for name, a, b in shift_windows(profile.shifts, start, min(end, now), zone):
        report = period_report(profile, semantic, {}, a, b, now)
        for key in results[name]:
            if key != "name":
                results[name][key] += report[key]
    for row in results.values():
        den = row["included_known_seconds"]
        row["work_percent"] = round(row["work_seconds"] / den * 100, 2) if den else 0
        row["idle_percent"] = round(row["idle_seconds"] / den * 100, 2) if den else 0
    return list(results.values())


def build_reports(runtime, a_start, a_end, b_start=None, b_end=None, zone="UTC", now=None):
    now = now or datetime.now(timezone.utc)
    a = period_report(runtime.profile, runtime.history.intervals, runtime.history.input_intervals(), a_start, a_end, now)
    result = {"machine_id": runtime.machine_id, "name": runtime.name, "a": a,
              "history": runtime.history.metadata(now), "timezone": zone,
              "shifts": shift_reports(runtime.profile, runtime.history.intervals, {}, a_start, a_end, now, zone)}
    if b_start is not None and b_end is not None:
        b = period_report(runtime.profile, runtime.history.intervals, runtime.history.input_intervals(), b_start, b_end, now)
        result.update(b=b, comparison=compare_reports(a, b))
    return result
