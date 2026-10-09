"""Regression tests with minimal HA boundaries; no running HA is required.

Run: python -m unittest discover -s tests -v
The stubs exercise our code, not the full Home Assistant runtime.
"""
import asyncio
import copy
import importlib
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def module(name, **attrs):
    obj = types.ModuleType(name)
    obj.__dict__.update(attrs)
    sys.modules[name] = obj
    return obj

class Store:
    data = {}
    def __init__(self, hass, version, key, **kwargs):
        self.key = key
    def __class_getitem__(cls, item):
        return cls
    async def async_load(self):
        return copy.deepcopy(self.data.get(self.key))
    async def async_save(self, payload):
        self.data[self.key] = copy.deepcopy(payload)

class BaseFlow:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()
    def async_show_form(self, **kwargs):
        return kwargs
    def async_show_menu(self, **kwargs):
        return kwargs
    def async_create_entry(self, **kwargs):
        return kwargs

class Coordinator:
    def __class_getitem__(cls, item):
        return cls
    def __init__(self, hass, logger, **kwargs):
        self.hass = hass
        self.refreshes = 0
        self.options = kwargs
    async def async_request_refresh(self):
        self.refreshes += 1
        await self._async_update_data()

class Field:
    def __init__(self, key, **kwargs):
        self.key = key
        self.default = kwargs.get('default')
class Schema:
    def __init__(self, schema):
        self.schema = schema
    def __call__(self, value):
        return value
class Selector:
    def __init__(self, *args, **kwargs):
        pass

module('homeassistant')
module('homeassistant.core', HomeAssistant=object, Event=object, ServiceCall=object, callback=lambda f:f)
module('homeassistant.helpers')
module('homeassistant.util')
module('homeassistant.util.dt', as_local=lambda value:value)
module('homeassistant.helpers.storage', Store=Store)
module('homeassistant.helpers.event', async_track_state_change_event=lambda hass, ids, cb: hass.listen(ids, cb))
module('homeassistant.helpers.update_coordinator', DataUpdateCoordinator=Coordinator, CoordinatorEntity=Coordinator)
module('homeassistant.helpers.debounce', Debouncer=Selector)
module('homeassistant.config_entries', ConfigEntry=object, ConfigFlow=BaseFlow, OptionsFlow=BaseFlow)
module('homeassistant.const', EVENT_HOMEASSISTANT_STOP='stop', PERCENTAGE='%', UnitOfTime=types.SimpleNamespace(SECONDS='s', HOURS='h'))
module('homeassistant.helpers.typing', ConfigType=dict)
module('homeassistant.helpers.device_registry', DeviceEntry=object)
module('homeassistant.helpers.entity_registry', async_get=lambda hass:hass.entity_registry, EVENT_ENTITY_REGISTRY_UPDATED='entity_registry_updated')
module('homeassistant.helpers.entity_platform', AddEntitiesCallback=object)
module('homeassistant.helpers.selector', EntitySelector=Selector, EntitySelectorConfig=Selector, SelectSelector=Selector, SelectSelectorConfig=Selector, SelectSelectorMode=types.SimpleNamespace(DROPDOWN='dropdown',LIST='list'), TextSelector=Selector, IconSelector=Selector, ColorSelector=Selector)
module('homeassistant.components')
module('homeassistant.components.websocket_api', websocket_command=lambda schema:lambda f:f, async_response=lambda f:f, ActiveConnection=object)
module('homeassistant.components.sensor', SensorEntity=object, SensorEntityDescription=object, SensorDeviceClass=types.SimpleNamespace(TIMESTAMP='timestamp'), SensorStateClass=types.SimpleNamespace(MEASUREMENT='measurement',TOTAL_INCREASING='total_increasing'))
class BinaryEntity: pass
module('homeassistant.components.binary_sensor', BinarySensorEntity=BinaryEntity, BinarySensorDeviceClass=types.SimpleNamespace(PROBLEM='problem'))
module('voluptuous', Required=Field, Optional=Field, Schema=Schema, All=lambda *a: a, Coerce=lambda *a:a, Range=lambda **kw:kw)
package = module('machine_monitor')
package.__path__ = [str(ROOT)]
models = importlib.import_module('machine_monitor.models')
storage = importlib.import_module('machine_monitor.storage')
engine_mod = importlib.import_module('machine_monitor.event_engine')
machine = importlib.import_module('machine_monitor.machine')
stats_mod = importlib.import_module('machine_monitor.stats')
coordinator_mod = importlib.import_module('machine_monitor.coordinator')
ws = importlib.import_module('machine_monitor.websocket_api')
flow_mod = importlib.import_module('machine_monitor.config_flow')

T = datetime(2026, 10, 5, 8, tzinfo=timezone.utc)
class Clock(datetime):
    value = T
    @classmethod
    def now(cls, tz=None):
        return cls.value if tz is None else cls.value.astimezone(tz)

class Hass:
    def __init__(self, states):
        self.values = {k:types.SimpleNamespace(state=v) for k,v in states.items()}
        self.states = types.SimpleNamespace(get=self.values.get)
        self.events=[]
        self.listeners=[]
        self.tasks=[]
        self.data={}
        self.registry_entries={}
        self.entity_registry=types.SimpleNamespace(entities=self.registry_entries, async_get=self.registry_entries.get,
            async_update_entity=self.update_registry)
        self.registry_listeners=[]
        self.bus=types.SimpleNamespace(async_fire=lambda name,data:self.events.append((name,data)), async_listen=self.listen_bus)
    def listen_bus(self, event_type, cb):
        item=(event_type,cb);self.registry_listeners.append(item)
        return lambda:self.registry_listeners.remove(item)
    def update_registry(self, entity_id, **kwargs):
        old=self.registry_entries[entity_id]
        changes={k:getattr(old,k,None) for k,v in kwargs.items() if getattr(old,k,None)!=v}
        new=types.SimpleNamespace(**{**vars(old),**kwargs});self.registry_entries[entity_id]=new
        if changes:
            event=types.SimpleNamespace(data={'action':'update','entity_id':entity_id,'changes':changes})
            for event_type,cb in list(self.registry_listeners):cb(event)
        return new
    async def async_add_executor_job(self, fn, *args):
        return fn(*args)

    def listen(self, ids, callback):
        entry=(ids,callback)
        self.listeners.append(entry)
        return lambda:self.listeners.remove(entry)
    def async_create_task(self, coro, *args):
        task=asyncio.create_task(coro)
        self.tasks.append(task)
        return task

class Connection:
    def send_result(self, id, result): self.result=result
    def send_error(self, id, code, message): self.error=code

class RegressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        Store.data={}
        Clock.value=T
        self.patches=[patch.object(m, 'datetime', Clock) for m in (engine_mod, storage, machine, stats_mod, ws, coordinator_mod)]
        for p in self.patches:p.start()
        self.addCleanup(lambda:[p.stop() for p in self.patches])
        self.hass=Hass({'binary_sensor.a':'off','binary_sensor.b':'off'})
        self.profile=models.MachineProfile(machine_id='m', inputs={
            'input_1':models.InputConfig('binary_sensor.a', semantic_state='heating', priority=60),
            'input_2':models.InputConfig('binary_sensor.b', semantic_state='work', priority=100),
        })
        self.history=storage.HistoryStore(self.hass,'m')
        self.engine=engine_mod.EventEngine(self.hass,'m',self.profile,self.history)
        self.runtime=machine.MachineRuntime('m',self.profile,self.history,self.engine)
        await self.engine.async_start()
    def edge(self, entity, state, second, update=True):
        Clock.value=T+timedelta(seconds=second)
        obj=types.SimpleNamespace(state=state) if state is not None else None
        if update:
            if obj is None:self.hass.values.pop(entity,None)
            else:self.hass.values[entity]=obj
        event=types.SimpleNamespace(data={'entity_id':entity,'new_state':obj},time_fired=Clock.value)
        self.engine._async_on_state_change(event)
    def durations(self, slot):
        return [i.duration_seconds(Clock.value) for i in self.history.input_intervals(slot)]
    async def test_concurrency_priority_and_off_edge(self):
        self.edge('binary_sensor.a','on',10)
        self.edge('binary_sensor.b','on',20)
        self.assertEqual(self.engine.state,'work')
        self.assertEqual(self.durations('input_1'),[10])
        self.assertEqual(self.durations('input_2'),[0])
        self.edge('binary_sensor.a','off',30)
        self.assertEqual(self.durations('input_1'),[20])
        self.assertEqual(self.engine.state,'work')
        payload=self.runtime.dashboard_payload(T,T+timedelta(seconds=30))
        self.assertEqual([len(r['intervals']) for r in payload['input_timeline']['rows']],[1,1])
    async def test_on_unavailable_recover_on_offline_history_stats(self):
        self.edge('binary_sensor.b','on',10)
        self.edge('binary_sensor.b','unavailable',20)
        self.assertEqual(self.engine.state,'offline')
        self.assertIsNone(self.engine.async_snapshot().active_inputs['input_2'])
        self.edge('binary_sensor.b','on',40)
        self.edge('binary_sensor.b','off',50)
        self.assertEqual(self.durations('input_2'),[10,10])
        periods=self.runtime.offline_periods(T,Clock.value)
        self.assertEqual(periods[0]['duration'],20)
        st=self.runtime.stats(start=T,end=Clock.value)
        self.assertEqual((st.work_seconds,st.idle_seconds,st.offline_seconds),(20,10,20))
        self.assertEqual(st.work_percent,66.7)
        self.assertEqual(st.offline_percent,40)
        self.assertTrue(any(x['state']=='offline' for x in self.runtime.timeline(T,Clock.value)))
    async def test_off_unavailable_recover_off(self):
        self.edge('binary_sensor.a','unknown',10)
        self.edge('binary_sensor.a','off',20)
        self.assertEqual(self.history.input_intervals('input_1'),[])
        self.assertEqual(self.runtime.offline_periods(T,Clock.value)[0]['duration'],10)
    async def test_queued_events_do_not_reread_future_state(self):
        self.hass.values['binary_sensor.a']=types.SimpleNamespace(state='off')
        self.hass.values['binary_sensor.b']=types.SimpleNamespace(state='on')
        self.edge('binary_sensor.a','on',10,update=False)
        self.assertEqual(self.engine.state,'heating')
        self.edge('binary_sensor.a','off',20,update=False)
        self.edge('binary_sensor.b','on',30,update=False)
        self.assertEqual(self.durations('input_1'),[10])
        self.assertEqual(len(self.history.input_intervals('input_2')),1)
    async def test_one_entity_in_two_slots(self):
        profile=copy.deepcopy(self.profile)
        profile.inputs['input_2'].entity_id='binary_sensor.a'
        await self.runtime.async_apply_profile(profile)
        self.edge('binary_sensor.a','on',10)
        self.assertTrue(all(self.history.input_intervals(s)[-1].is_open for s in profile.inputs))
    async def test_same_semantic_winner_change_tracks_source(self):
        profile=copy.deepcopy(self.profile)
        profile.inputs['input_1'].semantic_state='work'
        await self.runtime.async_apply_profile(profile)
        self.edge('binary_sensor.a','on',10)
        since=self.engine.state_since
        self.edge('binary_sensor.b','on',20)
        self.assertEqual(self.engine.async_snapshot().source_input,'input_2')
        self.assertEqual(self.engine.state_since,since)
        self.assertEqual(self.history.intervals[-2].end,T+timedelta(seconds=20))
    async def test_profile_rebinding_updates_listener(self):
        self.edge('binary_sensor.a','on',10)
        profile=copy.deepcopy(self.profile)
        profile.inputs['input_1'].entity_id='binary_sensor.c'
        self.hass.values['binary_sensor.c']=types.SimpleNamespace(state='off')
        Clock.value=T+timedelta(seconds=20)
        await self.runtime.async_apply_profile(profile)
        self.assertEqual(len(self.hass.listeners),1)
        self.assertIn('binary_sensor.c',self.hass.listeners[0][0])
        self.assertEqual(self.durations('input_1'),[10])
        self.edge('binary_sensor.c','on',30)
        self.assertEqual(len(self.history.input_intervals('input_1')),2)
    async def test_disabled_input_does_not_affect_history_or_offline(self):
        profile=copy.deepcopy(self.profile)
        profile.inputs['input_1'].enabled=False
        await self.runtime.async_apply_profile(profile)
        self.edge('binary_sensor.a','on',10)
        self.edge('binary_sensor.a','unavailable',20)
        self.assertEqual(self.history.input_intervals('input_1'),[])
        self.assertEqual(self.engine.state,'idle')
    async def test_clean_restart_preserves_full_duration_and_gap(self):
        self.edge('binary_sensor.b','on',10)
        Clock.value=T+timedelta(hours=2)
        await self.engine.async_stop()
        end=Clock.value
        Clock.value+=timedelta(minutes=30)
        await self.engine.async_start()
        entries=self.history.input_intervals('input_2')
        self.assertEqual(entries[0].end,end)
        self.assertEqual(entries[1].start,Clock.value)
        self.assertEqual(entries[0].duration_seconds(),7190)
    async def test_crash_restart_closes_at_checkpoint(self):
        self.edge('binary_sensor.b','on',10)
        Clock.value=T+timedelta(hours=2)
        await self.engine.async_flush()
        end=Clock.value
        Clock.value+=timedelta(hours=1)
        restored=storage.HistoryStore(self.hass,'m')
        await restored.async_load()
        restored.async_repair_open_interval(Clock.value)
        restored.async_repair_open_input_intervals(Clock.value)
        self.assertEqual(restored.input_intervals('input_2')[-1].end,end)
        self.assertEqual(restored.intervals[-1].end,end)
    async def test_legacy_storage_preserved_without_invented_physical_history(self):
        Store.data['machine_monitor.old']={'intervals':[models.Interval(T,None,'work').to_dict()]}
        old=storage.HistoryStore(self.hass,'old')
        await old.async_load()
        old.async_repair_open_interval(T+timedelta(hours=1))
        self.assertEqual(len(old.intervals),1)
        self.assertEqual(old.intervals[0].end,T)
        self.assertEqual(old.input_intervals(),{})
    async def test_clear_history_resumes_observed_on(self):
        self.edge('binary_sensor.b','on',10)
        Clock.value=T+timedelta(seconds=20)
        await self.engine.async_flush()
        await self.engine.async_clear_history()
        self.assertEqual(self.history.input_intervals('input_2')[0].start,Clock.value)
        self.assertEqual(len(Store.data['machine_monitor.m']['intervals']),1)
    async def test_prune_preserves_open_and_crossing_intervals(self):
        self.edge('binary_sensor.b','on',10)
        cutoff=T+timedelta(seconds=20)
        self.history.async_prune(cutoff)
        self.assertTrue(self.history.input_intervals('input_2')[-1].is_open)
        self.edge('binary_sensor.b','off',30)
        self.history.async_prune(cutoff)
        self.assertEqual(self.durations('input_2'),[20])
    async def test_save_failure_remains_dirty_and_retry_succeeds(self):
        async def fail(payload):raise OSError('test failure')
        with patch.object(self.history._store,'async_save',fail):
            with self.assertLogs('machine_monitor.storage',level='ERROR'):
                self.assertFalse(await self.history.async_flush())
        self.assertTrue(self.history._dirty)
        await self.history.async_flush_if_dirty()
        self.assertFalse(self.history._dirty)
    async def test_changes_during_save_are_not_lost(self):
        save=self.history._store.async_save
        async def during(payload):
            self.edge('binary_sensor.b','on',10)
            await save(payload)
        with patch.object(self.history._store,'async_save',during):
            await self.history.async_flush()
        self.assertTrue(self.history._dirty)
        await self.history.async_flush_if_dirty()
        self.assertEqual(len(Store.data['machine_monitor.m']['input_intervals']['input_2']),1)
    async def test_coordinator_callback_schedules_coroutine(self):
        c=coordinator_mod.MachineMonitorCoordinator(self.hass)
        c.machines['m']=self.runtime
        self.engine.set_update_callback(c._schedule_refresh)
        self.hass.events.clear()
        self.edge('binary_sensor.a','on',10)
        await asyncio.gather(*self.hass.tasks)
        self.assertEqual(c.refreshes,1)
        self.assertEqual(len(self.hass.events),1)
    async def test_websocket_import_and_validation_empty_filter(self):
        c=coordinator_mod.MachineMonitorCoordinator(self.hass)
        c.machines['m']=self.runtime
        self.hass.data={'machine_monitor':{'coordinator':c}}
        self.edge('binary_sensor.b','on',10)
        conn=Connection()
        await ws.ws_timeline(self.hass,conn,{'id':1,'machine_id':'m','start':T.isoformat(),'end':Clock.value.isoformat(),'inputs':[]})
        self.assertEqual(conn.result['input_timeline']['rows'],[])
        for start,end in [('invalid',Clock.value.isoformat()),('2026-10-05T08:00:00',Clock.value.isoformat()),(Clock.value.isoformat(),T.isoformat())]:
            await ws.ws_timeline(self.hass,conn,{'id':1,'machine_id':'m','start':start,'end':end})
            self.assertEqual(conn.error,'invalid_range')
        await ws.ws_overview(self.hass,conn,{'id':2})
        self.assertEqual(conn.result['machines'][0]['machine_id'],'m')
    async def test_restart_gap_is_offline_and_never_work(self):
        self.edge('binary_sensor.b','on',10)
        Clock.value=T+timedelta(seconds=20)
        await self.engine.async_stop()
        Clock.value=T+timedelta(seconds=40)
        await self.engine.async_start()
        st=self.runtime.stats(start=T,end=Clock.value)
        self.assertEqual(st.work_seconds,10)
        self.assertEqual(st.offline_seconds,20)
        self.assertEqual(self.runtime.offline_periods(T,Clock.value)[0]['duration'],20)

    async def test_load_error_does_not_overwrite_history(self):
        before=copy.deepcopy(Store.data)
        async def fail():raise OSError('test read failure')
        with patch.object(self.history._store, 'async_load', fail):
            with self.assertLogs('machine_monitor.storage',level='ERROR'):
                with self.assertRaises(OSError):await self.history.async_load()
        self.assertEqual(Store.data,before)

    async def test_future_schema_refused_without_data_loss(self):
        Store.data['machine_monitor.future']={'history_schema_version':99,'intervals':[]}
        old=storage.HistoryStore(self.hass,'future')
        with self.assertRaises(ValueError):await old.async_load()
        self.assertEqual(Store.data['machine_monitor.future']['history_schema_version'],99)

    async def test_closed_physical_storage_roundtrip(self):
        self.edge('binary_sensor.a','on',10)
        self.edge('binary_sensor.b','on',20)
        self.edge('binary_sensor.a','off',30)
        await self.engine.async_flush()
        restored=storage.HistoryStore(self.hass,'m')
        await restored.async_load()
        self.assertEqual(restored.input_intervals('input_1')[0].duration_seconds(),20)
        self.assertTrue(restored.input_intervals('input_2')[0].is_open)
        self.assertEqual(Store.data['machine_monitor.m']['history_schema_version'],3)

    async def test_last_seen_persists_while_sources_offline(self):
        self.edge('binary_sensor.a','unavailable',10)
        self.edge('binary_sensor.b','unavailable',20)
        await self.engine.async_flush()
        seen=self.engine.last_seen
        Clock.value=T+timedelta(seconds=40)
        restored=engine_mod.EventEngine(self.hass,'m',self.profile,storage.HistoryStore(self.hass,'m'))
        await restored.async_start()
        self.assertEqual(restored.last_seen,seen)
        self.assertEqual(seen,T+timedelta(seconds=20))
        await restored.async_stop()

    async def test_invalid_binary_state_is_unknown_not_work(self):
        self.edge('binary_sensor.b','unexpected',10)
        self.assertEqual(self.engine.state,'offline')
        self.assertIsNone(self.runtime.snapshot().active_inputs['input_2'])
        self.assertEqual(self.history.input_intervals('input_2'),[])

    async def test_binary_entity_uses_updated_profile_source(self):
        mod=importlib.import_module('machine_monitor.binary_sensor')
        obj=object.__new__(mod.MachineInputBinarySensor)
        obj._machine_id='m'; obj._slot='input_1'; obj._entity_id='binary_sensor.a'
        obj.coordinator=types.SimpleNamespace(runtime_for=lambda id:self.runtime)
        obj.hass=self.hass
        profile=copy.deepcopy(self.profile)
        profile.inputs['input_1'].entity_id='binary_sensor.c'
        profile.inputs['input_1'].input_name='New input'
        self.hass.values['binary_sensor.c']=types.SimpleNamespace(state='on')
        self.hass.values['binary_sensor.a']=types.SimpleNamespace(state='unavailable')
        await self.runtime.async_apply_profile(profile)
        self.assertTrue(obj.available)
        self.assertTrue(obj.is_on)
        self.assertEqual(obj.name,'New input')
        self.assertEqual(obj.extra_state_attributes['source_entity'],'binary_sensor.c')

    async def test_profile_update_does_not_reload_stale_disk_after_save_failure(self):
        self.edge('binary_sensor.b','on',10)
        Clock.value=T+timedelta(seconds=20)
        profile=copy.deepcopy(self.profile)
        async def fail(payload):raise OSError('test write failure')
        with patch.object(self.history._store,'async_save',fail):
            with self.assertLogs('machine_monitor.storage',level='ERROR'):
                await self.runtime.async_apply_profile(profile)
        self.assertEqual(self.history.input_intervals('input_2')[0].duration_seconds(),10)
        self.assertEqual(len(self.history.input_intervals('input_2')),2)
        self.assertTrue(self.history._dirty)

    async def test_options_input_editor_persists_values(self):
        f=flow_mod.MachineMonitorOptionsFlow()
        f.hass=self.hass
        async def profile():return copy.deepcopy(self.profile)
        saved=[]
        async def save(p):saved.append(p)
        f._async_current_profile=profile
        f._async_save_profile=save
        await f.async_step_input_1({'input_name':'Heater','semantic_state':'heating','priority':72,'color':[1,2,3],'show_in_timeline':False,'include_in_statistics':False})
        cfg=saved[0].inputs['input_1']
        self.assertEqual((cfg.input_name,cfg.priority,cfg.color),('Heater',72,'#010203'))
        self.assertFalse(cfg.show_in_timeline)
        self.assertFalse(cfg.include_in_statistics)
        await f.async_step_machine({'row_order':'input_2, input_1, input_2, unknown'})
        self.assertEqual(saved[-1].row_order,['input_2','input_1'])

    async def test_startup_input4_on_through_websocket_and_frontend(self):
        import json, shutil, subprocess
        await self.engine.async_stop()
        self.hass.values={f'binary_sensor.raw{i}':types.SimpleNamespace(
            state='on' if i==4 else 'off', last_changed=T-timedelta(hours=1)) for i in range(1,5)}
        self.hass.states=types.SimpleNamespace(get=self.hass.values.get)
        self.profile=models.MachineProfile('startup', inputs={f'input_{i}':models.InputConfig(
            f'binary_sensor.raw{i}', input_name=f'Signal {i}', semantic_state='work') for i in range(1,5)})
        self.history=storage.HistoryStore(self.hass,'startup')
        self.engine=engine_mod.EventEngine(self.hass,'startup',self.profile,self.history)
        self.runtime=machine.MachineRuntime('startup',self.profile,self.history,self.engine)
        updates=[]; self.engine.set_update_callback(lambda:updates.append(True))
        await self.engine.async_start()
        self.assertEqual(self.history.input_intervals('input_4')[0].start,T)
        self.assertTrue(self.history.input_intervals('input_4')[0].is_open)
        self.assertEqual(self.engine.state,'work')
        self.assertEqual(updates,[True])
        self.assertEqual(Store.data['machine_monitor.startup']['input_intervals']['input_4'][0]['end'],None)
        self.hass.data['machine_monitor']={'coordinator':types.SimpleNamespace(runtime_for=lambda id:self.runtime)}
        Clock.value=T+timedelta(seconds=120)
        connection=Connection()
        await ws.ws_timeline(self.hass,connection,{'id':1,'machine_id':'startup','start':(T-timedelta(hours=1)).isoformat(),
            'end':(Clock.value-timedelta(milliseconds=125)).isoformat()})
        rows=connection.result['input_timeline']['rows']
        self.assertEqual([len(r['intervals']) for r in rows],[0,0,0,1])
        self.assertTrue(rows[3]['intervals'][0]['open'])
        self.assertEqual(rows[3]['intervals'][0]['duration'],119.9)
        # Actual WebSocket payload goes through the real card's active render path.
        node=shutil.which('node')
        if node is None:self.fail('Node required for end-to-end frontend verification')
        script="""const {setup,prepare,walk,flowBox}=require('./tests/frontend_harness.cjs');
        const fs=require('fs'),assert=require('assert/strict');const {card}=setup();prepare(card);
        card._selected='startup';card._machines=[{machine_id:'startup',name:'Test'}];
        card._detail=JSON.parse(fs.readFileSync(0,'utf8'));card._adoptVisibility(card._detail);
        card._dirty=true;card._render();
        const bars=walk(flowBox(card)).filter(n=>String(n.title).startsWith('Input:'));
        assert.equal(bars.length,1);assert.ok(bars[0].title.includes('Signal 4'));
        assert.ok(parseFloat(bars[0].style.width)>0);assert.ok(bars[0].title.includes('End: NOW'));
        """
        result=subprocess.run([node,'-e',script],input=json.dumps(connection.result),text=True,
                              cwd=ROOT,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    async def test_open_interval_clipped_to_now_and_earlier_window(self):
        self.edge('binary_sensor.b','on',10)
        Clock.value=T+timedelta(seconds=120)
        rows=self.runtime.input_timeline(T,T+timedelta(hours=1))['rows']
        self.assertEqual(datetime.fromisoformat(rows[1]['intervals'][0]['end']),Clock.value)
        self.assertEqual(rows[1]['intervals'][0]['duration'],110)
        past=self.runtime.input_timeline(T+timedelta(seconds=30),T+timedelta(seconds=60))['rows'][1]['intervals'][0]
        self.assertEqual((past['start'],past['end']),( (T+timedelta(seconds=30)).isoformat(),(T+timedelta(seconds=60)).isoformat()))
        self.assertEqual(past['duration'],30)

    async def test_on_without_events_for_hours_stays_online(self):
        self.edge('binary_sensor.b','on',10)
        since=self.engine.state_since
        for seconds in (61,120,3600,7200):
            Clock.value=T+timedelta(seconds=seconds)
            await self.engine.async_flush()
            self.assertEqual(self.engine.state,'work')
            self.assertTrue(self.runtime.snapshot().inputs_available)
            self.assertTrue(self.history.input_intervals('input_2')[0].is_open)
        self.assertEqual(self.engine.state_since,since)
        self.assertEqual(self.runtime.offline_periods(T,Clock.value),[])

    async def test_off_without_events_for_hours_stays_online(self):
        Clock.value=T+timedelta(hours=2)
        await self.engine.async_flush()
        self.assertEqual(self.engine.state,'idle')
        self.assertTrue(self.runtime.snapshot().inputs_available)
        self.assertFalse(self.runtime.snapshot().active_inputs['input_1'])
        self.assertEqual(self.runtime.offline_periods(T,Clock.value),[])

    async def test_diagnostics_exact_unavailable_source_and_raw_transitions(self):
        self.edge('binary_sensor.b','on',10)
        self.edge('binary_sensor.b','unknown',20)
        self.assertEqual(self.engine.state,'offline')
        first=self.engine.offline_reason()['sources'][0]
        self.assertEqual((first['slot'],first['entity_id'],first['ha_state'],first['physical_on']),
                         ('input_2','binary_sensor.b','unknown',None))
        events=len(self.hass.events)
        self.edge('binary_sensor.b','unavailable',30)
        self.assertEqual(len(self.hass.events),events+1)
        self.assertEqual(self.engine.offline_reason()['sources'][0]['ha_state'],'unavailable')
        self.edge('binary_sensor.b',None,40)
        self.assertIsNone(self.engine.source_diagnostics()[1]['ha_state'])
        self.assertEqual(self.engine.source_diagnostics()[1]['last_changed'],Clock.value.isoformat())
        self.edge('binary_sensor.b','on',50)
        self.assertIsNone(self.engine.offline_reason()['code'])
        self.assertEqual(self.durations('input_2'),[10,0])
        self.assertEqual(self.runtime.offline_periods(T,Clock.value)[0]['duration'],30)
        self.assertEqual(self.runtime.dashboard_payload(T,Clock.value)['source_diagnostics'][1]['ha_state'],'on')

    async def test_source_absent_at_start_then_confirmed_on(self):
        await self.engine.async_stop()
        self.hass.values.pop('binary_sensor.b')
        Clock.value=T+timedelta(seconds=10)
        await self.engine.async_start()
        self.assertEqual(self.engine.state,'offline')
        self.assertIsNone(self.engine.offline_reason()['sources'][0]['ha_state'])
        self.edge('binary_sensor.b','on',30)
        self.assertEqual(self.history.input_intervals('input_2')[0].start,Clock.value)
        self.assertEqual(self.runtime.offline_periods(T,Clock.value)[-1]['duration'],20)

    async def test_state_object_recreation_does_not_split_on(self):
        self.edge('binary_sensor.b','on',10)
        self.edge('binary_sensor.b','on',120)
        self.assertEqual(len(self.history.input_intervals('input_2')),1)
        self.assertEqual(self.engine.state,'work')

    async def test_restart_reconciles_on_after_crash_preserving_closed_history(self):
        self.edge('binary_sensor.a','on',10)
        self.edge('binary_sensor.a','off',20)
        self.edge('binary_sensor.b','on',30)
        Clock.value=T+timedelta(seconds=60)
        await self.engine.async_flush()
        Clock.value=T+timedelta(seconds=120)
        fresh=engine_mod.EventEngine(self.hass,'m',self.profile,storage.HistoryStore(self.hass,'m'))
        await fresh.async_start()
        self.assertEqual(fresh.history.input_intervals('input_1')[0].duration_seconds(),10)
        entries=fresh.history.input_intervals('input_2')
        self.assertEqual(entries[0].end,T+timedelta(seconds=60))
        self.assertEqual(entries[1].start,Clock.value)
        offline=[i for i in fresh.history.intervals if i.state=='offline']
        self.assertEqual((offline[0].start,offline[0].end),(T+timedelta(seconds=60),Clock.value))
        self.assertEqual(fresh.history.intervals[-1].start,Clock.value)
        self.assertTrue(entries[1].is_open)
        await fresh.async_stop()

    async def test_own_source_rejected_in_create_reconfigure_options(self):
        own='binary_sensor.renamed_diagnostic'
        self.hass.registry_entries[own]=types.SimpleNamespace(platform='machine_monitor',entity_id=own)
        user={f'input_{i}':own if i==4 else 'binary_sensor.a' for i in range(1,5)}
        flow=flow_mod.MachineMonitorConfigFlow();flow.hass=self.hass
        result=await flow.async_step_user(user)
        self.assertEqual(result['errors'],{'input_4':'own_entity'})
        flow._get_reconfigure_entry=lambda:types.SimpleNamespace(title='Test',data=user)
        result=await flow.async_step_reconfigure(user)
        self.assertEqual(result['errors'],{'input_4':'own_entity'})
        options=flow_mod.MachineMonitorOptionsFlow();options.hass=self.hass
        async def profile():return copy.deepcopy(self.profile)
        options._async_current_profile=profile
        async def save(p):self.fail('Invalid source must not be saved')
        options._async_save_profile=save
        result=await options.async_step_input_1({'entity_id':own})
        self.assertEqual(result['errors'],{'entity_id':'own_entity'})

    async def test_own_source_existing_profile_is_unknown_with_reason(self):
        self.hass.registry_entries['binary_sensor.b']=types.SimpleNamespace(platform='machine_monitor',entity_id='binary_sensor.b')
        self.hass.values['binary_sensor.b']=types.SimpleNamespace(state='on')
        await self.engine.async_stop()
        await self.engine.async_start()
        self.assertEqual(self.engine.state,'offline')
        self.assertIsNone(self.runtime.snapshot().active_inputs['input_2'])
        self.assertEqual(self.engine.offline_reason()['sources'][0]['source_error'],'own_entity')
        self.assertEqual(self.history.input_intervals('input_2'),[])

    async def test_profile_store_rejects_own_sources_without_overwriting(self):
        coordinator=coordinator_mod.MachineMonitorCoordinator(self.hass)
        await coordinator.async_update_profile('m',self.profile)
        before=copy.deepcopy(Store.data)
        invalid=copy.deepcopy(self.profile)
        invalid.inputs['input_1'].entity_id='binary_sensor.self'
        self.hass.registry_entries['binary_sensor.self']=types.SimpleNamespace(platform='machine_monitor',entity_id='binary_sensor.self')
        with self.assertRaises(ValueError):await coordinator.async_update_profile('m',invalid)
        self.assertEqual(Store.data,before)

    async def test_reconfigure_preserves_real_sources_and_semantics(self):
        coordinator=coordinator_mod.MachineMonitorCoordinator(self.hass)
        await coordinator.async_update_profile('m',self.profile)
        self.hass.data['machine_monitor']={'coordinator':coordinator}
        entry=types.SimpleNamespace(entry_id='m',title='Test',data={'input_1':'binary_sensor.a','input_2':'binary_sensor.b'})
        flow=flow_mod.MachineMonitorConfigFlow();flow.hass=self.hass
        flow._get_reconfigure_entry=lambda:entry
        flow.async_update_reload_and_abort=lambda entry,**kw:kw
        user={f'input_{i}':f'binary_sensor.mqtt_input{i}' for i in range(1,5)}
        # Reconfigure is normally four configured slots; retain their semantics.
        profile=copy.deepcopy(self.profile)
        profile.inputs.update({f'input_{i}':models.InputConfig('binary_sensor.old'+str(i)) for i in (3,4)})
        await coordinator.async_update_profile('m',profile)
        result=await flow.async_step_reconfigure(user)
        restored=await coordinator.async_profile_for(entry)
        self.assertEqual({slot:cfg.entity_id for slot,cfg in restored.inputs.items()},user)
        self.assertEqual({slot:result['data'][slot] for slot in user},user)
        self.assertEqual(restored.inputs['input_2'].semantic_state,'work')

    async def test_debug_logs_include_source_and_interval_edges(self):
        with self.assertLogs('machine_monitor.event_engine',level='DEBUG') as log:
            self.edge('binary_sensor.b','on',10)
            self.edge('binary_sensor.b','unavailable',20)
        output='\n'.join(log.output)
        for word in ('Machine m', 'input_2', 'binary_sensor.b', 'HA state=unavailable',
                     'physical interval opened','physical interval closed','offline_reason='):
            self.assertIn(word,output)

    async def test_original_mqtt_source_name_not_mistaken_for_own_entity(self):
        name='binary_sensor.machine_monitor_esp_input4'
        self.hass.registry_entries[name]=types.SimpleNamespace(platform='mqtt',entity_id=name)
        self.assertFalse(importlib.import_module('machine_monitor.source_validation').is_own_source(self.hass,name))

    async def test_source_ids_persist_after_profile_save_and_reload(self):
        coordinator=coordinator_mod.MachineMonitorCoordinator(self.hass)
        entry=types.SimpleNamespace(entry_id='m',title='Test',data={'input_1':'binary_sensor.a','input_2':'binary_sensor.b'})
        await coordinator.async_update_profile('m',self.profile)
        reloaded=await coordinator.async_profile_for(entry)
        self.assertEqual(reloaded.entity_ids(),self.profile.entity_ids())
        self.assertEqual(reloaded.inputs['input_2'].semantic_state,'work')

    def register_diagnostic_names(self, names):
        for i,name in enumerate(names,1):
            entity_id=f'binary_sensor.diagnostic_{i}'
            self.hass.registry_entries[entity_id]=types.SimpleNamespace(
                entity_id=entity_id,platform='machine_monitor',config_entry_id='m',unique_id=f'm_input_{i}',name=name)

    async def name_coordinator(self):
        profile=copy.deepcopy(self.profile)
        for i in (3,4):
            entity_id=f'binary_sensor.raw{i}'
            self.hass.values[entity_id]=types.SimpleNamespace(state='off')
            profile.inputs[f'input_{i}']=models.InputConfig(entity_id)
        await self.runtime.async_apply_profile(profile)
        self.profile=profile
        coordinator=coordinator_mod.MachineMonitorCoordinator(self.hass)
        coordinator.machines['m']=self.runtime
        self.hass.data['machine_monitor']={'coordinator':coordinator}
        entry=types.SimpleNamespace(entry_id='m',title='Test',data={slot:cfg.entity_id for slot,cfg in profile.inputs.items()})
        await coordinator.async_update_profile('m',profile)
        return coordinator,entry

    async def test_options_names_to_profile_reload_and_websocket_metadata(self):
        c,entry=await self.name_coordinator()
        self.assertEqual(self.runtime.profile.inputs['input_1'].display_name,'Input')
        options=flow_mod.MachineMonitorOptionsFlow(entry);options.hass=self.hass
        names=['Нагрев','Остывание','Поддержание','']
        for i,name in enumerate(names,1):
            await options._async_step_input(f'input_{i}',{'input_name':name})
        expected=names[:3]+['Input']
        self.assertEqual([cfg.display_name for cfg in self.runtime.profile.inputs.values()],expected)
        self.assertEqual([cfg.display_name for cfg in (await c.async_profile_for(entry)).inputs.values()],expected)
        await c.async_reload_machine_task(entry)
        runtime=c.runtime_for('m');Clock.value=T+timedelta(seconds=120)
        conn=Connection();await ws.ws_timeline(self.hass,conn,{'id':1,'machine_id':'m','start':T.isoformat(),'end':Clock.value.isoformat()})
        for field in ('inputs','source_diagnostics','input_summary'):
            self.assertEqual([row['name'] for row in conn.result[field]],expected)
        self.assertEqual([row['name'] for row in conn.result['input_timeline']['rows']],expected)
        await runtime.async_stop()

    async def test_legacy_ha_renames_imported_once_into_profile(self):
        c,entry=await self.name_coordinator()
        raw=Store.data['machine_monitor.profiles']['profiles']['m']
        raw.pop('input_names_profile_owned')
        self.register_diagnostic_names(['Нагрев','Остывание','Поддержание',None])
        restored=await c.async_profile_for(entry)
        self.assertEqual([cfg.display_name for cfg in restored.inputs.values()],['Нагрев','Остывание','Поддержание','Input'])
        persisted=Store.data['machine_monitor.profiles']['profiles']['m']
        self.assertTrue(persisted['input_names_profile_owned'])
        self.assertEqual(persisted['inputs']['input_1']['input_name'],'Нагрев')
        # A stale registry override cannot replace an already canonical profile.
        self.hass.registry_entries['binary_sensor.diagnostic_1'].name='Stale'
        c.machines.pop('m')  # Reload/startup reconciles the HA projection.
        restored=await c.async_profile_for(entry)
        self.assertEqual(restored.inputs['input_1'].display_name,'Нагрев')
        self.assertEqual(self.hass.registry_entries['binary_sensor.diagnostic_1'].name,'Нагрев')

    async def test_registry_rename_updates_profile_live_without_history_changes(self):
        c,entry=await self.name_coordinator()
        self.register_diagnostic_names(['Input']*4)
        unsubs=[];entry.async_on_unload=unsubs.append
        c.async_listen_input_names(entry)
        self.edge('binary_sensor.b','on',10)
        physical=self.history.input_intervals('input_2')[0]
        semantic=self.history.intervals[-1]
        self.engine.set_update_callback(c._schedule_refresh)
        for i,name in enumerate(['Нагрев','Остывание','Поддержание'],1):
            self.hass.update_registry(f'binary_sensor.diagnostic_{i}',name=name)
        # Drain rename tasks and coordinator update tasks scheduled by callbacks.
        for _ in range(4):
            await asyncio.gather(*self.hass.tasks)
        expected=['Нагрев','Остывание','Поддержание','Input']
        self.assertEqual([cfg.display_name for cfg in self.runtime.profile.inputs.values()],expected)
        self.assertIs(self.history.input_intervals('input_2')[0],physical)
        self.assertTrue(physical.is_open)
        self.assertIs(self.history.intervals[-1],semantic)
        self.assertTrue(semantic.is_open)
        self.assertEqual(len(self.history.input_intervals('input_2')),1)
        self.assertEqual(self.engine._inputs['input_2'].config.display_name,'Остывание')
        self.hass.update_registry('binary_sensor.diagnostic_1',name=None)
        for _ in range(4):await asyncio.gather(*self.hass.tasks)
        self.assertEqual(self.runtime.profile.inputs['input_1'].display_name,'Input')
        self.assertTrue(any(data.get('type')=='profile' for _,data in self.hass.events))
        unsubs[0]();self.assertEqual(self.hass.registry_listeners,[])

    async def test_profile_read_does_not_erase_pending_registry_rename(self):
        c,entry=await self.name_coordinator()
        self.register_diagnostic_names(['Input']*4)
        unsubs=[];entry.async_on_unload=unsubs.append;c.async_listen_input_names(entry)
        self.hass.update_registry('binary_sensor.diagnostic_1',name='Нагрев')
        # Options defaults may be read before the queued rename task obtains the lock.
        await c.async_profile_for(entry)
        for _ in range(4):await asyncio.gather(*self.hass.tasks)
        self.assertEqual(self.runtime.profile.inputs['input_1'].display_name,'Нагрев')
        self.assertEqual(self.hass.registry_entries['binary_sensor.diagnostic_1'].name,'Нагрев')
        unsubs[0]()

    async def test_profile_options_override_old_registry_mirror(self):
        c,entry=await self.name_coordinator()
        self.register_diagnostic_names(['Старое имя']*4)
        options=flow_mod.MachineMonitorOptionsFlow(entry);options.hass=self.hass
        await options.async_step_input_1({'input_name':'Нагрев'})
        self.assertEqual(self.runtime.profile.inputs['input_1'].display_name,'Нагрев')
        self.assertEqual(self.hass.registry_entries['binary_sensor.diagnostic_1'].name,'Нагрев')

    async def test_migration_preserves_explicit_profile_name(self):
        c,entry=await self.name_coordinator()
        raw=Store.data['machine_monitor.profiles']['profiles']['m']
        raw.pop('input_names_profile_owned')
        raw['inputs']['input_1']['input_name']='Профиль'
        self.register_diagnostic_names(['Старое имя',None,None,None])
        restored=await c.async_profile_for(entry)
        self.assertEqual(restored.inputs['input_1'].display_name,'Профиль')
        self.assertEqual(self.hass.registry_entries['binary_sensor.diagnostic_1'].name,'Профиль')

class PureTests(unittest.TestCase):
    def test_display_name_fallback_and_profile_roundtrip(self):
        for name in ('',None,'   '):
            cfg=models.InputConfig('binary_sensor.source',input_name=name)
            self.assertEqual(cfg.display_name,'Input')
            self.assertEqual(models.InputConfig.from_dict(cfg.to_dict()).display_name,'Input')
        profile=models.MachineProfile('m',inputs={'input_1':models.InputConfig('binary_sensor.source',input_name='Нагрев')})
        self.assertEqual(models.MachineProfile.from_dict(profile.to_dict()).inputs['input_1'].display_name,'Нагрев')

    def test_row_order_normalization_and_reload(self):
        order=['input_3','input_1','input_4','input_2']
        self.assertEqual(models.normalize_row_order(order),order)
        self.assertEqual(models.normalize_row_order(order+['unknown','input_1']),order)
        p=models.MachineProfile('m',inputs={s:models.InputConfig('binary_sensor.'+s) for s in order},row_order=order)
        self.assertEqual(models.MachineProfile.from_dict(p.to_dict()).row_order,order)
    def test_downtime_clipped_and_never_bridges_offline_gap(self):
        intervals=[models.Interval(T,T+timedelta(minutes=10),'idle'),models.Interval(T+timedelta(minutes=10),T+timedelta(minutes=10,seconds=1),'offline'),models.Interval(T+timedelta(minutes=10,seconds=1),T+timedelta(minutes=20),'idle')]
        info=stats_mod.analyse_downtime(intervals,T+timedelta(minutes=5),T+timedelta(minutes=15),states=['idle','offline'],threshold_minutes=0)
        self.assertEqual(info.count,2)
        self.assertEqual(info.total_seconds,599)
    def test_exclusion_per_input_does_not_remove_physical_history(self):
        end=T+timedelta(minutes=10)
        intervals=[models.Interval(T,end,'work',source_input='input_1')]
        st=stats_mod.compute_period_stats(intervals,T,end,include_inputs={'input_1':False})
        self.assertEqual((st.work_seconds,st.idle_seconds),(0,0))
        self.assertEqual(st.states,[])
        physical=stats_mod.input_statistics({'input_1':[models.Interval(T,end,'on')]},T,end)
        self.assertEqual(physical['input_1']['on_seconds'],600)
    def test_offline_cannot_be_used_as_an_online_signal_meaning(self):
        self.assertEqual(models.InputConfig('binary_sensor.a',semantic_state='offline').semantic_state,'other')
        self.assertEqual(models.MachineProfile('m',no_active_state='offline').no_active_state,'idle')

    def test_long_period(self):
        start,end=stats_mod.period_bounds(T,'30d')
        self.assertEqual((end-start).days,30)
    def test_imports_all_python_modules_with_ha_boundaries(self):
        for name in ('sensor','binary_sensor','config_flow','coordinator','websocket_api'):
            importlib.import_module('machine_monitor.'+name)
        from importlib.machinery import SourceFileLoader
        spec=importlib.util.spec_from_loader('machine_monitor.integration', SourceFileLoader('machine_monitor.integration', str(ROOT/'__init__.py')), is_package=False)
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

if __name__=='__main__':unittest.main()
