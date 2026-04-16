# FIFA World Cup 2026 Ticket Monitor

A real-time monitoring dashboard and alert system for the FIFA World Cup 2026 last-minute ticket sales queue. Built with a Flask web app, a Chrome extension, and Slack integration.

> **Legal Disclaimer:** This tool is a **monitoring and notification assistant only**. It watches a web page and alerts a human — it does not purchase, reserve, or check out tickets. Under the United States [BOTS Act of 2016](https://www.congress.gov/bill/114th-congress/senate-bill/3183) (Better Online Ticket Sales Act, 15 U.S.C. 45c), it is **illegal to use automated software to circumvent security measures, access controls, or ticket purchasing limits on ticket sales websites**, and any tickets obtained through such means may be voided. This program does not bypass any access controls, interact with purchase flows, or submit any transactions. All purchasing decisions and actions are made by the human user.

## Why This Exists

Hi, I'm Alex Yang — a lifelong soccer fan who's been dreaming of attending the FIFA World Cup 2026. When I finally sat down to buy tickets through FIFA's official portal, I was met with the most frustrating ticket sales experience imaginable: a queue page that shows "The page you are trying to access does not exist" for hours, then suddenly opens with a countdown timer, drops you into a queue, and expects you to be glued to your screen the entire time or risk missing your window.

![Cannot access page](screens/0x.%20Screen%20-%20Cannot%20access.png)

I wasn't going to sit there refreshing a browser tab all day. So I built this — a monitoring bot that watches the FIFA ticket page for me, sends Slack alerts the moment anything changes, tracks countdown timers, and lets me control it all remotely from my phone. If the queue opens at 3 AM, I'll know about it.

## What It Does

The monitor tracks five distinct page states on the FIFA ticket sales site:

### 1. Waiting for Queue to Start

The sales phase landing page before the queue opens. Nothing to do yet but wait.

![Waiting for queue](screens/0.%20Screenshot%20-%20Waiting%20for%20queue%20to%20start.png)

### 2. Cannot Access

The dreaded "does not exist" page. This is where you'll spend most of your time. The monitor watches for any change away from this state.

### 3. In Queue

You're in. The monitor reads the circular SVG progress bar and reports your queue progress percentage.

![In Queue](screens/1.%20Screenshot%20-%20Waiting%20in%20Queue.png)

### 4. Countdown

The queue is about to open. A countdown timer appears showing minutes and seconds remaining. The monitor parses this, speeds up its reporting interval from 10s to 3s, and sends Slack alerts at configurable thresholds (30, 20, 10, 5, 2, 1 minutes by default).

![Countdown](screens/2.%20Screenshot%20-%20countdown%20minutes.png)

## Architecture

```
+-------------------+       POST /api/page-content       +-------------------+
|  Chrome Extension |  -------------------------------->  |   Flask App       |
|  (content script  |  page text, countdown, progress     |   localhost:7777  |
|   on FIFA tab)    |                                     |                   |
+-------------------+                                     |  - analyze page   |
                                                          |  - detect changes |
+-------------------+       Webhook POST                  |  - countdown      |
|  Slack Channel    |  <--------------------------------  |  - progress       |
|                   |  alerts, reports, command replies    |                   |
|  user commands    |  -------------------------------->  |  poll channel     |
+-------------------+       Bot Token API                 +-------------------+
                                                                  ^
+-------------------+                                             |
|  Dashboard        |  <--- browser polls /api/status ------------|
|  (browser tab)    |  ---> POST /api/command --------------------|
+-------------------+
```

Three components work together:

- **Flask Web App** (`src/`) — Dashboard server at `http://localhost:7777`. Analyzes page content, manages state, sends Slack alerts, processes commands, serves the dashboard UI.
- **Chrome Extension** (`chrome_extension/`) — Manifest V3 content script that runs on the FIFA ticket page. Reads the actual DOM (page text, countdown timers, SVG progress bars), and POSTs the data to the Flask server every 10 seconds (3 seconds during countdowns). Also watches for DOM mutations to catch page transitions instantly.
- **Slack Integration** — Two-way: sends alerts/reports via incoming webhook, and polls a channel for user commands via bot token.

### Project Structure

```
src/
├── __init__.py                # Package root with __version__
├── app.py                     # Entry point — create_app() factory, starts background threads
├── config.py                  # Constants, env vars, shared mutable state
├── services/
│   ├── slack.py               # Slack message sending (alerts, reports)
│   ├── commands.py            # Command processor (dashboard + Slack)
│   ├── monitor.py             # Page analysis, countdown alerts, fallback monitor
│   └── slack_listener.py      # Polls Slack channel for incoming commands
├── routes/
│   ├── api.py                 # REST API endpoints (Flask Blueprint)
│   └── dashboard.py           # Dashboard route (Flask Blueprint + Jinja2)
└── templates/
    └── dashboard.html         # Dark-themed dashboard UI

chrome_extension/
├── manifest.json              # Manifest V3 content script config
└── monitor.js                 # DOM reader, countdown parser, progress extractor
```

## Installation

### Prerequisites

- Python 3.7+
- Google Chrome
- A Slack workspace (optional, but recommended)

### 1. Install Python Dependencies

```bash
pip install flask requests
```

### 2. Configure Slack (Optional)

#### Incoming Webhook (for sending alerts)

1. Go to https://api.slack.com/apps and create a new app
2. Enable **Incoming Webhooks**
3. Click **Add New Webhook to Workspace**, select a channel
4. Copy the Webhook URL

#### Bot Token (for receiving commands from Slack)

1. In your Slack app, go to **OAuth & Permissions**
2. Add bot scope: `channels:history`
3. Install/reinstall to workspace
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)
5. Invite the bot to your channel: `/invite @YourBotName`

#### Find Your Channel ID

Open Slack in a browser, navigate to the channel. The URL contains the channel ID: `https://app.slack.com/client/TXXXXXXX/CXXXXXXXX` — the `CXXXXXXXX` part is your Channel ID.

### 3. Start the App

```bash
cd src

# Set environment variables
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
export SLACK_BOT_TOKEN="xoxb-your-bot-token"          # optional
export SLACK_CHANNEL_ID="CXXXXXXXX"                    # optional

# Run
python app.py
```

The dashboard will be available at **http://localhost:7777**.

### 4. Install the Chrome Extension

1. Open `chrome://extensions` in Chrome
2. Enable **Developer mode** (toggle top-right)
3. Click **Load unpacked**
4. Select the `chrome_extension/` folder
5. Verify the extension appears and is enabled

### 5. Start Monitoring

1. Open **http://localhost:7777** in your browser
2. Click **"Open FIFA Ticket Page"** — this opens the FIFA ticket page in a new tab
3. The Chrome extension silently monitors the page and reports to the dashboard
4. Interact with the FIFA page normally — the extension runs in the background

## Usage

### Dashboard

![Dashboard UI](screens/Screenshot%20-%20Dashboard%20Waiting.png)

The dashboard at `http://localhost:7777` shows live status with:

- **Status badges** — Extension connection (green/yellow), report interval, Slack command listener, live countdown timer (color-coded: blue > 10min, yellow 5-10min, red < 5min), queue progress (blue < 50%, yellow 50-79%, green >= 80%), monitored URL
- **Alert banner** — green popup + audio beep + browser notification when the page changes
- **Command console** — type commands directly, see responses and command history

### Commands

All commands work from both the dashboard console and Slack:

| Command | Description |
|---|---|
| `report every N minutes` | Change Slack report frequency |
| `report every N seconds` | Change report frequency (min 10s) |
| `report now` | Send a status report immediately |
| `url` | Show current FIFA ticket URL |
| `url <full-url>` | Change the monitored URL at runtime |
| `countdown alerts 30,20,10,5,2,1` | Set countdown alert thresholds (minutes) |
| `reset countdown` | Re-arm all countdown alerts |
| `status` | Show full current status |
| `pause` / `resume` | Pause/resume periodic Slack reports |
| `reset` | Reset page-change alert state |
| `help` | Show all commands |

Commands sent from Slack are picked up by the bot and processed in real time. Responses are posted back to the channel, so you can control the monitor entirely from your phone.

![Slack Interactions](screens/Screenshot%20-%20Slack%20Interactions.png)

### Slack Alerts

![Slack Notifications](screens/Screenshot%20-%20Slack%20Notifications.png)

The system sends four types of Slack messages:

1. **Page change alert** — one-time alert when the page leaves the "Cannot access" state
2. **Countdown threshold alerts** — when the countdown crosses each configured threshold
3. **Periodic status reports** — at the configured interval (default 60s) with page status, countdown, and content preview
4. **Command responses** — replies to commands sent via Slack

## Troubleshooting

| Problem | Solution |
|---|---|
| Extension shows "waiting" | Reload extension in `chrome://extensions`, hard refresh the FIFA tab |
| "Server check got blocked" | Normal — FIFA blocks direct HTTP requests. Use the Chrome extension |
| Slack commands not working | Verify bot token starts with `xoxb-`, has `channels:history` scope, and bot is invited to channel |
| Countdown not detected | Reload extension + refresh FIFA tab. Parser looks for "enter in" text with MM:SS |
| Port 7777 in use | `lsof -ti:7777 \| xargs kill -9` then restart |
