const test=require('node:test');const assert=require('node:assert/strict');
const {setup,fixture,walk,prepare}=require('./frontend_harness.cjs');
const languageSelect=view=>walk(view.shadowRoot).find(n=>n['aria-label']==='Language / Язык');
function choose(view,value){const select=languageSelect(view);assert.ok(select);select.value=value;select.onchange();}

test('Russian follows HA language, translates all workspaces and keeps profile names intact',()=>{
 const {card}=setup();prepare(card);card.hass={language:'ru-RU',connection:null};
 card._detail.input_timeline.rows[0].name='Work';card._detail.input_timeline.rows[1].name='Input';
 card._dirty=true;card._render();
 for(const text of ['Мониторинг','Отчёты','Диагностика','ФИЛЬТРЫ ВХОДОВ','ФИЗИЧЕСКИЕ ВХОДЫ','Работа','ХРАНЕНИЕ ИСТОРИИ','Срок хранения:','30 дн.','Сегодня'])assert.ok(card.shadowRoot.textContent.includes(text),text);
 const bars=walk(card.shadowRoot).filter(n=>n.role==='button'&&n.title?.startsWith('Вход:'));
 assert.equal(bars.length,4);assert.ok(bars.some(n=>n.title.startsWith('Вход: Work')));assert.ok(bars.some(n=>n.title.startsWith('Вход: Input')));
 assert.ok(bars.every(n=>n.title.includes('Состояние: ВКЛ')&&n.title.includes('Конец: СЕЙЧАС')));
 assert.equal(card._detail.input_timeline.rows[0].name,'Work');
});

test('manual language persists after reload without requests or losing viewport and filters',()=>{
 const {card,storage}=setup();prepare(card);card._visible.input_2=false;card._zoom=4;card._panMs=100;
 card._reportDates={start:'2026-10-01T08:00'};const before=JSON.stringify(card._detail);
 card._hass={callWS(){throw Error('Language switch must be local');}};
 choose(card,'ru');assert.equal(storage.get('machine_monitor.language'),'ru');
 assert.equal(card._visible.input_2,false);assert.equal(card._zoom,4);assert.equal(card._panMs,100);
 assert.equal(card._reportDates.start,'2026-10-01T08:00');assert.equal(JSON.stringify(card._detail),before);
 const reload=setup({storage});prepare(reload.card);assert.ok(reload.card.shadowRoot.textContent.includes('ФИЛЬТРЫ ВХОДОВ'));
 choose(reload.card,'en');assert.ok(reload.card.shadowRoot.textContent.includes('INPUT FILTERS'));
 assert.equal(storage.get('machine_monitor.language'),'en');
});

test('automatic mode follows HA changes while manual override wins and can be reset',()=>{
 const {card}=setup({language:'ru'});prepare(card);card.connectedCallback();
 assert.ok(card.shadowRoot.textContent.includes('Мониторинг'));
 card.hass={language:'en',connection:null};assert.ok(card.shadowRoot.textContent.includes('INPUT FILTERS'));
 choose(card,'ru');card.hass={language:'en',connection:null};assert.ok(card.shadowRoot.textContent.includes('ФИЛЬТРЫ ВХОДОВ'));
 choose(card,'auto');assert.ok(card.shadowRoot.textContent.includes('INPUT FILTERS'));
 card.disconnectedCallback();
});

test('language updates connected machine card and editor and cleans up disconnected views',()=>{
 const {card,elements}=setup();prepare(card);card.connectedCallback();
 const Single=elements.get('machine-monitor-machine-card'),single=new Single();single.setConfig({machine_id:'m'});single._detail=fixture();single.connectedCallback();
 const Editor=elements.get('machine-monitor-machine-editor'),editor=new Editor();editor.setConfig({machine_id:'m'});editor.connectedCallback();
 choose(card,'ru');assert.ok(single.shadowRoot.textContent.includes('ФИЗИЧЕСКИЕ ВХОДЫ'));
 assert.ok(editor.shadowRoot.textContent.includes('Показывать текущее состояние'));assert.ok(editor.shadowRoot.textContent.includes('1 ч'));
 assert.equal(languageSelect(editor).children.find(n=>n.selected).value,'ru');
 single.disconnectedCallback();editor.disconnectedCallback();const text=editor.shadowRoot.textContent;
 choose(card,'en');assert.equal(editor.shadowRoot.textContent,text);card.disconnectedCallback();
});

test('denied browser storage and invalid saved preferences do not break localization',()=>{
 const {card}=setup({storageDenied:true});prepare(card);choose(card,'ru');assert.ok(card.shadowRoot.textContent.includes('Мониторинг'));
 const bad=setup({storage:new Map([['machine_monitor.language','xx']])});prepare(bad.card);
 assert.ok(bad.card.shadowRoot.textContent.includes('INPUT FILTERS'));choose(bad.card,'xx');assert.ok(bad.card.shadowRoot.textContent.includes('INPUT FILTERS'));
});

test('reports translate semantic categories but preserve input and shift names and values',()=>{
 const {card}=setup();prepare(card);const period={start:new Date(Date.now()-3600000).toISOString(),end:new Date().toISOString(),states:{work:60,offline:20},inputs:[{name:'Heating',on_seconds:60,activations:2}],work_seconds:60};
 card._report={a:period,shifts:[{name:'Night shift',known_seconds:60,work_seconds:60,idle_seconds:0,offline_seconds:20,work_percent:100,idle_percent:0,downtime_count:0}],timezone:'Europe/Moscow'};
 choose(card,'ru');const report=walk(card.shadowRoot).find(n=>n.tag==='details'&&n.textContent.includes('ОТЧЁТЫ —'));
 for(const text of ['Рассчитать / сравнить','Работа','Нет связи','Физические входы A','Heating','Night shift','1 мин 00 с'])assert.ok(report.textContent.includes(text),text);
 choose(card,'en');assert.ok(card.shadowRoot.textContent.includes('Generate report / compare'));
});
