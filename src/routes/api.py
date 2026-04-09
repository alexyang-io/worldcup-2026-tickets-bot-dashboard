"""
API endpoints for the ticket monitor.
"""

from flask import Blueprint, jsonify, request

from config import command_log, get_fifa_url, monitor_state, settings
from services.commands import process_command
from services.monitor import analyze_page, check_countdown_thresholds

api_bp = Blueprint("api", __name__)


@api_bp.route("/api/page-content", methods=["POST"])
def page_content():
    data = request.get_json(silent=True)
    if not data or "text" not in data:
        return jsonify({"error": "missing text"}), 400

    monitor_state["extension_connected"] = True

    # Handle countdown from extension
    countdown_secs = data.get("countdown_seconds")
    if countdown_secs is not None:
        monitor_state["countdown_seconds"] = countdown_secs
        mins = countdown_secs // 60
        secs = countdown_secs % 60
        monitor_state["countdown_status"] = f"{mins:02d}:{secs:02d} remaining"
        check_countdown_thresholds(countdown_secs)
    else:
        monitor_state["countdown_seconds"] = None
        monitor_state["countdown_status"] = None

    analyze_page(data["text"], source="extension")
    return jsonify({"ok": True})


@api_bp.route("/api/status")
def api_status():
    return jsonify({**monitor_state, "settings": settings, "fifa_url": get_fifa_url()})


@api_bp.route("/api/command", methods=["POST"])
def api_command():
    data = request.get_json(silent=True)
    if not data or "command" not in data:
        return jsonify({"error": "missing command"}), 400
    response = process_command(data["command"], source="dashboard")
    return jsonify({"ok": True, "response": response})


@api_bp.route("/api/commands")
def api_commands():
    return jsonify(command_log[-20:])


@api_bp.route("/api/reset", methods=["POST"])
def api_reset():
    monitor_state["alert_sent"] = False
    monitor_state["changed"] = False
    monitor_state["status"] = "Reset — monitoring…"
    return jsonify({"ok": True})
