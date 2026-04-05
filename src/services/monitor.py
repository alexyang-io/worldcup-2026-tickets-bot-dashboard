"""
Page analysis and fallback server-side monitor.
"""

import time

import requests as http_requests

from config import (
    CANNOT_ACCESS_TEXT,
    CHECK_INTERVAL,
    FIFA_URL,
    monitor_state,
    settings,
)
from services.slack import send_slack_alert, send_slack_status_update


def analyze_page(text: str, source: str):
    ts = time.strftime("%H:%M:%S")
    now = time.time()
    monitor_state["last_check"] = ts
    monitor_state["source"] = source

    # Ignore bad/error responses from server-side fallback
    if source == "server" and ("bad request" in text.lower() or "<title>Bad" in text or len(text.strip()) < 20):
        monitor_state["status"] = "Server check got blocked — waiting for extension"
        print(f"[{ts}] [{source}] Ignoring bad response from server")
        return

    if CANNOT_ACCESS_TEXT in text:
        monitor_state["status"] = "Still showing 'Cannot access' page"
        monitor_state["changed"] = False
    else:
        if "In Queue" in text:
            msg = "You are IN THE QUEUE! Go go go!"
        elif "queue" in text.lower() or "waiting" in text.lower():
            msg = "Queue page detected — may be opening!"
        else:
            preview = text[:100].replace("\n", " ").strip()
            msg = f"Page changed! Preview: {preview}"
        monitor_state["status"] = msg
        monitor_state["changed"] = True

        if not monitor_state["alert_sent"] and settings["alert_on_change"]:
            send_slack_alert(msg)
            monitor_state["alert_sent"] = True

    # Periodic Slack status update
    if not settings["paused"] and now - monitor_state["last_slack_update"] >= settings["report_interval"]:
        monitor_state["last_slack_update"] = now
        summary = text.strip().replace("\n", " | ")
        if len(summary) > 300:
            summary = summary[:300] + "…"
        send_slack_status_update(monitor_state["status"], summary)

    print(f"[{ts}] [{source}] {monitor_state['status']}")


def fallback_monitor_loop():
    time.sleep(60)
    while True:
        if monitor_state["extension_connected"] and monitor_state["source"] == "extension":
            last = monitor_state.get("last_check")
            if last:
                time.sleep(CHECK_INTERVAL)
                continue

        try:
            resp = http_requests.get(FIFA_URL, timeout=20, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                ),
            })
            analyze_page(resp.text, source="server")
        except Exception as e:
            monitor_state["status"] = f"Error: {e}"

        time.sleep(CHECK_INTERVAL)
