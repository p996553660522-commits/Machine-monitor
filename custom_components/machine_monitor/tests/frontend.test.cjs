/* Run: node --test tests/frontend.test.cjs. Minimal DOM and fake timer boundaries. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const {setup,fixture,walk,flowBox,flowLabels,prepare}=require('./frontend_harness.cjs');
const flush = async () => { for(let i=0;i<12;i++) await Promise.resolve(); };

test('active render uses physical rows, filters, custom order and independent simultaneous bars',()=>{
  const {card}=setup(); prepare(card);
  assert.deepEqual(flowLabels(card),['Signal 3','Signal 1','Signal 4','Signal 2']);
  assert.ok(card.shadowRoot.textContent.includes('INPUT FILTERS'));
  assert.equal(walk(flowBox(card)).filter(n=>String(n.title).startsWith('Input:')).length,4);
  assert.ok(walk(flowBox(card)).some(n=>String(n.title).includes('End: NOW')));
});

test('all 16 visibility combinations retain every filter and require no fetch',()=>{
  const {card}=setup(); prepare(card);
  card._loadDetail=()=>{throw Error('display filters must not fetch');};
  for(let mask=0;mask<16;mask++) {
    for(let i=1;i<=4;i++)card._visible['input_'+i]=!!(mask&(1<<(i-1)));
    card._dirty=true; card._render();
    assert.equal(flowLabels(card).length,mask.toString(2).replaceAll('0','').length);
    const filter=walk(card.shadowRoot).find(n=>n.children.some(c=>c._text==='INPUT FILTERS'));
    assert.equal(walk(filter).filter(n=>n._text.startsWith('Signal ')).length,4);
  }
  card._allVisible(true); assert.equal(flowLabels(card).length,4);
  card._allVisible(false); assert.equal(flowLabels(card).length,0);
  card._toggleVisible('input_2'); assert.deepEqual(flowLabels(card),['Signal 2']);
});

test('compact flow renders concurrent physical inputs and offline tracks',()=>{
  const {card}=setup(); prepare(card); card._setMode('compact');
  assert.equal(walk(flowBox(card)).filter(n=>String(n.title).startsWith('Input:')).length,4);
  assert.ok(walk(flowBox(card)).some(n=>String(n.title).startsWith('OFFLINE')));
});

test('offline uses same track coordinates and is visible when all inputs hidden',()=>{
  const {card}=setup(); prepare(card);
  let bands=walk(flowBox(card)).filter(n=>String(n.title).startsWith('OFFLINE'));
  assert.equal(bands.length,4);
  assert.ok(bands.every(n=>n.style.left==='0%'&&n.style.width==='100%'));
  card._allVisible(false);
  bands=walk(flowBox(card)).filter(n=>String(n.title).startsWith('OFFLINE'));
  assert.equal(bands.length,1);
});

test('unknown source displays UNKNOWN and local timer makes no requests',()=>{
  const {card}=setup(); prepare(card);
  card._detail.input_timeline.rows[0].on=null;
  card._detail.input_timeline.rows[0].available=false;
  card._dirty=true;card._render();
  assert.ok(card.shadowRoot.textContent.includes('UNKNOWN'));
  card._callWs=()=>{throw Error('elapsed timer must be local');};
  card._tickLive(); assert.ok(card._liveNode.textContent.includes(':'));
});

test('last_week is seven days; plotted range follows API bounds',()=>{
  const {card}=setup(); card._period='last_week';
  const range=card._periodRange();
  assert.equal(Math.round((range.end-range.start)/86400000),7);
  prepare(card);
  const data=card._detail.input_timeline, view=card._viewRange();
  assert.equal(view.start.toISOString(),data.start);
  assert.equal(view.end.toISOString(),data.end);
});

test('subscription and fallback survive disconnect/reconnect without duplicates',async()=>{
  const {card,timers}=setup(); let subscriptions=0,unsubs=0;
  const hass={connection:{subscribeEvents:async()=>{subscriptions++;return ()=>unsubs++;}},callWS:async type=> type.type.endsWith('states')?{states:[]}:{machines:[]}};
  card.hass=hass; await flush();
  assert.equal(subscriptions,1);
  assert.deepEqual([...timers.values()].filter(t=>t.interval).map(t=>t.ms).sort(),[1000,5000]);
  card.hass=hass; assert.equal(subscriptions,1);
  card.isConnected=false;card.disconnectedCallback();await flush();assert.equal(unsubs,1);assert.equal(timers.size,0);
  card.isConnected=true;card.connectedCallback();await flush();assert.equal(subscriptions,2);
  assert.equal([...timers.values()].filter(t=>t.interval).length,2);
});

test('event bursts coalesce at 250 ms and do not lose updates during fetch',async()=>{
  const {card,timers}=setup(); let calls=0;card._refreshCurrent=()=>calls++;
  card._onMachineEvent({});card._onMachineEvent({});card._onMachineEvent({});
  assert.equal(timers.size,1);const timer=[...timers.values()][0];assert.equal(timer.ms,250);timer.fn();assert.equal(calls,1);
  const other=setup().card;other._hass={};let release,count=0;
  other._loadOverview=async()=>{count++;if(count===1)await new Promise(r=>release=r);};
  const first=other._refreshCurrent();await flush();await other._refreshCurrent();release();await first;
  assert.equal(count,2);
});

test('detail fetch retains full input list and ignores responses for old selection',async()=>{
  const {card}=setup();prepare(card);let releases=[],requests=[];
  card._hass={callWS:req=>{requests.push(req);return new Promise(resolve=>releases.push(resolve));}};
  const first=card._loadDetail();card._selected='other';const second=card._loadDetail();
  releases[1]({...fixture(),machine_id:'other',name:'Other'});await second;
  releases[0](fixture());await first;
  assert.equal(card._detail.machine_id,'other');assert.ok(requests.every(r=>!('inputs' in r)));
});


test('custom range fields are inserted and use the chosen bounds',()=>{
  const {card}=setup();prepare(card);card._period='custom';
  card._customStart=new Date('2026-10-01T10:00:00Z');card._customEnd=new Date('2026-10-02T10:00:00Z');
  card._dirty=true;card._render();
  assert.equal(walk(card.shadowRoot).filter(n=>n.type==='datetime-local' && /^Range /.test(n.title || '')).length,2);
  const range=card._periodRange();assert.equal(range.end-range.start,86400000);
});

test('zoom and pan stay within the fetched history',()=>{
  const {card}=setup();prepare(card);card._zoom=2;card._panMs=1e12;
  let range=card._viewRange();assert.ok(range.end<=new Date(card._detail.input_timeline.end));
  card._panMs=-1e12;range=card._viewRange();assert.ok(range.start>=new Date(card._detail.input_timeline.start));
});


test('Add Card metadata and stub configuration are ready without entity YAML',()=>{
  const {card,context,elements}=setup();
  const descriptor=context.window.customCards.find(c=>c.type==='machine-monitor-card');
  assert.equal(descriptor.name,'Machine Monitor — Full UI');assert.equal(descriptor.preview,true);
  const config=elements.get('machine-monitor-card').getStubConfig();
  assert.equal(config.type,'custom:machine-monitor-card');
  card.setConfig(config);assert.equal(card._mode,'detailed');
  assert.equal(card._view,'overview');
});

test('loading module from two resource URLs does not duplicate registration',()=>{
  const {context,elements}=setup();const first=elements.get('machine-monitor-card');
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../frontend/machine_monitor_card.js'),'utf8'),context);
  assert.equal(elements.get('machine-monitor-card'),first);
  assert.equal(context.window.customCards.filter(c=>c.type==='machine-monitor-card').length,1);
});

test('legacy overview configuration still opens overview with detailed Real Flow',()=>{
  const {card}=setup();card.setConfig({type:'custom:machine-monitor-card',mode:'overview'});
  assert.equal(card._view,'overview');assert.equal(card._mode,'detailed');
});


test('open null-end ON and ISO timezone clipping render finite positive segments',()=>{
  const {card}=setup();prepare(card);
  const start='2026-10-05T11:00:00+03:00',end='2026-10-05T12:00:00+03:00';
  const data=card._detail.input_timeline;data.start=start;data.end=end;
  data.rows=data.rows.slice(0,1);
  data.rows[0].intervals=[
    {start:'2026-10-05T07:30:00Z',end:'2026-10-05T09:30:00Z',duration:7200},
    {start:'2026-10-05T08:30:00Z',end:null,open:true,duration:1800},
    {start:'invalid',end:'invalid'},
    {start:end,end:start},
  ];
  for (const mode of ['detailed','compact']) {
    card._mode=mode;card._dirty=true;card._render();
    const bars=walk(flowBox(card)).filter(n=>String(n.title).startsWith('Input:'));
    assert.equal(bars.length,2);
    assert.equal(bars[0].style.left,'0%');assert.equal(bars[0].style.width,'100%');
    assert.equal(bars[1].style.left,'50%');assert.equal(bars[1].style.width,'50%');
    assert.ok(bars[1].title.includes('End: NOW'));
    assert.ok(bars.every(b=>Number.isFinite(parseFloat(b.style.width))));
  }
});

test('offline exact source and compact diagnostics are inserted in active UI',()=>{
  const {card}=setup();prepare(card);
  const source={slot:'input_3',name:'Cooling',entity_id:'binary_sensor.esp_input3',ha_state:'unavailable',
    available:false,physical_on:null,last_changed:'2026-10-05T08:00:00Z',semantic_state:'cooling',enabled:true};
  card._detail.snapshot.offline=true;
  card._detail.snapshot.offline_reason={code:'unavailable_sources',sources:[source]};
  card._detail.source_diagnostics=[source];card._dirty=true;card._render();
  assert.ok(card.shadowRoot.textContent.includes('Unavailable sources'));
  assert.ok(card.shadowRoot.textContent.includes('Cooling / input_3 — binary_sensor.esp_input3 = unavailable'));
  const details=walk(card.shadowRoot).find(n=>n.tag==='details' && n.children.some(c=>c._text==='SOURCE DIAGNOSTICS'));
  assert.ok(details.textContent.includes('HA: unavailable'));
  assert.ok(details.textContent.includes('Physical: UNKNOWN'));
  assert.ok(details.textContent.includes('Last state change:'));
});


test('profile names are used for rows filters physical summaries and tooltips after live response',async()=>{
  const {card}=setup();prepare(card);
  const payload=fixture(),names=['Нагрев','Остывание','Поддержание','Input'];
  payload.input_timeline.rows.forEach((row,i)=>row.name=names[i]);
  card._hass={callWS:async()=>payload};await card._loadDetail();
  const box=flowBox(card);
  const labels=walk(box).filter(n=>n.className==='mm-flow-label').flatMap(n=>walk(n).filter(c=>names.includes(c._text)).map(c=>c._text));
  assert.deepEqual(labels,['Поддержание','Нагрев','Input','Остывание']);
  for (const heading of ['INPUT FILTERS','PHYSICAL INPUTS']) {
    const section=walk(card.shadowRoot).find(n=>n.children.some(c=>c._text===heading));
    assert.ok(section,heading);
    for(const name of names)assert.ok(walk(section).some(n=>n._text===name),heading+' '+name);
  }
  const bars=walk(box).filter(n=>String(n.title).startsWith('Input:'));
  for(const name of names)assert.ok(bars.some(n=>n.title.startsWith('Input: '+name+'\n')));
});


test('workspace navigation keeps filters zoom and row order without fetching',()=>{
  const {card}=setup();prepare(card);
  card._refreshCurrent=()=>{throw Error('tabs must not fetch');};
  card._visible.input_2=false;card._zoom=2;card._panMs=200;
  for(const workspace of ['reports','diagnostics','monitor']) {
    card._setWorkspace(workspace,true);
    const panels=walk(card.shadowRoot).filter(n=>n.role==='tabpanel');
    assert.equal(panels.filter(n=>!n.hidden).length,1);
    assert.equal(panels.find(n=>!n.hidden).id,'mm-panel-'+workspace);
    const tab=walk(card.shadowRoot).find(n=>n.id==='mm-tab-'+workspace);
    assert.equal(tab['aria-selected'],'true');assert.equal(tab.tabIndex,0);assert.equal(tab.focused,true);
    assert.equal(card._visible.input_2,false);assert.equal(card._zoom,2);assert.equal(card._panMs,200);
  }
  assert.deepEqual(flowLabels(card),['Signal 3','Signal 1','Signal 4']);
});

test('keyboard tabs wrap and retain focus through background redraw',()=>{
  const {card}=setup();prepare(card);
  let prevented=false;
  let tab=walk(card.shadowRoot).find(n=>n.id==='mm-tab-monitor');
  tab.onkeydown({key:'ArrowLeft',preventDefault(){prevented=true;}});
  assert.equal(prevented,true);assert.equal(card._workspace,'diagnostics');
  tab=walk(card.shadowRoot).find(n=>n.id==='mm-tab-diagnostics');
  card.shadowRoot.activeElement={id:tab.id,tagName:'BUTTON'};
  card._dirty=true;card._render();
  assert.equal(walk(card.shadowRoot).find(n=>n.id===tab.id).focused,true);
  card.shadowRoot.activeElement=null;
  walk(card.shadowRoot).find(n=>n.id===tab.id).onkeydown({key:'Home',preventDefault(){}});
  assert.equal(card._workspace,'monitor');
});

test('connection error preserves last timeline and offers a working retry',()=>{
  const {card}=setup();prepare(card);const detail=card._detail;
  card._error='Connection interrupted';card._dirty=true;card._render();
  assert.equal(card._detail,detail);assert.equal(flowLabels(card).length,4);
  assert.ok(walk(card.shadowRoot).some(n=>n.role==='alert'&&n.textContent.includes(card._error)));
  let retried=false;card._refreshCurrent=()=>{retried=true;};
  walk(card.shadowRoot).find(n=>n._text==='Try again').onclick();assert.equal(retried,true);
});

test('physical interval tooltips are reachable with touch and keyboard',()=>{
  const {card,context}=setup();prepare(card);
  const bar=walk(flowBox(card)).find(n=>String(n.title).startsWith('Input:'));
  assert.equal(bar.tabIndex,0);assert.equal(bar.role,'button');assert.equal(bar['aria-label'],bar.title);
  const rows=walk(flowBox(card)).find(n=>n.onmousemove && n.onclick);
  rows.onclick({target:bar,clientX:20,clientY:20});
  const tooltip=context.document.body.children.at(-1);
  assert.equal(tooltip.style.display,'block');assert.ok(tooltip.textContent.includes('State: ON'));
  rows.onkeydown({target:bar,key:'Escape',currentTarget:bar,preventDefault(){}});
  assert.equal(tooltip.style.display,'none');
  rows.onkeydown({target:bar,key:'Enter',currentTarget:bar,preventDefault(){}});
  assert.equal(tooltip.style.display,'block');
});
