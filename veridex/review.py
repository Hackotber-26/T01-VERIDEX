import json
import numpy as np
from .images import load_image, crop_roi, quality, jpeg, validate_roi
from .gemma import infer, ProviderError
from .policy import parse_observation, decide, insufficient

def review(before, after, roi, provider=None):
    validate_roi(roi)
    original, completion = load_image(before), load_image(after)
    crop = crop_roi(original, roi)
    checks = {'before': quality(original), 'target_crop': quality(crop), 'after': quality(completion)}
    if original.size == completion.size and np.array_equal(np.asarray(original), np.asarray(completion)):
        result = insufficient('REUSED_PHOTO')
    elif any(q['low_quality'] for q in checks.values()):
        result = insufficient('LOW_IMAGE_QUALITY')
    else:
        try:
            text = (provider or infer)([jpeg(original), jpeg(crop), jpeg(completion)], roi)
            result = decide(parse_observation(text))
        except ProviderError as exc:
            result = insufficient('MODEL_UNAVAILABLE')
            result['provider_error'] = str(exc)
        except (ValueError, TypeError):
            result = insufficient('MODEL_OUTPUT_INVALID')
    result.update({'quality_checks': checks, 'engine': 'gemma_baseline+aecp',
                   'policy_version': '0.2.0', 'trained_weights': False})
    return result
