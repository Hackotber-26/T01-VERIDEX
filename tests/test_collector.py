import hashlib
import tempfile
import unittest
from PIL import Image
from veridex.api import authenticate,adapt_app_case,app_finding
from veridex.collector import Store

class CollectorTests(unittest.TestCase):
    def test_auth_and_app_contract(self):
        entry={'app_id':'a','role':'client','key_sha256':hashlib.sha256(b'correct').hexdigest()}
        self.assertEqual(authenticate([entry],'Bearer correct'),entry)
        self.assertIsNone(authenticate([entry],'Bearer wrong'))
        case={'photos':[{'role':'before','region':[0,0,1,1],'image_base64':'original'},
                        {'role':'after','image_base64':'old'}, {'role':'recapture','image_base64':'latest'}]}
        adapted=adapt_app_case(case)
        self.assertEqual(adapted['after_base64'],'latest')
        self.assertFalse(adapted['training_consent'])

    def test_export_needs_human_approval_and_respects_withdrawal(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);image=Image.new('RGB',(64,64),'gray')
            case=store.save('app-a',image,image,[0,0,1,1],{},'receipt-1','site-1')
            self.assertEqual(store.eligible(),[])
            with self.assertRaises(KeyError):store.get('app-b',case)
            store.label('app-a',case,'insufficient_evidence','reviewer-1',approved=True)
            self.assertEqual(len(store.eligible()),1)
            store.withdraw('app-a',case)
            self.assertEqual(store.eligible(),[])

    def test_app_finding_schema(self):
        result={'outcome':'insufficient_evidence','observations':None,'next_request':'Show the target.'}
        self.assertEqual(app_finding(result)['next_photo'],'Show the target.')

    def test_private_export_rejects_public_repo(self):
        from unittest.mock import patch
        from veridex.sync_dataset import sync
        with patch('veridex.sync_dataset.gh',return_value={'private':False}):
            with self.assertRaises(ValueError):sync('owner/public',None)

    def test_http_review_matches_app_and_rejects_wrong_key(self):
        import base64,io,json,threading,urllib.request,urllib.error
        from http.server import ThreadingHTTPServer
        from unittest.mock import patch
        from pathlib import Path
        from veridex.api import make_handler
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'store')
            config=[{'app_id':'test','role':'client','key_sha256':hashlib.sha256(b'test-key').hexdigest()}]
            server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(store,config))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            stream=io.BytesIO();Image.new('RGB',(64,64),'gray').save(stream,format='JPEG')
            photo=base64.b64encode(stream.getvalue()).decode()
            body=json.dumps({'photos':[{'role':'before','region':[0,0,1,1],'image_base64':photo},
                                      {'role':'after','image_base64':photo}]}).encode()
            url=f'http://127.0.0.1:{server.server_port}/review'
            try:
                with patch('veridex.api.ROOT',Path(tmp)):
                    req=urllib.request.Request(url,body,{'Authorization':'Bearer test-key','Content-Type':'application/json'})
                    result=json.load(urllib.request.urlopen(req,timeout=5))
                    self.assertEqual(result['outcome'],'insufficient_evidence')
                    self.assertTrue(result['explanation'])
                    self.assertTrue(result['next_photo'])
                    self.assertIsNone(result['training_case_id'])
                    req=urllib.request.Request(url,body,{'Authorization':'Bearer wrong'})
                    with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req,timeout=5)
                    self.assertEqual(error.exception.code,401)
            finally:server.shutdown();server.server_close();thread.join()
