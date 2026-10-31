"""Local development upload API. Run behind authentication/TLS before deployment."""
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import threading

from flask import Flask, jsonify, request
from PIL import Image, UnidentifiedImageError

BACKEND_DIR = Path(__file__).resolve().parent
REPOSITORY_DIR = BACKEND_DIR.parent.parent


def load_local_env():
    """Load backend-only secrets from .env without ever printing them."""
    env_file = BACKEND_DIR / ".env"
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if name and value and name.replace("_", "").isalnum():
            os.environ.setdefault(name, value.strip("\"'"))


load_local_env()
if os.environ.get("MODEL_API_KEY"):
    os.environ.setdefault("GEMINI_API_KEY", os.environ["MODEL_API_KEY"])
sys.path.insert(0, str(REPOSITORY_DIR))
from veridex.review import review as run_model_review

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
app.config["DATA_DIR"] = BACKEND_DIR / "data"
lock = threading.Lock()
OUTCOMES = {"visible_repair_evidence", "visible_defect_remains", "insufficient_evidence"}


def validate(payload):
    if not isinstance(payload, dict):
        raise ValueError("Expected a case object")
    if payload.get("review_consent") is not True:
        raise ValueError("Explicit consent is required before evidence can be uploaded for AI review")
    consent_at = payload.get("review_consent_at")
    if type(consent_at) is not int or consent_at <= 0:
        raise ValueError("A valid consent timestamp is required")
    case_id = payload.get("id", "")
    if not isinstance(case_id, str) or not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", case_id):
        raise ValueError("Invalid case ID")
    revision = payload.get("revision")
    if type(revision) is not int or revision < 1:
        raise ValueError("Invalid revision")
    if payload.get("review_consent_revision") != revision:
        raise ValueError("Consent must apply to the exact evidence revision being uploaded")
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
    return {"id": case_id, "revision": revision, "location": location.strip(), "note": note, "created": payload.get("created"), "review_consent": True, "review_consent_revision": revision, "review_consent_at": consent_at, "photos": clean}


@app.errorhandler(413)
def too_large(_):
    return jsonify(error="Upload exceeds 40 MB"), 413


@app.get("/health")
def health():
    app_registered = bool(os.environ.get("VERIDEX_APP_KEY"))
    model_configured = bool(os.environ.get("MODEL_API_KEY"))
    return jsonify(
        status="ok", mode="local-development", app=os.environ.get("VERIDEX_APP_NAME", "daksha-app"),
        app_registered=app_registered, ai_connected=app_registered and model_configured,
        model_configured=model_configured, model=os.environ.get("VERIDEX_MODEL", "gemma-4-26b-a4b-it"),
        consent_required=True, human_label_approval=False,
    )


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
    if case.get("review_consent") is not True or case.get("review_consent_revision") != case["revision"] or type(case.get("review_consent_at")) is not int:
        return jsonify(error="Current explicit consent is required before model review"), 403
    if len(case["photos"]) < 2:
        return jsonify(error="A before and an after photo are required"), 400
    if not os.environ.get("VERIDEX_APP_KEY"):
        return jsonify(error="This VERIDEX app is not registered on the local backend"), 503
    if not os.environ.get("MODEL_API_KEY"):
        return jsonify(error="The model API key is not configured on the local backend"), 503
    original, latest = case["photos"][0], case["photos"][-1]
    before_path = root / (original["sha256"] + ".jpg")
    after_path = root / (latest["sha256"] + ".jpg")
    try:
        result = run_model_review(before_path, after_path, original["region"])
        observations = result.get("observations") or {}
        explanation = observations.get("evidence") if isinstance(observations, dict) else None
        if not explanation:
            reasons = result.get("reason_codes") or ["MODEL_UNAVAILABLE"]
            explanation = {
                "LOW_IMAGE_QUALITY": "One or more photos need a clearer, better-lit capture.",
                "MODEL_UNAVAILABLE": "The model could not complete this review. No positive finding was produced.",
                "MODEL_OUTPUT_INVALID": "The model response could not be validated. No positive finding was produced.",
            }.get(reasons[0], "The evidence was not sufficient for a positive finding.")
            # ProviderError strings are intentionally restricted to safe diagnostics
            # (HTTP status, timeout, or generic transport/schema errors). Never pass
            # request headers, credentials, or provider response bodies to the client.
            provider_error = result.get("provider_error")
            if reasons[0] == "MODEL_UNAVAILABLE" and isinstance(provider_error, str) and provider_error:
                explanation = f"{provider_error[:180]}. No positive finding was produced."
        finding = {"outcome": result["outcome"], "explanation": explanation, "next_photo": result.get("next_request") or ""}
        if finding["outcome"] not in OUTCOMES or not finding["explanation"].strip() or finding["outcome"] == "insufficient_evidence" and not finding["next_photo"].strip():
            raise ValueError("Review policy returned an invalid finding")
        with lock:
            current = json.loads((root / "case.json").read_text())
            if current["revision"] != case["revision"] or current.get("review_consent") is not True:
                return jsonify(error="Evidence or consent changed during review. Review the current case."), 409
            (root / f"review-{case['revision']}.json").write_text(json.dumps(finding))
        return jsonify(finding)
    except (ValueError, TimeoutError, OSError):
        return jsonify(error="Model review failed or returned an invalid response. Your photos are retained; try again later."), 502


@app.delete("/v1/cases/<case_id>")
def revoke_case(case_id):
    if not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", case_id):
        return jsonify(error="Invalid case ID"), 400
    root = Path(app.config["DATA_DIR"]) / case_id
    with lock:
        if root.exists():
            shutil.rmtree(root)
    return jsonify(id=case_id, status="deleted")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    app.run(host="127.0.0.1", port=args.port, debug=False, load_dotenv=False)
