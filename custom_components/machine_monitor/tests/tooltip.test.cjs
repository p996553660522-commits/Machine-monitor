const test = require('node:test');
const assert = require('node:assert/strict');
const {setup,prepare,walk,flowBox} = require('./frontend_harness.cjs');

for(const mode of ['detailed','compact']) {
  test(`${mode}: custom interval and OFFLINE tooltips never expose native title`,()=>{
    const {card,context}=setup();prepare(card);card._setMode(mode);
    const box=flowBox(card),nodes=walk(box);
    const rows=nodes.find(n=>n.onmousemove&&n.onclick);
    const bars=nodes.filter(n=>n._tooltipText?.startsWith('Input:'));
    const offline=nodes.filter(n=>n._tooltipText?.startsWith('OFFLINE'));
    assert.equal(bars.length,4);assert.ok(offline.length);
    assert.ok(walk(rows).every(n=>!n.title),'Custom tooltip targets must not trigger browser tooltips');
    for(const target of [...bars,...offline]) {
      assert.equal(target['aria-label'],target._tooltipText);
      assert.equal(target.tabIndex,0);
      rows.onmousemove({target,clientX:20,clientY:20});
      const tooltip=context.document.body.children.at(-1);
      assert.equal(tooltip.textContent,target._tooltipText);
      assert.equal(tooltip.style.display,'block');
      // Remaining hovered must still have no native tooltip source.
      rows.onmousemove({target,clientX:20,clientY:20});
      assert.ok(!target.title);
      rows.onmouseleave();assert.equal(tooltip.style.display,'none');
      rows.onclick({target});assert.equal(tooltip.style.display,'block');
      rows.onkeydown({target,key:'Escape'});assert.equal(tooltip.style.display,'none');
      rows.onfocusin({target});assert.equal(tooltip.style.display,'block');
      rows.onfocusout();assert.equal(tooltip.style.display,'none');
      rows.onkeydown({target,key:' ',preventDefault(){}});
      assert.equal(tooltip.style.display,'block');
    }
    if(mode==='detailed') {
      const label=nodes.find(n=>n.className==='mm-flow-label'&&n._tooltipText);
      rows.onmousemove({target:label.children.at(-1)});
      assert.equal(context.document.body.children.at(-1).textContent,label._tooltipText);
    }
    card._allVisible(false);
    const hiddenBox=flowBox(card), hiddenRows=walk(hiddenBox).find(n=>n.onmousemove&&n.onclick);
    const band=walk(hiddenBox).find(n=>n._tooltipText?.startsWith('OFFLINE'));
    assert.ok(band);assert.ok(!band.title);
    hiddenRows.onclick({target:band});
    assert.ok(context.document.body.children.at(-1).textContent.startsWith('OFFLINE'));
    card.disconnectedCallback();
    assert.equal(context.document.body.children.at(-1).style.display,'none');
  });
}
