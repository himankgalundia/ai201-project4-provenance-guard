"""Provenance Guard — content-attribution API.

Endpoints:
  POST /submit  -> classify text, return attribution + confidence + label
  POST /appeal  -> contest a classification, set status=under_review, log it
  GET  /log     -> recent structured audit-log entries (for grading visibility)
  GET  /health  -> liveness check
"""

import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import db
from signals import combine_and_classify, generate_label

app = Flask(__name__)
db.init_db()

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "error": "rate_limit_exceeded",
        "message": f"Too many submissions ({e.description}). Please slow down.",
    }), 429


@app.route("/", methods=["GET"])
def index():
    """Reader/creator-facing UI. Calls the same JSON endpoints under the hood."""
    return render_template("index.html")


@app.route("/api", methods=["GET"])
def api_info():
    return jsonify({
        "service": "Provenance Guard",
        "status": "running",
        "endpoints": {
            "POST /submit": "classify text — body: {text, creator_id}",
            "POST /appeal": "contest a classification — body: {content_id, creator_reasoning}",
            "GET /log": "recent audit-log entries (optional ?limit=N)",
            "GET /health": "liveness check",
        },
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    creator_id = (body.get("creator_id") or "").strip()

    if not text:
        return jsonify({"error": "missing_field", "message": "'text' is required."}), 400
    if not creator_id:
        return jsonify({"error": "missing_field", "message": "'creator_id' is required."}), 400

    content_id = str(uuid.uuid4())
    result = combine_and_classify(text)
    label = generate_label(result["attribution"], result["confidence"])
    timestamp = _now()
    status = "classified"

    db.save_content({
        "content_id": content_id,
        "creator_id": creator_id,
        "text": text,
        "attribution": result["attribution"],
        "confidence": result["confidence"],
        "ai_score": result["ai_score"],
        "llm_score": result["llm_score"],
        "stylometric_score": result["stylometric_score"],
        "status": status,
        "creator_reasoning": None,
        "created_at": timestamp,
    })

    db.add_log_entry(content_id, "classification", timestamp, {
        "creator_id": creator_id,
        "attribution": result["attribution"],
        "confidence": result["confidence"],
        "ai_score": result["ai_score"],
        "llm_score": result["llm_score"],
        "stylometric_score": result["stylometric_score"],
        "llm_degraded": result["llm_degraded"],
        "short_input": result["short_input"],
        "status": status,
        "label_variant": label["variant"],
    })

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": result["attribution"],
        "confidence": result["confidence"],
        "signals": {
            "llm_score": result["llm_score"],
            "stylometric_score": result["stylometric_score"],
            "combined_ai_score": result["ai_score"],
            "llm_reasoning": result["llm_reasoning"],
            "llm_degraded": result["llm_degraded"],
            "stylometric_metrics": result["stylometric_metrics"],
            "weights": result["weights"],
        },
        "label": label,
        "status": status,
    })


@app.route("/appeal", methods=["POST"])
@limiter.limit("20 per minute;200 per day")
def appeal():
    body = request.get_json(silent=True) or {}
    content_id = (body.get("content_id") or "").strip()
    reasoning = (body.get("creator_reasoning") or "").strip()

    if not content_id:
        return jsonify({"error": "missing_field", "message": "'content_id' is required."}), 400
    if not reasoning:
        return jsonify({"error": "missing_field",
                        "message": "'creator_reasoning' is required."}), 400

    record = db.get_content(content_id)
    if not record:
        return jsonify({"error": "not_found",
                        "message": f"No content with id {content_id}."}), 404

    new_status = "under_review"
    db.update_status(content_id, new_status, reasoning)
    timestamp = _now()

    db.add_log_entry(content_id, "appeal", timestamp, {
        "creator_id": record["creator_id"],
        "creator_reasoning": reasoning,
        "status": new_status,
        "original_attribution": record["attribution"],
        "original_confidence": record["confidence"],
        "original_llm_score": record["llm_score"],
        "original_stylometric_score": record["stylometric_score"],
    })

    return jsonify({
        "content_id": content_id,
        "status": new_status,
        "appeal_logged": True,
        "message": (
            "Your appeal has been received. This content is now under review by "
            "a human moderator. The original classification has been preserved "
            "alongside your reasoning."
        ),
        "original_decision": {
            "attribution": record["attribution"],
            "confidence": record["confidence"],
        },
    })


@app.route("/log", methods=["GET"])
def log():
    limit = request.args.get("limit", default=50, type=int)
    return jsonify({"entries": db.get_log(limit)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
