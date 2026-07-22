from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash
import sqlite3
import json
import os
from datetime import datetime, timezone

api = Blueprint("api", __name__, url_prefix="/api")

DB_FILE = os.path.join("database", "subscribers.db")


def init_signup_tables():
    os.makedirs("database", exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Main user accounts
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

    # Multiple monitored locations per account
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

    # Multiple phone numbers per account
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account_phones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            phone TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    # Separate phone-call and SMS alert preferences
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

    # Basic validation
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

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        # Check for an existing account
        existing = cursor.execute(
            "SELECT id FROM accounts WHERE email = ?",
            (email,)
        ).fetchone()

        if existing:
            conn.close()

            return jsonify({
                "ok": False,
                "error": "An account with that email already exists."
            }), 409

        # Create account with hashed password
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

        # Save monitored locations
        for location in locations:
            label = str(location.get("label", "")).strip()
            address = str(location.get("address", "")).strip()
            active = 1 if location.get("active", True) else 0

            if not label or not address:
                conn.rollback()
                conn.close()

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

        # Save phone numbers
        for phone in phone_numbers:
            label = str(phone.get("label", "")).strip()
            number = str(phone.get("number", "")).strip()

            if not label or not number:
                conn.rollback()
                conn.close()

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

        # Save notification preferences
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
        conn.close()

        return jsonify({
            "ok": True,
            "message": "TrevorWX Alerts account created successfully.",
            "accountId": account_id
        }), 201

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": "Unable to create account.",
            "details": str(e)
        }), 500
