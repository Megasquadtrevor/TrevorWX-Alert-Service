from flask import Blueprint, jsonify, request

api = Blueprint("api", __name__, url_prefix="/api")


@api.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "service": "TrevorWX Alerts API"
    }), 200
