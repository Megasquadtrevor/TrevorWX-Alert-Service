from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from functools import wraps
from datetime import datetime, timezone
import sqlite3
import json
import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone

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

@api.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not email or not password:
        return jsonify({
            "ok": False,
            "error": "Email and password are required."
        }), 400

    conn = None

    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        account = cursor.execute("""
            SELECT id, first_name, last_name, email, password_hash
            FROM accounts
            WHERE email = ? AND active = 1
        """, (email,)).fetchone()

        if not account or not check_password_hash(
            account["password_hash"],
            password
        ):
            return jsonify({
                "ok": False,
                "error": "Invalid email or password."
            }), 401

        token = create_token(account["id"])

        return jsonify({
            "ok": True,
            "message": "Login successful.",
            "token": token,
            "account": {
                "id": account["id"],
                "firstName": account["first_name"],
                "lastName": account["last_name"],
                "email": account["email"]
            }
        }), 200

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": "Unable to log in.",
            "details": str(e)
        }), 500

    finally:
        if conn:
            conn.close()

@api.route("/locations", methods=["POST"])
@token_required
def add_location(account_id):
    data = request.get_json(silent=True) or {}

    label = str(data.get("label", "")).strip()
    address = str(data.get("address", "")).strip()

    if not label or not address:
        return jsonify({
            "ok": False,
            "error": "Location label and address are required."
        }), 400

    conn = None

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO account_locations (
                account_id,
                label,
                address,
                active
            )
            VALUES (?, ?, ?, 1)
        """, (
            account_id,
            label,
            address
        ))

        location_id = cursor.lastrowid
        conn.commit()

        return jsonify({
            "ok": True,
            "location": {
                "id": str(location_id),
                "label": label,
                "address": address,
                "active": True
            }
        }), 201

    except Exception as e:
        if conn:
            conn.rollback()

        return jsonify({
            "ok": False,
            "error": "Unable to add location.",
            "details": str(e)
        }), 500

    finally:
        if conn:
            conn.close()


@api.route("/locations/<int:location_id>", methods=["PATCH"])
@token_required
def update_location(account_id, location_id):
    data = request.get_json(silent=True) or {}

    allowed_fields = {}

    if "label" in data:
        label = str(data.get("label", "")).strip()
        if not label:
            return jsonify({
                "ok": False,
                "error": "Location label cannot be empty."
            }), 400
        allowed_fields["label"] = label

    if "address" in data:
        address = str(data.get("address", "")).strip()
        if not address:
            return jsonify({
                "ok": False,
                "error": "Location address cannot be empty."
            }), 400
        allowed_fields["address"] = address

    if "active" in data:
        allowed_fields["active"] = 1 if bool(data["active"]) else 0

    if not allowed_fields:
        return jsonify({
            "ok": False,
            "error": "No valid fields were provided."
        }), 400

    conn = None

    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        existing = cursor.execute("""
            SELECT id
            FROM account_locations
            WHERE id = ? AND account_id = ?
        """, (
            location_id,
            account_id
        )).fetchone()

        if not existing:
            return jsonify({
                "ok": False,
                "error": "Location not found."
            }), 404

        set_clause = ", ".join(
            f"{field} = ?" for field in allowed_fields
        )

        values = list(allowed_fields.values())
        values.extend([location_id, account_id])

        cursor.execute(
            f"""
            UPDATE account_locations
            SET {set_clause}
            WHERE id = ? AND account_id = ?
            """,
            values
        )

        conn.commit()

        location = cursor.execute("""
            SELECT id, label, address, active
            FROM account_locations
            WHERE id = ? AND account_id = ?
        """, (
            location_id,
            account_id
        )).fetchone()

        return jsonify({
            "ok": True,
            "location": {
                "id": str(location["id"]),
                "label": location["label"],
                "address": location["address"],
                "active": bool(location["active"])
            }
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()

        return jsonify({
            "ok": False,
            "error": "Unable to update location.",
            "details": str(e)
        }), 500

    finally:
        if conn:
            conn.close()


@api.route("/locations/<int:location_id>", methods=["DELETE"])
@token_required
def delete_location(account_id, location_id):
    conn = None

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        existing = cursor.execute("""
            SELECT id
            FROM account_locations
            WHERE id = ? AND account_id = ?
        """, (
            location_id,
            account_id
        )).fetchone()

        if not existing:
            return jsonify({
                "ok": False,
                "error": "Location not found."
            }), 404

        cursor.execute("""
            DELETE FROM account_locations
            WHERE id = ? AND account_id = ?
        """, (
            location_id,
            account_id
        ))

        conn.commit()

        return jsonify({
            "ok": True
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()

        return jsonify({
            "ok": False,
            "error": "Unable to delete location.",
            "details": str(e)
        }), 500

    finally:
        if conn:
            conn.close()
@api.route("/password-reset/request", methods=["POST"])
def request_password_reset():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()

    if not email:
        return jsonify({
            "ok": False,
            "error": "Email address is required."
        }), 400

    conn = None

    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        account = cursor.execute("""
            SELECT id, email
            FROM accounts
            WHERE email = ? AND active = 1
        """, (email,)).fetchone()

        # Always return the same response whether the account exists or not.
        # This prevents people from using this endpoint to discover
        # which email addresses have TrevorWX Alerts accounts.
        if not account:
            return jsonify({
                "ok": True,
                "message": "If an account exists for that email, a password reset link will be sent."
            }), 200

        reset_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(
            reset_token.encode("utf-8")
        ).hexdigest()

        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(minutes=30)

        # Invalidate any previous unused reset tokens for this account.
        cursor.execute("""
            UPDATE password_reset_tokens
            SET used = 1
            WHERE account_id = ? AND used = 0
        """, (account["id"],))

        cursor.execute("""
            INSERT INTO password_reset_tokens (
                account_id,
                token_hash,
                expires_at,
                used,
                created_at
            )
            VALUES (?, ?, ?, 0, ?)
        """, (
            account["id"],
            token_hash,
            expires_at.isoformat(),
            created_at.isoformat()
        ))

        conn.commit()

        # TEMPORARY FOR DEVELOPMENT ONLY:
        # This lets us test the reset flow before connecting an email service.
        return jsonify({
            "ok": True,
            "message": "If an account exists for that email, a password reset link will be sent.",
            "resetToken": reset_token
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()

        return jsonify({
            "ok": False,
            "error": "Unable to process password reset request.",
            "details": str(e)
        }), 500

    finally:
        if conn:
            conn.close()

@api.route("/password-reset/confirm", methods=["POST"])
def confirm_password_reset():
    data = request.get_json(silent=True) or {}

    token = str(data.get("token", "")).strip()
    new_password = str(data.get("newPassword", ""))

    if not token:
        return jsonify({
            "ok": False,
            "error": "Reset token is required."
        }), 400

    if len(new_password) < 8:
        return jsonify({
            "ok": False,
            "error": "Password must be at least 8 characters."
        }), 400

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    conn = None

    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        reset = cursor.execute("""
            SELECT id, account_id, expires_at, used
            FROM password_reset_tokens
            WHERE token_hash = ?
        """, (token_hash,)).fetchone()

        if not reset or reset["used"]:
            return jsonify({
                "ok": False,
                "error": "Invalid or already used password reset token."
            }), 400

        expires_at = datetime.fromisoformat(
            reset["expires_at"]
        )

        if datetime.now(timezone.utc) > expires_at:
            return jsonify({
                "ok": False,
                "error": "Password reset token has expired."
            }), 400

        new_password_hash = generate_password_hash(
            new_password
        )

        cursor.execute("""
            UPDATE accounts
            SET password_hash = ?
            WHERE id = ?
        """, (
            new_password_hash,
            reset["account_id"]
        ))

        cursor.execute("""
            UPDATE password_reset_tokens
            SET used = 1
            WHERE id = ?
        """, (reset["id"],))

        conn.commit()

        return jsonify({
            "ok": True,
            "message": "Password updated successfully."
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()

        return jsonify({
            "ok": False,
            "error": "Unable to reset password.",
            "details": str(e)
        }), 500

    finally:
        if conn:
            conn.close()
