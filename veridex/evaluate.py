"""Reproducible dataset audit, live evaluation and saved-result scoring."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import time
from .images import validate_roi
from .review import review
from .gemma import infer, BASELINE_PROMPT
from functools import partial

LABELS = ['visible_repair_evidence', 'visible_defect_remains', 'insufficient_evidence']
FAILURE_CODES = {'MODEL_UNAVAILABLE', 'MODEL_OUTPUT_INVALID'}

def load_cases(path):
    path = Path(path).resolve()
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    ids, groups, hashes = set(), {}, {}
    for c in cases:
        if not isinstance(c.get('id'), str) or not c['id'] or c['id'] in ids:
            raise ValueError('Missing or duplicate case id')
        ids.add(c['id'])
        if c.get('label') not in LABELS or c.get('split') not in {'train','validation','test','demo'}:
            raise ValueError('Invalid label or split')
        if type(c.get('synthetic')) is not bool or not c.get('location_group'):
            raise ValueError('synthetic and location_group required')
        if not c.get('label_source'):
            raise ValueError('Record the label source')
        validate_roi(c['roi'])
        group = c['location_group']
        if group in groups and groups[group] != c['split']:
            raise ValueError('Location leakage across splits: '+group)
        groups[group] = c['split']
        for field in ['before','after']:
            image = (path.parent / c[field]).resolve()
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            if digest in hashes and hashes[digest] != c['split']:
                raise ValueError('Exact image leakage across splits: '+c['id'])
            hashes[digest] = c['split']
            c[field] = str(image)
    return cases

def divide(n,d): return n/d if d else None

def wilson(k,n):
    if not n: return None
    z=1.96; p=k/n; den=1+z*z/n
    center=(p+z*z/(2*n))/den
    radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,center-radius),min(1,center+radius)]

def score(cases, predictions):
    by_id={p['id']:p for p in predictions}
    if len(by_id)!=len(predictions): raise ValueError('Duplicate prediction ids')
    if set(by_id)-{c['id'] for c in cases}: raise ValueError('Unknown prediction ids')
    matrix={a:{b:0 for b in LABELS} for a in LABELS}
    missing=failed=correct=completed=approved=false_approved=correct_abstain=unsafe=decided=0
    latencies=[]
    for c in cases:
        p=by_id.get(c['id'])
        if p is None: missing+=1; continue
        result=p['result']
        if FAILURE_CODES.intersection(result.get('reason_codes',[])):
            failed+=1; continue
        predicted=result.get('outcome')
        if predicted not in LABELS: raise ValueError('Invalid predicted outcome')
        completed+=1
        expected=c['label']; matrix[expected][predicted]+=1
        correct+=predicted==expected
        decided+=predicted!='insufficient_evidence'
        if predicted=='visible_repair_evidence':
            approved+=1; false_approved+=expected!='visible_repair_evidence'
        if expected=='insufficient_evidence' and predicted=='insufficient_evidence':correct_abstain+=1
        if p.get('elapsed_seconds') is not None: latencies.append(p['elapsed_seconds'])
    unsafe=sum(c['label']!='visible_repair_evidence' for c in cases)
    insufficient=sum(c['label']=='insufficient_evidence' for c in cases)
    per_class={}
    for label in LABELS:
        tp=matrix[label][label]; support=sum(matrix[label].values()); predicted=sum(row[label] for row in matrix.values())
        per_class[label]={'precision':divide(tp,predicted),'recall':divide(tp,support),
                          'f1':divide(2*tp,support+predicted),'completed_support':support}
    return {'unique_location_groups':len({c.get('location_group',c['id']) for c in cases}),
            'macro_f1_completed':sum(v['f1'] or 0 for v in per_class.values())/len(LABELS),
            'cases':len(cases),'completed_inferences':completed,'missing':missing,'provider_or_output_failures':failed,
            'accuracy_completed':divide(correct,completed),'accuracy_completed_wilson95':wilson(correct,completed) if len({c.get('location_group',c['id']) for c in cases})==len(cases) else None,
            'correct_result_rate_all_cases':divide(correct,len(cases)),
            'decision_coverage_completed':divide(decided,completed),
            'false_repair_findings':false_approved,'repair_findings':approved,
            'false_discovery_rate_repair':divide(false_approved,approved),
            'false_approval_rate_all_nonrepair_cases':divide(false_approved,unsafe),
            'correct_abstention_rate_all_insufficient_cases':divide(correct_abstain,insufficient),
            'per_class':per_class,'confusion_matrix':matrix,
            'mean_latency_seconds':divide(sum(latencies),len(latencies)),
            'note':'Rates are not independent site-level estimates when cases share a location. Synthetic results do not establish field accuracy. Provider failures are excluded from completed accuracy, included in all-case rates.'}

def grouped_report(cases,predictions):
    out={'provenance_warning':'Selected historical successes after prompt development; not an unbiased accuracy benchmark.' if any(p.get('provenance') for p in predictions) else None}
    for synthetic in [False,True]:
        subset=[c for c in cases if c['synthetic']==synthetic]
        ids={c['id'] for c in subset}
        out['synthetic' if synthetic else 'real']=score(subset,[p for p in predictions if p['id'] in ids])
    return out

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['audit','run','score'])
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--predictions',help='JSONL results path; run appends and resumes all recorded case ids')
    parser.add_argument('--split',choices=['train','validation','test','demo'],default='test')
    parser.add_argument('--report')
    parser.add_argument('--method',choices=['aecp','static_prompt'],default='aecp')
    args=parser.parse_args()
    try:
        all_cases=load_cases(args.manifest)
        cases=[c for c in all_cases if c['split']==args.split]
        if not cases: raise ValueError('No cases in selected split')
        if args.command=='audit':
            output={'selected_cases':len(cases),'unique_locations':len({c['location_group'] for c in cases}),
                    'labels':dict(Counter(c['label'] for c in cases)),
                    'synthetic_cases':sum(c['synthetic'] for c in cases),'leakage_checks':'location groups and exact hashes pass; near-duplicates need manual review'}
        else:
            if not args.predictions: raise ValueError('--predictions required')
            dest=Path(args.predictions)
            predictions=[json.loads(x) for x in dest.read_text().splitlines() if x.strip()] if dest.exists() else []
            if args.command=='run':
                if any(p.get('method')!=args.method for p in predictions): raise ValueError('Use separate prediction files for each method')
                known={p['id'] for p in predictions}
                dest.parent.mkdir(parents=True,exist_ok=True)
                for c in cases:
                    if c['id'] in known: continue
                    start=time.monotonic(); result=review(c['before'],c['after'],c['roi'],provider=partial(infer,prompt=BASELINE_PROMPT) if args.method=='static_prompt' else None)
                    row={'id':c['id'],'method':args.method,'result':result,'elapsed_seconds':round(time.monotonic()-start,3)}
                    with dest.open('a') as f:f.write(json.dumps(row)+'\n')
                    predictions.append(row)
            output=grouped_report(cases,predictions)
        text=json.dumps(output,indent=2)
        if args.report:
            dest=Path(args.report);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text+'\n')
        print(text)
    except (ValueError,OSError,KeyError) as exc:parser.error(str(exc))

if __name__=='__main__': main()
