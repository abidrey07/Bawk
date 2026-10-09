import test_bridge
bridge = test_bridge.bridge
import uuid

class FeatureTests(test_bridge.BridgeTests):
    # Only new cases; reuse fixture helpers without repeating inherited cases.
    def test_new_lifecycle(self):
        cid=self.client(); other=self.client('Other'); token=self.pair(cid)
        goal=self.call('goals',{'client_id':cid,'title':'Tracing','mastery_criteria':'80% over 3 sessions'},supervisor=True)[1]
        draft={'client_id':cid,'goal_id':goal['id'],'goal':'Tracing','title':'Path','publish':True,'problems':[{'id':'t','mode':'tracing','scenario':'School','question':'Trace','trace_template':'school'}]}
        status,created=self.call('sets',draft,supervisor=True); self.assertEqual(status,200)
        sid=created['id']; self.assertEqual(self.call('client',token=token)[1]['sets'][0]['problems'][0]['trace_template'],'school')
        total=0
        for attempt,award in enumerate([30,15,10,7,6,5],1):
            run=self.call('practice',{'set_id':sid},token=token)[1]['run_id']
            body={'set_id':sid,'run_id':run,'answers':[{'problem_id':'t','trace':{'strokes':[[{'x':.1,'y':.1},{'x':.2,'y':.2}]],'coverage':1}}]}
            status,result=self.call('submit',body,token=token); self.assertEqual(status,200,result)
            total+=award; self.assertEqual(result['awarded_seeds'],award); self.assertEqual(result['earned_seeds'],total)
            self.assertEqual(result['results'][0]['independent'],None)
            self.assertEqual(self.call('submit',body,token=token)[1]['earned_seeds'],total)
        bridge.initialize(); self.assertEqual(self.call('client',token=token)[1]['earned_seeds'],total)
        self.assertEqual(self.call('goals/archive',{'client_id':cid,'id':goal['id']},supervisor=True)[0],200)
        self.assertEqual(self.call('client',token=token)[1]['sets'],[])
        self.assertEqual(self.call('practice',{'set_id':sid},token=token)[0],404)
        self.assertEqual(self.call('goals/restore',{'client_id':cid,'id':goal['id']},supervisor=True)[0],200)
        self.assertEqual(len(self.call('client',token=token)[1]['sets']),1)
        pairing=self.call('rbt/pair-code',{'client_ids':[cid,other],'provider_name':'Test RBT','credentials':'RBT','title':'Technician'},supervisor=True)[1]
        status,paired=self.call('rbt/pair',{'code':pairing['code']});self.assertEqual(status,200,paired);rbt=paired['token']
        self.assertEqual(self.call('rbt/pair',{'code':pairing['code']})[0],401)
        self.assertEqual(self.call('rbt/workspace',token=token)[0],401)
        self.assertEqual(self.call('client',token=rbt)[0],401)
        work=self.call('rbt/workspace',token=rbt)[1];self.assertEqual(len(work['clients']),2)
        body={'client_id':cid,'request_id':str(uuid.uuid4())}
        status,session=self.call('rbt/start',body,token=rbt);self.assertEqual(status,200,session)
        self.assertEqual(self.call('rbt/start',body,token=rbt)[1]['id'],session['id'])
        saved={'session_id':session['id'],'counts':[{'goal_id':goal['id'],'independent':3,'prompted':1,'no_response':0}],'fields':{'preparedness':'Calm'},'note_text':'Observed session. 75% independent.'}
        self.assertEqual(self.call('rbt/save',saved,token=rbt)[0],200)
        self.assertEqual(self.call('rbt/workspace',token=rbt)[1]['sessions'][0]['counts'][0]['independent'],3)
        submitted=self.call('rbt/submit',saved,token=rbt)[1];self.assertIsNotNone(submitted['ended_at'])
        self.assertEqual(self.call('rbt/submit',saved,token=rbt)[1]['ended_at'],submitted['ended_at'])
        self.assertEqual(self.call('rbt/save',saved,token=rbt)[0],409)
        notes=self.call('workspace',supervisor=True)[1]['session_notes'];self.assertEqual(len(notes),1);self.assertEqual(notes[0]['note_text'],saved['note_text'])
        active=self.call('rbt/start',{'client_id':cid,'request_id':str(uuid.uuid4())},token=rbt);self.assertEqual(active[0],200)
        self.assertEqual(self.call('clients/delete',{'client_id':cid},supervisor=True)[0],200)
        self.assertEqual(self.call('client',token=token)[0],401)
        self.assertEqual(self.call('rbt/start',{'client_id':other,'request_id':str(uuid.uuid4())},token=rbt)[0],200)
        self.assertEqual(len(self.call('workspace',supervisor=True)[1]['clients']),1)

# unittest would otherwise execute inherited cases for this subclass as well.
for name in list(test_bridge.BridgeTests.__dict__):
    if name.startswith('test_'):
        setattr(FeatureTests,name,None)
