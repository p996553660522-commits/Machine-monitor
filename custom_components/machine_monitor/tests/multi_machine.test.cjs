const test = require('node:test');
const assert = require('node:assert/strict');
const {setup,walk} = require('./frontend_harness.cjs');

test('overview retains both machines and coalesces refresh after either machine changes',async()=>{
  const {card,timers}=setup();
  const machines=[
    {machine_id:'a',name:'Малярка',state:'idle',offline:false},
    {machine_id:'b',name:'Oree4',state:'offline',offline:true}
  ];
  let listener, requests=0, subscriptions=0;
  card.setConfig({sort_by:'name'});
  card.hass={connection:{subscribeEvents:async cb=>{listener=cb;subscriptions++;return ()=>{};}},
    callWS:async ({type})=>{if(type.endsWith('/states'))return {states:[]};requests++;return {machines};}};
  for(let i=0;i<16;i++)await Promise.resolve();
  let tiles=walk(card.shadowRoot).filter(n=>n.className==='mm-machine-tile');
  assert.equal(tiles.length,2);
  assert.ok(tiles.some(n=>n.textContent.includes('Малярка')));
  assert.ok(tiles.some(n=>n.textContent.includes('Oree4')&&n.textContent.includes('Offline')));
  const before=requests;
  listener({data:{machine_id:'a'}});
  listener({data:{machine_id:'b'}});
  const pending=[...timers.values()].filter(t=>t.ms===250);
  assert.equal(pending.length,1);
  pending[0].fn();
  for(let i=0;i<16;i++)await Promise.resolve();
  assert.equal(requests,before+1);
  assert.equal(subscriptions,1);
  tiles=walk(card.shadowRoot).filter(n=>n.className==='mm-machine-tile');
  assert.equal(tiles.length,2);
  card.disconnectedCallback();
});
