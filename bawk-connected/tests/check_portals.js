// Exercise the actual portal scripts with a minimal DOM and an isolated API fixture.
// This checks behavior and data wiring; it does not replace a visual browser review.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
function fixture(file) {
  const nodes = [], ids = new Map();
  class Element {
    constructor(tag, attrs = {}) { this.tagName = tag; this.attrs = attrs; this.children = []; this.style = {}; this.dataset = {}; this.value = ''; this.textContent = ''; this.hidden = 'hidden' in attrs; this.events = {}; this.className = attrs.class || ''; for (const [k,v] of Object.entries(attrs)) if (k.startsWith('data-')) this.dataset[k.slice(5)] = v; nodes.push(this); if (attrs.id) ids.set(attrs.id, this); }
    setAttribute(k,v) { this.attrs[k] = String(v); }
    getAttribute(k) { return this.attrs[k] ?? null; }
    removeAttribute(k) { delete this.attrs[k]; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    addEventListener(event, fn) { this.events[event] = fn; }
    focus() { this.focused = true; }
    scrollIntoView() {}
    querySelectorAll(selector) { return nodes.filter(n => match(n, selector)); }
  }
  function match(node, selector) { return selector.split(',').some(s => { s = s.trim(); if(s.startsWith('.'))return node.className.split(' ').includes(s.slice(1)); if(s.startsWith('['))return s.slice(1,-1) in node.attrs; return node.tagName===s; }); }
  const html = fs.readFileSync(path.join(__dirname, '../website/dist/', file+'.html'),'utf8');
  for(const m of html.matchAll(/<([\w-]+)\b([^>]*)>/g)) {
    const attrs = {}; for(const a of m[2].matchAll(/([\w-]+)(?:="([^"]*)")?/g))attrs[a[1]] = a[2] ?? '';
    new Element(m[1], attrs);
  }
  const document = { getElementById: id => ids.get(id) || null, createElement: tag => new Element(tag), createElementNS: (_,tag) => new Element(tag), querySelectorAll: selector => nodes.filter(n=>match(n,selector)), querySelector: () => new Element('h1') };
  return { nodes, ids, document };
}
const parent = fixture('parent');
const parentContext = { document:parent.document, window:{scrollTo(){}}, Date, console };
vm.createContext(parentContext);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../website/dist/parent.js'),'utf8'),parentContext);
assert.equal(parent.ids.get('goal-percent').textContent,'80%');
parent.nodes.find(n=>n.dataset.goal==='turns').events.click();
assert.equal(parent.ids.get('goal-percent').textContent,'67%');
assert.equal(parent.ids.get('chart').children[0].tagName,'svg');
assert.equal(parent.ids.get('daily-data').children[0].children[1].children.length,7);
parent.nodes.find(n=>n.dataset.page==='home').events.click();
assert.equal(parent.ids.get('home').hidden,false);assert.equal(parent.ids.get('overview').hidden,true);
parent.nodes.find(n=>n.dataset.page==='goals').events.click();
assert.equal(parent.ids.get('goals').hidden,false);assert.equal(parent.ids.get('home').hidden,true);

async function supervisor() {
  const sup=fixture('index');
  let client={id:'demo',name:'Avery Morgan',first_name:'Avery',last_name:'Morgan',date_of_birth:'',caregiver_1:'',caregiver_2:'',address:''};
  const calls=[];
  const ctx={document:sup.document, window:{addEventListener(){}}, Date, console, crypto:{randomUUID:()=> 'test-id'}, confirm:()=>true, structuredClone,
    fetch: async (url,options)=> { const body=options?.body ? JSON.parse(options.body):null; calls.push({url,body});if(url==='/api/clients')client={...client,...body,name:[body.first_name || client.first_name,body.last_name ?? client.last_name].join(' ')};
      return {ok:true,json:async()=>url==='/api/workspace'?{clients:[client],goals:[],sets:[],responses:[]}:url==='/api/clients'?client:{ready:true}}; }};
  vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../website/dist/app.js'),'utf8'),ctx);
  for(let i=0;i<10;i++)await Promise.resolve();
  await ctx.refresh();
  sup.ids.get('client-list').children[0].children[1].onclick();
  assert.equal(sup.ids.get('client-panel').hidden,false);
  assert.equal(sup.ids.get('first-name').value,'Avery');
  sup.ids.get('caregiver-1').value='Jordan';sup.ids.get('client-address').value='Sample address';sup.ids.get('client-details').oninput();
  // A goal refresh must not discard unsaved profile edits.
  await ctx.refresh();assert.equal(sup.ids.get('caregiver-1').value,'Jordan');
  sup.ids.get('client-details').onsubmit({preventDefault(){}});
  for(let i=0;i<15;i++)await Promise.resolve();
  const saved=calls.find(c=>c.url==='/api/clients');assert.equal(saved.body.caregiver_1,'Jordan');assert.equal(saved.body.address,'Sample address');
  assert.equal(sup.ids.get('profile-status').textContent,'Details saved.');
  sup.ids.get('close-details').onclick();assert.equal(sup.ids.get('client-panel').hidden,true);
  assert.equal(sup.ids.has('rename'),false);
  // Render a real seven-day series: weighted practice today, an unscored day,
  // and missing days must all have dots without changing the overall metric.
  const today = new Date(); today.setHours(12, 0, 0, 0);
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
  ctx.chartResponses = [
    { client_id: 'demo', set_id: 's', created: today.getTime() / 1000, results: [{ independent: true }, { independent: false }, { independent: true }] },
    { client_id: 'demo', set_id: 's', created: yesterday.getTime() / 1000, results: [{}] }
  ];
  vm.runInContext(`workspace.sets = [{id:'s', client_id:'demo', goal_id:'g'}]; workspace.responses = chartResponses; selectedGoalId = 'g'; renderGoals([{id:'g',title:'Practice'}]);`, ctx);
  const detail = sup.ids.get('goal-detail');
  const chart = detail.children.find(n => n.tagName === 'svg');
  const points = chart.children.filter(n => n.tagName === 'circle');
  const segments = chart.children.filter(n => n.attrs.class === 'chart-segment');
  const tooltip = chart.children.find(n => n.attrs.class === 'chart-tooltip');
  assert.equal(points.length, 7);
  assert.equal(segments.length, 6);
  assert.equal(points[0].attrs.cy, '205');
  assert.match(points[0].attrs['aria-label'], /0% \(no scored data\)/);
  assert.match(points[6].attrs['aria-label'], /66.7%/);
  assert.equal(detail.children.find(n => n.className === 'goal-metric').children[0].textContent, '66.7%');
  points[0].events.pointerenter();
  assert.equal(tooltip.attrs.visibility, 'visible');
  assert.equal(tooltip.children[2].textContent, '0% · No scored data');
  points[0].events.pointerleave(); assert.equal(tooltip.attrs.visibility, 'hidden');
  points[6].events.focus();
  assert.equal(tooltip.children[2].textContent, '66.7% · 2 / 3 independent');
  points[6].events.keydown({key:'Escape'}); assert.equal(tooltip.attrs.visibility, 'hidden');
  const dailyRows = detail.children.find(n => n.className === 'chart-data').children[1].children[1].children;
  assert.equal(dailyRows[0].children[1].textContent, '0% (no scored data)');
  assert.equal(dailyRows[5].children[1].textContent, '0% (no scored data)');
  vm.runInContext(`workspace.goals = [{id:'g',client_id:'demo',title:'Social'}, {id:'empty',client_id:'demo',title:'Empty'}, {id:'removed',client_id:'demo',title:'Removed',deleted_at:1}];
    workspace.sets = [{id:'s',client_id:'demo',goal_id:'g',title:'School',problems:[],published:1}, {id:'old',client_id:'demo',goal_id:'g',title:'Old',superseded_by:'s'}, {id:'deleted',client_id:'demo',goal_id:'g',title:'Deleted',deleted_at:1}]; render();`,ctx);
  const groups=sup.ids.get('sets').children;
  assert.equal(groups.length,2); assert.equal(groups[0].tagName,'details');
  assert.equal(groups[0].children[0].textContent,'Social · 1 problem set');
  assert.equal(groups[1].children[0].textContent,'Empty · 0 problem sets');
  const row=groups[0].children[1].children[0];
  assert.equal(row.children[0].children[0].textContent,'School');
  for(let i=0;i<20;i++)await Promise.resolve();
  ctx.confirm=()=>false; row.children[1].children.find(n=>n.textContent==='Delete problem set').onclick();
  assert.equal(calls.filter(c=>c.url.endsWith('/delete')).length,0);
  ctx.confirm=()=>true; row.children[1].children.find(n=>n.textContent==='Delete problem set').onclick();
  for(let i=0;i<20;i++)await Promise.resolve();
  assert.deepEqual(calls.find(c=>c.url==='/api/sets/delete').body,{id:'s',client_id:'demo'});
  vm.runInContext(`workspace.sets=[{id:'s',goal_id:'g'}]; setId='s'; dirty=true; $('goal-input').value='other';`,ctx);
  let confirmation=''; ctx.confirm=message=>{confirmation=message;return true;};
  ctx.deleteGoal({id:'g',title:'Social'});
  for(let i=0;i<20;i++)await Promise.resolve();
  assert.match(confirmation,/Unsaved changes/);
  assert.equal(vm.runInContext('setId',ctx),null);
  assert.deepEqual(calls.find(c=>c.url==='/api/goals/delete').body,{id:'g',client_id:'demo'});
  assert.equal(row.children[0].children[1].textContent, '(Assigned to client)');
  assert.equal(row.children[1].className, 'saved-set-actions');
  vm.runInContext(`workspace.goals = [{id:'active',client_id:'demo',title:'Active',mastery_criteria:'80% for 3 sessions'}, {id:'archived',client_id:'demo',title:'Mastered',mastery_criteria:'90%',archived_at:1}]; selectedGoalId = 'active'; render();`,ctx);
  assert.equal(sup.ids.get('goals').children.length, 1);
  assert(sup.ids.get('goal-detail').children.some(n => n.textContent === '80% for 3 sessions'));
  sup.ids.get('show-archived').checked = true; sup.ids.get('show-archived').onchange();
  assert.equal(sup.ids.get('goals').children.length, 2);
  assert.equal(sup.ids.get('goal-input').children.length, 2); // placeholder and active only
  vm.runInContext(`selectedGoalId='archived'; render();`,ctx);
  assert(sup.ids.get('goal-detail').children.some(n => n.textContent === 'Restore goal to active practice'));
  assert(!sup.ids.get('goal-detail').children.some(n => n.textContent === 'Add problem set for this goal'));
  ctx.confirm=()=>false; ctx.changeGoalArchive({id:'active',title:'Active'});
  assert.equal(calls.filter(c => c.url === '/api/goals/archive').length, 0);
  ctx.confirm=()=>true; ctx.changeGoalArchive({id:'active',title:'Active'});
  for(let i=0;i<20;i++)await Promise.resolve();
  assert.deepEqual(calls.find(c=>c.url==='/api/goals/archive').body,{id:'active',client_id:'demo'});
  vm.runInContext(`problems=[{id:'trace',mode:'tracing',scenario:'School',question:'Follow the path',choices:[]}];renderProblems();`,ctx);
  assert.equal(vm.runInContext('problems[0].trace_template',ctx), 'school');
  const traceCard = sup.ids.get('draft-list').children[0];
  const templatePicker = traceCard.children.find(n => n.textContent === 'Tracing activity').children[0];
  assert.equal(templatePicker.children.length, 4);
  templatePicker.value='star'; templatePicker.onchange();
  assert.equal(vm.runInContext('problems[0].trace_template',ctx), 'star');
  vm.runInContext(`workspace.session_notes=[{id:'note',client_id:'demo',started_at:1700000000,ended_at:1700003600,provider_name:'Casey RBT',note_text:'Session narrative',counts:[{goal_id:'g',goal_title:'Social',independent:3,prompted:1,no_response:0}]}];renderSessionNotes();`,ctx);
  const noteCard=sup.ids.get('session-notes').children[0];
  assert.match(noteCard.children[0].textContent,/Casey RBT/);
  assert(noteCard.children[1].children.some(n => n.textContent === 'Session narrative'));
  const countTable=noteCard.children[1].children.find(n => n.className === 'session-data-wrap').children[0];
  assert.equal(countTable.children[1].children[0].children[4].textContent, '75%');
  ctx.confirm=()=>false; sup.ids.get('delete-client').onclick();
  assert.equal(calls.filter(c => c.url === '/api/clients/delete').length,0);
  ctx.confirm=()=>true; sup.ids.get('delete-client').onclick();
  for(let i=0;i<20;i++)await Promise.resolve();
  assert.deepEqual(calls.find(c=>c.url==='/api/clients/delete').body,{client_id:'demo'});
  assert.equal(vm.runInContext('clientId',ctx), null);
  console.log('PASS: mastery criteria, archive visibility and submission, tracing templates, RBT session history counts, client deletion confirmation.');
  console.log('PASS: goal disclosure groups, deleted/superseded filtering, empty goals, deletion cancellation, separate delete actions and editor reset.');
  console.log('PASS: parent navigation, goal switching and chart data; supervisor details open/save/close, optional fields and unsaved-edit preservation; seven connected daily dots, zero placeholders, hover/focus tooltips and weighted aggregate.');
}
supervisor().catch(e=>{console.error(e);process.exitCode=1;});
