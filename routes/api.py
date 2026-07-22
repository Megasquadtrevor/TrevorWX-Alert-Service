from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from functools import wraps
from datetime import datetime, timezone
import sqlite3
import json
import os

api = Blueprint("api", __name__, url_prefix="/api")

DB_FILE = os.path.join("database", "subscribers.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
serializer = URLSafeTimedSerializer(SECRET_KEY)


def create_token(account_id):
    return serializer.dumps({"account_id": account_id})


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({
                "ok": False,
                "error": "Authentication required."
            }), 401

        token = auth_header.split(" ", 1)[1].strip()

        try:
            token_data = serializer.loads(
                token,
                max_age=60 * 60 * 24 * 30
            )
            account_id = token_data.get("account_id")

            if not account_id:
                raise BadSignature("Invalid token")

        except SignatureExpired:
            return jsonify({
                "ok": False,
                "error": "Authentication token has expired."
            }), 401

        except BadSignature:
            return jsonify({
                "ok": False,
                "error": "Invalid authentication token."
            }), 401

        return f(account_id, *args, **kwargs)

    return decorated


def init_signup_tables():
    os.makedirs("database", exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            consent INTEGER NOT NULL DEFAULT 0,
            consent_timestamp TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            address TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account_phones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            phone TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notification_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL UNIQUE,
            phone_alerts TEXT NOT NULL DEFAULT '[]',
            text_alerts TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    conn.commit()
    conn.close()


@api.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "service": "TrevorWX Alerts API"
    }), 200


@api.route("/signup", methods=["POST"])
def signup():
    init_signup_tables()

    data = request.get_json(silent=True) or {}

    first_name = str(data.get("firstName", "")).strip()
    last_name = str(data.get("lastName", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    locations = data.get("locations") or []
    phone_numbers = data.get("phoneNumbers") or []
    phone_alerts = data.get("phoneAlerts") or []
    text_alerts = data.get("textAlerts") or []
    consent = bool(data.get("consent"))

    if not first_name or not last_name:
        return jsonify({
            "ok": False,
            "error": "First and last name are required."
        }), 400

    if not email:
        return jsonify({
            "ok": False,
            "error": "Email address is required."
        }), 400

    if len(password) < 8:
        return jsonify({
            "ok": False,
            "error": "Password must be at least 8 characters."
        }), 400

    if not locations:
        return jsonify({
            "ok": False,
            "error": "Add at least one monitored location."
        }), 400

    if not phone_numbers:
        return jsonify({
            "ok": False,
            "error": "Add at least one phone number."
        }), 400

    if not consent:
        return jsonify({
            "ok": False,
            "error": "You must agree to receive the selected alerts."
        }), 400

    created_at = datetime.now(timezone.utc).isoformat()

    conn = None

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        existing = cursor.execute(
            "SELECT id FROM accounts WHERE email = ?",
            (email,)
        ).fetchone()

        if existing:
            return jsonify({
                "ok": False,
                "error": "An account with that email already exists."
            }), 409

        cursor.execute("""
            INSERT INTO accounts (
                first_name,
                last_name,
                email,
                password_hash,
                consent,
                consent_timestamp,
                active,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            first_name,
            last_name,
            email,
            generate_password_hash(password),
            1,
            created_at,
            1,
            created_at
        ))

        account_id = cursor.lastrowid

        for location in locations:
            label = str(location.get("label", "")).strip()
            address = str(location.get("address", "")).strip()
            active = 1 if location.get("active", True) else 0

            if not label or not address:
                conn.rollback()
                return jsonify({
                    "ok": False,
                    "error": "Every monitored location needs a label and address."
                }), 400

            cursor.execute("""
                INSERT INTO account_locations (
                    account_id,
                    label,
                    address,
                    active
                )
                VALUES (?, ?, ?, ?)
            """, (
                account_id,
                label,
                address,
                active
            ))

        for phone in phone_numbers:
            label = str(phone.get("label", "")).strip()
            number = str(phone.get("number", "")).strip()

            if not label or not number:
                conn.rollback()
                return jsonify({
                    "ok": False,
                    "error": "Every phone number needs a label and number."
                }), 400

            cursor.execute("""
                INSERT INTO account_phones (
                    account_id,
                    label,
                    phone
                )
                VALUES (?, ?, ?)
            """, (
                account_id,
                label,
                number
            ))

        cursor.execute("""
            INSERT INTO notification_preferences (
                account_id,
                phone_alerts,
                text_alerts
            )
            VALUES (?, ?, ?)
        """, (
            account_id,
            json.dumps(phone_alerts),
            json.dumps(text_alerts)
        ))

        conn.commit()

        token = create_token(account_id)

        return jsonify({
            "ok": True,
            "message": "TrevorWX Alerts account created successfully.",
            "accountId": account_id,
            "token": token
        }), 201

    except Exception as e:
        if conn:
            conn.rollback()

        return jsonify({
            "ok": False,
            "error": "Unable to create account.",
            "details": str(e)
        }), 500

    finally:
        if conn:
            conn.close()


@api.route("/account", methods=["GET"])
@token_required
def get_account(account_id):
    conn = None

    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        account = cursor.execute("""
            SELECT id, first_name, last_name, email, created_at
            FROM accounts
            WHERE id = ? AND active = 1
        """, (account_id,)).fetchone()

        if not account:
            return jsonify({
                "ok": False,
                "error": "Account not found."
            }), 404

        locations = cursor.execute("""
            SELECT id, label, address, active
            FROM account_locations
            WHERE account_id = ?
        """, (account_id,)).fetchall()

        phones = cursor.execute("""
            SELECT id, label, phone
            FROM account_phones
            WHERE account_id = ?
        """, (account_id,)).fetchall()

        preferences = cursor.execute("""
            SELECT phone_alerts, text_alerts
            FROM notification_preferences
            WHERE account_id = ?
        """, (account_id,)).fetchone()

        return jsonify({
            "ok": True,
            "account": {
                "firstName": account["first_name"],
                "lastName": account["last_name"],
                "email": account["email"],
                "createdAt": account["created_at"],
                "locations": [
                    {
                        "id": str(location["id"]),
                        "label": location["label"],
                        "address": location["address"],
                        "active": bool(location["active"])
                    }
                    for location in locations
                ],
                "phoneNumbers": [
                    {
                        "id": str(phone["id"]),
                        "label": phone["label"],
                        "number": phone["phone"],
                        "active": True
                    }
                    for phone in phones
                ],
                "phoneAlerts": (
                    json.loads(preferences["phone_alerts"])
                    if preferences else []
                ),
                "textAlerts": (
                    json.loads(preferences["text_alerts"])
                    if preferences else []
                )
            }
        }), 200

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": "Unable to load account.",
            "details": str(e)
        }), 500

    finally:
        if conn:
            conn.close()
