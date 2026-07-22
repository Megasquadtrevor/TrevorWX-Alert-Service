from flask import Blueprint, render_template
from services.nws_service import get_important_alerts, get_alert_counts
import sqlite3
import os

dashboard = Blueprint("dashboard", __name__)

DB_FILE = os.path.join("database", "subscribers.db")


@dashboard.route("/dashboard")
def dashboard_page():

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM subscribers")
    subscribers = cursor.fetchall()

    conn.close()

    alerts = get_important_alerts()
    counts = get_alert_counts()

    return render_template(
        "dashboard.html",
        subscribers=subscribers,
        alerts=alerts,
        counts=counts
    )