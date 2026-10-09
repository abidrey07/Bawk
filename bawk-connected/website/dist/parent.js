'use strict';
const pages = ['overview', 'goals', 'home'];
function openPage(page) {
  if (!pages.includes(page)) return;
  pages.forEach(id => { document.getElementById(id).hidden = id !== page; });
  document.querySelectorAll('[data-page]').forEach(button => {
    if (button.dataset.page === page) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  window.scrollTo({ top: 0, behavior: 'auto' });
  const heading = document.querySelector(`#${page} h1`);
  heading.tabIndex = -1; heading.focus({ preventScroll: true });
}
document.querySelectorAll('[data-page],[data-open]').forEach(button => {
  button.addEventListener('click', () => openPage(button.dataset.page || button.dataset.open));
});
const goals = {
  help: { title: 'Asking for help', days: [null, [1,2], null, [3,3], null, null, [4,5]] },
  turns: { title: 'Taking turns', days: [null, [1,3], null, [2,3], null, [7,9], null] }
};
function showGoal(key) {
  const goal = goals[key];
  if (!goal) return;
  document.querySelectorAll('[data-goal]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.goal === key)));
  const scored = goal.days.reduce((sum, d) => sum + (d?.[1] || 0), 0);
  const independent = goal.days.reduce((sum, d) => sum + (d?.[0] || 0), 0);
  document.getElementById('goal-title').textContent = goal.title;
  document.getElementById('goal-percent').textContent = `${Math.round(independent / scored * 100)}%`;
  document.getElementById('goal-count').textContent = `${independent} of ${scored} scored answers · fictional example`;
  const now = new Date();
  const dates = goal.days.map((_, i) => new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6 + i));
  const labels = dates.map(date => date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }));
  const ns = 'http://www.w3.org/2000/svg';
  function node(tag, attrs, text) {
    const el = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([k,v]) => el.setAttribute(k, v));
    if (text) el.textContent = text;
    return el;
  }
  const svg = node('svg', { viewBox: '0 0 680 260', role: 'img', 'aria-label': `${goal.title}: sample daily independence percentages for the last seven days. Exact values in the table below.` });
  const x = i => 55 + i * 95, y = percent => 215 - percent * 1.8;
  [0,25,50,75,100].forEach(percent => {
    svg.append(node('line',{ x1:55,x2:625,y1:y(percent),y2:y(percent),stroke:'#e4e8df' }));
    svg.append(node('text',{ x:44,y:y(percent)+4,'text-anchor':'end',fill:'#64736d','font-size':12 },`${percent}%`));
  });
  goal.days.forEach((day,i) => {
    svg.append(node('text',{x:x(i),y:244,'text-anchor':'middle',fill:'#64736d','font-size':12},labels[i]));
    if (!day) return;
    const percent = day[0] / day[1] * 100;
    const prior = goal.days[i-1];
    if (prior) svg.append(node('line',{x1:x(i-1),x2:x(i),y1:y(prior[0]/prior[1]*100),y2:y(percent),stroke:'#548367','stroke-width':3}));
    const dot = node('circle',{cx:x(i),cy:y(percent),r:6,fill:'#548367',stroke:'white','stroke-width':2});
    dot.append(node('title',{},`${labels[i]}: ${Math.round(percent)}%`));svg.append(dot);
  });
  document.getElementById('chart').replaceChildren(svg);
  const table = document.createElement('table');
  const head = document.createElement('thead');
  const header = document.createElement('tr');
  ['Date','Independent / scored','Percentage'].forEach(label=> { const cell = document.createElement('th');cell.scope='col';cell.textContent=label;header.append(cell); });head.append(header);table.append(head);
  const body = document.createElement('tbody');
  goal.days.forEach((day,i)=> { const row=document.createElement('tr');[labels[i],day ? `${day[0]} / ${day[1]}`:'—',day ? `${Math.round(day[0]/day[1]*100)}%`:'No practice'].forEach(value=> {const cell=document.createElement('td');cell.textContent=value;row.append(cell);});body.append(row); });table.append(body);
  document.getElementById('daily-data').replaceChildren(table);
}
document.querySelectorAll('[data-goal]').forEach(button=>button.addEventListener('click',()=>showGoal(button.dataset.goal)));
showGoal('help');
