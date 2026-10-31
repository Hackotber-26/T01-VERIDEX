# Prototype verification — 31 October 2026

## Passed

- `gradlew.bat assembleDebug lintDebug`: build successful, zero lint errors. Remaining warnings concern newer dependency/target versions, backup configuration and optional Kotlin conveniences; they are not suppressed.
- `backend/.venv/Scripts/python.exe -m unittest -v test_server`: all 10 tests passed.
- Installed the debug APK on the Medium Phone API 36 emulator.
- Opened and visually inspected the overview and photo-marking screens. Fixed status-bar contrast and rebuilt the APK.
- Granted camera permission, captured the emulator's virtual-camera image, marked/confirmed the region, entered a landmark, and saved a case.
- Added a completion photo to that same case, retaining the original.
- Uploaded both revisions from Android through WorkManager to the local Flask server on port 8787. Confirmed HTTP 200 and persisted images/metadata on disk.
- Requested a review with no model configured. The app displayed the explicit disconnected-AI error and retained evidence; it did not fabricate an outcome.
- Installed the updated APK and force-stopped/reopened the app. The saved case and upload state survived.
- Opened the scripted demo and switched to visible-repair evidence. Demo findings are labelled and remain separate from real cases.
- Upgraded and installed the v0.2 APK on the same emulator; retained existing local case data.
- Completed the Hindi onboarding and confirmed Hindi main navigation, then opened the capture guide again from Settings.
- Opened the case detail and shared a generated PDF through Android's share sheet; confirmed the PDF file was generated.
- Uploaded original and completion photos and confirmed backend persistence. Server now also validates optional client SHA-256 against the received image bytes and retains source, quality, and coordinate metadata.
- Build after v0.2 changes: `assembleDebug lintDebug` succeeds. Backend suite: all 10 tests pass.
- Follow-up fix 0.2.1: emulator location permission prompt appeared automatically on repair-photo review. After granting, a mock current location was attached automatically and displayed with approximately 15 m accuracy. This confirmed fresh-location capture works with the emulator's simulated coordinate.
- No AndroidRuntime crash was reported during these checks.

## Not yet verified

- Physical phone cameras, outdoor location acquisition, denied-permission recovery, photo picker across device vendors, and all Android versions.
- Airplane-mode/OS-killed background retry behaviour on physical phones (queue/retry code is present).
- Version 2.1 was built, but the actual provider request has not been made with a real before/after pair. Live key validity, provider quota/model availability and real-photo accuracy remain unverified.
- Production authentication, reviewer accounts, deployment and Play Store release. The included backend is development-only.

## Version 2.1 integration

- The real app now requires explicit consent for the current photo revision before upload or AI review. Adding evidence invalidates consent; withdrawing consent cancels queued upload work and requests deletion of the backend case.
- The local backend loads its ignored `backend/.env`, checks app registration and model-key presence, then calls the repository's `veridex.review` pipeline. The API key is not embedded in Android source or the APK.
- The Connection screen's health check reports configuration only; it does not send images to the provider. The live provider call and findings still require a user-consented photo pair.
- No human-label approval or model-training workflow is part of this client scope.

## Version 2.1.1 provider-failure clarity

- Provider request failures are labelled as a model-review failure instead of being presented as an image needing a clearer view. The app advises that no new photo is needed and offers a retry.
- The backend returns only safe provider diagnostics (such as HTTP status or timeout category) and excludes credentials and provider response bodies.
- `assembleDebug lintDebug` succeeds. The provider was not called during this update; verify the exact key/model error by retrying a consented review with the updated backend.

## Version 2.2.0 PR #1 integration

- PR #1 adds distinct Gemini/app credentials, one-time app-key registration, optional training collection consent, local collection storage, operator labeling, and explicit private-repository export.
- Review consent remains required for uploads. Training consent is off by default and separately required before a successful review is added to the local training collection.
- Automated tests use injected/mock model results; live Gemini review remains unverified until a valid Google AI Studio key is supplied privately.

## v0.2 checks not yet performed

- Outdoor, physical-device GPS and camera overlay alignment, notification delivery at the scheduled time, voice recognition availability, gallery import from several Android vendors, duplicate-image warning and offline queue retry after process death.
- Physical device location quality and behavior with Location disabled or permission denied.
- Kannada walkthrough and complete translation of explanatory detail text. The language selector localizes onboarding, primary navigation and selected core actions; much of the remaining copy is currently English.
- The captured test image is the Android emulator's indoor virtual scene, not pothole evidence or an AI evaluation sample. It is not bundled as a default case in the APK.
