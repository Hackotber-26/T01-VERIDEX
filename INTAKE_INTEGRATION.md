# Optional intake features

These additions extend the local Android Flask backend. Start it using APP_INTEGRATION.md.
They use the existing hosted Gemma model and image/location heuristics; no new weights were trained.

1. Upload a case using the existing POST /v1/cases/sync route, with current review consent.
2. POST /v1/cases/CASE_ID/analyze with JSON {"revision": 1}.
   Response includes potholes (normalized x1,y1,x2,y2 boxes), evidence, quality_checks,
   human_review_required, and annotated_image_base64 (JPEG). Display boxes as editable suggestions.
   Ask the user to confirm one before saving its region in a NEW evidence revision.
   Empty boxes mean no clear suggestion, not proof the road is safe. On 502 retain manual marking.
   Poor photos return recapture_required without calling the provider.
3. GET /v1/cases/CASE_ID/related to show candidate complaint links.
   Identical original uploads are possible_duplicate. Different images require GPS accuracy <=25m,
   distance <=25m and similar perceptual signatures. These thresholds are uncalibrated.
   possible_recurring_damage additionally requires the older case's current review to show
   visible_repair_evidence, with server review time before the new case's first server receipt.
   This flags a possible history for inspection; it does not prove that a repair failed.

Example calls (backend running on your computer):

```sh
curl -X POST http://127.0.0.1:8080/v1/cases/CASE_ID/analyze -H 'Content-Type: application/json' -d '{"revision":1}'
curl http://127.0.0.1:8080/v1/cases/CASE_ID/related
```

The Android screens still need buttons/overlays for these optional routes. Existing repair review
and separate training permission are unchanged. Results do not become training labels automatically.
Related-report scans are local and linear in stored cases, intended for a small hackathon pilot.
This backend is local development only; add user authorization, tenant isolation, TLS and indexing
before a multi-app deployment. Neither feature has independently measured field accuracy yet.
