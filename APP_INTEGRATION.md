# Send this to Daksha: current app integration + training collection

Use the pull request branch `fix/app-training-collection`, targeting `daksha-app`. It merges the shared model/collector code from main. This guide supersedes the older external MODEL_REVIEW_URL setup for this app: the local Flask backend now calls `veridex.review` directly.

## 1. Keys (different purposes)

- `VERIDEX_APP_KEY`: shared private app registration key, supplied separately by Darshan. Register its hash with this checkout. It never belongs in Kotlin or Git.
- `GEMINI_API_KEY`: Google provider credential, only on the machine running the backend. Do NOT put the VERIDEX key here.
- `MODEL_API_KEY`: no longer used by this branch; remove it from old .env files to avoid confusion.

The app uses hosted Gemma 4 26B-A4B + AECP. The E4B training adapter is experimental and is not loaded by this backend. No public model endpoint is deployed.

## 2. Checkout and install

```sh
git fetch origin
git switch fix/app-training-collection
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r android-app/backend/requirements.txt
```

Windows: activate with `.venv\Scripts\Activate.ps1` and use `python` instead of `python3`.

Copy `android-app/backend/.env.example` to `android-app/backend/.env` and fill in the two keys privately. On first setup, register that SAME app key from the repository root. macOS zsh:

```sh
read -s 'VERIDEX_APP_KEY?Paste shared app key: '
export VERIDEX_APP_KEY
python -m veridex.api --register-app daksha-app --key-from-env
```

Windows PowerShell: set `$env:VERIDEX_APP_KEY` locally, then run the same registration command. Do not send commands containing actual secrets to chat or commit .env. Registration is per checkout. It does not authenticate individual phone users; this remains a localhost development backend.

Run:

```sh
python android-app/backend/server.py --port 8080
```

`GET /health` should show app_registered and model_configured true. This checks configuration only; it does not verify Google credentials or model availability. A wrong/unregistered app key fails registration checks; Google connection failures return errors, not repair findings.

## 3. Android test connection

Open `android-app` in Android Studio, build using JDK 17/21 and SDK 35.

- Emulator Connection URL: `http://10.0.2.2:8080`
- USB phone: run `adb reverse tcp:8080 tcp:8080`, then use `http://127.0.0.1:8080`.
- A remote friend must run the backend on THEIR computer with their authorized Google key, or use an authenticated HTTPS deployment. Your localhost is not reachable from their laptop.

No model secrets go into the APK. Review requests now wait up to 420 seconds; upload timeout remains 60 seconds. Production should use background review jobs, HTTPS and user/case authentication.

## 4. Exact training collection test

1. Capture/import original + completion photos and mark the original target.
2. Give consent for AI review of this revision.
3. Leave **Optional: help train VERIDEX** OFF; upload and review. No training record should be created.
4. Turn the training option ON. Changing permission clears the backend copy/finding; upload again, then review.
5. A successful review now returns `training_case_id`, and the collector stores metadata-free images, original ROI, model result, app ID, consent receipt and an opaque hashed case grouping under `.local/collection/`.
6. Re-reviewing the same revision reuses the training case ID instead of creating duplicates.
7. New photos reset both permissions. Withdrawal removes local training image files and makes the case ineligible for export. Old Git commits require separate cleanup if a case was previously exported.

Review permission and training permission are SEPARATE. Do not preselect training consent. The app's backend still stores review evidence locally when review consent is granted. The training collector does not retain precise GPS, location text or notes, but visible faces/plates are not automatically blurred. Screen those before human export approval.

Provider outages/invalid responses return HTTP 502 and do not create training cases or evidence findings. No automatic training job runs from user uploads.

## 5. Human labels and private GitHub storage

Private dataset repository: https://github.com/Hackotber-26/T01-VERIDEX-training-data

It contains only an empty initial manifest at setup. Organization members may need repository access granted separately. Do not make it public. Code stays in T01-VERIDEX; photos must not be committed there.

An operator creates a separate reviewer key for the SAME app ID:

```sh
python -m veridex.api --register-app daksha-app --role reviewer
python -m veridex.api --port 8081
```

Use that reviewer key only on the operator/backend. `POST http://127.0.0.1:8081/v1/cases/TRAINING_CASE_ID/label` with `Authorization: Bearer REVIEWER_KEY` and JSON:

```json
{"label":"visible_defect_remains","reviewer_ref":"reviewer-01","export_approved":true,"synthetic":false}
```

Allowed labels: visible_repair_evidence, visible_defect_remains, insufficient_evidence. Optional human `observation` must follow the strict policy schema and agree with the label. Check consent, image privacy, label correctness and physical-site grouping before approval. Model predictions are not ground truth. Case-based grouping must be consolidated where separate app cases refer to the same physical road before creating train/test splits.

Authenticate GitHub CLI on the operator machine, then:

```sh
python -m veridex.sync_dataset --repo Hackotber-26/T01-VERIDEX-training-data --watch 60
```

The sync loop exports only consented + human-labelled + export-approved cases. It refuses public repositories. It updates the current snapshot; previous Git history retains copies and requires separate deletion handling. Pilot storage only: migrate large/private datasets to object storage with appropriate deletion controls.

## 6. Tests

```sh
python -m unittest discover -s tests -v
cd android-app/backend
python -m unittest -v test_server
```

The automated backend tests use injected AI results, not live Google inference. Check real camera, consent toggles, upload, model review, timeout/error display and private export on a device before declaring the app integrated.
