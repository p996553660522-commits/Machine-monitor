"""1.4 profile accounting, mode conditions, historical compatibility and forms."""
import copy, types
from datetime import timedelta
import test_machine_monitor as h

import unittest
class V14Tests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=h.RegressionTests.asyncSetUp
    edge=h.RegressionTests.edge

    async def test_accounting_change_applies_only_future_without_splitting_physical_on(self):
        self.edge('binary_sensor.a','on',10)
        physical=self.history.input_intervals('input_1')[0]
        profile=copy.deepcopy(self.runtime.profile)
        profile.inputs['input_1'].accounting='productive'
        h.Clock.value=h.T+timedelta(seconds=20)
        await self.runtime.async_apply_profile(profile)
        self.assertIs(self.history.input_intervals('input_1')[0],physical)
        self.assertTrue(physical.is_open)
        self.edge('binary_sensor.a','off',30)
        h.Clock.value=h.T+timedelta(seconds=40)
        stats=self.runtime.stats(start=h.T,end=h.Clock.value)
        self.assertEqual((stats.work_seconds,stats.idle_seconds),(10,30))
        self.assertEqual([iv.accounting for iv in self.history.intervals],['non_productive','non_productive','productive','non_productive'])
        self.edge('binary_sensor.b','unavailable',40)
        h.Clock.value=h.T+timedelta(seconds=50)
        stats=self.runtime.stats(start=h.T,end=h.Clock.value)
        self.assertEqual((stats.work_seconds,stats.offline_seconds),(10,10))
        await self.engine.async_stop();await self.engine.async_start()
        self.assertEqual(self.runtime.stats(start=h.T,end=h.Clock.value).work_seconds,10)

    async def test_excluded_named_mode_remains_in_events_but_not_denominator(self):
        profile=copy.deepcopy(self.runtime.profile)
        profile.inputs['input_1'].input_name='Vent'
        profile.inputs['input_1'].accounting='excluded'
        await self.runtime.async_apply_profile(profile)
        self.edge('binary_sensor.a','on',10)
        h.Clock.value=h.T+timedelta(seconds=30)
        data=self.runtime.dashboard_payload(h.T,h.Clock.value)
        self.assertEqual(data['snapshot']['custom_label'],'Vent')
        self.assertEqual(data['events'][0]['custom_label'],'Vent')
        self.assertEqual(data['stats']['monitored_seconds'],10)
        self.assertEqual(data['input_timeline']['rows'][0]['on_seconds'],20)

    async def test_legacy_schema_three_pins_old_category_despite_new_profile_rule(self):
        await self.engine.async_stop()
        h.Store.data['machine_monitor.m']={'history_schema_version':3,'observed_at':(h.T+timedelta(seconds=10)).isoformat(),
            'intervals':[h.models.Interval(h.T,h.T+timedelta(seconds=10),'heating','input_1').to_dict()], 'input_intervals':{}}
        self.profile.inputs['input_1'].accounting='productive'
        self.hass.values['binary_sensor.a']=types.SimpleNamespace(state='on')
        h.Clock.value=h.T+timedelta(seconds=20)
        await self.engine.async_start()
        h.Clock.value=h.T+timedelta(seconds=30)
        stats=self.runtime.stats(start=h.T,end=h.Clock.value)
        self.assertEqual((stats.work_seconds,stats.idle_seconds,stats.offline_seconds),(10,10,10))
        self.assertEqual(self.history.intervals[0].accounting,'non_productive')

    async def test_rules_and_or_fan_heaters_priority_and_offline(self):
        profile=copy.deepcopy(self.runtime.profile)
        profile.inputs['input_3']=h.models.InputConfig('binary_sensor.fan')
        self.hass.values['binary_sensor.fan']=types.SimpleNamespace(state='off')
        def rule(ident,name,state,groups,priority=100):
            return {'id':ident,'name':name,'state':state,'accounting':'productive','priority':priority,
                    'enabled':True,'conditions':[[{'input':slot,'state':value} for slot,value in group] for group in groups]}
        profile.rules=[rule('heat','Нагрев','heating',[[('input_1','on'),('input_2','on')]]),
            rule('hold','Поддержание','technical',[[('input_1','on'),('input_2','off')],[('input_1','off'),('input_2','on')]]),
            rule('cool','Остывание','cooling',[[('input_1','off'),('input_2','off'),('input_3','on')]])]
        profile=h.models.MachineProfile.from_dict(profile.to_dict())
        await self.runtime.async_apply_profile(profile)
        self.edge('binary_sensor.fan','on',1)
        self.assertEqual(self.engine.async_snapshot().custom_label,'Остывание')
        self.edge('binary_sensor.a','on',2)
        self.assertEqual(self.engine.async_snapshot().custom_label,'Поддержание')
        self.edge('binary_sensor.b','on',3)
        self.assertEqual(self.engine.async_snapshot().custom_label,'Нагрев')
        self.assertTrue(all(self.history.input_intervals(slot)[-1].is_open for slot in profile.inputs))
        self.edge('binary_sensor.a','off',4)
        self.assertEqual(self.engine.async_snapshot().custom_label,'Поддержание')
        self.edge('binary_sensor.b','off',5)
        self.assertEqual(self.engine.async_snapshot().custom_label,'Остывание')
        self.edge('binary_sensor.fan','off',6)
        self.assertEqual(self.engine.state,'idle')
        self.edge('binary_sensor.a','unavailable',7)
        self.assertEqual(self.engine.state,'offline')
        self.assertIsNone(self.engine.async_snapshot().custom_label)

    async def test_rule_editor_saves_or_groups_and_all_input_forms_open(self):
        coordinator=h.coordinator_mod.MachineMonitorCoordinator(self.hass)
        coordinator.machines['m']=self.runtime
        await coordinator.async_update_profile('m',self.profile)
        self.hass.data['machine_monitor']={'coordinator':coordinator}
        entry=types.SimpleNamespace(entry_id='m',title='Machine',data={})
        flow=h.flow_mod.MachineMonitorOptionsFlow(entry);flow.hass=self.hass
        await flow.async_step_rules({'mode':'new'})
        await flow.async_step_mode({'name':'Laser emission','state':'work','accounting':'productive','priority':500,'enabled':True})
        await flow.async_step_conditions({'input_1':'on','input_2':'off','another_group':True})
        await flow.async_step_conditions({'input_1':'off','input_2':'on','another_group':False})
        profile=await coordinator.async_profile_for(entry)
        self.assertEqual(len(profile.rules[0]['conditions']),2)
        self.assertEqual(profile.rules[0]['name'],'Laser emission')
        for slot in profile.inputs:
            form=await getattr(flow,'async_step_'+slot)()
            self.assertEqual(form['step_id'],slot)
        with self.assertRaises(ValueError):h.models.validate_mode_rules([{**profile.rules[0],'state':'offline'}])
        with self.assertRaises(ValueError):h.models.validate_mode_rules([{**profile.rules[0],'conditions':[[]]}])
        await flow.async_step_rules({'mode':profile.rules[0]['id'],'delete':True})
        self.assertFalse((await coordinator.async_profile_for(entry)).rules)

    async def test_mode_identity_priority_disabled_unknown_and_persistence(self):
        profile=copy.deepcopy(self.runtime.profile)
        def rule(ident,name,priority,slot='input_1',state='on'):
            return {'id':ident,'name':name,'state':'technical','priority':priority,'accounting':'productive',
                    'enabled':True,'conditions':[[{'input':slot,'state':state}]]}
        profile.rules=[rule('a','Source',100),rule('b','Vent',100)]
        await self.runtime.async_apply_profile(profile)
        self.edge('binary_sensor.a','on',10)
        self.assertEqual(self.engine.async_snapshot().custom_label,'Vent')
        profile=copy.deepcopy(self.runtime.profile);profile.rules[0]['priority']=200
        physical=self.history.input_intervals('input_1')[-1]
        h.Clock.value=h.T+timedelta(seconds=20)
        await self.runtime.async_apply_profile(profile)
        self.assertEqual(self.engine.async_snapshot().custom_label,'Source')
        self.assertEqual(self.engine.state_since,h.Clock.value)
        self.assertIs(self.history.input_intervals('input_1')[-1],physical)
        self.edge('binary_sensor.a','unavailable',30)
        self.assertEqual(self.engine.state,'offline')
        await self.engine.async_stop();await self.engine.async_start()
        self.assertTrue(any(iv.input_label == 'Source' and iv.accounting == 'productive' for iv in self.history.intervals))
        profile=copy.deepcopy(self.runtime.profile)
        profile.inputs['input_1'].enabled=False
        profile.rules=[rule('c','Disabled OFF is unknown',100,state='off')]
        await self.runtime.async_apply_profile(profile)
        self.assertEqual(self.engine.state,'idle')
        self.assertIsNone(self.engine.async_snapshot().custom_label)

    async def test_rules_group_limit_and_accounting_reports(self):
        coordinator=h.coordinator_mod.MachineMonitorCoordinator(self.hass)
        coordinator.machines['m']=self.runtime
        await coordinator.async_update_profile('m',self.profile)
        self.hass.data['machine_monitor']={'coordinator':coordinator}
        entry=types.SimpleNamespace(entry_id='m',title='Machine',data={})
        flow=h.flow_mod.MachineMonitorOptionsFlow(entry);flow.hass=self.hass
        await flow.async_step_rules({'mode':'new'})
        await flow.async_step_mode({'name':'Bending','state':'idle','accounting':'productive'})
        for _ in range(16):
            result=await flow.async_step_conditions({'input_1':'on','another_group':True})
        self.assertEqual(len((await coordinator.async_profile_for(entry)).rules[0]['conditions']),16)
        self.edge('binary_sensor.a','on',10)
        h.Clock.value=h.T+timedelta(seconds=30)
        period_report=h.importlib.import_module('machine_monitor.reports').period_report
        report=period_report(self.runtime.profile,self.history.intervals,{},h.T,h.Clock.value,h.Clock.value)
        self.assertEqual(report['work_seconds'],20)
        self.assertEqual(report['idle_seconds'],10)
        self.assertEqual(report['work_cycles'],1)
        self.assertEqual(report['non_productive_seconds'],10)
