from flask import Blueprint, render_template

radar = Blueprint("radar", __name__)


@radar.route("/radar")
def radar_page():
    return render_template("radar.html")