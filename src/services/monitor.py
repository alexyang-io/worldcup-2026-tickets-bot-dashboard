"""
Page analysis and fallback server-side monitor.
"""

import re
import time

import requests as http_requests

from config import (
    CANNOT_ACCESS_TEXT,
    CHECK_INTERVAL,
    countdown_alerted,
    get_fifa_url,
    monitor_state,
    settings,
)
from services.slack import send_slack_alert, send_slack_message, send_slack_status_update


def parse_countdown_from_text(text: str):
    """Parse countdown seconds from page text server-side.

    The FIFA page shows:
        You will be able to enter in....
        07:30
        min.
        sec.
    """
    if "enter in" not in text.lower():
        return None
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        # Match MM:SS (e.g., "07:30", "11:50")
        m = re.match(r"^(\d{1,3}):(\d{2})$", line)
        if m:
            mins = int(m.group(1))
            secs = int(m.group(2))
            return mins * 60 + secs
        # Match standalone number followed by "sec." on next line
        m = re.match(r"^(\d{1,4})$", line)
        if m:
            val = int(m.group(1))
            next_line = lines[i + 1].lower() if i + 1 < len(lines) else ""
            if "sec" in next_line:
                return val
            if "min" in next_line:
                return val * 60
    return None


def send_countdown_alert(minutes_remaining: int, seconds_total: int):
    mins = seconds_total // 60
    secs = seconds_total % 60
    send_slack_message(
        f":hourglass_flowing_sand: *Countdown Alert — {minutes_remaining} min threshold!*\n"
        f"Time remaining: *{mins:02d}:{secs:02d}*\n"
        f"Get ready to grab those tickets!"
    )


def check_countdown_thresholds(seconds_remaining: int):
    """Check if countdown crossed any configured thresholds and send alerts."""
    if seconds_remaining is None:
        return
    minutes_remaining = seconds_remaining / 60.0
    for threshold in sorted(settings["countdown_thresholds"], reverse=True):
        if minutes_remaining <= threshold and threshold not in countdown_alerted:
            countdown_alerted.add(threshold)
            send_countdown_alert(threshold, seconds_remaining)
            print(f"Countdown alert: {threshold}min threshold (actual: {seconds_remaining}s)")


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

    # Server-side countdown parsing from page text
    countdown_secs = parse_countdown_from_text(text)
    if countdown_secs is not None:
        monitor_state["countdown_seconds"] = countdown_secs
        mins = countdown_secs // 60
        secs = countdown_secs % 60
        monitor_state["countdown_status"] = f"{mins:02d}:{secs:02d} remaining"
        check_countdown_thresholds(countdown_secs)
    elif "enter in" not in text.lower():
        monitor_state["countdown_seconds"] = None
        monitor_state["countdown_status"] = None

    if CANNOT_ACCESS_TEXT in text:
        monitor_state["status"] = "Still showing 'Cannot access' page"
        monitor_state["changed"] = False
    else:
        if "In Queue" in text:
            msg = "You are IN THE QUEUE! Go go go!"
        elif monitor_state.get("countdown_seconds") is not None:
            cd = monitor_state["countdown_seconds"]
            msg = f"Countdown active! {cd // 60:02d}:{cd % 60:02d} remaining"
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
            resp = http_requests.get(get_fifa_url(), timeout=20, headers={
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
