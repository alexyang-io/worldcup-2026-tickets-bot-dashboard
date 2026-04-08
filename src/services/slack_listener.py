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
    last_ts = str(time.time())  # only process messages after startup

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
                print(f"Slack listener API error: {data.get('error', 'unknown')} — need a xoxb- Bot Token with channels:history scope")
            if data.get("ok") and data.get("messages"):
                # Process messages oldest-first
                for msg in reversed(data["messages"]):
                    # Skip bot messages (our own replies)
                    if msg.get("bot_id") or msg.get("subtype"):
                        continue
                    text = msg.get("text", "").strip()
                    msg_ts = msg.get("ts", last_ts)
                    if text and float(msg_ts) > float(last_ts):
                        process_command(text, source="slack")
                        last_ts = msg_ts
                # Update last_ts to most recent
                if data["messages"]:
                    newest_ts = max(m.get("ts", "0") for m in data["messages"])
                    if float(newest_ts) > float(last_ts):
                        last_ts = newest_ts
        except Exception as e:
            print(f"Slack listener error: {e}")

        time.sleep(5)  # poll every 5 seconds
