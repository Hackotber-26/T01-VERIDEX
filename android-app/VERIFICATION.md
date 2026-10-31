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
- The actual VERIDEX model/provider integration and real-photo accuracy. The model source/endpoint was not present in the supplied workspace.
- Production authentication, reviewer accounts, deployment and Play Store release. The included backend is development-only.

## v0.2 checks not yet performed

- Outdoor, physical-device GPS and camera overlay alignment, notification delivery at the scheduled time, voice recognition availability, gallery import from several Android vendors, duplicate-image warning and offline queue retry after process death.
- Physical device location quality and behavior with Location disabled or permission denied.
- Kannada walkthrough and complete translation of explanatory detail text. The language selector localizes onboarding, primary navigation and selected core actions; much of the remaining copy is currently English.
- The captured test image is the Android emulator's indoor virtual scene, not pothole evidence or an AI evaluation sample. It is not bundled as a default case in the APK.
