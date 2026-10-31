# Round-one demo run sheet (no API key)

## Start

1. Install and open VERIDEX; keep Wi-Fi and mobile data off to show this path is bundled locally.
2. From the home screen tap **Explore the evidence-review demo**. No backend URL or API key is required.
3. Present the three tabs in order: **Work in progress**, **Patch visible**, **Pothole remains**. Each tab changes the real photo and shows a preset response with a specific follow-up where evidence is incomplete.
4. Point out the photo credit link and the **REAL PUBLIC PHOTO · SCRIPTED RESULT** label. The result card also says demo result, not AI prediction.
5. Tap **Start a real case** only if you want to show camera capture; real upload/review requires a backend.

## What to say

“Today we’re showing the evidence workflow and the kinds of responses the product can present. The three photos are real, public reference photos. The response is scripted, the images are not paired, and no AI inference is running. Once the API adapter is configured, the same result format will be populated by our model.”

## Demo scenarios

| Tab | Real photo | Preset illustrative response |
|---|---|---|
| Work in progress | U.S. Air Force repair worker at a pothole | Insufficient evidence: capture the finished surface. |
| Patch visible | Recently patched potholes, Fairfax County, Virginia | Visible repair evidence, with an explicit durability caveat. |
| Pothole remains | Damaged asphalt road | Visible defect remains. |

This is a presentation pack, not a labeled validation set. See `app/src/main/assets/demo/ATTRIBUTION.md` for attribution and license details.
