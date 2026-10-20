"""Exercise concurrent config-entry setup at real await boundaries."""
import asyncio
import importlib.util
from importlib.machinery import SourceFileLoader
import types
import unittest
from unittest.mock import patch

import test_machine_monitor as harness

spec = importlib.util.spec_from_loader("machine_monitor.integration", SourceFileLoader(
    "machine_monitor.integration", str(harness.ROOT / "__init__.py")), is_package=False)
integration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integration)


class MultiMachineSetupTests(unittest.IsolatedAsyncioTestCase):
    async def test_parallel_entries_share_one_coordinator_and_api_sees_both(self):
        hass = harness.Hass({})
        async def forward(*args):
            await asyncio.sleep(0)
        hass.config_entries = types.SimpleNamespace(async_forward_entry_setups=forward)
        instances = []
        class Coordinator:
            def __init__(self, hass):
                self.machines = {}
                self.data = None
                instances.append(self)
            async def async_refresh(self):
                await asyncio.sleep(0)  # HA refresh/executor yields during startup
            async def async_register_shutdown(self):
                await asyncio.sleep(0)
            async def async_profile_for(self, entry):
                await asyncio.sleep(0)
                return types.SimpleNamespace(name=entry.title, inputs={})
            async def async_add_machine(self, entry):
                await asyncio.sleep(0)
                runtime = types.SimpleNamespace(name=entry.title, machine_id=entry.entry_id)
                self.machines[entry.entry_id] = runtime
                return runtime
            async def async_request_refresh(self):
                await asyncio.sleep(0)
            def async_listen_input_names(self, entry):
                pass
            async def async_machine_summaries(self):
                return {key: {"machine_id": key, "name": value.name}
                        for key, value in self.machines.items()}
        def entry(key, title):
            return types.SimpleNamespace(entry_id=key, title=title,
                async_on_unload=lambda cb: None, add_update_listener=lambda cb: lambda: None)
        registry = types.SimpleNamespace(async_get_or_create=lambda **kw: None)
        with patch.object(harness.coordinator_mod, "MachineMonitorCoordinator", Coordinator), \
             patch.object(integration.dr, "async_get", return_value=registry, create=True):
            await asyncio.gather(integration.async_setup_entry(hass, entry("a", "Малярка")),
                                 integration.async_setup_entry(hass, entry("b", "Oree4")))
        self.assertEqual(len(instances), 1)
        shared = hass.data["machine_monitor"]["coordinator"]
        self.assertEqual(set(shared.machines), {"a", "b"})
        connection = harness.Connection()
        await harness.ws.ws_overview(hass, connection, {"id": 1})
        self.assertEqual({m["machine_id"] for m in connection.result["machines"]}, {"a", "b"})
        self.assertEqual(set(hass.data["machine_monitor"]["entries"]), {"a", "b"})
