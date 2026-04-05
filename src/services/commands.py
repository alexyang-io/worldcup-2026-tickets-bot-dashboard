"""
Command processor for dashboard and Slack commands.
"""

import re
import time

from config import command_log, monitor_state, settings
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
        response = (
            f"Status: {monitor_state['status']}\n"
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

    # help
    elif cmd == "help":
        response = (
            "Commands:\n"
            "  report every N minutes  — change report frequency\n"
            "  report every N seconds  — change report frequency\n"
            "  report now              — send a report immediately\n"
            "  status                  — show current status\n"
            "  pause                   — pause Slack reports\n"
            "  resume                  — resume Slack reports\n"
            "  reset                   — reset alert state\n"
            "  help                    — show this help"
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
