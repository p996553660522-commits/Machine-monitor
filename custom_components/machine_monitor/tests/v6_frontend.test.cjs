const test = require('node:test');
const assert = require('node:assert/strict');
const {setup,fixture,walk,flowBox,prepare}=require('./frontend_harness.cjs');

function navigator(card) { return walk(card.shadowRoot).find(n=>n.role==='scrollbar'); }

test('distinct configured colors reach tracks, markers, filters, tooltips and compact flow',()=>{
  const {card}=setup();prepare(card);
  const colors=['#ff8800','#00cc44','#22aaff','#cc33cc'];
  card._detail.input_timeline.rows.forEach((r,i)=>r.color=colors[i]);card._dirty=true;card._render();
  let bars=walk(flowBox(card)).filter(n=>(n.title||'').startsWith('Input:'));
  assert.deepEqual(new Set(bars.map(b=>b.style.background)),new Set(colors));
  assert.ok(bars.every(b=>b._inputColor===b.style.background));
  for (const color of colors) assert.ok(walk(card.shadowRoot).filter(n=>n.style.background===color).length>=4);
  const offline=walk(flowBox(card)).filter(n=>(n.title||'').startsWith('OFFLINE'));
  assert.equal(offline.length,4);assert.ok(offline.every(n=>n.style.background.includes('repeating-linear-gradient')));
  card._setMode('compact');bars=walk(flowBox(card)).filter(n=>(n.title||'').startsWith('Input:'));
  assert.deepEqual(new Set(bars.map(b=>b.style.background)),new Set(colors));
});

test('navigator drag and keyboard pan all rows locally; zoom thumb and Now preserve viewport size',()=>{
  const {card}=setup();prepare(card);let calls=0;card._callWs=()=>{calls++;};
  assert.equal(navigator(card).children[0].style.width,'100%');
  card._zoomIn();assert.equal(navigator(card).children[0].style.width,'50%');
  const before=card._viewRange();const nav=navigator(card),thumb=nav.children[0];
  nav.onpointerdown({pointerId:1,button:0,clientX:500,target:thumb,preventDefault(){}});
  card.onpointermove({pointerId:1,clientX:750});
  const after=card._viewRange();assert.ok(after.start>before.start);assert.equal(after.span,before.span);
  card.onpointerup({pointerId:1});assert.equal(card._drag,null);assert.equal(card.capture,null);
  navigator(card).onkeydown({key:'Home',preventDefault(){}});
  assert.equal(card._viewRange().start.toISOString(),card._detail.input_timeline.start);
  card._jumpNow();assert.equal(card._zoom,2);
  assert.equal(card._viewRange().end.toISOString(),card._detail.input_timeline.end);
  card._zoomOut();assert.equal(navigator(card).children[0].style.width,'100%');
  assert.equal(calls,0);
});

test('navigator capture is cleaned up on disconnect',()=>{
  const {card}=setup();prepare(card);card._zoomIn();const nav=navigator(card);
  nav.onpointerdown({pointerId:2,clientX:400,target:nav.children[0],preventDefault(){}});
  card.disconnectedCallback();assert.equal(card._drag,null);assert.equal(card.capture,null);
});

test('long periods last month and retained history warning are visible',()=>{
  const {card}=setup();prepare(card);
  const options=walk(card.shadowRoot).filter(n=>n.tag==='option').map(n=>n.value);
  for(const id of ['last_month','60d','90d','180d','365d','custom']) assert.ok(options.includes(id));
  for(const days of [60,90,180,365]){card._period=days+'d';const r=card._periodRange();assert.equal(r.end-r.start,days*86400000);}
  card._period='last_month';const range=card._periodRange();assert.equal(range.start.getDate(),1);assert.equal(range.end.getDate(),1);
  card._detail.history={available_from:card._detail.input_timeline.end,size_bytes:1234,physical_intervals:42,semantic_intervals:7};
  card._dirty=true;card._render();assert.ok(card.shadowRoot.textContent.includes('History available from:'));
  assert.ok(card.shadowRoot.textContent.includes('Physical intervals: 42'));assert.ok(card.shadowRoot.textContent.includes((1234).toLocaleString('en')+' bytes'));
});

test('single machine card requests selected machine only, reuses flow and backend totals',async()=>{
  const {elements,context}=setup(), Card=elements.get('machine-monitor-machine-card'),card=new Card();
  card.setConfig({...Card.getStubConfig(),machine_id:'m',period:'6h'});
  const calls=[];card._hass={callWS:async msg=>{calls.push(msg);return fixture();}};
  await card._refreshCurrent();
  assert.equal(calls.length,1);assert.equal(calls[0].type,'machine_monitor/timeline');assert.equal(calls[0].machine_id,'m');
  assert.ok(card.shadowRoot.textContent.includes('Test'));assert.ok(card.shadowRoot.textContent.includes('REAL FLOW'));
  assert.ok(card.shadowRoot.textContent.includes('PHYSICAL INPUTS'));assert.ok(card.shadowRoot.textContent.includes('1m 00s'));
  assert.ok(!card.shadowRoot.textContent.includes('REPORTS'));assert.ok(!card.shadowRoot.textContent.includes('SEMANTIC EVENTS'));
  assert.equal(Card.prototype._renderRealFlow,elements.get('machine-monitor-card').prototype._renderRealFlow);
  assert.ok(context.window.customCards.some(c=>c.type==='machine-monitor-machine-card'));
  card._hass=null;card.setConfig({...Card.getStubConfig(),machine_id:'m',show_status:false,show_totals:false,show_offline:false});
  assert.ok(!card.shadowRoot.textContent.includes('CURRENT STATUS'));assert.ok(!card.shadowRoot.textContent.includes('PHYSICAL INPUTS'));
  assert.equal(walk(flowBox(card)).filter(n=>(n.title||'').startsWith('OFFLINE')).length,0);
});

test('visual editor machine and all configuration controls emit Lovelace config-changed',async()=>{
  const {elements}=setup(),Editor=elements.get('machine-monitor-machine-editor'),editor=new Editor();
  editor.setConfig({type:'custom:machine-monitor-machine-card'});
  editor.hass={connection:{},callWS:async()=>({machines:[{machine_id:'a',name:'Laser'},{machine_id:'b',name:'Chamber'}]})};
  await Promise.resolve();await Promise.resolve();
  const selects=walk(editor.shadowRoot).filter(n=>n.tag==='select' && n['aria-label']!=='Language / Язык');assert.equal(selects.length,3);
  selects[0].value='b';selects[0].onchange();
  assert.equal(editor.lastEvent.type,'config-changed');assert.equal(editor.lastEvent.detail.config.machine_id,'b');
  assert.equal(editor.lastEvent.bubbles,true);assert.equal(editor.lastEvent.composed,true);
  selects[1].value='24h';selects[1].onchange();assert.equal(editor.lastEvent.detail.config.period,'24h');
  selects[2].value='compact';selects[2].onchange();assert.equal(editor.lastEvent.detail.config.mode,'compact');
  const checks=walk(editor.shadowRoot).filter(n=>n.type==='checkbox');assert.equal(checks.length,3);
  checks[2].checked=false;checks[2].onchange();assert.equal(editor.lastEvent.detail.config.show_offline,false);
});

test('machine card switches selected machine without stale metadata and ignores other machine events',async()=>{
  const {elements,timers}=setup(),Card=elements.get('machine-monitor-machine-card'),card=new Card();
  card.setConfig({machine_id:'a'});card._detail=fixture();card.setConfig({machine_id:'b'});assert.equal(card._detail,null);
  card._onMachineEvent({data:{machine_id:'a'}});assert.equal(timers.size,0);
  card._onMachineEvent({data:{machine_id:'b'}});assert.equal([...timers.values()][0].ms,250);
});

test('reports send custom dates once, show comparisons and shifts; no report fetch on live refresh',async()=>{
  const {card}=setup();prepare(card);card._reportOpen=true;
  card._reportDates={start:'2026-01-01T00:00',end:'2026-02-01T00:00',compare_start:'2026-02-01T00:00',compare_end:'2026-03-01T00:00'};
  const calls=[];const r={start:'2026-01-01T00:00:00Z',end:'2026-02-01T00:00:00Z',states:{work:3600},inputs:[{name:'Heating',on_seconds:3600,activations:3}]};
  card._callWs=async(type,payload)=>{calls.push({type,...payload});return {a:r,b:r,timezone:'Europe/Moscow',shifts:[{name:'Night',known_seconds:3600,work_seconds:3000,idle_seconds:600,offline_seconds:0,work_percent:83.33,idle_percent:16.67,downtime_count:2}],comparison:[{metric:'work_percent',a:50,b:60,change:10,unit:'pp'}]};};
  await card._loadReports();assert.equal(calls.length,1);assert.equal(calls[0].type,'machine_monitor/reports');assert.equal(calls[0].machine_id,'m');
  assert.ok(calls[0].compare_start.endsWith('Z'));
  const text=card.shadowRoot.textContent;for(const expected of ['B versus A','+10 pp','Night','Europe/Moscow','Heating','83.33%','16.67%','Downtimes']) assert.ok(text.includes(expected),expected);
  card._dirty=true;card._render();assert.equal(calls.length,1);
});


test('background render preserves focused native date controls',()=>{
  const {card}=setup();prepare(card);const root=card.shadowRoot, before=root.children;
  root.activeElement={tagName:'INPUT'};card._dirty=true;card._render();
  assert.equal(root.children,before);assert.equal(card._dirty,true);
  root.activeElement=null;card._render();assert.notEqual(root.children,before);
});
