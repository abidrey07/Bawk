const $ = id => document.getElementById(id);
const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
let archive = { clients: [], session_notes: [] }, account = null, requestId = null, saving = false, changed = false;
const selected = new URLSearchParams(location.search).get('client') || '';
async function api(body) {
  const response = await fetch('/api/session-notes', {credentials:'same-origin', ...(body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {})});
  const data = await response.json();
  if (response.status === 401) { $('archive-workspace').hidden = true; $('archive-list').replaceChildren(); $('archive-login').hidden = false; archive = {clients:[],session_notes:[]}; }
  if (!response.ok) throw new Error(data.error || 'Could not load session notes.');
  return data;
}
function option(value, label) { const o = el('option',label); o.value = value; return o; }
async function refresh(initial = false) {
  $('archive-refresh').disabled = true;
  try {
    const previous = initial ? selected : $('archive-client').value;
    archive = await api(); account = archive.supervisor;
    $('archive-client').replaceChildren(option('', 'All clients'));
    archive.clients.forEach(c => $('archive-client').append(option(c.id,c.name + (c.deleted_at ? ' (closed case)' : ''))));
    $('archive-client').value = archive.clients.some(c => c.id === previous) ? previous : '';
    $('archive-workspace').hidden = false; $('archive-login').hidden = true;
    $('new-note').disabled = !archive.clients.some(c => !c.deleted_at);
    $('archive-status').textContent = ''; render();
  } catch (error) { $('archive-status').textContent = error.message; }
  finally { $('archive-refresh').disabled = false; }
}
function render() {
  const notes = archive.session_notes.filter(n => (!$('archive-client').value || n.client_id === $('archive-client').value) && (!$('archive-role').value || n.author_role === $('archive-role').value));
  $('archive-list').replaceChildren(); $('archive-count').textContent = `${notes.length} archived note${notes.length === 1 ? '' : 's'}`;
  if (!notes.length) { $('archive-list').append(el('p','No session notes match these filters. Submitted RBT notes and BCBA or student analyst notes will appear here.','empty-state')); return; }
  for (const note of notes) {
    const card = el('details',undefined,'session-note panel'), summary = el('summary');
    const start = new Date(note.started_at * 1000), end = new Date(note.ended_at * 1000);
    summary.append(el('span',note.author_role,'note-role'), el('strong',note.client_name),el('span',`${start.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'})} · ${note.provider_name}`,'note-meta'));
    const body = el('div',undefined,'session-note-body');
    body.append(el('p',`${start.toLocaleString()} – ${end.toLocaleString()}`,'sample-note'));
    if (note.recorded_by) body.append(el('p',`Recorded by ${note.recorded_by} · ${new Date(note.created * 1000).toLocaleString()}`,'sample-note'));
    if (note.counts?.length) {
      const table = el('table',undefined,'session-data'), head = el('thead'), hr = el('tr');
      ['Goal','Independent','Prompted','No response','Independence'].forEach(v => { const th = el('th',v); th.scope='col'; hr.append(th); }); head.append(hr); table.append(head);
      const rows = el('tbody');
      note.counts.forEach(c => { const tr=el('tr'), total=c.independent+c.prompted+c.no_response; [c.goal_title || 'Goal',c.independent,c.prompted,c.no_response,total ? `${Math.round(c.independent / total * 1000) / 10}%` : 'No trials'].forEach(v=>tr.append(el('td',String(v)))); rows.append(tr); });
      table.append(rows); const wrap=el('div',undefined,'session-data-wrap'); wrap.append(table); body.append(wrap);
    }
    body.append(el('p',note.note_text || 'No note text available.','session-note-text')); card.append(summary,body); $('archive-list').append(card);
  }
}
$('archive-client').onchange = render; $('archive-role').onchange = render;
$('archive-refresh').onclick = () => refresh();
const localTime = date => { const d = new Date(date.getTime() - date.getTimezoneOffset()*60000); return d.toISOString().slice(0,16); };
$('new-note').onclick = () => {
  $('staff-note-form').reset(); $('note-status').textContent = ''; requestId = crypto.randomUUID(); changed = false;
  $('note-client').replaceChildren(option('','Choose a client'));
  archive.clients.filter(c=>!c.deleted_at).forEach(c=>$('note-client').append(option(c.id,c.name)));
  if (archive.clients.some(c=>!c.deleted_at && c.id === $('archive-client').value)) $('note-client').value = $('archive-client').value;
  $('note-author').value = [account.first_name,account.last_name].filter(Boolean).join(' ');
  $('note-recorder').textContent = `Recorded under ${$('note-author').value}’s supervisor account.`;
  $('note-end').value = localTime(new Date()); $('note-start').value = localTime(new Date(Date.now()-3600000));
  $('note-dialog').showModal(); $('note-client').focus();
};
$('staff-note-form').oninput = () => { changed = true; };
function closeNote(event) { if (saving || (changed && !confirm('Discard this unsaved session note?'))) { event?.preventDefault(); return; } $('note-dialog').close(); changed=false; }
$('note-cancel').onclick = closeNote; $('note-dialog').oncancel = closeNote;
window.addEventListener('beforeunload', e => { if (changed) { e.preventDefault(); e.returnValue=''; } });
$('staff-note-form').onsubmit = async event => {
  event.preventDefault(); if (saving) return;
  const body = {request_id:requestId,client_id:$('note-client').value,author_role:$('note-role').value,provider_name:$('note-author').value.trim(),started_at:new Date($('note-start').value).getTime()/1000,ended_at:new Date($('note-end').value).getTime()/1000,note_text:$('note-body').value.trim()};
  if (!body.note_text || !body.provider_name || !Number.isFinite(body.started_at) || !Number.isFinite(body.ended_at) || body.started_at > body.ended_at || body.ended_at > Date.now()/1000+60) { $('note-status').textContent='Enter the author, note, and valid session times. The end cannot be before the start or in the future.'; return; }
  saving=true; $('staff-note-form').querySelectorAll('input,select,textarea,button').forEach(n=>n.disabled=true); $('note-status').textContent='Saving…';
  try { await api(body); changed=false; $('note-dialog').close(); $('archive-role').value=''; await refresh(); $('archive-client').value=body.client_id; render(); $('archive-status').textContent='Session note submitted and archived.'; }
  catch(error) { $('note-status').textContent=error.message; }
  finally { saving=false; $('staff-note-form').querySelectorAll('input,select,textarea,button').forEach(n=>n.disabled=false); }
};
refresh(true);
