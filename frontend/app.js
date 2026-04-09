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
  analysis: { title: "AI Analysis", crumb: "Gemini · Frame Log" },
  herd: { title: "Herd", crumb: "Individual Cows · Status" },
  chat: { title: "AI Chat", crumb: "Gemini · Farmer Assistant" },
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
  if (name === "analysis") loadAnalysisLog();
  if (name === "conversations") loadConversations();
  if (name === "herd") renderHerdCards();
  if (name === "dashboard") renderMiniHerd();
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
    showToast("AI responded", "ok");
  } catch (err) {
    typing.remove();
    appendBubble("ai", `⚠ Could not reach the backend right now.\n\nError: ${err.message}\n\nMake sure Flask is running on port 5000.`);
    showToast("Backend unreachable", "err");
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
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 140) + "px";
}

// Quick action shortcut
function quickChat(question) {
  setView("chat", document.querySelector("[data-view=chat]"));
  setTimeout(() => sendChatMsg(question), 100);
}

// ─── POST /send — SMS ─────────────────────────────────────────
async function previewAI() {
  const msg = document.getElementById("smsMessage").value.trim();
  if (!msg) { showToast("Enter a message first", "err"); return; }

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
    showToast("SMS sent successfully", "ok");

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
    showToast("SMS send failed", "err");
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

// ─── POST /conversations/clear ────────────────────────────────
async function clearConversations() {
  if (!confirm("Clear all conversation history?")) return;
  try {
    await apiPost("/conversations/clear", {});
    state.conversations = {};
    loadConversations();
    document.getElementById("convThread").innerHTML =
      `<div class="conv-thread-empty">Conversation history cleared.</div>`;
    showToast("History cleared", "ok");
  } catch {
    showToast("Failed to clear history", "err");
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
    pollAnalysisStatus();
    loadAnalysisLog();
  } else {
    // Demo mode: show placeholder data
    updateStatusUI({ 
      timestamp: new Date().toISOString(),
      analysis: "Demo mode - backend not responding", 
      frame_count: 0, 
      status: "disconnected" 
    });
  }

  // Initial chart with historical data from the log
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
    setInterval(pollAnalysisStatus, POLL_INTERVAL);
    setInterval(loadAnalysisLog, LOG_POLL_INTERVAL);
  }

  // Redraw chart on resize
  window.addEventListener("resize", drawChart);
});
