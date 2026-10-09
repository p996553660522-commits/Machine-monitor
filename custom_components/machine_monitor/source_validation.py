"""Prevent monitoring our derived entities instead of physical sources."""
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


def own_source_entities(hass) -> list[str]:
    """Use registry ownership, never a name/prefix (MQTT may use our name)."""
    return [entry.entity_id for entry in er.async_get(hass).entities.values()
            if entry.platform == DOMAIN]


def is_own_source(hass, entity_id: str) -> bool:
    entry = er.async_get(hass).async_get(entity_id)
    return entry is not None and entry.platform == DOMAIN
