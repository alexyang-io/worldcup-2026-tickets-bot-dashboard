# FIFA World Cup 2026 Ticket Monitor

## What This Project Does

A monitoring system that watches the FIFA World Cup 2026 ticket queue page and sends Slack alerts when the page status changes. It has three components:

1. **Flask web dashboard** at `http://localhost:7777/` — shows live status, countdown timer, command console
2. **Chrome extension** — content script that runs on the FIFA ticket page, reads page content every 10s (3s during countdown), and POSTs it to the dashboard server
3. **Slack integration** — sends alerts on page changes, periodic status reports, countdown threshold alerts, and accepts commands from a Slack channel

## Target URL

The FIFA ticket page URL:
```
https://access.tickets.fifa.com/pkpcontroller/wp/FWC26SHOP/index_en.html?queue=11-FWC26-Shop
```

## Page States to Detect

Reference screenshots are in `screens/`. The monitor must detect these states:

1. **"Cannot access"** — page shows "The page you are trying to access does not exist". This is the default/waiting state before the queue opens
2. **"In Queue"** — user is in the ticket queue. The extension should parse the circular SVG progress bar (look for `#progress-arc` element or SVG circles with `stroke-dasharray`/`stroke-dashoffset`)
3. **Countdown (minutes)** — page shows "You will be able to enter in...." with a `MM:SS` timer (e.g. "11:50" with "min." / "sec." labels)
4. **Countdown (seconds)** — same but just seconds remaining
5. **Page changed** — any other content means the queue opened or changed

## Environment Variables

```
SLACK_WEBHOOK_URL  — Slack incoming webhook for sending messages
SLACK_BOT_TOKEN    — xoxb- bot token with channels:history scope (for reading commands)
SLACK_CHANNEL_ID   — Slack channel ID to poll for commands
```

## Dependencies

```
pip install flask requests
```

## Project Structure

```
src/
├── __init__.py                # Package root with __version__
├── app.py                     # Entry point — create_app() factory, starts background threads
├── config.py                  # All constants, env vars, shared mutable state (monitor_state, settings, settings_url, countdown_alerted, command_log, last_page_text)
├── services/
│   ├── __init__.py
│   ├── slack.py               # send_slack_message(), send_slack_alert(), send_slack_status_update()
│   ├── commands.py            # process_command() — shared command processor for dashboard + Slack (including url command)
│   ├── monitor.py             # analyze_page(), parse_countdown_from_text(), fallback_monitor_loop(), countdown alert functions
│   └── slack_listener.py      # slack_command_listener() — polls Slack channel for commands
├── routes/
│   ├── __init__.py
│   ├── api.py                 # Flask Blueprint: /api/page-content, /api/status, /api/command, /api/commands, /api/reset, /api/debug/page-text
│   └── dashboard.py           # Flask Blueprint: / (serves Jinja2 template)
└── templates/
    └── dashboard.html         # Jinja2 template — dark theme dashboard with badges, command console, alert banner

chrome_extension/
├── manifest.json              # Manifest V3, content script on access.tickets.fifa.com/*
└── monitor.js                 # Content script — reads page text, parses countdown/progress, POSTs to /api/page-content
```

## Architecture Details

### Shared State (config.py)

All mutable state lives in `config.py` as module-level dicts/sets so all modules share the same references:

- `DEFAULT_FIFA_URL` — the default FIFA ticket page URL constant
- `settings_url` dict — `{"fifa_url": DEFAULT_FIFA_URL}`, changeable at runtime via the `url` command
- `get_fifa_url()` — accessor function that returns the current FIFA URL from `settings_url`
- `monitor_state` dict — current status, changed flag, alert_sent, last_check time, source (extension/server), extension_connected, countdown_seconds, countdown_status, queue_progress
- `settings` dict — report_interval (default 60s), paused, alert_on_change, countdown_thresholds ([30,20,10,5,2,1] minutes)
- `countdown_alerted` set — tracks which minute-thresholds have fired (prevents duplicate alerts)
- `command_log` list — last 50 commands with timestamp, source, command text, response text
- `last_page_text` dict — `{"text": ""}`, stores last page text received from extension for debug

### Flask App (app.py)

- Uses `create_app()` factory pattern
- Registers `api_bp` and `dashboard_bp` blueprints
- Adds CORS headers via `@app.after_request` (Allow-Origin: *, Content-Type, GET/POST/OPTIONS)
- `__main__` block starts two daemon threads: `fallback_monitor_loop` and `slack_command_listener`
- Runs on `0.0.0.0:7777`

### Page Analysis (services/monitor.py)

`parse_countdown_from_text(text)`:
- Server-side countdown parser that extracts countdown seconds from page text
- Looks for "enter in" text, then parses MM:SS (e.g. "07:30") or standalone number with sec/min label on the next line
- Returns total seconds or None

`analyze_page(text, source)`:
- Ignores bad/blocked server responses (text contains "bad request", `<title>Bad`, or is < 20 chars) — only for source="server"
- Calls `parse_countdown_from_text()` to detect and update countdown state server-side (works for both extension and server sources)
- Detects "Cannot access" text → status unchanged
- Detects "In Queue" (with queue progress percentage if available), active countdown, queue/waiting keywords, or any other change → sets changed=True, sends Slack alert (once)
- Sends periodic Slack status updates based on `settings["report_interval"]` unless paused

`fallback_monitor_loop()`:
- Waits 60s for extension to connect, then polls FIFA URL directly every 30s via `get_fifa_url()`
- Skips if extension is connected and reporting
- Uses Chrome-like User-Agent header

Countdown functions:
- `check_countdown_thresholds(seconds)` — iterates thresholds, fires `send_countdown_alert()` when countdown crosses each threshold for the first time
- `send_countdown_alert()` — Slack message with hourglass emoji, threshold name, and MM:SS remaining

### Slack Services (services/slack.py)

- `send_slack_message(text)` — base function, POSTs to webhook. Prints to console if no webhook configured
- `send_slack_alert(message)` — wraps with rotating_light emoji and dynamic FIFA URL link via `get_fifa_url()`
- `send_slack_status_update(status, page_summary)` — includes timestamp, status, queue progress, countdown info, report interval, paused state, and page content summary (truncated to 300 chars)

### Command Processor (services/commands.py)

`process_command(cmd, source)` handles these commands (case-insensitive):

| Command | Action |
|---------|--------|
| `report every N minutes/seconds` | Change report interval (min 10s) |
| `report now` | Force next report by resetting last_slack_update to 0 |
| `status` | Show full status including URL, countdown, thresholds, extension state |
| `pause` / `resume` | Pause/resume periodic Slack reports |
| `reset` | Reset alert_sent and changed flags |
| `countdown alerts 30,20,10` | Set countdown threshold minutes |
| `url` | Show current FIFA ticket URL |
| `url <full-url>` | Change the monitored URL at runtime via `settings_url` |
| `reset countdown` | Clear countdown_alerted set (re-arms all thresholds) |
| `help` / `list commands` / `commands` | Show help text |

- Logs every command to `command_log` (max 50 entries)
- Echoes response to Slack if command came from Slack (with robot_face emoji)

### Slack Command Listener (services/slack_listener.py)

- On startup, fetches latest message timestamp from channel (avoids replaying history on restart)
- Polls `conversations.history` every 5s for new messages
- Skips bot messages and subtypes
- Advances `last_ts` for ALL messages (including bot) to prevent reprocessing
- Processes user messages through `process_command(text, source="slack")`
- Requires `SLACK_BOT_TOKEN` (xoxb-) with `channels:history` scope

### API Endpoints (routes/api.py)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/page-content` | POST | Extension sends `{text, url, queue_progress, progress_debug, dom_snapshot, ...}`. Stores text/debug data, handles queue_progress, calls `analyze_page()` (countdown parsing is handled server-side in `analyze_page`) |
| `/api/status` | GET | Returns `{...monitor_state, settings: {...}, fifa_url: "..."}` |
| `/api/command` | POST | Accepts `{command: "..."}`, returns `{ok, response}` |
| `/api/commands` | GET | Returns last 20 command log entries |
| `/api/debug/page-text` | GET | Returns `{text, progress_debug, dom_snapshot}` — last data received from extension (for troubleshooting) |
| `/api/reset` | POST | Resets alert_sent, changed, status |

### Dashboard (routes/dashboard.py + templates/dashboard.html)

- Blueprint with `template_folder` pointing to `../templates`
- Passes `fifa_url` via `get_fifa_url()` to the Jinja2 template
- Dark theme (#0e0e1a background, #181830 card)
- Status badges: Extension (green/yellow), Report interval (blue/red when paused), Slack cmds (green), Countdown (blue/yellow/red based on time: red <=5min, yellow <=10min), Progress (blue < 50%, yellow 50-79%, green >= 80%), URL (blue, truncated with tooltip)
- Dynamic FIFA URL: JS `currentFifaUrl` variable updated from `/api/status` poll, used by `openFifa()` function
- Pulsing status dot: waiting (gray), monitoring (amber), changed (green), error (red)
- Alert banner with popIn animation when page changes
- Audio beep + browser Notification on change
- Command console with text input, Run button, response display, and scrollable command log
- Polls `/api/status` every 3s, refreshes command log every 10s

### Chrome Extension (chrome_extension/)

Manifest V3 content script running on `https://access.tickets.fifa.com/*` at `document_idle`.

`monitor.js` features:
- Reports page text to `http://localhost:7777/api/page-content` every 10s normally, 3s when countdown detected
- `parseCountdown(text)` — looks for "enter in" text, then parses MM:SS or standalone number with sec/min label. Returns total seconds
- `parseQueueProgress()` — first tries `document.getElementById("progress-arc")`, then SVG circles with non-zero dashoffset (skips background circles), then aria-valuenow. Returns 0-100 percentage
- `getProgressDebugInfo()` — collects SVG circle attributes and progress element attributes (only sent when progress not found)
- `getDomSnapshot()` — captures SVGs, styled elements with gradient/stroke/dash, and canvases (only sent when progress not found)
- MutationObserver watches for DOM changes and triggers report after 1.5s debounce
- POSTs JSON: `{text, url, countdown_seconds, queue_progress, progress_debug, dom_snapshot}`

## How to Run

```bash
cd src
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_CHANNEL_ID="C0XXXXXXX"
python app.py
```

Then load `chrome_extension/` in Chrome (chrome://extensions, Developer mode, Load unpacked) and open the FIFA ticket page from the dashboard.

## Use a Chrome extension to interact with the browser tabs and pass information and commands between.
