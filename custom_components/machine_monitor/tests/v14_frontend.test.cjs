const test=require('node:test');const assert=require('node:assert/strict');
const {setup,prepare,walk,flowBox}=require('./frontend_harness.cjs');
const start=Date.parse('2026-10-05T08:00:00Z');
function iv(a,b){return {start:new Date(start+a*1000).toISOString(),end:new Date(start+b*1000).toISOString(),duration:b-a,open:false};}
test('grouping is strict below ten seconds, per-input, cached and does not mutate raw history',()=>{
 const {card}=setup();const raw=[iv(0,20),iv(29,50),iv(60,80)];const row={intervals:raw};
 const d={offline_periods:[iv(20,29)]};const before=JSON.stringify(raw);
 const groups=card._displayIntervals(row,d);
 assert.equal(groups.length,2);assert.equal(groups[0].group_count,2);
 assert.equal(groups[0].duration,50);assert.equal(groups[0].on_seconds,41);
 assert.equal(groups[0].gap_seconds,9);assert.equal(groups[0].offline_seconds,9);
 assert.strictEqual(groups,card._displayIntervals(row,d));assert.equal(JSON.stringify(raw),before);
 assert.equal(card._displayIntervals({intervals:[iv(0,20),iv(29,50)]},d).length,1);
 card._groupShort=false;assert.strictEqual(card._displayIntervals(row,d),raw);
});
test('active grouped and exact controls render both modes without backend requests; gaps remain visible',()=>{
 const {card}=setup();prepare(card);const data=card._detail;
 const base=Date.parse(data.input_timeline.start);const r=data.input_timeline.rows[0];
 r.intervals=[{start:new Date(base+1000).toISOString(),end:new Date(base+20000).toISOString(),duration:19},
 {start:new Date(base+25000).toISOString(),end:new Date(base+40000).toISOString(),duration:15}];
 card._callWs=()=>{throw Error('grouping cannot fetch');};card._dirty=true;card._render();
 let bars=walk(flowBox(card)).filter(n=>String(n._tooltipText).includes('Grouped signals'));
 assert.equal(bars.length,1);assert.ok(bars[0]._tooltipText.includes('Actual ON time'));assert.ok(bars[0].style.background.includes('transparent'));
 const exact=walk(card.shadowRoot).find(n=>n._text==='Exact history');exact.onclick();
 assert.equal(walk(flowBox(card)).filter(n=>String(n._tooltipText).includes('Grouped signals')).length,0);
 card._mode='compact';card._groupShort=true;card._dirty=true;card._render();
 assert.equal(walk(flowBox(card)).filter(n=>String(n._tooltipText).includes('Grouped signals')).length,1);
});
test('custom mode names bypass semantic translations in status and events',()=>{
 const {card}=setup();prepare(card);
 card._detail.snapshot.custom_label='Vent';card._detail.events=[{state:'technical',custom_label:'Laser emission',start:new Date(start).toISOString(),end:new Date(start+10000).toISOString(),duration:10}];
 card._dirty=true;card._render();assert.ok(card.shadowRoot.textContent.includes('Vent'));assert.ok(card.shadowRoot.textContent.includes('Laser emission'));
});
test('dense bursts use bounded styles and cache even across local elapsed ticks',()=>{
 const {card}=setup();const raw=Array.from({length:10000},(_,i)=>iv(i*2,i*2+1));const row={intervals:raw},d={offline_periods:[]};
 const begun=performance.now(),groups=card._displayIntervals(row,d);const duration=performance.now()-begun;
 assert.equal(groups.length,1);assert.equal(groups[0].on_seconds,10000);
 assert.ok(card._groupBackground(groups[0],'#123456').length<150);
 assert.strictEqual(card._displayIntervals(row,d),groups);
 console.log('Grouping 10000 intervals:',duration.toFixed(1),'ms');
});

test('event ordering compares instants across UTC offsets',()=>{
 const {card}=setup();prepare(card);
 card._detail.events=[{state:'technical',custom_label:'Older',start:'2026-10-05T11:00:00+03:00',duration:10},
 {state:'work',custom_label:'Newer',start:'2026-10-05T08:01:00Z',duration:10}];
 card._dirty=true;card._render();const text=card.shadowRoot.textContent;
 assert.ok(text.indexOf('Newer')<text.indexOf('Older'));
 card._eventSort='oldest';card._dirty=true;card._render();
 assert.ok(card.shadowRoot.textContent.indexOf('Older')<card.shadowRoot.textContent.indexOf('Newer'));
});
test('grouping preference persists locally and Russian controls remain connected',()=>{
 const storage=new Map();const {card}=setup({storage,language:'ru'});prepare(card);
 const exact=walk(card.shadowRoot).find(n=>n._text==='Точная история');assert.ok(exact);exact.onclick();
 const reopened=setup({storage}).card;assert.equal(reopened._groupShort,false);
});

test('zoom clips group gaps to the visible time axis without stretching unknown time',()=>{
 const {card}=setup(),groups=card._displayIntervals({intervals:[iv(0,20),iv(25,40)]},{offline_periods:[]});
 const style=card._groupBackground(groups[0],'#123456',{start:start+20000,end:start+30000});
 assert.ok(style.includes('transparent 0%'));assert.ok(style.includes('transparent 50%'));
 assert.ok(!card._groupBackground(groups[0],'#123456',{start:start+30000,end:start+40000}).includes('transparent'));
});
