"""Local development upload API. Run behind authentication/TLS before deployment."""
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import threading
import urllib.error
import urllib.request

from flask import Flask, jsonify, request
from PIL import Image, UnidentifiedImageError

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
app.config["DATA_DIR"] = Path(__file__).parent / "data"
lock = threading.Lock()
OUTCOMES = {"visible_repair_evidence", "visible_defect_remains", "insufficient_evidence"}


def validate(payload):
    if not isinstance(payload, dict):
        raise ValueError("Expected a case object")
    case_id = payload.get("id", "")
    if not isinstance(case_id, str) or not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", case_id):
        raise ValueError("Invalid case ID")
    revision = payload.get("revision")
    if type(revision) is not int or revision < 1:
        raise ValueError("Invalid revision")
    location = payload.get("location")
    if not isinstance(location, str) or not location.strip() or len(location) > 500:
        raise ValueError("A location or landmark is required (max 500 characters)")
    note = payload.get("note", "")
    if not isinstance(note, str) or len(note) > 5000:
        raise ValueError("Notes must be at most 5000 characters")
    photos = payload.get("photos")
    if not isinstance(photos, list) or not 1 <= len(photos) <= 12:
        raise ValueError("A case must have 1 to 12 photos")
    clean = []
    for index, photo in enumerate(photos):
        if not isinstance(photo, dict):
            raise ValueError("Invalid photo")
        role = photo.get("role")
        if role != ("before" if index == 0 else "after" if index == 1 else "recapture"):
            raise ValueError("Photos must be original, after, then recaptures")
        region = photo.get("region", [])
        if not isinstance(region, list) or len(region) != 4 or not all(type(x) in (float, int) and math.isfinite(x) and 0 <= x <= 1 for x in region):
            raise ValueError("Invalid normalized region")
        if region[2] - region[0] < .029 or region[3] - region[1] < .029:
            raise ValueError("Region is too small")
        source = photo.get("source", "camera")
        if source not in {"camera", "gallery"}:
            raise ValueError("Invalid image source")
        declared_sha = photo.get("sha256", "")
        if declared_sha and (not isinstance(declared_sha, str) or not re.fullmatch(r"[a-f0-9]{64}", declared_sha)):
            raise ValueError("Invalid image fingerprint")
        quality = photo.get("quality", {})
        if not isinstance(quality, dict) or any(type(quality.get(key, 0)) is not int or not 0 <= quality.get(key, 0) <= 100 for key in ("brightness", "sharpness")):
            raise ValueError("Invalid image quality metadata")
        latitude, longitude = photo.get("latitude"), photo.get("longitude")
        if (latitude is None) != (longitude is None):
            raise ValueError("Coordinates must include both latitude and longitude")
        if latitude is not None and (type(latitude) not in (float, int) or type(longitude) not in (float, int) or not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
            raise ValueError("Invalid coordinates")
        try:
            raw = base64.b64decode(photo["image_base64"], validate=True)
            if not 0 < len(raw) <= 6_000_000:
                raise ValueError("Image exceeds 6 MB")
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != "JPEG" or max(image.size) > 2400:
                    raise ValueError("Upload normalized JPEG photos up to 2400 pixels")
                image.verify()
        except (KeyError, TypeError, UnidentifiedImageError, OSError) as exc:
            raise ValueError("Invalid JPEG photo") from exc
        actual_sha = hashlib.sha256(raw).hexdigest()
        if declared_sha and declared_sha != actual_sha:
            raise ValueError("Photo fingerprint does not match image bytes")
        clean.append({"role": role, "region": region, "time": photo.get("time"), "source": source, "quality": quality, "latitude": latitude, "longitude": longitude, "accuracy_meters": photo.get("accuracy_meters"), "sha256": actual_sha, "bytes": raw})
    return {"id": case_id, "revision": revision, "location": location.strip(), "note": note, "created": payload.get("created"), "photos": clean}


@app.errorhandler(413)
def too_large(_):
    return jsonify(error="Upload exceeds 40 MB"), 413


@app.get("/health")
def health():
    return jsonify(status="ok", mode="local-development", ai_connected=bool(os.environ.get("MODEL_REVIEW_URL")))


@app.post("/v1/cases/sync")
def sync_case():
    try:
        case = validate(request.get_json(silent=True))
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400
    root = Path(app.config["DATA_DIR"]) / case["id"]
    metadata = {**case, "photos": [{k: v for k, v in p.items() if k != "bytes"} for p in case["photos"]]}
    encoded = json.dumps(metadata, sort_keys=True)
    with lock:
        current = root / "case.json"
        if current.exists():
            old = json.loads(current.read_text())
            if old["revision"] > case["revision"]:
                return jsonify(error="A newer revision already exists"), 409
            if old["revision"] == case["revision"]:
                if json.dumps(old, sort_keys=True) != encoded:
                    return jsonify(error="This revision already contains different evidence"), 409
                return jsonify(id=case["id"], revision=case["revision"], status="uploaded")
        root.mkdir(parents=True, exist_ok=True)
        for photo in case["photos"]:
            target = root / (photo["sha256"] + ".jpg")
            if not target.exists():
                target.write_bytes(photo["bytes"])
        # Keep immutable metadata revisions and atomically publish the current one.
        (root / f"revision-{case['revision']}.json").write_text(encoded)
        pending = root / "case.pending"
        pending.write_text(encoded)
        pending.replace(current)
    return jsonify(id=case["id"], revision=case["revision"], status="uploaded")


@app.post("/v1/cases/<case_id>/review")
def review(case_id):
    if not re.fullmatch(r"[a-f0-9-]{36}", case_id):
        return jsonify(error="Invalid case ID"), 400
    root = Path(app.config["DATA_DIR"]) / case_id
    with lock:
        if not (root / "case.json").exists():
            return jsonify(error="Upload this case first"), 404
        case = json.loads((root / "case.json").read_text())
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get("revision") != case["revision"]:
        return jsonify(error="Upload the latest evidence before reviewing"), 409
    if len(case["photos"]) < 2:
        return jsonify(error="A before and an after photo are required"), 400
    endpoint = os.environ.get("MODEL_REVIEW_URL", "")
    if not endpoint:
        return jsonify(error="AI is not connected yet. Your evidence is uploaded. Configure MODEL_REVIEW_URL and MODEL_API_KEY on the backend."), 503
    if not endpoint.startswith("https://"):
        return jsonify(error="The model adapter requires an HTTPS endpoint"), 503
    model_input = {**case, "photos": [{**p, "image_base64": base64.b64encode((root / (p["sha256"] + ".jpg")).read_bytes()).decode()} for p in case["photos"]]}
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("MODEL_API_KEY")
    if key:
        headers["Authorization"] = "Bearer " + key
    try:
        req = urllib.request.Request(endpoint, json.dumps(model_input).encode(), headers, method="POST")
        with urllib.request.urlopen(req, timeout=45) as response:
            result = json.load(response)
        if not isinstance(result, dict) or result.get("outcome") not in OUTCOMES or not isinstance(result.get("explanation"), str) or not result["explanation"].strip():
            raise ValueError("Invalid structured finding")
        next_photo = result.get("next_photo", "")
        if not isinstance(next_photo, str) or result["outcome"] == "insufficient_evidence" and not next_photo.strip():
            raise ValueError("Missing recapture instructions")
        finding = {"outcome": result["outcome"], "explanation": result["explanation"], "next_photo": next_photo}
        with lock:
            current = json.loads((root / "case.json").read_text())
            if current["revision"] != case["revision"]:
                return jsonify(error="Evidence changed during review. Review the latest revision."), 409
            (root / f"review-{case['revision']}.json").write_text(json.dumps(finding))
        return jsonify(finding)
    except (urllib.error.URLError, ValueError, TimeoutError, OSError):
        return jsonify(error="Model review failed or returned an invalid response. Your photos are retained; try again later."), 502


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    app.run(host="127.0.0.1", port=args.port, debug=False)
