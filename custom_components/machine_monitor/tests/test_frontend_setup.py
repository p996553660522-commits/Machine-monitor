"""UI registration tests against explicit HA frontend/Lovelace boundaries."""
import copy
import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import test_machine_monitor as harness

ui = importlib.import_module("machine_monitor.frontend_setup")

class Resources:
    def __init__(self, items=None):
        self.items = copy.deepcopy(items or [])
        self.created = []
        self.updated = []
        self.deleted = []
        self.loaded = False
    async def async_get_info(self):
        self.loaded = True
        return {"resources": len(self.items)}
    def async_items(self):
        assert self.loaded
        return self.items
    async def async_create_item(self, data):
        self.created.append(data)
        item = {"id": str(len(self.items)+1), "url": data["url"], "type": data["res_type"]}
        self.items.append(item)
        return item
    async def async_update_item(self, id, updates):
        self.updated.append((id, updates))
        for item in self.items:
            if item["id"] == id:
                item.update(url=updates["url"], type=updates["res_type"])
    async def async_delete_item(self, id):
        self.deleted.append(id)
        self.items = [item for item in self.items if item["id"] != id]

class YAMLDashboard:
    def __init__(self, hass, path, config):
        self.config = config
        self.path = path
        self.filename = config["filename"]

class FrontendTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.panels = {}
        self.modules = set()
        self.static = []
        self.resources = Resources()
        self.lovelace = types.SimpleNamespace(resources=self.resources, dashboards={})
        self.hass = types.SimpleNamespace(data={"lovelace": self.lovelace})
        async def executor(fn, *args):return fn(*args)
        async def static_paths(paths):self.static.extend(paths)
        self.hass.async_add_executor_job = executor
        self.hass.http = types.SimpleNamespace(async_register_static_paths=static_paths)
        self.frontend = types.ModuleType("homeassistant.components.frontend")
        self.frontend.add_extra_js_url = lambda hass,url:self.modules.add(url)
        self.frontend.remove_extra_js_url = lambda hass,url:self.modules.remove(url)
        self.frontend.async_panel_exists = lambda hass,path:path in self.panels
        def register(hass, component, **kwargs):
            path = kwargs["frontend_url_path"]
            if path in self.panels:raise ValueError("duplicate panel")
            self.panels[path] = {"component":component, **kwargs}
        self.frontend.async_register_built_in_panel = register
        http = types.ModuleType("homeassistant.components.http")
        http.StaticPathConfig = lambda url,path,cache:types.SimpleNamespace(url=url,path=path,cache=cache)
        const = types.ModuleType("homeassistant.components.lovelace.const")
        const.LOVELACE_DATA = "lovelace"
        dashboard = types.ModuleType("homeassistant.components.lovelace.dashboard")
        dashboard.LovelaceYAML = YAMLDashboard
        self.patch = patch.dict(sys.modules, {
            "homeassistant.components.frontend":self.frontend,
            "homeassistant.components.http":http,
            "homeassistant.components.lovelace":types.ModuleType("homeassistant.components.lovelace"),
            "homeassistant.components.lovelace.const":const,
            "homeassistant.components.lovelace.dashboard":dashboard,
        })
        self.patch.start()
        self.addCleanup(self.patch.stop)

    async def test_module_static_resource_and_sidebar_registered(self):
        await ui.async_setup_frontend(self.hass)
        self.assertEqual(len(self.static),1)
        self.assertEqual(self.static[0].url,"/machine_monitor_static")
        self.assertFalse(self.static[0].cache)
        self.assertTrue((Path(self.static[0].path)/ui.CARD_FILENAME).is_file())
        url = next(iter(self.modules))
        self.assertTrue(url.startswith(ui.CARD_URL+"?v="))
        self.assertEqual(self.resources.items[0]["url"],url)
        self.assertEqual(self.resources.items[0]["type"],"module")
        panel = self.panels["machine-monitor"]
        self.assertEqual(panel["component"],"lovelace")
        self.assertTrue(panel["show_in_sidebar"])
        self.assertFalse(panel["require_admin"])
        self.assertEqual(self.lovelace.dashboards[ui.UI_PATH].filename,str(harness.ROOT/"dashboard.yaml"))

    async def test_repeated_setup_and_multiple_machines_are_idempotent(self):
        await ui.async_setup_frontend(self.hass)
        await ui.async_setup_frontend(self.hass)
        self.assertEqual(len(self.static),1)
        self.assertEqual(len(self.resources.created),1)
        self.assertEqual(self.resources.updated,[])
        self.assertEqual(len(self.modules),1)
        self.assertEqual(len(self.panels),1)

    async def test_existing_owned_resources_updated_and_deduplicated(self):
        unrelated = {"id":"other","url":"/other/card.js","type":"module"}
        self.resources.items = [
            {"id":"old","url":ui.CARD_URL,"type":"js"},
            {"id":"duplicate","url":ui.CARD_URL+"?v=old","type":"module"},unrelated,
        ]
        await ui.async_setup_frontend(self.hass)
        self.assertEqual(self.resources.updated[0][0],"old")
        self.assertEqual(self.resources.deleted,["duplicate"])
        self.assertIn(unrelated,self.resources.items)
        self.assertEqual(len(self.resources.items),2)

    async def test_yaml_resources_untouched_but_module_and_dashboard_available(self):
        original = [{"url":"/user.js","type":"module"}]
        self.lovelace.resources = types.SimpleNamespace(data=original)
        await ui.async_setup_frontend(self.hass)
        self.assertEqual(self.lovelace.resources.data,original)
        self.assertEqual(len(self.modules),1)
        self.assertIn(ui.UI_PATH,self.panels)

    async def test_old_dict_based_lovelace_data(self):
        self.hass.data["lovelace"] = {"resources":self.resources,"dashboards":{}}
        await ui.async_setup_frontend(self.hass)
        self.assertIn(ui.UI_PATH,self.hass.data["lovelace"]["dashboards"])

    async def test_resource_storage_failure_keeps_ui_available(self):
        async def fail(data):raise OSError("test storage failure")
        self.resources.async_create_item = fail
        with self.assertLogs("machine_monitor.frontend_setup",level="ERROR"):
            await ui.async_setup_frontend(self.hass)
        self.assertEqual(len(self.modules),1)
        self.assertIn(ui.UI_PATH,self.panels)

    async def test_existing_user_dashboard_is_preserved(self):
        user = object()
        self.lovelace.dashboards[ui.UI_PATH] = user
        self.panels[ui.UI_PATH] = {"user":True}
        with self.assertLogs("machine_monitor.frontend_setup",level="WARNING"):
            await ui.async_setup_frontend(self.hass)
        self.assertIs(self.lovelace.dashboards[ui.UI_PATH],user)
        self.assertEqual(self.panels[ui.UI_PATH],{"user":True})
        self.assertEqual(len(self.modules),1)

    async def test_panel_only_collision_is_preserved_and_reported(self):
        self.panels[ui.UI_PATH] = {"component":"user-panel"}
        with self.assertLogs("machine_monitor.frontend_setup",level="WARNING"):
            await ui.async_setup_frontend(self.hass)
        self.assertNotIn(ui.UI_PATH,self.lovelace.dashboards)
        self.assertEqual(self.panels[ui.UI_PATH],{"component":"user-panel"})

    async def test_integration_hook_registers_the_full_ui(self):
        from importlib.machinery import SourceFileLoader
        spec=importlib.util.spec_from_loader("machine_monitor.integration", SourceFileLoader("machine_monitor.integration", str(harness.ROOT/"__init__.py")), is_package=False)
        integration=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(integration)
        await integration._async_register_card(self.hass)
        self.assertIn(ui.UI_PATH,self.panels)
        self.assertEqual(len(self.modules),1)
        self.assertEqual(len(self.resources.items),1)

    async def test_content_change_updates_resource_without_manifest_bump(self):
        await ui.async_setup_frontend(self.hass)
        old = next(iter(self.modules))
        new = ui.CARD_URL+"?v=different"
        with patch.object(ui,"_versioned_url",return_value=new):
            await ui.async_setup_frontend(self.hass)
        self.assertNotIn(old,self.modules)
        self.assertEqual(self.modules,{new})
        self.assertEqual(self.resources.items[0]["url"],new)
        self.assertEqual(len(self.static),1)

    async def test_old_static_api_is_called_synchronously(self):
        del sys.modules["homeassistant.components.http"].StaticPathConfig
        self.hass.http = types.SimpleNamespace(register_static_path=lambda *args:self.static.append(args))
        await ui.async_setup_frontend(self.hass)
        self.assertEqual(len(self.static),1)
        self.assertEqual(self.static[0][0],ui.CARD_MOUNT)

    def test_hash_version_changes_with_bytes_and_not_for_same_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            card = Path(tmp)/"card.js"
            card.write_text("first")
            first = ui._versioned_url(card)
            self.assertEqual(first,ui._versioned_url(card))
            card.write_text("second")
            self.assertNotEqual(first,ui._versioned_url(card))

    def test_only_owned_local_resource_matches(self):
        self.assertTrue(ui._owns_resource(ui.CARD_URL+"?v=old"))
        for other in ("/other/card.js","https://example.com"+ui.CARD_URL,"//example.com"+ui.CARD_URL):
            self.assertFalse(ui._owns_resource(other))

    def test_manifest_dependencies_and_generic_dashboard(self):
        manifest = json.loads((harness.ROOT/"manifest.json").read_text())
        self.assertTrue({"http","frontend","lovelace","websocket_api"}.issubset(manifest["dependencies"]))
        config = (harness.ROOT/"dashboard.yaml").read_text()
        self.assertIn("custom:machine-monitor-card",config)
        self.assertNotIn("sensor.malarka",config)
        self.assertNotIn("mode: overview",config)
