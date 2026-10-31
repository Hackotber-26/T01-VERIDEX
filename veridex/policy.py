"""Conservative evidence policy. Model observations are untrusted input."""
import json

FIELDS = {
    'same_scene': {'yes', 'no', 'uncertain'},
    'original_defect_visible': {'yes', 'no', 'uncertain'},
    'target_visible_after': {'yes', 'no', 'uncertain'},
    'obstruction': {'yes', 'no', 'uncertain'},
    'appearance': {'repair_visible', 'defect_visible', 'uncertain'},
}
REQUESTS = {
    'REUSED_PHOTO': 'The completion image repeats the original photograph. Provide a newly captured completion view of the marked area with shared landmarks.',
    'SCENE_UNCERTAIN': 'Provide a wider view of the original marked area with shared permanent landmarks. Capture only from a safe position.',
    'ORIGINAL_UNCLEAR': 'Provide an original image that clearly shows the reported pothole and surrounding landmarks.',
    'TARGET_NOT_VISIBLE': 'Provide a view showing the entire marked area and surrounding landmarks from a safe position.',
    'OBSTRUCTED': 'Provide an unobstructed view of the marked area when safely possible. Do not enter traffic.',
    'VISUAL_CHANGE_UNCERTAIN': 'Provide a clearer view of the marked surface plus a wider context image from a safe position.',
    'MODEL_UNAVAILABLE': 'Retry analysis or send the evidence to a human reviewer.',
    'MODEL_OUTPUT_INVALID': 'Send this evidence to a human reviewer; the model response could not be validated.',
    'LOW_IMAGE_QUALITY': 'Provide clear, adequately lit photos of the marked area and surrounding landmarks.',
}

def insufficient(code, observation=None):
    return {'outcome': 'insufficient_evidence', 'reason_codes': [code],
            'next_request': REQUESTS[code], 'observations': observation,
            'human_review_required': True, 'certifies_repair_quality': False}

def parse_observation(text):
    text = text.strip()
    if text.startswith('```json') and text.endswith('```'):
        text = text[7:-3].strip()
    elif text.startswith('```') and text.endswith('```'):
        text = text[3:-3].strip()
    obj = json.loads(text)
    if not isinstance(obj, dict) or set(obj) != set(FIELDS) | {'evidence'}:
        raise ValueError('Unexpected observation schema')
    for field, allowed in FIELDS.items():
        if not isinstance(obj[field], str) or obj[field] not in allowed:
            raise ValueError('Invalid observation value')
    if not isinstance(obj['evidence'], str) or not 1 <= len(obj['evidence'].strip()) <= 1500:
        raise ValueError('Invalid evidence description')
    return obj

def decide(obj):
    # Revalidate even when called directly by an integration.
    obj = parse_observation(json.dumps(obj))
    checks = [
        (obj['same_scene'] != 'yes', 'SCENE_UNCERTAIN'),
        (obj['original_defect_visible'] != 'yes', 'ORIGINAL_UNCLEAR'),
        (obj['obstruction'] != 'no', 'OBSTRUCTED'),
        (obj['target_visible_after'] != 'yes', 'TARGET_NOT_VISIBLE'),
        (obj['appearance'] == 'uncertain', 'VISUAL_CHANGE_UNCERTAIN'),
    ]
    failures = [code for failed, code in checks if failed]
    if failures:
        result = insufficient(failures[0], obj)
        result['reason_codes'] = failures
        return result
    return {'outcome': 'visible_repair_evidence' if obj['appearance'] == 'repair_visible' else 'visible_defect_remains',
            'reason_codes': [], 'next_request': None, 'observations': obj,
            'human_review_required': True, 'certifies_repair_quality': False}
