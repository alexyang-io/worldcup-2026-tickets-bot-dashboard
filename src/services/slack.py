"""
Slack notification services.
"""

import time

import requests as http_requests

from config import FIFA_URL, SLACK_WEBHOOK_URL, monitor_state, settings


def send_slack_message(text: str):
    if not SLACK_WEBHOOK_URL:
        print(f"[Slack - no webhook] {text}")
        return
    try:
        r = http_requests.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=10)
        print(f"Slack msg {'sent' if r.ok else 'failed'}: {r.status_code}")
    except Exception as e:
        print(f"Slack error: {e}")


def send_slack_alert(message: str):
    send_slack_message(
        f":rotating_light: *FIFA WC 2026 Ticket Alert* :rotating_light:\n"
        f"{message}\n\n<{FIFA_URL}|Open ticket page>"
    )


def send_slack_status_update(status: str, page_summary: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    cd = monitor_state.get("countdown_status") or "not detected"
    send_slack_message(
        f":satellite: *FIFA Ticket Monitor — Status Update*\n"
        f"*Time:* {ts}\n"
        f"*Status:* {status}\n"
        f"*Countdown:* {cd}\n"
        f"*Report interval:* {settings['report_interval']}s | *Paused:* {settings['paused']}\n"
        f"*Page content:* {page_summary}"
    )
