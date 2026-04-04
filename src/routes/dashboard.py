"""
Dashboard route serving the main HTML page.
"""

import os

from flask import Blueprint, render_template

from config import FIFA_URL

dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"),
)


@dashboard_bp.route("/")
def index():
    return render_template("dashboard.html", fifa_url=FIFA_URL)
