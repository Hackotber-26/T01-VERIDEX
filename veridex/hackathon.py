"""One-command live demonstration. Includes failures in the saved results."""
import argparse
from datetime import datetime, timezone
from functools import partial
import getpass
import hashlib
import json
import os
from pathlib import Path
import time
from .evaluate import load_cases, grouped_report
from .gemma import infer, PROMPT, BASELINE_PROMPT
from .review import review

ROOT = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compare', action='store_true', help='Also run the static prompt, doubling API calls')
    args = parser.parse_args()
    if not os.environ.get('GEMINI_API_KEY'):
        os.environ['GEMINI_API_KEY'] = getpass.getpass('Paste API key (hidden, not saved): ').strip()
    if not os.environ['GEMINI_API_KEY']:
        parser.error('API key is empty')
    cases = load_cases(ROOT / 'evaluation/demo.jsonl')
    out = ROOT / 'results' / datetime.now(timezone.utc).strftime('demo-%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True)
    methods = ['aecp', 'static_prompt'] if args.compare else ['aecp']
    metadata = {
        'model': os.environ.get('VERIDEX_MODEL', 'gemma-4-26b-a4b-it'),
        'synthetic': True, 'location_count': 1, 'methods': methods,
        'prompt_hashes': {m: hashlib.sha256((PROMPT if m == 'aecp' else BASELINE_PROMPT).encode()).hexdigest() for m in methods},
        'encoding': 'JPEG85; longest edge <=1024',
        'http_retry': 'one retry for HTTP 500/502/503/504; no timeout retry',
        'limitations': 'Development demo, not held-out accuracy or fine-tuned weights.'
    }
    (out / 'run.json').write_text(json.dumps(metadata, indent=2))
    for method in methods:
        rows = []
        for i, case in enumerate(cases, 1):
            print(f'[{method} {i}/{len(cases)}] {case["id"]}: contacting Gemma...', flush=True)
            start = time.monotonic()
            provider = partial(infer, prompt=BASELINE_PROMPT) if method == 'static_prompt' else None
            result = review(case['before'], case['after'], case['roi'], provider=provider)
            row = {'id': case['id'], 'method': method, 'result': result, 'elapsed_seconds': round(time.monotonic()-start, 2)}
            rows.append(row)
            with (out / f'{method}.jsonl').open('a') as f:
                f.write(json.dumps(row)+'\n')
            print(f'  {result["outcome"]} ({row["elapsed_seconds"]}s); expected {case["label"]}', flush=True)
            if result.get('provider_error'):
                print('  Service failure:', result['provider_error'], flush=True)
            elif result.get('observations'):
                print(' ', result['observations']['evidence'], flush=True)
            if result['next_request']:
                print('  Next:', result['next_request'], flush=True)
        report = grouped_report(cases, rows)
        (out / f'{method}-report.json').write_text(json.dumps(report, indent=2))
        scored = report['synthetic']
        print(f'{method}: completed {scored["completed_inferences"]}/{len(cases)}; service/output failures {scored["provider_or_output_failures"]}.', flush=True)
    print('Reports saved:', out)
    print('Synthetic demo only; this does not establish field accuracy or train Gemma weights.')

if __name__ == '__main__':
    main()
