"""Validate human labels and create reproducible location-grouped manifests."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
from .evaluate import LABELS
from .images import load_image, crop_roi
from .policy import decide, parse_observation

def prepare(source, destination, seed=42):
    source=Path(source).resolve();destination=Path(destination).resolve()
    rows=[json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    if not rows:raise ValueError('No labelled cases')
    ids=set();hash_groups={}
    for row in rows:
        if not row.get('id') or row['id'] in ids:raise ValueError('Missing or duplicate id')
        ids.add(row['id'])
        if not isinstance(row.get('location_group'),str) or not row['location_group']:raise ValueError('location_group required')
        if type(row.get('synthetic')) is not bool:raise ValueError('synthetic boolean required')
        if row.get('label') not in LABELS:raise ValueError('Invalid label')
        for field in ['label_source','consent_or_license']:
            if not isinstance(row.get(field),str) or not row[field].strip() or 'REPLACE' in row[field]:
                raise ValueError('Complete '+field+' for '+row['id'])
        for field in ['before','after']:
            path=(source.parent/row[field]).resolve()
            image=load_image(path)
            if field=='before':crop_roi(image,row['roi'])
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in hash_groups and hash_groups[digest]!=row['location_group']:
                raise ValueError('Same image assigned to different location groups')
            hash_groups[digest]=row['location_group']
            row[field]=str(path)
        if row.get('observation') is not None:
            observation=parse_observation(json.dumps(row['observation']))
            if decide(observation)['outcome']!=row['label']:
                raise ValueError('Structured observation disagrees with label: '+row['id'])
    groups=sorted({r['location_group'] for r in rows})
    if len(groups)<5:raise ValueError('At least 5 independent locations required to make train/validation/test splits; use demo manifests for smaller sets')
    random.Random(seed).shuffle(groups)
    ntest=max(1,round(len(groups)*.2));nval=max(1,round(len(groups)*.2))
    assignment={g:('test' if i<ntest else 'validation' if i<ntest+nval else 'train') for i,g in enumerate(groups)}
    for row in rows:row['split']=assignment[row['location_group']]
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation prevents accidentally changing a locked split manifest.
    with destination.open('x') as out:
        for row in rows:out.write(json.dumps(row)+'\n')
    return {'cases':len(rows),'locations':len(groups),'split_cases':dict(Counter(r['split'] for r in rows)),
            'seed':seed,'synthetic_cases':sum(r['synthetic'] for r in rows),
            'note':'Review class balance and near-duplicates manually before locking. Never reroll splits based on model test performance.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--labels',required=True);p.add_argument('--output',required=True);p.add_argument('--seed',type=int,default=42)
    a=p.parse_args()
    try:print(json.dumps(prepare(a.labels,a.output,a.seed),indent=2))
    except (OSError,ValueError,KeyError) as exc:p.error(str(exc))

if __name__=='__main__':main()
