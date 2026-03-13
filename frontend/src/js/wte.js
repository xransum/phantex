/**
 * WTE -- Wireless Terminal Explorer
 * Polls /wte/data every 10s and updates the network table in place.
 * Pure ES modules, no framework, no dependencies.
 */

const POLL_INTERVAL_MS = 10000;
const STALE_THRESHOLD_MS = 60_000;
const LOG_MAX_ENTRIES = 100;

/** @type {Map<string, {record: object, lastUpdated: number}>} */
const networkState = new Map();

/**
 * JS-side set of every BSSID seen this session (page lifetime only).
 * Drives the SEEN counter -- does not reset between polls.
 * @type {Set<string>}
 */
const historyState = new Set();

/**
 * Last-fetched history rows, kept so re-sorting does not require a new fetch.
 * @type {Array<object>}
 */
let _historyRows = [];

/**
 * Sort state for the live network table.
 * col: field name or null for default (newest first).
 * @type {{ col: string|null, dir: string|null }}
 */
const liveSort = { col: null, dir: null };

/**
 * Sort state for the history modal table.
 * @type {{ col: string|null, dir: string|null }}
 */
const historySort = { col: null, dir: null };

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
    const res = await fetch("/wte/data");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    render(data);
  } catch (err) {
    setStatus("ERROR", false);
    appendLog(`poll failed: ${err.message}`, "log-error");
    console.error("[WTE] poll failed:", err);
  }
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

/**
 * @param {{ networks: object[], scan_warning: string|null, last_scan: string|null }} data
 */
function render(data) {
  const { networks, scan_warning, last_scan } = data;
  const now = Date.now();

  setStatus("SCANNING", true);
  countEl.textContent = networks.length;

  if (last_scan) {
    lastScanEl.textContent = new Date(last_scan).toLocaleTimeString();
  }

  if (scan_warning) {
    warningTextEl.textContent = scan_warning;
    warningEl.classList.remove("hidden");
  } else {
    warningEl.classList.add("hidden");
  }

  const incomingBssids = new Set(networks.map((n) => n.bssid));

  for (const record of networks) {
    if (!networkState.has(record.bssid)) {
      const label = record.ssid && record.ssid !== "[hidden]"
        ? `${record.ssid} (${record.bssid})`
        : record.bssid;
      appendLog(
        `new network: ${label} ch=${record.channel ?? "--"} signal=${record.signal ?? "--"} ${record.security ?? "open"}`,
        "log-new",
      );
    }
    if (!historyState.has(record.bssid)) {
      historyState.add(record.bssid);
      updateSeenCount();
    }
  }

  for (const record of networks) {
    networkState.set(record.bssid, { record, lastUpdated: now });
  }

  for (const [bssid, entry] of networkState.entries()) {
    if (!incomingBssids.has(bssid)) {
      const wasRecent = now - entry.lastUpdated <= STALE_THRESHOLD_MS;
      const isNowStale = now - entry.lastUpdated > STALE_THRESHOLD_MS;
      if (wasRecent && isNowStale) {
        const label = entry.record.ssid && entry.record.ssid !== "[hidden]"
          ? `${entry.record.ssid} (${bssid})`
          : bssid;
        appendLog(`network stale: ${label}`, "log-stale");
      }
    }
  }

  if (networks.length > 0) {
    appendLog(`scan complete: ${networks.length} network(s) visible`);
  } else {
    appendLog("scan complete: no networks found");
  }

  updateTable(now);
}

/**
 * Diff networkState against the current tbody rows and update in place.
 * @param {number} now
 */
function updateTable(now) {
  if (networkState.size === 0) {
    tbody.innerHTML = `
      <tr class="empty-row">
        <td colspan="7">SCANNING... AWAITING FIRST RESULT</td>
      </tr>`;
    return;
  }

  /** @type {Map<string, HTMLTableRowElement>} */
  const existingRows = new Map();
  for (const row of tbody.querySelectorAll("tr[data-bssid]")) {
    existingRows.set(row.dataset.bssid, row);
  }

  const emptyRow = tbody.querySelector(".empty-row");
  if (emptyRow) emptyRow.remove();

  const sorted = [...networkState.entries()].sort((a, b) => {
    if (liveSort.col) {
      return compareRecords(a[1].record, b[1].record, liveSort.col, liveSort.dir);
    }
    return b[1].lastUpdated - a[1].lastUpdated;
  });

  for (const [bssid, { record, lastUpdated }] of sorted) {
    const isStale = now - lastUpdated > STALE_THRESHOLD_MS;
    let row = existingRows.get(bssid);

    if (!row) {
      row = document.createElement("tr");
      row.dataset.bssid = bssid;
      row.classList.add("row-new");
      row.addEventListener("animationend", () => row.classList.remove("row-new"), { once: true });
      tbody.appendChild(row);
    }

    row.classList.toggle("row-stale", isStale);
    row.innerHTML = buildRowCells(record);
    existingRows.delete(bssid);
  }

  for (const [, staleRow] of existingRows) {
    staleRow.remove();
  }
}

/**
 * @param {object} record
 * @returns {string}
 */
function buildRowCells(record) {
  const signal = record.signal != null ? `${record.signal}%` : "--";
  const security = record.security || "open";
  const firstSeen = formatTime(record.first_seen);
  const lastSeen = formatTime(record.last_seen);

  return `
    <td>${escHtml(record.ssid)}</td>
    <td>${escHtml(record.bssid)}</td>
    <td>${record.channel != null ? escHtml(String(record.channel)) : "--"}</td>
    <td>${escHtml(signal)}</td>
    <td>${escHtml(security)}</td>
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
    const res = await fetch("/wte/history");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload = await res.json();
    _historyRows = payload.networks || [];
    renderHistoryRows(_historyRows);
  } catch (err) {
    historyTbody.innerHTML = `<tr class="empty-row"><td colspan="7" style="color:var(--red)">ERROR: ${escHtml(err.message)}</td></tr>`;
  }
}

/**
 * @param {Array<object>} rows - source rows (unsorted original order preserved)
 */
function renderHistoryRows(rows) {
  if (!rows.length) {
    historyTbody.innerHTML = `<tr class="empty-row"><td colspan="7">NO HISTORY YET</td></tr>`;
    return;
  }
  const display = historySort.col
    ? [...rows].sort((a, b) => compareRecords(a, b, historySort.col, historySort.dir))
    : rows;
  historyTbody.innerHTML = display.map((r) => {
    const signal = r.signal != null ? `${r.signal}%` : "--";
    const security = r.security || "open";
    return `<tr>
      <td>${escHtml(r.ssid)}</td>
      <td>${escHtml(r.bssid)}</td>
      <td>${r.channel != null ? escHtml(String(r.channel)) : "--"}</td>
      <td>${escHtml(signal)}</td>
      <td>${escHtml(security)}</td>
      <td>${escHtml(formatTime(r.first_seen))}</td>
      <td>${escHtml(formatTime(r.last_seen))}</td>
    </tr>`;
  }).join("");
}

async function clearHistory() {
  try {
    const res = await fetch("/wte/history/clear", { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    historyState.clear();
    _historyRows = [];
    updateSeenCount();
    historyTbody.innerHTML = `<tr class="empty-row"><td colspan="7">NO HISTORY YET</td></tr>`;
    appendLog("network history cleared", "log-warn");
  } catch (err) {
    appendLog(`clear history failed: ${err.message}`, "log-error");
  }
}

// ---------------------------------------------------------------------------
// Log panel
// ---------------------------------------------------------------------------

/**
 * @param {string} msg
 * @param {string} [cls]
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

  while (logBody.children.length > LOG_MAX_ENTRIES) {
    logBody.removeChild(logBody.firstChild);
  }

  logBody.scrollTop = logBody.scrollHeight;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Compare two records on a given field for sorting.
 * Nulls sort last regardless of direction.
 * @param {object} a
 * @param {object} b
 * @param {string} col
 * @param {'asc'|'desc'} dir
 * @returns {number}
 */
function compareRecords(a, b, col, dir) {
  let av = a[col] != null ? a[col] : null;
  let bv = b[col] != null ? b[col] : null;

  if (av === null && bv === null) return 0;
  if (av === null) return 1;
  if (bv === null) return -1;

  if (col === "signal" || col === "channel") {
    av = Number(av);
    bv = Number(bv);
  }

  let cmp;
  if (typeof av === "number" && typeof bv === "number") {
    cmp = av - bv;
  } else {
    cmp = String(av).localeCompare(String(bv));
  }

  return dir === "desc" ? -cmp : cmp;
}

/**
 * Cycle: null -> 'asc' -> 'desc' -> null
 * @param {string|null} current
 * @returns {string|null}
 */
function cycleDir(current) {
  if (current === null) return "asc";
  if (current === "asc") return "desc";
  return null;
}

/**
 * Wire sort-click listeners to all th[data-col] inside a thead.
 * @param {HTMLTableElement} table
 * @param {{ col: string|null, dir: string|null }} sortState
 * @param {function} rerender
 */
function wireSortHeaders(table, sortState, rerender) {
  const headers = table.querySelectorAll("thead th[data-col]");
  headers.forEach((th) => {
    th.addEventListener("click", () => {
      const col = th.dataset.col;
      if (sortState.col === col) {
        sortState.dir = cycleDir(sortState.dir);
        if (sortState.dir === null) sortState.col = null;
      } else {
        sortState.col = col;
        sortState.dir = "asc";
      }
      headers.forEach((h) => {
        if (h.dataset.col === sortState.col) {
          h.setAttribute("aria-sort", sortState.dir === "asc" ? "ascending" : "descending");
        } else {
          h.removeAttribute("aria-sort");
        }
      });
      rerender();
    });
  });
}

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
  tbody = document.getElementById("wte-tbody");
  statusBadge = document.getElementById("wte-status");
  countEl = document.getElementById("wte-count");
  lastScanEl = document.getElementById("wte-last-scan");
  warningEl = document.getElementById("wte-warning");
  warningTextEl = document.getElementById("wte-warning-text");
  logBody = document.getElementById("wte-log-body");
  seenCountEl = document.getElementById("wte-seen-count");
  historyModal = document.getElementById("wte-history-modal");
  historyTbody = document.getElementById("wte-history-tbody");

  const clearBtn = document.getElementById("wte-log-clear");
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      if (logBody) logBody.innerHTML = "";
    });
  }

  const historyOpenBtn = document.getElementById("wte-history-open");
  if (historyOpenBtn) historyOpenBtn.addEventListener("click", openHistoryModal);

  const historyCloseBtn = document.getElementById("wte-history-close");
  if (historyCloseBtn) historyCloseBtn.addEventListener("click", closeHistoryModal);

  const historyClearBtn = document.getElementById("wte-history-clear");
  if (historyClearBtn) historyClearBtn.addEventListener("click", clearHistory);

  if (historyModal) {
    historyModal.addEventListener("click", (e) => {
      if (e.target === historyModal) closeHistoryModal();
    });
  }

  const liveTable = document.getElementById("wte-table");
  if (liveTable) {
    wireSortHeaders(liveTable, liveSort, () => updateTable(Date.now()));
  }

  const historyTable = document.getElementById("wte-history-table");
  if (historyTable) {
    wireSortHeaders(historyTable, historySort, () => renderHistoryRows(_historyRows));
  }

  appendLog("scanner initializing...");
  setStatus("CONNECTING", false);
  poll();
  setInterval(poll, POLL_INTERVAL_MS);
});
