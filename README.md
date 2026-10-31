# VERIDEX pothole evidence model baseline

This implements the submitted WHY CLOSED? concept: compare before/claimed-after photos for a marked pothole, return visible repair evidence, a remaining visible defect, or insufficient evidence with a targeted photo request. The main review pipeline uses hosted Gemma plus AECP rules. A separate experimental Gemma 4 E4B LoRA adapter has also been trained and is included; it is not enabled in the hosted pipeline.

## Setup

Python 3.10+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Set `GEMINI_API_KEY` in your terminal environment using your own secret manager or shell. Do not commit it, put it in frontend code or send it in chat. Default model: `gemma-4-26b-a4b-it`. Override with `VERIDEX_MODEL` if needed. Provider availability, quotas and costs depend on your account.

```sh
python -m veridex --before before.jpg --after after.jpg \
  --roi 0.20 0.35 0.65 0.80 --output results/case-001.json
```

ROI is `[left, top, right, bottom]`, normalized to 0..1 on the EXIF-oriented BEFORE image. It must identify the original pothole. The AFTER target is located by the vision model, not assumed to be at identical coordinates.

The command sends the resized original, original target crop and completion image to Google when the local image-quality screen passes. Only use images you are authorized to process. JPEG re-encoding drops original EXIF metadata; visible faces and plates are not automatically redacted.

## Pipeline

1. Decode actual image bytes, limit file size and pixel count, apply EXIF rotation and resize.
2. Screen whole images and original target crop using OpenCV sharpness/exposure heuristics.
3. Send images to Gemma with a task-specific instruction and structured observation contract.
4. Validate returned JSON locally. Ambiguous scene, missing target or obstruction prevents positive repair evidence.
5. Return a controlled outcome, reason codes and targeted next request. Human review is always required.

No live inference is claimed by offline test results. Missing provider credentials or failed inference returns `MODEL_UNAVAILABLE`, never a simulated successful review. Invalid input files are CLI errors. Quality thresholds are preliminary heuristics and need calibration. No geometric scene registration, image authenticity guarantee, calibrated model confidence, durable case history or automatic complaint closure is implemented.

## Test

```sh
python -m unittest discover -s tests -v
```

Tests inject model observations explicitly. Synthetic image noise is used only to exercise I/O and quality plumbing; it is not a pothole dataset and proves no vision accuracy.

## Real-data training requirements

Collect permissioned, labelled before/after pairs including real repairs, visible unresolved defects and inadequate evidence. Label the original region, evidence sufficiency, failure reason and next useful capture. Split by physical location before training/evaluation. Compare this baseline against a static prompt and checklist. Measure false approvals, correct abstentions, coverage and successful recaptures. Fine-tune only after establishing this baseline and reserving an untouched test set.

Google integration reference: https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api

## Request timeouts

Provider requests wait up to 180 seconds by default. Set `VERIDEX_TIMEOUT_SECONDS` to a value between 1 and 600 to change this. Timeout failures return `MODEL_UNAVAILABLE` and a sanitized `provider_error`; they do not indicate anything about the repair. One automatic retry is performed for HTTP 500/502/503/504; timeouts are not retried. A retried request may add latency and provider usage.

## Public-data training experiment

A separate HOG/linear-SVM supporting crop classifier has now been trained on a licensed real-image dataset. This does not change Gemma weights or the review pipeline. See training/README.md and training/artifacts/crop-baseline-v1/report.json. Its minority-class precision is weak, so it is not enabled in review decisions.

## One-hour hackathon path

Run `python -m veridex.hackathon --compare` to compare AECP with the simpler prompt on all three synthetic development cases. The command prompts privately for a missing key, prints progress and saves every result plus reports under a new timestamped results folder. It does not train Gemma. Images sent to the provider are JPEG quality 85 with longest edge at most 1024, reducing request size; a user-run development comparison completed successfully, but these synthetic results do not establish field accuracy. Each request can wait up to 180 seconds, plus one retry for temporary HTTP server failures.

## Reused completion photos (policy 0.2)

Pixel-identical decoded/oriented/resized before and after images are rejected before inference with REUSED_PHOTO. This prevents the observed adapter false approval for the identical-photo example. It does not detect all re-encodings, crops, viewpoint changes or manipulated images, and does not repair model weights. A real newly captured unresolved photo is still needed to test visible_defect_remains. Historical reports used policy 0.1 and are not a current-policy benchmark.

## Repository status and included adapter

- Main entry point: `python -m veridex`; hosted Gemma 4 26B-A4B with conservative review rules.
- Tests: 17 local automated checks; these are software checks, not vision accuracy.
- Colab notebook: `training/gemma4-finetune/VERIDEX_Gemma4_Finetune.ipynb`.
- Downloaded adapter: `training/artifacts/gemma4-e4b-smoke/adapter.zip`; unpack and load with its exact base model through the notebook. It cannot be attached to Google's hosted API.
- Adapter training: 10 steps on three synthetic cases, approximately 87 seconds on Colab T4.
- Known failure: adapter incorrectly called an identical unrepaired photo repaired. Policy 0.2 now rejects repeated pixels, but this is a safeguard, not proof that weights improved.
- Base E4B and adapter both identified a new synthetic unrepaired view correctly; no tuning advantage established.
- Hosted detailed and static prompts both passed the three original synthetic cases; no accuracy advantage established.
- Supporting crop classifier: 79.8% held-out crop accuracy vs 82.2% majority baseline; kept out of decisions.
- Citizen/official app and government routing are planned, not implemented here. The unrelated shopping demo is not part of VERIDEX.

API credentials, virtual environments, bulk public dataset files and local inference runs are excluded. Public dataset metadata and attribution are retained. Synthetic examples are labelled as synthetic. No structural repair certification, government integration or real-world accuracy is claimed. See `training/artifacts/crop-baseline-v1/RESULTS.md` and `evaluation/PLAN.md`.
## Android application

The native Android client and its local development API are in [`android-app/`](android-app/). It supports pothole photo capture/import, evidence review, case history and local storage. Current location is requested automatically during photo review after Android permission is granted, with cached, network and GPS provider fallback. The app can run without a live AI connection; configure a backend/model adapter separately for inference.

Open `android-app/` in Android Studio or build a debug APK from that directory with `gradlew assembleDebug`. See [`android-app/README.md`](android-app/README.md) for setup, [`android-app/ROUND_ONE_DEMO.md`](android-app/ROUND_ONE_DEMO.md) for the offline presentation run sheet and [`android-app/VERIFICATION.md`](android-app/VERIFICATION.md) for tested behavior and device follow-ups. Local SDK paths, build outputs, virtual environments and backend case uploads are excluded from version control.
