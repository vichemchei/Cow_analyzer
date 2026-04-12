/* ═══════════════════════════════════════════════════════════
   HerdWatch — app.js
   Full API integration with all Flask endpoints.
   Endpoints used:
     GET  /api/health        → check if backend is running
     GET  /analysis/status    → poll every 5s
     GET  /analysis/log       → load frame log
     POST /test               → AI chat
     POST /send               → send SMS (use_ai toggle)
     GET  /conversations      → load all threads
     POST /conversations/clear→ wipe history
═══════════════════════════════════════════════════════════ */

"use strict";

// ─── Configuration ───────────────────────────────────────────
const API_BASE = window.location.origin;  // Use same origin as frontend
const POLL_INTERVAL = 5000;    // ms between status polls
const LOG_POLL_INTERVAL = 15000;

// ─── Debug logging ───────────────────────────────────────────
const debug = {
  log: (msg, data) => {
    console.log(`[HerdWatch] ${msg}`, data || "");
  },
  error: (msg, err) => {
    console.error(`[HerdWatch ERROR] ${msg}`, err || "");
  },
  warn: (msg, data) => {
    console.warn(`[HerdWatch WARN] ${msg}`, data || "");
  },
};

// ─── State ───────────────────────────────────────────────────
const state = {
  analysisStatus: null,
  logEntries: [],
  backendHealthy: false,
  herd: [
    { id: "COW-001", name: "Lewis", status: "eating", detail: "Eating hay consistently", tag: null },
    { id: "COW-002", name: "Cow 2", status: "eating", detail: "Eating hay", tag: null },
    { id: "COW-003", name: "Cow 3", status: "eating", detail: "Eating hay", tag: null },
    { id: "COW-004", name: "Cow 4", status: "eating", detail: "Eating hay", tag: null },
    { id: "COW-005", name: "Cow 5", status: "eating", detail: "Eating hay", tag: null },
    { id: "COW-006", name: "Cow 6", status: "eating", detail: "Eating hay", tag: null },
    { id: "COW-007", name: "Cow 7", status: "eating", detail: "Eating hay", tag: null },
    { id: "COW-600", name: "Cow #600", status: "eating", detail: "Tag 600 · Black & white", tag: "600" },
  ],
  conversations: {},
  chartData: [],
  recentSends: [],
  herdFilter: "all",
  chatIsLoading: false,
};

// ─── API helpers ──────────────────────────────────────────────
async function apiGet(path) {
  try {
    debug.log(`GET ${path}`);
    const r = await fetch(API_BASE + path);
    if (!r.ok) {
      debug.error(`GET ${path} failed: ${r.status}`, r.statusText);
      throw new Error(`GET ${path} → ${r.status} ${r.statusText}`);
    }
    const json = await r.json();
    debug.log(`GET ${path} success`, json);
    return json;
  } catch (e) {
    debug.error(`apiGet(${path})`, e);
    throw e;
  }
}

async function apiPost(path, body) {
  try {
    debug.log(`POST ${path}`, body);
    const r = await fetch(API_BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      debug.error(`POST ${path} failed: ${r.status}`, r.statusText);
      throw new Error(`POST ${path} → ${r.status}`);
    }
    const json = await r.json();
    debug.log(`POST ${path} success`, json);
    return json;
  } catch (e) {
    debug.error(`apiPost(${path})`, e);
    throw e;
  }
}

// ─── Toast ────────────────────────────────────────────────────
let toastTimer;
function showToast(msg, type = "") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = `toast show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = "toast"; }, 3500);
}

// ─── Clock ────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  document.getElementById("clock").textContent =
    now.toLocaleTimeString("en-GB", { hour12: false });
}
setInterval(updateClock, 1000);
updateClock();

// ─── View routing ─────────────────────────────────────────────
const viewMeta = {
  dashboard: { title: "Dashboard", crumb: "Overview · Live" },
  "video-source": { title: "Video Source", crumb: "Upload · Webcam · Processing" },
  analysis: { title: "AI Analysis", crumb: "Azure OpenAI · Frame Log" },
  herd: { title: "Herd", crumb: "Individual Cows · Status" },
  chat: { title: "AI Chat", crumb: "Azure OpenAI · Farmer Assistant" },
  sms: { title: "SMS Center", crumb: "Africa's Talking · Compose" },
  conversations: { title: "Conversations", crumb: "SMS · Incoming Threads" },
};

function setView(name, btn) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));

  const el = document.getElementById(`view-${name}`);
  if (el) el.classList.add("active");
  if (btn) btn.classList.add("active");

  const meta = viewMeta[name] || {};
  document.getElementById("viewTitle").textContent = meta.title || name;
  document.getElementById("breadcrumb").textContent = meta.crumb || "";

  // Trigger data loads on view switch
  if (name === "video-source") loadVideoSourceView();
  if (name === "analysis") loadAnalysisLog();
  if (name === "conversations") loadConversations();
  if (name === "herd") {
    loadHerdData().then(() => renderHerdCards());
  }
  if (name === "dashboard") {
    loadHerdData().then(() => renderMiniHerd());
  }
}

// ─── GET /analysis/status  (polled) ──────────────────────────
async function pollAnalysisStatus() {
  try {
    const data = await apiGet("/analysis/status");
    state.analysisStatus = data;
    updateStatusUI(data);
  } catch (e) {
    updateStatusUI({ status: "disconnected", analysis: "Backend unreachable", frame_count: 0, timestamp: null });
  }
}

function updateStatusUI(d) {
  const { status, analysis, frame_count, timestamp } = d;

  // Sidebar dot
  const dot = document.getElementById("ssDot");
  dot.className = `ss-dot ${status}`;
  document.getElementById("ssVal").textContent = status;
  document.getElementById("sidebarFrame").textContent = frame_count ? frame_count.toLocaleString() : "—";

  // Topbar stats
  const cowMatch = analysis ? analysis.match(/(\d+)\s+cow/i) : null;
  const cowCount = cowMatch ? cowMatch[1] : "—";
  document.getElementById("tbCowVal").textContent = cowCount;
  document.getElementById("tbEatVal").textContent =
    (analysis && analysis.toLowerCase().includes("eating")) ? "✓" : "—";

  // Dashboard status card
  const ring = document.getElementById("statusRing");
  ring.className = `status-ring ${status}`;
  document.getElementById("ringVal").textContent = cowCount;
  document.getElementById("smStatus").textContent = status;
  document.getElementById("smFrame").textContent = frame_count ? "#" + frame_count.toLocaleString() : "—";
  document.getElementById("smUpdated").textContent = timestamp
    ? new Date(timestamp).toLocaleTimeString("en-GB")
    : "—";

  const snippet = document.getElementById("analysisSnippet");
  snippet.textContent = analysis || "No data.";

  // Update chart with a new data point
  if (frame_count && status === "running") {
    const n = cowMatch ? parseInt(cowMatch[1]) : 0;
    state.chartData.push({ frame: frame_count, count: n });
    if (state.chartData.length > 30) state.chartData.shift();
    drawChart();
  }

  // Update topbar error count (count from log)
  const errCount = state.logEntries.filter(e => e.is_error).length;
  document.getElementById("tbErrVal").textContent = errCount || "0";
}

// ─── GET /analysis/log ────────────────────────────────────────
async function loadAnalysisLog() {
  const lines = document.getElementById("logLines")?.value || 100;
  try {
    const data = await apiGet(`/analysis/log?lines=${lines}`);
    state.logEntries = data.entries || [];
    document.getElementById("totalFrames").textContent =
      data.total ? data.total.toLocaleString() : "0";
    renderLogTable();
  } catch (e) {
    document.getElementById("logTableBody").innerHTML =
      `<tr><td colspan="4" class="log-empty">⚠ Could not load log — backend may be offline.</td></tr>`;
  }
}

function renderLogTable() {
  const filter = document.getElementById("logFilter")?.value || "all";
  const entries = state.logEntries.filter(e => {
    if (filter === "ok") return !e.is_error;
    if (filter === "error") return e.is_error;
    return true;
  }).slice().reverse();   // newest first

  const tbody = document.getElementById("logTableBody");
  if (!entries.length) {
    tbody.innerHTML = `<tr><td colspan="4" class="log-empty">No entries match filter.</td></tr>`;
    return;
  }
  tbody.innerHTML = entries.map(e => `
    <tr class="${e.is_error ? "is-error" : ""}">
      <td style="white-space:nowrap">${e.timestamp || "—"}</td>
      <td><span class="frame-badge">${e.frame || "—"}</span></td>
      <td>${e.analysis}</td>
      <td>${e.is_error
      ? `<span class="status-badge-err">Error</span>`
      : `<span class="status-badge-ok">OK</span>`}</td>
    </tr>
  `).join("");
}

function filterLog() { renderLogTable(); }

// ─── Herd cards ───────────────────────────────────────────────
async function loadHerdData() {
  // Fetch herd data from API and update state
  try {
    const response = await apiGet("/api/herd");
    if (response.herd && Array.isArray(response.herd)) {
      state.herd = response.herd;
      debug.log("Herd data loaded", `${response.herd.length} cows`);
    }
  } catch (e) {
    debug.warn("Failed to load herd data from API, using defaults", e);
    // Keep existing state.herd as fallback
  }
}

function renderHerdCards() {
  const search = (document.getElementById("herdSearch")?.value || "").toLowerCase();
  const filter = state.herdFilter;

  const cows = state.herd.filter(c => {
    const matchSearch = c.name.toLowerCase().includes(search) || c.id.toLowerCase().includes(search);
    const matchFilter = filter === "all" || c.status === filter;
    return matchSearch && matchFilter;
  });

  const grid = document.getElementById("herdCards");
  grid.innerHTML = cows.map(c => `
    <div class="herd-card ${c.status}" onclick="cowChat('${c.id}')">
      <div class="hc-header">
        <div class="hc-avatar">🐄</div>
        <span class="hc-badge ${c.status}">${c.status === "eating" ? "🌿 Eating" : "⬜ Idle"}</span>
      </div>
      <div class="hc-name">${c.name}</div>
      <div class="hc-id">${c.id}</div>
      ${c.tag ? `<span class="hc-tag">Tag ${c.tag}</span>` : ""}
      <div class="hc-detail">${c.detail}</div>
      ${c.last_update ? `<div style="font-size:0.65rem;color:var(--text2);margin-top:0.5rem;">Updated: ${new Date(c.last_update).toLocaleTimeString()}</div>` : ""}
    </div>
  `).join("");
}

function filterHerd() { renderHerdCards(); }
function filterHerdStatus(status, btn) {
  state.herdFilter = status;
  document.querySelectorAll(".hf-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  renderHerdCards();
}

function cowChat(id) {
  const cow = state.herd.find(c => c.id === id);
  if (!cow) return;
  const q = `Tell me about ${cow.name} (${cow.id}). Current status: ${cow.status}. Detail: ${cow.detail}.`;
  setView("chat", document.querySelector("[data-view=chat]"));
  sendChatMsg(q);
}

// ─── Mini herd (dashboard) ────────────────────────────────────
function renderMiniHerd() {
  const grid = document.getElementById("miniHerdGrid");
  grid.innerHTML = state.herd.map(c => `
    <div class="mini-cow ${c.status}" onclick="cowChat('${c.id}')" title="${c.name}">
      <span class="mini-cow-emoji">🐄</span>
      <span class="mini-cow-name">${c.name}</span>
      <span class="mini-cow-badge ${c.status === "eating" ? "" : "idle"}">
        ${c.status === "eating" ? "Eating" : "Idle"}
      </span>
    </div>
  `).join("");
}

// ─── Chart ────────────────────────────────────────────────────
function drawChart() {
  const canvas = document.getElementById("activityChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  const W = canvas.parentElement.offsetWidth;
  const H = 160;
  canvas.width = W;
  canvas.height = H;

  const pts = state.chartData.length > 1 ? state.chartData : [{ frame: 0, count: 4 }, { frame: 90, count: 4 }];
  const maxVal = Math.max(...pts.map(p => p.count), 1);
  const pad = { t: 12, r: 12, b: 24, l: 28 };
  const w = W - pad.l - pad.r;
  const h = H - pad.t - pad.b;

  ctx.clearRect(0, 0, W, H);

  // Grid lines
  ctx.strokeStyle = "rgba(47,61,54,0.6)";
  ctx.lineWidth = 1;
  [0, 0.25, 0.5, 0.75, 1].forEach(ratio => {
    const y = pad.t + h * (1 - ratio);
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + w, y); ctx.stroke();
  });

  // Line
  const toX = (i) => pad.l + (i / (pts.length - 1)) * w;
  const toY = (v) => pad.t + h - (v / maxVal) * h;

  ctx.beginPath();
  pts.forEach((p, i) => {
    i === 0 ? ctx.moveTo(toX(i), toY(p.count)) : ctx.lineTo(toX(i), toY(p.count));
  });
  ctx.strokeStyle = "#4ade80";
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.stroke();

  // Fill
  ctx.beginPath();
  pts.forEach((p, i) => {
    i === 0 ? ctx.moveTo(toX(i), toY(p.count)) : ctx.lineTo(toX(i), toY(p.count));
  });
  ctx.lineTo(toX(pts.length - 1), pad.t + h);
  ctx.lineTo(pad.l, pad.t + h);
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, pad.t, 0, pad.t + h);
  grad.addColorStop(0, "rgba(74,222,128,0.25)");
  grad.addColorStop(1, "rgba(74,222,128,0)");
  ctx.fillStyle = grad;
  ctx.fill();

  // Dots
  pts.forEach((p, i) => {
    ctx.beginPath();
    ctx.arc(toX(i), toY(p.count), 3, 0, Math.PI * 2);
    ctx.fillStyle = "#4ade80";
    ctx.fill();
  });

  // Y labels
  ctx.fillStyle = "rgba(90,112,99,0.8)";
  ctx.font = "9px DM Mono, monospace";
  ctx.textAlign = "right";
  [0, maxVal].forEach(v => {
    ctx.fillText(v, pad.l - 4, toY(v) + 3);
  });

  // X label
  ctx.textAlign = "center";
  ctx.fillText(`Frame ${pts[pts.length - 1]?.frame || "—"}`, pad.l + w, H - 4);
}

// ─── POST /test — AI Chat ─────────────────────────────────────
async function sendChat() {
  if (state.chatIsLoading) return;
  const input = document.getElementById("chatInput");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  autoResize(input);
  sendChatMsg(text);
}

async function sendChatMsg(text) {
  if (state.chatIsLoading) return;
  state.chatIsLoading = true;
  document.getElementById("chatSendBtn").disabled = true;

  appendBubble("farmer", text);
  hideSuggestions();

  const typing = appendTyping();

  try {
    const data = await apiPost("/test", { message: text });
    typing.remove();
    appendBubble("ai", data.response || "No response received.");
    showToast("AI responded", "success");
  } catch (err) {
    typing.remove();
    appendBubble("ai", `⚠ Could not reach the backend right now.\n\nError: ${err.message}\n\nMake sure Flask is running on port 5000.`);
    showToast("Backend unreachable", "error");
  }

  state.chatIsLoading = false;
  document.getElementById("chatSendBtn").disabled = false;
}

function appendBubble(role, text) {
  const msgs = document.getElementById("chatMessages");
  const now = new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  const div = document.createElement("div");
  div.className = `chat-bubble ${role}`;
  div.innerHTML = `
    <div class="bubble-avatar">${role === "ai" ? "AI" : "You"}</div>
    <div class="bubble-body">
      <div class="bubble-text">${escapeHtml(text).replace(/\n/g, "<br/>")}</div>
      <div class="bubble-time">${now}</div>
    </div>
  `;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function appendTyping() {
  const msgs = document.getElementById("chatMessages");
  const div = document.createElement("div");
  div.className = "chat-bubble ai";
  div.innerHTML = `
    <div class="bubble-avatar">AI</div>
    <div class="bubble-body">
      <div class="bubble-text">
        <div class="typing-dots"><span></span><span></span><span></span></div>
      </div>
    </div>
  `;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function hideSuggestions() {
  const s = document.getElementById("chatSuggestions");
  if (s) s.style.display = "none";
}

function handleChatKey(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
}

function autoResize(el) {
  // No-op: height controlled via CSS min-height & max-height to prevent flicker
  // Textarea has: min-height: 40px; max-height: 140px; overflow-y: auto;
}

// Quick action shortcut
function quickChat(question) {
  setView("chat", document.querySelector('[data-view="chat"]'));
  setTimeout(() => sendChatMsg(question), 100);
}

// ─── POST /send — SMS ─────────────────────────────────────────
async function previewAI() {
  const msg = document.getElementById("smsMessage").value.trim();
  if (!msg) { showToast("Enter a message first", "error"); return; }

  const preview = document.getElementById("aiPreviewBox");
  const wrap = document.getElementById("aiPreviewWrap");
  preview.textContent = "Generating…";
  wrap.style.display = "block";

  try {
    const data = await apiPost("/test", { message: msg });
    preview.textContent = data.response || "No response.";
  } catch {
    preview.textContent = "⚠ Backend unreachable.";
  }
}

async function sendSMS() {
  const recipients = document.getElementById("smsRecipients").value.trim();
  const message = document.getElementById("smsMessage").value.trim();
  const use_ai = document.getElementById("useAiToggle").checked;
  const feedback = document.getElementById("smsFeedback");
  const btn = document.getElementById("smsSendBtn");

  if (!recipients || !message) {
    feedback.textContent = "⚠ Fill in both recipients and message.";
    feedback.className = "sms-feedback err";
    return;
  }

  btn.disabled = true;
  btn.textContent = "Sending…";
  feedback.textContent = "";
  feedback.className = "sms-feedback";

  try {
    const data = await apiPost("/send", { recipients, message, use_ai });
    feedback.textContent = `✓ Sent to ${data.recipients?.join(", ") || recipients}`;
    feedback.className = "sms-feedback ok";
    showToast("SMS sent successfully", "success");

    // Track in recent sends
    state.recentSends.unshift({
      phone: recipients,
      msg: data.response || message,
      time: new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }),
    });
    renderRecentSends();

    document.getElementById("smsMessage").value = "";
    document.getElementById("charCount").textContent = "0";
    document.getElementById("aiPreviewWrap").style.display = "none";
  } catch (err) {
    feedback.textContent = `⚠ Failed: ${err.message}`;
    feedback.className = "sms-feedback err";
    showToast("SMS send failed", "error");
  }

  btn.disabled = false;
  btn.textContent = "Send SMS ➤";
}

function renderRecentSends() {
  const el = document.getElementById("recentSends");
  if (!state.recentSends.length) {
    el.innerHTML = `<div class="rs-empty">No messages sent this session.</div>`;
    return;
  }
  el.innerHTML = state.recentSends.slice(0, 5).map(s => `
    <div class="rs-item">
      <div class="rs-phone">${s.phone}</div>
      <div class="rs-msg">${escapeHtml(s.msg)}</div>
      <div class="rs-time">${s.time}</div>
    </div>
  `).join("");
}

// Char counter
document.addEventListener("DOMContentLoaded", () => {
  const ta = document.getElementById("smsMessage");
  if (ta) {
    ta.addEventListener("input", () => {
      document.getElementById("charCount").textContent = ta.value.length;
    });
  }
});

// ─── GET /conversations ───────────────────────────────────────
async function loadConversations() {
  const list = document.getElementById("convList");
  list.innerHTML = `<div class="conv-empty">Loading…</div>`;

  try {
    const data = await apiGet("/conversations");
    state.conversations = data.conversations || {};
    const phones = Object.keys(state.conversations);

    if (!phones.length) {
      list.innerHTML = `<div class="conv-empty">No SMS conversations yet. Incoming SMS from farmers will appear here.</div>`;
      return;
    }

    list.innerHTML = phones.map(phone => {
      const msgs = state.conversations[phone] || [];
      const last = msgs[msgs.length - 1];
      return `
        <div class="conv-item" onclick="openConversation('${escapeHtml(phone)}')">
          <div class="conv-item-phone">${phone}</div>
          <div class="conv-item-preview">${last ? escapeHtml(last.message.substring(0, 45)) : "—"}</div>
          <div class="conv-item-count">${msgs.length} message${msgs.length !== 1 ? "s" : ""}</div>
        </div>
      `;
    }).join("");
  } catch (err) {
    list.innerHTML = `<div class="conv-empty">⚠ Could not load conversations.<br/>Make sure Flask is running.</div>`;
  }
}

function openConversation(phone) {
  const msgs = state.conversations[phone] || [];
  const thread = document.getElementById("convThread");

  // Highlight selected
  document.querySelectorAll(".conv-item").forEach(el => el.classList.remove("active"));
  const items = document.querySelectorAll(".conv-item");
  items.forEach(el => {
    if (el.querySelector(".conv-item-phone")?.textContent === phone)
      el.classList.add("active");
  });

  thread.innerHTML = `
    <div style="padding:1rem 1.25rem; border-bottom:1px solid var(--border); font-size:0.72rem; color:var(--text2);">
      <strong style="color:var(--text)">${phone}</strong>
      &nbsp;·&nbsp; ${msgs.length} messages
    </div>
    <div class="conv-thread-msgs">
      ${msgs.map(m => `
        <div class="ct-msg ${m.type}">
          ${escapeHtml(m.message)}
          <div class="ct-msg-time">${m.type === "received" ? "Farmer" : "AI Reply"} · ${m.timestamp ? new Date(m.timestamp).toLocaleTimeString("en-GB") : "—"}</div>
        </div>
      `).join("")}
    </div>
  `;
}

// Note: clearConversations() is defined below with confirm() dialog - that's the version to use

// ═══════════════════════════════════════════════════════════════
// ─── VIDEO SOURCE MANAGEMENT ──────────────────────────────────
// ═══════════════════════════════════════════════════════════════

let selectedFile = null;
let webcamStream = null;
let webcamInterval = null;

async function loadVideoSourceView() {
  listUploadedVideos();
  pollVideoStatus();
}

async function listUploadedVideos() {
  try {
    const response = await apiGet("/video/list-uploads");
    const uploadsList = document.getElementById("uploadsList");
    
    if (!response.files || response.files.length === 0) {
      uploadsList.innerHTML = "<p style=\"color:#666;font-size:0.9rem;\">No uploaded videos yet</p>";
      return;
    }
    
    uploadsList.innerHTML = response.files.map(f => `
      <div class="upload-item">
        <div class="ui-name">${escapeHtml(f.filename)}</div>
        <div class="ui-meta">
          <span>${(f.size / 1024 / 1024).toFixed(2)}MB</span> ·
          <span>${new Date(f.uploaded).toLocaleString()}</span>
        </div>
        <div style="display:flex;gap:0.5rem;">
          <button class="ui-btn" onclick="selectAndProcessVideo('${escapeHtml(f.filename)}')">Process</button>
          <button class="ui-btn ui-btn-danger" onclick="deleteVideo('${escapeHtml(f.filename)}')">Delete</button>
        </div>
      </div>
    `).join("");
  } catch (e) {
    debug.error("Failed to list uploads", e);
  }
}

async function deleteVideo(filename) {
  if (!confirm(`Delete video: ${filename}?`)) return;
  
  try {
    showToast("Deleting video...", "info");
    const response = await fetch(API_BASE + `/video/delete/${encodeURIComponent(filename)}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" }
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || `Delete failed: ${response.status}`);
    }
    
    const json = await response.json();
    showToast(`Successfully deleted: ${filename}`, "success");
    debug.log("Video deleted", json);
    
    // Refresh the list
    listUploadedVideos();
    
  } catch (e) {
    showToast(`Delete error: ${e.message}`, "error");
    debug.error("Delete video failed", e);
  }
}

function handleVideoFileSelect() {
  const input = document.getElementById("videoFileInput");
  const file = input.files[0];
  
  if (!file) return;
  
  selectedFile = file;
  document.getElementById("fileInfo").style.display = "block";
  document.getElementById("fileName").textContent = file.name;
  document.getElementById("fileSize").textContent = `${(file.size / 1024 / 1024).toFixed(2)}MB`;
  document.getElementById("uploadBtn").style.display = "block";
}

async function uploadVideo() {
  if (!selectedFile) {
    showToast("No file selected", "error");
    return;
  }
  
  try {
    const formData = new FormData();
    formData.append("file", selectedFile);
    
    document.getElementById("uploadProgress").style.display = "block";
    
    const response = await fetch(API_BASE + "/video/upload", {
      method: "POST",
      body: formData,
    });
    
    if (!response.ok) throw new Error(`Upload failed: ${response.status}`);
    
    const json = await response.json();
    showToast("Video uploaded successfully!", "success");
    
    // Start processing
    await apiPost("/video/process", {
      source: "file",
      filename: json.filename,
    });
    
    showToast("Processing started", "success");
    selectedFile = null;
    document.getElementById("videoFileInput").value = "";
    document.getElementById("fileInfo").style.display = "none";
    document.getElementById("uploadBtn").style.display = "none";
    document.getElementById("uploadProgress").style.display = "none";
    
    // Poll for status
    pollVideoStatus();
    listUploadedVideos();
    
  } catch (e) {
    showToast(`Upload error: ${e.message}`, "error");
    debug.error("Upload failed", e);
  }
}

async function selectAndProcessVideo(filename) {
  try {
    showToast("Starting video processing...", "info");
    await apiPost("/video/process", {
      source: "file",
      filename: filename,
    });
    showToast("Processing started", "success");
    pollVideoStatus();
  } catch (e) {
    showToast(`Processing error: ${e.message}`, "error");
  }
}

async function startWebcamCapture() {
  try {
    const duration = parseInt(document.getElementById("webcamDuration").value) || 60;
    
    // Request camera access
    webcamStream = await navigator.mediaDevices.getUserMedia({ video: true });
    const video = document.createElement("video");
    video.srcObject = webcamStream;
    video.play();
    
    // Get canvas
    const canvas = document.getElementById("webcamCanvas");
    const ctx = canvas.getContext("2d");
    canvas.width = 640;
    canvas.height = 480;
    
    // Draw frames
    webcamInterval = setInterval(() => {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    }, 100);
    
    // Start backend processing
    await apiPost("/video/process", {
      source: "webcam",
      duration: duration,
    });
    
    document.getElementById("startWebcamBtn").style.display = "none";
    document.getElementById("stopWebcamBtn").style.display = "block";
    showToast("Webcam capture started", "success");
    pollVideoStatus();
    
  } catch (e) {
    showToast(`Webcam error: ${e.message}`, "error");
    debug.error("Webcam capture failed", e);
  }
}

async function stopWebcamCapture() {
  try {
    if (webcamStream) {
      webcamStream.getTracks().forEach(track => track.stop());
      webcamStream = null;
    }
    if (webcamInterval) {
      clearInterval(webcamInterval);
      webcamInterval = null;
    }
    
    await stopVideoProcessing();
    
    document.getElementById("startWebcamBtn").style.display = "block";
    document.getElementById("stopWebcamBtn").style.display = "none";
    showToast("Webcam stopped", "info");
    
  } catch (e) {
    debug.error("Stop webcam error", e);
  }
}

async function stopVideoProcessing() {
  try {
    await apiPost("/video/stop", {});
    showToast("Video processing stopped", "info");
    pollVideoStatus();
  } catch (e) {
    debug.error("Stop video processing error", e);
  }
}

async function pollVideoStatus() {
  try {
    const status = await apiGet("/video/status");
    
    document.getElementById("procStatus").textContent = status.status || "idle";
    document.getElementById("procFrames").textContent = status.frame_count || "0";
    document.getElementById("procAnalysis").textContent = (status.latest_analysis || "—").substring(0, 100);
    
    if (status.is_processing) {
      setTimeout(pollVideoStatus, 2000);
    }
  } catch (e) {
    debug.warn("Video status poll failed", e);
  }
}

// Drag and drop for video upload
const uploadArea = document.getElementById("videoUploadArea");
if (uploadArea) {
  uploadArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = "var(--accent)";
  });
  
  uploadArea.addEventListener("dragleave", () => {
    uploadArea.style.borderColor = "var(--border)";
  });
  
  uploadArea.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = "var(--border)";
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      document.getElementById("videoFileInput").files = files;
      handleVideoFileSelect();
    }
  });
}

// ═══════════════════════════════════════════════════════════════
// ─── NEW FEATURES: Live Frame, Health Tracking, Notifications ──
// ═══════════════════════════════════════════════════════════════

// Add to state
state.lastSuccessfulAnalysis = null;
state.consecutiveErrors = 0;
state.feedType = "—";
state.feedTime = "—";
state.alerts = [];
state.lastFramePoolTime = 0;

// Live frame viewer - poll every 3 seconds
function pollLiveFrame() {
  const now = Date.now();
  if (now - state.lastFramePoolTime < 3000) return; // Skip if polled recently
  
  state.lastFramePoolTime = now;
  
  fetch(API_BASE + "/video/current-frame")
    .then(r => {
      if (r.ok) return r.blob();
      throw new Error("No frame");
    })
    .then(blob => {
      const url = URL.createObjectURL(blob);
      const img = document.getElementById("liveFrameImg");
      img.src = url;
      img.style.display = "block";
      document.getElementById("frameNotAvailable").style.display = "none";
    })
    .catch(() => {
      document.getElementById("liveFrameImg").style.display = "none";
      document.getElementById("frameNotAvailable").style.display = "flex";
    });
}

// Update live frame analysis text
function updateLiveFrameAnalysis() {
  if (state.analysisStatus) {
    document.getElementById("frameAnalysis").textContent = 
      state.analysisStatus.analysis || "—";
  }
}

// Parse feed type from analysis text
function parseFeedType(analysisText) {
  if (!analysisText) return;
  const patterns = [
    /hay/i, /silage/i, /fodder/i, /green feed/i, 
    /grain/i, /concentrate/i, /pasture/i
  ];
  for (const pattern of patterns) {
    const match = analysisText.match(pattern);
    if (match) {
      state.feedType = match[0].toLowerCase();
      state.feedTime = new Date().toLocaleTimeString("en-GB", { hour12: false });
      document.getElementById("feedType").textContent = state.feedType;
      document.getElementById("feedTime").textContent = state.feedTime;
      return;
    }
  }
}

// Auto-sync herd status from analysis
function syncHerdStatus() {
  if (!state.analysisStatus || !state.analysisStatus.analysis) return;
  
  const text = state.analysisStatus.analysis;
  const cowPattern = /Cow\s*(\d+)[:\s]+(\w+)/gi;
  let match;
  
  while ((match = cowPattern.exec(text)) !== null) {
    const cowNum = parseInt(match[1]);
    const status = match[2].toLowerCase();
    
    // Find cow in state.herd
    const cow = state.herd.find(c => {
      const id = parseInt(c.id.match(/\d+$/)?.[0] || "0");
      return id === cowNum;
    });
    
    if (cow) {
      cow.status = status.includes("eat") ? "eating" : "idle";
      cow.detail = status.includes("eat") ? `${state.feedType || 'hay'}` : "Standing";
    }
  }
  
  // Update UI
  if (document.getElementById("view-herd")?.classList.contains("active")) {
    renderHerdCards();
  }
  renderMiniHerd();
}

// Track analysis errors for health indicator
function updateHealthStatus() {
  const now = new Date();
  if (!state.analysisStatus) return;
  
  const analysis = state.analysisStatus.analysis || "";
  const isError = analysis.includes("Analysis error");
  const timestamp = state.analysisStatus.timestamp;
  
  if (!isError) {
    state.lastSuccessfulAnalysis = now;
    state.consecutiveErrors = 0;
  } else {
    state.consecutiveErrors++;
  }
  
  // Update health UI
  const healthDot = document.getElementById("healthDot");
  const healthMsg = document.getElementById("healthMsg");
  const healthStatus = document.getElementById("healthStatus");
  const errorBanner = document.querySelector("#feedTrackingCard [id='errorBanner']");
  
  if (state.lastSuccessfulAnalysis) {
    const timeDiff = now - state.lastSuccessfulAnalysis;
    const minSince = Math.floor(timeDiff / 60000);
    
    healthDot.classList.remove("error");
    healthMsg.classList.remove("error");
    
    if (minSince > 5) {
      healthDot.classList.add("error");
      healthMsg.classList.add("error");
      healthMsg.textContent = `No successful analysis for ${minSince} minutes`;
      if (errorBanner) errorBanner.style.display = "block";
    } else {
      healthMsg.classList.remove("error");
      healthMsg.textContent = `${minSince}m ago`;
      if (errorBanner) errorBanner.style.display = "none";
    }
    
    document.getElementById("lastSuccessTime").textContent = 
      state.lastSuccessfulAnalysis.toLocaleTimeString("en-GB", { hour12: false });
  }
}

// Connection status banner
let isConnected = true;
function updateConnectionStatus(healthy) {
  const banner = document.getElementById("connectionBanner");
  if (healthy && !isConnected) {
    // Reconnected
    banner.style.display = "none";
    isConnected = true;
    showToast("Connection restored", "success");
  } else if (!healthy && isConnected) {
    // Lost connection
    banner.style.display = "flex";
    isConnected = false;
  }
}

// Add alerts for anomalies
function checkForAnomalies() {
  if (!state.analysisStatus) return;
  
  // Cow count drops by >50%
  if (state.lastCowCount) {
    const current = parseInt(state.analysisStatus.analysis.match(/(\d+)\s+cow/i)?.[1] || "0");
    if (current > 0 && state.lastCowCount > 0) {
      const drop = ((state.lastCowCount - current) / state.lastCowCount) * 100;
      if (drop > 50) {
        addAlert("🚨 Cow count dropped by " + Math.round(drop) + "%");
      }
    }
    state.lastCowCount = current;
  }
  
  // 5+ consecutive errors
  if (state.consecutiveErrors >= 5) {
    addAlert("❌ 5 consecutive analysis errors detected");
  }
}

// Note: Full addAlert() defined below with level support

// Style error count in red
function updateErrorBadge() {
  const errorCount = parseInt(document.getElementById("tbErrVal").textContent);
  const element = document.getElementById("tbErrVal");
  if (errorCount > 0) {
    element.classList.add("error");
  } else {
    element.classList.remove("error");
  }
}

// Enhanced poll analysis status with new features
async function enhancedPollAnalysisStatus() {
  // Await the original async fetch so state.analysisStatus is populated before we act
  await pollAnalysisStatus();
  
  // Now state.analysisStatus is guaranteed to be updated
  if (state.analysisStatus) {
    parseFeedType(state.analysisStatus.analysis);
    syncHerdStatus();
    updateHealthStatus();
    updateErrorBadge();
    checkForAnomalies();
    updateLiveFrameAnalysis();
    pollLiveFrame();
    updateConnectionStatus(state.backendHealthy);
  }
}

// Add chat context indicator to chat input area
function updateChatContext() {
  let contextHTML = "—";
  if (state.analysisStatus) {
    const ts = state.analysisStatus.timestamp ? 
      new Date(state.analysisStatus.timestamp).toLocaleTimeString("en-GB") : "—";
    const frame = state.analysisStatus.frame_count || "—";
    const cowMatch = state.analysisStatus.analysis.match(/(\d+)\s+cow/i);
    const cows = cowMatch ? cowMatch[1] : "—";
    contextHTML = `Using data from ${ts} · Frame ${frame} · ${cows} cows`;
  }
  
  const contextEl = document.querySelector(".chat-context");
  if (contextEl) {
    contextEl.innerHTML = contextHTML;
    contextEl.style.display = "block";
  }
}

// ─── Alert System ────────────────────────────────────────────
function addAlert(message, level = "info") {
  // Deduplicate alerts
  if (state.alerts.some(a => a.message === message)) return;
  
  state.alerts.unshift({
    message: message,
    level: level,
    timestamp: new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
  });
  
  // Keep last 20 alerts
  if (state.alerts.length > 20) state.alerts.pop();
  
  renderAlerts();
  updateAlertCount();
}

function renderAlerts() {
  const list = document.getElementById("alertsList");
  if (!list) return;
  
  if (!state.alerts.length) {
    list.innerHTML = `<div class="alerts-empty">No alerts</div>`;
    return;
  }
  
  list.innerHTML = state.alerts.map(alert => `
    <div class="alert-item ${alert.level}">
      <div style="font-weight:500;">${alert.message}</div>
      <div style="font-size:0.7rem;color:var(--text3);margin-top:0.3rem;">${alert.timestamp}</div>
    </div>
  `).join("");
}

function updateAlertCount() {
  const count = state.alerts.length;
  document.getElementById("alertCount").textContent = count || "0";
}

function toggleAlertsDropdown() {
  const panel = document.getElementById("alertsPanel");
  if (panel.style.display === "none") {
    panel.style.display = "block";
    renderAlerts();
  } else {
    panel.style.display = "none";
  }
}

function clearAllAlerts() {
  state.alerts = [];
  renderAlerts();
  updateAlertCount();
  showToast("Alerts cleared", "info");
}

// Close alerts dropdown when clicking elsewhere
document.addEventListener("click", function(event) {
  const dropdown = document.getElementById("alertsDropdown");
  const btn = document.getElementById("alertsBtn");
  if (dropdown && btn && !dropdown.contains(event.target) && !btn.contains(event.target)) {
    document.getElementById("alertsPanel").style.display = "none";
  }
});

// Initialize new features on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  // Set initial state
  state.analysisLogInterval = null;
  state.lastCowCount = 0;
  state.consecutiveErrors = 0;
  state.framesAnalyzed = 0;
  
  // Ensure pollLiveFrame runs when dashboard is active
  const originalSetView = window.setView;
  window.setView = function(name, btn) {
    originalSetView(name, btn);
    if (name === "dashboard") {
      pollLiveFrame();
      // Poll frame every 3 seconds when dashboard is active
      if (state.framePollInterval) clearInterval(state.framePollInterval);
      state.framePollInterval = setInterval(pollLiveFrame, 3000);
    } else {
      if (state.framePollInterval) clearInterval(state.framePollInterval);
    }
  };
});
async function clearConversations() {
  if (!confirm("Clear all conversation history?")) return;
  try {
    await apiPost("/conversations/clear", {});
    state.conversations = {};
    loadConversations();
    document.getElementById("convThread").innerHTML =
      `<div class="conv-thread-empty">Conversation history cleared.</div>`;
    showToast("History cleared", "success");
  } catch {
    showToast("Failed to clear history", "error");
  }
}

// ─── Utilities ────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ─── Bootstrap ───────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  debug.log("Initializing HerdWatch frontend");
  debug.log("API_BASE:", API_BASE);

  // Check backend health
  try {
    const health = await apiGet("/api/health");
    state.backendHealthy = true;
    debug.log("Backend health check passed", health);
    showToast("✓ Backend connected", "success");
  } catch (e) {
    debug.error("Backend health check failed", e);
    showToast("✗ Backend unreachable - using demo mode", "warning");
    state.backendHealthy = false;
  }

  renderMiniHerd();
  renderHerdCards();
  renderRecentSends();
  
  if (state.backendHealthy) {
    // First poll immediately (enhanced version awaits fetch + runs feature hooks)
    await enhancedPollAnalysisStatus();
    loadAnalysisLog();
    // Also start live frame polling right away for the dashboard view
    pollLiveFrame();
    if (state.framePollInterval) clearInterval(state.framePollInterval);
    state.framePollInterval = setInterval(pollLiveFrame, 3000);
  } else {
    // Demo mode: show placeholder data
    updateStatusUI({ 
      timestamp: new Date().toISOString(),
      analysis: "Demo mode - backend not responding", 
      frame_count: 0, 
      status: "disconnected" 
    });
  }

  // Initial chart — will be overwritten once real data arrives
  state.chartData = [
    { frame: 90, count: 7 }, { frame: 180, count: 4 },
    { frame: 360, count: 8 }, { frame: 540, count: 3 },
    { frame: 720, count: 7 }, { frame: 900, count: 4 },
    { frame: 1080, count: 5 }, { frame: 1350, count: 7 },
    { frame: 1620, count: 8 }, { frame: 1710, count: 6 },
    { frame: 1980, count: 7 }, { frame: 2250, count: 7 },
    { frame: 2340, count: 7 }, { frame: 2610, count: 6 },
    { frame: 2880, count: 6 }, { frame: 3060, count: 4 },
    { frame: 3240, count: 7 }, { frame: 3510, count: 7 },
    { frame: 3600, count: 6 }, { frame: 3870, count: 8 },
  ];
  drawChart();

  // Start polling loops (only if backend is healthy)
  if (state.backendHealthy) {
    setInterval(enhancedPollAnalysisStatus, POLL_INTERVAL);
    setInterval(loadAnalysisLog, LOG_POLL_INTERVAL);
    setInterval(loadHerdData, 10000); // Poll herd data every 10 seconds
  }

  // Redraw chart on resize
  window.addEventListener("resize", drawChart);
});
