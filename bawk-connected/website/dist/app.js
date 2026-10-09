const $ = id => document.getElementById(id);
let workspace = { clients: [], goals: [], sets: [], responses: [] };
let selectedGoalId = null;
let detailsOpen = false, profileDirty = false;
const profileFields = { first_name: "first-name", last_name: "last-name", date_of_birth: "date-of-birth", caregiver_1: "caregiver-1", caregiver_2: "caregiver-2", address: "client-address" };
const today = new Date();
$("date-of-birth").max = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
let clientId = null, setId = null, editingAssigned = false, problems = [], dirty = false, busy = false;
const uid = () => crypto.randomUUID();
const status = (message, error = false) => { $('status').textContent = message; $('status').style.color = error ? '#a33119' : '#466038'; };
async function api(path, body) {
  const response = await fetch(`/api/${path}`, { credentials: 'same-origin', ...(body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) });
  const value = await response.json();
  if (!response.ok) {
    if (response.status === 401 && !['account/login', 'account/register'].includes(path)) window.dispatchEvent(new Event('bawk-session-expired'));
    throw new Error(value.error || 'Could not connect');
  }
  return value;
}
async function action(fn) {
  if (busy) return;
  busy = true;
  document.querySelectorAll('button, input, textarea, select').forEach(b => b.disabled = true);
  try { await fn(); } catch (e) { status(e.message, true); }
  finally { busy = false; document.querySelectorAll('button, input, textarea, select').forEach(b => b.disabled = false); }
}
const element = (tag, text, className) => { const e = document.createElement(tag); if (text) e.textContent = text; if (className) e.className = className; return e; };
function button(label, fn) { const b = element('button', label, 'secondary-button'); b.type = 'button'; b.onclick = fn; return b; }
function field(label, value, change, multiline = false) {
  const wrap = element('label', label), input = element(multiline ? 'textarea' : 'input');
  input.value = value || ''; input.maxLength = 4000; if (multiline) input.rows = 3;
  input.oninput = () => { dirty = true; change(input.value); };
  wrap.append(input); return wrap;
}
function guardDraft() { return !dirty || confirm('Discard unsaved changes?'); }
function resetEditor() { setId = null; editingAssigned = false; $('save').hidden = false; $('publish').textContent = 'Save & assign to client'; problems = []; $('set-title').value = ''; $('goal-input').value = ''; dirty = false; renderProblems(); }
function selectClient(id) {
  if (id === clientId) return true;
  if (!guardDraft() || (profileDirty && !confirm('Discard unsaved client details?'))) return false;
  profileDirty = false; $('profile-status').textContent = '';
  clientId = id; resetEditor(); $('pair-info').textContent = ''; render(); return true;
}
function renderProblems() {
  $('draft-list').replaceChildren(); $('draft-count').textContent = `${problems.length} question${problems.length === 1 ? '' : 's'}`;
  for (const [i, p] of problems.entries()) {
    const card = element('article', '', 'draft-card'); card.append(element('h3', `Question ${i + 1}`));
    card.append(field('Scenario', p.scenario, v => p.scenario = v, true), field('Question', p.question, v => p.question = v));
    const format = element('label', 'Answer format'), select = element('select');
    for (const [value, label] of [['multiple_choice', 'Multiple choice'], ['open_ended', 'Open-ended'], ['tracing', 'Tracing']]) { const o = element('option', label); o.value = value; select.append(o); }
    select.value = p.mode; select.onchange = () => { p.mode = select.value; dirty = true; renderProblems(); }; format.append(select); card.append(format);
    if (p.mode === 'multiple_choice') {
      card.append(element('p', 'Select the circle beside the correct answer.', 'sample-note'));
      p.choices.forEach((c, j) => {
        const row = element('div', '', 'choice-edit'); const correct = element('input'); correct.type = 'radio'; correct.name = `correct-${p.id}`; correct.checked = p.correct_choice_id === c.id;
        correct.setAttribute('aria-label', `Mark choice ${j + 1} correct`); correct.onchange = () => { p.correct_choice_id = c.id; dirty = true; };
        row.append(correct, field(`Choice ${j + 1}`, c.text, v => c.text = v), button('Remove', () => { p.choices = p.choices.filter(x => x.id !== c.id); if (p.correct_choice_id === c.id) p.correct_choice_id = null; dirty = true; renderProblems(); })); card.append(row);
      });
      card.append(button('Add choice', () => { if (p.choices.length >= 10) return status('Up to 10 choices per question.', true); p.choices.push({ id: uid(), text: '' }); dirty = true; renderProblems(); }));
    } else if (p.mode === 'tracing') {
      const label = element('label', 'Tracing activity'), template = element('select');
      [['school', 'Help the chicken get to school'], ['letter_a', 'Trace the letter A'], ['number_2', 'Trace the number 2'], ['star', 'Trace a star symbol']].forEach(([value, title]) => { const option = element('option', title); option.value = value; template.append(option); });
      p.trace_template ||= 'school'; template.value = p.trace_template; template.onchange = () => { p.trace_template = template.value; dirty = true; };
      label.append(template); card.append(label, element('p', 'Clients follow the dotted guide with a finger. Completion records practice; it does not establish motor-skill mastery.', 'sample-note'));
    } else {
      card.append(field('Example correct response', p.expected_response, v => p.expected_response = v, true), field('What makes an answer acceptable?', p.acceptance_criteria, v => p.acceptance_criteria = v, true), element('p', 'Written answers are saved but are not scored for independence. AI feedback is not enabled.', 'sample-note'));
    }
    card.append(field('Feedback / explanation', p.explanation, v => p.explanation = v, true), button('Remove question', () => { problems = problems.filter(x => x.id !== p.id); dirty = true; renderProblems(); }));
    $('draft-list').append(card);
  }
  if (!problems.length) $('draft-list').append(element('p', 'No questions yet. Add your first question below.', 'empty-state'));
}
function render() {
  $('client-list').replaceChildren();
  workspace.clients.forEach(c => {
    const row = element('div', '', 'client-row');
    const b = button(c.name, () => selectClient(c.id)); b.className = 'client-button'; b.setAttribute('aria-pressed', String(c.id === clientId));
    const more = button('•••', () => {
      if (!selectClient(c.id)) return;
      detailsOpen = true; render(); $('first-name').focus();
    });
    more.className = 'client-more'; more.setAttribute('aria-label', `Details for ${c.name}`);
    more.setAttribute('aria-controls', 'client-panel'); more.setAttribute('aria-expanded', String(detailsOpen && c.id === clientId));
    row.append(b, more); $('client-list').append(row);
  });
  $('session-history-link').href = '/notes.html' + (clientId ? '?client=' + encodeURIComponent(clientId) : '');
  const client = workspace.clients.find(c => c.id === clientId);
  ['goals-panel', 'editor', 'sets-panel'].forEach(id => $(id).hidden = !client);
  $('client-panel').hidden = !client || !detailsOpen;
  renderRbtClients();
  if (!client) return;
  $('selected-name').textContent = client.name;
  if (!profileDirty) Object.entries(profileFields).forEach(([key, id]) => $(id).value = client[key] || '');
  const selectedGoal = $('goal-input').value;
  $('goal-input').replaceChildren();
  const placeholder = element('option', 'Choose a goal'); placeholder.value = ''; $('goal-input').append(placeholder);
  const allGoals = workspace.goals.filter(g => g.client_id === clientId && !g.deleted_at);
  const goals = allGoals.filter(g => !g.archived_at);
  const visibleGoals = $('show-archived').checked ? allGoals : goals;
  goals.forEach(g => {
    const option = element('option', g.title); option.value = g.id; $('goal-input').append(option);
  });
  if (goals.some(g => g.id === selectedGoal)) $('goal-input').value = selectedGoal;
  if (!visibleGoals.some(g => g.id === selectedGoalId)) selectedGoalId = visibleGoals[0]?.id || null;
  renderGoals(visibleGoals);
  renderSavedSets(goals);


}

const expandedGoals = new Set();
function deleteProblemSet(set) {
  const editing = setId === set.id;
  if (!confirm(`Delete “${set.title}”? This removes it from active practice. Its goal and previous results will be kept.${editing && dirty ? ' Unsaved changes to this set will be discarded.' : ''}`)) return;
  action(async () => {
    await api('sets/delete', { id: set.id, client_id: clientId });
    if (editing) resetEditor();
    await refresh(); status('Problem set deleted. Its goal and previous results were kept.');
  });
}
function deleteGoal(goal) {
  const count = workspace.sets.filter(s => s.goal_id === goal.id && !s.deleted_at && !s.superseded_by).length;
  const editing = $('goal-input').value === goal.id || workspace.sets.some(s => s.id === setId && s.goal_id === goal.id);
  if (!confirm(`Delete “${goal.title}” and its ${count} problem set${count === 1 ? '' : 's'}? They will be removed from active practice. Previous results will be kept.${editing && dirty ? ' Unsaved changes for this goal will be discarded.' : ''}`)) return;
  action(async () => {
    await api('goals/delete', { id: goal.id, client_id: clientId });
    if (editing) resetEditor();
    expandedGoals.delete(goal.id);
    await refresh(); status('Goal and its problem sets deleted. Previous results were kept.');
  });
}
function renderSavedSets(goals) {
  $('sets').replaceChildren();
  goals.forEach(goal => {
    const sets = workspace.sets.filter(s => s.client_id === clientId && s.goal_id === goal.id && !s.deleted_at && !s.superseded_by);
    const group = element('details', '', 'goal-set-group');
    group.open = expandedGoals.has(goal.id);
    group.ontoggle = () => { if (!group.isConnected) return; if (group.open) expandedGoals.add(goal.id); else expandedGoals.delete(goal.id); };
    group.append(element('summary', `${goal.title} · ${sets.length} problem set${sets.length === 1 ? '' : 's'}`));
    const contents = element('div', '', 'goal-set-contents');
    sets.forEach(s => {
      const row = element('article', '', 'saved-set');
      const heading = element('div', '', 'saved-set-heading'); heading.append(element('strong', s.title), element('span', s.published ? '(Assigned to client)' : '(Draft)')); row.append(heading);
      const actions = element('div', '', 'saved-set-actions');
    actions.append(button('Edit problem set', () => { if (!guardDraft()) return; setId = s.id; editingAssigned = Boolean(s.published); $('save').hidden = editingAssigned; $('publish').textContent = editingAssigned ? 'Save & update assignment' : 'Save & assign to client'; $('set-title').value = s.title; $('goal-input').value = s.goal_id; problems = structuredClone(s.problems); dirty = false; renderProblems(); $('editor').scrollIntoView({ behavior: 'smooth', block: 'start' }); if (editingAssigned) status('Saving updates the client’s assignment. Previous responses are kept; completed sets become available again as new practice.'); }));

      const remove = button('Delete problem set', () => deleteProblemSet(s)); remove.className += ' danger-button'; actions.append(remove); row.append(actions);
      contents.append(row);
    });
    if (!sets.length) contents.append(element('p', 'No problem sets for this goal yet.', 'empty-state'));
    const removeGoal = button('Delete goal', () => deleteGoal(goal)); removeGoal.className += ' danger-button';
    contents.append(removeGoal); group.append(contents); $('sets').append(group);
  });
  if (!goals.length) $('sets').append(element('p', 'Add a goal to organize your problem sets.'));
}

async function refresh() { workspace = await api('workspace'); render(); }
$('new-client').onsubmit = e => { e.preventDefault(); if (!guardDraft() || (profileDirty && !confirm('Discard unsaved client details?'))) return; action(async () => { const c = await api('clients', { name: $('new-name').value }); $('new-name').value = ''; clientId = c.id; profileDirty = false; detailsOpen = false; resetEditor(); await refresh(); status('Client added.'); }); };
$('client-details').oninput = () => { profileDirty = true; $('profile-status').textContent = 'Unsaved details'; };
$('close-details').onclick = () => {
  if (profileDirty && !confirm('Discard unsaved client details?')) return;
  profileDirty = false; detailsOpen = false; $('profile-status').textContent = ''; render();
  Array.from($('client-list').querySelectorAll('.client-more'))[workspace.clients.findIndex(c => c.id === clientId)]?.focus();
};
$('client-details').onsubmit = e => { e.preventDefault(); action(async () => {
  const details = Object.fromEntries(Object.entries(profileFields).map(([key, id]) => [key, $(id).value.trim()]));
  if (details.date_of_birth && details.date_of_birth > $('date-of-birth').max) throw new Error('Date of birth cannot be in the future.');
  await api('clients', { id: clientId, ...details }); profileDirty = false;
  await refresh(); $('profile-status').textContent = 'Details saved.'; status('Client details saved.');
}); };
$('pair').onclick = () => action(async () => { const r = await api('pair-code', { client_id: clientId }); $('pair-info').textContent = `Pairing code: ${r.code.match(/.{1,4}/g).join('-')} · valid for 10 minutes. In the iOS Simulator use http://127.0.0.1:8765. On an iPhone, use this Mac’s local network address with port 8765.`; });
$('add-question').onclick = () => { if (problems.length >= 30) return status('Up to 30 questions per set.', true); problems.push({ id: uid(), scenario: '', question: '', mode: 'multiple_choice', choices: [{ id: uid(), text: '' }, { id: uid(), text: '' }], correct_choice_id: null, explanation: '', expected_response: '', acceptance_criteria: '' }); dirty = true; renderProblems(); };
$('new-set').onclick = () => { if (guardDraft()) resetEditor(); };
$('set-title').oninput = $('goal-input').oninput = () => dirty = true;
async function save(publish) {
  if (!$('goal-input').value) throw new Error('Choose a goal first.');
  publish = publish || editingAssigned;
  const r = await api('sets', { id: setId, client_id: clientId, title: $('set-title').value, goal_id: $('goal-input').value, problems, publish }); setId = r.id; dirty = false;
  if (publish) resetEditor();
  await refresh(); status(publish ? 'Assigned. The client can now open this problem set in the app.' : 'Draft saved.');
}
$('save').onclick = () => action(() => save(false)); $('publish').onclick = () => action(() => save(true)); $('refresh').onclick = $('refresh-goals').onclick = () => action(refresh);
window.addEventListener('beforeunload', e => { if (dirty || profileDirty) { e.preventDefault(); e.returnValue = ''; } });
// Supervisor sign-in and startup are handled by supervisor.js.

function summaryLabel(summary) {
  if (!summary || summary.independence_percent === null) return 'Independence: no scored responses yet';
  return `${summary.independence_percent}% independence · ${summary.independent} independent / ${summary.scored} scored · ${summary.prompted} prompted${summary.unscored ? ` · ${summary.unscored} unscored` : ''}`;
}
$('new-goal').onsubmit = e => { e.preventDefault(); action(async () => {
  const goal = await api('goals', { client_id: clientId, title: $('new-goal-title').value, description: $('new-goal-description').value, mastery_criteria: $('new-goal-mastery').value });
  $('new-goal-title').value = ''; $('new-goal-description').value = ''; $('new-goal-mastery').value = ''; selectedGoalId = goal.id; await refresh(); $('goal-input').value = goal.id; status('Goal added. You can create several problem sets under it.');
}); };

function goalDays(goalId, now = new Date()) {
  const key = date => `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
  const days = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6 + index);
    return { date, key: key(date), independent: 0, scored: 0, unscored: 0, sessions: 0, percent: null };
  });
  const sets = new Set(workspace.sets.filter(s => s.client_id === clientId && s.goal_id === goalId).map(s => s.id));
  workspace.responses.filter(r => r.client_id === clientId && sets.has(r.set_id)).forEach(response => {
    const day = days.find(d => d.key === key(new Date(response.created * 1000)));
    if (!day) return;
    day.sessions++;
    (response.results || []).forEach(result => {
      if (typeof result.independent !== 'boolean') day.unscored++;
      else { day.scored++; if (result.independent) day.independent++; }
    });
  });
  days.forEach(day => { if (day.scored) day.percent = Math.round(day.independent / day.scored * 1000) / 10; });
  return days;
}
function renderGoals(goals) {
  $('goals').replaceChildren(); $('goal-detail').replaceChildren();
  if (!goals.length) {
    $('goals').append(element('p', 'Add your first goal to start tracking progress.', 'empty-state'));
    return;
  }
  goals.forEach(goal => {
    const b = button(goal.title + (goal.archived_at ? ' · Mastered' : ''), () => {
      selectedGoalId = goal.id; renderGoals(goals);
      Array.from($('goals').children).find(child => child.getAttribute('aria-pressed') === 'true')?.focus();
    });
    b.className = 'goal-button'; b.setAttribute('aria-pressed', String(goal.id === selectedGoalId));
    b.setAttribute('aria-controls', 'goal-detail'); $('goals').append(b);
  });
  const goal = goals.find(g => g.id === selectedGoalId);
  if (!goal) return;
  const days = goalDays(goal.id), scored = days.reduce((sum, d) => sum + d.scored, 0);
  const independent = days.reduce((sum, d) => sum + d.independent, 0);
  const unscored = days.reduce((sum, d) => sum + d.unscored, 0);
  const sessions = days.reduce((sum, d) => sum + d.sessions, 0);
  const detail = $('goal-detail');
  detail.append(element('h3', goal.title, 'goal-title'));
  if (goal.description) detail.append(element('p', goal.description, 'goal-description'));
  detail.append(element('h4', 'Mastery criteria'), element('p', goal.mastery_criteria || 'No mastery criteria entered yet.', 'goal-description'));
  const goalEditor = element('details'); goalEditor.append(element('summary', 'Edit goal'));
  const editForm = element('form');
  const titleLabel = element('label', 'Goal title'), titleInput = element('input'); titleInput.value = goal.title; titleInput.required = true; titleInput.maxLength = 4000; titleLabel.append(titleInput);
  const descriptionLabel = element('label', 'Goal description'), descriptionInput = element('textarea'); descriptionInput.value = goal.description || ''; descriptionInput.maxLength = 4000; descriptionInput.rows = 3; descriptionLabel.append(descriptionInput);
  const masteryLabel = element('label', 'Mastery criteria'), masteryInput = element('textarea'); masteryInput.value = goal.mastery_criteria || ''; masteryInput.maxLength = 4000; masteryInput.rows = 3; masteryLabel.append(masteryInput);
  const saveGoal = element('button', 'Save goal', 'secondary-button'); saveGoal.type = 'submit';
  editForm.append(titleLabel, descriptionLabel, masteryLabel, element('p', 'Rewriting this goal keeps its assigned problem sets and existing progress. Create a new goal if the next level should have separate progress.', 'sample-note'), saveGoal);
  editForm.onsubmit = e => { e.preventDefault(); action(async () => {
    if (!titleInput.value.trim()) throw new Error('Enter a goal title.');
    await api('goals', { id: goal.id, client_id: clientId, title: titleInput.value.trim(), description: descriptionInput.value, mastery_criteria: masteryInput.value });
    await refresh(); status('Goal title, description, and mastery criteria saved.');
  }); };
  goalEditor.append(editForm); detail.append(goalEditor);
  if (goal.archived_at) detail.append(element('p', `Mastered and archived ${new Date(goal.archived_at * 1000).toLocaleDateString()}. Previous results are retained.`, 'sample-note'));
  detail.append(button(goal.archived_at ? 'Restore goal to active practice' : 'Mark mastered & archive', () => changeGoalArchive(goal)));
  const metric = element('div', '', 'goal-metric');
  metric.append(element('strong', scored ? `${Math.round(independent / scored * 1000) / 10}%` : '—'), element('span', 'independence · last 7 days'));
  detail.append(metric, element('p', `${independent} independent / ${scored} scored answers · ${sessions} completed practice${sessions === 1 ? '' : 's'}${unscored ? ` · ${unscored} unscored answers excluded` : ''}`, 'sample-note'));
  detail.append(element('p', 'Independence means answering correctly without an in-app hint. Each completed practice contributes to the percentage; help outside the app is not measured.', 'sample-note'));
  const ns = 'http://www.w3.org/2000/svg';
  const svgNode = (tag, attributes, text) => { const node = document.createElementNS(ns, tag); Object.entries(attributes).forEach(([k, v]) => node.setAttribute(k, v)); if (text) node.textContent = text; return node; };
  const svg = svgNode('svg', { viewBox: '0 0 640 260', role: 'img', 'aria-labelledby': 'chart-title chart-desc', class: 'goal-chart' });
  svg.append(svgNode('title', { id: 'chart-title' }, 'Daily independence for the last seven days'), svgNode('desc', { id: 'chart-desc' }, 'Percentage of scored answers completed independently, grouped by completion date in your local time zone. Days with no scored answers are shown at zero percent and labeled as no scored data. A table of exact values follows.'));
  const x = i => 54 + i * 90, y = value => 205 - value * 1.65;
  [0, 25, 50, 75, 100].forEach(value => {
    svg.append(svgNode('line', { x1: 54, x2: 594, y1: y(value), y2: y(value), stroke: '#e8ddc9' }), svgNode('text', { x: 44, y: y(value) + 4, 'text-anchor': 'end', class: 'chart-label' }, `${value}%`));
  });
  // Zero is a display placeholder only; unrecorded days never enter the scored average.
  const displayPercent = day => day.percent ?? 0;
  const tooltip = svgNode('g', { visibility: 'hidden', 'pointer-events': 'none', class: 'chart-tooltip' });
  const tooltipDate = svgNode('text', { x: 12, y: 21, fill: '#fffdf8', 'font-size': 13 });
  const tooltipValue = svgNode('text', { x: 12, y: 42, fill: '#fffdf8', 'font-size': 13, 'font-weight': 700 });
  tooltip.append(svgNode('rect', { width: 220, height: 56, rx: 9, fill: '#51331f' }), tooltipDate, tooltipValue);
  const points = [];
  days.forEach((day, i) => {
    svg.append(svgNode('text', { x: x(i), y: 230, 'text-anchor': 'middle', class: 'chart-label' }, day.date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })));
    if (i) svg.append(svgNode('line', { x1: x(i - 1), y1: y(displayPercent(days[i - 1])), x2: x(i), y2: y(displayPercent(day)), stroke: '#a33b1f', 'stroke-width': 3, class: 'chart-segment' }));
    const percent = displayPercent(day);
    const label = `${day.date.toLocaleDateString()}: ${percent}% (${day.percent === null ? 'no scored data' : `${day.independent} of ${day.scored} independent`})`;
    const point = svgNode('circle', { cx: x(i), cy: y(percent), r: 6, fill: day.percent === null ? '#fffdf8' : '#a33b1f', stroke: '#a33b1f', 'stroke-width': 2, tabindex: 0, 'aria-label': label, class: 'chart-point' });
    point.append(svgNode('title', {}, label));
    const show = () => {
      tooltipDate.textContent = day.date.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
      tooltipValue.textContent = `${percent}% · ${day.percent === null ? 'No scored data' : `${day.independent} / ${day.scored} independent`}`;
      tooltip.setAttribute('transform', `translate(${Math.max(8, Math.min(412, x(i) - 110))},${Math.max(4, y(percent) - 66)})`);
      tooltip.setAttribute('visibility', 'visible');
    };
    const hide = () => tooltip.setAttribute('visibility', 'hidden');
    point.addEventListener('pointerenter', show);
    point.addEventListener('pointerleave', hide);
    point.addEventListener('focus', show);
    point.addEventListener('blur', hide);
    point.addEventListener('click', show);
    point.addEventListener('keydown', event => { if (event.key === 'Escape') hide(); });
    points.push(point);
  });
  svg.append(...points, tooltip);
  detail.append(svg);
  detail.append(element('p', 'Dates use this device’s time zone. Hollow dots at 0% mean no scored data that day and do not affect the overall percentage. Hover or focus a dot to see daily numbers.', 'sample-note'));
  const tableDetails = element('details', '', 'chart-data'); tableDetails.append(element('summary', 'View daily numbers'));
  const table = element('table'), head = element('thead'), headRow = element('tr');
  ['Date', 'Independence', 'Independent / scored'].forEach(label => { const th = element('th', label); th.scope = 'col'; headRow.append(th); });
  head.append(headRow); table.append(head); const body = element('tbody');
  days.forEach(day => { const row = element('tr'); row.append(element('td', day.date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })), element('td', day.percent === null ? '0% (no scored data)' : `${day.percent}%`), element('td', `${day.independent} / ${day.scored}`)); body.append(row); });
  table.append(body); tableDetails.append(table); detail.append(tableDetails);
  const removeGoal = button('Delete goal', () => deleteGoal(goal)); removeGoal.className += ' danger-button'; detail.append(removeGoal);
  if (!goal.archived_at) detail.append(button('Add problem set for this goal', () => { if (!guardDraft()) return; resetEditor(); $('goal-input').value = goal.id; $('editor').scrollIntoView({ behavior: 'smooth' }); }));
}

$('show-archived').onchange = render;
$('session-history-link').onclick = e => { if (!guardDraft() || (profileDirty && !confirm('Discard unsaved client details?'))) e.preventDefault(); };
$('delete-client').onclick = () => {
  const client = workspace.clients.find(c => c.id === clientId);
  if (!client || !confirm(`Delete ${client.name} from your client list and disconnect their apps? This ends access to their active case. Historical records will be retained.`)) return;
  action(async () => { await api('clients/delete', { client_id: clientId }); clientId = null; selectedGoalId = null; profileDirty = false; detailsOpen = false; resetEditor(); await refresh(); status('Client deleted from the active client list.'); });
};
function changeGoalArchive(goal) {
  const restore = Boolean(goal.archived_at);
  if (!restore && !confirm(`Mark “${goal.title}” as mastered and archive it? Its problem sets will leave active practice, and its results will remain available.`)) return;
  if (!guardDraft()) return;
  action(async () => { await api(`goals/${restore ? 'restore' : 'archive'}`, { id: goal.id, client_id: clientId }); resetEditor(); await refresh(); status(restore ? 'Goal restored to active practice.' : 'Goal mastered and archived. Use Show mastered / archived goals to review it.'); });
}
function renderRbtClients() {
  const checked = new Set(Array.from($('rbt-clients').querySelectorAll('input:checked')).map(input => input.value));
  $('rbt-clients').replaceChildren();
  workspace.clients.forEach(client => { const label = element('label', '', 'inline-check'); const input = element('input'); input.type = 'checkbox'; input.value = client.id; input.checked = checked.has(client.id); label.append(input, element('span', client.name)); $('rbt-clients').append(label); });
  if (!workspace.clients.length) $('rbt-clients').append(element('p', 'Add a client first.', 'sample-note'));
}
$('rbt-pair-form').onsubmit = e => { e.preventDefault(); action(async () => {
  const client_ids = Array.from($('rbt-clients').querySelectorAll('input:checked')).map(input => input.value);
  if (!client_ids.length) throw new Error('Select at least one client for the RBT.');
  const result = await api('rbt/pair-code', { client_ids, provider_name: $('rbt-provider').value.trim(), credentials: $('rbt-credentials').value.trim(), title: $('rbt-title').value.trim() });
  $('rbt-pair-info').textContent = `RBT pairing code: ${result.code.match(/.{1,4}/g).join('-')} · valid for ${result.expires_minutes || 10} minutes. Enter this in the RBT app with this server’s address.`;
}); };
