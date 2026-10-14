"""Config and options flow for Machine Monitor.

The *user* step binds the physical inputs of an ESP32 node to Home Assistant
entities. It deliberately carries no business meaning.

The *options* flow maintains the machine profile: every input gets a name, a
description, an icon, a colour, a semantic state, a priority and the
statistics/timeline flags. This is the only place where the mapping from a
physical signal to a machine meaning is defined.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from uuid import uuid4
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    RETENTION_DAYS,
    CONF_COLOR,
    CONF_DESCRIPTION,
    CONF_DOWNTIME_THRESHOLD,
    CONF_ENABLED,
    CONF_ENTITY_ID,
    CONF_HISTORY_LIMIT,
    CONF_ICON,
    CONF_INCLUDE_IN_STATISTICS,
    CONF_INPUT_DESCRIPTION,
    CONF_INPUT_NAME,
    CONF_INPUTS,
    CONF_NAME,
    CONF_NO_ACTIVE_STATE,
    CONF_PRIORITY,
    CONF_ROW_ORDER,
    CONF_SEMANTIC_STATE,
    CONF_SHOW_IN_TIMELINE,
    DEFAULT_DOWNTIME_THRESHOLD,
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_INPUT_NAME,
    DEFAULT_NAME,
    DEFAULT_NO_ACTIVE_STATE,
    DOMAIN,
    INPUT_SLOTS,
    SEMANTIC_STATES,
    STATE_OTHER,
)
from .models import InputConfig, MachineProfile, normalize_row_order, normalize_color, validate_shifts, validate_mode_rules
from .source_validation import is_own_source, own_source_entities

_LOGGER = logging.getLogger(__name__)


def _binary_sensor_selector(hass=None) -> selector.EntitySelector:
    """Return a fresh entity selector limited to binary sensors."""
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain="binary_sensor",
                                      exclude_entities=own_source_entities(hass) if hass else [])
    )


def _binding_schema(name, sources, hass):
    """All physical slots are optional; preserve valid current selections."""
    return vol.Schema({
        vol.Optional(CONF_NAME, default=name): str,
        **{vol.Optional(slot, **({'default': sources[slot]} if sources.get(slot) else {})):
           _binary_sensor_selector(hass) for slot in INPUT_SLOTS},
    })


def _state_selector() -> selector.SelectSelector:
    """Return a selector for the semantic state of an input."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[state for state in SEMANTIC_STATES if state != "offline"],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _slot_schema(
    defaults: dict[str, Any] | None = None,
    *,
    require_entity: bool = False,
    hass=None,
) -> dict[Any, Any]:
    """Return the schema fields describing one physical input."""
    values = defaults or {}

    if require_entity:
        entity_field = vol.Required(
            CONF_ENTITY_ID, **({"default": values[CONF_ENTITY_ID]} if values.get(CONF_ENTITY_ID) else {})
        )
    else:
        entity_field = vol.Optional(
            CONF_ENTITY_ID, **({"default": values[CONF_ENTITY_ID]} if values.get(CONF_ENTITY_ID) else {})
        )

    priority_field = vol.Optional(CONF_PRIORITY)
    if values.get(CONF_PRIORITY) is not None:
        priority_field = vol.Optional(CONF_PRIORITY, default=values[CONF_PRIORITY])
    icon_field = vol.Optional(CONF_ICON)
    if values.get(CONF_ICON):
        icon_field = vol.Optional(CONF_ICON, default=values[CONF_ICON])
    color_field = vol.Optional(CONF_COLOR)
    color = normalize_color(values.get(CONF_COLOR))
    if isinstance(color, str) and len(color) == 7 and color.startswith("#"):
        try:
            rgb = [int(color[i:i+2], 16) for i in (1, 3, 5)]
            color_field = vol.Optional(CONF_COLOR, default=rgb)
        except ValueError:
            pass
    return {
        entity_field: _binary_sensor_selector(hass),
        vol.Optional(
            CONF_INPUT_NAME,
            default=values.get(CONF_INPUT_NAME, DEFAULT_INPUT_NAME),
        ): str,
        vol.Optional(
            CONF_INPUT_DESCRIPTION,
            default=values.get(CONF_INPUT_DESCRIPTION, ""),
        ): str,
        vol.Optional(
            CONF_SEMANTIC_STATE,
            default=values.get(CONF_SEMANTIC_STATE, STATE_OTHER),
        ): _state_selector(),
        vol.Optional("accounting", default=values.get("accounting", "auto")): selector.SelectSelector(
            selector.SelectSelectorConfig(options=["auto", "productive", "non_productive", "excluded"],
                                          mode=selector.SelectSelectorMode.DROPDOWN,
                                          translation_key="accounting")),
        priority_field: vol.Coerce(int),
        icon_field: selector.IconSelector(),
        color_field: selector.ColorRGBSelector(),
        vol.Optional(CONF_ENABLED, default=values.get(CONF_ENABLED, True)): bool,
        vol.Optional(
            CONF_SHOW_IN_TIMELINE,
            default=values.get(CONF_SHOW_IN_TIMELINE, True),
        ): bool,
        vol.Optional(
            CONF_INCLUDE_IN_STATISTICS,
            default=values.get(CONF_INCLUDE_IN_STATISTICS, True),
        ): bool,
    }


def _profile_defaults(profile: MachineProfile) -> dict[str, Any]:
    """Build the default values for the profile editor."""
    return {
        CONF_DESCRIPTION: profile.description,
        CONF_ENABLED: profile.enabled,
        CONF_NO_ACTIVE_STATE: profile.no_active_state,
        CONF_DOWNTIME_THRESHOLD: profile.downtime_threshold,
        "retention_days": profile.retention_days,
        "shifts": "\n".join(f"{s['name']} | {s['start']} | {s['end']}" for s in profile.shifts),
        CONF_ROW_ORDER: (
            list(profile.row_order) if profile.row_order else list(INPUT_SLOTS)
        ),
        CONF_INPUTS: {
            slot: cfg.to_dict() for slot, cfg in sorted(profile.inputs.items())
        },
    }


def _row_order_selector() -> selector.TextSelector:
    """An ordered comma-separated list; a multi-select cannot reorder rows."""
    return selector.TextSelector()


def _profile_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the profile editor schema."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_DESCRIPTION, default=defaults.get(CONF_DESCRIPTION, "")
            ): str,
            vol.Optional(
                CONF_ENABLED, default=defaults.get(CONF_ENABLED, True)
            ): bool,
            vol.Optional(
                CONF_NO_ACTIVE_STATE,
                default=defaults.get(
                    CONF_NO_ACTIVE_STATE, DEFAULT_NO_ACTIVE_STATE
                ),
            ): _state_selector(),
            vol.Optional(
                CONF_DOWNTIME_THRESHOLD,
                default=defaults.get(
                    CONF_DOWNTIME_THRESHOLD, DEFAULT_DOWNTIME_THRESHOLD
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
            vol.Optional("retention_days", default=str(defaults.get("retention_days", 30))): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[{"value": str(d), "label": f"{d} days"} for d in RETENTION_DAYS],
                                              mode=selector.SelectSelectorMode.DROPDOWN)),
            vol.Optional("shifts", default=defaults.get("shifts", "")): selector.TextSelector({"multiline": True}),
            vol.Optional(
                CONF_ROW_ORDER,
                default=", ".join(defaults.get(CONF_ROW_ORDER) or INPUT_SLOTS),
            ): _row_order_selector(),
        }
    )


def _default_profile(entry: config_entries.ConfigEntry) -> MachineProfile:
    """Build a profile straight from the config entry data."""
    inputs: dict[str, InputConfig] = {}
    for slot in INPUT_SLOTS:
        entity_id = entry.data.get(slot)
        if entity_id:
            inputs[slot] = InputConfig(entity_id=entity_id)
    return MachineProfile(
        machine_id=entry.entry_id,
        name=entry.title,
        inputs=inputs,
    )


class MachineMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the creation of a Machine Monitor machine."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Bind the physical inputs of one ESP32 node to entities."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entity_ids = [user_input.get(slot) for slot in INPUT_SLOTS]
            if not any(entity_ids):
                errors["base"] = "entity_required"
            for slot, entity_id in zip(INPUT_SLOTS, entity_ids):
                if entity_id and is_own_source(self.hass, entity_id):
                    errors[slot] = "own_entity"
            if not errors:
                await self.async_set_unique_id(
                    "machine:" + "|".join(sorted(e for e in entity_ids if e))
                )
                self._abort_if_unique_id_configured()
                name = (user_input.get(CONF_NAME) or "").strip() or DEFAULT_NAME
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_NAME: name,
                        **{
                            slot: user_input[slot]
                            for slot in INPUT_SLOTS if user_input.get(slot)
                        },
                    },
                    options={
                        CONF_INPUTS: {
                            slot: {
                                CONF_ENTITY_ID: user_input[slot],
                                CONF_INPUT_NAME: DEFAULT_INPUT_NAME,
                                CONF_INPUT_DESCRIPTION: "",
                                CONF_SEMANTIC_STATE: STATE_OTHER,
                                CONF_ENABLED: True,
                                CONF_SHOW_IN_TIMELINE: True,
                                CONF_INCLUDE_IN_STATISTICS: True,
                                CONF_PRIORITY: None,
                            }
                            for slot in INPUT_SLOTS if user_input.get(slot)
                        },
                    },
                )

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                **{
                    vol.Optional(slot): _binary_sensor_selector(self.hass)
                    for slot in INPUT_SLOTS
                },
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Allow rebinding the source entities of an existing machine."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            if not any(user_input.get(slot) for slot in INPUT_SLOTS):
                errors["base"] = "entity_required"
            for slot in INPUT_SLOTS:
                if user_input.get(slot) and is_own_source(self.hass, user_input[slot]):
                    errors[slot] = "own_entity"
            if errors:
                schema = _binding_schema(entry.title, user_input, self.hass)
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=schema,
                    errors=errors,
                    description_placeholders={"name": entry.title},
                )

            data = dict(entry.data)
            data.update({slot: user_input.get(slot, "") for slot in INPUT_SLOTS})
            data[CONF_NAME] = (
                (user_input.get(CONF_NAME) or "").strip() or entry.title
            )
            coordinator = self.hass.data.get(DOMAIN, {}).get("coordinator")
            if coordinator is not None:
                profile = await coordinator.async_profile_for(entry)
                for slot in INPUT_SLOTS:
                    entity_id = user_input.get(slot)
                    if entity_id:
                        cfg = profile.inputs.get(slot) or InputConfig(entity_id=entity_id)
                        cfg.entity_id = entity_id
                        profile.inputs[slot] = cfg
                    else:
                        profile.inputs.pop(slot, None)
                profile.row_order = normalize_row_order(profile.row_order, profile.inputs)
                profile.name = data[CONF_NAME]
                await coordinator.async_update_profile(entry.entry_id, profile)
            if hasattr(self, "async_update_reload_and_abort"):
                return self.async_update_reload_and_abort(
                    entry,
                    data=data,
                    title=data[CONF_NAME],
                )
            # Fallback for cores without async_update_reload_and_abort.
            self.hass.config_entries.async_update_entry(
                entry, data=data, title=data[CONF_NAME]
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(entry.entry_id)
            )
            return self.async_abort(reason="reconfigure_successful")

        sources = dict(entry.data)
        coordinator = self.hass.data.get(DOMAIN, {}).get("coordinator")
        if coordinator is not None:
            profile = await coordinator.async_profile_for(entry)
            sources = {slot: cfg.entity_id for slot, cfg in profile.inputs.items()}
        schema = _binding_schema(entry.title, sources, self.hass)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MachineMonitorOptionsFlow:
        """Return the options flow."""
        return MachineMonitorOptionsFlow(config_entry)


class MachineMonitorOptionsFlow(config_entries.OptionsFlow):
    """Edit the profile of one machine."""

    def __init__(
        self,
        config_entry: config_entries.ConfigEntry | None = None,
    ) -> None:
        """Initialise the options flow.

        On cores before 2024.11 the entry has to be handed over by the
        factory, on newer cores it is assigned by Home Assistant after the
        factory returned. Both paths are supported.
        """
        if config_entry is not None:
            try:
                self.config_entry = config_entry
            except AttributeError:  # pragma: no cover - very old cores
                self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """HA forms support scalar selectors, so edit each input separately."""
        profile = await self._async_current_profile()
        return self.async_show_menu(
            step_id="init", menu_options=["machine", "rules", *INPUT_SLOTS],
            description_placeholders={"name": profile.name},
        )

    async def async_step_rules(self, user_input=None):
        """Graphical editor: one mode, with an OR of AND groups."""
        profile = await self._async_current_profile()
        errors = {}
        if user_input is not None:
            selected = user_input.get("mode", "new")
            existing = next((r for r in profile.rules if r["id"] == selected), None)
            if selected != "new" and existing is None:
                errors["base"] = "invalid_rule"
            elif user_input.get("delete", False) and existing:
                profile.rules = [r for r in profile.rules if r["id"] != selected]
                await self._async_save_profile(profile)
                return self.async_create_entry(data={})
            elif len(profile.rules) >= 32 and existing is None:
                errors["base"] = "invalid_rule"
            else:
                self._draft_rule = deepcopy(existing) if existing else {
                    "id": "mode_" + uuid4().hex[:12], "name": "", "state": STATE_OTHER,
                    "priority": 100, "enabled": True, "accounting": "auto", "conditions": []}
                return await self.async_step_mode()
        choices = [{"value":"new","label":"+"}] + [{"value":r["id"],"label":r["name"]} for r in profile.rules]
        return self.async_show_form(step_id="rules", errors=errors, data_schema=vol.Schema({
            vol.Required("mode", default="new"): selector.SelectSelector(selector.SelectSelectorConfig(options=choices, mode=selector.SelectSelectorMode.DROPDOWN)),
            vol.Optional("delete", default=False): bool,
        }), description_placeholders={"name": profile.name})

    async def async_step_mode(self, user_input=None):
        errors = {}
        if user_input is not None:
            values = {**self._draft_rule, **user_input}
            if not str(values.get("name", "")).strip():
                errors["base"] = "invalid_rule"
            else:
                self._draft_rule = values
                self._group_index = 0
                self._edited_groups = []
                return await self.async_step_conditions()
        rule = self._draft_rule
        return self.async_show_form(step_id="mode", errors=errors, data_schema=vol.Schema({
            vol.Required("name", default=rule["name"]): str,
            vol.Required("state", default=rule["state"]): _state_selector(),
            vol.Optional("priority", default=rule["priority"]): vol.Coerce(int),
            vol.Optional("enabled", default=rule["enabled"]): bool,
            vol.Optional("accounting", default=rule["accounting"]): selector.SelectSelector(selector.SelectSelectorConfig(
                options=["auto","productive","non_productive","excluded"], translation_key="accounting", mode=selector.SelectSelectorMode.DROPDOWN)),
        }))

    async def async_step_conditions(self, user_input=None):
        profile = await self._async_current_profile()
        errors = {}
        if user_input is not None:
            group = [{"input":slot,"state":user_input[slot]} for slot in profile.inputs if user_input.get(slot) in ("on","off")]
            if not group or self._group_index >= 16:
                errors["base"] = "invalid_rule"
            else:
                self._edited_groups.append(group)
                self._group_index += 1
                if user_input.get("another_group", False) and self._group_index < 16:
                    return await self.async_step_conditions()
                # Finishing replaces old groups, allowing an operator to remove them.
                rule = {**self._draft_rule, "conditions": self._edited_groups}
                try:
                    rules = [r for r in profile.rules if r["id"] != rule["id"]] + [rule]
                    profile.rules = validate_mode_rules(rules)
                except (ValueError, TypeError, KeyError):
                    errors["base"] = "invalid_rule"
                else:
                    await self._async_save_profile(profile)
                    return self.async_create_entry(data={})
        original = self._draft_rule["conditions"]
        defaults = {term["input"]:term["state"] for term in original[self._group_index]} if self._group_index < len(original) else {}
        fields = {vol.Optional(slot, default=defaults.get(slot,"ignore")): selector.SelectSelector(
            selector.SelectSelectorConfig(options=["ignore","on","off"], translation_key="condition_state", mode=selector.SelectSelectorMode.DROPDOWN)) for slot in profile.inputs}
        fields[vol.Optional("another_group", default=self._group_index + 1 < len(original))] = bool
        return self.async_show_form(step_id="conditions", errors=errors, data_schema=vol.Schema(fields),
                                    description_placeholders={"mode":self._draft_rule["name"],"group":str(self._group_index+1),
                                        "inputs": "; ".join(f"{slot}: {cfg.display_name}" for slot, cfg in profile.inputs.items())})

    async def async_step_machine(self, user_input=None):
        profile = await self._async_current_profile()
        errors = {}
        if user_input is not None:
            try:
                lines = user_input.get("shifts")
                if lines is not None:
                    parsed = []
                    for line in lines.splitlines():
                        if not line.strip():
                            continue
                        name, start, end = [part.strip() for part in line.split("|")]
                        parsed.append({"name": name, "start": start, "end": end})
                    profile.shifts = validate_shifts(parsed)
                days = int(user_input.get("retention_days", profile.retention_days))
                if days not in RETENTION_DAYS:
                    raise ValueError("Invalid retention")
                profile.retention_days = days
            except (ValueError, KeyError, TypeError):
                errors["base"] = "invalid_history_settings"
        if user_input is not None and not errors:
            profile.description = user_input.get(CONF_DESCRIPTION, profile.description)
            profile.enabled = user_input.get(CONF_ENABLED, profile.enabled)
            profile.no_active_state = user_input.get(CONF_NO_ACTIVE_STATE, profile.no_active_state)
            profile.downtime_threshold = int(user_input.get(CONF_DOWNTIME_THRESHOLD, profile.downtime_threshold))
            profile.history_limit = int(user_input.get(CONF_HISTORY_LIMIT, profile.history_limit))
            profile.row_order = normalize_row_order(user_input.get(CONF_ROW_ORDER, profile.row_order), profile.inputs)
            await self._async_save_profile(profile)
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="machine", data_schema=_profile_schema(_profile_defaults(profile)), errors=errors,
            description_placeholders={"name": profile.name},
        )

    async def _async_step_input(self, slot, user_input=None):
        profile = await self._async_current_profile()
        cfg = profile.input_for(slot) or InputConfig(entity_id="")
        errors = {}
        if user_input is not None:
            entity_id = user_input.get(CONF_ENTITY_ID, cfg.entity_id)
            if not entity_id:
                errors[CONF_ENTITY_ID] = "entity_required"
            elif is_own_source(self.hass, entity_id):
                errors[CONF_ENTITY_ID] = "own_entity"
        if user_input is not None and not errors:
            values = cfg.to_dict()
            values.update(user_input)
            profile.inputs[slot] = InputConfig.from_dict(values)
            await self._async_save_profile(profile)
            return self.async_create_entry(data={})
        # Optional selector fields must not have invalid None defaults.
        values = cfg.to_dict()
        if user_input:
            values.update(user_input)
        schema = _slot_schema(values, require_entity=True, hass=self.hass)
        return self.async_show_form(
            step_id=slot, data_schema=vol.Schema(schema), errors=errors,
            description_placeholders={"slot": slot, "machine": profile.name, "state": cfg.semantic_state},
        )

    async def async_step_input_1(self, user_input=None):
        return await self._async_step_input("input_1", user_input)

    async def async_step_input_2(self, user_input=None):
        return await self._async_step_input("input_2", user_input)

    async def async_step_input_3(self, user_input=None):
        return await self._async_step_input("input_3", user_input)

    async def async_step_input_4(self, user_input=None):
        return await self._async_step_input("input_4", user_input)

    async def _async_current_profile(self) -> MachineProfile:
        """Return the live profile of the configured machine."""
        coordinator = self.hass.data.get(DOMAIN, {}).get("coordinator")
        if coordinator is not None:
            return await coordinator.async_profile_for(self.config_entry)
        return _default_profile(self.config_entry)

    async def _async_save_profile(self, profile: MachineProfile) -> None:
        """Persist the profile and apply it to the running machine."""
        coordinator = self.hass.data.get(DOMAIN, {}).get("coordinator")
        if coordinator is None:
            _LOGGER.warning(
                "Machine Monitor: coordinator unavailable, profile not saved"
            )
            raise RuntimeError("Machine Monitor coordinator unavailable; profile was not saved")
        await coordinator.async_update_profile(profile.machine_id, profile)
