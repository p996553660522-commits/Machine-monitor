"""V6 behavioral regressions at the HA boundaries (no running HA required)."""
import asyncio
import copy
import importlib
import json
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import test_machine_monitor as t

reports = importlib.import_module("machine_monitor.reports")
I = t.models.Interval
T = t.T


def iv(start, end, state="work", slot="input_2"):
    return I(start, end, state, source_input=slot)


class V6Tests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = t.RegressionTests.asyncSetUp
    edge = t.RegressionTests.edge

    async def test_retention_closed_crossing_and_open_intervals(self):
        cutoff = T - timedelta(days=30)
        expired = iv(cutoff-timedelta(days=2), cutoff)
        crossing = iv(cutoff-timedelta(hours=1), cutoff+timedelta(hours=1))
        current = iv(T-timedelta(minutes=5), None)
        self.history._intervals = [expired, crossing, current]
        self.history._input_intervals = {"input_2": copy.deepcopy([expired, crossing, current])}
        self.assertEqual(await self.history.async_prune_due(T, force=True), 2)
        self.assertIs(self.history.intervals[-1], current)
        self.assertEqual(self.history.intervals[0].start, crossing.start)
        self.assertIsNone(current.end)
        self.assertEqual(await self.history.async_prune_due(T+timedelta(hours=1)), 0)
        self.assertEqual(await self.history.async_prune_due(T+timedelta(days=1)), 2)
        self.assertEqual(self.history.intervals, [current])

    async def test_retention_change_is_immediate_and_does_not_split_current(self):
        self.edge("binary_sensor.b", "on", 10)
        old = iv(T-timedelta(days=60), T-timedelta(days=59))
        self.history.intervals.insert(0, old)
        self.history.input_intervals("input_2").insert(0, copy.deepcopy(old))
        current = self.history.intervals[-1]
        physical = self.history.input_intervals("input_2")[-1]
        profile = copy.deepcopy(self.profile); profile.retention_days = 365
        await self.runtime.async_apply_profile(profile)
        self.assertIn(old, self.history.intervals)
        profile = copy.deepcopy(profile); profile.retention_days = 30
        await self.runtime.async_apply_profile(profile)
        self.assertNotIn(old, self.history.intervals)
        self.assertIs(self.history.intervals[-1], current)
        self.assertIs(self.history.input_intervals("input_2")[-1], physical)
        self.assertIsNone(physical.end)
        saved=t.Store.data[self.history._store.key]
        self.assertFalse(any(datetime.fromisoformat(x["start"]) < T-timedelta(days=30) for x in saved["intervals"]))

    async def test_retention_independent_and_no_5000_cap(self):
        other = t.storage.HistoryStore(self.hass, "other")
        old = iv(T-timedelta(days=60), T-timedelta(days=59))
        for store, days in [(self.history, 30), (other, 365)]:
            store._intervals = [copy.deepcopy(old)]
            store.set_retention(days); await store.async_prune_due(T, force=True)
        self.assertEqual(len(self.history.intervals), 0)
        self.assertEqual(len(other.intervals), 1)
        for i in range(5100):
            other.async_open_input_interval("input_1", T+timedelta(seconds=i*2))
            other.async_close_input_interval("input_1", T+timedelta(seconds=i*2+1))
        self.assertEqual(len(other.input_intervals("input_1")), 5100)

    async def test_v5_migration_and_restart_keep_both_histories(self):
        old = iv(T-timedelta(days=1), T-timedelta(hours=23))
        payload = {"history_schema_version":2, "observed_at":T.isoformat(),
                   "intervals":[old.to_dict()], "input_intervals":{"input_2":[old.to_dict()]}}
        t.Store.data[self.history._store.key] = payload
        loaded = t.storage.HistoryStore(self.hass, "m")
        await loaded.async_load(); await loaded.async_flush()
        self.assertEqual(t.Store.data[loaded._store.key]["history_schema_version"], 3)
        again = t.storage.HistoryStore(self.hass, "m"); await again.async_load()
        self.assertEqual(again.intervals[0].to_dict(), old.to_dict())
        self.assertEqual(again.input_intervals("input_2")[0].to_dict(), old.to_dict())
        p = t.models.MachineProfile.from_dict({"machine_id":"m", "inputs":self.profile.to_dict()["inputs"]})
        self.assertEqual(p.retention_days, 30)

    async def test_metadata_uses_actual_persistent_file_size(self):
        self.edge("binary_sensor.b", "on", 10)
        t.Clock.value = T+timedelta(seconds=100)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"machine_monitor.m"
            self.history._store.path = str(path)
            async def save(payload): path.write_bytes(json.dumps(payload).encode())
            self.history._store.async_save = save
            await self.runtime.async_flush()
            h = self.history.metadata(t.Clock.value)
            self.assertEqual(h["size_bytes"], path.stat().st_size)
            self.assertEqual(datetime.fromisoformat(h["oldest_record"]), T)
            self.assertEqual(datetime.fromisoformat(h["newest_record"]), t.Clock.value)
            self.assertEqual((h["physical_intervals"], h["semantic_intervals"]), (1, 2))
            self.assertEqual(h["retention_days"], 30)

    async def test_batching_forced_stop_and_dirty_during_save(self):
        calls=[]; original=self.history._store.async_save
        async def save(data): calls.append(data); await original(data)
        self.history._store.async_save=save
        for second in range(1, 30):
            self.edge("binary_sensor.b", "on" if second%2 else "off", second)
            await self.runtime.async_flush(force=False)
        self.assertEqual(calls, [])
        t.Clock.value=T+timedelta(seconds=30)
        await self.runtime.async_flush(force=False)
        self.assertEqual(len(calls), 1)
        self.edge("binary_sensor.b", "off", 31)
        await self.runtime.async_stop()
        self.assertEqual(len(calls), 2)
        self.assertFalse(self.history.intervals[-1].is_open)
        async def concurrent(data):
            await original(data)
            self.history.async_open_interval(T+timedelta(seconds=40), "idle")
        self.history._store.async_save=concurrent
        await self.history.async_flush()
        self.assertTrue(self.history._dirty)

    async def test_colors_options_reload_and_selected_historical_api(self):
        profile=copy.deepcopy(self.profile)
        profile.inputs["input_1"].color="#123456"
        profile.inputs["input_2"].color="#abcdef"
        profile=t.models.MachineProfile.from_dict(profile.to_dict())
        await self.runtime.async_apply_profile(profile)
        self.edge("binary_sensor.a", "on", 10); self.edge("binary_sensor.b", "on", 20)
        t.Clock.value=T+timedelta(seconds=120)
        self.hass.data={"machine_monitor":{"coordinator":types.SimpleNamespace(runtime_for=lambda mid:self.runtime if mid=="m" else None)}}
        conn=t.Connection()
        await t.ws.ws_timeline(self.hass,conn,{"id":1,"machine_id":"m","start":(T+timedelta(seconds=30)).isoformat(),"end":(T+timedelta(seconds=60)).isoformat()})
        rows=conn.result["input_timeline"]["rows"]
        self.assertEqual([r["color"] for r in rows],["#123456","#abcdef"])
        self.assertEqual([r["on_seconds"] for r in rows],[30,30])
        self.assertEqual([r["on_seconds"] for r in conn.result["input_summary"]],[30,30])
        self.assertEqual(conn.result["machine_id"],"m")
        unknown=t.Connection();await t.ws.ws_timeline(self.hass,unknown,{"id":2,"machine_id":"other"})
        self.assertEqual(unknown.error,"unknown_machine")

    async def test_snapshot_is_bounded_and_open_tail_is_frozen(self):
        self.edge("binary_sensor.b", "on", 10)
        old=iv(T-timedelta(days=300),T-timedelta(days=299))
        self.history.intervals.insert(0,old)
        snap=self.runtime.query_snapshot(T,T+timedelta(hours=1))
        self.assertEqual(snap.history.intervals[0],old)  # one predecessor for work-cycle boundary semantics
        self.edge("binary_sensor.b", "off", 50)
        self.assertIsNone(snap.history.input_intervals("input_2")[-1].end)
        self.assertEqual(snap.engine.async_snapshot().active_inputs["input_2"],True)
        self.assertEqual(len(self.history.intervals),len(snap.history.intervals)+1)

    async def test_report_concurrent_offline_and_open_now(self):
        self.edge("binary_sensor.a","on",10)
        self.edge("binary_sensor.b","on",20)
        self.edge("binary_sensor.b","unavailable",40)
        self.edge("binary_sensor.b","on",60)
        t.Clock.value=T+timedelta(seconds=100)
        r=reports.period_report(self.profile,self.history.intervals,self.history.input_intervals(),T,t.Clock.value,t.Clock.value)
        self.assertEqual((r["total_seconds"],r["known_seconds"],r["offline_seconds"]),(100,80,20))
        self.assertEqual((r["work_seconds"],r["idle_seconds"]),(60,10))
        self.assertEqual((r["work_percent"],r["idle_percent"],r["offline_percent"]),(75,12.5,20))
        self.assertEqual([x["on_seconds"] for x in r["inputs"]],[90,60])
        self.assertEqual((r["work_cycles"],r["longest_work_seconds"]),(2,40))
        self.assertEqual(r["unrecorded_seconds"],0)

    async def test_reports_api_custom_comparison_and_invalid_range(self):
        self.hass.config=types.SimpleNamespace(time_zone="Europe/Moscow")
        self.hass.data={"machine_monitor":{"coordinator":types.SimpleNamespace(runtime_for=lambda mid:self.runtime)}}
        self.edge("binary_sensor.b","on",10);t.Clock.value=T+timedelta(seconds=100)
        msg={"id":1,"machine_id":"m","start":T.isoformat(),"end":(T+timedelta(seconds=50)).isoformat(),
             "compare_start":(T+timedelta(seconds=50)).isoformat(),"compare_end":t.Clock.value.isoformat()}
        conn=t.Connection();await t.ws.ws_reports(self.hass,conn,msg)
        self.assertEqual((conn.result["a"]["work_seconds"],conn.result["b"]["work_seconds"]),(40,50))
        self.assertEqual(conn.result["timezone"],"Europe/Moscow")
        for bad in [{"start":"2026-01-01"},{"end":T.isoformat()},{"compare_end":"bad"}]:
            conn=t.Connection();await t.ws.ws_reports(self.hass,conn,{**msg,**bad})
            self.assertEqual(conn.error,"invalid_range")

    async def test_options_persist_retention_shifts_and_reload(self):
        coordinator=t.coordinator_mod.MachineMonitorCoordinator(self.hass)
        coordinator.machines["m"]=self.runtime
        self.hass.data={"machine_monitor":{"coordinator":coordinator}}
        entry=types.SimpleNamespace(entry_id="m",title="Test",data={"input_1":"binary_sensor.a","input_2":"binary_sensor.b"})
        await coordinator.async_update_profile("m",self.profile)
        options=t.flow_mod.MachineMonitorOptionsFlow(entry);options.hass=self.hass
        result=await options.async_step_machine({"retention_days":"90","shifts":"Day | 08:00 | 20:00\nNight | 20:00 | 08:00"})
        self.assertEqual(result,{"data":{}})
        await coordinator.async_reload_machine_task(entry)
        p=coordinator.runtime_for("m").profile
        self.assertEqual((p.retention_days,len(p.shifts)),(90,2))
        bad=await options.async_step_machine({"retention_days":"31"})
        self.assertEqual(bad["errors"]["base"],"invalid_history_settings")
        await coordinator.runtime_for("m").async_stop()

    async def test_cleanup_keeps_events_arriving_during_executor_work(self):
        self.edge("binary_sensor.b", "on", 10)
        self.history.intervals.insert(0, iv(T-timedelta(days=60), T-timedelta(days=59)))
        self.history.input_intervals("input_2").insert(0, iv(T-timedelta(days=60), T-timedelta(days=59)))
        original = self.hass.async_add_executor_job
        async def executor(fn, *args):
            result = await original(fn, *args)
            if getattr(fn, "__name__", "") == "_retained_groups":
                self.edge("binary_sensor.b", "off", 20)
                self.edge("binary_sensor.b", "on", 30)
            return result
        self.hass.async_add_executor_job = executor
        self.assertEqual(await self.history.async_prune_due(T, force=True), 2)
        entries=self.history.input_intervals("input_2")
        self.assertEqual(len(entries),2)
        self.assertEqual(entries[0].duration_seconds(),10)
        self.assertEqual(entries[1].start,T+timedelta(seconds=30))
        self.assertIsNone(entries[1].end)

    async def test_atomic_store_configuration(self):
        with patch.object(t.storage, "Store", wraps=t.Store) as factory:
            t.storage.HistoryStore(self.hass, "atomic")
        self.assertEqual(factory.call_args.kwargs,{"atomic_writes":True,"serialize_in_event_loop":False})

    async def test_work_source_change_at_report_boundary_is_not_new_cycle(self):
        self.history._intervals=[iv(T,T+timedelta(seconds=20),slot="input_1"),
                                 iv(T+timedelta(seconds=20),None,slot="input_2")]
        t.Clock.value=T+timedelta(seconds=40)
        snap=self.runtime.query_snapshot(T+timedelta(seconds=20),t.Clock.value)
        r=reports.build_reports(snap,T+timedelta(seconds=20),t.Clock.value,now=t.Clock.value)["a"]
        self.assertEqual(r["work_seconds"],20)
        self.assertEqual(r["work_cycles"],0)

    async def test_query_excludes_start_at_period_end(self):
        a=iv(T,T+timedelta(seconds=20));b=iv(T+timedelta(seconds=20),None)
        self.assertEqual(self.history.query([a,b],T,T+timedelta(seconds=20)),[a])


class ReportMathTests(unittest.TestCase):
    def setUp(self):
        self.profile=t.models.MachineProfile("m",inputs={"input_2":t.models.InputConfig("binary_sensor.b")})

    def test_january_february_comparison_relative_and_points(self):
        jan=datetime(2026,1,1,tzinfo=timezone.utc);feb=datetime(2026,2,1,tzinfo=timezone.utc);mar=datetime(2026,3,1,tzinfo=timezone.utc)
        entries=[iv(jan,jan+timedelta(hours=182)),iv(jan+timedelta(hours=182),jan+timedelta(hours=256),"idle"),
                 iv(feb,feb+timedelta(hours=205)),iv(feb+timedelta(hours=205),feb+timedelta(hours=256),"idle")]
        a=reports.period_report(self.profile,entries,{},jan,feb,mar)
        b=reports.period_report(self.profile,entries,{},feb,mar,mar)
        comparison={r["metric"]:r for r in reports.compare_reports(a,b)}
        self.assertEqual(comparison["work_seconds"]["change"],12.64)
        self.assertEqual(comparison["work_percent"]["change"],round(b["work_percent"]-a["work_percent"],2))
        self.assertEqual(comparison["work_percent"]["unit"],"pp")
        self.assertIsNone(comparison["offline_seconds"]["change"])
        self.assertEqual(a["total_seconds"],31*86400)
        self.assertEqual(b["total_seconds"],28*86400)

    def test_shift_midnight_three_shifts_and_timezone(self):
        self.profile.shifts=t.models.validate_shifts([
            {"name":"Morning","start":"08:00","end":"16:00"},
            {"name":"Evening","start":"16:00","end":"00:00"},
            {"name":"Night","start":"00:00","end":"08:00"}])
        start=datetime(2026,1,1,21,tzinfo=timezone.utc);end=start+timedelta(days=1)
        rows=reports.shift_reports(self.profile,[iv(start,end)],{},start,end,end,"Europe/Moscow")
        self.assertEqual([r["work_seconds"] for r in rows],[28800]*3)
        self.assertEqual([r["work_percent"] for r in rows],[100]*3)
        night=[{"name":"Night","start":"20:00","end":"08:00"}]
        windows=list(reports.shift_windows(night,start,end,"Europe/Moscow"))
        self.assertEqual(sum((b-a).total_seconds() for _,a,b in windows),43200)
        self.assertEqual(windows[0][1],start)

    def test_shift_dst_elapsed_time(self):
        shifts=[{"name":"Night","start":"20:00","end":"08:00"}]
        for start, expected in [(datetime(2026,3,28,19,tzinfo=timezone.utc),11),
                                (datetime(2026,10,24,18,tzinfo=timezone.utc),13)]:
            end=start+timedelta(hours=expected)
            windows=list(reports.shift_windows(shifts,start,end,"Europe/Berlin"))
            self.assertEqual(sum((b-a).total_seconds() for _,a,b in windows),expected*3600)

    def test_shift_validation_and_palette_roundtrip(self):
        for shifts in [[{"name":"A","start":"00:00","end":"00:00"}],
                       [{"name":"A","start":"08:00","end":"20:00"},{"name":"B","start":"19:00","end":"23:00"}]]:
            with self.assertRaises(ValueError): t.models.validate_shifts(shifts)
        p=t.models.MachineProfile("m",inputs={f"input_{i}":t.models.InputConfig(f"binary_sensor.i{i}") for i in range(1,5)})
        self.assertEqual(len({x.effective_color for x in p.inputs.values()}),4)
        restored=t.models.MachineProfile.from_dict(p.to_dict())
        self.assertEqual([x.effective_color for x in restored.inputs.values()],[x.effective_color for x in p.inputs.values()])

    def test_long_periods_and_last_month(self):
        now=datetime(2026,3,15,tzinfo=timezone.utc)
        for days in [7,30,60,90,180,365]:
            a,b=t.stats_mod.period_bounds(now,f"{days}d");self.assertEqual(b-a,timedelta(days=days))
        a,b=t.stats_mod.period_bounds(now,"last_month")
        self.assertEqual((a.day,a.month,b.day,b.month),(1,2,1,3))
