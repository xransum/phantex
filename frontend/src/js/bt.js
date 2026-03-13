/**
 * BT -- Bluetooth Scanner
 * Polls /bt/data every 2s and updates the device table in place.
 * Pure ES modules, no framework, no dependencies.
 */

const POLL_INTERVAL_MS = 2000;
const STALE_THRESHOLD_MS = 30_000;

/** @type {Map<string, {record: object, lastUpdated: number}>} */
const deviceState = new Map();

// ---------------------------------------------------------------------------
// DOM refs (set after DOMContentLoaded)
// ---------------------------------------------------------------------------
let tbody;
let statusBadge;
let countEl;
let lastScanEl;
let warningEl;
let warningTextEl;

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

  // Update state map
  for (const record of devices) {
    deviceState.set(record.mac, { record, lastUpdated: now });
  }

  // Mark stale entries (present in state but not in this cycle)
  for (const [mac, entry] of deviceState.entries()) {
    if (!incomingMacs.has(mac)) {
      entry.lastUpdated = entry.lastUpdated; // preserve existing time
    }
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

  setStatus("CONNECTING", false);
  poll();
  setInterval(poll, POLL_INTERVAL_MS);
});
