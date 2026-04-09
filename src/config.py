"""
Shared configuration and global state for the FIFA ticket monitor.
"""

import os

DEFAULT_FIFA_URL = (
    "https://access.tickets.fifa.com/pkpcontroller/wp/FWC26SHOP/"
    "index_en.html?queue=11-FWC26-Shop"
)
FIFA_URL = DEFAULT_FIFA_URL  # backward compat

# Mutable URL setting (changeable via commands)
settings_url = {"fifa_url": DEFAULT_FIFA_URL}


def get_fifa_url():
    return settings_url["fifa_url"]
CANNOT_ACCESS_TEXT = "The page you are trying to access does not exist"
CHECK_INTERVAL = 30
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID", "")

monitor_state = {
    "status": "Waiting for extension to report…",
    "changed": False,
    "alert_sent": False,
    "last_check": None,
    "source": None,
    "extension_connected": False,
    "last_slack_update": 0,
    "countdown_seconds": None,
    "countdown_status": None,
}

# Mutable settings (controllable via commands)
settings = {
    "report_interval": 60,    # seconds between Slack status reports
    "paused": False,           # pause Slack reports
    "alert_on_change": True,   # send alert on page change
    "countdown_thresholds": [30, 20, 10, 5, 2, 1],  # minutes remaining to alert
}

# Track which thresholds have been alerted
countdown_alerted = set()

# Command log for dashboard display
command_log = []  # list of {"time": str, "source": str, "command": str, "response": str}

# Debug: store last page text from extension
last_page_text = {"text": ""}
