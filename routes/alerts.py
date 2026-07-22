from flask import Blueprint, render_template, jsonify
from services.nws_service import get_important_alerts

alerts = Blueprint("alerts", __name__)


@alerts.route("/alerts")
def alerts_page():

    weather_alerts = get_important_alerts()

    return render_template(
        "alerts.html",
        alerts=weather_alerts
    )

@alerts.route("/api/alerts")
def alerts_api():
    """Public JSON endpoint for the TrevorWX website."""
    weather_alerts = get_important_alerts()
    return jsonify(weather_alerts)

