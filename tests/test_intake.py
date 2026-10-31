import json
import unittest
from PIL import Image
from unittest.mock import patch
from veridex.intake import mark_potholes, related_reports, distance_m


class IntakeTests(unittest.TestCase):
    def test_low_quality_does_not_call_provider(self):
        def forbidden(*args, **kwargs):
            self.fail('Provider should not run')
        self.assertEqual(mark_potholes(Image.new('RGB', (64, 64)), forbidden)['status'], 'recapture_required')

    def test_boxes_validated_and_not_auto_confirmed(self):
        with patch('veridex.intake.quality', return_value={'low_quality': False}):
            result = mark_potholes(Image.new('RGB', (64, 64)), lambda *a, **k: json.dumps({'potholes': [[.1, .2, .8, .9]], 'evidence': 'Visible depression'}))
            self.assertTrue(result['human_review_required'])
            with self.assertRaises(ValueError):
                mark_potholes(Image.new('RGB', (64, 64)), lambda *a, **k: json.dumps({'potholes': [[.9, .2, .1, .8]], 'evidence': 'Bad box'}))

    def test_reused_image_is_duplicate_not_recurring(self):
        case = {'id': 'new', 'photos': [{'sha256': 'same'}], 'received_at_ms': 20}
        old = {'id': 'old', 'photos': [{'sha256': 'same'}]}
        result = related_reports(case, [case, old], lambda *a: Image.new('RGB', (64, 64)), lambda *a: {'outcome': 'visible_repair_evidence', 'reviewed_at_ms': 10})
        self.assertEqual(result['suggestions'][0]['type'], 'possible_duplicate')
        self.assertFalse(result['automatically_merged'])

    def test_nearby_recurrence_requires_prior_review_and_visual_match(self):
        photo = {'sha256': 'new', 'latitude': 12.97, 'longitude': 77.59, 'accuracy_meters': 5}
        case = {'id': 'new', 'photos': [photo], 'received_at_ms': 20}
        old = {'id': 'old', 'photos': [{**photo, 'sha256': 'old'}]}
        with patch('veridex.intake.signature', return_value=123):
            result = related_reports(case, [old], lambda *a: None, lambda *a: {'outcome': 'visible_repair_evidence', 'reviewed_at_ms': 10})
            self.assertEqual(result['suggestions'][0]['type'], 'possible_recurring_damage')
            old['photos'][0]['longitude'] = 78
            self.assertEqual(related_reports(case, [old], lambda *a: None, lambda *a: {})['suggestions'], [])

    def test_missing_or_poor_gps_does_not_link(self):
        self.assertIsNone(distance_m({}, {}))
        point = {'latitude': 12.97, 'longitude': 77.59, 'accuracy_meters': 100}
        self.assertIsNone(distance_m(point, point))


if __name__ == '__main__':
    unittest.main()
