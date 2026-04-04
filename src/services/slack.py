"""
Slack notification services.
"""

import time

import requests as http_requests

from config import FIFA_URL, SLACK_WEBHOOK_URL


def send_slack_alert(message: str):
    if not SLACK_WEBHOOK_URL:
        print(f"[ALERT - no webhook] {message}")
        return
    payload = {
        "text": (
            ":rotating_light: *FIFA WC 2026 Ticket Alert* :rotating_light:\n"
            f"{message}\n\n<{FIFA_URL}|Open ticket page>"
        ),
    }
    try:
        r = http_requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        print(f"Slack alert {'sent' if r.ok else 'failed'}: {r.status_code}")
    except Exception as e:
        print(f"Slack error: {e}")


def send_slack_status_update(status: str, page_summary: str):
    if not SLACK_WEBHOOK_URL:
        print(f"[STATUS - no webhook] {status}")
        return
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "text": (
            f":satellite: *FIFA Ticket Monitor — Status Update*\n"
            f"*Time:* {ts}\n"
            f"*Status:* {status}\n"
            f"*Page content:* {page_summary}"
        ),
    }
    try:
        r = http_requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        print(f"Slack status update {'sent' if r.ok else 'failed'}: {r.status_code}")
    except Exception as e:
        print(f"Slack status update error: {e}")
