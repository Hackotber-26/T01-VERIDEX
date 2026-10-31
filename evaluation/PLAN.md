# VERIDEX: training and evidence plan

## Current status

No new weights have been trained. Available data: three synthetic cases derived from ONE generated location. The historical report scores selected successful user-pasted responses after prompt revisions. It excludes earlier failed attempts and cannot estimate field accuracy. Never describe it as 100% model accuracy. No independent real test set exists yet.

## The proposed contribution

Evaluate target-grounded evidence review with targeted recapture. Given an inadequate completion image, identify the original region, explain the missing evidence and select a useful next capture. Success means fewer incorrect repair findings AND fewer unresolved cases per capture, not a larger chatbot or a prettier map. This is a hypothesis, not an established first-of-its-kind claim.

Keep existing civic systems as the case-of-record. Human reviewers retain closure authority. API integration follows a successful evaluation and authorized pilot.

## Existing approaches and what can be compared

- RoadMetrics advertises road assessment, prioritization and afterwork status. Its public marketing page does not establish whether its recapture policy matches ours: https://www.roadmetrics.ai/
- iWatchRoadv2 describes detection, GIS and repair verification. It is related prior work; broad repair verification is not our unique invention: https://arxiv.org/abs/2510.16375
- Official Fix Pothole workflow already supports geotagged reporting, routing and resolution photos: https://play.google.com/store/apps/details?id=com.indigo.bbmp.fixpothole
- The 2026 Road Damage Dataset has pothole/crack/manhole boxes and a CC BY 4.0 release. These labels can support a detector, NOT certify before/after repair comparisons. Its curated images exclude major quality failures, so it cannot substitute for our insufficient-evidence set: https://www.nature.com/articles/s41598-026-46679-4

Do not compare our three-way review accuracy against a paper's pothole detection mAP. Tasks, datasets and denominators differ. Do not invent competitor performance without access to the same benchmark.

## Data collection and labels

Start with a pilot of 60 permissioned cases from at least 20 distinct sites, balanced across visible repair, visible remaining defect and insufficient evidence. This is a collection goal, not a sufficient sample size for deployment claims. Include real viewpoint changes, different locations, nearby irrelevant patches, water, shadows, obstruction and blur. Annotate original target ROI, case outcome, evidence gap and the useful next view. Have two people label independently, blind to model output; record disagreements and adjudication. Preserve ambiguous cases as uncertain.

Include provenance, license/consent and label_source. Keep each physical site, all near-duplicate frames and all generated derivatives entirely in ONE split. Reserve a real untouched test set before tuning. Do not use test responses to revise instructions and still call that set held-out.

## Fair comparison

A: short static Gemma prompt + identical local policy (implemented).
B: VERIDEX detailed target/evidence prompt + same policy (implemented).
C: human-labelled review reference.

For a recapture study, compare generic retake instructions with targeted requests on matched initial cases, with equal image/call budgets and randomized assignment. A human must actually provide a new image. Measure unresolved cases after one recapture, false repair findings, review time, number of captures, API failure rate and cost. Current evaluator does NOT yet measure the recapture intervention itself.

Report three-way confusion matrix, macro F1, class precision/recall, false repair findings, coverage, correct abstentions, availability and latency. Report synthetic and real results separately. Repeat runs to measure nondeterminism and record every attempt; temperature zero is not a guarantee of determinism.

## Training gate

Do not fine-tune on these three generated images. First collect human-adjudicated TRAIN examples with full images, target ROI, structured observations and useful next requests. Use validation sites to select adapter settings; compare a Gemma LoRA adapter with the frozen baseline on untouched test sites. Hardware, Gemma multimodal tuning compatibility and model license must be checked before selecting a trainer. No training job or improved accuracy is claimed here.

## Commands

Audit the existing demo:

    python -m veridex.evaluate audit --manifest evaluation/demo.jsonl --split demo

Run fresh AECP inference (uses your terminal's GEMINI_API_KEY and may incur provider usage):

    python -m veridex.evaluate run --manifest evaluation/demo.jsonl --split demo --method aecp --predictions results/aecp-run1.jsonl --report results/aecp-run1-report.json

Run the static prompt on the SAME cases:

    python -m veridex.evaluate run --manifest evaluation/demo.jsonl --split demo --method static_prompt --predictions results/static-run1.jsonl --report results/static-run1-report.json

Use fresh filenames for independent repeat runs. Existing prediction files resume all recorded cases, including failures. Preserve failed attempts rather than rerunning until only successes remain. Live provider access has not been exercised by the authoring session; user-terminal historical outputs are the only live evidence so far.
