"""Register the bundled UI without changing machine monitoring or user YAML."""
from __future__ import annotations

from hashlib import sha256
import logging
from pathlib import Path
from urllib.parse import urlsplit

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
CARD_FILENAME = "machine_monitor_card.js"
CARD_MOUNT = "/machine_monitor_static"
CARD_URL = f"{CARD_MOUNT}/{CARD_FILENAME}"
UI_PATH = "machine-monitor"


def _versioned_url(card: Path) -> str:
    """Content-based version also catches updates without a manifest bump."""
    return f"{CARD_URL}?v={sha256(card.read_bytes()).hexdigest()[:16]}"


def _lovelace_field(data, key):
    """Support current LovelaceData and older dict-based cores."""
    return data[key] if isinstance(data, dict) else getattr(data, key)


def _owns_resource(url: str) -> bool:
    parts = urlsplit(url)
    return not parts.scheme and not parts.netloc and parts.path == CARD_URL


async def _async_register_resource(resources, url: str) -> None:
    """Upsert our module in storage mode; YAML remains user-owned."""
    if not hasattr(resources, "async_create_item"):
        # YAML resource collections are read-only. The frontend module API
        # below loads the card in both modes without editing configuration.yaml.
        return
    await resources.async_get_info()  # Public API ensures lazy storage is loaded.
    matches = [item for item in resources.async_items() if _owns_resource(item.get("url", ""))]
    if not matches:
        await resources.async_create_item({"url": url, "res_type": "module"})
        return
    first = matches[0]
    if first.get("url") != url or first.get("type") != "module":
        await resources.async_update_item(first["id"], {"url": url, "res_type": "module"})
    for duplicate in matches[1:]:
        await resources.async_delete_item(duplicate["id"])


def _register_dashboard(hass, lovelace, state):
    """Publish one integration-owned YAML dashboard; never replace a user's."""
    from homeassistant.components import frontend
    from homeassistant.components.lovelace.dashboard import LovelaceYAML

    dashboards = _lovelace_field(lovelace, "dashboards")
    if UI_PATH in dashboards or frontend.async_panel_exists(hass, UI_PATH):
        if state.get("dashboard") is None or dashboards.get(UI_PATH) is not state["dashboard"]:
            _LOGGER.warning(
                "Machine Monitor: /%s is already used; add the Machine Monitor card to an existing dashboard",
                UI_PATH,
            )
        return
    config = {
        "title": "Machine Monitor", "icon": "mdi:chart-timeline-variant",
        "show_in_sidebar": True, "require_admin": False, "mode": "yaml",
        "filename": str(Path(__file__).parent / "dashboard.yaml"),
    }
    dashboard = LovelaceYAML(hass, UI_PATH, config)
    dashboards[UI_PATH] = dashboard
    try:
        frontend.async_register_built_in_panel(
            hass, "lovelace", frontend_url_path=UI_PATH,
            sidebar_title=config["title"], sidebar_icon=config["icon"],
            config={"mode": "yaml"}, require_admin=False, show_in_sidebar=True,
        )
    except Exception:
        dashboards.pop(UI_PATH, None)
        raise
    state["dashboard"] = dashboard


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Serve, load and expose the UI once for all configured machines."""
    from homeassistant.components import frontend
    from homeassistant.components.lovelace.const import LOVELACE_DATA

    state = hass.data.setdefault(DOMAIN, {}).setdefault("frontend", {})
    card = Path(__file__).parent / "frontend" / CARD_FILENAME
    url = await hass.async_add_executor_job(_versioned_url, card)
    if not state.get("static_registered"):
        try:
            from homeassistant.components.http import StaticPathConfig
        except ImportError:  # Older cores use the synchronous registration API.
            hass.http.register_static_path(CARD_MOUNT, str(card.parent), False)
        else:
            await hass.http.async_register_static_paths(
                [StaticPathConfig(CARD_MOUNT, str(card.parent), False)]
            )
        state["static_registered"] = True

    lovelace = hass.data[LOVELACE_DATA]
    try:
        await _async_register_resource(_lovelace_field(lovelace, "resources"), url)
    except Exception:  # The module API still makes the UI usable if storage fails.
        _LOGGER.exception("Machine Monitor: Lovelace resource registration failed; using frontend module loading")
    if state.get("module_url") != url:
        if previous := state.get("module_url"):
            frontend.remove_extra_js_url(hass, previous)
        frontend.add_extra_js_url(hass, url)
        state["module_url"] = url
    _register_dashboard(hass, lovelace, state)
    if state.get("dashboard") is not None:
        _LOGGER.info("Machine Monitor UI: /%s; frontend module: %s", UI_PATH, url)
    else:
        _LOGGER.info("Machine Monitor card available in Add Card; frontend module: %s", url)
