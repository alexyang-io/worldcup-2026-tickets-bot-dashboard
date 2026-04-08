"""
Command processor for dashboard and Slack commands.
"""

import re
import time

from config import command_log, countdown_alerted, monitor_state, settings
from services.slack import send_slack_message


def process_command(cmd: str, source: str = "dashboard") -> str:
    cmd = cmd.strip().lower()
    ts = time.strftime("%H:%M:%S")
    response = ""

    # report every N minutes/seconds
    m = re.match(r"report\s+every\s+(\d+)\s*(m(?:in(?:ute)?s?)?|s(?:ec(?:ond)?s?)?)?", cmd)
    if m:
        val = int(m.group(1))
        unit = (m.group(2) or "m")[0]
        secs = val * 60 if unit == "m" else val
        secs = max(10, secs)  # minimum 10 seconds
        settings["report_interval"] = secs
        response = f"Report interval set to {secs}s ({secs//60}m {secs%60}s)"

    # status
    elif cmd == "status":
        cd = monitor_state.get("countdown_status") or "not detected"
        alerted = sorted(countdown_alerted, reverse=True) if countdown_alerted else "none"
        response = (
            f"Status: {monitor_state['status']}\n"
            f"Countdown: {cd}\n"
            f"Countdown thresholds: {settings['countdown_thresholds']} min\n"
            f"Countdown alerted: {alerted}\n"
            f"Changed: {monitor_state['changed']}\n"
            f"Extension: {'connected' if monitor_state['extension_connected'] else 'disconnected'}\n"
            f"Report interval: {settings['report_interval']}s\n"
            f"Paused: {settings['paused']}\n"
            f"Last check: {monitor_state['last_check']} (via {monitor_state['source']})"
        )

    # pause / resume
    elif cmd == "pause":
        settings["paused"] = True
        response = "Slack reports paused."

    elif cmd == "resume":
        settings["paused"] = False
        response = "Slack reports resumed."

    # report now
    elif cmd in ("report", "report now"):
        monitor_state["last_slack_update"] = 0  # force next report
        response = "Sending report now."

    # reset alert
    elif cmd in ("reset", "reset alert"):
        monitor_state["alert_sent"] = False
        monitor_state["changed"] = False
        response = "Alert reset."

    # countdown thresholds: "countdown alerts 30,20,10,5,2,1"
    elif cmd.startswith("countdown alerts") or cmd.startswith("countdown thresholds"):
        nums = re.findall(r"\d+", cmd[len("countdown"):])
        if nums:
            settings["countdown_thresholds"] = sorted([int(n) for n in nums], reverse=True)
            countdown_alerted.clear()
            response = f"Countdown alert thresholds set to {settings['countdown_thresholds']} minutes"
        else:
            response = f"Current thresholds: {settings['countdown_thresholds']} minutes\nUsage: countdown alerts 30,20,10,5,2,1"

    # reset countdown alerts
    elif cmd == "reset countdown":
        countdown_alerted.clear()
        response = f"Countdown alerts reset. Thresholds: {settings['countdown_thresholds']} min"

    # help
    elif cmd in ("help", "list commands", "commands"):
        response = (
            "Commands:\n"
            "  report every N minutes    — change report frequency\n"
            "  report every N seconds    — change report frequency\n"
            "  report now                — send a report immediately\n"
            "  countdown alerts 30,20,10 — set countdown alert thresholds (minutes)\n"
            "  reset countdown           — re-arm countdown alerts\n"
            "  status                    — show current status\n"
            "  pause / resume            — pause/resume Slack reports\n"
            "  reset                     — reset alert state\n"
            "  help                      — show this help"
        )

    else:
        response = f"Unknown command: '{cmd}'. Type 'help' for available commands."

    # Log it
    command_log.append({"time": ts, "source": source, "command": cmd, "response": response})
    if len(command_log) > 50:
        command_log.pop(0)

    print(f"[{ts}] [CMD/{source}] {cmd} → {response}")

    # Echo response to Slack if command came from Slack
    if source == "slack":
        send_slack_message(f":robot_face: {response}")

    return response
