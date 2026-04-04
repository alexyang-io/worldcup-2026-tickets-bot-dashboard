"""
Shared configuration and global state for the FIFA ticket monitor.
"""

import os

FIFA_URL = (
    "https://access.tickets.fifa.com/pkpcontroller/wp/FWC26SHOP/"
    "index_en.html?queue=11-FWC26-Shop"
)
CANNOT_ACCESS_TEXT = "The page you are trying to access does not exist"
CHECK_INTERVAL = 30
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
SLACK_UPDATE_INTERVAL = 60  # send Slack status update every 60 seconds

monitor_state = {
    "status": "Waiting for extension to report…",
    "changed": False,
    "alert_sent": False,
    "last_check": None,
    "source": None,
    "extension_connected": False,
    "last_slack_update": 0,
}
