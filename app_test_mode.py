import os, threading, time
from datetime import datetime, timezone
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

NWS_URL = "https://api.weather.gov/alerts/active"
HEADERS = {"User-Agent": "TrevorWX Alerts", "Accept": "application/geo+json"}
latest_data = {}
lock = threading.Lock()
test_mode = {"until": 0, "data": None}

def empty_data(status="ONLINE"):
    return {
        "updated": datetime.now(timezone.utc).isoformat(),
        "monitorStatus": status,
        "highest": {"type":"NO ACTIVE ALERT","location":"MONITORING NATIONWIDE","headline":"No active severe weather alerts","color":"none"},
        "counts": {"tornado":0,"severe":0,"flashFlood":0,"watch":0,"pds":0,"emergency":0,"confirmed":0},
        "tornadoAlerts": []
    }

latest_data = empty_data("STARTING")

def classify_tornado(p):
    text = f"{p.get('headline') or ''} {p.get('description') or ''} {p.get('instruction') or ''}".lower()
    if "tornado emergency" in text: return {"type":"TORNADO EMERGENCY","color":"purple","priority":100}
    if "particularly dangerous situation" in text or "pds" in (p.get("headline") or "").lower(): return {"type":"PDS TORNADO WARNING","color":"pink","priority":90}
    if "confirmed tornado" in text or "radar confirmed tornado" in text or "observed tornado" in text: return {"type":"CONFIRMED TORNADO WARNING","color":"darkred","priority":85}
    return {"type":"TORNADO WARNING","color":"red","priority":80}

def build_data(features):
    data = empty_data()
    best, best_score = None, -1
    for f in features:
        p = f.get("properties", {})
        event = (p.get("event") or "").lower()
        score, color, label = 0, "red", (p.get("event") or "SEVERE WEATHER ALERT").upper()

        if "tornado warning" in event:
            t = classify_tornado(p)
            score, color, label = t["priority"], t["color"], t["type"]
            data["counts"]["tornado"] += 1
            if color == "pink": data["counts"]["pds"] += 1
            elif color == "purple": data["counts"]["emergency"] += 1
            elif color == "darkred": data["counts"]["confirmed"] += 1
            alert_id = p.get("id") or f.get("id") or f"{p.get('sent','')}|{p.get('areaDesc','')}|{p.get('headline','')}"
            data["tornadoAlerts"].append({
                "id": str(alert_id), "type": label,
                "location": (p.get("areaDesc") or "Affected area").upper(),
                "headline": (p.get("headline") or label).upper(),
                "color": color, "sent": p.get("sent") or ""
            })
        elif "severe thunderstorm warning" in event:
            data["counts"]["severe"] += 1; score, color, label = 60, "orange", "SEVERE THUNDERSTORM WARNING"
        elif "flash flood warning" in event:
            data["counts"]["flashFlood"] += 1; score, color, label = 50, "green", "FLASH FLOOD WARNING"
        elif "watch" in event:
            data["counts"]["watch"] += 1; score, color = 20, "yellow"

        if score > best_score:
            best_score = score
            best = {"type":label,"location":(p.get("areaDesc") or "Affected area").upper(),"headline":(p.get("headline") or label).upper(),"color":color}

    data["tornadoAlerts"].sort(key=lambda a:a.get("sent",""), reverse=True)
    if best: data["highest"] = best
    return data

def monitor():
    global latest_data
    while True:
        try:
            r = requests.get(NWS_URL, headers=HEADERS, timeout=20)
            r.raise_for_status()
            new_data = build_data(r.json().get("features", []))
            with lock: latest_data = new_data
        except Exception as e:
            print("Monitor error:", e)
            with lock:
                latest_data["monitorStatus"] = "OFFLINE"
                latest_data["updated"] = datetime.now(timezone.utc).isoformat()
        time.sleep(15)

@app.get("/")
def home():
    return jsonify({"service":"TrevorWX Alert Service","status":"ONLINE","alertEndpoint":"/alert.json"})

@app.get("/alert.json")
def alerts():
    with lock:
        if test_mode["data"] is not None and time.time() < test_mode["until"]:
            return jsonify(test_mode["data"])
        return jsonify(latest_data)


@app.get("/test/<kind>")
def test_alert(kind):
    tests = {
        "tornado": ("TORNADO WARNING", "red"),
        "confirmed": ("CONFIRMED TORNADO WARNING", "darkred"),
        "pds": ("PDS TORNADO WARNING", "pink"),
        "emergency": ("TORNADO EMERGENCY", "purple"),
    }

    if kind not in tests:
        return jsonify({
            "error": "Unknown test type",
            "valid": list(tests.keys())
        }), 400

    alert_type, color = tests[kind]
    now = datetime.now(timezone.utc).isoformat()
    test_id = f"trevorwx-test-{kind}-{time.time_ns()}"

    test_data = empty_data("TEST MODE")
    test_data["highest"] = {
        "type": alert_type,
        "location": "TREVORWX TEST AREA",
        "headline": f"THIS IS A TEST - {alert_type}",
        "color": color,
    }
    test_data["counts"]["tornado"] = 1
    if color == "darkred":
        test_data["counts"]["confirmed"] = 1
    elif color == "pink":
        test_data["counts"]["pds"] = 1
    elif color == "purple":
        test_data["counts"]["emergency"] = 1

    test_data["tornadoAlerts"] = [{
        "id": test_id,
        "type": alert_type,
        "location": "TREVORWX TEST AREA",
        "headline": f"THIS IS A TEST - {alert_type}",
        "color": color,
        "sent": now,
    }]

    with lock:
        test_mode["data"] = test_data
        test_mode["until"] = time.time() + 60

    return jsonify({
        "status": "TEST ACTIVE",
        "type": alert_type,
        "durationSeconds": 60,
        "alertEndpoint": "/alert.json"
    })

@app.get("/health")
def health():
    with lock: return jsonify({"status":latest_data.get("monitorStatus"),"updated":latest_data.get("updated")})

threading.Thread(target=monitor, daemon=True).start()
