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
        app.config.update(TESTING=True, DATA_DIR=Path(self.temp.name)/'cases', TRAINING_DIR=Path(self.temp.name)/'training')
        registration=patch('server.registered_app',return_value='daksha-app')
        registration.start(); self.addCleanup(registration.stop)
        self.client = app.test_client()
        image = io.BytesIO()
        Image.new("RGB", (64, 64), "gray").save(image, format="JPEG")
        self.photo = {"role": "before", "region": [.2, .2, .8, .8], "time": 1, "image_base64": base64.b64encode(image.getvalue()).decode()}
        self.case = {"id": "12345678-1234-1234-1234-123456789abc", "location": "Test road", "revision": 1, "review_consent": True, "review_consent_revision": 1, "review_consent_at": 1770000000000, "photos": [self.photo]}

    def tearDown(self):
        self.temp.cleanup()

    def upload(self):
        return self.client.post("/v1/cases/sync", json=self.case)

    def test_upload_is_durable_and_idempotent(self):
        self.assertEqual(self.upload().status_code, 200)
        self.assertEqual(self.upload().status_code, 200)
        saved = Path(self.temp.name) / 'cases' / self.case["id"]
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
        with patch.dict(os.environ, {"VERIDEX_APP_KEY": "", "GEMINI_API_KEY": ""}):
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
        with patch.dict(os.environ, {"VERIDEX_APP_KEY": "registered", "GEMINI_API_KEY": "local-test-key"}), patch("server.run_model_review", return_value={"outcome": "approved", "observations": {"evidence": "Region obscured"}, "next_request": "Show the marked area without obstruction"}):
            result = self.client.post(f"/v1/cases/{self.case['id']}/review", json={"revision": 1})
        self.assertEqual(result.status_code, 502)

    def test_valid_model_result(self):
        self.case["photos"].append({**self.photo, "role": "after"})
        self.upload()
        expected = {"outcome": "insufficient_evidence", "explanation": "Region obscured", "next_photo": "Show the marked area without obstruction", "training_case_id": None}
        analysis = {"outcome": "insufficient_evidence", "observations": {"evidence": "Region obscured"}, "next_request": "Show the marked area without obstruction"}
        with patch.dict(os.environ, {"VERIDEX_APP_KEY": "registered", "GEMINI_API_KEY": "local-test-key"}), patch("server.run_model_review", return_value=analysis):
            result = self.client.post(f"/v1/cases/{self.case['id']}/review", json={"revision": 1})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json, expected)


    def test_provider_failure_is_not_a_finding(self):
        self.case['photos'].append({**self.photo,'role':'after'})
        self.upload()
        analysis={'outcome':'insufficient_evidence','reason_codes':['MODEL_UNAVAILABLE']}
        with patch.dict(os.environ,{'GEMINI_API_KEY':'local-test-key'}), patch('server.run_model_review',return_value=analysis):
            result=self.client.post(f"/v1/cases/{self.case['id']}/review",json={'revision':1})
        self.assertEqual(result.status_code,502)
        self.assertNotIn('outcome',result.json)

    def test_training_collection_is_separate_and_idempotent(self):
        from server import training_store
        self.case['photos'].append({**self.photo,'role':'after'})
        self.case.update(training_consent=True,training_consent_revision=1,training_consent_at=1770000000000)
        self.assertEqual(self.upload().status_code,200)
        analysis={'outcome':'insufficient_evidence','reason_codes':['REUSED_PHOTO'],'next_request':'Upload a new photo.','observations':None}
        with patch.dict(os.environ,{'GEMINI_API_KEY':'local-test-key'}),patch('server.run_model_review',return_value=analysis):
            first=self.client.post(f"/v1/cases/{self.case['id']}/review",json={'revision':1})
            second=self.client.post(f"/v1/cases/{self.case['id']}/review",json={'revision':1})
        self.assertEqual(first.status_code,200)
        case_id=first.json['training_case_id']
        self.assertEqual(case_id,second.json['training_case_id'])
        store=training_store()
        self.assertTrue(store.get('daksha-app',case_id)['training_consent'])
        self.assertEqual(store.eligible(),[])
        self.assertEqual(self.client.delete(f"/v1/cases/{self.case['id']}").status_code,200)
        self.assertFalse(store.get('daksha-app',case_id)['training_consent'])

    def test_marking_route_and_stale_revision(self):
        self.upload()
        url = f"/v1/cases/{self.case['id']}/analyze"
        self.assertEqual(self.client.post(url, json={'revision': 2}).status_code, 409)
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test'}), patch('server.mark_potholes', return_value={'status': 'suggestions_only', 'potholes': [[.2,.2,.8,.8]], 'human_review_required': True}):
            response = self.client.post(url, json={'revision': 1})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['annotated_image_base64'])
        self.assertEqual(response.json['potholes'], [[.2,.2,.8,.8]])

    def test_related_route_duplicate_and_deletion(self):
        self.upload()
        original_id = self.case['id']
        self.case['id'] = 'abcdef12-1234-1234-1234-123456789abc'
        self.upload()
        url = f'/v1/cases/{original_id}/related'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['suggestions'][0]['type'], 'possible_duplicate')
        self.client.delete(f"/v1/cases/{self.case['id']}")
        self.assertEqual(self.client.get(url).json['suggestions'], [])

    def test_invalid_training_permission_is_rejected(self):
        self.case.update(training_consent=True,training_consent_revision=2,training_consent_at=1770000000000)
        self.assertEqual(self.upload().status_code,400)

if __name__ == "__main__":
    unittest.main()
