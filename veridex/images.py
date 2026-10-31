from io import BytesIO
from pathlib import Path
import math
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
import cv2
import numpy as np

MAX_BYTES = 10 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 24_000_000

def load_image(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Each image must be 10 MB or smaller')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(path) as source:
                source.load()
                image = ImageOps.exif_transpose(source).convert('RGB')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('Invalid or excessively large image') from exc
    if min(image.size) < 64:
        raise ValueError('Image dimensions must be at least 64 pixels')
    image.thumbnail((1600, 1600))
    return image

def validate_roi(roi):
    if len(roi) != 4 or any(not math.isfinite(x) or x < 0 or x > 1 for x in roi):
        raise ValueError('ROI must contain four finite normalized coordinates between 0 and 1')
    if roi[0] >= roi[2] or roi[1] >= roi[3]:
        raise ValueError('ROI must have positive width and height')
    return list(roi)

def crop_roi(image, roi):
    validate_roi(roi)
    w, h = image.size
    box = (int(roi[0]*w), int(roi[1]*h), int(roi[2]*w), int(roi[3]*h))
    if box[2]-box[0] < 16 or box[3]-box[1] < 16:
        raise ValueError('Marked area must be at least 16 by 16 pixels after resizing')
    return image.crop(box)

def quality(image):
    gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
    # These are uncalibrated screening heuristics, not repair classifiers.
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    darkness = float(np.mean(gray < 15))
    brightness = float(np.mean(gray > 245))
    return {'laplacian_variance': round(sharpness, 2), 'dark_fraction': round(darkness, 3),
            'bright_fraction': round(brightness, 3),
            'low_quality': sharpness < 30 or darkness > .85 or brightness > .85}

def jpeg(image):
    stream = BytesIO()
    image = image.copy()
    image.thumbnail((1024, 1024))
    image.save(stream, format='JPEG', quality=85)
    return stream.getvalue()
