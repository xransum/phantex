/**
 * BT -- Bluetooth Scanner
 * Polls /bt/data every 2s and updates the device table in place.
 * Pure ES modules, no framework, no dependencies.
 */

const POLL_INTERVAL_MS = 2000;
const STALE_THRESHOLD_MS = 30_000;
const LOG_MAX_ENTRIES = 100;

/** @type {Map<string, {record: object, lastUpdated: number}>} */
const deviceState = new Map();

/**
 * JS-side set of every MAC seen this session (page lifetime only).
 * Drives the SEEN counter -- does not reset between polls.
 * @type {Set<string>}
 */
const historyState = new Set();

// ---------------------------------------------------------------------------
// DOM refs (set after DOMContentLoaded)
// ---------------------------------------------------------------------------
let tbody;
let statusBadge;
let countEl;
let lastScanEl;
let warningEl;
let warningTextEl;
let logBody;
let seenCountEl;
let historyModal;
let historyTbody;

// ---------------------------------------------------------------------------
// Polling
// ---------------------------------------------------------------------------

async function poll() {
  try {
    const res = await fetch("/bt/data");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    render(data);
  } catch (err) {
    setStatus("ERROR", false);
    appendLog(`poll failed: ${err.message}`, "log-error");
    console.error("[BT] poll failed:", err);
  }
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

/**
 * @param {{ devices: object[], scan_warning: string|null, last_scan: string|null }} data
 */
function render(data) {
  const { devices, scan_warning, last_scan } = data;
  const now = Date.now();

  // Status badge
  setStatus("SCANNING", true);

  // Device count
  countEl.textContent = devices.length;

  // Last scan timestamp
  if (last_scan) {
    const d = new Date(last_scan);
    lastScanEl.textContent = d.toLocaleTimeString();
  }

  // Warning banner
  if (scan_warning) {
    warningTextEl.textContent = scan_warning;
    warningEl.classList.remove("hidden");

    // If classic BT failed, reflect that in mode label
    const modeEl = document.getElementById("bt-mode");
    if (modeEl && scan_warning.toLowerCase().includes("classic")) {
      modeEl.textContent = "BLE ONLY";
    }
  } else {
    warningEl.classList.add("hidden");
  }

  // Track which MACs came in this cycle
  const incomingMacs = new Set(devices.map((d) => d.mac));

  // Detect new devices before updating state
  for (const record of devices) {
    if (!deviceState.has(record.mac)) {
      const label = record.name && record.name !== "Unknown"
        ? `${record.name} (${record.mac})`
        : record.mac;
      appendLog(`new device: ${label} [${record.device_type}]${record.rssi != null ? ` rssi=${record.rssi} dBm` : ""}`, "log-new");
    }
    // Track in session history set
    if (!historyState.has(record.mac)) {
      historyState.add(record.mac);
      updateSeenCount();
    }
  }

  // Update state map
  for (const record of devices) {
    deviceState.set(record.mac, { record, lastUpdated: now });
  }

  // Mark stale entries (present in state but not in this cycle)
  for (const [mac, entry] of deviceState.entries()) {
    if (!incomingMacs.has(mac)) {
      const wasRecent = now - entry.lastUpdated <= STALE_THRESHOLD_MS;
      const isNowStale = now - entry.lastUpdated > STALE_THRESHOLD_MS;
      if (wasRecent && isNowStale) {
        const label = entry.record.name && entry.record.name !== "Unknown"
          ? `${entry.record.name} (${mac})`
          : mac;
        appendLog(`device stale: ${label}`, "log-stale");
      }
      entry.lastUpdated = entry.lastUpdated; // preserve existing time
    }
  }

  // Log scan summary
  if (devices.length > 0) {
    appendLog(`scan complete: ${devices.length} device(s) visible`);
  } else {
    appendLog("scan complete: no devices found");
  }

  updateTable(now);
}

/**
 * Diff deviceState against the current tbody rows and update in place.
 * @param {number} now
 */
function updateTable(now) {
  if (deviceState.size === 0) {
    tbody.innerHTML = `
      <tr class="empty-row">
        <td colspan="7">SCANNING... AWAITING FIRST RESULT</td>
      </tr>`;
    return;
  }

  // Build a map of existing rows by MAC for diffing
  /** @type {Map<string, HTMLTableRowElement>} */
  const existingRows = new Map();
  for (const row of tbody.querySelectorAll("tr[data-mac]")) {
    existingRows.set(row.dataset.mac, row);
  }

  // Remove the empty placeholder row if present
  const emptyRow = tbody.querySelector(".empty-row");
  if (emptyRow) emptyRow.remove();

  // Sort devices: newest last_seen first
  const sorted = [...deviceState.entries()].sort(
    (a, b) => b[1].lastUpdated - a[1].lastUpdated
  );

  for (const [mac, { record, lastUpdated }] of sorted) {
    const isStale = now - lastUpdated > STALE_THRESHOLD_MS;
    let row = existingRows.get(mac);

    if (!row) {
      row = document.createElement("tr");
      row.dataset.mac = mac;
      row.classList.add("row-new");
      // Remove the animation class after it plays so re-appearing rows
      // can animate again.
      row.addEventListener("animationend", () => row.classList.remove("row-new"), {
        once: true,
      });
      tbody.appendChild(row);
    }

    row.classList.toggle("row-stale", isStale);
    row.innerHTML = buildRowCells(record);

    // Remove from existingRows so we know what to prune at the end
    existingRows.delete(mac);
  }

  // Prune rows for MACs that have been evicted from deviceState
  for (const [, staleRow] of existingRows) {
    staleRow.remove();
  }
}

/**
 * @param {object} record
 * @returns {string}
 */
function buildRowCells(record) {
  const typeClass = record.device_type === "BLE" ? "type-ble" : "type-classic";
  const rssi = record.rssi != null ? `${record.rssi} dBm` : "--";
  const deviceClass = record.device_class || "--";
  const firstSeen = formatTime(record.first_seen);
  const lastSeen = formatTime(record.last_seen);

  return `
    <td>${escHtml(record.mac)}</td>
    <td>${escHtml(record.name)}</td>
    <td class="${typeClass}">${escHtml(record.device_type)}</td>
    <td>${escHtml(rssi)}</td>
    <td>${escHtml(deviceClass)}</td>
    <td>${escHtml(firstSeen)}</td>
    <td>${escHtml(lastSeen)}</td>
  `;
}

// ---------------------------------------------------------------------------
// History modal
// ---------------------------------------------------------------------------

function updateSeenCount() {
  if (seenCountEl) seenCountEl.textContent = historyState.size;
}

async function openHistoryModal() {
  historyModal.classList.remove("hidden");
  await loadHistory();
}

function closeHistoryModal() {
  historyModal.classList.add("hidden");
}

async function loadHistory() {
  if (!historyTbody) return;
  historyTbody.innerHTML = `<tr class="empty-row"><td colspan="7">LOADING...</td></tr>`;
  try {
    const res = await fetch("/bt/history");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload = await res.json();
    renderHistoryRows(payload.devices || []);
  } catch (err) {
    historyTbody.innerHTML = `<tr class="empty-row"><td colspan="7" style="color:var(--red)">ERROR: ${escHtml(err.message)}</td></tr>`;
  }
}

/**
 * @param {Array<object>} rows
 */
function renderHistoryRows(rows) {
  if (!rows.length) {
    historyTbody.innerHTML = `<tr class="empty-row"><td colspan="7">NO HISTORY YET</td></tr>`;
    return;
  }
  historyTbody.innerHTML = rows.map((r) => {
    const typeClass = r.device_type === "BLE" ? "type-ble" : "type-classic";
    const rssi = r.rssi != null ? `${r.rssi} dBm` : "--";
    const dc = r.device_class || "--";
    return `<tr>
      <td>${escHtml(r.mac)}</td>
      <td>${escHtml(r.name)}</td>
      <td class="${typeClass}">${escHtml(r.device_type)}</td>
      <td>${escHtml(rssi)}</td>
      <td>${escHtml(dc)}</td>
      <td>${escHtml(formatTime(r.first_seen))}</td>
      <td>${escHtml(formatTime(r.last_seen))}</td>
    </tr>`;
  }).join("");
}

async function clearHistory() {
  try {
    const res = await fetch("/bt/history/clear", { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    historyState.clear();
    updateSeenCount();
    historyTbody.innerHTML = `<tr class="empty-row"><td colspan="7">NO HISTORY YET</td></tr>`;
    appendLog("device history cleared", "log-warn");
  } catch (err) {
    appendLog(`clear history failed: ${err.message}`, "log-error");
  }
}

// ---------------------------------------------------------------------------
// Log panel
// ---------------------------------------------------------------------------

/**
 * Append a line to the scan log panel.
 * @param {string} msg
 * @param {string} [cls] - optional extra CSS class (log-new, log-stale, log-error, log-warn)
 */
function appendLog(msg, cls) {
  if (!logBody) return;

  const now = new Date().toLocaleTimeString();
  const entry = document.createElement("div");
  entry.className = "bt-log-entry";

  const timeSpan = document.createElement("span");
  timeSpan.className = "bt-log-time";
  timeSpan.textContent = now;

  const msgSpan = document.createElement("span");
  msgSpan.className = cls ? `bt-log-msg ${cls}` : "bt-log-msg";
  msgSpan.textContent = msg;

  entry.appendChild(timeSpan);
  entry.appendChild(msgSpan);
  logBody.appendChild(entry);

  // Trim to max entries
  while (logBody.children.length > LOG_MAX_ENTRIES) {
    logBody.removeChild(logBody.firstChild);
  }

  // Auto-scroll to bottom
  logBody.scrollTop = logBody.scrollHeight;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * @param {string} label
 * @param {boolean} active
 */
function setStatus(label, active) {
  statusBadge.textContent = label;
  statusBadge.classList.toggle("scanning", active);
}

/**
 * @param {string|null} iso
 * @returns {string}
 */
function formatTime(iso) {
  if (!iso) return "--";
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}

/**
 * Minimal HTML escape to prevent XSS from device names/MACs.
 * @param {string} str
 * @returns {string}
 */
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  tbody = document.getElementById("bt-tbody");
  statusBadge = document.getElementById("bt-status");
  countEl = document.getElementById("bt-count");
  lastScanEl = document.getElementById("bt-last-scan");
  warningEl = document.getElementById("bt-warning");
  warningTextEl = document.getElementById("bt-warning-text");
  logBody = document.getElementById("bt-log-body");
  seenCountEl = document.getElementById("bt-seen-count");
  historyModal = document.getElementById("bt-history-modal");
  historyTbody = document.getElementById("bt-history-tbody");

  const clearBtn = document.getElementById("bt-log-clear");
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      if (logBody) logBody.innerHTML = "";
    });
  }

  const historyOpenBtn = document.getElementById("bt-history-open");
  if (historyOpenBtn) historyOpenBtn.addEventListener("click", openHistoryModal);

  const historyCloseBtn = document.getElementById("bt-history-close");
  if (historyCloseBtn) historyCloseBtn.addEventListener("click", closeHistoryModal);

  const historyClearBtn = document.getElementById("bt-history-clear");
  if (historyClearBtn) historyClearBtn.addEventListener("click", clearHistory);

  // Close modal on overlay click
  if (historyModal) {
    historyModal.addEventListener("click", (e) => {
      if (e.target === historyModal) closeHistoryModal();
    });
  }

  appendLog("scanner initializing...");
  setStatus("CONNECTING", false);
  poll();
  setInterval(poll, POLL_INTERVAL_MS);
});
