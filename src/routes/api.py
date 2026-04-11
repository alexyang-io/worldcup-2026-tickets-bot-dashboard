"""
API endpoints for the ticket monitor.
"""

from flask import Blueprint, jsonify, request

from config import command_log, get_fifa_url, last_page_text, monitor_state, settings
from services.commands import process_command
from services.monitor import analyze_page

api_bp = Blueprint("api", __name__)


@api_bp.route("/api/debug/page-text")
def debug_page_text():
    return jsonify({
        "text": last_page_text["text"],
        "progress_debug": last_page_text.get("progress_debug"),
        "dom_snapshot": last_page_text.get("dom_snapshot"),
    })


@api_bp.route("/api/page-content", methods=["POST"])
def page_content():
    data = request.get_json(silent=True)
    if not data or "text" not in data:
        return jsonify({"error": "missing text"}), 400

    last_page_text["text"] = data["text"]  # store for debug
    last_page_text["progress_debug"] = data.get("progress_debug")
    last_page_text["dom_snapshot"] = data.get("dom_snapshot")
    monitor_state["extension_connected"] = True

    # Queue progress from extension
    progress = data.get("queue_progress")
    if progress is not None:
        monitor_state["queue_progress"] = progress
    else:
        monitor_state["queue_progress"] = None

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
