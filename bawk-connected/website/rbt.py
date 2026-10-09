"""Scoped RBT access and persisted session records for the local prototype."""
import hashlib
import json
import secrets
import time
from uuid import uuid4

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS rbt_providers(id TEXT PRIMARY KEY, supervisor_id TEXT NOT NULL REFERENCES supervisors(id), name TEXT NOT NULL, credentials TEXT NOT NULL, title TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS rbt_assignments(provider_id TEXT NOT NULL REFERENCES rbt_providers(id), client_id TEXT NOT NULL REFERENCES clients(id), PRIMARY KEY(provider_id,client_id));
    CREATE TABLE IF NOT EXISTS rbt_pairing(code_hash TEXT PRIMARY KEY, provider_id TEXT NOT NULL REFERENCES rbt_providers(id), expires REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS rbt_devices(token_hash TEXT PRIMARY KEY, provider_id TEXT NOT NULL REFERENCES rbt_providers(id));
    CREATE TABLE IF NOT EXISTS rbt_sessions(id TEXT PRIMARY KEY, provider_id TEXT NOT NULL REFERENCES rbt_providers(id), client_id TEXT NOT NULL REFERENCES clients(id), request_id TEXT NOT NULL, started_at REAL NOT NULL, ended_at REAL, counts TEXT NOT NULL DEFAULT '[]', fields TEXT NOT NULL DEFAULT '{}', note_text TEXT NOT NULL DEFAULT '', UNIQUE(provider_id,request_id));
    CREATE UNIQUE INDEX IF NOT EXISTS rbt_one_active ON rbt_sessions(provider_id) WHERE ended_at IS NULL;
    ''')

def provider(handler, db):
    auth = handler.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    return db.execute('SELECT p.* FROM rbt_providers p JOIN rbt_devices d ON d.provider_id=p.id WHERE d.token_hash=?',(digest(auth[7:]),)).fetchone()

def session_dict(db, row):
    item = dict(row)
    item['counts'], item['fields'] = json.loads(item['counts']), json.loads(item['fields'])
    client = db.execute('SELECT name FROM clients WHERE id=?',(row['client_id'],)).fetchone()
    p = db.execute('SELECT * FROM rbt_providers WHERE id=?',(row['provider_id'],)).fetchone()
    item.update(client_name=client['name'], provider_name=p['name'], credentials=p['credentials'], title=p['title'])
    return item

def supervisor_notes(db, supervisor_id):
    return [session_dict(db,r) for r in db.execute('SELECT s.* FROM rbt_sessions s JOIN clients c ON c.id=s.client_id WHERE c.supervisor_id=? AND s.ended_at IS NOT NULL ORDER BY s.ended_at DESC',(supervisor_id,))]

def workspace(handler, db):
    p = provider(handler, db)
    if not p:
        return handler.reply(401, {'error':'Connect your RBT app using a supervisor pairing code.'})
    clients = []
    for row in db.execute('SELECT c.id,c.name FROM clients c JOIN rbt_assignments a ON a.client_id=c.id WHERE a.provider_id=? AND c.deleted_at IS NULL ORDER BY c.name',(p['id'],)):
        client = dict(row)
        client['goals'] = [dict(g) for g in db.execute('SELECT id,title,description,mastery_criteria FROM goals WHERE client_id=? AND deleted_at IS NULL AND archived_at IS NULL ORDER BY rowid',(row['id'],))]
        clients.append(client)
    sessions = [session_dict(db,r) for r in db.execute('SELECT s.* FROM rbt_sessions s JOIN clients c ON c.id=s.client_id WHERE s.provider_id=? AND c.deleted_at IS NULL ORDER BY s.started_at DESC',(p['id'],))]
    return handler.reply(200, {'provider':{'name':p['name'],'credentials':p['credentials'],'title':p['title']},'clients':clients,'sessions':sessions})

def string(value, label, limit=4000, required=False):
    if not isinstance(value,str) or len(value)>limit or (required and not value.strip()):
        raise ValueError(f'Enter valid {label} (maximum {limit} characters).')
    return value.strip()

def post(handler, db, path, body):
    if path == '/api/rbt/pair-code':
        supervisor = handler.supervisor()
        if not supervisor:
            return handler.reply(401, {'error':'Sign in to your supervisor account.'})
        origin = handler.headers.get('Origin')
        if origin and origin != 'http://' + handler.headers.get('Host',''):
            return handler.reply(403, {'error':'Request origin not allowed.'})
        ids = body.get('client_ids')
        if not isinstance(ids,list) or not 1 <= len(ids) <= 100 or len(set(ids)) != len(ids):
            raise ValueError('Select at least one assigned client.')
        for cid in ids:
            if not db.execute('SELECT id FROM clients WHERE id=? AND supervisor_id=? AND deleted_at IS NULL',(cid,supervisor['id'])).fetchone():
                return handler.reply(404, {'error':'Assigned client not found.'})
        pid = str(uuid4())
        db.execute('INSERT INTO rbt_providers VALUES (?,?,?,?,?)',(pid,supervisor['id'], string(body.get('provider_name'),'provider name',200,True),string(body.get('credentials',''),'credentials',100),string(body.get('title','RBT'),'provider title',100)))
        db.executemany('INSERT INTO rbt_assignments VALUES (?,?)',[(pid,cid) for cid in ids])
        code = secrets.token_hex(6).upper()
        db.execute('INSERT INTO rbt_pairing VALUES (?,?,?)',(digest(code),pid,time.time()+600))
        db.commit()
        return handler.reply(200, {'code':code,'expires_minutes':10})
    if path == '/api/rbt/pair':
        code = string(body.get('code'),'pairing code',100,True).upper().replace('-','').replace(' ','')
        row = db.execute('DELETE FROM rbt_pairing WHERE code_hash=? AND expires>? RETURNING provider_id',(digest(code),time.time())).fetchone()
        if not row:
            return handler.reply(401, {'error':'Code expired or incorrect. Ask your supervisor for a new code.'})
        token = secrets.token_urlsafe(32)
        db.execute('INSERT INTO rbt_devices VALUES (?,?)',(digest(token),row['provider_id']))
        db.commit()
        return handler.reply(200, {'token':token})
    db.execute('BEGIN IMMEDIATE')
    p = provider(handler,db)
    if not p:
        return handler.reply(401, {'error':'Connect your RBT app again.'})
    if path == '/api/rbt/start':
        cid = body.get('client_id')
        if not db.execute('SELECT c.id FROM clients c JOIN rbt_assignments a ON a.client_id=c.id WHERE c.id=? AND a.provider_id=? AND c.deleted_at IS NULL',(cid,p['id'])).fetchone():
            return handler.reply(404, {'error':'Assigned client not found.'})
        request = string(body.get('request_id'),'session request',100,True)
        row = db.execute('SELECT * FROM rbt_sessions WHERE provider_id=? AND request_id=?',(p['id'],request)).fetchone()
        if row and row['client_id'] != cid:
            raise ValueError('Session request already used for another client.')
        if not row:
            row = db.execute('SELECT * FROM rbt_sessions WHERE provider_id=? AND ended_at IS NULL',(p['id'],)).fetchone()
            if row and row['client_id'] != cid:
                return handler.reply(409, {'error':'Finish your current session before starting another client.'})
        if not row:
            sid = str(uuid4())
            db.execute('INSERT INTO rbt_sessions(id,provider_id,client_id,request_id,started_at) VALUES (?,?,?,?,?)',(sid,p['id'],cid,request,time.time()))
            row = db.execute('SELECT * FROM rbt_sessions WHERE id=?',(sid,)).fetchone()
        db.commit()
        return handler.reply(200, session_dict(db,row))
    if path not in ('/api/rbt/save','/api/rbt/submit'):
        return handler.reply(404, {'error':'Not found'})
    row = db.execute('SELECT s.* FROM rbt_sessions s JOIN rbt_assignments a ON a.provider_id=s.provider_id AND a.client_id=s.client_id JOIN clients c ON c.id=s.client_id WHERE s.id=? AND s.provider_id=? AND c.deleted_at IS NULL',(body.get('session_id'),p['id'])).fetchone()
    if not row:
        return handler.reply(404, {'error':'Session not found.'})
    if row['ended_at'] is not None:
        if path.endswith('/save'):
            return handler.reply(409, {'error':'Submitted notes are archived and cannot be changed.'})
        return handler.reply(200, session_dict(db,row))
    counts = body.get('counts',[])
    fields = body.get('fields',{})
    if not isinstance(counts,list) or len(counts)>500 or not isinstance(fields,dict) or len(fields)>50:
        raise ValueError('Invalid session data.')
    cleaned=[]; seen=set()
    for count in counts:
        if not isinstance(count,dict):
            raise ValueError('Invalid goal counts.')
        gid=count.get('goal_id')
        goal=db.execute('SELECT title FROM goals WHERE id=? AND client_id=?',(gid,row['client_id'])).fetchone()
        if not goal or gid in seen:
            raise ValueError('Each recorded goal must belong to this client and occur once.')
        seen.add(gid)
        result={'goal_id':gid,'goal_title':goal['title']}
        for key in ('independent','prompted','no_response'):
            value=count.get(key,0)
            if type(value) is not int or not 0<=value<=100000:
                raise ValueError('Goal counts must be whole numbers from 0 to 100000.')
            result[key]=value
        cleaned.append(result)
    fields={string(k,'field name',100,True):string(v,'note field',10000) for k,v in fields.items()}
    note=string(body.get('note_text',''),'session note',60000,path.endswith('/submit'))
    ended=time.time() if path.endswith('/submit') else None
    db.execute('UPDATE rbt_sessions SET counts=?,fields=?,note_text=?,ended_at=? WHERE id=?',(json.dumps(cleaned),json.dumps(fields),note,ended,row['id']))
    db.commit()
    return handler.reply(200,session_dict(db,db.execute('SELECT * FROM rbt_sessions WHERE id=?',(row['id'],)).fetchone()))
