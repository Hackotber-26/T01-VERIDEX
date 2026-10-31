# Real-photo dataset intake

No real photos or verified training labels are included yet. `labels.template.jsonl` is an EXAMPLE, not a training case. Copy to `labels.jsonl` and replace every placeholder; use one JSON object per case.

1. Put authorized original and completion photos in `images/`. Do not capture from traffic.
2. Assign each physical road site one location_group. Keep alternate views, synthetic derivatives and recaptures in the same group.
3. Record the BEFORE target ROI in normalized EXIF-oriented coordinates.
4. Two reviewers independently assign one label: visible_repair_evidence, visible_defect_remains or insufficient_evidence. Resolve disagreements without seeing model predictions.
5. Record reviewer/adjudication provenance and image permission/license. For unclear cases, record the missing evidence and next useful photo request.
6. Optionally add a human-labelled `observation` with the exact fields documented in veridex/policy.py. Leave null if not annotated. Never copy a model response and call it independent ground truth.

Prepare a manifest when at least five distinct sites exist:

    python -m veridex.prepare_dataset --labels dataset/labels.jsonl --output dataset/manifest.v1.jsonl

The 60/20/20 approximate split is grouped by location, deterministic by seed, and never overwrites an existing output. Five sites is a technical minimum, not a statistically adequate field benchmark. Aim initially for at least 20 diverse sites and 60 adjudicated cases. Review split class balance before using it; collect more sites if a class is missing.

Audit all split assignments and evaluate the test split:

    python -m veridex.evaluate audit --manifest dataset/manifest.v1.jsonl --split test
    python -m veridex.evaluate run --manifest dataset/manifest.v1.jsonl --split test --method aecp --predictions results/real-aecp-v1.jsonl --report results/real-aecp-v1-report.json

Use validation cases to improve prompts or training. Freeze the test manifest before those changes. Existing evaluator outputs are not a Gemma fine-tuning format; no training job is launched by preparation.
