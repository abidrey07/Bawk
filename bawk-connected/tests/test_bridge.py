import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
import uuid
import copy
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location('bridge', Path(__file__).parents[1] / 'website/server.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        bridge.DB = Path(self.temp.name) / 'test.sqlite'
        bridge.initialize()
        self.server = bridge.ThreadingHTTPServer(('127.0.0.1', 0), bridge.Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.cookie = ''
        result = self.call('account/register', {'name':'Test Supervisor','email':'supervisor@example.test','password':'test-password-123'})
        self.assertEqual(result[0],200)
        self.cookie = self.last_cookie
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.temp.cleanup()
    def call(self, path, data=None, token=None, supervisor=False):
        headers = {'Content-Type': 'application/json'}
        if supervisor: headers['Cookie'] = self.cookie
        if token: headers['Authorization'] = 'Bearer '+token
        req = Request(self.url+'/api/'+path, headers=headers, data=json.dumps(data).encode() if data is not None else None)
        try:
            with urlopen(req) as r:
                self.last_cookie = (r.headers.get('Set-Cookie') or '').split(';')[0]
                return r.status, json.load(r)
        except HTTPError as e: return e.code, json.load(e)
    def test_goal_title_description_and_legacy_migration(self):
        cid = self.client()
        status, goal = self.call('goals', {'client_id':cid, 'title':'Social skills', 'description':'  Recognize behavior.\nPractice in school.  '}, supervisor=True)
        self.assertEqual(status, 200)
        self.assertEqual(goal['description'], 'Recognize behavior.\nPractice in school.')
        legacy = self.call('goals', {'client_id':cid, 'title':'Older goal'}, supervisor=True)[1]
        self.assertEqual(legacy['description'], '')
        bridge.initialize()
        goals = self.call('workspace', supervisor=True)[1]['goals']
        self.assertEqual(goals[0]['description'], goal['description'])
        self.assertEqual(goals[1]['title'], 'Older goal')
        for description in [None, 42, 'x' * 4001]:
            self.assertEqual(self.call('goals', {'client_id':cid, 'title':'Invalid', 'description':description}, supervisor=True)[0], 400)
        with bridge.connect() as db:
            db.execute('ALTER TABLE goals DROP COLUMN description')
        bridge.initialize()
        goals = self.call('workspace', supervisor=True)[1]['goals']
        self.assertEqual(len(goals), 2)
        self.assertTrue(all(g['description'] == '' for g in goals))

    def test_supervisor_accounts_sessions_profiles_and_isolation(self):
        first_cookie = self.cookie
        cid = self.client()
        goal = self.call('goals', {'client_id':cid, 'title':'Private goal'}, supervisor=True)[1]
        saved = self.call('sets', self.draft(cid), supervisor=True)[1]
        self.assertEqual(self.call('workspace')[0],401)
        self.assertIsNone(self.call('session')[1]['supervisor'])
        result = self.call('account/register', {'name':'Other Supervisor','email':'other@example.test','password':'other-password-123'})
        self.assertEqual(result[0],200)
        second_cookie = self.last_cookie
        self.cookie = second_cookie
        workspace = self.call('workspace',supervisor=True)[1]
        for key in ('clients','goals','sets','responses'): self.assertEqual(workspace[key],[])
        for endpoint, body in [('clients',{'id':cid,'name':'Stolen'}),('pair-code',{'client_id':cid}),('goals',{'client_id':cid,'title':'Stolen'}),('sets',self.draft(cid))]:
            self.assertEqual(self.call(endpoint,body,supervisor=True)[0],404)
        own_client = self.client('Own client')
        draft = self.draft(own_client); draft['goal_id'] = goal['id']
        self.assertEqual(self.call('sets',draft,supervisor=True)[0],400)
        draft.pop('goal_id'); draft['id'] = saved['id']
        self.assertEqual(self.call('sets',draft,supervisor=True)[0],400)
        updated = self.call('account/profile', {'name':'Updated Name','photo':''}, supervisor=True)
        self.assertEqual(updated[1]['supervisor']['name'],'Updated Name')
        self.assertNotIn('password_hash',updated[1]['supervisor'])
        self.assertEqual(self.call('account/profile',{'name':'Bad','photo':'data:image/svg+xml;base64,aaa'},supervisor=True)[0],400)
        self.assertEqual(self.call('account/profile',{'name':'Updated Name','new_password':'replacement-123','current_password':'wrong-password'},supervisor=True)[0],400)
        self.assertEqual(self.call('account/profile',{'name':'Updated Name','new_password':'replacement-123','current_password':'other-password-123'},supervisor=True)[0],200)
        self.assertEqual(self.call('account/logout',{},supervisor=True)[0],200)
        self.assertEqual(self.call('workspace',supervisor=True)[0],401)
        self.assertEqual(self.call('account/login',{'email':'other@example.test','password':'other-password-123'})[0],401)
        self.assertEqual(self.call('account/login',{'email':'OTHER@example.test','password':'replacement-123'})[0],200)
        self.cookie = self.last_cookie
        bridge.initialize()
        self.assertEqual(self.call('session',supervisor=True)[1]['supervisor']['name'],'Updated Name')
        with bridge.connect() as db:
            db.execute('UPDATE supervisor_sessions SET expires=0 WHERE token_hash=?',(bridge.digest(self.cookie.split('=',1)[1]),))
        self.assertEqual(self.call('workspace',supervisor=True)[0],401)
        self.cookie = first_cookie
        self.assertEqual(self.call('workspace',supervisor=True)[1]['clients'][0]['name'],'Test Client')

    def test_first_supervisor_claims_existing_clients_only_once(self):
        with bridge.connect() as db:
            db.execute('DELETE FROM supervisor_sessions'); db.execute('DELETE FROM supervisors')
            db.execute("INSERT INTO clients(id,name) VALUES ('legacy','Existing Client')")
        self.assertEqual(self.call('account/register',{'name':'Owner','email':'owner@example.test','password':'owner-password-123'})[0],200)
        self.cookie = self.last_cookie
        self.assertEqual(self.call('workspace',supervisor=True)[1]['clients'][0]['id'],'legacy')
        self.assertEqual(self.call('account/register',{'name':'Second','email':'second@example.test','password':'second-password-123'})[0],200)
        self.cookie = self.last_cookie
        self.assertEqual(self.call('workspace',supervisor=True)[1]['clients'],[])

    def test_login_throttling_and_origin_protection(self):
        for _ in range(5):
            self.assertEqual(self.call('account/login',{'email':'supervisor@example.test','password':'wrong-password-123'})[0],401)
        self.assertEqual(self.call('account/login',{'email':'supervisor@example.test','password':'test-password-123'})[0],429)
        request = Request(self.url+'/api/account/register', data=json.dumps({'name':'Bad','email':'bad@example.test','password':'test-password-123'}).encode(), headers={'Content-Type':'application/json','Origin':'https://untrusted.example'})
        with self.assertRaises(HTTPError) as error: urlopen(request)
        self.assertEqual(error.exception.code,403)
        with bridge.connect() as db:
            row = db.execute('SELECT password_hash FROM supervisors').fetchone()
            self.assertNotEqual(row['password_hash'],'test-password-123')
            self.assertNotIn(self.cookie.split('=',1)[1],[r['token_hash'] for r in db.execute('SELECT token_hash FROM supervisor_sessions')])

    def test_supervisor_multiword_names_and_legacy_name_migration(self):
        result = self.call('account/register', {'first_name':'  Mary Jane  ', 'last_name':'  de la Cruz  ', 'email':'multi@example.test','password':'test-password-123'})
        self.assertEqual(result[0],200)
        self.cookie = self.last_cookie
        profile = result[1]['supervisor']
        self.assertEqual((profile['first_name'],profile['last_name'],profile['name']), ('Mary Jane','de la Cruz','Mary Jane de la Cruz'))
        result = self.call('account/profile', {'first_name':'Mary Jane','last_name':'Smith Jones'}, supervisor=True)
        self.assertEqual(result[1]['supervisor']['first_name'],'Mary Jane')
        bridge.initialize()
        self.assertEqual(self.call('session',supervisor=True)[1]['supervisor']['last_name'],'Smith Jones')
        self.assertEqual(self.call('account/profile', {'first_name':'Mary Jane','last_name':''}, supervisor=True)[1]['supervisor']['name'],'Mary Jane')
        self.assertEqual(self.call('account/profile', {'first_name':'  ','last_name':'Smith'}, supervisor=True)[0],400)
        with bridge.connect() as db:
            db.execute('ALTER TABLE supervisors RENAME COLUMN first_name TO name')
            db.execute('ALTER TABLE supervisors DROP COLUMN last_name')
            db.execute("UPDATE supervisors SET name='Mary Jane de la Cruz' WHERE email='multi@example.test'")
        bridge.initialize(); bridge.initialize()
        profile = self.call('session',supervisor=True)[1]['supervisor']
        self.assertEqual(profile['first_name'],'Mary Jane de la Cruz')
        self.assertEqual(profile['last_name'],'')
        with bridge.connect() as db:
            columns = {r['name'] for r in db.execute('PRAGMA table_info(supervisors)')}
            self.assertNotIn('name',columns)
            self.assertIn('first_name',columns)
            self.assertIn('last_name',columns)

    def client(self, name='Test Client'):
        return self.call('clients', {'name':name}, supervisor=True)[1]['id']
    def pair(self, cid):
        code = self.call('pair-code', {'client_id':cid}, supervisor=True)[1]['code']
        status, result = self.call('pair', {'code':code})
        self.assertEqual(status,200)
        self.assertEqual(self.call('pair', {'code':code})[0],401)
        return result['token']
    def draft(self, cid):
        return {'client_id':cid, 'goal':'Ask for clarification', 'title':'Practice', 'problems':[
            {'id':'p1','scenario':'Someone says put it there.','question':'What can you say?', 'mode':'multiple_choice',
             'choices':[{'id':'a','text':'Where?'},{'id':'b','text':'No.'}], 'correct_choice_id':'a','explanation':'Ask where they mean.'}]}
    def test_full_flow_and_client_isolation(self):
        cid = self.client(); token = self.pair(cid)
        self.assertEqual(self.call('client', token=token)[1]['sets'],[])
        draft = self.draft(cid)
        code, saved = self.call('sets',draft,supervisor=True); self.assertEqual(code,200)
        self.assertEqual(self.call('client',token=token)[1]['sets'],[])
        draft.update(id=saved['id'],publish=True)
        self.assertEqual(self.call('sets',draft,supervisor=True)[0],200)
        snapshot = self.call('client',token=token)[1]
        self.assertEqual(len(snapshot['sets']),1)
        self.assertNotIn('correct_choice_id',snapshot['sets'][0]['problems'][0])
        other = self.pair(self.client('Other'))
        self.assertEqual(self.call('client',token=other)[1]['sets'],[])
        submission = {'set_id':saved['id'],'answers':[{'problem_id':'p1','choice_id':'a'}]}
        self.assertEqual(self.call('submit',submission,token=other)[0],404)
        self.assertEqual(self.call('attempt',{'set_id':saved['id'],'problem_id':'p1','choice_id':'a','request_id':str(uuid.uuid4())},token=token)[0],200)
        self.assertEqual(self.call('submit',submission,token=token)[1]['results'][0]['correct'],True)
        self.assertEqual(self.call('submit',submission,token=token)[0],409)
        self.assertEqual(len(self.call('client',token=token)[1]['sets']),1)
        self.assertEqual(len(self.call('workspace',supervisor=True)[1]['responses']),1)
        draft['title'] = 'Updated practice'
        draft['problems'][0]['choices'].append({'id':'c','text':'Can you show me?'})
        draft['problems'][0]['correct_choice_id'] = 'c'
        status, updated = self.call('sets',draft,supervisor=True)
        self.assertEqual(status,200)
        self.assertNotEqual(updated['id'],saved['id'])
        latest = self.call('client',token=token)[1]['sets']
        self.assertEqual([s['id'] for s in latest],[updated['id']])
        workspace = self.call('workspace',supervisor=True)[1]
        original = next(s for s in workspace['sets'] if s['id']==saved['id'])
        self.assertEqual(original['problems'][0]['correct_choice_id'],'a')
        self.assertEqual(workspace['responses'][0]['set_id'],saved['id'])
        self.assertEqual(self.call('submit',submission,token=token)[0],404)
        self.assertEqual(self.call('sets',draft,supervisor=True)[0],400)
    def test_validation_names_and_open_ended(self):
        cid=self.client();token=self.pair(cid)
        self.call('clients',{'id':cid,'name':'Updated Name'},supervisor=True)
        self.assertEqual(self.call('client',token=token)[1]['client']['name'],'Updated Name')
        d=self.draft(cid);d['problems'][0]['choices'].pop(0)
        self.assertEqual(self.call('sets',d,supervisor=True)[0],400)
        d=self.draft(cid);d['problems'][0].update(mode='open_ended',expected_response='Where?',acceptance_criteria='Ask a relevant clarification question');d['publish']=True
        saved=self.call('sets',d,supervisor=True)[1]
        response=self.call('submit',{'set_id':saved['id'],'answers':[{'problem_id':'p1','text':'Which shelf?'}]},token=token)
        self.assertEqual(response[0],200);self.assertIsNone(response[1]['results'][0]['correct'])
    def test_retries_independence_and_multiple_sets(self):
        cid=self.client(); token=self.pair(cid)
        goal=self.call('goals',{'client_id':cid,'title':'Appropriate vs inappropriate'},supervisor=True)[1]
        draft=self.draft(cid); draft.update(goal_id=goal['id'],title='School',publish=True)
        sample=draft['problems'][0]
        draft['problems']=[{**copy.deepcopy(sample),'id':f'p{i}'} for i in range(5)]
        saved=self.call('sets',draft,supervisor=True)[1]
        answers=[]
        for i in range(5):
            payload={'set_id':saved['id'],'problem_id':f'p{i}','choice_id':'b' if i>=3 else 'a','request_id':str(uuid.uuid4())}
            response=self.call('attempt',payload,token=token)[1]
            if i>=3:
                self.assertFalse(response['correct']);self.assertEqual(response['hint_choice_id'],'a')
                self.assertEqual(self.call('attempt',payload,token=token)[1]['attempts'],1)
                resumed=self.call('practice',{'set_id':saved['id']},token=token)[1]['results'][i]
                self.assertTrue(resumed['prompted'])
                payload.update(choice_id='a',request_id=str(uuid.uuid4()))
                response=self.call('attempt',payload,token=token)[1]
                self.assertFalse(response['independent'])
            else:
                self.assertTrue(response['independent']);self.assertIsNone(response['hint_choice_id'])
            self.assertTrue(response['correct'])
            answers.append({'problem_id':f'p{i}','choice_id':'a'})
        result=self.call('submit',{'set_id':saved['id'],'answers':answers},token=token)[1]
        self.assertEqual(result['summary']['independence_percent'],60)
        workspace=self.call('workspace',supervisor=True)[1]
        self.assertEqual(workspace['goals'][0]['summary']['independence_percent'],60)
        home=self.draft(cid);home.update(goal_id=goal['id'],title='Home',publish=True)
        other=self.call('sets',home,supervisor=True)[1]
        self.call('attempt',{'set_id':other['id'],'problem_id':'p1','choice_id':'a','request_id':str(uuid.uuid4())},token=token)
        self.call('submit',{'set_id':other['id'],'answers':[{'problem_id':'p1','choice_id':'a'}]},token=token)
        workspace=self.call('workspace',supervisor=True)[1]
        self.assertEqual(len(workspace['goals']),1)
        self.assertEqual(workspace['goals'][0]['summary']['independence_percent'],66.7)
        self.assertEqual(workspace['goals'][0]['summary']['scored'],6)

    def test_cannot_skip_wrong_answer_or_reset_prompt(self):
        cid=self.client();token=self.pair(cid)
        draft=self.draft(cid);draft['publish']=True
        saved=self.call('sets',draft,supervisor=True)[1]
        payload={'set_id':saved['id'],'answers':[{'problem_id':'p1','choice_id':'a'}]}
        self.assertEqual(self.call('submit',payload,token=token)[0],400)
        self.call('attempt',{'set_id':saved['id'],'problem_id':'p1','choice_id':'b','request_id':str(uuid.uuid4())},token=token)
        self.assertEqual(self.call('submit',payload,token=token)[0],400)
        another_device=self.pair(cid)
        state=self.call('practice',{'set_id':saved['id']},token=another_device)[1]['results'][0]
        self.assertTrue(state['prompted'])

    def test_migration_groups_existing_sets_without_losing_data(self):
        cid=self.client()
        with bridge.connect() as db:
            for sid in ['school','home']:
                db.execute('INSERT INTO sets(id,client_id,goal,title,problems,published,created) VALUES (?,?,?,?,?,?,?)',(sid,cid,'Shared goal',sid,'[]',0,1))
        bridge.initialize();bridge.initialize()
        with bridge.connect() as db:
            rows=db.execute('SELECT goal_id FROM sets').fetchall()
            self.assertEqual(len({r['goal_id'] for r in rows}),1)
            self.assertIsNotNone(rows[0]['goal_id'])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM goals').fetchone()[0],1)

    def test_replay_rounds_reset_hints_and_submit_is_idempotent(self):
        cid=self.client(); token=self.pair(cid)
        draft=self.draft(cid);draft['publish']=True
        sid=self.call('sets',draft,supervisor=True)[1]['id']
        run_ids=[]
        for round_index in range(3):
            status, started=self.call('practice',{'set_id':sid},token=token)
            self.assertEqual(status,200)
            rid=started['run_id'];run_ids.append(rid)
            self.assertFalse(started['results'][0]['correct'])
            self.assertFalse(started['results'][0]['prompted'])
            self.assertIsNone(started['results'][0]['hint_choice_id'])
            self.assertEqual(self.call('practice',{'set_id':sid},token=token)[1]['run_id'],rid)
            if round_index==0:
                self.call('attempt',{'set_id':sid,'run_id':rid,'problem_id':'p1','choice_id':'b','request_id':str(uuid.uuid4())},token=token)
            payload={'set_id':sid,'run_id':rid,'problem_id':'p1','choice_id':'a','request_id':str(uuid.uuid4())}
            self.assertEqual(self.call('attempt',payload,token=token)[0],200)
            submission={'set_id':sid,'run_id':rid,'answers':[{'problem_id':'p1','choice_id':'a'}]}
            status,result=self.call('submit',submission,token=token)
            self.assertEqual(status,200)
            self.assertEqual(result['completed_sets'],round_index+1)
            self.assertEqual(result['results'][0]['independent'],round_index!=0)
            retry=self.call('submit',submission,token=token)[1]
            self.assertEqual(retry['results'],result['results'])
            self.assertEqual(retry['completed_sets'],result['completed_sets'])
            self.assertEqual(self.call('attempt',payload,token=token)[0],409)
        self.assertEqual(len(set(run_ids)),3)
        workspace=self.call('workspace',supervisor=True)[1]
        self.assertEqual(len(workspace['responses']),3)
        self.assertEqual(workspace['goals'][0]['summary']['independence_percent'],66.7)
        self.assertEqual(len(self.call('client',token=token)[1]['sets']),1)
        # A delayed submission from an old round must not consume a new round.
        new=self.call('practice',{'set_id':sid},token=token)[1]
        self.assertEqual(self.call('submit',submission,token=token)[1]['completed_sets'],3)
        self.assertEqual(self.call('practice',{'set_id':sid},token=token)[1]['run_id'],new['run_id'])
        other=self.pair(self.client('Other'))
        self.assertEqual(self.call('practice',{'set_id':sid,'run_id':new['run_id']},token=other)[0],404)

    def test_legacy_history_and_in_progress_migration(self):
        cid=self.client();draft=self.draft(cid);draft['publish']=True
        sid=self.call('sets',draft,supervisor=True)[1]['id']
        with bridge.connect() as db:
            db.execute('DROP TABLE responses')
            db.execute('DROP TABLE attempts')
            db.execute('DROP TABLE practice_runs')
            db.execute('CREATE TABLE responses(id TEXT PRIMARY KEY,client_id TEXT,set_id TEXT,answers TEXT,results TEXT,created REAL,UNIQUE(client_id,set_id))')
            db.execute('CREATE TABLE attempts(request_id TEXT PRIMARY KEY,client_id TEXT,set_id TEXT,problem_id TEXT,choice_id TEXT,correct INTEGER,created REAL)')
            db.execute('INSERT INTO responses VALUES (?,?,?,?,?,?)',('old',cid,sid,'[]','[{"independent":true}]',123))
            db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?)',('attempt',cid,sid,'p1','a',1,122))
        bridge.initialize();bridge.initialize()
        with bridge.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM responses').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT run_id FROM attempts').fetchone()[0],'old')
            self.assertEqual(db.execute('SELECT completed FROM practice_runs').fetchone()[0],123)
        token=self.pair(cid)
        started=self.call('practice',{'set_id':sid},token=token)[1]
        self.assertNotEqual(started['run_id'],'old')
        self.assertFalse(started['results'][0]['correct'])

    def test_round_ids_cannot_cross_sets_or_reuse_attempt_ids(self):
        cid=self.client();token=self.pair(cid)
        draft=self.draft(cid);draft['publish']=True
        sid=self.call('sets',draft,supervisor=True)[1]['id']
        sid2=self.call('sets',draft,supervisor=True)[1]['id']
        rid=self.call('practice',{'set_id':sid},token=token)[1]['run_id']
        self.assertEqual(self.call('practice',{'set_id':sid2,'run_id':rid},token=token)[0],400)
        attempt={'set_id':sid,'run_id':rid,'problem_id':'p1','choice_id':'a','request_id':str(uuid.uuid4())}
        self.assertEqual(self.call('attempt',attempt,token=token)[0],200)
        self.call('submit',{'set_id':sid,'run_id':rid,'answers':[{'problem_id':'p1','choice_id':'a'}]},token=token)
        new=self.call('practice',{'set_id':sid},token=token)[1]['run_id']
        attempt['run_id']=new
        self.assertEqual(self.call('attempt',attempt,token=token)[0],400)
        self.assertFalse(self.call('practice',{'set_id':sid,'run_id':new},token=token)[1]['results'][0]['correct'])

    def test_priority_queue_least_completed_rounds_first(self):
        cid=self.client();token=self.pair(cid)
        ids=[]
        for title in ['First','Second','Third']:
            draft=self.draft(cid);draft.update(title=title,publish=True)
            ids.append(self.call('sets',draft,supervisor=True)[1]['id'])
        def queue():
            return [s['id'] for s in self.call('client',token=token)[1]['sets']]
        self.assertEqual(queue(),ids)
        # Even after several complete passes the least-practiced sets lead.
        for index in range(7):
            sid=queue()[0]
            self.assertEqual(sid,ids[index % 3])
            run=self.call('practice',{'set_id':sid},token=token)[1]['run_id']
            # Opening/abandoning practice must not push this set out of priority.
            self.assertEqual(queue()[0],sid)
            self.call('attempt',{'set_id':sid,'run_id':run,'problem_id':'p1','choice_id':'a','request_id':str(uuid.uuid4())},token=token)
            self.call('submit',{'set_id':sid,'run_id':run,'answers':[{'problem_id':'p1','choice_id':'a'}]},token=token)
        self.assertEqual(queue(),[ids[1],ids[2],ids[0]])
        # A new assignment with zero rounds immediately takes priority.
        draft=self.draft(cid);draft.update(title='New',publish=True)
        newest=self.call('sets',draft,supervisor=True)[1]['id']
        self.assertEqual(queue()[0],newest)
        draft=self.draft(cid);draft['title']='Unpublished'
        self.call('sets',draft,supervisor=True)
        self.assertEqual(len(queue()),4)

    def test_hunger_continuous_decay_and_persistent_feed(self):
        cid=self.client();token=self.pair(cid)
        with bridge.connect() as db:
            db.execute('UPDATE chicken_state SET level=80,updated_at=10000 WHERE client_id=?',(cid,))
            self.assertEqual(bridge.hunger_snapshot(db,cid,10000)['level'],80)
            self.assertEqual(bridge.hunger_snapshot(db,cid,10900)['level'],77.5)
            self.assertEqual(bridge.hunger_snapshot(db,cid,11800)['level'],75)
            self.assertAlmostEqual(bridge.hunger_snapshot(db,cid,10001)['level'],80-5/1800)
            self.assertEqual(bridge.hunger_snapshot(db,cid,9000)['level'],80)
            self.assertEqual(bridge.hunger_snapshot(db,cid,1000000)['level'],0)
            bridge.feed_chicken(db,cid,11800)
        # New connection, like a restart: 95 after feeding, then 90 in 30 minutes.
        with bridge.connect() as db:
            self.assertEqual(bridge.hunger_snapshot(db,cid,11800)['level'],95)
            self.assertEqual(bridge.hunger_snapshot(db,cid,13600)['level'],90)
            bridge.feed_chicken(db,cid,13600)
            self.assertEqual(bridge.hunger_snapshot(db,cid,13600)['level'],100)
        with patch.object(bridge.time,'time',return_value=15400):
            bridge.initialize()
            self.assertEqual(self.call('client',token=token)[1]['hunger']['level'],95)

    def test_submit_feeds_once_and_does_not_reset_decay_on_refresh(self):
        cid=self.client();token=self.pair(cid)
        draft=self.draft(cid);draft['publish']=True
        sid=self.call('sets',draft,supervisor=True)[1]['id']
        rid=self.call('practice',{'set_id':sid},token=token)[1]['run_id']
        self.call('attempt',{'set_id':sid,'run_id':rid,'problem_id':'p1','choice_id':'a','request_id':str(uuid.uuid4())},token=token)
        submission={'set_id':sid,'run_id':rid,'answers':[{'problem_id':'p1','choice_id':'a'}]}
        with patch.object(bridge.time,'time',return_value=20000):
            self.assertEqual(self.call('submit',submission,token=token)[1]['hunger']['level'],20)
        with patch.object(bridge.time,'time',return_value=21800):
            self.assertEqual(self.call('submit',submission,token=token)[1]['hunger']['level'],15)
            self.assertEqual(self.call('client',token=token)[1]['hunger']['level'],15)
        with patch.object(bridge.time,'time',return_value=23600):
            self.assertEqual(self.call('client',token=token)[1]['hunger']['level'],10)

    def test_optional_client_details_and_child_privacy(self):
        cid=self.client('Alex Morgan');token=self.pair(cid)
        client=self.call('workspace',supervisor=True)[1]['clients'][0]
        self.assertEqual((client['first_name'],client['last_name']),('Alex','Morgan'))
        self.assertEqual(client['date_of_birth'],'')
        details={'id':cid,'first_name':'Alex Lee','last_name':'Morgan','date_of_birth':'2017-03-12','caregiver_1':'Sam','caregiver_2':'Jo','address':'123 Sample Lane'}
        status,client=self.call('clients',details,supervisor=True)
        self.assertEqual(status,200);self.assertEqual(client['name'],'Alex Lee Morgan')
        updated=self.call('clients',{'id':cid,'address':'New address'},supervisor=True)[1]
        self.assertEqual(updated['caregiver_1'],'Sam');self.assertEqual(updated['first_name'],'Alex Lee')
        self.assertEqual(self.call('clients',{'id':cid,'date_of_birth':'2999-01-01'},supervisor=True)[0],400)
        self.assertEqual(self.call('clients',{'id':cid,'date_of_birth':'2020-02-30'},supervisor=True)[0],400)
        self.assertEqual(self.call('clients',{'id':cid,'first_name':'','last_name':''},supervisor=True)[0],400)
        self.assertEqual(self.call('clients',{'id':cid,'address':123},supervisor=True)[0],400)
        self.assertEqual(self.call('clients',{'id':cid,'caregiver_1':'A'*150},supervisor=True)[0],200)
        self.assertEqual(self.call('clients',{'id':cid,'caregiver_1':'A'*201},supervisor=True)[0],400)
        child=self.call('client',token=token)[1]['client']
        self.assertEqual(child,{'id':cid,'name':'Alex Lee Morgan'})
        self.assertEqual(self.call('clients',details,token=token)[0],401)

    def test_parent_portal_serves_only_sample_pages(self):
        for path in ('parent.html','parent.css','parent.js'):
            with urlopen(self.url+'/'+path) as response:
                self.assertEqual(response.status,200)
                data=response.read().decode()
                if path=='parent.html':
                    self.assertIn('Fictional family and sample progress',data)
                    self.assertIn('id="goals"',data)
                    self.assertIn('id="home"',data)
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url+'/data/bawk.sqlite3')
        self.assertEqual(error.exception.code,404)

    def test_delete_sets_and_goals_preserves_history_and_blocks_stale_practice(self):
        cid=self.client(); token=self.pair(cid)
        draft=self.draft(cid); draft['publish']=True
        sid=self.call('sets',draft,supervisor=True)[1]['id']
        rid=self.call('practice',{'set_id':sid},token=token)[1]['run_id']
        attempt={'set_id':sid,'run_id':rid,'problem_id':'p1','choice_id':'a','request_id':str(uuid.uuid4())}
        self.call('attempt',attempt,token=token)
        submission={'set_id':sid,'run_id':rid,'answers':[{'problem_id':'p1','choice_id':'a'}]}
        self.call('submit',submission,token=token)
        draft['id']=sid
        latest=self.call('sets',draft,supervisor=True)[1]['id']
        goal=self.call('workspace',supervisor=True)[1]['goals'][0]
        with bridge.connect() as db:
            hunger=tuple(db.execute('SELECT level,updated_at FROM chicken_state WHERE client_id=?',(cid,)).fetchone())
        self.assertEqual(self.call('sets/delete',{'client_id':cid,'id':latest},supervisor=True)[0],200)
        ws=self.call('workspace',supervisor=True)[1]
        self.assertIsNone(ws['goals'][0]['deleted_at'])
        self.assertEqual(ws['goals'][0]['summary']['independence_percent'],100)
        self.assertEqual(len(ws['responses']),1)
        self.assertEqual(self.call('client',token=token)[1]['sets'],[])
        self.assertEqual(self.call('client',token=token)[1]['completed_sets'],1)
        draft['id']=latest
        self.assertEqual(self.call('sets',draft,supervisor=True)[0],400)
        for endpoint,payload in [('practice',{'set_id':latest}),('attempt',{**attempt,'set_id':latest}),('submit',{**submission,'set_id':latest})]:
            self.assertEqual(self.call(endpoint,payload,token=token)[0],404)
        draft.pop('id'); draft['goal_id']=goal['id']
        active=self.call('sets',draft,supervisor=True)[1]['id']
        self.assertEqual(self.call('goals/delete',{'client_id':cid,'id':goal['id']},supervisor=True)[0],200)
        ws=self.call('workspace',supervisor=True)[1]
        self.assertTrue(all(s['deleted_at'] for s in ws['sets']))
        self.assertTrue(ws['goals'][0]['deleted_at'])
        self.assertEqual(len(ws['responses']),1)
        self.assertEqual(self.call('client',token=token)[1]['sets'],[])
        self.assertEqual(self.call('practice',{'set_id':active},token=token)[0],404)
        self.assertEqual(self.call('sets',draft,supervisor=True)[0],400)
        draft.pop('goal_id')
        self.assertEqual(self.call('sets',draft,supervisor=True)[0],200)
        ws=self.call('workspace',supervisor=True)[1]
        self.assertEqual(len([g for g in ws['goals'] if not g['deleted_at']]),1)
        with bridge.connect() as db:
            self.assertEqual(tuple(db.execute('SELECT level,updated_at FROM chicken_state WHERE client_id=?',(cid,)).fetchone()),hunger)
        bridge.initialize(); bridge.initialize()
        self.assertEqual(len(self.call('workspace',supervisor=True)[1]['responses']),1)

    def test_delete_authorization_and_client_isolation(self):
        cid=self.client(); sid=self.call('sets',self.draft(cid),supervisor=True)[1]['id']
        goal=self.call('workspace',supervisor=True)[1]['goals'][0]['id']
        other=self.client('Other')
        for endpoint,identifier in [('sets/delete',sid),('goals/delete',goal)]:
            self.assertEqual(self.call(endpoint,{'client_id':cid,'id':identifier})[0],401)
            self.assertEqual(self.call(endpoint,{'client_id':other,'id':identifier},supervisor=True)[0],404)
        self.call('account/register',{'first_name':'Other','email':'second@example.test','password':'password-123'})
        self.cookie=self.last_cookie
        own=self.client('Own')
        for endpoint,identifier in [('sets/delete',sid),('goals/delete',goal)]:
            self.assertEqual(self.call(endpoint,{'client_id':cid,'id':identifier},supervisor=True)[0],404)
            self.assertEqual(self.call(endpoint,{'client_id':own,'id':identifier},supervisor=True)[0],404)

    def test_permissions(self):
        self.assertEqual(self.call('workspace')[0],401)
        self.assertEqual(self.call('clients',{'name':'Unauthorized'})[0],401)
        self.assertEqual(self.call('client',token='bad')[0],401)
        self.assertEqual(self.call('session')[0],200)

if __name__ == '__main__': unittest.main()
