#!/usr/bin/env python3
"""Bawk local development bridge. Website and paired iOS devices share SQLite data.
Run on a trusted local network; deploy behind HTTPS/auth before real client use.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import time
from datetime import date
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DB = Path(os.environ.get('BAWK_DB', str(ROOT / 'data' / 'bawk.sqlite3')))
SESSION_DAYS = 7

def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def initialize():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS clients(id TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sets(id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), goal TEXT NOT NULL, title TEXT NOT NULL, problems TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS pairing(code_hash TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS devices(token_hash TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id));
        CREATE TABLE IF NOT EXISTS responses(id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), set_id TEXT NOT NULL REFERENCES sets(id), answers TEXT NOT NULL, results TEXT NOT NULL, created REAL NOT NULL, UNIQUE(client_id,set_id));
        ''')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS goals(id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), title TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS attempts(request_id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), set_id TEXT NOT NULL REFERENCES sets(id), problem_id TEXT NOT NULL, choice_id TEXT NOT NULL, correct INTEGER NOT NULL, created REAL NOT NULL);
        ''')
        for table in ('goals', 'sets'):
            if 'deleted_at' not in {r['name'] for r in db.execute(f'PRAGMA table_info({table})')}:
                db.execute(f'ALTER TABLE {table} ADD COLUMN deleted_at REAL')
        if 'deleted_at' not in {r['name'] for r in db.execute('PRAGMA table_info(clients)')}:
            db.execute('ALTER TABLE clients ADD COLUMN deleted_at REAL')
        goal_columns = {r['name'] for r in db.execute('PRAGMA table_info(goals)')}
        if 'description' not in goal_columns:
            db.execute("ALTER TABLE goals ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        for column, declaration in [('mastery_criteria', "TEXT NOT NULL DEFAULT ''"), ('archived_at', 'REAL')]:
            if column not in goal_columns:
                db.execute(f'ALTER TABLE goals ADD COLUMN {column} {declaration}')
        db.executescript("""
        CREATE TABLE IF NOT EXISTS supervisors(id TEXT PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL DEFAULT '', email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, photo TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS supervisor_sessions(token_hash TEXT PRIMARY KEY, supervisor_id TEXT NOT NULL REFERENCES supervisors(id), expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS login_limits(email TEXT PRIMARY KEY, failures INTEGER NOT NULL, blocked_until REAL NOT NULL);
        """)
        supervisor_columns = {r['name'] for r in db.execute('PRAGMA table_info(supervisors)')}
        if 'first_name' not in supervisor_columns:
            # Preserve the complete legacy name; never guess a multi-word first name.
            db.execute('ALTER TABLE supervisors RENAME COLUMN name TO first_name')
        if 'last_name' not in supervisor_columns:
            db.execute("ALTER TABLE supervisors ADD COLUMN last_name TEXT NOT NULL DEFAULT ''")
        client_columns = {r['name'] for r in db.execute('PRAGMA table_info(clients)')}
        if 'supervisor_id' not in client_columns:
            db.execute('ALTER TABLE clients ADD COLUMN supervisor_id TEXT REFERENCES supervisors(id)')
        for field in ('first_name','last_name','date_of_birth','caregiver_1','caregiver_2','address'):
            if field not in client_columns:
                db.execute(f"ALTER TABLE clients ADD COLUMN {field} TEXT NOT NULL DEFAULT ''")
        if 'first_name' not in client_columns:
            for client in db.execute('SELECT id,name FROM clients').fetchall():
                first, _, last = client['name'].strip().partition(' ')
                db.execute('UPDATE clients SET first_name=?,last_name=? WHERE id=?',(first,last.strip(),client['id']))
        db.execute("CREATE TABLE IF NOT EXISTS chicken_state(client_id TEXT PRIMARY KEY REFERENCES clients(id), level REAL NOT NULL, updated_at REAL NOT NULL)")
        # Begin decay at migration time, preserving the old visible fullness once.
        db.execute("INSERT OR IGNORE INTO chicken_state SELECT c.id, MIN(100,COUNT(r.id)*20), ? FROM clients c LEFT JOIN responses r ON r.client_id=c.id GROUP BY c.id", (time.time(),))
        # Each replay has its own progress and immutable completion. Preserve old history.
        db.execute("CREATE TABLE IF NOT EXISTS practice_runs(id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), set_id TEXT NOT NULL REFERENCES sets(id), created REAL NOT NULL, completed REAL)")
        if 'run_id' not in {r['name'] for r in db.execute('PRAGMA table_info(responses)')}:
            db.execute("ALTER TABLE responses RENAME TO legacy_responses")
            db.execute("CREATE TABLE responses(id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES clients(id), set_id TEXT NOT NULL REFERENCES sets(id), answers TEXT NOT NULL, results TEXT NOT NULL, created REAL NOT NULL, run_id TEXT UNIQUE REFERENCES practice_runs(id))")
            db.execute("INSERT INTO practice_runs SELECT id,client_id,set_id,created,created FROM legacy_responses")
            db.execute("INSERT INTO responses SELECT id,client_id,set_id,answers,results,created,id FROM legacy_responses")
            db.execute("DROP TABLE legacy_responses")
        if 'run_id' not in {r['name'] for r in db.execute('PRAGMA table_info(attempts)')}:
            db.execute("ALTER TABLE attempts ADD COLUMN run_id TEXT REFERENCES practice_runs(id)")
        db.execute('CREATE TABLE IF NOT EXISTS seed_rewards(run_id TEXT PRIMARY KEY REFERENCES practice_runs(id), client_id TEXT NOT NULL REFERENCES clients(id), amount INTEGER NOT NULL, attempt INTEGER NOT NULL)')
        # Preserve previously earned rewards when upgrading existing installations.
        db.execute('INSERT OR IGNORE INTO seed_rewards SELECT id,client_id,30,1 FROM practice_runs WHERE completed IS NOT NULL')
        from rbt import initialize as initialize_rbt
        initialize_rbt(db)
        for old in db.execute("SELECT DISTINCT client_id,set_id FROM attempts WHERE run_id IS NULL").fetchall():
            run = db.execute("SELECT id FROM practice_runs WHERE client_id=? AND set_id=? ORDER BY created DESC LIMIT 1", tuple(old)).fetchone()
            rid = run['id'] if run else str(uuid4())
            if not run:
                db.execute("INSERT INTO practice_runs VALUES (?,?,?,?,NULL)", (rid,old['client_id'],old['set_id'],time.time()))
            db.execute("UPDATE attempts SET run_id=? WHERE client_id=? AND set_id=? AND run_id IS NULL", (rid,old['client_id'],old['set_id']))
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_active_run ON practice_runs(client_id,set_id) WHERE completed IS NULL")
        db.execute("CREATE INDEX IF NOT EXISTS attempts_by_run ON attempts(run_id,problem_id)")
        columns = {row['name'] for row in db.execute('PRAGMA table_info(sets)')}
        if 'superseded_by' not in columns:
            db.execute('ALTER TABLE sets ADD COLUMN superseded_by TEXT')
        if 'goal_id' not in columns:
            db.execute('ALTER TABLE sets ADD COLUMN goal_id TEXT REFERENCES goals(id)')
        for row in db.execute('SELECT id,client_id,goal FROM sets WHERE goal_id IS NULL').fetchall():
            goal = db.execute('SELECT id FROM goals WHERE client_id=? AND title=? AND deleted_at IS NULL', (row['client_id'], row['goal'])).fetchone()
            gid = goal['id'] if goal else str(uuid4())
            if not goal:
                db.execute('INSERT INTO goals (id,client_id,title) VALUES (?,?,?)', (gid,row['client_id'],row['goal']))
            db.execute('UPDATE sets SET goal_id=? WHERE id=?', (gid,row['id']))

HUNGER_DECAY_PER_SECOND = 5.0 / (30 * 60)


def earned_seeds(db, cid):
    return db.execute('SELECT COALESCE(SUM(amount),0) FROM seed_rewards WHERE client_id=?',(cid,)).fetchone()[0]

def hunger_snapshot(db, cid, now=None):
    now = time.time() if now is None else now
    row = db.execute('SELECT level,updated_at FROM chicken_state WHERE client_id=?',(cid,)).fetchone()
    if row is None:
        db.execute('INSERT INTO chicken_state VALUES (?,?,?)',(cid,0,now))
        return {'level': 0.0, 'updated_at': now}
    level = max(0.0, min(100.0, row['level'] - max(0.0,now-row['updated_at']) * HUNGER_DECAY_PER_SECOND))
    return {'level': level, 'updated_at': now}


def feed_chicken(db, cid, now):
    state = hunger_snapshot(db,cid,now)
    db.execute('UPDATE chicken_state SET level=?,updated_at=? WHERE client_id=?',(min(100.0,state['level']+20.0),now,cid))


def save_client(db, body):
    cid = body.get('id') or str(uuid4())
    old = db.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone()
    if body.get('id') and not old:
        raise ValueError('Client not found. Refresh and try again.')
    fields = ('first_name','last_name','date_of_birth','caregiver_1','caregiver_2','address')
    values = {key: old[key] if old else '' for key in fields}
    for key in fields:
        if key in body:
            value = body[key]
            limit = 1000 if key == 'address' else 200 if key.startswith('caregiver_') else 100
            if not isinstance(value,str) or len(value) > limit:
                raise ValueError(f"Invalid {key.replace('_',' ')} (maximum {limit} characters).")
            values[key] = value.strip()
    if values['date_of_birth']:
        try:
            birthday = date.fromisoformat(values['date_of_birth'])
            if birthday.isoformat() != values['date_of_birth'] or birthday > date.today():
                raise ValueError()
        except ValueError:
            raise ValueError('Enter a valid date of birth that is not in the future.')
    if 'first_name' in body or 'last_name' in body:
        name = text(' '.join(v for v in (values['first_name'],values['last_name']) if v),'Client name',201)
    elif 'name' in body or not old:
        name = text(body.get('name'),'Client name',100)
        values['first_name'], _, values['last_name'] = name.partition(' ')
        values['last_name'] = values['last_name'].strip()
    else:
        name = old['name']
    db.execute('INSERT INTO clients(id,name,first_name,last_name,date_of_birth,caregiver_1,caregiver_2,address) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,first_name=excluded.first_name,last_name=excluded.last_name,date_of_birth=excluded.date_of_birth,caregiver_1=excluded.caregiver_1,caregiver_2=excluded.caregiver_2,address=excluded.address', (cid,name,*(values[k] for k in fields)))
    hunger_snapshot(db,cid)
    return {'id':cid,'name':name,**values}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def text(value, name, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{name} is required (maximum {limit} characters).')
    return value.strip()

def validate_set(body):
    goal = text(body.get('goal'), 'Goal')
    title = text(body.get('title'), 'Problem set title', 200)
    problems = body.get('problems')
    if not isinstance(problems, list) or not 1 <= len(problems) <= 30:
        raise ValueError('Add between 1 and 30 problems.')
    ids = set()
    cleaned = []
    for p in problems:
        pid = text(p.get('id'), 'Problem ID', 100)
        if pid in ids:
            raise ValueError('Problem IDs must be unique.')
        ids.add(pid)
        mode = p.get('mode', 'multiple_choice')
        if mode not in ('multiple_choice', 'open_ended', 'tracing'):
            raise ValueError('Choose a supported answer format.')
        item = dict(id=pid, scenario=text(p.get('scenario'), 'Scenario'), question=text(p.get('question'), 'Question'), mode=mode)
        explanation = p.get('explanation', '')
        if not isinstance(explanation, str) or len(explanation) > 2000:
            raise ValueError('Feedback must be text under 2000 characters.')
        item['explanation'] = explanation.strip()
        if mode == 'multiple_choice':
            choices = p.get('choices')
            if not isinstance(choices, list) or not 2 <= len(choices) <= 10:
                raise ValueError('Each multiple-choice problem needs 2–10 choices.')
            item['choices'] = [{'id': text(c.get('id'), 'Choice ID', 100), 'text': text(c.get('text'), 'Choice', 1000)} for c in choices]
            cids = [c['id'] for c in item['choices']]
            if len(set(cids)) != len(cids) or p.get('correct_choice_id') not in cids:
                raise ValueError('Select a correct answer from the current choices.')
            item['correct_choice_id'] = p['correct_choice_id']
        elif mode == 'tracing':
            template = p.get('trace_template', 'school')
            if template not in ('school','letter_a','number_2','star'):
                raise ValueError('Choose a supported tracing template.')
            item.update(choices=[], trace_template=template)
        else:
            item.update(choices=[], expected_response=text(p.get('expected_response'), 'Example correct response'), acceptance_criteria=text(p.get('acceptance_criteria'), 'Acceptance criteria'))
        cleaned.append(item)
    return goal, title, cleaned

def public_set(row):
    return {'id': row['id'], 'goal_id': row['goal_id'], 'goal': row['goal'], 'title': row['title'], 'problems': [
        {k: p[k] for k in ('id', 'scenario', 'question', 'mode', 'choices', 'trace_template') if k in p} for p in json.loads(row['problems'])]}

def get_run(db, cid, sid, requested=None, create=True):
    if requested is not None:
        requested = text(requested, 'Practice round', 100)
        row = db.execute('SELECT * FROM practice_runs WHERE id=? AND client_id=? AND set_id=?', (requested,cid,sid)).fetchone()
        if not row:
            raise ValueError('Practice round not found. Close practice and try again.')
        return row
    row = db.execute('SELECT * FROM practice_runs WHERE client_id=? AND set_id=? AND completed IS NULL', (cid,sid)).fetchone()
    if row or not create:
        return row
    rid = str(uuid4())
    db.execute('INSERT INTO practice_runs VALUES (?,?,?,?,NULL)', (rid,cid,sid,time.time()))
    return db.execute('SELECT * FROM practice_runs WHERE id=?', (rid,)).fetchone()


def progress(db, cid, sid, problem, run_id):
    rows = db.execute('SELECT * FROM attempts WHERE client_id=? AND set_id=? AND problem_id=? AND run_id=? ORDER BY rowid', (cid,sid,problem['id'],run_id)).fetchall()
    prompted = any(not r['correct'] for r in rows)
    correct = bool(rows and rows[-1]['correct'])
    feedback = ('Good job! ' + problem.get('explanation','')) if correct else ('Try again. The highlighted answer can help.' if rows else '')
    return dict(problem_id=problem['id'], correct=correct, prompted=prompted,
        independent=(correct and not prompted), attempts=len(rows),
        hint_choice_id=problem['correct_choice_id'] if prompted else None,
        selected_choice_id=rows[-1]['choice_id'] if rows else None, feedback=feedback.strip())


def summarize(results):
    scored = [r for r in results if isinstance(r.get('independent'), bool)]
    independent = sum(r['independent'] for r in scored)
    return {'independent': independent, 'prompted': len(scored)-independent,
        'scored': len(scored), 'unscored': len(results)-len(scored),
        'independence_percent': round(100*independent/len(scored), 1) if scored else None}


def grade(db, cid, sid, problems, answers, run_id):
    if not isinstance(answers, list) or len(answers) != len(problems):
        raise ValueError('Answer every problem before submitting.')
    by_id = {a.get('problem_id'): a for a in answers}
    if set(by_id) != {p['id'] for p in problems}:
        raise ValueError('Answer every problem exactly once.')
    results = []
    for p in problems:
        a = by_id[p['id']]
        if p['mode'] == 'multiple_choice':
            result = progress(db, cid, sid, p, run_id)
            if not result['correct'] or a.get('choice_id') != p['correct_choice_id']:
                raise ValueError('Keep practicing each question until you select the correct answer.')
            results.append(result)
        elif p['mode'] == 'tracing':
            trace = a.get('trace')
            strokes = trace.get('strokes') if isinstance(trace, dict) else None
            if not isinstance(strokes, list) or not 1 <= len(strokes) <= 200:
                raise ValueError('Draw the tracing path before submitting.')
            total = 0
            for stroke in strokes:
                if not isinstance(stroke, list) or not stroke:
                    raise ValueError('Invalid tracing stroke.')
                total += len(stroke)
                for point in stroke:
                    if not isinstance(point, dict) or any(type(point.get(k)) not in (int,float) or not 0 <= point[k] <= 1 for k in ('x','y')):
                        raise ValueError('Invalid tracing coordinates.')
            if not 2 <= total <= 10000:
                raise ValueError('Invalid tracing length.')
            results.append(dict(problem_id=p['id'], correct=None, independent=None, feedback='Your tracing is saved for your supervisor to review.'))
        else:
            text(a.get('text'), 'Your answer', 5000)
            results.append(dict(problem_id=p['id'], correct=None, independent=None, feedback='Thank you for sharing. Your supervisor will review your answer.'))
    return results

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    value = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return salt + ':' + value


def valid_password(value):
    if not isinstance(value, str) or not 10 <= len(value) <= 128:
        raise ValueError('Use a password with 10 to 128 characters.')
    return value


def valid_email(value):
    value = text(value, 'Email', 254).lower()
    if value.count('@') != 1 or not all(value.split('@')) or any(c.isspace() for c in value):
        raise ValueError('Enter a valid email address.')
    return value


def supervisor_full_name(first_name, last_name):
    return ' '.join(part for part in (first_name, last_name) if part)


def supervisor_names(body, existing=None):
    # Legacy callers may still send name; keep it intact rather than splitting it.
    first = text(body.get('first_name', body.get('name')), 'First name', 100)
    last = body.get('last_name', existing['last_name'] if existing else '')
    if not isinstance(last, str) or len(last) > 100:
        raise ValueError('Last name must be text (maximum 100 characters).')
    return first, last.strip()


def public_supervisor(row):
    result = {key: row[key] for key in ('id', 'first_name', 'last_name', 'email', 'photo')}
    # Computed compatibility field; names are stored separately.
    result['name'] = supervisor_full_name(row['first_name'], row['last_name'])
    return result


def valid_photo(value):
    if value == '':
        return value
    if not isinstance(value, str) or len(value) > 200000:
        raise ValueError('Choose a smaller profile photo.')
    prefix = 'data:image/jpeg;base64,'
    if not value.startswith(prefix):
        raise ValueError('Choose a JPEG or PNG profile photo.')
    try:
        raw = base64.b64decode(value[len(prefix):], validate=True)
    except ValueError:
        raise ValueError('Invalid profile photo.')
    if not raw.startswith(b'\xff\xd8\xff') or not raw.endswith(b'\xff\xd9'):
        raise ValueError('Invalid profile photo.')
    return value


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'dist'), **kwargs)

    def log_message(self, fmt, *args):
        # Do not log response bodies, pairing codes or tokens.
        pass

    def reply(self, status, payload, cookie=None):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        if cookie is not None:
            age = SESSION_DAYS * 86400 if cookie else 0
            self.send_header('Set-Cookie', f'bawk_session={cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age={age}')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def local_supervisor_request(self):
        host = self.headers.get('Host', '').split(':')[0]
        origin = self.headers.get('Origin')
        return (self.client_address[0] in ('127.0.0.1', '::1') and host in ('localhost', '127.0.0.1')
                and (not origin or origin == 'http://' + self.headers.get('Host', '')))

    def session_token(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', '')).get('bawk_session')
            return cookie.value if cookie else ''
        except Exception:
            return ''

    def supervisor(self):
        if not self.local_supervisor_request():
            return None
        with connect() as db:
            row = db.execute('SELECT s.* FROM supervisors s JOIN supervisor_sessions t ON s.id=t.supervisor_id WHERE t.token_hash=? AND t.expires>?', (digest(self.session_token()), time.time())).fetchone()
            return public_supervisor(row) if row else None

    def account_request(self, db, path, body):
        if not self.local_supervisor_request():
            return self.reply(403, {'error': 'Open Bawk on this Mac at http://localhost:8765.'})
        if path in ('/api/account/register', '/api/account/login'):
            email = valid_email(body.get('email'))
            password = valid_password(body.get('password'))
            db.execute('BEGIN IMMEDIATE')
            limit = db.execute('SELECT * FROM login_limits WHERE email=?', (email,)).fetchone()
            if limit and limit['blocked_until'] > time.time():
                return self.reply(429, {'error': 'Too many attempts. Try again in 15 minutes.'})
            if path.endswith('/register'):
                first_name, last_name = supervisor_names(body)
                if db.execute('SELECT id FROM supervisors WHERE email=?', (email,)).fetchone():
                    return self.reply(409, {'error': 'An account with that email already exists. Sign in instead.'})
                first_account = not db.execute('SELECT 1 FROM supervisors LIMIT 1').fetchone()
                supervisor_id = str(uuid4())
                db.execute('INSERT INTO supervisors(id,first_name,last_name,email,password_hash) VALUES (?,?,?,?,?)', (supervisor_id,first_name,last_name,email,password_hash(password)))
                if first_account:
                    db.execute('UPDATE clients SET supervisor_id=? WHERE supervisor_id IS NULL', (supervisor_id,))
            row = db.execute('SELECT * FROM supervisors WHERE email=?', (email,)).fetchone()
            expected = row['password_hash'] if row else password_hash('unused-password', '0'*32)
            if not row or not secrets.compare_digest(password_hash(password, expected.split(':')[0]), expected):
                failures = (limit['failures'] if limit and limit['blocked_until'] > time.time() - 900 else 0) + 1
                db.execute('INSERT OR REPLACE INTO login_limits VALUES (?,?,?)', (email,failures,time.time()+900 if failures >= 5 else time.time()))
                db.commit()
                return self.reply(401, {'error': 'Email or password is incorrect.'})
            db.execute('DELETE FROM login_limits WHERE email=?', (email,))
            token = secrets.token_urlsafe(32)
            db.execute('DELETE FROM supervisor_sessions WHERE expires<=? OR token_hash=?', (time.time(),digest(self.session_token())))
            db.execute('INSERT INTO supervisor_sessions VALUES (?,?,?)', (digest(token),row['id'],time.time()+SESSION_DAYS*86400))
            db.commit()
            return self.reply(200, {'supervisor': public_supervisor(row)}, cookie=token)
        supervisor = self.supervisor()
        if not supervisor:
            return self.reply(401, {'error': 'Sign in to your supervisor account.'})
        if path.endswith('/logout'):
            db.execute('DELETE FROM supervisor_sessions WHERE token_hash=?', (digest(self.session_token()),))
            db.commit()
            return self.reply(200, {'ready': True}, cookie='')
        if path.endswith('/profile'):
            first_name, last_name = supervisor_names(body, supervisor)
            photo = valid_photo(body.get('photo', supervisor['photo']))
            new_password = body.get('new_password')
            if new_password:
                valid_password(new_password)
                current = text(body.get('current_password'), 'Current password', 128)
                row = db.execute('SELECT password_hash FROM supervisors WHERE id=?',(supervisor['id'],)).fetchone()
                expected = row['password_hash']
                if not secrets.compare_digest(password_hash(current, expected.split(':')[0]),expected):
                    return self.reply(400, {'error': 'Current password is incorrect.'})
                db.execute('UPDATE supervisors SET password_hash=? WHERE id=?',(password_hash(new_password),supervisor['id']))
                db.execute('DELETE FROM supervisor_sessions WHERE supervisor_id=? AND token_hash<>?', (supervisor['id'],digest(self.session_token())))
            db.execute('UPDATE supervisors SET first_name=?,last_name=?,photo=? WHERE id=?',(first_name,last_name,photo,supervisor['id']))
            db.commit()
            return self.reply(200, {'supervisor': self.supervisor()})
        return self.reply(404, {'error': 'Not found'})

    def device(self, db):
        auth = self.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return None
        row = db.execute('SELECT d.client_id FROM devices d JOIN clients c ON c.id=d.client_id WHERE d.token_hash=? AND c.deleted_at IS NULL', (digest(auth[7:]),)).fetchone()
        return row['client_id'] if row else None

    def do_GET(self):
        path = urlparse(self.path).path
        if not path.startswith('/api/'):
            if path not in ('/', '/index.html', '/app.js', '/supervisor.js', '/style.css', '/parent.html', '/parent.js', '/parent.css'):
                return self.reply(404, {'error': 'Not found'})
            return super().do_GET()
        if path == '/api/session':
            if not self.local_supervisor_request():
                return self.reply(403, {'error': 'Open the supervisor website on this Mac at http://localhost:8765.'})
            return self.reply(200, {'supervisor': self.supervisor()})
        with connect() as db:
            if path == '/api/rbt/workspace':
                from rbt import workspace
                return workspace(self, db)
            if path == '/api/workspace':
                supervisor = self.supervisor()
                if not supervisor:
                    return self.reply(401, {'error': 'Sign in to your supervisor account.'})
                clients = [dict(r) for r in db.execute('SELECT * FROM clients WHERE supervisor_id=? AND deleted_at IS NULL ORDER BY rowid', (supervisor['id'],))]
                sets = [dict(r) for r in db.execute('SELECT * FROM sets WHERE client_id IN (SELECT id FROM clients WHERE supervisor_id=?) ORDER BY created DESC', (supervisor['id'],))]
                for row in sets:
                    row['problems'] = json.loads(row['problems'])
                responses = [dict(r) for r in db.execute('SELECT * FROM responses WHERE client_id IN (SELECT id FROM clients WHERE supervisor_id=?) ORDER BY created DESC', (supervisor['id'],))]
                for row in responses:
                    row['answers'], row['results'] = json.loads(row['answers']), json.loads(row['results'])
                goals = [dict(r) for r in db.execute('SELECT * FROM goals WHERE client_id IN (SELECT id FROM clients WHERE supervisor_id=?) ORDER BY rowid', (supervisor['id'],))]
                for response in responses:
                    response['summary'] = summarize(response['results'])
                set_goals = {s['id']: s['goal_id'] for s in sets}
                for goal in goals:
                    goal['summary'] = summarize([result for r in responses if set_goals.get(r['set_id']) == goal['id'] for result in r['results']])
                from rbt import supervisor_notes
                return self.reply(200, dict(clients=clients, goals=goals, sets=sets, responses=responses, session_notes=supervisor_notes(db, supervisor['id'])))
            if path == '/api/client':
                cid = self.device(db)
                if not cid:
                    return self.reply(401, {'error': 'Pair this device with your client again.'})
                client = dict(db.execute('SELECT id,name FROM clients WHERE id=?', (cid,)).fetchone())
                # Least-practiced sets come first. Ties favor the least recently
                # completed set, then assignment order for never-played sets.
                rows = db.execute("""
                    SELECT s.* FROM sets s
                    LEFT JOIN (
                        SELECT set_id, COUNT(*) AS rounds, MAX(created) AS last_completed
                        FROM responses WHERE client_id=? GROUP BY set_id
                    ) history ON history.set_id=s.id
                    WHERE s.client_id=? AND s.published=1 AND s.deleted_at IS NULL AND s.goal_id IN (SELECT id FROM goals WHERE archived_at IS NULL AND deleted_at IS NULL)
                    ORDER BY COALESCE(history.rounds,0), COALESCE(history.last_completed,0), s.created, s.rowid
                """, (cid,cid)).fetchall()
                completed = db.execute('SELECT COUNT(*) FROM responses WHERE client_id=?', (cid,)).fetchone()[0]
                return self.reply(200, {'client': client, 'sets': [public_set(r) for r in rows], 'completed_sets': completed, 'earned_seeds': earned_seeds(db,cid), 'hunger': hunger_snapshot(db,cid)})
        self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 2000000:
                raise ValueError('Invalid request size.')
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('JSON request required.')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Invalid request.')
            path = urlparse(self.path).path
            with connect() as db:
                if path.startswith('/api/rbt/'):
                    from rbt import post
                    return post(self, db, path, body)
                if path.startswith('/api/account/'):
                    return self.account_request(db, path, body)
                if path == '/api/pair':
                    code = text(body.get('code'), 'Pairing code', 100).upper().replace('-', '').replace(' ', '')
                    row = db.execute('DELETE FROM pairing WHERE code_hash=? AND expires>? RETURNING client_id', (digest(code), time.time())).fetchone()
                    if not row:
                        return self.reply(401, {'error': 'Code expired or incorrect. Generate a new code on the website.'})
                    token = secrets.token_urlsafe(32)
                    db.execute('INSERT INTO devices VALUES (?,?)', (digest(token), row['client_id']))
                    db.commit()
                    return self.reply(200, {'token': token})
                if path in ('/api/attempt', '/api/practice'):
                    db.execute('BEGIN IMMEDIATE')
                    cid = self.device(db)
                    if not cid:
                        return self.reply(401, {'error': 'Please pair this device again.'})
                    row = db.execute('SELECT * FROM sets WHERE id=? AND client_id=? AND published=1 AND deleted_at IS NULL AND goal_id IN (SELECT id FROM goals WHERE archived_at IS NULL AND deleted_at IS NULL)', (body.get('set_id'),cid)).fetchone()
                    if not row:
                        return self.reply(404, {'error': 'This set has changed. Close practice and refresh.'})
                    run = get_run(db, cid, row['id'], body.get('run_id'))
                    if run['completed'] is not None:
                        return self.reply(409, {'error': 'This round is complete. Open practice again for a fresh round.'})
                    problems = json.loads(row['problems'])
                    if path == '/api/practice':
                        result = {'run_id': run['id'], 'results': [progress(db,cid,row['id'],p,run['id']) for p in problems if p['mode']=='multiple_choice']}
                        db.commit()
                        return self.reply(200, result)
                    problem = next((p for p in problems if p['id']==body.get('problem_id')), None)
                    if not problem or problem['mode'] != 'multiple_choice':
                        raise ValueError('Choose a multiple-choice problem.')
                    choice = body.get('choice_id')
                    if choice not in {c['id'] for c in problem['choices']}:
                        raise ValueError('Choose an available answer.')
                    request_id = text(body.get('request_id'), 'Attempt ID', 100)
                    existing = db.execute('SELECT * FROM attempts WHERE request_id=?', (request_id,)).fetchone()
                    if existing and (existing['client_id'],existing['set_id'],existing['problem_id'],existing['choice_id'],existing['run_id']) != (cid,row['id'],problem['id'],choice,run['id']):
                        raise ValueError('Attempt ID was already used.')
                    current = progress(db,cid,row['id'],problem,run['id'])
                    if not existing and not current['correct']:
                        db.execute('INSERT INTO attempts (request_id,client_id,set_id,problem_id,choice_id,correct,created,run_id) VALUES (?,?,?,?,?,?,?,?)', (request_id,cid,row['id'],problem['id'],choice,int(choice==problem['correct_choice_id']),time.time(),run['id']))
                    result = progress(db,cid,row['id'],problem,run['id'])
                    db.commit()
                    return self.reply(200,result)
                if path == '/api/submit':
                    db.execute('BEGIN IMMEDIATE')
                    cid = self.device(db)
                    if not cid:
                        return self.reply(401, {'error': 'Please pair this device again.'})
                    row = db.execute('SELECT * FROM sets WHERE id=? AND client_id=? AND published=1 AND deleted_at IS NULL AND goal_id IN (SELECT id FROM goals WHERE archived_at IS NULL AND deleted_at IS NULL)', (body.get('set_id'), cid)).fetchone()
                    if not row:
                        return self.reply(404, {'error': 'Your supervisor updated this problem set. Close practice and refresh to load the latest version.'})
                    run = get_run(db, cid, row['id'], body.get('run_id'), create=False)
                    if not run:
                        # Legacy clients may submit open-ended sets without a start call.
                        if db.execute('SELECT id FROM responses WHERE client_id=? AND set_id=?', (cid,row['id'])).fetchone():
                            return self.reply(409, {'error': 'Start a new practice round before submitting again.'})
                        run = get_run(db, cid, row['id'])
                    if run['completed'] is not None:
                        saved = db.execute('SELECT results FROM responses WHERE run_id=?', (run['id'],)).fetchone()
                        results = json.loads(saved['results'])
                    else:
                        results = grade(db, cid, row['id'], json.loads(row['problems']), body.get('answers'), run['id'])
                        attempt = db.execute('SELECT COUNT(*) FROM responses WHERE client_id=? AND set_id=?', (cid,row['id'])).fetchone()[0] + 1
                        award = max(1, 30 // attempt)
                        db.execute('INSERT INTO seed_rewards VALUES (?,?,?,?)', (run['id'],cid,award,attempt))
                        now = time.time()
                        feed_chicken(db,cid,now)
                        db.execute('INSERT INTO responses VALUES (?,?,?,?,?,?,?)', (str(uuid4()), cid, row['id'], json.dumps(body['answers']), json.dumps(results), now,run['id']))
                        db.execute('UPDATE practice_runs SET completed=? WHERE id=?', (now,run['id']))
                    completed = db.execute('SELECT COUNT(*) FROM responses WHERE client_id=?', (cid,)).fetchone()[0]
                    db.commit()
                    reward = db.execute('SELECT amount,attempt FROM seed_rewards WHERE run_id=?', (run['id'],)).fetchone()
                    return self.reply(200, {'run_id': run['id'], 'results': results, 'summary': summarize(results), 'completed_sets': completed, 'earned_seeds': earned_seeds(db,cid), 'awarded_seeds': reward['amount'], 'set_attempt': reward['attempt'], 'hunger': hunger_snapshot(db,cid)})
                supervisor = self.supervisor()
                if not supervisor:
                    return self.reply(401, {'error': 'Sign in to your supervisor account.'})
                if path in ('/api/clients', '/api/pair-code', '/api/goals', '/api/sets', '/api/goals/delete', '/api/sets/delete', '/api/clients/delete', '/api/goals/archive', '/api/goals/restore'):
                    cid = body.get('id') if path == '/api/clients' else body.get('client_id')
                    if path == '/api/clients/delete':
                        cid = body.get('client_id') or body.get('id')
                    if (path != '/api/clients' or cid) and not db.execute('SELECT id FROM clients WHERE id=? AND supervisor_id=? AND deleted_at IS NULL', (cid,supervisor['id'])).fetchone():
                        return self.reply(404, {'error': 'Client not found.'})
                origin = self.headers.get('Origin')
                if origin and origin != 'http://' + self.headers.get('Host', ''):
                    return self.reply(403, {'error': 'Request origin not allowed.'})
                if path == '/api/clients/delete':
                    db.execute('UPDATE clients SET deleted_at=? WHERE id=?', (time.time(),cid))
                    db.execute('DELETE FROM devices WHERE client_id=?', (cid,))
                    db.execute('DELETE FROM pairing WHERE client_id=?', (cid,))
                    db.execute("UPDATE rbt_sessions SET ended_at=?,note_text='Session closed because the client was removed. Unsubmitted draft retained.' WHERE client_id=? AND ended_at IS NULL", (time.time(),cid))
                    db.execute('DELETE FROM rbt_assignments WHERE client_id=?', (cid,))
                    db.commit()
                    return self.reply(200, {'id':cid})
                if path in ('/api/goals/archive', '/api/goals/restore'):
                    goal = db.execute('SELECT id FROM goals WHERE id=? AND client_id=? AND deleted_at IS NULL', (body.get('id'),cid)).fetchone()
                    if not goal:
                        return self.reply(404, {'error':'Goal not found.'})
                    archived = time.time() if path.endswith('/archive') else None
                    db.execute('UPDATE goals SET archived_at=? WHERE id=?', (archived,goal['id']))
                    db.commit()
                    return self.reply(200, {'id':goal['id'],'archived_at':archived})
                if path in ('/api/goals/delete', '/api/sets/delete'):
                    db.execute('BEGIN IMMEDIATE')
                    table = 'goals' if path == '/api/goals/delete' else 'sets'
                    row = db.execute(f'SELECT * FROM {table} WHERE id=? AND client_id=? AND deleted_at IS NULL', (body.get('id'),body.get('client_id'))).fetchone()
                    if not row:
                        return self.reply(404, {'error': 'Goal or problem set not found. Refresh and try again.'})
                    now = time.time()
                    db.execute(f'UPDATE {table} SET deleted_at=? WHERE id=?', (now,row['id']))
                    if table == 'goals':
                        db.execute('UPDATE sets SET deleted_at=COALESCE(deleted_at,?),published=0 WHERE goal_id=? AND client_id=?', (now,row['id'],row['client_id']))
                    else:
                        db.execute('UPDATE sets SET published=0 WHERE id=?', (row['id'],))
                    db.commit()
                    return self.reply(200, {'id':row['id']})
                if path == '/api/clients':
                    client = save_client(db,body)
                    db.execute('UPDATE clients SET supervisor_id=? WHERE id=?', (supervisor['id'],client['id']))
                    db.commit()
                    return self.reply(200, client)
                if path == '/api/pair-code':
                    cid = body.get('client_id')
                    if not db.execute('SELECT id FROM clients WHERE id=?', (cid,)).fetchone():
                        raise ValueError('Choose a client first.')
                    code = secrets.token_hex(6).upper()
                    db.execute('DELETE FROM pairing WHERE client_id=? OR expires<?', (cid, time.time()))
                    db.execute('INSERT INTO pairing VALUES (?,?,?)', (digest(code), cid, time.time()+600))
                    db.commit()
                    return self.reply(200, {'code': code, 'expires_minutes': 10})
                if path == '/api/goals':
                    cid = body.get('client_id')
                    if not db.execute('SELECT id FROM clients WHERE id=?',(cid,)).fetchone():
                        raise ValueError('Choose a client first.')
                    title = text(body.get('title'),'Goal title')
                    description = body.get('description', '')
                    if not isinstance(description, str) or len(description) > 4000:
                        raise ValueError('Goal description must be text (maximum 4000 characters).')
                    description = description.strip()
                    criteria = body.get('mastery_criteria', '')
                    if not isinstance(criteria, str) or len(criteria) > 4000:
                        raise ValueError('Mastery criteria must be text under 4000 characters.')
                    gid = body.get('id') or str(uuid4())
                    if body.get('id') and not db.execute('SELECT id FROM goals WHERE id=? AND client_id=? AND deleted_at IS NULL',(gid,cid)).fetchone():
                        return self.reply(404, {'error':'Goal not found.'})
                    db.execute('INSERT INTO goals (id,client_id,title,description,mastery_criteria) VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,description=excluded.description,mastery_criteria=excluded.mastery_criteria',(gid,cid,title,description,criteria.strip()))
                    db.commit()
                    return self.reply(200, {'id':gid,'client_id':cid,'title':title,'description':description,'mastery_criteria':criteria.strip()})
                if path == '/api/sets':
                    db.execute('BEGIN IMMEDIATE')
                    selected_goal = db.execute('SELECT * FROM goals WHERE id=? AND client_id=? AND deleted_at IS NULL AND archived_at IS NULL',(body.get('goal_id'),body.get('client_id'))).fetchone()
                    if selected_goal:
                        body['goal'] = selected_goal['title']
                    elif body.get('goal_id'):
                        raise ValueError('Choose a goal belonging to this client.')
                    goal, title, problems = validate_set(body)
                    cid = body.get('client_id')
                    if not db.execute('SELECT id FROM clients WHERE id=?', (cid,)).fetchone():
                        raise ValueError('Choose a client first.')
                    sid = body.get('id') or str(uuid4())
                    old = db.execute('SELECT * FROM sets WHERE id=?', (sid,)).fetchone()
                    if old and old['client_id'] != cid:
                        raise ValueError('This problem set belongs to another client.')
                    if body.get('id') and not old:
                        raise ValueError('Problem set not found. Refresh and try again.')
                    if old and old['deleted_at'] is not None:
                        raise ValueError('This problem set was deleted. Refresh and create a new set.')
                    if old and old['superseded_by']:
                        raise ValueError('This set was already updated. Refresh and edit the latest version.')
                    if not selected_goal:
                        # Compatibility for old drafts/clients; identical goal text shares one goal.
                        selected_goal = db.execute('SELECT * FROM goals WHERE client_id=? AND title=? AND deleted_at IS NULL AND archived_at IS NULL',(cid,goal)).fetchone()
                        if not selected_goal:
                            gid = str(uuid4())
                            db.execute('INSERT INTO goals (id,client_id,title) VALUES (?,?,?)',(gid,cid,goal))
                            selected_goal = {'id':gid}
                    published = int(body.get('publish') is True)
                    if old and old['published']:
                        # Keep submitted answers attached to the exact original questions/key.
                        previous_id = sid
                        sid = str(uuid4())
                        published = 1
                        db.execute('UPDATE sets SET published=0, superseded_by=? WHERE id=?', (sid, previous_id))
                    db.execute('INSERT INTO sets (id,client_id,goal,title,problems,published,created) VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET goal=excluded.goal,title=excluded.title,problems=excluded.problems,published=excluded.published',
                        (sid, cid, goal, title, json.dumps(problems), published, time.time()))
                    db.execute('UPDATE sets SET goal_id=? WHERE id=?',(selected_goal['id'],sid))
                    db.commit()
                    return self.reply(200, {'id': sid})
                return self.reply(404, {'error': 'Not found'})
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            self.reply(400, {'error': str(exc)})
        except Exception:
            self.reply(500, {'error': 'Could not save your changes. Please try again.'})

if __name__ == '__main__':
    initialize()
    port = int(os.environ.get('BAWK_PORT', '8765'))
    print(f'Bawk supervisor: http://localhost:{port}', flush=True)
    print('Keep this window open while using the iOS app. This is a local development connection.', flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
