/* Fonts from Google only when not offline (v0.12). The last known mode is cached so the boot animation doesn't
   flash fallback fonts; offline it falls back to Bahnschrift / Segoe UI / Consolas, already in the CSS. */
function loadFonts(mode) {
  try { localStorage.setItem("nexus.net", mode); } catch (e) { /* ignore */ }
  if (mode === "offline" || document.getElementById("gfonts")) return;
  const l = Object.assign(document.createElement("link"), { id: "gfonts", rel: "stylesheet",
    href: "https://fonts.googleapis.com/css2?family=Michroma&family=Orbitron:wght@600;700;800&family=Rajdhani:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" });
  document.head.appendChild(l);
}
try { loadFonts(localStorage.getItem("nexus.net") || "hybrid"); } catch (e) { loadFonts("hybrid"); }

/* v0.16: ring, core and background colours (Settings > Interface). Cached so the boot screen starts with them. */
const COLOR_DEFAULTS = { color_ring: "#cfe4ff", color_core: "#2f86ff", color_bg: "#0b1f5c" };
function setColors(src) {
  const css = { color_ring: "--c-ring", color_core: "--c-core", color_bg: "--c-bg" }, used = {};
  for (const [k, v] of Object.entries(css)) {
    used[k] = /^#[0-9a-f]{6}$/i.test(src[k] || "") ? src[k] : COLOR_DEFAULTS[k];
    document.documentElement.style.setProperty(v, used[k]);
  }
  try { localStorage.setItem("nexus.colors", JSON.stringify(used)); } catch (e) { /* ignore */ }
}
try { setColors(JSON.parse(localStorage.getItem("nexus.colors") || "{}")); } catch (e) { /* defaults from the CSS */ }

/* N.E.X.U.S interface. Talks to Python through window.pywebview.api; Python pushes events via nexus.on(). */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const BOOT_MIN_MS = 4200;

let L = "pt";
let settings = {};
let profile = null;
let streaming = null; // { el, text }
let voiceState = "idle";
let dash = null;

const T = (key, vars = {}) => {
  const s = (I18N[L] && I18N[L][key]) ?? I18N.pt[key] ?? key;
  return typeof s === "string" ? s.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "") : s;
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/* ------------------------------------------------------------------ visuals */
function ringsSVG(id) {
  // v0.16 ring: thin light arcs with tick marks, a dotted ring, a segmented ring and a glowing core.
  // Colours come from CSS variables (--c-ring, --c-core), so Settings > Interface can change them.
  const C = (r) => 2 * Math.PI * r;
  const arcs = (r, parts, gapFrac) => {  // `parts` equal arcs separated by gaps
    const seg = C(r) / parts;
    return `stroke-dasharray="${seg * (1 - gapFrac)} ${seg * gapFrac}"`;
  };
  const boot = (delay, inner) => `<g class="ring-boot" style="--delay:${delay}s">${inner}</g>`;
  const spin = (dur, dir, inner) => `<g class="ring-spin" style="--dur:${dur}s;--dir:${dir}">${inner}</g>`;
  const ticks = (r, n, len, cls, every = 1) => {
    let out = "";
    for (let i = 0; i < n; i += every) {
      const a = (i / n) * 2 * Math.PI, c = Math.cos(a), s = Math.sin(a);
      out += `<line x1="${(300 + r * c).toFixed(1)}" y1="${(300 + r * s).toFixed(1)}" x2="${(300 + (r + len) * c).toFixed(1)}" y2="${(300 + (r + len) * s).toFixed(1)}"/>`;
    }
    return `<g class="${cls}">${out}</g>`;
  };
  return `<svg class="hud-rings" viewBox="0 0 600 600" aria-hidden="true">
  <defs>
    <radialGradient id="${id}Core" cx="50%" cy="50%" r="50%">
      <stop offset="0%" style="stop-color:var(--c-core-hot)"/><stop offset="22%" style="stop-color:var(--c-core)"/>
      <stop offset="55%" style="stop-color:var(--c-core);stop-opacity:.35"/><stop offset="100%" style="stop-color:var(--c-core);stop-opacity:0"/>
    </radialGradient>
    <radialGradient id="${id}Halo" cx="50%" cy="50%" r="50%">
      <stop offset="0%" style="stop-color:var(--c-core);stop-opacity:.28"/><stop offset="100%" style="stop-color:var(--c-core);stop-opacity:0"/>
    </radialGradient>
    <filter id="${id}Glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="2.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <circle cx="300" cy="300" r="230" fill="url(#${id}Halo)" class="ring-halo"/>
  ${boot(0, spin(200, "normal", ticks(268, 72, 7, "j-tick") + ticks(262, 72, 15, "j-tick strong", 9)))}
  ${boot(0.15, spin(70, "reverse", `<circle cx="300" cy="300" r="246" class="j-arc" ${arcs(246, 4, 0.34)} filter="url(#${id}Glow)"/>`))}
  ${boot(0.3, `<circle cx="300" cy="300" r="232" class="j-thin faint"/>`)}
  ${boot(0.4, spin(110, "normal", `<circle cx="300" cy="300" r="214" class="j-thin" ${arcs(214, 3, 0.5)}/>`))}
  ${boot(0.5, `<circle cx="300" cy="300" r="170" class="j-thin faint"/>`)}
  ${boot(0.6, spin(48, "normal", `<circle cx="300" cy="300" r="150" class="j-dots"/>`))}
  ${boot(0.7, spin(26, "reverse", `<circle cx="300" cy="300" r="128" class="j-seg" ${arcs(128, 9, 0.3)} filter="url(#${id}Glow)"/>`))}
  ${boot(0.8, `<circle cx="300" cy="300" r="108" class="j-thin"/>`)}
  ${boot(0.9, `<circle cx="300" cy="300" r="100" fill="url(#${id}Core)" class="ring-core"/>`)}
</svg>`;
}

function wordmarkHTML() {
  return [..."NEXUS"].map((ch, i) =>
    `<span aria-hidden="true" class="wm-group" style="--i:${i}"><span class="wm-letter">${ch}</span>${i < 4 ? '<span class="wm-dot">.</span>' : ""}</span>`
  ).join("");
}

function md(text) {
  const blocks = [];
  let s = esc(text).replace(/```(\w*)\n?([\s\S]*?)```/g, (_, _l, code) => `\u0000${blocks.push(code) - 1}\u0000`);
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|\n)(?:[-*]|\d+\.) (.+)/g, "$1<li>$2</li>")
    .replace(/<\/li>\n(?=<li>)/g, "</li>")
    .replace(/((?:<li>.*?<\/li>)+)\n?/g, "<ul>$1</ul>")
    .replace(/\n/g, "<br>");
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<pre>${blocks[i]}</pre>`);
}

/* ------------------------------------------------------------------ i18n */
function applyLang(lang) {
  L = I18N[lang] ? lang : "pt";
  document.documentElement.lang = { pt: "pt-BR", en: "en", es: "es" }[L];
  $$("[data-i18n]").forEach((el) => (el.textContent = T(el.dataset.i18n)));
  $$("[data-i18n-ph]").forEach((el) => (el.placeholder = T(el.dataset.i18nPh)));
  $$("[data-i18n-title]").forEach((el) => (el.title = T(el.dataset.i18nTitle)));
  $$("#langSwitch button").forEach((b) => b.classList.toggle("on", b.dataset.lang === L));
  $("#bridgeHint").textContent = T("bridgeHint", { port: settings.bridge_port || 47800 });
  setVoiceState(voiceState);
  if (dash) renderDashboard(dash);
}

/* ------------------------------------------------------------------ events from Python */
window.nexus = {
  on(event, p) {
    switch (event) {
      case "boot": return bootLine(p);
      case "token": return onToken(p);
      case "reset": if (streaming) { streaming.text = (p && p.keep) || ""; streaming.el.querySelector(".txt").innerHTML = md(streaming.text); } return;
      case "tool": return onTool(p);
      case "done": return onDone(p);
      case "error": return onError(p);
      case "refresh": return loadDashboard();
      case "voice": return setVoiceState(p);
      case "heard": return onHeard(p);
      case "speak_env": ringSpeak(p); return wakeRing();
      case "mic_level": ringMicTarget = Math.max(ringMicTarget, p); return wakeRing();
      case "control": return onControl(p);
      case "ai_state": return setAiState(p);
      case "alert": return onAlert(p);
      case "profile": return onProfile(p);
      case "conversations": return !$("#convDrawer").hidden && renderConversations();
      case "workspace": return renderWsPanel(p);
      case "levelup": return onLevelUp(p);
      case "podcast": return onPodcast(p);
      case "network": return applyState({ network_effective: p.effective, net_quality: p.quality });
      case "confirm": return askConfirm(p);
      case "confirm_done": return (confirmId === p.id) && closeConfirm(p.ok);
    }
  },
};

/* ------------------------------------------------------------------ boot */
const bootQueue = [];
let bootPumping = false;
function bootLine(step) {
  bootQueue.push(step);
  if (bootPumping) return;
  bootPumping = true;
  (function pump() {
    const s = bootQueue.shift();
    if (!s) return (bootPumping = false);
    const li = document.createElement("li");
    li.innerHTML = `<span>${esc(T("boot_" + s.key))}</span><span class="fill"></span><span class="${s.ok ? "ok" : "warn"}">${s.ok ? "OK" : "!!"}</span>`
      + (s.detail ? `<span class="muted">${esc(s.detail)}</span>` : "");
    $("#bootLog").appendChild(li);
    setTimeout(pump, 380);
  })();
}

async function start() {
  const t0 = Date.now();
  await api().ui_ready();
  const st = await api().boot();
  settings = st.settings;
  profile = st.profile;
  applyLang(st.lang);
  setAi(st.llm);
  $("#version").textContent = "v" + st.version;
  $("#modelName").textContent = st.model_name || "NEX-1.0";
  applyInterface();
  api().notifications().then((r) => setBadge(r.unread));
  api().skills().then(renderLvBadge);
  applyState({ network: settings.network_mode, performance: settings.performance, ai_target: settings.ai_target || "local",
    ui_mode: settings.ui_mode, mic_muted: settings.mic_muted, voice_enabled: settings.voice_enabled, stt: st.stt,
    ai_mode: settings.ai_mode || "assistant", temporary: false });
  await new Promise((r) => setTimeout(r, Math.max(0, BOOT_MIN_MS - (Date.now() - t0))));
  $("#boot").classList.add("leaving");
  $("#app").hidden = false;
  requestAnimationFrame(() => $("#app").classList.add("on"));
  setTimeout(() => ($("#boot").hidden = true), 1200);
  await loadDashboard();
  for (const m of await api().history()) addMsg(m.role === "user" ? "user" : "nexus", m.content);
  const hello = await api().greet();
  addMsg("nexus", hello);
  caption(hello, 7000);
  if (!profile) openOnboarding();
  setFull(!!st.fullscreen);
  if (!st.llm.online || !st.llm.model_ready) notice(aiHelp(st.llm), T("moreAi"));
  else if (state.ui_mode === "audio" && !state.mic_muted && st.stt === "missing") notice(T("voiceFirstUse"), T("moreVoice"));
}

function aiHelp(llm) {
  return llm.online ? T("modelMissing", { model: llm.model }) : T("aiOfflineHelp", { model: llm.model });
}

let aiDown = false, aiPoll = null, aiHelpText = "";
function setAi(llm) {
  $("#chipAi").classList.toggle("on", !!(llm.online && llm.model_ready));
  $("#chipAi").title = llm.online ? llm.model : T("offline");
  // v0.16.1: no AI available -> the ring says so, with a "how to fix" button (NEXUS speaks the steps)
  aiDown = !(llm.online && llm.model_ready);
  aiHelpText = aiDown ? aiHelp(llm) : "";
  $("#app").classList.toggle("ai-down", aiDown);
  $("#btnAiFix").hidden = !aiDown;
  if (aiDown && !aiPoll) aiPoll = setInterval(() => api().llm_status().then(setAi), 20000);
  if (!aiDown && aiPoll) { clearInterval(aiPoll); aiPoll = null; }
  setVoiceState(voiceState);
}

// Model loading during the boot animation (v0.6): amber while warming, blue when ready.
function setAiState(p) {
  const chip = $("#chipAi");
  chip.classList.toggle("warm", p.state === "warming");
  chip.classList.toggle("on", p.state === "ready");
  chip.title = p.state === "warming" ? T("aiWarming") : p.state === "ready" ? T("aiReady", { s: p.seconds }) : T("offline");
  if (p.state === "ready" && aiDown) api().llm_status().then(setAi);
}

/* ------------------------------------------------------------------ conversation */
/* v0.16: the last exchange is shown under the ring (audio mode), like a two-line transcript */
const plain = (t) => String(t || "").replace(/```[\s\S]*?```/g, " ").replace(/[*`#>]/g, "").replace(/\s+/g, " ").trim();
function setExchange(who, text) {
  if (who === "user") { $("#exUser").textContent = plain(text); $("#exNexus").textContent = ""; }
  else $("#exNexus").textContent = plain(text);
}

let aiBusy = false;
function addMsg(kind, text, spoken = false) {
  if (kind === "user" || (kind === "nexus" && text)) setExchange(kind, text);
  if (kind === "user") aiBusy = true;
  activity();
  const el = document.createElement("div");
  el.className = `msg ${kind}`;
  const who = kind === "user" ? T("you") + (spoken ? " · 🎙 " + T("heard") : "") : kind === "nexus" ? "N.E.X.U.S" : "";
  el.innerHTML = (who ? `<span class="who">${esc(who)}</span>` : "") + `<div class="txt">${kind === "nexus" ? md(text) : esc(text)}</div>`
    + (kind === "system" ? "" : `<button class="msg-copy" data-copy title="${esc(T("copy"))}">${esc(T("copy"))}</button>`);
  $("#chat").appendChild(el);
  $("#chat").scrollTop = $("#chat").scrollHeight;
  if (kind === "user") { setVoiceState("thinking"); }
  return el;
}

function ensureStream() {
  if (!streaming) {
    const el = addMsg("nexus", "");
    el.querySelector(".txt").classList.add("caret");
    streaming = { el, text: "" };
  }
  return streaming;
}

function onToken(tok) {
  const s = ensureStream();
  s.text += tok;
  s.el.querySelector(".txt").innerHTML = md(s.text);
  $("#chat").scrollTop = $("#chat").scrollHeight;
  setExchange("nexus", tail(s.text));
  updateDock();
}

const tail = (text) => {  // last ~150 chars, cut at a word
  const t = text.replace(/[*`#]/g, "").trim();
  return t.length <= 150 ? t : "…" + t.slice(-150).replace(/^\S*\s/, "");
};

function onTool(p) {
  const s = ensureStream();
  const chip = document.createElement("span");
  chip.className = "tool-chip";
  chip.textContent = "⚙ " + (T("tool")[p.name] || p.name);
  s.el.insertBefore(chip, s.el.querySelector(".txt"));
}

function onDone(p) {
  aiBusy = false;
  const s = ensureStream();
  if (!p.text) { s.el.remove(); streaming = null; setVoiceState("idle"); return; }  // pause/stop handled by the model
  s.el.querySelector(".txt").classList.remove("caret");
  s.el.querySelector(".txt").innerHTML = md(p.text) + (p.interrupted ? " <span class=\"muted\">…</span>" : "");
  setExchange("nexus", p.text);
  streaming = null;
  state.can_repeat = true;
  if (!(state.ui_mode === "audio" && state.voice_enabled && p.speak)) setVoiceState("idle");
  updateDock();
}

function onError(p) {
  aiBusy = false;
  if (streaming) { streaming.el.remove(); streaming = null; }
  addMsg("system", p.message).classList.add("error");
  notice(p.message, T("moreError"));
  setVoiceState("idle");
  api().get_settings().then((r) => setAi(r.llm));
}

function onHeard(p) {
  addMsg("user", p.text, true);
  if (p.control) setVoiceState("idle");
}

function onControl(p) {
  const label = T("ctl_" + p.action);
  if (p.text) addMsg("nexus", (p.intro ? p.intro + "\n\n" : "") + p.text);
  else if (p.intro) addMsg("system", p.intro);
  caption(label, 2500);
  if (p.action === "stop" && streaming) onDone({ text: streaming.text, interrupted: true });
}

let unread = 0;
function setBadge(n) {
  unread = n;
  $("#notifBadge").hidden = !n;
  $("#notifBadge").textContent = n > 9 ? "9+" : n;
}

// Short two-tone chime (WebAudio, no file): plays for reminders when "Alert sound" is on.
let audioCtx;
function chime() {
  try {
    audioCtx = audioCtx || new AudioContext();
    const t0 = audioCtx.currentTime;
    [[880, 0], [1320, 0.12]].forEach(([f, d]) => {
      const o = audioCtx.createOscillator(), g = audioCtx.createGain();
      o.type = "sine"; o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, t0 + d); g.gain.exponentialRampToValueAtTime(0.18, t0 + d + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + d + 0.35);
      o.connect(g).connect(audioCtx.destination); o.start(t0 + d); o.stop(t0 + d + 0.4);
    });
  } catch (e) { /* no audio device */ }
}

async function openNotifications() {
  const r = await api().notifications();
  $("#notifList").innerHTML = r.items.map((n) => `
    <div class="notif-item ${n.read ? "" : "unread"}"><time class="mono">${esc(fmtDate(n.ts))}</time>
      <b>${esc(n.title)}</b><span>${esc(n.body)}</span></div>`).join("") || `<p class="muted">${esc(T("notifEmpty"))}</p>`;
  $("#notifDrawer").hidden = false;
  api().mark_notifications_read();
  setBadge(0);
}

function onAlert(a) {
  if (a.notification) setBadge(unread + 1);
  if (a.quiet) return;  // quiet hours / focus mode: only the bell
  if (a.sound) chime();
  const el = document.createElement("div");
  el.className = "toast";
  el.innerHTML = `<b>${esc(T("reminder"))}</b>${esc(a.text)}`;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 15000);
  addMsg("system", "⏰ " + a.text);
  loadDashboard();
}

async function send(text) {
  text = text.trim();
  if (!text && pendingFiles.length) text = T("attachDefault");
  if (!text) return;
  addMsg("user", text + (pendingFiles.length ? "\n📎 " + pendingFiles.map((f) => f.name).join(", ") : ""));
  pendingFiles = [];
  renderAttachChips();
  const r = await api().send(text, false);
  if (r && r.control) setVoiceState("idle");
}

/* ------------------------------------------------------------------ voice state */
let state = { ui_mode: "audio", mic_muted: false, voice_enabled: true, stt: "ready", ai_mode: "assistant", temporary: false, can_repeat: false };
let transcriptOn = false;
try { transcriptOn = localStorage.getItem("nexus.transcript") === "1"; } catch (e) { /* storage unavailable */ }

function setVoiceState(st) {
  voiceState = st;
  let shown = st;
  if (st === "idle" && state.ui_mode === "audio") shown = state.mic_muted ? "muted" : state.stt === "ready" ? "standby" : "idle";
  if (aiBusy && ["idle", "standby", "muted"].includes(shown)) shown = "thinking";  // v0.16.1: spins fast until it answers
  if (shown !== "idle" && shown !== "standby" && shown !== "muted") activity();
  $("#core").dataset.state = shown;
  if (st === "speaking") wakeRing();
  const label = $("#coreLabel");
  label.textContent = aiDown && !aiBusy ? T("aiDown") : T("st_" + shown) || "";
  label.className = "core-label " + (["listening", "awake"].includes(shown) ? "red" : ["speaking", "thinking"].includes(shown) ? "blue" : "");
  $("#chipVoice").classList.toggle("on", state.ui_mode === "audio" && !state.mic_muted && state.stt === "ready");
  updateDock();
  updateTelemetry();
}

/* ------------------------------------------------------------------ HUD telemetry (v0.9) */
function updateTelemetry() {
  $("#tmMode").textContent = T(state.ai_mode === "direct" ? "modeDirect" : "modeAssistant").toUpperCase();
  const micOn = state.ui_mode === "audio" && !state.mic_muted && state.stt === "ready";
  $("#tmMic").textContent = state.ui_mode === "text" ? T("micText") : T(state.mic_muted ? "micMuted" : "micLive");
  $("#tmMicLed").className = "led " + (micOn ? "on" : state.mic_muted ? "off" : "");
  $("#tmAi").textContent = T(state.voice_enabled ? "aiVoiceOn" : "aiVoiceOff");
  $("#tmAiLed").className = "led " + (state.voice_enabled ? "on" : "off");
}

function tickClock() {
  const d = new Date(), lc = document.documentElement.lang;
  const hm = d.toLocaleTimeString(lc, { hour: "2-digit", minute: "2-digit" });
  $("#clock").textContent = $("#tmClock").textContent = hm;
  $("#tmDate").textContent = d.toLocaleDateString(lc, { weekday: "short", day: "2-digit", month: "short" }).toUpperCase();
}

// Interrupt only when something is running; repeat only when NEXUS already said something (v0.8).
const BUSY = ["speaking", "paused", "thinking", "transcribing", "listening"];
function updateDock() {
  $("#btnInterrupt").disabled = !(streaming || BUSY.includes(voiceState));
  $("#btnRepeat").disabled = !(state.can_repeat || $("#chat .msg.nexus"));
}

function applyState(st) {
  state = { ...state, ...st };
  $("#app").dataset.mode = state.ui_mode;
  $("#btnModeText").classList.toggle("on", state.ui_mode === "text");
  $("#btnModeAudio").classList.toggle("on", state.ui_mode === "audio");
  $("#btnMic").classList.toggle("off", state.mic_muted);
  $("#btnAiVoice").classList.toggle("off", !state.voice_enabled);
  $("#btnMic").disabled = $("#btnAiVoice").disabled = state.ui_mode === "text";
  $$("[data-ai-mode]").forEach((b) => b.classList.toggle("on", b.dataset.aiMode === state.ai_mode));
  $("#btnTemp").classList.toggle("on", state.temporary);
  $("#tempBadge").hidden = !state.temporary;
  $("#app").classList.toggle("transcript", transcriptOn);
  $("#btnTranscript").classList.toggle("on", transcriptOn);
  $("#btnTranscript").disabled = state.ui_mode === "text";
  $("#app").classList.toggle("temporary", state.temporary);
  const ws = state.workspace;
  $("#app").classList.toggle("ws-mode", !!ws);
  $("#wsBar").hidden = $("#wsPanel").hidden = !ws;
  if (ws) $("#wsName").textContent = ws.name;
  $("#app").classList.toggle("focus", !!state.focus);
  $("#btnFocus").classList.toggle("on", !!state.focus);
  if (state.ai_target) renderAiTarget();
  if (state.network) {
    const eff = state.network === "auto" ? (state.network_effective || "hybrid") : state.network;
    $("#chipNet").textContent = (state.network === "auto" ? T("netChip_auto") + " · " : "") + T("netChip_" + eff);
    $("#chipNet").classList.toggle("offline", eff === "offline");
    const q = state.net_quality || {};
    $("#chipNet").title = q.latency_ms ? `${q.latency_ms} ms · ${q.mbps ?? "?"} Mbit/s` : "";
    loadFonts(eff);
  }
  if (state.ui_mode === "text") setTimeout(() => $("#prompt").focus(), 300);
  setVoiceState(voiceState === "speaking" ? "speaking" : "idle");
}

/* ------------------------------------------------------------------ ring: grows with NEXUS's voice, shrinks with the user's */
let ringEnv = null, ringEnvStart = 0, ringEnvDt = 0.04, ringMicTarget = 0, ringAi = 0, ringMic = 0;

function ringSpeak(p) {
  ringEnv = p.env;
  ringEnvDt = p.dt;
  ringEnvStart = performance.now();
}

// v0.16: the loop sleeps while NEXUS is quiet. v0.15 ran it 60x/s forever: 3 CSS variables rewritten every frame
// (each one restyles the whole ring and its glow) plus the pulse trace - ~210 DOM writes per second doing nothing.
// The idle "breathing" is a CSS animation of the core now; voice and mic levels wake the loop up.
let ringRunning = false, ringLast = { s: "", ai: "", mic: "" };
function wakeRing() {
  if (!ringRunning && !$("#app").classList.contains("bg")) { ringRunning = true; requestAnimationFrame(ringFrame); }
}
function ringFrame(now) {
  if ($("#app").classList.contains("bg")) { ringRunning = false; return; }  // v0.14: no work while unfocused
  let aiTarget = 0;
  const speaking = ringEnv && voiceState === "speaking";
  if (speaking) {
    const i = Math.floor((now - ringEnvStart) / 1000 / ringEnvDt);
    aiTarget = i < ringEnv.length ? ringEnv[i] : 0;
  }
  ringAi += (aiTarget - ringAi) * 0.3;
  ringMic += (ringMicTarget - ringMic) * 0.3;
  ringMicTarget *= 0.9;  // mic levels arrive ~16x/s; decay between updates
  const ring = $("#ring"), v = { s: (1 + 0.14 * ringAi - 0.12 * ringMic).toFixed(3), ai: ringAi.toFixed(2), mic: ringMic.toFixed(2) };
  for (const k of ["s", "ai", "mic"]) if (v[k] !== ringLast[k]) { ring.style.setProperty("--" + k, v[k]); ringLast[k] = v[k]; ringWrites++; }
  if (!speaking && ringAi < 0.004 && ringMic < 0.004 && ringMicTarget < 0.004) { ringRunning = false; return; }
  requestAnimationFrame(ringFrame);
}
let ringWrites = 0;  // diagnostics: CSS variable writes (read by the tests/benchmarks)

/* ------------------------------------------------------------------ captions & notices (audio mode has no chat) */
let captionTimer;
function applyInterface() {
  const app = $("#app");
  app.classList.toggle("no-hud", settings.show_hud === false);
  app.classList.toggle("reduce-motion", !!settings.reduce_motion);
  setColors(settings);
  applyBars();
  app.classList.toggle("wander", settings.ring_wander !== false);
  $("#btnSkillsRail").hidden = !feature("skills");
  // v0.15.5: beta features that are off disappear from the interface (Settings > Beta)
  $("#btnWorkspaces").hidden = !feature("workspace");
  $("#btnLibrary").hidden = !feature("library");
  $("#btnSkills").hidden = !feature("skills");
  const anyWork = feature("workspace") || feature("library");
  $('#railRight [data-i18n="wsRail"]').hidden = !anyWork;
  $('#railRight [data-i18n="convTitle"]').classList.toggle("rail-sep", anyWork);
}

/* ------------------------------------------------------------------ v0.16 shortcuts and guide HUD */
const openPanel = () => { loadDashboard(); $("#panelDrawer").hidden = false; };
const SHORTCUTS = [
  { keys: "F1", label: "kGuide" },
  { keys: "Ctrl+Espaço", label: "kTalk" },
  { keys: "Ctrl+1", key: "1", panel: "panelDrawer", label: "kPanel", run: openPanel },
  { keys: "Ctrl+2", key: "2", panel: "convDrawer", label: "kConvs", run: () => openConversations("threads") },
  { keys: "Ctrl+3", key: "3", panel: "notifDrawer", label: "kNotif", run: () => openNotifications() },
  { keys: "Ctrl+4", key: "4", panel: "libDrawer", label: "kLibrary", feature: "library", run: () => openLibrary() },
  { keys: "Ctrl+5", key: "5", panel: "wsDrawer", label: "kWorkspace", feature: "workspace", run: () => openWorkspaces() },
  { keys: "Ctrl+6", key: "6", panel: "skillsDrawer", label: "kSkills", feature: "skills", run: () => openSkills() },
  { keys: "Ctrl+,", key: ",", panel: "settings", label: "kSettings", run: () => openSettings() },
  { key: "h", panel: "convDrawer", run: () => openConversations("threads") },  // v0.10 aliases (not listed)
  { key: "j", panel: "notifDrawer", run: () => openNotifications() },
  { keys: "Ctrl+M", key: "m", label: "kMode", run: () => dock(state.ui_mode === "audio" ? "text" : "audio") },
  { keys: "Ctrl+Shift+N", label: "kNewConv" },
  { keys: "Ctrl+T", label: "kTranscript" },
  { keys: "Ctrl+Shift+X", label: "kToasts" },
  { keys: "Esc", label: "kStop" },
  { keys: "F11", label: "kFull" },
  { keys: "Ctrl+Shift+M", label: "kMin" },
  { keys: "Ctrl+Shift+Q", label: "kQuit" },
];
const SHORTCUT_KEYS = Object.fromEntries(SHORTCUTS.filter((x) => x.key).map((x) => [x.key, x]));

function toggleGuide(on) {
  const g = $("#guide"), show = on ?? g.hidden;
  if (show) {
    $("#guideKeys").innerHTML = SHORTCUTS.filter((x) => x.keys && (!x.feature || feature(x.feature)))
      .map((x) => `<li><kbd>${esc(x.keys.replace("Espaço", T("kSpace")))}</kbd><span>${esc(T(x.label))}</span></li>`).join("");
  }
  g.hidden = !show;
}

/* beta features (v0.15.5): developer mode turns all of them on */
function feature(name) { return settings.app_mode === "developer" || !!settings["beta_" + name]; }

function renderBeta() {
  const f = $("#settingsForm"), dev = (f.elements.app_mode.value || settings.app_mode) === "developer";
  $$("#modeCards [data-app-mode]").forEach((b) => b.classList.toggle("on", b.dataset.appMode === (dev ? "developer" : "user")));
  $$("#betaList input").forEach((el) => { el.disabled = dev; if (dev) el.checked = true; else el.checked = !!settings[el.name]; });
  $("#betaList").classList.toggle("dim", dev);
  $("#betaDevHint").hidden = !dev;
}

function caption(text, ms = 3000) {
  if (state.ui_mode !== "audio" || !text || settings.show_captions === false) return;
  const el = $("#caption");
  el.textContent = text.length > 160 ? text.slice(0, 157) + "…" : text;
  el.classList.add("show");
  clearTimeout(captionTimer);
  captionTimer = setTimeout(() => el.classList.remove("show"), ms);
}

/* v0.16.1 notices: the same text is never stacked (it counts ×2, ×3), each one leaves on its own timer, at most
   3 on screen, ✕ closes one, Ctrl+Shift+X closes all, "more" shows a short explanation. */
const TOAST_MAX = 3, TOAST_MS = 7000;
function notice(text, more = "") {
  if (!text) return null;
  const box = $("#toasts");
  const same = [...box.querySelectorAll(".toast[data-text]")].find((t) => t.dataset.text === text);
  if (same) {
    same.dataset.n = +(same.dataset.n || 1) + 1;
    same.querySelector(".t-count").textContent = "×" + same.dataset.n;
    armToast(same);
    return same;
  }
  const el = document.createElement("div");
  el.className = "toast";
  el.dataset.text = text;
  el.innerHTML = `<div class="t-head"><b>NEXUS</b><i class="t-count"></i>`
    + (more ? `<button class="t-more" type="button">${esc(T("toastMore"))}</button>` : "")
    + `<button class="t-x" type="button" title="${esc(T("close"))}">✕</button></div><p class="t-text">${esc(text)}</p>`
    + (more ? `<p class="t-detail" hidden>${esc(more)}</p>` : "");
  el.querySelector(".t-x").onclick = () => el.remove();
  const mb = el.querySelector(".t-more");
  if (mb) mb.onclick = () => {
    const d = el.querySelector(".t-detail");
    d.hidden = !d.hidden;
    mb.textContent = T(d.hidden ? "toastMore" : "toastLess");
  };
  el.onmouseenter = () => clearTimeout(el._t);
  el.onmouseleave = () => armToast(el, 3000);
  box.appendChild(el);
  while (box.querySelectorAll(".toast").length > TOAST_MAX) box.querySelector(".toast").remove();
  armToast(el);
  return el;
}
function armToast(el, ms = TOAST_MS) {
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.classList.add("leaving"); setTimeout(() => el.remove(), 280); }, ms);
}
function closeToasts() { $$("#toasts .toast").forEach((t) => t.remove()); }

/* ------------------------------------------------------------------ edge bars: top bar and dock appear near the screen edges */
const EDGE_TOP = 64, EDGE_BOTTOM = 110, EDGE_SIDE = 56;
const barTimers = {};
function showBar(el, on) {
  clearTimeout(barTimers[el.id]);
  if (on) return el.classList.add("show");
  barTimers[el.id] = setTimeout(() => el.classList.remove("show"), 220);  // v0.16.1: was 900 ms - felt stuck
}

// v0.16.1: every menu is "hover" (appears at its screen edge), "fixed" or "off"; the shortcuts-only layout has none.
const BAR_SETTING = { topbar: "bar_top", railLeft: "bar_left", railRight: "bar_right", dock: "bar_bottom" };
function barMode(id) { return settings.ui_layout === "shortcuts" ? "off" : settings[BAR_SETTING[id]] || "hover"; }
function applyBars() {
  $("#app").classList.toggle("layout-shortcuts", settings.ui_layout === "shortcuts");
  for (const id of Object.keys(BAR_SETTING)) {
    const el = $("#" + id), m = barMode(id);
    el.hidden = m === "off";
    el.classList.toggle("fixed", m === "fixed");
    el.classList.toggle("show", m === "fixed");
  }
}

function trackEdges(e) {
  pointerActive();
  activity();
  const hover = (id) => $("#" + id).matches(":hover");
  const edge = { topbar: e.clientY < EDGE_TOP, dock: e.clientY > innerHeight - EDGE_BOTTOM,
    railLeft: e.clientX < EDGE_SIDE, railRight: e.clientX > innerWidth - EDGE_SIDE };
  for (const id of Object.keys(edge)) if (barMode(id) === "hover") showBar($("#" + id), edge[id] || hover(id));
}

// The name in the corner (and the F1 hint) only show while the mouse moves.
let pointerTimer;
function pointerActive() {
  $("#app").classList.add("pointer");
  clearTimeout(pointerTimer);
  pointerTimer = setTimeout(() => $("#app").classList.remove("pointer"), 2600);
}

// Rest: no interaction for a while -> texts go away and only the ring stays, playing (Settings > Interface).
let lastActivity = Date.now();
function activity() {
  lastActivity = Date.now();
  $("#app").classList.remove("resting");
}
setInterval(() => {
  const min = +settings.rest_minutes || 0;
  if (!min || state.ui_mode === "text" || state.workspace || aiBusy || ["speaking", "listening", "thinking"].includes(voiceState)) return;
  if (Date.now() - lastActivity > min * 60000) $("#app").classList.add("resting");
}, 5000);

/* Only one menu at a time: opening one (click or shortcut) closes the one that was open. */
const EXCLUSIVE = ["panelDrawer", "convDrawer", "wsDrawer", "skillsDrawer", "libDrawer", "settings", "notifDrawer", "guide"];
function initExclusivePanels() {
  const obs = new MutationObserver((muts) => {
    for (const m of muts) if (!m.target.hidden) for (const id of EXCLUSIVE) if (id !== m.target.id) $("#" + id).hidden = true;
  });
  for (const id of EXCLUSIVE) obs.observe($("#" + id), { attributes: true, attributeFilter: ["hidden"] });
}
const isOpen = (id) => !$("#" + id).hidden;

/* Menus can be dragged by their top area. */
function initMovable() {
  let drag = null;
  document.addEventListener("mousedown", (e) => {
    const box = e.target.closest(".drawer-box, .conv-box, .modal-box");
    if (!box || e.button !== 0 || box.closest("#confirmModal")) return;
    if (e.target.closest("button, input, select, textarea, a, label, .list, .chat, .conv-body, .set-body *, .reader-text, .file-view, .book-grid")) return;
    const r = box.getBoundingClientRect();
    if (e.clientY - r.top > 52) return;
    const [x0, y0] = (box.style.translate || "0px 0px").split(" ").map((v) => parseFloat(v) || 0);
    drag = { box, sx: e.clientX, sy: e.clientY, x0, y0 };
    box.classList.add("moving");
    e.preventDefault();
  });
  document.addEventListener("mousemove", (e) => {
    if (drag) drag.box.style.translate = `${drag.x0 + e.clientX - drag.sx}px ${drag.y0 + e.clientY - drag.sy}px`;
  });
  document.addEventListener("mouseup", () => { if (drag) drag.box.classList.remove("moving"); drag = null; });
}

/* Window state: no window buttons in full screen */
function setFull(on) { state.fullscreen = on; $("#app").classList.toggle("is-full", on); }
async function toggleFull() { setFull(await api().toggle_fullscreen()); }

const BARS = ["topbar", "dock", "railLeft", "railRight"];
function flashBars() {  // show every bar briefly once, so the user discovers them
  BARS.forEach((id) => $("#" + id).classList.add("show"));
  setTimeout(() => BARS.forEach((id) => showBar($("#" + id), false)), 3500);
}

async function setAiMode(mode) {
  const st = await api().set_ai_mode(mode);
  applyState(st);
  showTip(T({ direct: "modeDirect", study: "modeStudy" }[mode] || "modeAssistant"));
  if (st.spoken) { caption(st.spoken, 3000); addMsg("system", st.spoken); }
}

function toggleTranscript() {
  transcriptOn = !transcriptOn;
  try { localStorage.setItem("nexus.transcript", transcriptOn ? "1" : "0"); } catch (e) { /* ignore */ }
  applyState({});
  $("#chat").scrollTop = $("#chat").scrollHeight;
}

async function copyText(text, btn) {
  try { await navigator.clipboard.writeText(text); } catch (e) {  // WebView without clipboard permission
    const ta = Object.assign(document.createElement("textarea"), { value: text });
    document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove();
  }
  btn.textContent = T("copied"); btn.classList.add("done");
  setTimeout(() => { btn.textContent = T("copy"); btn.classList.remove("done"); }, 1400);
}

async function toggleTemporary() {
  const st = await api().set_temporary(!state.temporary);
  applyState(st);
  $("#chat").innerHTML = "";
  if (st.temporary) addMsg("system", T("tempStarted"));
  else for (const m of await api().history()) addMsg(m.role === "user" ? "user" : "nexus", m.content);
  caption(T(st.temporary ? "tempStarted" : "tempEnded"), 3000);
}

async function dock(action) {
  if (action === "text" || action === "audio") applyState(await api().set_mode(action));
  else if (action === "mic") {
    const st = await api().set_mic(!state.mic_muted);
    applyState(st);
    if (!st.mic_muted && st.stt !== "ready") notice(T("voiceLoading"), T("moreVoice"));
  } else if (action === "ai") applyState(await api().set_ai_voice(!state.voice_enabled));
  else if (action === "interrupt") { if ($("#btnInterrupt").disabled) return; api().interrupt(); setVoiceState("idle"); }
  else if (action === "transcript") toggleTranscript();
  else if (action === "repeat") {
    const r = await api().repeat();
    if (r.text) addMsg("nexus", r.intro + "\n\n" + r.text); else addMsg("system", r.intro);
    caption(r.intro, 2500);
  }
  const tip = { text: "modeText", audio: "modeAudio", mic: state.mic_muted ? "micOff" : "micOn", ai: state.voice_enabled ? "aiOn" : "aiOff",
    interrupt: "interrupt", repeat: "repeat", transcript: "transcript" }[action];
  showTip(T(tip));
}

let tipTimer;
function showTip(text) {
  const el = $("#dockTip");
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(tipTimer);
  tipTimer = setTimeout(() => el.classList.remove("show"), 1600);
}

/* ------------------------------------------------------------------ dashboard */
async function loadDashboard() {
  dash = await api().dashboard();
  profile = dash.profile;
  renderDashboard(dash);
}

function fmtWhen(iso) {
  if (!iso) return "";
  const d = new Date(iso), now = new Date();
  const day = (x) => x.toDateString();
  const tomorrow = new Date(now); tomorrow.setDate(now.getDate() + 1);
  const hm = iso.length > 10 ? iso.slice(11, 16) : "";
  if (day(d) === day(now)) return `${T("today")} ${hm}`;
  if (day(d) === day(tomorrow)) return `${T("tomorrow")} ${hm}`;
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)} ${hm}`;
}

const empty = (key) => `<li class="empty">${esc(T(key))}</li>`;

function renderDashboard(d) {
  renderProfile(d.profile);
  $("#eventList").innerHTML = d.events.map((e) => `
    <li><span class="when ${fmtWhen(e.start).startsWith(T("today")) ? "today" : ""}">${esc(fmtWhen(e.start))}</span>
      <span class="body">${esc(e.title)}${e.notes && e.notes !== "reminder" ? `<span class="meta">${esc(e.notes)}</span>` : ""}</span>
      <button class="x" data-del-event="${e.id}" title="✕">✕</button></li>`).join("") || empty("noEvents");
  $("#taskList").innerHTML = d.tasks.map((t) => `
    <li class="prio-${t.priority}"><button class="check-btn" data-done="${t.id}" aria-label="done"></button>
      <span class="body">${esc(t.title)}${t.due ? `<span class="meta">${esc(fmtWhen(t.due))}</span>` : ""}</span>
      <button class="x" data-del-task="${t.id}">✕</button></li>`).join("") || empty("noTasks");
  $("#memoryList").innerHTML = d.memories.map((m) => `
    <li><span class="body">${esc(m.content)}<span class="meta">${esc(m.category)} · ${esc(m.created.slice(0, 10))}${m.source === "auto" ? " · auto" : ""}</span></span>
      <button class="x" data-forget="${m.id}">✕</button></li>`).join("") || empty("noMemories");
  $("#actionList").innerHTML = d.actions.map((a) => `
    <li><span class="body">${esc(a.summary)}<span class="meta">${esc(a.ts.replace("T", " ").slice(0, 16))} · ${esc(a.kind)}</span></span></li>`).join("");
  $("#kbStats").innerHTML = d.knowledge.map((k) => `<span class="kb-stat">${catIcon(k.category)}${esc(k.category)}<b>${k.chunks}</b></span>`).join("");
  if (!$("#kbSearch").value) renderDocs(d.documents);
  $("#collectionList").innerHTML = d.collections.map((c) => `
    <li class="clickable" data-collection="${esc(c.collection)}"><span class="body">${esc(c.collection)}<span class="meta">${c.items} · ${esc(c.last.slice(0, 10))}</span></span></li>`).join("") || empty("noCollections");
  $("#noteList").innerHTML = d.notes.map((n) => `
    <li><span class="body"><b>${esc(n.title)}</b><span class="meta">${esc(n.content.slice(0, 140))}</span></span></li>`).join("") || empty("noNotes");
}

function renderDocs(docs) {
  $("#kbList").innerHTML = docs.map((doc) => `
    <li>${catIcon(doc.category)}<span class="body">${esc(doc.title)}<span class="meta">${esc(doc.category)} · ${esc(doc.source.split(":")[0])}</span></span>
      ${doc.source.startsWith("seed:") ? "" : `<button class="x" data-del-doc="${doc.id}">✕</button>`}</li>`).join("");
}

function renderProfile(p) {
  if (!p) {
    $("#profileCard").innerHTML = `<p class="muted small">${esc(T("noProfile"))}</p><button class="btn-ghost" id="btnOpenOnb">${esc(T("importProfile"))}</button>`;
    $("#btnOpenOnb").onclick = openOnboarding;
    return;
  }
  $("#profileCard").innerHTML = `
    <div class="name">${esc(p.name)}</div>
    <div class="role">${esc(p.profession || p.profile)}</div>
    ${p.routine ? `<div class="line">${esc(T("routine"))}: ${esc(p.routine)}</div>` : ""}
    ${p.goals?.length ? `<div class="line">${esc(T("goals"))}: ${esc(p.goals.join(", "))}</div>` : ""}
    <div class="tags">${(p.interests || []).map((i) => `<span class="tag">${esc(i)}</span>`).join("")}
      ${(p.modules || []).map((m) => `<span class="tag" style="border-color:var(--red-soft)">${esc(m)}</span>`).join("")}</div>`;
}

/* ------------------------------------------------------------------ onboarding & settings */
function openOnboarding() { $("#profileErr").textContent = ""; $("#onboarding").hidden = false; }

function onProfile(p) {
  profile = p.profile;
  $("#onboarding").hidden = true;
  applyLang(p.lang);
  addMsg("system", `${T("imported")}: ${p.profile.name}`);
  api().greet().then((t) => addMsg("nexus", t));
}

async function importResult(r) {
  if (r && r.ok === false && r.error) $("#profileErr").textContent = r.error;
}

// Opens instantly with the settings the UI already has; the AI status, model list, voices and microphones are
// fetched afterwards. (v0.6 and older waited for Python - and for Ollama while the model was loading - first.)
const LEADS = [1440, 120, 60, 30, 15, 10, 5];
let presets = [];

function leadLabel(m) { return m >= 1440 ? T("leadDay") : m >= 60 ? `${m / 60} h` : `${m} min`; }

function fillSettings() {
  const f = $("#settingsForm");
  for (const name of Object.values(BAR_SETTING)) {  // v0.16.1 menus: hover / fixed / off
    f.elements[name].innerHTML = ["hover", "fixed", "off"].map((v) => `<option value="${v}">${esc(T("bar_" + v))}</option>`).join("");
  }
  for (const [k, v] of Object.entries(settings)) {
    const el = f.elements[k];
    if (!el || el.type === "hidden" || el.tagName === "SELECT" && k === "llm_preset" && !presets.length) continue;
    if (el.type === "checkbox") el.checked = !!v; else el.value = v;
  }
  f.elements.network_mode.value = settings.network_mode || "hybrid";
  f.elements.app_mode.value = settings.app_mode || "user";
  f.elements.ui_layout.value = settings.ui_layout || "computer";
  $$("#layoutCards [data-layout]").forEach((b) => b.classList.toggle("on", b.dataset.layout === f.elements.ui_layout.value));
  const leads = String(settings.reminder_leads || "").split(",").map(Number);
  $("#leadChips").innerHTML = LEADS.map((m) => `<button type="button" class="chip-opt ${leads.includes(m) ? "on" : ""}" data-lead="${m}">${esc(leadLabel(m))}</button>`).join("")
    + `<span class="chip-opt on fixed">${esc(T("leadNow"))}</span>`;
  const [qf, qt] = String(settings.quiet_hours || "").split("-");
  $("#quietOn").checked = !!settings.quiet_hours; $("#quietFrom").value = qf || "22:00"; $("#quietTo").value = qt || "07:00";
  $("#briefingOn").checked = !!settings.daily_briefing; $("#briefingAt").value = settings.daily_briefing || "08:00";
  $$("output[data-for]", f).forEach(syncOutput);
  renderVoiceInfo();
}

function syncOutput(out) {
  const v = $("#settingsForm").elements[out.dataset.for].value;
  out.textContent = { tts_volume: v + "%", vad_silence: v + " s", tts_speed: (v > 0 ? "+" : "") + v }[out.dataset.for] ?? v;
}

function collectSettings() {
  const f = $("#settingsForm"), changes = {};
  f.elements.reminder_leads.value = [...$$("#leadChips [data-lead].on")].map((b) => b.dataset.lead).concat("0").join(",");
  f.elements.quiet_hours.value = $("#quietOn").checked ? `${$("#quietFrom").value}-${$("#quietTo").value}` : "";
  f.elements.daily_briefing.value = $("#briefingOn").checked ? $("#briefingAt").value : "";
  for (const el of f.elements) if (el.name) changes[el.name] = el.type === "checkbox" ? el.checked : el.value;
  // developer mode shows every beta box checked, but the user's own choices stay saved for user mode
  if (changes.app_mode === "developer") for (const el of $$("#betaList input")) changes[el.name] = !!settings[el.name];
  return changes;
}

function showSection(sec) {
  $$("#setNav [data-sec]").forEach((b) => b.classList.toggle("on", b.dataset.sec === sec));
  $$(".set-sec").forEach((x) => (x.hidden = x.dataset.sec !== sec));
}

function onPresetChange() {
  const f = $("#settingsForm"), pr = presets.find((x) => x.id === f.elements.llm_preset.value);
  if (!pr) return;
  if (pr.url) f.elements.llm_base_url.value = pr.url;
  if (pr.local && !f.elements.llm_api_key.value) f.elements.llm_api_key.value = "ollama";
  renderPresetHints();
}

function renderPresetHints() {
  const f = $("#settingsForm"), pr = presets.find((x) => x.id === f.elements.llm_preset.value);
  $("#cloudWarn").hidden = !pr || pr.local !== false;
  $("#keyRow").classList.toggle("dim", !!(pr && !pr.key));
}

function aiStatusHTML(llm) {
  if (!llm.online) return `<span class="bad">● ${esc(T("connFail", { error: (llm.error || "").slice(0, 120) }))}</span>`;
  return llm.model_ready ? `<span class="ok">● ${esc(T("connOk", { model: llm.model }))}</span>`
    : `<span class="bad">● ${esc(T("connNoModel", { model: llm.model }))}</span>`;
}

async function renderPerf() {
  const f = $("#settingsForm"), info = await api().performance_info();
  $$("#netCards [data-net]").forEach((b) => b.classList.toggle("on", b.dataset.net === (f.elements.network_mode.value || settings.network_mode)));
  $$("#perfCards [data-perf]").forEach((b) => b.classList.toggle("on", b.dataset.perf === settings.performance));
  const maxBtn = $('#perfCards [data-perf="max"]'), [kind, v] = (info.max_reason || ":").split(":");
  maxBtn.disabled = !info.max_allowed;
  $("#maxWhy").textContent = info.max_allowed ? "" : T(kind === "ram" ? "maxNoRam" : "maxNoVram", { v });
  const hw = info.hardware, gpu = hw.gpus.map((g) => `${g.name} · ${g.vram_gb} GB`).join(", ") || T("hwNone");
  const yes = (ok) => `<span class="${ok ? "ok" : "bad"}">${esc(T(ok ? "hwOk" : "hwNo"))}</span>`;
  $("#hwBox").innerHTML = `${esc(T("hwCpu"))}: ${esc(hw.cpu)} · ${hw.cores} threads<br>${esc(T("hwRam"))}: ${hw.ram_gb} GB<br>`
    + `${esc(T("hwGpu"))}: ${esc(gpu)}<br>${esc(T("hwCtx"))}: ${info.max_context || "—"}<br>`
    + `${esc(T("hwMin"))}: ${yes(info.minimum)} · ${esc(T("hwRec"))}: ${yes(info.recommended)}`;
}

async function pickProfile(name) {
  const r = await api().set_performance(name);
  settings = r.settings;
  fillSettings();
  applyInterface();
  applyState(r.state);
  renderPerf();
  showTip(T("perfApplied", { name: T({ economy: "perfEconomy", balanced: "perfBalanced", max: "perfMax" }[name]) }));
}

function openSettings(sec) {
  fillSettings();
  renderBeta();
  renderPerf();
  renderBackups();
  showSection(typeof sec === "string" ? sec : "general");
  $("#setSaved").textContent = "";
  $("#aiStatus").innerHTML = `<span class="muted">● ${esc(T("checking"))}</span>`;
  $("#settings").hidden = false;
  api().get_settings().then((r) => {
    presets = r.presets || [];
    const f = $("#settingsForm");
    f.elements.llm_preset.innerHTML = presets.map((x) => `<option value="${x.id}">${esc(x.name)}${x.local ? " · local" : ""}</option>`).join("");
    f.elements.llm_preset.value = settings.llm_preset || "ollama";
    renderPresetHints();
    $("#modelList").innerHTML = r.llm.models.map((m) => `<option value="${esc(m)}">`).join("");
    const mics = r.mics || { devices: [], default: "" };
    f.elements.mic_device.innerHTML = `<option value="">${esc(T("micDefault", { name: mics.default || "—" }))}</option>`
      + mics.devices.map((d) => `<option>${esc(d)}</option>`).join("");
    f.elements.mic_device.value = settings.mic_device || "";
    voices = r.voices || [];
    renderVoiceInfo();
    $("#aiStatus").innerHTML = aiStatusHTML(r.llm);
    setAi(r.llm);
  });
}

let voices = [];
function renderVoiceInfo() {
  const f = $("#settingsForm");
  const gender = f.elements.voice_gender.value;
  const list = voices.map((v) => `${v.name.replace("Microsoft ", "")} (${v.lang || "?"}, ${T(v.gender)})`).join(" · ");
  const missing = !voices.some((v) => v.lang === L && v.gender === gender);
  $("#voiceInfo").innerHTML = `${esc(T("installedVoices"))}: ${esc(list || "—")}`
    + (missing ? `<br><span class="warn">${esc(T("voiceMissing", { gender: T(gender), lang: L.toUpperCase() }))}</span>` : "");
}

async function testVoice() {
  const f = $("#settingsForm");
  const changes = { voice_gender: f.elements.voice_gender.value, voice_effect: f.elements.voice_effect.value,
    tts_speed: f.elements.tts_speed.value, tts_volume: f.elements.tts_volume.value };
  settings = (await api().save_settings(changes)).settings;
  api().test_voice(T("voiceSample", { name: profile ? profile.name.split(" ")[0] : "" }));
}

/* ------------------------------------------------------------------ wiring */
function wire() {
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); send($("#prompt").value); $("#prompt").value = ""; });
  const dockButtons = { btnModeText: "text", btnModeAudio: "audio", btnTranscript: "transcript", btnMic: "mic", btnAiVoice: "ai",
    btnInterrupt: "interrupt", btnRepeat: "repeat" };
  for (const [id, action] of Object.entries(dockButtons)) {
    $("#" + id).onclick = () => dock(action);
    $("#" + id).onmouseenter = (e) => showTip(e.currentTarget.title);
  }
  document.addEventListener("mousemove", trackEdges);
  $("#btnPanel").onclick = () => { loadDashboard(); $("#panelDrawer").hidden = false; };
  $$("[data-ai-mode]").forEach((b) => (b.onclick = () => setAiMode(b.dataset.aiMode)));
  $("#btnTemp").onclick = toggleTemporary;
  document.addEventListener("keydown", async (e) => {
    if (e.ctrlKey && e.code === "Space") {  // push-to-talk works in both modes
      e.preventDefault();
      const r = await api().push_to_talk();
      if (!r.ok) notice(T("voiceLoading") + (r.error && r.error !== "loading" ? ` (${r.error})` : ""), T("moreVoice"));
    }
    if (e.key === "Escape" && confirmId) { answerConfirm(false); return; }
    if (e.key === "F1" || (e.ctrlKey && e.key === "/")) { e.preventDefault(); toggleGuide(); return; }
    if (e.key === "Escape" && !$("#guide").hidden) { toggleGuide(false); return; }
    if (e.ctrlKey && !e.altKey && !e.shiftKey && SHORTCUT_KEYS[e.key]) {
      const sc = SHORTCUT_KEYS[e.key];
      e.preventDefault();
      if (sc.feature && !feature(sc.feature)) return;
      if (sc.panel && isOpen(sc.panel)) { $("#" + sc.panel).hidden = true; return; }  // same shortcut closes it
      toggleGuide(false);
      sc.run();
      return;
    }
    if (e.ctrlKey && e.shiftKey && !e.altKey) {
      const k = e.key.toLowerCase();
      const act = { m: () => api().minimize(), q: () => api().quit(), x: closeToasts }[k];
      if (act) { e.preventDefault(); act(); return; }
    }
    if (e.key === "Escape") {
      const open = $$(".modal:not([hidden]), .drawer:not([hidden])");
      if (open.length) open.forEach((m) => (m.hidden = true)); else dock("interrupt");
    }
    if (e.key === "F11") { e.preventDefault(); toggleFull(); }
    // v0.10 shortcuts: Ctrl+, settings · Ctrl+Shift+N new conversation · Ctrl+H conversations · Ctrl+J notifications
    // · Ctrl+T transcript (audio mode)
    if (e.ctrlKey && !e.altKey) {
      const k = e.key.toLowerCase();
      const act = { t: () => state.ui_mode === "audio" && toggleTranscript(), n: e.shiftKey ? newConversation : null }[k];
      if (act) { e.preventDefault(); act(); }
    }
  });

  // Click outside a modal/drawer box closes it (press and release on the backdrop, so selecting text doesn't).
  $$(".modal:not(#confirmModal), .drawer").forEach((m) => {
    let downOnBackdrop = false;
    m.addEventListener("mousedown", (e) => (downOnBackdrop = e.target === m));
    m.addEventListener("click", (e) => { if (downOnBackdrop && e.target === m) m.hidden = true; });
  });
  $("#chat").addEventListener("click", (e) => {
    const b = e.target.closest("[data-copy]");
    if (b) copyText(b.closest(".msg").querySelector(".txt").innerText, b);
  });
  $("#btnMinimize").onclick = () => api().minimize();
  $("#btnFullscreen").onclick = toggleFull;
  $("#btnPanelRail").onclick = openPanel;
  $$("#layoutCards [data-layout]").forEach((b) => (b.onclick = () => {
    $("#settingsForm").elements.ui_layout.value = b.dataset.layout;
    $$("#layoutCards [data-layout]").forEach((x) => x.classList.toggle("on", x === b));
  }));
  $("#btnSkillsRail").onclick = () => openSkills();
  $("#btnAiFix").onclick = () => { api().speak_help(aiHelpText); notice(aiHelpText, T("moreAi")); };
  document.addEventListener("keydown", activity);
  document.addEventListener("mousedown", activity);
  document.addEventListener("wheel", activity, { passive: true });
  initExclusivePanels();
  initMovable();
  $("#btnQuit").onclick = () => api().quit();

  $("#taskForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const v = $("#taskInput").value.trim();
    if (!v) return;
    $("#taskInput").value = "";
    await api().add_task(v, null);
    loadDashboard();
  });

  // Delegated list actions
  document.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-done],[data-del-task],[data-del-event],[data-forget],[data-del-doc],[data-collection]");
    if (!b) return;
    const d = b.dataset;
    if (d.done) await api().complete_task(d.done);
    else if (d.delTask) await api().delete_task(d.delTask);
    else if (d.delEvent) await api().delete_event(d.delEvent);
    else if (d.forget) await api().forget(d.forget);
    else if (d.delDoc) await api().delete_document(d.delDoc);
    else if (d.collection) return showCollection(d.collection);
    loadDashboard();
  });

  $$("#tabs button").forEach((b) => (b.onclick = () => {
    $$("#tabs button").forEach((x) => x.classList.toggle("on", x === b));
    $$(".tab-body").forEach((x) => (x.hidden = x.dataset.body !== b.dataset.tab));
  }));

  $("#btnImportKb").onclick = async () => {
    const res = await api().import_knowledge_files();
    res.forEach((r) => addMsg("system", r.ok ? `📚 ${T("imported")}: ${r.title} (${r.chunks} ${T("chunks")})` : `⚠ ${r.error}`));
  };
  $("#btnTeach").onclick = () => ($("#teachForm").hidden = !$("#teachForm").hidden);
  $("#teachForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    await api().learn($("#teachTitle").value, $("#teachContent").value, $("#teachCat").value);
    addMsg("system", `📚 ${T("imported")}: ${$("#teachTitle").value}`);
    e.target.reset(); e.target.hidden = true;
  });
  let kbTimer;
  $("#kbSearch").addEventListener("input", (e) => {
    clearTimeout(kbTimer);
    kbTimer = setTimeout(async () => {
      const q = e.target.value.trim();
      if (!q) return renderDocs(dash.documents);
      const hits = await api().search_knowledge(q);
      $("#kbList").innerHTML = hits.map((h) => `<li><span class="body"><b>${esc(h.heading)}</b><span class="meta">${esc(h.title)}</span>
        <span class="meta" style="font-family:var(--f-body);font-size:13px">${esc(h.content.slice(0, 260))}…</span></span></li>`).join("");
    }, 250);
  });

  $$("#langSwitch button").forEach((b) => (b.onclick = async () => {
    const r = await api().save_settings({ language: b.dataset.lang });
    settings = r.settings;
    applyLang(r.lang);
  }));

  $("#btnProfileFile").onclick = async () => importResult(await api().import_profile_file());
  $("#btnProfilePaste").onclick = async () => importResult(await api().import_profile_text($("#profileJson").value));
  $("#btnProfileSkip").onclick = () => ($("#onboarding").hidden = true);

  $("#btnSettings").onclick = openSettings;
  $("#btnGuide").onclick = () => toggleGuide(true);
  $("#guide").onclick = () => toggleGuide(false);
  const colorForm = $("#settingsForm");
  ["color_ring", "color_core", "color_bg"].forEach((n) => (colorForm.elements[n].oninput = () =>
    setColors({ color_ring: colorForm.elements.color_ring.value, color_core: colorForm.elements.color_core.value,
      color_bg: colorForm.elements.color_bg.value })));
  $("#btnColorsReset").onclick = () => {
    for (const [k, v] of Object.entries(COLOR_DEFAULTS)) colorForm.elements[k].value = v;
    setColors(COLOR_DEFAULTS);
  };
  $("#btnTestVoice").onclick = testVoice;
  $("#settingsForm").elements.voice_gender.onchange = renderVoiceInfo;
  $("#settingsForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const r = await api().save_settings(collectSettings());
    settings = r.settings;
    setAi(r.llm);
    applyLang(r.lang);
    applyInterface();
    applyState({ network: settings.network_mode, performance: settings.performance });
    if (!$("#wsBar").hidden && !feature("workspace")) exitWorkspace();  // Beta > workspace switched off inside one
    $("#settings").hidden = true;
  });
  $$("#setNav [data-sec]").forEach((b) => (b.onclick = () => showSection(b.dataset.sec)));
  $$("#modeCards [data-app-mode]").forEach((b) => (b.onclick = () => {
    const f = $("#settingsForm");
    if (f.elements.app_mode.value === "developer") for (const el of $$("#betaList input")) el.checked = !!settings[el.name];
    f.elements.app_mode.value = b.dataset.appMode;
    if (b.dataset.appMode === "developer") renderBeta();
    else {
      $$("#modeCards [data-app-mode]").forEach((x) => x.classList.toggle("on", x === b));
      $$("#betaList input").forEach((el) => (el.disabled = false));
      $("#betaList").classList.remove("dim");
      $("#betaDevHint").hidden = true;
    }
  }));
  $("#leadChips").addEventListener("click", (e) => e.target.closest("[data-lead]")?.classList.toggle("on"));
  $$("#settingsForm output[data-for]").forEach((out) => ($("#settingsForm").elements[out.dataset.for].oninput = () => syncOutput(out)));
  $("#settingsForm").elements.llm_preset.onchange = onPresetChange;
  $("#btnShowKey").onclick = () => {
    const k = $("#settingsForm").elements.llm_api_key, show = k.type === "password";
    k.type = show ? "text" : "password";
    $("#btnShowKey").textContent = T(show ? "hide" : "show");
  };
  $("#btnTestLlm").onclick = async () => {
    $("#aiStatus").innerHTML = `<span class="muted">● ${esc(T("checking"))}</span>`;
    const c = collectSettings(), llmFields = Object.fromEntries(Object.entries(c).filter(([k]) => k.startsWith("llm_")));
    const st = await api().test_llm(llmFields);
    Object.assign(settings, llmFields);
    $("#modelList").innerHTML = (st.models || []).map((m) => `<option value="${esc(m)}">`).join("");
    $("#aiStatus").innerHTML = aiStatusHTML(st);
    setAi(st);
  };
  $("#btnTestNotif").onclick = async () => { await api().save_settings(collectSettings()); api().test_notification(); };
  $("#btnBriefing").onclick = () => api().briefing_now();
  $("#btnOpenData").onclick = () => api().open_data_folder();
  $("#btnCenterRing").onclick = () => setRingPos(0, 0);
  $("#btnNotif").onclick = openNotifications;
  $("#netCards").addEventListener("click", (e) => {
    const b = e.target.closest("[data-net]");
    if (!b) return;
    $("#settingsForm").elements.network_mode.value = b.dataset.net;
    $$("#netCards [data-net]").forEach((x) => x.classList.toggle("on", x === b));
  });
  $("#perfCards").addEventListener("click", (e) => { const b = e.target.closest("[data-perf]"); if (b && !b.disabled) pickProfile(b.dataset.perf); });
  $("#btnNotifClear").onclick = async () => { await api().clear_notifications(); openNotifications(); };
  $("#btnReimport").onclick = () => { $("#settings").hidden = true; openOnboarding(); };
  $("#btnClearChat").onclick = async () => { await api().clear_history(); $("#chat").innerHTML = ""; $("#settings").hidden = true; };
  $("#btnReport").onclick = async () => {
    const r = await api().report_issue();
    if (r && r.ok) notice(T("reportSaved", { file: r.file.split(/[\\/]/).pop() }));
  };
  $$("[data-close]").forEach((b) => (b.onclick = () => (b.closest(".modal, .drawer").hidden = true)));

  tickClock();
  setInterval(tickClock, 1000);
  wireRingDrag();
  wireWorkspace();
  wireEssentials();
  wireLightness();
  wireLibrary();
  $("#btnNewConv").onclick = newConversation;
  $("#btnConvs").onclick = () => openConversations("threads");
  $$("#convTabs button").forEach((b) => (b.onclick = () => openConversations(b.dataset.ctab)));
  $("#convThreads").addEventListener("click", onConversationClick);
  $("#convAll").addEventListener("click", onConversationClick);
}

async function showCollection(name) {
  const rows = await api().collection(name);
  $("#recordView").innerHTML = `<div class="records"><b>${esc(name)}</b>${rows.map((r) => {
    const { id, created, ...rest } = r;
    return `<div>#${id} · ${esc(created.slice(0, 16).replace("T", " "))} · ${esc(Object.entries(rest).map(([k, v]) => `${k}: ${v}`).join(" · "))}</div>`;
  }).join("")}</div>`;
}

/* ------------------------------------------------------------------ knowledge icons (v0.9) */
const ICONS = {  // 24x24 line icons, one per area (pt/en/es category names map to the same icon)
  aid: '<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z"/>',
  philo: '<path d="M4 21h16M5 18h14M6 7h12M5 7l7-4 7 4M7 7v11M10.3 7v11M13.7 7v11M17 7v11"/>',
  money: '<circle cx="12" cy="12" r="9"/><path d="M15 9.2c-.5-1-1.6-1.6-3-1.6-1.8 0-3 .9-3 2.2 0 3 6 1.6 6 4.6 0 1.3-1.3 2.2-3 2.2-1.5 0-2.6-.6-3.1-1.7M12 6v1.6M12 16.6V18"/>',
  code: '<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>',
  health: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/><path d="M5.5 12h3l1.5-2.5 2 5 1.5-2.5h5"/>',
  focus: '<path d="M7 3h10M7 21h10M8 3c0 5 8 5 8 9s-8 4-8 9M16 3c0 5-8 5-8 9s8 4 8 9"/>',
  body: '<circle cx="12" cy="4.5" r="2"/><path d="M12 7v7M8 9.5h8M12 14l-3 7M12 14l3 7"/>',
  learned: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.6.5 1 1.2 1 2V16h5.2v-.2c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z"/>',
  book: '<path d="M4 4h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4zM20 4h-6a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h6z"/>',
  search: '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="1"/><path d="M3 10h18M8 3v4M16 3v4"/>',
};
const CAT_RULES = [[/socorr|first aid|auxilio/, "aid"], [/filosof|philosoph/, "philo"], [/finan/, "money"],
  [/program|codigo|code/, "code"], [/saud|health|salud/, "health"], [/produtiv|productiv/, "focus"],
  [/anatom/, "body"], [/aprend|learn/, "learned"], [/pesquis|research/, "search"], [/^voz|^voice/, "mic"],
  [/agenda|organiz/, "calendar"]];
function catIcon(category) {
  const c = String(category || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const key = (CAT_RULES.find(([rx]) => rx.test(c)) || [null, "book"])[1];
  return `<svg class="cat-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${ICONS[key]}</svg>`;
}

/* ------------------------------------------------------------------ draggable ring (v0.9) */
function setRingPos(dx, dy, save = true) {
  const max = (v, lim) => Math.max(-lim, Math.min(lim, v));
  dx = max(dx, innerWidth / 2 - 80); dy = max(dy, innerHeight / 2 - 80);
  $("#stage").style.setProperty("--dx", dx + "px");
  $("#stage").style.setProperty("--dy", dy + "px");
  if (save) try { localStorage.setItem("nexus.ringPos", JSON.stringify([dx, dy])); } catch (e) { /* ignore */ }
  return [dx, dy];
}

function wireRingDrag() {
  let pos = [0, 0];
  try { pos = JSON.parse(localStorage.getItem("nexus.ringPos")) || [0, 0]; } catch (e) { /* ignore */ }
  pos = setRingPos(pos[0], pos[1], false);
  const core = $("#core");
  core.title = T("ringDrag");
  let start = null;
  core.addEventListener("pointerdown", (e) => {
    if (state.ui_mode !== "audio" || e.button !== 0) return;
    start = { x: e.clientX, y: e.clientY, pos: [...pos], moved: false };
    core.setPointerCapture(e.pointerId);
  });
  core.addEventListener("pointermove", (e) => {
    if (!start) return;
    const dx = e.clientX - start.x, dy = e.clientY - start.y;
    if (!start.moved && Math.hypot(dx, dy) < 4) return;  // a click is not a drag
    start.moved = true;
    core.classList.add("dragging"); $("#stage").classList.add("dragging");
    pos = setRingPos(start.pos[0] + dx, start.pos[1] + dy, false);
  });
  const end = () => {
    if (start && start.moved) setRingPos(pos[0], pos[1]);
    start = null;
    core.classList.remove("dragging"); $("#stage").classList.remove("dragging");
  };
  core.addEventListener("pointerup", end);
  core.addEventListener("pointercancel", end);
  core.addEventListener("dblclick", () => (pos = setRingPos(0, 0)));
}

/* ------------------------------------------------------------------ conversations (v0.9) */
let convTab = "threads", timelineOldest = null;

async function openConversations(tab = convTab) {
  convTab = tab;
  $$("#convTabs button").forEach((b) => b.classList.toggle("on", b.dataset.ctab === tab));
  $("#convThreads").hidden = tab !== "threads";
  $("#convAll").hidden = tab !== "all";
  $("#convDrawer").hidden = false;
  await renderConversations();
}

function fmtDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString(document.documentElement.lang, { weekday: "short", day: "2-digit", month: "short", year: "numeric" })
    + " · " + iso.slice(11, 16);
}

async function renderConversations() {
  if (convTab === "threads") {
    const r = await api().conversations();
    $("#convThreads").innerHTML = r.list.map((c) => `
      <div class="conv-card ${c.id === r.current ? "current" : ""}" data-copen="${c.id}">
        <span class="t">${esc(c.title || "…")}${c.id === r.current ? `<span class="badge">${esc(T("convCurrent"))}</span>` : ""}</span>
        ${c.description ? `<span class="d">${esc(c.description)}</span>` : ""}
        <span class="m">${esc(fmtDate(c.updated))} · ${esc(T("convMsgs", { n: c.messages }))}</span>
        <span class="acts"><button data-crename="${c.id}" title="✎">✎</button><button data-cdel="${c.id}" title="✕">✕</button></span>
      </div>`).join("") || `<p class="muted">${esc(T("convEmpty"))}</p>`;
  } else {
    timelineOldest = null;
    $("#convAll").innerHTML = "";
    await loadTimeline(true);
  }
}

async function loadTimeline(first = false) {
  const rows = await api().timeline(timelineOldest);
  if (!rows.length) { if (first) $("#convAll").innerHTML = `<p class="muted">${esc(T("convEmpty"))}</p>`; return; }
  timelineOldest = rows[0].id;
  let html = "", day = "", conv = null;
  for (const m of rows) {
    const d = m.ts.slice(0, 10);
    if (d !== day) { day = d; conv = null; html += `<div class="tl-day">${esc(new Date(m.ts).toLocaleDateString(document.documentElement.lang, { weekday: "long", day: "2-digit", month: "long", year: "numeric" }).toUpperCase())}</div>`; }
    if (m.conversation_id !== conv) { conv = m.conversation_id; html += `<div class="tl-conv" data-copen="${conv}">▸ ${esc(m.title || "…")}</div>`; }
    html += `<div class="tl-msg ${m.role}"><time>${esc(m.ts.slice(11, 16))}</time><span>${esc(m.content)}</span></div>`;
  }
  const box = $("#convAll"), oldHeight = box.scrollHeight;
  $(".conv-more", box)?.remove();
  box.insertAdjacentHTML("afterbegin", (rows.length >= 200 ? `<button class="btn-ghost conv-more" data-cmore>${esc(T("convLoadMore"))}</button>` : "") + html);
  if (first) box.scrollTop = box.scrollHeight; else box.scrollTop = box.scrollHeight - oldHeight;
}

async function onConversationClick(e) {
  const b = e.target.closest("[data-copen],[data-cdel],[data-crename],[data-cmore]");
  if (!b) return;
  const d = b.dataset;
  if (d.cmore !== undefined) return loadTimeline();
  if (d.cdel) { e.stopPropagation(); if (confirm(T("convDelete"))) { await api().delete_conversation(d.cdel); renderConversations(); } return; }
  if (d.crename) {
    e.stopPropagation();
    const card = b.closest(".conv-card"), title = prompt(T("convRename"), $(".t", card).firstChild.textContent);
    if (title) { await api().rename_conversation(d.crename, title); renderConversations(); }
    return;
  }
  if (window.getSelection().toString()) return;  // selecting text is not opening
  const r = await api().open_conversation(d.copen);
  if (!r.ok) return;
  applyState(r);
  $("#chat").innerHTML = "";
  for (const m of r.messages) addMsg(m.role === "user" ? "user" : "nexus", m.content);
  setVoiceState("idle");
  $("#convDrawer").hidden = true;
  const title = $(`[data-copen="${d.copen}"] .t`)?.firstChild?.textContent || $(`[data-copen="${d.copen}"]`)?.textContent.replace("▸", "").trim() || "";
  caption(T("convOpened", { title }), 3500);
  showTip(T("convOpened", { title }));
}

async function newConversation() {
  applyState(await api().new_conversation());
  $("#chat").innerHTML = "";
  addMsg("system", T("convNew"));
  setVoiceState("idle");
  caption(T("convNew"), 2500);
}

/* ------------------------------------------------------------------ focus mode (v0.11) */
async function toggleFocus() {
  const st = await api().set_focus(!state.focus);
  applyState(st);
  showTip(T(st.focus ? "focusOn" : "focusOff"));
}

/* ------------------------------------------------------------------ workspace (v0.11) */
async function openWorkspaces() {
  const list = await api().workspaces();
  $("#wsList").innerHTML = list.map((w) => `
    <div class="conv-card ${state.workspace && state.workspace.id === w.id ? "current" : ""}" data-wsopen="${w.id}">
      <span class="t">${esc(w.name)}</span>
      ${w.description ? `<span class="d">${esc(w.description)}</span>` : ""}
      <span class="m">${esc(T("wsMeta", { n: w.files, date: fmtDate(w.updated) }))}</span>
      <span class="acts"><button data-wsdel="${w.id}" title="✕">✕</button></span>
    </div>`).join("") || `<p class="muted">${esc(T("wsEmpty"))}</p>`;
  $("#wsDrawer").hidden = false;
  setTimeout(() => $("#wsNewName").focus(), 50);
}

function enterWorkspaceView(r) {
  applyState(r);
  $("#chat").innerHTML = "";
  addMsg("system", T("wsEntered", { name: r.workspace.name }));
  for (const m of r.messages || []) addMsg(m.role === "user" ? "user" : "nexus", m.content);
  renderWsPanel(r);
  $("#wsDrawer").hidden = true;
  setVoiceState("idle");
  setTimeout(() => $("#prompt").focus(), 200);
}

async function exitWorkspace() {
  const r = await api().close_workspace();
  applyState(r);
  $("#chat").innerHTML = "";
  addMsg("system", T("wsLeft"));
  for (const m of r.messages || []) addMsg(m.role === "user" ? "user" : "nexus", m.content);
  setVoiceState("idle");
}

function fmtSize(b) { return b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(1)} MB`; }

function renderWsPanel(v) {
  if (!v || !v.files) return;
  const files = v.files;
  $("#wsCount").textContent = files.length ? ` · ${files.filter((f) => !f.dir).length}` : "";
  $("#wsFiles").innerHTML = files.map((f) => {
    const depth = f.path.split("/").length - 1, name = f.path.split("/").pop();
    return `<li class="${f.dir ? "dir" : "file"}" style="--d:${depth}" ${f.dir ? "" : `data-wsfile="${esc(f.path)}"`}>
      <span>${f.dir ? "▸ " : ""}${esc(name)}</span>${f.dir ? "" : `<small>${fmtSize(f.size)}</small>`}</li>`;
  }).join("") || `<li class="empty">${esc(T("wsEmptyFiles"))}</li>`;
  $("#wsChanges").innerHTML = (v.changes || []).map((c) => `
    <li><span><b>${esc(T("op_" + c.op))}</b> ${esc(c.path)}<small>${esc(c.ts.slice(11, 16))}</small></span>
      ${c.op === "command" ? "" : `<button class="link-btn" data-wsundo="${c.id}">${esc(T("wsUndo"))}</button>`}</li>`).join("")
    || `<li class="empty">${esc(T("wsNoChanges"))}</li>`;
}

async function viewFile(path) {
  const r = await api().read_workspace_file(path);
  $("#filePath").textContent = path;
  $("#fileView").textContent = r.error || r.content + (r.truncated ? "\n…" : "");
  $("#fileModal").hidden = false;
}

async function undoChange(id) {
  const r = await api().undo_workspace(id || null);
  renderWsPanel(r);
  if (r.ok) showTip(T("wsUndone", { path: r.path }));
}

let confirmId = null;
function askConfirm(p) {
  confirmId = p.id;
  $("#confirmCmd").textContent = p.command;
  $("#confirmModal").hidden = false;
  chime();
}
function closeConfirm(ok) {
  $("#confirmModal").hidden = true;
  if (confirmId) showTip(T(ok ? "allowed" : "denied"));
  confirmId = null;
}
function answerConfirm(ok) {
  if (!confirmId) return;
  api().confirm_command(confirmId, ok);
  closeConfirm(ok);
}

function wireWorkspace() {
  $("#btnWorkspaces").onclick = openWorkspaces;
  $("#btnFocus").onclick = toggleFocus;
  $("#wsNew").addEventListener("submit", async (e) => {
    e.preventDefault();
    const r = await api().create_workspace($("#wsNewName").value, $("#wsNewDesc").value);
    e.target.reset();
    enterWorkspaceView(r);
  });
  $("#wsList").addEventListener("click", async (e) => {
    const del = e.target.closest("[data-wsdel]"), open = e.target.closest("[data-wsopen]");
    if (del) {
      e.stopPropagation();
      if (confirm(T("wsDelete"))) {
        const wasOpen = state.workspace && String(state.workspace.id) === del.dataset.wsdel;
        await api().delete_workspace(del.dataset.wsdel);
        if (wasOpen) applyState(await api().state());
        openWorkspaces();
      }
    } else if (open) enterWorkspaceView(await api().open_workspace(open.dataset.wsopen));
  });
  $("#btnWsExit").onclick = exitWorkspace;
  $("#btnWsFolder").onclick = () => api().open_workspace_folder();
  $("#btnWsUndo").onclick = () => undoChange();
  $("#wsFiles").addEventListener("click", (e) => { const f = e.target.closest("[data-wsfile]"); if (f) viewFile(f.dataset.wsfile); });
  $("#wsChanges").addEventListener("click", (e) => { const b = e.target.closest("[data-wsundo]"); if (b) undoChange(b.dataset.wsundo); });
  $("#btnAllow").onclick = () => answerConfirm(true);
  $("#btnDeny").onclick = () => answerConfirm(false);
  $("#btnFileCopy").onclick = (e) => copyText($("#fileView").textContent, e.currentTarget);
}

/* ------------------------------------------------------------------ skills (v0.13) */
const SKILL_ICON = { organization: "agenda", finance: "finanças", programming: "programação", study: "aprendido",
  health: "saúde", knowledge: "filosofia", research: "pesquisa", voice: "voz" };
let skillsData = null;

function renderLvBadge(d) {
  skillsData = d;
  $("#lvRank").textContent = d.rank;
  $("#lvNum").textContent = `LV ${d.level}`;
  $("#lvBar").style.width = Math.round(d.progress * 100) + "%";
}

async function openSkills() {
  const d = await api().skills();
  renderLvBadge(d);
  $("#skRank").textContent = d.rank;
  $("#skLevel").textContent = `N.E.X.U.S · LV ${d.level}`;
  $("#skBar").style.width = Math.round(d.progress * 100) + "%";
  $("#skNext").textContent = `${d.total_xp} XP`;
  $("#skList").innerHTML = d.skills.map((x) => `
    <li>${catIcon(SKILL_ICON[x.skill] ?? x.skill)}<b>${esc(T("sk_" + x.skill))}</b>
      <span class="lv"><span>${x.rank}</span>LV ${x.level}</span>
      <i class="bar" title="${esc(T("skNext", { n: x.next }))}"><em style="width:${Math.round(x.progress * 100)}%"></em></i></li>`).join("");
  $("#skillsDrawer").hidden = false;
}

function onLevelUp(ups) {
  for (const u of ups) {
    const el = document.createElement("div");
    el.className = "toast levelup";
    el.innerHTML = `<b>${esc(T("levelUpTitle"))} · ${esc(u.rank)}</b>${esc(T("levelUp", { skill: T("sk_" + u.skill), level: u.level, rank: u.rank }))}`;
    $("#toasts").appendChild(el);
    setTimeout(() => el.remove(), 7000);
  }
  if (!state.focus) chime();
  api().skills().then(renderLvBadge);
}

/* ------------------------------------------------------------------ backups (v0.13) */
async function renderBackups(list) {
  list = list || await api().list_backups();
  $("#backupList").innerHTML = list.slice(0, 10).map((b) => `<li>${esc(b.name)} · ${fmtSize(b.size)}</li>`).join("")
    || `<li>${esc(T("backupNone"))}</li>`;
}

function wireEssentials() {
  $("#btnSkills").onclick = openSkills;
  $("#quickForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const r = await api().quick_profile($("#quickName").value, $("#quickProf").value, "");
    importResult(r);
  });
  $("#btnBackup").onclick = async () => {
    const r = await api().create_backup();
    if (r.ok) { notice(T("backupDone", { file: r.file.split(/[\\/]/).pop() })); renderBackups(r.backups); }
    else notice(r.error);
  };
  $("#btnRestore").onclick = async () => {
    const r = await api().restore_backup();
    if (r.ok) notice(T("restoreScheduled")); else if (r.error) notice(r.error);
  };
  $("#btnBackupFolder").onclick = () => api().open_backups_folder();
}

/* ------------------------------------------------------------------ background & AI switch (v0.14) */
let bgState = "visible";
function reportBackground() {
  const st = document.hidden ? "hidden" : document.hasFocus() ? "visible" : "blurred";
  if (st === bgState) return;
  bgState = st;
  const pause = st !== "visible" && settings.pause_when_unfocused !== false;
  $("#app").classList.toggle("bg", pause);
  if (!pause) wakeRing();
  if (window.pywebview && api()) api().set_background(st);
}

function renderAiTarget() {
  const api_ = state.ai_target === "api";
  $("#aiTargetName").textContent = T(api_ ? "aiTargetApi" : "aiTargetLocal");
  $("#btnAiTarget").classList.toggle("api", api_);
  $$("#aiSeg [data-target]").forEach((b) => b.classList.toggle("on", b.dataset.target === (state.ai_target || "local")));
}

async function switchAi(target) {
  const r = await api().switch_ai(target);
  settings = r.settings;
  applyState(r);
  setAi(r.llm);
  renderAiTarget();
  showTip(T("aiSwitched", { name: T(target === "api" ? "aiTargetApi" : "aiTargetLocal") }));
  if (r.need_setup) {
    openSettings("ai");
    const f = $("#settingsForm");
    if (!presets.length) await new Promise((res) => setTimeout(res, 400));
    const cloud = presets.find((x) => x.local === false);
    if (cloud && (!f.elements.llm_preset.value || presets.find((x) => x.id === f.elements.llm_preset.value)?.local)) {
      f.elements.llm_preset.value = cloud.id;
      onPresetChange();
      f.elements.llm_api_key.value = "";
    }
    notice(T("aiNeedSetup"));
  } else if (!$("#settings").hidden) openSettings("ai");
}

function wireLightness() {
  document.addEventListener("visibilitychange", reportBackground);
  window.addEventListener("blur", reportBackground);
  window.addEventListener("focus", reportBackground);
  $("#btnAiTarget").onclick = () => switchAi(state.ai_target === "api" ? "local" : "api");
  $("#aiSeg").addEventListener("click", (e) => {
    const b = e.target.closest("[data-target]");
    if (b && b.dataset.target !== (state.ai_target || "local")) switchAi(b.dataset.target);
  });
}

/* ------------------------------------------------------------------ attachments (v0.15) */
let pendingFiles = [];
function renderAttachChips() {
  const box = $("#attachChips");
  box.hidden = !pendingFiles.length;
  box.innerHTML = pendingFiles.map((f) => `<span class="att-chip">${catIcon(f.kind === "image" ? "" : f.kind)}${esc(f.name)}</span>`).join("")
    + (pendingFiles.length ? `<button class="link-btn" id="btnClearAtt">✕</button>` : "");
  const c = $("#btnClearAtt");
  if (c) c.onclick = async () => { await api().clear_attachments(); pendingFiles = []; renderAttachChips(); };
}

function afterAttach(r) {
  for (const x of r.results) if (!x.ok) notice(`${x.name}: ${x.error}`);
  pendingFiles = r.pending || [];
  renderAttachChips();
  if (pendingFiles.length) $("#prompt").focus();
}

async function attachDropped(fileList) {
  const paths = [...fileList].map((f) => f.pywebviewFullPath).filter(Boolean);
  if (paths.length) return afterAttach(await api().attach_files(paths));
  for (const f of fileList) {  // no path from the WebView: send the bytes
    if (f.size > 25 * 1024 * 1024) { notice(`${f.name}: > 25 MB`); continue; }
    const data = await new Promise((res) => { const r = new FileReader(); r.onload = () => res(r.result); r.readAsDataURL(f); });
    afterAttach(await api().attach_blob(f.name, data));
  }
}

/* ------------------------------------------------------------------ library & podcast (v0.15) */
let readerBook = null, readerPage = null;
async function openLibrary() {
  renderBooks(await api().books());
  $("#libDrawer").hidden = false;
}

function renderBooks(books) {
  $("#libList").innerHTML = books.map((b) => `
    <div class="book-card">
      <div class="book-spine">${catIcon(b.kind === "pdf" ? "" : "aprendido")}<span class="mono">${esc(b.kind.toUpperCase())}</span></div>
      <b class="t">${esc(b.title)}</b>
      <div class="book-progress"><em style="width:${Math.round(b.progress * 100)}%"></em></div>
      <span class="m mono">${Math.round(b.progress * 100)}% · ${Math.round(b.chars / 1000)}k</span>
      <div class="book-acts"><button class="btn-ghost" data-bread="${b.id}">${esc(T("libRead"))}</button>
        <button class="btn-primary" data-blisten="${b.id}">${esc(T("libListen"))}</button>
        <button class="link-btn" data-bdel="${b.id}">✕</button></div>
    </div>`).join("") || `<p class="muted">${esc(T("libEmpty"))}</p>`;
}

async function addBooks(paths) {
  const r = await api().add_books(paths || null);
  for (const x of r.results) if (!x.ok) notice(`${x.file.split(/[\\/]/).pop()}: ${x.error}`);
  const ok = r.results.filter((x) => x.ok).length;
  if (ok) showTip(T("libAdded", { n: ok }));
  renderBooks(r.books);
}

async function openReader(bid, position) {
  const r = await api().book_page(bid, position ?? null);
  if (r.error) return;
  readerBook = r.book; readerPage = r;
  $("#readerTitle").textContent = r.book.title;
  $("#readerText").textContent = r.text;
  $("#readerText").scrollTop = 0;
  const pct = Math.round((r.start / Math.max(r.chars, 1)) * 100);
  $("#readerProgress").style.width = pct + "%";
  $("#readerPct").textContent = pct + "%";
  $("#btnPrevPage").disabled = r.start <= 0;
  $("#btnNextPage").disabled = r.end >= r.chars;
  $("#readerModal").hidden = false;
}

function onPodcast(p) {
  const bar = $("#podcastBar");
  if (!p.active) { bar.hidden = true; if (p.finished) notice(T("podFinished", { title: p.title || "" })); return; }
  bar.hidden = false;
  $("#podTitle").textContent = p.title;
  $("#podProgress").style.width = Math.round(p.progress * 1000) / 10 + "%";
  $("#btnPodToggle").textContent = p.paused ? "▶" : "❚❚";
  if (p.finished) { bar.hidden = true; notice(T("podFinished", { title: p.title })); }
}

function wireLibrary() {
  $("#btnLibrary").onclick = openLibrary;
  $("#btnAddBooks").onclick = () => addBooks();
  $("#libList").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-bread],[data-blisten],[data-bdel]");
    if (!b) return;
    if (b.dataset.bread) openReader(b.dataset.bread);
    else if (b.dataset.blisten) { onPodcast(await api().podcast_start(b.dataset.blisten, null)); $("#libDrawer").hidden = true; }
    else if (b.dataset.bdel && confirm(T("libDelete"))) renderBooks(await api().delete_book(b.dataset.bdel));
  });
  $("#btnPrevPage").onclick = () => readerPage && openReader(readerBook.id, Math.max(0, readerPage.start - 2400));
  $("#btnNextPage").onclick = () => readerPage && openReader(readerBook.id, readerPage.end);
  $("#btnListenHere").onclick = async () => { onPodcast(await api().podcast_start(readerBook.id, readerPage.start)); $("#readerModal").hidden = true; };
  $("#btnPodToggle").onclick = async () => onPodcast(await api().podcast_toggle());
  $("#btnPodStop").onclick = async () => onPodcast(await api().podcast_stop());
  $("#btnAttach").onclick = async () => afterAttach(await api().attach_files(null));

  // Drag & drop: on the Library -> books; anywhere else -> attach to the next message.
  let depth = 0;
  document.addEventListener("dragenter", (e) => { if (e.dataTransfer?.types?.includes("Files")) { depth++; $("#dropZone").hidden = false; } });
  document.addEventListener("dragleave", () => { if (--depth <= 0) { depth = 0; $("#dropZone").hidden = true; } });
  document.addEventListener("dragover", (e) => e.preventDefault());
  document.addEventListener("drop", async (e) => {
    e.preventDefault(); depth = 0; $("#dropZone").hidden = true;
    const fl = e.dataTransfer?.files;
    if (!fl || !fl.length) return;
    if (!$("#libDrawer").hidden) {
      const paths = [...fl].map((f) => f.pywebviewFullPath).filter(Boolean);
      if (paths.length) return addBooks(paths);
    }
    attachDropped(fl);
  });
}

/* ------------------------------------------------------------------ init */
const api = () => window.pywebview.api;

document.querySelectorAll("[data-rings]").forEach((el) => (el.innerHTML = ringsSVG(el.dataset.rings)));
$$(".wordmark").forEach((el) => (el.innerHTML = wordmarkHTML()));
requestAnimationFrame(() => $("#boot .wordmark").classList.add("is-on"));
applyLang("pt");
wire();
wakeRing();

if (window.pywebview && window.pywebview.api) start();
else window.addEventListener("pywebviewready", start);
