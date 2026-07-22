from flask import Blueprint, render_template, request, redirect
import sqlite3
import re
from datetime import datetime, timezone
from database import DB_FILE, init_db

subscribers = Blueprint("subscribers", __name__)

def normalize_us_phone(value):
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return "+1" + digits

@subscribers.route("/signup", methods=["GET", "POST"])
def signup():
    init_db()
    error = None
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        phone = normalize_us_phone(request.form.get("phone", ""))
        state = request.form.get("state", "").strip()
        county = request.form.get("county", "").strip()

        sms = 1 if request.form.get("sms") == "on" else 0
        voice = 1 if request.form.get("voice") == "on" else 0
        tornado = 1 if request.form.get("tornado") == "on" else 0
        tornado_emergency = 1 if request.form.get("tornado_emergency") == "on" else 0
        severe = 1 if request.form.get("severe") == "on" else 0
        flash_flood = 1 if request.form.get("flash_flood") == "on" else 0
        winter = 1 if request.form.get("winter") == "on" else 0
        consent = 1 if request.form.get("consent") == "on" else 0

        if not first_name or not state or not county:
            error = "Please complete all required fields."
        elif not phone:
            error = "Enter a valid 10-digit U.S. phone number."
        elif not sms and not voice:
            error = "Choose at least one delivery method: SMS or phone call."
        elif not consent:
            error = "You must agree to receive the alerts you selected."

        if not error:
            with sqlite3.connect(DB_FILE) as conn:
                existing = conn.execute(
                    "SELECT id FROM subscribers WHERE phone=? AND state=? AND county=? AND active=1",
                    (phone, state, county)
                ).fetchone()
                if existing:
                    error = "That phone number is already subscribed for this location."
                else:
                    conn.execute("""
                        INSERT INTO subscribers
                        (first_name, phone, state, county, tornado, tornado_emergency,
                         severe, flash_flood, winter, sms, voice, consent,
                         consent_timestamp, active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, (
                        first_name, phone, state, county, tornado, tornado_emergency,
                        severe, flash_flood, winter, sms, voice, consent,
                        datetime.now(timezone.utc).isoformat()
                    ))
                    conn.commit()
                    return render_template("success.html", name=first_name)

    return render_template("signup.html", error=error)

@subscribers.route("/delete/<int:id>")
def delete(id):
    init_db()
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("UPDATE subscribers SET active=0 WHERE id=?", (id,))
        conn.commit()
    return redirect("/dashboard")
