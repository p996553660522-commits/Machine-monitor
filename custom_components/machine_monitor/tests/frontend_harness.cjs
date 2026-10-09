const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
class Element {
  constructor(tag) { this.tag = tag; this.style = {setProperty(name,value) { this[name]=value; }}; this.children = []; this.isConnected = true; this._text = ''; }
  getElementById(id) { return walk(this).find(n=>n.id===id); }
  focus() { this.focused=true; }
  setAttribute(key, value) { this[key] = value; }
  setPointerCapture(id) { this.capture = id; }
  hasPointerCapture(id) { return this.capture === id; }
  releasePointerCapture() { this.capture = null; }
  getBoundingClientRect() { return {left: 0, top: 0, bottom: 40, width: 1000}; }
  dispatchEvent(event) { this.lastEvent = event; }
  attachShadow() { this.shadowRoot = new Element('shadow'); }
  appendChild(child) { this.children.push(child); return child; }
  addEventListener(name, fn) { this['on' + name] = fn; }
  set innerHTML(value) { this.children = []; }
  set textContent(value) { this._text = value == null ? '' : String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(' '); }
}
function setup(options={}) {
  const storage=options.storage || new Map();
  const elements = new Map(), timers = new Map(); let timerId = 0;
  const context = vm.createContext({
    CustomEvent: class { constructor(type, options) { this.type = type; Object.assign(this, options); } },
    HTMLElement: Element, document: { createElement: tag => new Element(tag), body: new Element('body') },
    navigator: {language: options.language || "en"},
    window: { innerWidth: 1000, localStorage: {getItem:key=>{if(options.storageDenied)throw Error("denied");return storage.get(key)||null;},setItem:(key,value)=>{if(options.storageDenied)throw Error("denied");storage.set(key,value);}} }, customElements: { get: n => elements.get(n), define: (n,c) => elements.set(n,c) },
    setInterval: (fn,ms) => { timers.set(++timerId,{fn,ms,interval:true}); return timerId; },
    clearInterval: id => timers.delete(id),
    setTimeout: (fn,ms) => { timers.set(++timerId,{fn,ms}); return timerId; },
    clearTimeout: id => timers.delete(id), console
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../frontend/machine_monitor_card.js'),'utf8'),context);
  return {card:new (elements.get('machine-monitor-card'))(),timers,context,elements,storage};
}
function fixture() {
  const end = new Date().toISOString(), start = new Date(Date.now()-3600000).toISOString();
  return {
    machine_id:'m',name:'Test',snapshot:{state:'work',state_label:'Work',state_since:start,active_inputs:{input_1:true,input_2:true}},
    stats:{work_seconds:60,idle_seconds:30,states:[{state:'work',label:'Work',color:'#00ff00',seconds:60}],downtime:{count:0}},
    timeline:[{state:'work'}], offline_periods:[{start,end,duration:3600,open:true}],
    input_timeline:{start,end,row_order:['input_3','input_1','input_4','input_2'],rows:[1,2,3,4].map(i=>({slot:'input_'+i,name:'Signal '+i,color:'#00ff00',enabled:true,visible:true,on:true,available:true,on_seconds:60,intervals:[{start,end,duration:3600,open:true}]}))}
  };
}
function walk(node) { return [node,...node.children.flatMap(walk)]; }
function flowBox(card) { return walk(card.shadowRoot).find(n=>n.children.some(c=>c._text==='REAL FLOW')); }
function flowLabels(card) {
  const box=flowBox(card);
  return walk(box).filter(n=>n.className==='mm-flow-label').flatMap(n=>walk(n).filter(c=>c._text.startsWith('Signal ')).map(c=>c._text));
}
function prepare(card) {
  card._loading=false; card._machines=[{machine_id:'m',name:'Test'}]; card._selected='m'; card._view='machine';
  card._detail=fixture(); card._adoptVisibility(card._detail); card._dirty=true; card._render();
}

module.exports={setup,fixture,walk,flowBox,flowLabels,prepare};
