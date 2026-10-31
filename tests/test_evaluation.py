import unittest
from veridex.evaluate import score

class MetricTests(unittest.TestCase):
    def test_failures_not_counted_as_correct_abstentions(self):
        cases=[{'id':'a','label':'insufficient_evidence'}]
        result=score(cases,[{'id':'a','result':{'outcome':'insufficient_evidence','reason_codes':['MODEL_UNAVAILABLE']}}])
        self.assertIsNone(result['accuracy_completed'])
        self.assertEqual(result['correct_abstention_rate_all_insufficient_cases'],0)
        self.assertEqual(result['provider_or_output_failures'],1)

    def test_false_approval_and_missing_are_visible(self):
        cases=[{'id':'a','label':'visible_defect_remains'},{'id':'b','label':'visible_repair_evidence'}]
        result=score(cases,[{'id':'a','result':{'outcome':'visible_repair_evidence','reason_codes':[]}}])
        self.assertEqual(result['false_discovery_rate_repair'],1)
        self.assertEqual(result['missing'],1)
        self.assertEqual(result['correct_result_rate_all_cases'],0)

    def test_duplicate_prediction_rejected(self):
        with self.assertRaises(ValueError):score([], [{'id':'a'},{'id':'a'}])
