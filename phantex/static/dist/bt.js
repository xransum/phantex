//#region frontend/src/js/bt.js
/**
* BT -- Bluetooth Scanner
* Polls /bt/data every 2s and updates the device table in place.
* Pure ES modules, no framework, no dependencies.
*/
var POLL_INTERVAL_MS = 2e3;
var STALE_THRESHOLD_MS = 3e4;
/** @type {Map<string, {record: object, lastUpdated: number}>} */
var deviceState = /* @__PURE__ */ new Map();
var tbody;
var statusBadge;
var countEl;
var lastScanEl;
var warningEl;
var warningTextEl;
async function poll() {
	try {
		const res = await fetch("/bt/data");
		if (!res.ok) throw new Error(`HTTP ${res.status}`);
		render(await res.json());
	} catch (err) {
		setStatus("ERROR", false);
		console.error("[BT] poll failed:", err);
	}
}
/**
* @param {{ devices: object[], scan_warning: string|null, last_scan: string|null }} data
*/
function render(data) {
	const { devices, scan_warning, last_scan } = data;
	const now = Date.now();
	setStatus("SCANNING", true);
	countEl.textContent = devices.length;
	if (last_scan) lastScanEl.textContent = new Date(last_scan).toLocaleTimeString();
	if (scan_warning) {
		warningTextEl.textContent = scan_warning;
		warningEl.classList.remove("hidden");
		const modeEl = document.getElementById("bt-mode");
		if (modeEl && scan_warning.toLowerCase().includes("classic")) modeEl.textContent = "BLE ONLY";
	} else warningEl.classList.add("hidden");
	const incomingMacs = new Set(devices.map((d) => d.mac));
	for (const record of devices) deviceState.set(record.mac, {
		record,
		lastUpdated: now
	});
	for (const [mac, entry] of deviceState.entries()) if (!incomingMacs.has(mac)) entry.lastUpdated = entry.lastUpdated;
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
	/** @type {Map<string, HTMLTableRowElement>} */
	const existingRows = /* @__PURE__ */ new Map();
	for (const row of tbody.querySelectorAll("tr[data-mac]")) existingRows.set(row.dataset.mac, row);
	const emptyRow = tbody.querySelector(".empty-row");
	if (emptyRow) emptyRow.remove();
	const sorted = [...deviceState.entries()].sort((a, b) => b[1].lastUpdated - a[1].lastUpdated);
	for (const [mac, { record, lastUpdated }] of sorted) {
		const isStale = now - lastUpdated > STALE_THRESHOLD_MS;
		let row = existingRows.get(mac);
		if (!row) {
			row = document.createElement("tr");
			row.dataset.mac = mac;
			row.classList.add("row-new");
			row.addEventListener("animationend", () => row.classList.remove("row-new"), { once: true });
			tbody.appendChild(row);
		}
		row.classList.toggle("row-stale", isStale);
		row.innerHTML = buildRowCells(record);
		existingRows.delete(mac);
	}
	for (const [, staleRow] of existingRows) staleRow.remove();
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
	return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
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
//#endregion
