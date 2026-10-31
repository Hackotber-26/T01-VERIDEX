"""Explicit private-GitHub export of consented, human-approved cases via gh CLI."""
import argparse
import base64
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from .api import ROOT
from .collector import Store

def gh(path,method='GET',body=None):
    command=[shutil.which('gh') or 'gh','api',path,'--method',method]
    if body is not None:command+=['--input','-']
    result=subprocess.run(command,input=json.dumps(body) if body is not None else None,
                          text=True,capture_output=True)
    if result.returncode:raise RuntimeError('GitHub request failed; check gh authentication and repository access')
    return json.loads(result.stdout)

def sync(repo,store):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('Use owner/repository')
    metadata=gh('repos/'+repo)
    if not metadata.get('private'):raise ValueError('Training export requires a PRIVATE repository')
    branch=metadata['default_branch']
    head=gh(f'repos/{repo}/git/ref/heads/{branch}')['object']['sha']
    base=gh(f'repos/{repo}/git/commits/{head}')['tree']['sha']
    entries=[]
    rows=[]
    for item in store.eligible():
        for field in ['before','after']:
            data=(store.root/item[field]).read_bytes()
            blob=gh(f'repos/{repo}/git/blobs','POST',{'content':base64.b64encode(data).decode(),'encoding':'base64'})
            entries.append({'path':item[field],'mode':'100644','type':'blob','sha':blob['sha']})
        # Human labels are separate from model observations. Do not export precise locations or free text.
        row={key:item[key] for key in ['id','app_id','before','after','roi','location_group','synthetic','label','label_source','observation']}
        row.update(training_consent=True,consent_or_license='Recorded user training permission; receipt retained privately by operator')
        rows.append(row)
    entries.append({'path':'labels.jsonl','mode':'100644','type':'blob',
                    'content':''.join(json.dumps(r)+'\n' for r in rows)})
    subtree=gh(f'repos/{repo}/git/trees','POST',{'tree':entries})
    tree=gh(f'repos/{repo}/git/trees','POST',{'base_tree':base,'tree':[
        {'path':'veridex-cases','mode':'040000','type':'tree','sha':subtree['sha']}]})
    if tree['sha']==base:return {'exported_cases':len(rows),'changed':False}
    commit=gh(f'repos/{repo}/git/commits','POST',{'message':'Sync approved VERIDEX training cases','tree':tree['sha'],'parents':[head]})
    gh(f'repos/{repo}/git/refs/heads/{branch}','PATCH',{'sha':commit['sha'],'force':False})
    return {'exported_cases':len(rows),'commit':commit['sha'],'changed':True,
            'warning':'Withdrawn cases leave the current snapshot, but prior Git history retains earlier copies. Use appropriate history cleanup for deletion requests.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True)
    p.add_argument('--watch',type=int,default=0,help='Optional polling interval in seconds; at least 60')
    a=p.parse_args()
    if a.watch and a.watch<60:p.error('Minimum interval is 60 seconds')
    while True:
        print(json.dumps(sync(a.repo,Store(ROOT/'collection')),indent=2),flush=True)
        if not a.watch:break
        time.sleep(a.watch)

if __name__=='__main__':main()
