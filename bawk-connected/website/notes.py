"""Supervisor-managed BCBA/student notes and a unified session archive."""
import math
import time
from uuid import uuid4
from rbt import string, supervisor_notes

def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS staff_session_notes(
        id TEXT PRIMARY KEY, supervisor_id TEXT NOT NULL REFERENCES supervisors(id),
        client_id TEXT NOT NULL REFERENCES clients(id), request_id TEXT NOT NULL,
        author_role TEXT NOT NULL, provider_name TEXT NOT NULL, started_at REAL NOT NULL,
        ended_at REAL NOT NULL, note_text TEXT NOT NULL, created REAL NOT NULL,
        UNIQUE(supervisor_id,request_id))''')

def get_archive(handler, db):
    supervisor = handler.supervisor()
    if not supervisor:
        return handler.reply(401, {'error':'Sign in to your supervisor account to view session notes.'})
    clients = [dict(r) for r in db.execute('SELECT id,name,deleted_at FROM clients WHERE supervisor_id=? ORDER BY name',(supervisor['id'],))]
    notes = supervisor_notes(db, supervisor['id'])
    for note in notes:
        note.update(author_role='RBT', source='rbt')
    for r in db.execute('''SELECT n.*, c.name AS client_name, s.first_name, s.last_name
        FROM staff_session_notes n JOIN clients c ON c.id=n.client_id
        JOIN supervisors s ON s.id=n.supervisor_id WHERE n.supervisor_id=? AND c.supervisor_id=?''',(supervisor['id'],supervisor['id'])):
        item=dict(r)
        item['recorded_by']=' '.join(filter(None,[item.pop('first_name'),item.pop('last_name')]))
        item.update(source='staff',counts=[])
        notes.append(item)
    notes.sort(key=lambda n:n['started_at'],reverse=True)
    return handler.reply(200, {'clients':clients,'session_notes':notes,'supervisor':supervisor})

def submit_note(handler, db, body):
    supervisor=handler.supervisor()
    if not supervisor:
        return handler.reply(401, {'error':'Sign in to your supervisor account.'})
    origin=handler.headers.get('Origin')
    if origin and origin!='http://'+handler.headers.get('Host',''):
        return handler.reply(403, {'error':'Request origin not allowed.'})
    cid=body.get('client_id')
    if not db.execute('SELECT id FROM clients WHERE id=? AND supervisor_id=? AND deleted_at IS NULL',(cid,supervisor['id'])).fetchone():
        return handler.reply(404, {'error':'Active client not found.'})
    role=body.get('author_role')
    if role not in ('BCBA','Student analyst'):
        raise ValueError('Choose BCBA or Student analyst.')
    name=string(body.get('provider_name'),'author full name',200,True)
    note=string(body.get('note_text'),'session note',60000,True)
    request=string(body.get('request_id'),'submission ID',100,True)
    start,end=body.get('started_at'),body.get('ended_at')
    if any(type(v) not in (float,int) or not math.isfinite(v) for v in (start,end)) or not 0<start<=end<=time.time()+60:
        raise ValueError('Enter valid session times: end must follow start and cannot be in the future.')
    db.execute('BEGIN IMMEDIATE')
    old=db.execute('SELECT * FROM staff_session_notes WHERE supervisor_id=? AND request_id=?',(supervisor['id'],request)).fetchone()
    if old:
        if (old['client_id'],old['author_role'],old['provider_name'],old['started_at'],old['ended_at'],old['note_text'])!=(cid,role,name,start,end,note):
            return handler.reply(409, {'error':'This submission was already saved. Refresh the archive before adding another note.'})
        return handler.reply(200, {'id':old['id']})
    nid=str(uuid4())
    db.execute('INSERT INTO staff_session_notes VALUES (?,?,?,?,?,?,?,?,?,?)',(nid,supervisor['id'],cid,request,role,name,start,end,note,time.time()))
    db.commit()
    return handler.reply(200, {'id':nid})
