"""
Slack command listener — polls channel for new messages.
"""

import time

import requests as http_requests

from config import SLACK_BOT_TOKEN, SLACK_CHANNEL_ID
from services.commands import process_command


def slack_command_listener():
    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL_ID:
        print("Slack command listener disabled (no SLACK_BOT_TOKEN or SLACK_CHANNEL_ID)")
        return

    print(f"Slack command listener started for channel {SLACK_CHANNEL_ID}")

    # Get the latest message ts so we only process NEW messages from now
    try:
        resp = http_requests.get(
            "https://slack.com/api/conversations.history",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            params={"channel": SLACK_CHANNEL_ID, "limit": 1},
            timeout=15,
        )
        data = resp.json()
        if data.get("ok") and data.get("messages"):
            last_ts = data["messages"][0]["ts"]
        else:
            last_ts = str(time.time())
        print(f"Slack listener initialized, last_ts={last_ts}")
    except Exception as e:
        print(f"Slack listener init error: {e}")
        last_ts = str(time.time())

    while True:
        try:
            resp = http_requests.get(
                "https://slack.com/api/conversations.history",
                headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                params={
                    "channel": SLACK_CHANNEL_ID,
                    "oldest": last_ts,
                    "limit": 10,
                },
                timeout=15,
            )
            data = resp.json()
            if not data.get("ok"):
                print(f"Slack listener API error: {data.get('error', 'unknown')}")
            elif data.get("messages"):
                # Process messages oldest-first
                for msg in sorted(data["messages"], key=lambda m: float(m.get("ts", "0"))):
                    msg_ts = msg.get("ts", "0")
                    # Always advance last_ts to avoid reprocessing
                    if float(msg_ts) > float(last_ts):
                        last_ts = msg_ts
                    # Skip bot messages
                    if msg.get("bot_id") or msg.get("subtype"):
                        continue
                    text = msg.get("text", "").strip()
                    if text:
                        print(f"Slack command received: '{text}'")
                        process_command(text, source="slack")
        except Exception as e:
            print(f"Slack listener error: {e}")

        time.sleep(5)
