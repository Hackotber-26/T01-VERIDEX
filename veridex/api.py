"""Local integration API. Run behind HTTPS, authentication and limits before deployment."""
import argparse
import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
from .collector import Store
from .images import load_image, validate_roi
from .review import review

ROOT=Path(__file__).resolve().parents[1]/'.local'
MAX_BODY=28*1024*1024

def adapt_app_case(body):
    """daksha-app sends a complete case: use original plus latest completion."""
    photos=body.get('photos')
    if not isinstance(photos,list) or len(photos)<2 or len(photos)>12:
        raise ValueError('Original and completion photos required')
    if photos[0].get('role')!='before' or photos[-1].get('role') not in {'after','recapture'}:
        raise ValueError('Invalid photo roles')
    return dict(before_base64=photos[0]['image_base64'],after_base64=photos[-1]['image_base64'],
                roi=photos[0]['region'],training_consent=body.get('training_consent',False),
                consent_receipt=body.get('consent_receipt'),site_group=body.get('site_group'))

def app_finding(result,case_id=None):
    explanation=(result.get('observations') or {}).get('evidence')
    return dict(outcome=result['outcome'],explanation=explanation or result.get('next_request') or 'Human evidence review required.',
                next_photo=result.get('next_request') or '',training_case_id=case_id,
                human_review_required=True,inference_engine='hosted_gemma_base')

def authenticate(config, authorization):
    if not authorization.startswith('Bearer '): return None
    digest=hashlib.sha256(authorization[7:].encode()).hexdigest()
    return next((entry for entry in config if hmac.compare_digest(entry['key_sha256'],digest)),None)

def make_handler(store, config):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass  # Never log request data, keys or photos.

        def send(self,status,data):
            payload=json.dumps(data).encode()
            self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(payload)))
            self.end_headers();self.wfile.write(payload)

        def do_GET(self):
            if self.path=='/health': return self.send(200,{'status':'ok','inference':'hosted Gemma; experimental adapter not enabled'})
            self.send(404,{'error':'Not found'})

        def do_POST(self):
            client=authenticate(config,self.headers.get('Authorization',''))
            if client is None: return self.send(401,{'error':'Invalid API key'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if size<1 or size>MAX_BODY: return self.send(413,{'error':'JSON body required, maximum 28 MB'})
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict): raise ValueError('Expected JSON object')
                app=client['app_id']
                if self.path in {'/v1/reviews','/review'}:
                    app_contract=self.path=='/review'
                    if app_contract:body=adapt_app_case(body)
                    consent=body.get('training_consent',False)
                    if type(consent) is not bool: raise ValueError('training_consent must be boolean')
                    roi=validate_roi(body['roi'])
                    if consent and (not body.get('consent_receipt') or not body.get('site_group')):
                        raise ValueError('Training consent requires consent_receipt and site_group')
                    ROOT.mkdir(parents=True,exist_ok=True)
                    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                        paths=[]
                        for field in ['before_base64','after_base64']:
                            raw=base64.b64decode(body[field],validate=True)
                            if len(raw)>10*1024*1024: raise ValueError('Image exceeds 10 MB')
                            path=Path(tmp)/field;path.write_bytes(raw);load_image(path);paths.append(path)
                        result=review(*paths,roi)
                        case_id=None
                        if consent:
                            case_id=store.save(app,load_image(paths[0]),load_image(paths[1]),roi,result,
                                              body['consent_receipt'],body['site_group'])
                    if {'MODEL_UNAVAILABLE','MODEL_OUTPUT_INVALID'}.intersection(result['reason_codes']):
                        return self.send(502,{'error':'Model service failed; no repair finding issued','case_id':case_id})
                    if app_contract:return self.send(200,app_finding(result,case_id))
                    return self.send(200,{'result':result,'case_id':case_id,'training_data_saved':consent,
                        'inference_engine':'hosted_gemma_base','github_exported':False})
                match=re.fullmatch(r'/v1/cases/([a-f0-9]{32})/(label|withdraw)',self.path)
                if not match: return self.send(404,{'error':'Not found'})
                case_id,action=match.groups()
                if action=='withdraw':return self.send(200,store.withdraw(app,case_id))
                if client['role']!='reviewer':return self.send(403,{'error':'Reviewer API key required'})
                item=store.label(app,case_id,body['label'],body['reviewer_ref'],body.get('observation'),
                                 body.get('export_approved',False),body.get('synthetic',False))
                return self.send(200,{'id':item['id'],'human_reviewed':True,'export_approved':item['export_approved']})
            except KeyError:
                self.send(400,{'error':'Missing field or inaccessible case'})
            except (ValueError,TypeError,OSError,AttributeError):
                self.send(400,{'error':'Invalid input; check image files, ROI, consent and labels'})
    return Handler

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--register-app');p.add_argument('--role',choices=['client','reviewer'],default='client')
    p.add_argument('--key-from-env',action='store_true',help='Register VERIDEX_APP_KEY instead of generating a new key')
    p.add_argument('--port',type=int,default=8080)
    a=p.parse_args();ROOT.mkdir(parents=True,exist_ok=True)
    config_path=ROOT/'clients.json'
    config=json.loads(config_path.read_text()) if config_path.exists() else []
    if a.register_app:
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}',a.register_app):p.error('Use an app slug')
        key=os.environ.get('VERIDEX_APP_KEY','') if a.key_from_env else 'vdx_'+secrets.token_urlsafe(32)
        if len(key)<32:p.error('App key must contain at least 32 characters')
        config.append(dict(app_id=a.register_app,role=a.role,key_sha256=hashlib.sha256(key.encode()).hexdigest()))
        config_path.write_text(json.dumps(config,indent=2));config_path.chmod(0o600)
        print('Save this backend-only API key; it is shown once:',key);return
    if not config:p.error('Register a client first: --register-app my-app')
    server=ThreadingHTTPServer(('127.0.0.1',a.port),make_handler(Store(ROOT/'collection'),config))
    print(f'VERIDEX API listening at http://127.0.0.1:{a.port}; training collection is opt-in.')
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()

if __name__=='__main__': main()
