from datetime import datetime
import requests

NWS_URL = "https://api.weather.gov/alerts/active"


def get_active_alerts():
    """
    Returns all active NWS alerts.
    """

    response = requests.get(
        NWS_URL,
        headers={
            "User-Agent": "TrevorWX Alerts (your-email@example.com)"
        },
        timeout=15
    )

    response.raise_for_status()

    return response.json()


def get_important_alerts():

    data = get_active_alerts()

    important = []

    events = [
        "Tornado Warning",
        "Tornado Emergency",
        "Severe Thunderstorm Warning",
        "Flash Flood Warning"
    ]

    for feature in data["features"]:

        properties = feature["properties"]

        if properties["event"] in events:

            event = properties["event"]

            color = "blue"

            if event == "Tornado Warning":
                color = "red"

            elif event == "Tornado Emergency":
                color = "purple"

            elif event == "Severe Thunderstorm Warning":
                color = "orange"

            elif event == "Flash Flood Warning":
                color = "green"

            expires = properties["expires"]

            try:
                dt = datetime.fromisoformat(expires)
                expires = dt.strftime("%I:%M %p").lstrip("0")
            except Exception:
                pass

            important.append({
                "event": event,
                "area": properties["areaDesc"],
                "expires": expires,
                "color": color
            })

    return important

def get_alert_counts():

    alerts = get_important_alerts()

    counts = {
        "tornado": 0,
        "tornado_emergency": 0,
        "severe": 0,
        "flash_flood": 0
    }

    for alert in alerts:

        event = alert["event"]

        if event == "Tornado Warning":
            counts["tornado"] += 1

        elif event == "Tornado Emergency":
            counts["tornado_emergency"] += 1

        elif event == "Severe Thunderstorm Warning":
            counts["severe"] += 1

        elif event == "Flash Flood Warning":
            counts["flash_flood"] += 1

    return counts