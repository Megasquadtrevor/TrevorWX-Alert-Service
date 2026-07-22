from flask import Blueprint, jsonify, request
import sqlite3
import os

api = Blueprint("api", __name__, url_prefix="/api")

DB_FILE = os.path.join("database", "subscribers.db")


@api.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "service": "TrevorWX Alerts API"
    }), 200


@api.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json(silent=True) or {}

        first_name = data.get("first_name", "").strip()
        phone = data.get("phone", "").strip()
        state = data.get("state", "").strip()
        county = data.get("county", "").strip()

        if not first_name or not phone or not state or not county:
            return jsonify({
                "ok": False,
                "error": "first_name, phone, state, and county are required"
            }), 400

        tornado = int(bool(data.get("tornado", True)))
        tornado_emergency = int(bool(data.get("tornado_emergency", True)))
        severe = int(bool(data.get("severe", True)))
        flash_flood = int(bool(data.get("flash_flood", True)))
        winter = int(bool(data.get("winter", False)))

        sms = int(bool(data.get("sms", True)))
        voice = int(bool(data.get("voice", False)))

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO subscribers (
                first_name,
                phone,
                state,
                county,
                tornado,
                tornado_emergency,
                severe,
                flash_flood,
                winter,
                sms,
                voice
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            first_name,
            phone,
            state,
            county,
            tornado,
            tornado_emergency,
            severe,
            flash_flood,
            winter,
            sms,
            voice
        ))

        subscriber_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return jsonify({
            "ok": True,
            "message": "Signup successful",
            "subscriber_id": subscriber_id
        }), 201

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500
