"""
FIFA World Cup 2026 Ticket Monitor — Entry Point

Dashboard at http://localhost:7777.
Chrome extension monitors the FIFA ticket tab content.
Slack commands let you control the monitor remotely.

Setup:
    1. pip install flask requests
    2. export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
    3. export SLACK_BOT_TOKEN="xoxb-..."       (for reading commands from Slack)
    4. export SLACK_CHANNEL_ID="C0XXXXXXX"     (channel to listen for commands)
    5. python app.py
    6. Load chrome_extension/ in Chrome
"""

import threading

from flask import Flask

from config import (
    CHECK_INTERVAL,
    FIFA_URL,
    SLACK_BOT_TOKEN,
    SLACK_CHANNEL_ID,
    SLACK_WEBHOOK_URL,
    settings,
)
from routes.api import api_bp
from routes.dashboard import dashboard_bp
from services.monitor import fallback_monitor_loop
from services.slack_listener import slack_command_listener


def create_app() -> Flask:
    app = Flask(__name__)

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    app.register_blueprint(api_bp)
    app.register_blueprint(dashboard_bp)
    return app


if __name__ == "__main__":
    print(f"Slack webhook: {'configured' if SLACK_WEBHOOK_URL else 'NOT SET'}")
    print(f"Slack bot token: {'configured' if SLACK_BOT_TOKEN else 'NOT SET'}")
    print(f"Slack channel: {SLACK_CHANNEL_ID or 'NOT SET'}")
    print(f"Monitoring: {FIFA_URL}")
    print(f"Report interval: {settings['report_interval']}s\n")

    # Start fallback server-side monitor
    t1 = threading.Thread(target=fallback_monitor_loop, daemon=True)
    t1.start()

    # Start Slack command listener
    t2 = threading.Thread(target=slack_command_listener, daemon=True)
    t2.start()

    app = create_app()
    print(f"Dashboard: http://localhost:7777\n")
    app.run(host="0.0.0.0", port=7777, debug=False)
