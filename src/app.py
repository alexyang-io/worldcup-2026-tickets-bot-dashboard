"""
FIFA World Cup 2026 Ticket Monitor — Entry Point

Dashboard at http://localhost:7777.
A Chrome extension monitors the ACTUAL content of the FIFA ticket tab
and reports it back to this server. Sends Slack alerts when the page changes.

Setup:
    1. pip install flask requests
    2. export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
    3. python app.py
    4. Load chrome_extension/ in Chrome (chrome://extensions → Developer mode → Load unpacked)
    5. Open the FIFA ticket page from the dashboard
"""

import threading

from flask import Flask

from config import CHECK_INTERVAL, FIFA_URL, SLACK_WEBHOOK_URL
from routes.api import api_bp
from routes.dashboard import dashboard_bp
from services.monitor import fallback_monitor_loop


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.register_blueprint(dashboard_bp)
    return app


if __name__ == "__main__":
    print(f"Slack webhook: {'configured' if SLACK_WEBHOOK_URL else 'NOT SET'}")
    print(f"Monitoring: {FIFA_URL}")
    print(f"Check interval: {CHECK_INTERVAL}s\n")

    # Start fallback server-side monitor
    t = threading.Thread(target=fallback_monitor_loop, daemon=True)
    t.start()

    app = create_app()
    print(f"Dashboard: http://localhost:7777")
    print(f"Load chrome_extension/ in Chrome to enable live tab monitoring.\n")
    app.run(host="0.0.0.0", port=7777, debug=False)
