import test_bridge
import time
import uuid

class NotesTests(test_bridge.BridgeTests):
    def test_staff_archive_permissions_validation_and_retry(self):
        cid=self.client(); token=self.pair(cid)
        self.assertEqual(self.call('session-notes')[0],401)
        self.assertEqual(self.call('session-notes',token=token)[0],401)
        base={'client_id':cid,'provider_name':'Sample Author','started_at':time.time()-3600,'ended_at':time.time()-60,'note_text':'Session observations.'}
        for role in ('BCBA','Student analyst'):
            body={**base,'author_role':role,'request_id':str(uuid.uuid4())}
            status,result=self.call('session-notes',body,supervisor=True);self.assertEqual(status,200,result)
            self.assertEqual(self.call('session-notes',body,supervisor=True)[1]['id'],result['id'])
            self.assertEqual(self.call('session-notes',{**body,'note_text':'Changed'},supervisor=True)[0],409)
        rows=self.call('session-notes',supervisor=True)[1]['session_notes']
        self.assertEqual(len(rows),2);self.assertEqual({n['author_role'] for n in rows},{'BCBA','Student analyst'})
        self.assertTrue(all(n['recorded_by'] and n['client_name']=='Test Client' for n in rows))
        for change in ({'author_role':'RBT'},{'started_at':float('nan')},{'ended_at':time.time()+86400},{'note_text':' '},{'client_id':'missing'}):
            bad={**base,'author_role':'BCBA','request_id':str(uuid.uuid4()),**change}
            self.assertIn(self.call('session-notes',bad,supervisor=True)[0],(400,404))
        original_cookie=self.cookie
        self.call('account/register',{'name':'Other','email':'notes-other@example.test','password':'test-password-123'})
        self.cookie=self.last_cookie
        self.assertEqual(self.call('session-notes',supervisor=True)[1]['session_notes'],[])
        self.assertEqual(self.call('session-notes',{**base,'author_role':'BCBA','request_id':str(uuid.uuid4())},supervisor=True)[0],404)
        self.cookie=original_cookie
        self.call('clients/delete',{'client_id':cid},supervisor=True)
        archive=self.call('session-notes',supervisor=True)[1]
        self.assertEqual(len(archive['session_notes']),2);self.assertIsNotNone(archive['clients'][0]['deleted_at'])
        self.assertEqual(self.call('session-notes',{**base,'author_role':'BCBA','request_id':str(uuid.uuid4())},supervisor=True)[0],404)

for name in test_bridge.BridgeTests.__dict__:
    if name.startswith('test_'): setattr(NotesTests,name,None)
