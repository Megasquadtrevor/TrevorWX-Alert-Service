from flask import Flask, render_template
from flask_cors import CORS
from database import init_db

from routes.radar import radar
from routes.dashboard import dashboard
from routes.subscribers import subscribers
from routes.alerts import alerts
from routes.api import api

app = Flask(__name__)
CORS(app)
init_db()

app.register_blueprint(radar)
app.register_blueprint(dashboard)
app.register_blueprint(subscribers)
app.register_blueprint(alerts)
app.register_blueprint(api)

@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
