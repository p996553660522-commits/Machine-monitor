"""Websocket API for Machine Monitor.

The bundled dashboard card uses these commands to fetch the timeline, the
statistics and the multi machine overview without polling many entities.

Commands
--------
`machine_monitor/overview`   - all machines with their current status
`machine_monitor/timeline`   - timeline slices + stats for one machine
`machine_monitor/statistics` - statistics for one machine and one period
`machine_monitor/downtime`   - downtime analysis for one machine
`machine_monitor/states`     - the list of supported semantic states
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import (
    DOMAIN,
    SEMANTIC_STATES,
    STATE_COLOR,
    STATE_ICON,
    STATE_PRIORITY,
)
from .coordinator import MachineMonitorCoordinator
from .models import default_state_color, default_state_icon, default_state_priority
from .stats import period_bounds, previous_bounds

_LOGGER = logging.getLogger(__name__)


def _parse_dt(value: Any) -> datetime | None:
    """Parse an ISO timestamp."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def _machine_or_none(
    coordinator: MachineMonitorCoordinator, machine_id: str
):
    """Return the runtime of a machine."""
    return coordinator.runtime_for(machine_id)


@callback
def _register(hass: HomeAssistant) -> None:
    """Register all websocket commands."""
    websocket_api.async_register_command(hass, ws_overview)
    websocket_api.async_register_command(hass, ws_timeline)
    websocket_api.async_register_command(hass, ws_statistics)
    websocket_api.async_register_command(hass, ws_downtime)
    websocket_api.async_register_command(hass, ws_states)
    websocket_api.async_register_command(hass, ws_reports)


@websocket_api.websocket_command({vol.Required("type"): "machine_monitor/overview"})
@websocket_api.async_response
async def ws_overview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the overview of every machine."""
    coordinator: MachineMonitorCoordinator = hass.data[DOMAIN]["coordinator"]
    payload = await coordinator.async_machine_summaries()
    connection.send_result(
        msg["id"],
        {
            "machines": [
                payload[key] for key in sorted(payload, key=lambda k: payload[k]["name"].lower())
            ],
            "generated": datetime.now().astimezone().isoformat(),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "machine_monitor/timeline",
        vol.Required("machine_id"): str,
        vol.Optional("start"): str,
        vol.Optional("end"): str,
        vol.Optional("period"): str,
        vol.Optional("states"): vol.All(
            list, [str]
        ),
        vol.Optional("inputs"): vol.All(
            list, [str]
        ),
    }
)
@websocket_api.async_response
async def ws_timeline(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the timeline slices, statistics and events for one machine."""
    coordinator: MachineMonitorCoordinator = hass.data[DOMAIN]["coordinator"]
    runtime = _machine_or_none(coordinator, msg["machine_id"])
    if runtime is None:
        connection.send_error(
            msg["id"], "unknown_machine", "Unknown machine"
        )
        return

    if ("start" in msg or "end" in msg) and (
        _parse_dt(msg.get("start")) is None or _parse_dt(msg.get("end")) is None
    ):
        connection.send_error(msg["id"], "invalid_range", "Use aware ISO start and end timestamps")
        return
    start = _parse_dt(msg.get("start"))
    end = _parse_dt(msg.get("end"))
    if start is None or end is None:
        start, end = period_bounds(
            datetime.now().astimezone(), msg.get("period", "today")
        )

    if end <= start:
        connection.send_error(msg["id"], "invalid_range", "End must be after start")
        return
    end = min(end, datetime.now().astimezone())
    if end <= start:
        connection.send_error(msg["id"], "invalid_range", "Range must include past time")
        return
    payload = await runtime.async_dashboard_payload(
        start,
        end,
        states=msg.get("states"),
        slots=msg.get("inputs"),
    )
    connection.send_result(msg["id"], payload)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "machine_monitor/statistics",
        vol.Required("machine_id"): str,
        vol.Optional("period"): str,
    }
)
@websocket_api.async_response
async def ws_statistics(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return statistics for one machine and one period."""
    coordinator: MachineMonitorCoordinator = hass.data[DOMAIN]["coordinator"]
    runtime = _machine_or_none(coordinator, msg["machine_id"])
    if runtime is None:
        connection.send_error(
            msg["id"], "unknown_machine", "Unknown machine"
        )
        return

    period = msg.get("period", "today")
    now = datetime.now().astimezone()
    start, end = period_bounds(now, period)
    previous_start, _ = previous_bounds(start, end)
    snapshot = runtime.query_snapshot(previous_start, end)
    payload = await hass.async_add_executor_job(lambda: snapshot.stats_with_comparison(period, now=now))
    payload["machines_states"] = [
        {
            "state": state,
            "label": state.replace("_", " ").title(),
            "icon": default_state_icon(state),
            "color": default_state_color(state),
            "priority": default_state_priority(state),
        }
        for state in SEMANTIC_STATES
    ]
    connection.send_result(msg["id"], payload)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "machine_monitor/downtime",
        vol.Required("machine_id"): str,
        vol.Optional("period"): str,
        vol.Optional("threshold_minutes"): vol.Coerce(int),
    }
)
@websocket_api.async_response
async def ws_downtime(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the downtime analysis for one machine."""
    coordinator: MachineMonitorCoordinator = hass.data[DOMAIN]["coordinator"]
    runtime = _machine_or_none(coordinator, msg["machine_id"])
    if runtime is None:
        connection.send_error(
            msg["id"], "unknown_machine", "Unknown machine"
        )
        return

    period = msg.get("period", "today")
    now = datetime.now().astimezone()
    start, end = period_bounds(now, period)
    snapshot = runtime.query_snapshot(start, end)
    payload = await hass.async_add_executor_job(lambda: snapshot.downtime(
        period, now=now, threshold_minutes=msg.get("threshold_minutes")))
    connection.send_result(msg["id"], payload)


@websocket_api.websocket_command({vol.Required("type"): "machine_monitor/states"})
@websocket_api.async_response
async def ws_states(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return every supported semantic state with its metadata."""
    connection.send_result(
        msg["id"],
        {
            "states": [
                {
                    "state": state,
                    "label": state.replace("_", " ").title(),
                    "icon": STATE_ICON.get(state),
                    "color": STATE_COLOR.get(state),
                    "priority": STATE_PRIORITY.get(state),
                }
                for state in SEMANTIC_STATES
            ]
        },
    )


@websocket_api.websocket_command({vol.Required("type"): "machine_monitor/reports",
    vol.Required("machine_id"): str, vol.Required("start"): str, vol.Required("end"): str,
    vol.Optional("compare_start"): str, vol.Optional("compare_end"): str})
@websocket_api.async_response
async def ws_reports(hass, connection, msg):
    from .reports import build_reports
    runtime = hass.data[DOMAIN]["coordinator"].runtime_for(msg["machine_id"])
    if runtime is None:
        connection.send_error(msg["id"], "unknown_machine", "Unknown machine")
        return
    start, end = _parse_dt(msg.get("start")), _parse_dt(msg.get("end"))
    a, b = _parse_dt(msg.get("compare_start")), _parse_dt(msg.get("compare_end"))
    now = datetime.now().astimezone()
    comparison = "compare_start" in msg or "compare_end" in msg
    if not start or not end or end <= start or start >= now or (comparison and (not a or not b or b <= a or a >= now)):
        connection.send_error(msg["id"], "invalid_range", "Use aware ISO timestamps; start must be before end and NOW")
        return
    snapshot = runtime.query_snapshot(min(start, a or start), min(max(end, b or end), now))
    zone = getattr(getattr(hass, "config", None), "time_zone", "UTC")
    payload = await hass.async_add_executor_job(build_reports, snapshot, start, end, a, b, zone, now)
    connection.send_result(msg["id"], payload)


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the websocket API."""
    _register(hass)
