"""
API endpoints for the ticket monitor.
"""

from flask import Blueprint, jsonify, request

from config import monitor_state
from services.monitor import analyze_page

api_bp = Blueprint("api", __name__)


@api_bp.route("/api/page-content", methods=["POST"])
def page_content():
    data = request.get_json(silent=True)
    if not data or "text" not in data:
        return jsonify({"error": "missing text"}), 400

    monitor_state["extension_connected"] = True
    analyze_page(data["text"], source="extension")
    return jsonify({"ok": True})


@api_bp.route("/api/status")
def api_status():
    return jsonify(monitor_state)


@api_bp.route("/api/reset", methods=["POST"])
def api_reset():
    monitor_state["alert_sent"] = False
    monitor_state["changed"] = False
    monitor_state["status"] = "Reset — monitoring…"
    return jsonify({"ok": True})
