import base64
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from server import app


class UploadContractTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        app.config.update(TESTING=True, DATA_DIR=Path(self.temp.name))
        self.client = app.test_client()
        image = io.BytesIO()
        Image.new("RGB", (48, 48), "gray").save(image, format="JPEG")
        self.photo = {"role": "before", "region": [.2, .2, .8, .8], "time": 1, "image_base64": base64.b64encode(image.getvalue()).decode()}
        self.case = {"id": "12345678-1234-1234-1234-123456789abc", "location": "Test road", "revision": 1, "review_consent": True, "review_consent_revision": 1, "review_consent_at": 1770000000000, "photos": [self.photo]}

    def tearDown(self):
        self.temp.cleanup()

    def upload(self):
        return self.client.post("/v1/cases/sync", json=self.case)

    def test_upload_is_durable_and_idempotent(self):
        self.assertEqual(self.upload().status_code, 200)
        self.assertEqual(self.upload().status_code, 200)
        saved = Path(self.temp.name) / self.case["id"]
        self.assertEqual(len(list(saved.glob("*.jpg"))), 1)
        self.assertEqual(json.loads((saved / "case.json").read_text())["location"], "Test road")

    def test_same_revision_cannot_change_evidence(self):
        self.upload()
        self.case["location"] = "Another road"
        self.assertEqual(self.upload().status_code, 409)

    def test_path_traversal_rejected(self):
        self.case["id"] = "../../escape"
        self.assertEqual(self.upload().status_code, 400)

    def test_invalid_photo_rejected(self):
        self.photo["image_base64"] = base64.b64encode(b"not a photo").decode()
        self.assertEqual(self.upload().status_code, 400)

    def test_invalid_roi_rejected(self):
        self.photo["region"] = [.9, .2, .1, .8]
        self.assertEqual(self.upload().status_code, 400)

    def test_no_ai_does_not_produce_a_finding(self):
        self.case["photos"].append({**self.photo, "role": "after"})
        self.upload()
        with patch.dict(os.environ, {"VERIDEX_APP_KEY": "", "MODEL_API_KEY": ""}):
            result = self.client.post(f"/v1/cases/{self.case['id']}/review", json={"revision": 1})
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("outcome", result.json)

    def test_stale_review_rejected(self):
        self.upload()
        self.assertEqual(self.client.post(f"/v1/cases/{self.case['id']}/review", json={"revision": 2}).status_code, 409)

    def test_original_alone_cannot_be_reviewed(self):
        self.upload()
        self.assertEqual(self.client.post(f"/v1/cases/{self.case['id']}/review", json={"revision": 1}).status_code, 400)

    def test_malformed_model_finding_rejected(self):
        self.case["photos"].append({**self.photo, "role": "after"})
        self.upload()
        with patch.dict(os.environ, {"VERIDEX_APP_KEY": "registered", "MODEL_API_KEY": "local-test-key"}), patch("server.run_model_review", return_value={"outcome": "approved", "observations": {"evidence": "Region obscured"}, "next_request": "Show the marked area without obstruction"}):
            result = self.client.post(f"/v1/cases/{self.case['id']}/review", json={"revision": 1})
        self.assertEqual(result.status_code, 502)

    def test_valid_model_result(self):
        self.case["photos"].append({**self.photo, "role": "after"})
        self.upload()
        expected = {"outcome": "insufficient_evidence", "explanation": "Region obscured", "next_photo": "Show the marked area without obstruction"}
        analysis = {"outcome": "insufficient_evidence", "observations": {"evidence": "Region obscured"}, "next_request": "Show the marked area without obstruction"}
        with patch.dict(os.environ, {"VERIDEX_APP_KEY": "registered", "MODEL_API_KEY": "local-test-key"}), patch("server.run_model_review", return_value=analysis):
            result = self.client.post(f"/v1/cases/{self.case['id']}/review", json={"revision": 1})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json, expected)


if __name__ == "__main__":
    unittest.main()
