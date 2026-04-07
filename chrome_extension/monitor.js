/**
 * FIFA Ticket Monitor — Content Script
 *
 * Runs on the FIFA ticket page. Reads the visible page text and
 * POSTs it to the local Flask dashboard for analysis.
 * Reports more frequently when a countdown is detected.
 */

const REPORT_URL = "http://localhost:7777/api/page-content";
const NORMAL_INTERVAL = 10_000;    // 10s normally
const COUNTDOWN_INTERVAL = 3_000;  // 3s when countdown detected

let currentInterval = NORMAL_INTERVAL;
let intervalId = null;

function getPageText() {
  return document.body ? document.body.innerText : "";
}

/**
 * Parse countdown from the FIFA page text.
 *
 * The page shows:
 *   "You will be able to enter in...."
 *   "11:50"
 *   "min."
 *   "sec."
 *
 * Or just seconds:
 *   "15"
 *   "sec."
 */
function parseCountdown(text) {
  // Check if page has the "enter in" indicator
  if (!text.toLowerCase().includes("enter in")) {
    return null;
  }

  // Split into lines and look for the countdown value
  const lines = text.split("\n").map(l => l.trim()).filter(Boolean);

  for (let i = 0; i < lines.length; i++) {
    // Look for MM:SS pattern (e.g., "11:50", "01:03")
    const mmssMatch = lines[i].match(/^(\d{1,3}):(\d{2})$/);
    if (mmssMatch) {
      const mins = parseInt(mmssMatch[1], 10);
      const secs = parseInt(mmssMatch[2], 10);
      return mins * 60 + secs;
    }

    // Look for standalone number followed by "sec." or "min." on next lines
    const numMatch = lines[i].match(/^(\d{1,4})$/);
    if (numMatch) {
      const val = parseInt(numMatch[1], 10);
      // Check if next line says "sec." or "min."
      const nextLine = (lines[i + 1] || "").toLowerCase();
      if (nextLine.startsWith("sec")) {
        return val; // it's seconds
      }
      if (nextLine.startsWith("min")) {
        return val * 60; // it's minutes
      }
      // If the number is reasonable for a countdown (< 7200), treat as seconds
      if (val < 7200) {
        return val;
      }
    }
  }

  return null;
}

/**
 * Try to extract queue progress percentage from the circular progress bar.
 * Inspects the DOM for SVG circles, CSS gradients, aria attributes, etc.
 * Returns a number 0-100, or null if not found.
 */
function parseQueueProgress() {
  // Primary: look for the FIFA progress-arc SVG circle by ID
  const progressArc = document.getElementById("progress-arc");
  if (progressArc) {
    const da = parseFloat(progressArc.getAttribute("stroke-dasharray"));
    const doff = parseFloat(progressArc.getAttribute("stroke-dashoffset"));
    if (da > 0 && !isNaN(doff)) {
      const progress = ((da - Math.abs(doff)) / da) * 100;
      return Math.round(progress * 10) / 10;
    }
  }

  // Fallback: look for SVG circles with non-zero dashoffset (skip background circles)
  const circles = document.querySelectorAll("svg circle");
  for (const circle of circles) {
    const da = parseFloat(circle.getAttribute("stroke-dasharray"));
    const doff = parseFloat(circle.getAttribute("stroke-dashoffset"));
    // Skip background circles (offset=0 means full circle, not progress)
    if (da > 0 && !isNaN(doff) && Math.abs(doff) > 0) {
      const progress = ((da - Math.abs(doff)) / da) * 100;
      if (progress >= 0 && progress <= 100) return Math.round(progress * 10) / 10;
    }
  }

  // Fallback: aria-valuenow
  const ariaEls = document.querySelectorAll('[aria-valuenow], [role="progressbar"]');
  for (const el of ariaEls) {
    const val = parseFloat(el.getAttribute("aria-valuenow"));
    if (!isNaN(val) && val >= 0 && val <= 100) return val;
  }

  return null;
}

/**
 * Collect raw DOM data about progress elements for server-side debugging.
 */
function getProgressDebugInfo() {
  const info = [];

  // SVG circles
  const circles = document.querySelectorAll("svg circle");
  circles.forEach((c, i) => {
    const style = window.getComputedStyle(c);
    info.push({
      type: "svg-circle",
      index: i,
      r: c.getAttribute("r"),
      strokeDasharray: c.getAttribute("stroke-dasharray") || style.strokeDasharray,
      strokeDashoffset: c.getAttribute("stroke-dashoffset") || style.strokeDashoffset,
      stroke: c.getAttribute("stroke") || style.stroke,
      transform: c.getAttribute("transform") || style.transform,
    });
  });

  // Progress elements
  const progressEls = document.querySelectorAll("progress, [role='progressbar']");
  progressEls.forEach((el, i) => {
    info.push({
      type: "progress-el",
      index: i,
      value: el.getAttribute("value"),
      max: el.getAttribute("max"),
      ariaValueNow: el.getAttribute("aria-valuenow"),
      ariaValueMax: el.getAttribute("aria-valuemax"),
    });
  });

  return info;
}

/**
 * Get a full HTML snapshot of key elements for server-side analysis.
 * Captures SVG elements, style attributes, and progress-related DOM.
 */
function getDomSnapshot() {
  const snapshot = [];

  // All SVGs
  document.querySelectorAll("svg").forEach((svg, i) => {
    snapshot.push({ type: "svg", index: i, outerHTML: svg.outerHTML.substring(0, 2000) });
  });

  // Elements with style containing "gradient" or "progress"
  document.querySelectorAll("[style]").forEach((el) => {
    const s = el.getAttribute("style") || "";
    if (s.includes("gradient") || s.includes("progress") || s.includes("stroke") || s.includes("rotate") || s.includes("dash")) {
      snapshot.push({ type: "styled-el", tag: el.tagName, style: s.substring(0, 500) });
    }
  });

  // Canvas elements
  document.querySelectorAll("canvas").forEach((c, i) => {
    snapshot.push({ type: "canvas", index: i, width: c.width, height: c.height });
  });

  return snapshot.length > 0 ? snapshot : null;
}

async function report() {
  const text = getPageText();
  const url = window.location.href;
  const countdownSeconds = parseCountdown(text);
  const queueProgress = parseQueueProgress();
  const progressDebug = queueProgress === null ? getProgressDebugInfo() : null;
  const domSnapshot = queueProgress === null ? getDomSnapshot() : null;

  // Speed up reporting when countdown is active
  const hasCountdown = countdownSeconds !== null;
  const desiredInterval = hasCountdown ? COUNTDOWN_INTERVAL : NORMAL_INTERVAL;
  if (desiredInterval !== currentInterval) {
    currentInterval = desiredInterval;
    clearInterval(intervalId);
    intervalId = setInterval(report, currentInterval);
    console.log(`[FIFA Monitor] Interval changed to ${currentInterval / 1000}s (countdown: ${countdownSeconds}s)`);
  }

  try {
    await fetch(REPORT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        url,
        countdown_seconds: countdownSeconds,
        queue_progress: queueProgress,
        progress_debug: progressDebug,
        dom_snapshot: domSnapshot,
      }),
    });
  } catch (e) {
    // Dashboard might not be running — silently ignore
  }
}

// Report immediately, then on interval
report();
intervalId = setInterval(report, currentInterval);

// Also report on any significant DOM change (page transitions)
const observer = new MutationObserver(() => {
  clearTimeout(observer._timer);
  observer._timer = setTimeout(report, 1500);
});
observer.observe(document.body || document.documentElement, {
  childList: true,
  subtree: true,
  characterData: true,
});

console.log("[FIFA Monitor] Content script active — reporting to dashboard.");
