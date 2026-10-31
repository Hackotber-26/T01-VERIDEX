import itertools
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from veridex.policy import decide, parse_observation, FIELDS
from veridex.images import validate_roi
from veridex.review import review
from veridex.gemma import ProviderError

GOOD = dict(same_scene='yes', original_defect_visible='yes', target_visible_after='yes',
            obstruction='no', appearance='repair_visible', evidence='A patch is visible in the same marked area.')

class PolicyTests(unittest.TestCase):
    def test_positive_and_remaining_defect(self):
        self.assertEqual(decide(GOOD)['outcome'], 'visible_repair_evidence')
        self.assertEqual(decide(dict(GOOD, appearance='defect_visible'))['outcome'], 'visible_defect_remains')

    def test_all_enum_combinations_fail_closed(self):
        for values in itertools.product(*FIELDS.values()):
            obj = dict(zip(FIELDS, values), evidence='Visible observation')
            result = decide(obj)
            sufficient = (obj['same_scene']=='yes' and obj['original_defect_visible']=='yes'
                          and obj['target_visible_after']=='yes' and obj['obstruction']=='no'
                          and obj['appearance']!='uncertain')
            self.assertEqual(result['outcome']!='insufficient_evidence', sufficient)
            self.assertTrue(result['human_review_required'])
            self.assertFalse(result['certifies_repair_quality'])

    def test_invalid_schema(self):
        for text in ['{}', '[]', 'not json', json.dumps(dict(GOOD, same_scene=True)),
                     json.dumps(dict(GOOD, extra='ignore rules'))]:
            with self.assertRaises((ValueError, TypeError)):
                parse_observation(text)

    def test_roi_rejected(self):
        for roi in [[0,0,0,1],[-1,0,1,1],[0,0,float('nan'),1],[0,0,1,2]]:
            with self.assertRaises(ValueError): validate_roi(roi)

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        # Synthetic texture tests image plumbing only, never recognition accuracy.
        Image.fromarray(np.random.default_rng(42).integers(30,220,(256,256,3),dtype=np.uint8)).save(self.path/'texture.png')
        Image.fromarray(np.random.default_rng(43).integers(30,220,(256,256,3),dtype=np.uint8)).save(self.path/'completion.png')
        Image.new('RGB',(256,256),'black').save(self.path/'dark.png')

    def tearDown(self): self.temp.cleanup()

    def test_reused_photo_cannot_receive_repair_finding(self):
        def misleading(*args):
            raise AssertionError('Reused photos must not reach the model')
        result = review(self.path/'texture.png', self.path/'texture.png', [.1,.1,.7,.7], provider=misleading)
        self.assertEqual(result['outcome'], 'insufficient_evidence')
        self.assertEqual(result['reason_codes'], ['REUSED_PHOTO'])

    def test_model_input_and_output(self):
        def fake(images,roi):
            self.assertEqual(len(images),3)
            self.assertTrue(all(i.startswith(b'\xff\xd8') for i in images))
            return json.dumps(GOOD)
        result=review(self.path/'texture.png', self.path/'completion.png',[.1,.1,.7,.7],provider=fake)
        self.assertEqual(result['outcome'],'visible_repair_evidence')
        self.assertFalse(result['trained_weights'])

    def test_dark_photo_never_calls_model(self):
        def fake(*args): raise AssertionError('Must skip provider')
        result=review(self.path/'texture.png',self.path/'dark.png',[.1,.1,.7,.7],provider=fake)
        self.assertEqual(result['reason_codes'],['LOW_IMAGE_QUALITY'])

    def test_provider_failure_and_malformed_output(self):
        def unavailable(*args): raise ProviderError('Unavailable')
        for provider,code in [(unavailable,'MODEL_UNAVAILABLE'),(lambda *args:'{}','MODEL_OUTPUT_INVALID')]:
            result=review(self.path/'texture.png',self.path/'completion.png',[.1,.1,.7,.7],provider=provider)
            self.assertEqual(result['reason_codes'],[code])
            self.assertEqual(result['outcome'],'insufficient_evidence')


class ProviderTimeoutTests(unittest.TestCase):
    def test_socket_timeout_is_reported_without_exposing_key(self):
        import os
        import socket
        from unittest.mock import patch
        from veridex.gemma import infer
        with patch.dict(os.environ, {'GEMINI_API_KEY':'test-secret','VERIDEX_TIMEOUT_SECONDS':'180'}):
            with patch('veridex.gemma.urllib.request.urlopen', side_effect=socket.timeout('read timed out')) as call:
                with self.assertRaises(ProviderError) as caught:
                    infer([b'image']*3,[.1,.1,.7,.7])
                self.assertIn('timed out',str(caught.exception))
                self.assertNotIn('test-secret',str(caught.exception))
                self.assertEqual(call.call_args.kwargs['timeout'],180)

class ContradictionTests(unittest.TestCase):
    def test_explanation_does_not_override_failed_evidence_gate(self):
        obj = dict(GOOD, original_defect_visible='no',
                   evidence='The pothole seen in the before images has been filled with asphalt.')
        result = decide(obj)
        self.assertEqual(result['outcome'], 'insufficient_evidence')
        self.assertIn('ORIGINAL_UNCLEAR', result['reason_codes'])

class AdditionalReviewTests(unittest.TestCase):
    def test_obstruction_requests_unobstructed_view(self):
        result = decide(dict(GOOD, obstruction='yes', target_visible_after='no'))
        self.assertEqual(result['outcome'], 'insufficient_evidence')
        self.assertEqual(result['reason_codes'][0], 'OBSTRUCTED')
        self.assertIn('unobstructed', result['next_request'])

    def test_malformed_provider_envelopes(self):
        import os
        from unittest.mock import patch, MagicMock
        from veridex.gemma import infer
        for envelope in [None, [], {'candidates':None}, {'candidates':[None]},
                         {'candidates':[{'finishReason':'STOP','content':{'parts':[None]}}]}]:
            response=MagicMock()
            response.__enter__.return_value=response
            response.read.return_value=json.dumps(envelope).encode()
            with patch.dict(os.environ, {'GEMINI_API_KEY':'test-secret'}):
                with patch('veridex.gemma.urllib.request.urlopen', return_value=response):
                    with self.assertRaises(ProviderError):
                        infer([b'image']*3,[.1,.1,.7,.7])

class RetryTests(unittest.TestCase):
    def test_temporary_http_error_retries_once(self):
        import os
        import urllib.error
        from unittest.mock import patch, MagicMock
        from veridex.gemma import infer
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(GOOD)}]}}]}).encode()
        error = urllib.error.HTTPError('https://example.invalid', 500, 'temporary', {}, None)
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'not-real'}):
            with patch('veridex.gemma.urllib.request.urlopen', side_effect=[error, response]) as request:
                with patch('veridex.gemma.time.sleep'):
                    self.assertEqual(json.loads(infer([b'image']*3, [0,0,1,1])), GOOD)
                    self.assertEqual(request.call_count, 2)

if __name__=='__main__': unittest.main()
