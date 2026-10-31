# Handoff: daksha-app + VERIDEX model API

## What is ready

The `main` branch now includes `python -m veridex.api`: authenticated review, compatibility with daksha-app's case payload, optional training collection, reviewer labels, and a private GitHub export command. Inference uses **hosted Gemma 4 26B-A4B + AECP**, not the experimental E4B adapter. The adapter is not deployed as a service. No public endpoint has been deployed.

Two different keys are needed:

- `MODEL_API_KEY`: the private VERIDEX client key shared by Darshan. It authenticates the app backend to our model server.
- `GEMINI_API_KEY`: Darshan's Google provider key, present only on the machine running the model server. Do not put it in the APK or send it to teammates who do not operate the model server.

The shared app key is in `.local/daksha-app-key.txt` on Darshan's machine. That file and all collected data are ignored by Git. Do not commit it or paste it into public issues. It currently authenticates only a local registered service; it is not a Google key or a hosted model URL.

## 1. Run the model service (terminal A)

Use a checkout of `main`, separate from the friend's `daksha-app` checkout:

```sh
git clone --branch main https://github.com/Hackotber-26/T01-VERIDEX.git veridex-model-api
cd veridex-model-api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Set `VERIDEX_APP_KEY` privately to the shared app key. On macOS zsh:

```sh
read -s 'VERIDEX_APP_KEY?Paste shared VERIDEX key: '
export VERIDEX_APP_KEY
echo
python -m veridex.api --register-app daksha-app --key-from-env
read -s 'GEMINI_API_KEY?Paste Google provider key: '
export GEMINI_API_KEY
echo
python -m veridex.api --port 8081
```

On Darshan's existing checkout the app is already registered; skip registration unless using a new checkout. Restart the service after changing registered keys. `GET http://127.0.0.1:8081/health` checks server availability, not Google credentials or model availability.

## 2. Connect the existing app backend (terminal B)

App source: `daksha-app/android-app/backend/server.py`. It already forwards complete case JSON and an Authorization header. Configure:

```sh
export MODEL_REVIEW_URL='http://127.0.0.1:8081/review'
read -s 'MODEL_API_KEY?Paste shared VERIDEX key: '
export MODEL_API_KEY
echo
python server.py --port 8080
```

The current app backend rejects HTTP model endpoints. For SAME-MACHINE development only, replace its HTTPS-only condition with the following and add `from urllib.parse import urlparse`:

```python
parsed = urlparse(endpoint)
local_dev = parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost'}
if parsed.scheme != 'https' and not local_dev:
    return jsonify(error='Use HTTPS or a same-machine loopback development endpoint'), 503
```

Change the model `urlopen(..., timeout=45)` to `timeout=420`, since the current model request can take 180 seconds plus one HTTP-server-error retry. The Android review HTTP client must also wait long enough or use background review jobs. Do not enable arbitrary HTTP or expose the unauthenticated app backend to the internet.

Configure Android's existing Connection screen:

- Emulator: `http://10.0.2.2:8080`.
- USB phone: `adb reverse tcp:8080 tcp:8080`, then `http://127.0.0.1:8080`.
- Remote teammate on another computer: run both servers on their computer, or deploy an authenticated HTTPS model service and use its real URL. `127.0.0.1` on their computer does not reach Darshan's machine.

Current branch inspection found imports from `com.veridex.app.data` but no corresponding data-package Kotlin files in the remote tree. The app developer should commit those missing local files before expecting a clean checkout to compile. Android build/device testing has not been performed by this integration task.

## 3. Contract (already matches the backend's expected finding)

`POST /review`, header `Authorization: Bearer <MODEL_API_KEY>`, body: existing case JSON with `photos[]`. The first photo is `before`; the last is `after` or `recapture`. Each has `image_base64`; the original has normalized `region: [x1,y1,x2,y2]`. Our adapter uses the original and latest completion image. Previous recaptures remain in the app's own history.

```json
{
  "outcome": "insufficient_evidence",
  "explanation": "The original area is covered.",
  "next_photo": "Provide an unobstructed view.",
  "training_case_id": null,
  "human_review_required": true,
  "inference_engine": "hosted_gemma_base"
}
```

Invalid key: 401. Missing/invalid data: 400. Model service/output failure: 502, never a repair finding. The service has a 28 MB JSON body cap and 10 MB per decoded image cap. Resize before upload. Secret keys remain in backend process environments, never in Kotlin source or APK settings.

## 4. Collect training data only with permission

Default is **no training storage**. Add a separate opt-in in the app, and persist/forward these fields through its case model and `backend/server.py`'s `validate` return value:

```json
{
  "training_consent": true,
  "consent_receipt": "opaque-consent-record-id",
  "site_group": "opaque-stable-road-site-id"
}
```

Do not hardcode consent true. Do not use exact GPS or someone's name as site_group. The collector records a per-app hashed site group, stripped image metadata, AI result and the consent reference. It does not blur visible faces or plates; review those before approving an export. GPS, location text and app notes are not copied into the training store.

The existing app backend currently strips these new fields and does not preserve `training_case_id` in its finding. The friend must explicitly add those fields; otherwise review works but collection stays OFF.

An authorized backend reviewer with a separate `--role reviewer` key can call:

`POST /v1/cases/<training_case_id>/label`

```json
{"label":"visible_defect_remains","reviewer_ref":"reviewer-01","export_approved":true,"synthetic":false}
```

Optional `observation` must contain the exact validated policy fields and agree with the human label. Model outputs alone are NOT training ground truth. `POST /v1/cases/<id>/withdraw` with the client key excludes that app's case from future exports. Existing Git history requires separate deletion handling.

## 5. Save approved data to a PRIVATE GitHub dataset repository

Create a separate private dataset repo with a README, authenticate GitHub CLI on the collection server, and run:

```sh
python -m veridex.sync_dataset --repo OWNER/PRIVATE-DATASET-REPO
```

For ongoing synchronization, add `--watch 60`. It exports only consented, human-labelled, export-approved cases and refuses public repositories. It updates `veridex-cases/labels.jsonl` plus images; withdrawn cases leave the current snapshot but not old Git history. The main public code repo must not receive citizen images. No dataset repository has been configured or uploaded yet. Git is suitable for a small pilot; use private object storage with proper deletion controls as volume grows.

## 6. Friend's test checklist

1. Start both services and check `/health`.
2. Upload original + repaired examples; request review in app.
3. Upload blocked completion; check targeted photo request and recapture handling.
4. Reuse original as completion; expect `insufficient_evidence`.
5. Wrong API key must fail. Model disconnected must display an error, not a repair finding.
6. Consent OFF must save no training case; consent ON must return a training case ID.
7. Only a reviewer key can label; cases from another app must be inaccessible.
8. Label, approve and export to private dataset repo; verify permission withdrawal removes the current snapshot on next sync.

This is a development integration, not a production service. Production needs HTTPS, per-user case authorization, revocation/rotation, rate limits, retention controls and job-based review.
