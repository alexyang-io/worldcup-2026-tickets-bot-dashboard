"""
FIFA World Cup 2026 Ticket Monitor — Web App + Chrome Extension

Dashboard at http://localhost:7777.
A Chrome extension monitors the ACTUAL content of the FIFA ticket tab
and reports it back to this server. Sends Slack alerts when the page changes.

Setup:
    1. pip install flask requests
    2. export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
    3. python app.py
    4. Load chrome_extension/ in Chrome (chrome://extensions → Developer mode → Load unpacked)
    5. Open the FIFA ticket page from the dashboard
"""

import os
import threading
import time

import requests as http_requests
from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
FIFA_URL = (
    "https://access.tickets.fifa.com/pkpcontroller/wp/FWC26SHOP/"
    "index_en.html?queue=11-FWC26-Shop"
)
CANNOT_ACCESS_TEXT = "The page you are trying to access does not exist"
CHECK_INTERVAL = 30
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

monitor_state = {
    "status": "Waiting for extension to report…",
    "changed": False,
    "alert_sent": False,
    "last_check": None,
    "source": None,  # "extension" or "server"
    "extension_connected": False,
    "last_slack_update": 0,  # timestamp of last periodic Slack update
}

SLACK_UPDATE_INTERVAL = 60  # send Slack status update every 60 seconds

# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------

def send_slack_alert(message: str):
    if not SLACK_WEBHOOK_URL:
        print(f"[ALERT - no webhook] {message}")
        return
    payload = {
        "text": (
            ":rotating_light: *FIFA WC 2026 Ticket Alert* :rotating_light:\n"
            f"{message}\n\n<{FIFA_URL}|Open ticket page>"
        ),
    }
    try:
        r = http_requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        print(f"Slack alert {'sent' if r.ok else 'failed'}: {r.status_code}")
    except Exception as e:
        print(f"Slack error: {e}")

def send_slack_status_update(status: str, page_summary: str):
    if not SLACK_WEBHOOK_URL:
        print(f"[STATUS - no webhook] {status}")
        return
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "text": (
            f":satellite: *FIFA Ticket Monitor — Status Update*\n"
            f"*Time:* {ts}\n"
            f"*Status:* {status}\n"
            f"*Page content:* {page_summary}"
        ),
    }
    try:
        r = http_requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        print(f"Slack status update {'sent' if r.ok else 'failed'}: {r.status_code}")
    except Exception as e:
        print(f"Slack status update error: {e}")

# ---------------------------------------------------------------------------
# Analyze page text (shared by extension + server-side fallback)
# ---------------------------------------------------------------------------

def analyze_page(text: str, source: str):
    ts = time.strftime("%H:%M:%S")
    now = time.time()
    monitor_state["last_check"] = ts
    monitor_state["source"] = source

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

        if not monitor_state["alert_sent"]:
            send_slack_alert(msg)
            monitor_state["alert_sent"] = True

    # Send periodic Slack status update every 60 seconds
    if now - monitor_state["last_slack_update"] >= SLACK_UPDATE_INTERVAL:
        monitor_state["last_slack_update"] = now
        # Build a concise status summary from the page text
        summary = text.strip().replace("\n", " | ")
        if len(summary) > 300:
            summary = summary[:300] + "…"
        send_slack_status_update(monitor_state["status"], summary)

    print(f"[{ts}] [{source}] {monitor_state['status']}")

# ---------------------------------------------------------------------------
# Extension endpoint — receives page content from Chrome extension
# ---------------------------------------------------------------------------

@app.route("/api/page-content", methods=["POST"])
def page_content():
    data = request.get_json(silent=True)
    if not data or "text" not in data:
        return jsonify({"error": "missing text"}), 400

    monitor_state["extension_connected"] = True
    analyze_page(data["text"], source="extension")
    return jsonify({"ok": True})

# ---------------------------------------------------------------------------
# Server-side fallback monitor (only active if extension hasn't reported)
# ---------------------------------------------------------------------------

def fallback_monitor_loop():
    # Give extension 60s to connect before starting fallback
    time.sleep(60)
    while True:
        # If extension reported recently (within 60s), skip server-side check
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

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.route("/api/status")
def api_status():
    return jsonify(monitor_state)

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>FIFA WC 2026 — Ticket Monitor</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0e0e1a;
    color: #e0e0e0;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
  }
  .card {
    background: #181830;
    border: 1px solid #2a2a4a;
    border-radius: 16px;
    padding: 40px;
    max-width: 600px;
    width: 100%;
    text-align: center;
  }
  h1 { font-size: 22px; color: #fff; margin-bottom: 6px; }
  .subtitle { color: #888; font-size: 13px; margin-bottom: 28px; }

  /* Status */
  .status-section { margin-bottom: 24px; }
  .dot {
    width: 14px; height: 14px;
    border-radius: 50%;
    display: inline-block;
    vertical-align: middle;
    margin-right: 8px;
  }
  .dot.monitoring { background: #f0ad4e; animation: pulse 2s infinite; }
  .dot.changed   { background: #5cb85c; animation: pulse 0.5s infinite; }
  .dot.waiting   { background: #555; animation: pulse 3s infinite; }
  .dot.error     { background: #d9534f; }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
  .status-text { font-size: 16px; color: #ccc; }
  .status-text.changed { color: #5cb85c; font-weight: bold; }
  .meta { color: #555; font-size: 12px; margin-top: 6px; }

  /* Extension status */
  .ext-status {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    margin-bottom: 20px;
  }
  .ext-status.connected { background: #1a3a1a; color: #5cb85c; border: 1px solid #2a5a2a; }
  .ext-status.waiting { background: #3a3a1a; color: #f0ad4e; border: 1px solid #5a5a2a; }

  /* Alert banner */
  .alert-banner {
    display: none;
    padding: 16px 24px;
    background: linear-gradient(135deg, #28a745, #218838);
    color: #fff;
    font-size: 18px;
    font-weight: bold;
    border-radius: 12px;
    margin-bottom: 20px;
    max-width: 600px;
    width: 100%;
    text-align: center;
    animation: popIn 0.4s ease;
  }
  .alert-banner.show { display: block; }
  @keyframes popIn {
    from { transform: scale(0.9); opacity: 0; }
    to   { transform: scale(1);   opacity: 1; }
  }

  .btn {
    display: inline-block;
    padding: 12px 28px;
    background: #3b82f6;
    color: #fff;
    text-decoration: none;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 600;
    border: none;
    cursor: pointer;
    transition: background 0.2s;
    margin: 6px;
  }
  .btn:hover { background: #2563eb; }
  .btn.secondary {
    background: transparent;
    border: 1px solid #444;
    color: #aaa;
    font-size: 13px;
    padding: 8px 18px;
  }
  .btn.secondary:hover { background: #222; color: #fff; }

  .info {
    margin-top: 24px;
    padding: 16px;
    background: #1e1e38;
    border-radius: 8px;
    font-size: 13px;
    color: #777;
    line-height: 1.7;
    text-align: left;
  }
  .info b { color: #aaa; }
  .info code {
    background: #252545;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 12px;
    color: #bbb;
  }
</style>
</head>
<body>

<div class="alert-banner" id="alertBanner">
  PAGE CHANGED — Check the FIFA tab now!
</div>

<div class="card">
  <h1>FIFA World Cup 2026</h1>
  <p class="subtitle">Ticket Page Monitor</p>

  <div>
    <span class="ext-status waiting" id="extStatus">Extension: waiting…</span>
  </div>

  <div class="status-section">
    <span class="dot waiting" id="dot"></span>
    <span class="status-text" id="status">Waiting for first check…</span>
    <div class="meta" id="meta"></div>
  </div>

  <div>
    <button class="btn" onclick="window.open('FIFAURL_PLACEHOLDER', 'fifa_tickets')">
      Open FIFA Ticket Page
    </button>
  </div>
  <div style="margin-top: 8px;">
    <button class="btn secondary" onclick="resetAlert()">Reset Alert</button>
  </div>

  <div class="info">
    <b>Setup:</b><br>
    1. Go to <code>chrome://extensions</code> in Chrome<br>
    2. Enable <b>Developer mode</b> (toggle top-right)<br>
    3. Click <b>Load unpacked</b> → select the <code>chrome_extension/</code> folder<br>
    4. Click "Open FIFA Ticket Page" above<br><br>
    <b>How it works:</b><br>
    The extension reads the <b>actual content</b> of your FIFA tab every 10 seconds
    and reports it here. When the page changes from "Cannot access" →
    Slack alert + sound + browser notification. You interact with the page normally.
  </div>
</div>

<script>
  const dot = document.getElementById('dot');
  const statusEl = document.getElementById('status');
  const metaEl = document.getElementById('meta');
  const extStatus = document.getElementById('extStatus');
  const banner = document.getElementById('alertBanner');
  let alertShown = false;

  function resetAlert() {
    fetch('/api/reset', { method: 'POST' });
    alertShown = false;
    banner.classList.remove('show');
  }

  async function poll() {
    try {
      const r = await fetch('/api/status');
      const data = await r.json();
      statusEl.textContent = data.status;

      // Extension connection status
      if (data.extension_connected) {
        extStatus.textContent = 'Extension: connected';
        extStatus.className = 'ext-status connected';
      }

      // Meta info
      let meta = '';
      if (data.last_check) meta += 'Last check: ' + data.last_check;
      if (data.source) meta += ' (via ' + data.source + ')';
      metaEl.textContent = meta;

      if (data.changed) {
        dot.className = 'dot changed';
        statusEl.className = 'status-text changed';
        if (!alertShown) {
          banner.classList.add('show');
          alertShown = true;
          try { new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1sbHJ9g4eFh4mIiIeGhYSCf3x5dnRxb21sa2pqa2xtb3J1eHt+gYSGiImJiYmIh4WDgH17eHVzcG5sa2pqamtsbm9ydXh7foGEhoeIiIiIh4aEgn98eXZzcG5sa2ppamtsbW9ydXh7foGEhoeIiIiIh4aEgn98eXZzcG5samppamtsbW9ydXh7foGEhoeIiIiIh4aEgn98eXZzcG5samppamtsbW9ydXh7foGEhoeIiIiIh4aEgn98eXZzcG5samppamtsbW9ydnh7foGEhoeIiIiIh4aEgn98eXZzcG5samppamtsbW9ydXh7fQ==').play(); } catch(e) {}
          if (Notification.permission === 'granted') {
            new Notification('FIFA Ticket Alert!', { body: data.status });
          }
        }
      } else if (!data.last_check) {
        dot.className = 'dot waiting';
        statusEl.className = 'status-text';
      } else if (data.status && data.status.startsWith('Error')) {
        dot.className = 'dot error';
        statusEl.className = 'status-text';
      } else {
        dot.className = 'dot monitoring';
        statusEl.className = 'status-text';
      }
    } catch (e) {
      statusEl.textContent = 'Dashboard connection lost';
      dot.className = 'dot error';
    }
  }

  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }

  setInterval(poll, 3000);
  poll();
</script>
</body>
</html>
""".replace("FIFAURL_PLACEHOLDER", FIFA_URL)

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/reset", methods=["POST"])
def api_reset():
    monitor_state["alert_sent"] = False
    monitor_state["changed"] = False
    monitor_state["status"] = "Reset — monitoring…"
    return jsonify({"ok": True})

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Slack webhook: {'configured' if SLACK_WEBHOOK_URL else 'NOT SET'}")
    print(f"Monitoring: {FIFA_URL}")
    print(f"Check interval: {CHECK_INTERVAL}s\n")

    # Start fallback server-side monitor
    t = threading.Thread(target=fallback_monitor_loop, daemon=True)
    t.start()

    print(f"Dashboard: http://localhost:7777")
    print(f"Load chrome_extension/ in Chrome to enable live tab monitoring.\n")
    app.run(host="0.0.0.0", port=7777, debug=False)
