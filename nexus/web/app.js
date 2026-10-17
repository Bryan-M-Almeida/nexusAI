/* Fonts from Google only when not offline (v0.12). The last known mode is cached so the boot animation doesn't
   flash fallback fonts; offline it falls back to Bahnschrift / Segoe UI / Consolas, already in the CSS. */
const LEGAL_VERSION = "1.3";  // nexus/legal.py VERSION
function termsAccepted() { try { return localStorage.getItem("nexus.terms") === LEGAL_VERSION; } catch (e) { return false; } }
function loadFonts(mode) {
  try { localStorage.setItem("nexus.net", mode); } catch (e) { /* ignore */ }
  if (mode === "offline" || document.getElementById("gfonts") || !termsAccepted()) return;
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
// v0.19.0: the full intro (4.2 s) plays on the first start of the day; later starts the same day take 1.4 s
const BOOT_MIN_MS = (() => {
  try {
    const today = new Date().toDateString(), seen = localStorage.getItem("nexus.bootDay") === today;
    localStorage.setItem("nexus.bootDay", today);
    return seen ? 1400 : 4200;
  } catch (e) { return 4200; }
})();

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
/* PET (v0.19.6): the NEXUS orb instead of the ring. It lives in the same slot as the ring, so it wanders, rests,
   docks over menus, grows with the voice and glows with the microphone exactly like the ring. Of the ring only the
   halo and the breathing core stay (on top of the eye: same rhythm per state, theme colour); the eye spins like the
   ring's inner segmented circle (faster while listening / thinking) and looks at the mouse pointer. */
const PET_HTML = `<div class="pet" aria-hidden="true"><img class="pet-body" src="pet/body.webp" alt="" draggable="false">
  <div class="pet-eye-wrap"><div class="pet-eye ring-spin" style="--dur:26s;--dir:reverse"><img src="pet/eye.webp" alt="" draggable="false"></div></div></div>`;
let petRaf = 0, petPointer = null, petIdleTimer;
function petLook(e) {  // the eye moves towards the pointer (at most 6% of its size), back to the centre when idle
  petPointer = e ? [e.clientX, e.clientY] : null;
  if (!document.body.classList.contains("pet-mode") || petRaf) return;
  petRaf = requestAnimationFrame(() => {
    petRaf = 0;
    for (const wrap of document.querySelectorAll(".pet-eye-wrap")) {
      const r = wrap.getBoundingClientRect();
      if (!r.width) continue;
      let dx = 0, dy = 0;
      if (petPointer) {
        const vx = petPointer[0] - (r.left + r.width / 2), vy = petPointer[1] - (r.top + r.height / 2);
        const dist = Math.hypot(vx, vy) || 1, reach = Math.min(1, dist / (r.width * 3)) * r.width * 0.06;
        dx = (vx / dist) * reach; dy = (vy / dist) * reach;
      }
      wrap.style.translate = `${dx.toFixed(1)}px ${dy.toFixed(1)}px`;
    }
  });
  clearTimeout(petIdleTimer);
  if (e) petIdleTimer = setTimeout(() => petLook(null), 4000);
}
document.addEventListener("mousemove", petLook, { passive: true });
function petHue(hex) {  // the eye takes the theme's core colour: hue-rotate from the original blue (~214°)
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
  if (!m) return;
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16) / 255);
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  let h = 0;
  if (d) h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  h = (h * 60 + 360) % 360;
  const sat = max ? d / max : 0;
  document.documentElement.style.setProperty("--pet-hue", `${Math.round(h - 214)}deg`);
  document.documentElement.style.setProperty("--pet-sat", Math.min(1.2, sat / 0.8).toFixed(2));
}

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
      case "ui_open": return onUiOpen(p);
      case "stt_progress": return onSttProgress(p);
      case "training": return onTrainingState(p);
      case "suspended": return onSuspended(p);
      case "prefs": return onPrefs(p);
      case "model_progress": return onModelProgress(p);
      case "tutorial_spoken": return onTutorialSpoken(p);
      case "tutorial_cmd": return onTutorialCmd(p);
      case "tutorial_bg": return onTutorialBg(p);
      case "check_spoken": return checkSpoken && checkSpoken();
      case "training_progress": return onTrainingProgress(p);
      case "training_done": return showTrainingResult(p);
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
  const acc = await api().account_state();  // v0.19.0: the account is chosen / unlocked before anything loads
  if (acc.locked) await showLogin(acc);
  state.guest = acc.guest;
  $("#app").classList.toggle("guest", !!acc.guest);
  $("#guestChip").hidden = !acc.guest;
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
  try { localStorage.setItem("nexus.terms", st.terms && st.terms.accepted ? LEGAL_VERSION : ""); } catch (e) { /* ignore */ }
  if (!(st.terms && st.terms.accepted)) await showLegal();
  await loadDashboard();
  for (const m of await api().history()) addMsg(m.role === "user" ? "user" : "nexus", m.content);
  const hello = await api().greet();
  addMsg("nexus", hello);
  caption(hello, 7000);
  if (!profile && !state.guest) openOnboarding();  // v0.19.6: a guest has no profile to import
  setFull(!!st.fullscreen);
  api().training_state().then(onTrainingState);
  api().import_prompt(L).then((r) => (importSources = r.sources || {}));
  // v0.19.6: the first start checks every system and says it BEFORE the tutorial (they used to talk over each other)
  const checked = settings.system_check_done ? Promise.resolve() : new Promise((done) => {
    checkSpoken = done;
    setTimeout(done, 15000);  // never wait forever (voice off)
    api().first_check().then((r) => { setExchange("nexus", r.said); if (!r.spoken) done(); });
  });
  if (!settings.tutorial_done) {  // first run: narrated tutorial once the profile question is out of the way
    api().tutorial_begin();  // v0.20.0: AI closed from now until the tutorial ends; NEXUS gets ready meanwhile
    const go = () => checked.then(() => setTimeout(startTutorial, 1200));
    if ($("#onboarding").hidden) go();
    else new MutationObserver((m, obs) => { if ($("#onboarding").hidden) { obs.disconnect(); go(); } })
      .observe($("#onboarding"), { attributes: true, attributeFilter: ["hidden"] });
  }
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
  document.body.classList.toggle("ai-down", aiDown);
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
let exchangeAt = Date.now();
function setExchange(who, text) {
  exchangeAt = Date.now();
  $("#app").classList.remove("ex-faded");
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
  if (p.control && p.control !== "clearer") { aiBusy = false; setVoiceState("idle"); }
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
  if (r && r.control && r.control !== "clearer") { aiBusy = false; setVoiceState("idle"); }
  if (r && r.tutorial) { aiBusy = false; setVoiceState("idle"); onTutorialCmd({ cmd: r.tutorial }); }
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
  $("#dockRing").dataset.state = shown;
  if (st === "speaking") wakeRing();
  const label = $("#coreLabel");
  label.textContent = modelDownload >= 0 ? T("modelDownloading") : sttDownload >= 0 ? T("sttDownloading") : trainingPct >= 0 ? T("trainingAnalyzing")
    : suspendedOn ? T("st_suspended") : aiDown && !aiBusy ? T("aiDown") : trainingOn && ["idle", "standby"].includes(shown) ? T("st_training") : T("st_" + shown) || "";
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
  app.classList.toggle("follow", !!settings.exchange_follow);
  app.classList.toggle("no-exchange", settings.show_exchange === false);
  if (settings.ui_layout !== "shortcuts") app.classList.remove("zen");
  setCursor(settings.cursor_style, settings.cursor_size);
  applyLook(settings);
  setRingPos(ringPos[0], ringPos[1], false);
  $("#btnSkillsRail").hidden = !feature("skills");
  $("#btnMapRail").hidden = !feature("map");
  $("#btnTraining").hidden = $("#trainingRailTitle").hidden = !feature("training");
  $("#tabLearned").hidden = !feature("training");
  $("#btnImportMem").hidden = !feature("memory_import");
  // v0.18.0: parts of a settings section that belong to a beta feature
  $$("[data-feature]").forEach((el) => (el.hidden = !feature(el.dataset.feature)));
  $$("[data-feature-any]").forEach((el) => (el.hidden = !el.dataset.featureAny.split(",").some(feature)));
  // v0.15.5: beta features that are off disappear from the interface (Settings > Beta)
  $("#btnWorkspaces").hidden = !feature("workspace");
  $("#btnLibrary").hidden = !feature("library");
  $("#btnSkills").hidden = !feature("skills");
  const anyWork = feature("workspace") || feature("library");
  $('#railRight [data-i18n="wsRail"]').hidden = !anyWork;
  $('#railRight [data-i18n="convTitle"]').classList.toggle("rail-sep", anyWork);
}

/* ------------------------------------------------------------------ shortcuts (v0.16) - configurable (v0.16.5) */
const openPanel = () => { loadDashboard(); $("#panelDrawer").hidden = false; };
async function pushToTalk() {
  const r = await api().push_to_talk();
  if (!r.ok) notice(T("voiceLoading") + (r.error && r.error !== "loading" ? ` (${r.error})` : ""), T("moreVoice"));
}
// id, default keys, label, menu it opens (the same keys close it), beta feature it needs
const ACTIONS = [
  { id: "guide", def: "F1", label: "kGuide", panel: "guide", run: () => toggleGuide(true) },
  { id: "talk", def: "Ctrl+Space", label: "kTalk", run: pushToTalk },
  { id: "panel", def: "Ctrl+1", label: "kPanel", panel: "panelDrawer", run: openPanel },
  { id: "convs", def: "Ctrl+2", label: "kConvs", panel: "convDrawer", run: () => openConversations("threads") },
  { id: "notif", def: "Ctrl+3", label: "kNotif", panel: "notifDrawer", run: () => openNotifications() },
  { id: "library", def: "Ctrl+4", label: "kLibrary", panel: "libDrawer", feature: "library", run: () => openLibrary() },
  { id: "workspace", def: "Ctrl+5", label: "kWorkspace", panel: "wsDrawer", feature: "workspace", run: () => openWorkspaces() },
  { id: "skills", def: "Ctrl+6", label: "kSkills", panel: "skillsDrawer", feature: "skills", run: () => openSkills() },
  { id: "map", def: "Ctrl+7", label: "kMap", panel: "mapDrawer", feature: "map", run: () => openMap() },
  { id: "training", def: "Ctrl+8", label: "kTraining", feature: "training", run: () => toggleTraining() },
  { id: "clearText", def: "Ctrl+L", label: "kClearText", run: () => $("#app").classList.add("ex-faded") },
  { id: "settings", def: "Ctrl+,", label: "kSettings", panel: "settings", run: () => openSettings() },
  { id: "mode", def: "Ctrl+M", label: "kMode", run: () => dock(state.ui_mode === "audio" ? "text" : "audio") },
  { id: "info", def: "Ctrl+I", label: "kInfo", run: () => peekInfo() },
  { id: "newConv", def: "Ctrl+Shift+N", label: "kNewConv", run: () => newConversation() },
  { id: "transcript", def: "Ctrl+T", label: "kTranscript", run: () => state.ui_mode === "audio" && toggleTranscript() },
  { id: "toasts", def: "Ctrl+Shift+X", label: "kToasts", run: () => closeToasts() },
  { id: "zen", def: "Ctrl+Shift+H", label: "kZen", run: () => toggleZen() },
  { id: "full", def: "F11", label: "kFull", run: () => toggleFull() },
  { id: "min", def: "Ctrl+Shift+M", label: "kMin", run: () => api().minimize() },
  { id: "quit", def: "Ctrl+Shift+Q", label: "kQuit", run: () => api().quit() },
];
const keysOf = (a) => (settings.shortcuts || {})[a.id] ?? a.def;
const showKeys = (k) => (k || "—").replace("Space", T("kSpace"));

// "Ctrl+Shift+1" from a key event (by physical key, so Shift doesn't turn 1 into ! and layouts don't matter)
const CODE_KEYS = { Space: "Space", Comma: ",", Period: ".", Slash: "/", Minus: "-", Equal: "=", Semicolon: ";", Quote: "'",
  BracketLeft: "[", BracketRight: "]", Backslash: "\\", Backquote: "`", Enter: "Enter", Tab: "Tab", Backspace: "Backspace",
  Delete: "Delete", Insert: "Insert", Home: "Home", End: "End", PageUp: "PageUp", PageDown: "PageDown",
  ArrowUp: "Up", ArrowDown: "Down", ArrowLeft: "Left", ArrowRight: "Right", Escape: "Esc" };
function comboOf(e) {
  if (["Control", "Shift", "Alt", "Meta"].includes(e.key)) return null;
  const c = e.code || "";
  const k = c.startsWith("Key") ? c.slice(3) : c.startsWith("Digit") ? c.slice(5) : /^Numpad\d$/.test(c) ? c.slice(6)
    : CODE_KEYS[c] || (/^F\d{1,2}$/.test(e.key) ? e.key : e.key.length === 1 ? e.key.toUpperCase() : e.key);
  return [e.ctrlKey && "Ctrl", e.altKey && "Alt", e.shiftKey && "Shift", k].filter(Boolean).join("+");
}
const actionFor = (combo) => ACTIONS.find((a) => keysOf(a) === combo);

function toggleGuide(on) {
  const g = $("#guide"), show = on ?? g.hidden;
  if (show) {
    $("#guideKeys").innerHTML = ACTIONS.filter((a) => keysOf(a) && (!a.feature || feature(a.feature)))
      .map((a) => `<li><kbd>${esc(showKeys(keysOf(a)))}</kbd><span>${esc(T(a.label))}</span></li>`).join("")
      + `<li><kbd>Esc</kbd><span>${esc(T("kStop"))}</span></li>`;
  }
  g.hidden = !show;
}

/* Settings > Shortcuts: click a shortcut, press the new keys (Esc cancels, Backspace removes it) */
let capturing = null, holdKey = null;
function renderKeys() {
  const used = {};
  ACTIONS.forEach((a) => { const k = keysOf(a); if (k) used[k] = (used[k] || 0) + 1; });
  $("#keysList").innerHTML = ACTIONS.map((a) => {
    const k = keysOf(a), clash = k && used[k] > 1;
    return `<li><span>${esc(T(a.label))}${a.feature && !feature(a.feature) ? ` <i class="muted">(beta)</i>` : ""}</span>
      <button type="button" class="key-btn ${capturing === a.id ? "capturing" : ""} ${clash ? "clash" : ""}" data-action="${a.id}">
      ${esc(capturing === a.id ? T("keysPress") : showKeys(k))}</button></li>`;
  }).join("") + `<li><span>${esc(T("kStop"))}</span><button type="button" class="key-btn fixed" disabled>Esc</button></li>`;
}
async function saveShortcut(id, combo) {
  const map = { ...(settings.shortcuts || {}) };
  const a = ACTIONS.find((x) => x.id === id);
  if (combo === a.def) delete map[id]; else map[id] = combo;
  settings = (await api().save_settings({ shortcuts: map })).settings;
  renderKeys();
}

/* "Only shortcuts + AI" extra: nothing at all on the screen, not even the mouse pointer */
function toggleZen(on) {
  const app = $("#app");
  const next = on ?? !app.classList.contains("zen");
  if (next && settings.ui_layout !== "shortcuts") { notice(T("zenOnlyShortcuts"), T("zenMore")); return; }
  app.classList.toggle("zen", next);
  if (next) closeToasts();
}

/* Ctrl+I: show the state and the last exchange for a moment, even if hidden, faded or in zen */
let peekTimer;
function peekInfo() {
  const app = $("#app");
  app.classList.add("peek");
  clearTimeout(peekTimer);
  peekTimer = setTimeout(() => app.classList.remove("peek"), 6000);
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
// waiting a long time: the text under the ring fades too (Settings > Interface, 0 = never)
setInterval(() => {
  const sec = +settings.exchange_hide_seconds || 0;
  if (sec && !aiBusy && voiceState !== "speaking" && Date.now() - exchangeAt > sec * 1000) $("#app").classList.add("ex-faded");
}, 3000);

/* Only one menu at a time: opening one (click or shortcut) closes the one that was open. */
const EXCLUSIVE = ["panelDrawer", "convDrawer", "wsDrawer", "skillsDrawer", "libDrawer", "settings", "notifDrawer", "mapDrawer", "guide"];
const MENU_NAME = { panelDrawer: "panel", convDrawer: "conversations", wsDrawer: "workspace", skillsDrawer: "skills",
  libDrawer: "library", settings: "settings", notifDrawer: "notifications", mapDrawer: "map" };
let quietOpen = 0;  // the AI already said what it opened (v0.16.8)
function initExclusivePanels() {
  const obs = new MutationObserver((muts) => {
    for (const m of muts) {
      if (m.target.hidden) continue;
      for (const id of EXCLUSIVE) if (id !== m.target.id) $("#" + id).hidden = true;
      // v0.16.8: NEXUS says which menu opened (Settings > Interface; local voice, no API use)
      if (MENU_NAME[m.target.id] && settings.speak_menus !== false && Date.now() > quietOpen && tutorialStep < 0)
        api().speak_help(T("menuOpening", { name: T("menu_" + MENU_NAME[m.target.id]) }));
    }
    updateDocked();
  });
  for (const id of EXCLUSIVE) obs.observe($("#" + id), { attributes: true, attributeFilter: ["hidden"] });
  addEventListener("resize", () => placeTwin());
}
const isOpen = (id) => !$("#" + id).hidden;
const openBox = () => {
  const id = EXCLUSIVE.find((x) => x !== "guide" && isOpen(x));
  return id ? $("#" + id).querySelector(".drawer-box, .conv-box, .modal-box") : null;
};

/* Menus can be dragged by their top area. Dragged to the top edge they fill the screen; to the left or right edge
   they take that half (a transparent preview shows where, like Windows). Dragging again or a double click restores. */
const SNAPS = ["maximized", "snap-left", "snap-right"];
function initMovable() {
  let drag = null;
  const handle = (e) => {
    const box = e.target.closest(".drawer-box, .conv-box, .modal-box");
    if (!box || e.button !== 0 || box.closest("#confirmModal, #onboarding")) return null;
    if (e.target.closest("button, input, select, textarea, a, label")) return null;  // controls keep working
    // v0.19.0: a fixed strip on top of every menu, or the section's title, always drags - before, sections whose
    // content started at the very top (AMD, Personalization) left nothing to grab
    if (e.clientY - box.getBoundingClientRect().top <= 30 || e.target.closest(".set-sec > h2, .drawer-box h2, .kicker")) return box;
    if (e.target.closest(".list, .chat, .conv-body, .set-body *, .reader-text, .file-view, .book-grid, .map-stage")) return null;
    return e.clientY - box.getBoundingClientRect().top <= 52 ? box : null;
  };
  const zoneAt = (e) => e.clientY < 6 ? "maximized" : e.clientX < 6 ? "snap-left" : e.clientX > innerWidth - 7 ? "snap-right" : null;
  document.addEventListener("mousedown", (e) => {
    const box = handle(e);
    if (!box) return;
    if (SNAPS.some((c) => box.classList.contains(c))) {  // pulling a snapped menu restores it under the pointer
      box.classList.remove(...SNAPS);
      box.style.translate = "0px 0px";
      const r = box.getBoundingClientRect();
      box.style.translate = `${e.clientX - (r.left + r.width / 2)}px ${e.clientY - (r.top + 20)}px`;
    }
    const [x0, y0] = (box.style.translate || "0px 0px").split(" ").map((v) => parseFloat(v) || 0);
    drag = { box, sx: e.clientX, sy: e.clientY, x0, y0, zone: null };
    box.classList.add("moving");
    e.preventDefault();
  });
  document.addEventListener("mousemove", (e) => {
    if (!drag) return;
    drag.box.style.translate = `${drag.x0 + e.clientX - drag.sx}px ${drag.y0 + e.clientY - drag.sy}px`;
    drag.zone = zoneAt(e);
    const pv = $("#snapPreview");
    pv.hidden = !drag.zone;
    pv.dataset.zone = drag.zone || "";
    placeTwin();  // the ring follows the menu being dragged
  });
  document.addEventListener("mouseup", () => {
    if (!drag) return;
    drag.box.classList.remove("moving");
    if (drag.zone) { drag.box.classList.add(drag.zone); drag.box.style.translate = ""; }
    $("#snapPreview").hidden = true;
    drag = null;
    requestAnimationFrame(() => placeTwin());
  });
  document.addEventListener("dblclick", (e) => {
    const box = handle(e);
    if (!box) return;
    const was = box.classList.contains("maximized");
    box.style.translate = "";
    box.classList.remove(...SNAPS);
    if (!was) box.classList.add("maximized");
    requestAnimationFrame(() => placeTwin());
  });
}

/* The small ring waits above the open menu and follows it; a full-screen menu has no room for it, so it steps
   aside (v0.16.8: it used to sit on top and the menu couldn't fill the screen). */
function placeTwin(animate = false) {
  const twin = $("#dockRing"), box = openBox();
  if (!box || twin.hidden) return;
  const full = box.classList.contains("maximized");
  twin.classList.toggle("gone", full);
  if (full) return;
  const r = box.getBoundingClientRect();
  twin.style.left = `${Math.round(r.left + r.width / 2 - 39)}px`;
  twin.style.top = `${Math.max(8, Math.round(r.top - 90))}px`;
  if (animate) twin.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200 });
}

/* The ring docks above an open menu: it shrinks, flies to the top and waits for orders (v0.16.5) */
function updateDocked() {
  const app = $("#app"), twin = $("#dockRing"), core = $("#core");
  const on = EXCLUSIVE.some((id) => id !== "guide" && isOpen(id));
  if (on === app.classList.contains("docked")) { if (on) requestAnimationFrame(() => placeTwin()); return; }
  const fly = (el, from, to) => {
    const dx = from.left + from.width / 2 - (to.left + to.width / 2), dy = from.top + from.height / 2 - (to.top + to.height / 2);
    el.animate([{ transform: `translate(${dx}px, ${dy}px) scale(${from.width / Math.max(to.width, 1)})` },
      { transform: "translate(0, 0) scale(1)" }], { duration: 650, easing: "cubic-bezier(.22,.8,.26,1)" });
  };
  if (on) {
    const from = core.getBoundingClientRect();
    twin.hidden = false;
    app.classList.add("docked");
    placeTwin();
    fly(twin, from, twin.getBoundingClientRect());
  } else {
    const from = twin.getBoundingClientRect();
    app.classList.remove("docked");
    twin.hidden = true;
    fly(core, from, core.getBoundingClientRect());
  }
  wakeRing();
}

/* The AI opened (or closed) something for the user */
function onUiOpen(p) {
  aiBusy = false;
  quietOpen = Date.now() + 1500;  // NEXUS says it itself
  if (p.say) setExchange("nexus", p.say);
  setVoiceState(voiceState === "thinking" ? "idle" : voiceState);
  const open = { settings: () => openSettings(p.section || "general"),
    panel: () => { openPanel(); if (p.section) $(`#panelDrawer [data-tab="${p.section}"]`)?.click(); },
    conversations: () => openConversations("threads"), notifications: () => openNotifications(),
    library: () => openLibrary(), workspace: () => openWorkspaces(), skills: () => openSkills(), map: () => openMap(),
    guide: () => toggleGuide(true), tutorial: () => startTutorial() }[p.target];
  if (p.target === "close") { EXCLUSIVE.forEach((id) => ($("#" + id).hidden = true)); endTutorial(); }
  else if (open) { toggleGuide(false); open(); }
}

/* Voice model download: the ring waves and the core shows the percentage (v0.16.8) */
let sttDownload = -1;
/* local models (v0.18.6): catalog, fit for this PC, download on the ring, switch */
let modelDownload = -1, modelPending = null;
const gbTxt = (x) => (L === "en" ? x.toFixed(1) : x.toFixed(1).replace(".", ",")) + " GB";
async function renderModels() {
  const r = await api().models_catalog();
  $("#modelsPc").textContent = T("modelsPc", { vram: r.pc.vram_gb, ram: r.pc.ram_gb });
  $("#modelGrid").innerHTML = r.models.map((m) => {
    const ms = m.measured;
    const meas = ms ? T("modelMeasured", { tok: ms.tok_s ?? "—", checks: ms.checks, avg: ms.avg_answer_s }) : T("modelNotMeasured");
    const btn = m.active ? `<span class="pill on">${esc(T("modelActive"))}</span>`
      : m.installed ? `<button type="button" class="btn-ghost" data-model-use="${m.id}">${esc(T("modelUse"))}</button>`
      : m.status === "no" ? `<span class="pill">${esc(T("modelTooBig"))}</span>`
      : `<button type="button" class="btn-ghost" data-model-pull="${m.id}">${esc(T("modelDownload"))} · ${gbTxt(m.file_gb)}</button>`;
    return `<div class="model-card fit-${m.status}${m.active ? " active" : ""}">
      <div class="model-top"><b>${esc(m.name)}</b>${m.recommended ? `<span class="pill rec">${esc(T("modelRecommended"))}</span>` : ""}</div>
      <small class="mono">${esc(m.id)} · ${gbTxt(m.file_gb)}</small>
      <small>${esc(T("tier_" + m.tier))}</small>
      <div class="model-fit mono"><i style="width:${m.on_gpu_pct}%"></i><span>${esc(T("fit_" + m.status, { pct: m.on_gpu_pct }))}</span></div>
      <small class="muted">${esc(meas)}</small>
      <div class="model-act">${btn}</div></div>`;
  }).join("");
}
function onModelProgress(p) {
  modelDownload = p.pct >= 0 && p.pct < 100 ? p.pct : -1;
  $("#app").classList.toggle("dl", modelDownload >= 0 || sttDownload >= 0);
  $("#coreText").textContent = modelDownload >= 0 ? `${p.pct}%` : "";
  if (p.pct < 0) notice(T("modelDlFailed"));
  if (p.pct >= 100) { notice(T("modelDlDone")); if (!$("#settings").hidden) renderModels(); }
  setVoiceState(voiceState);
}
async function onModelsClick(e) {
  const pull = e.target.closest("[data-model-pull]"), use = e.target.closest("[data-model-use]");
  if (use) {
    const r = await api().model_use(use.dataset.modelUse);
    if (r.ok) { notice(T("modelSwitched", { name: r.name })); $("#modelName").textContent = r.name; }
    return renderModels();
  }
  if (!pull) return;
  modelPending = pull.dataset.modelPull;
  const card = pull.closest(".model-card");
  $("#modelConfirmText").textContent = T("modelConfirm", { name: card.querySelector("b").textContent, id: modelPending,
    size: card.querySelector(".mono").textContent.split("·")[1].trim() });
  $("#modelConfirm").hidden = false;
}

function onSttProgress(pct) {
  const app = $("#app");
  sttDownload = pct >= 0 && pct < 100 ? pct : -1;
  app.classList.toggle("dl", sttDownload >= 0);
  $("#coreText").textContent = sttDownload >= 0 ? `${pct}%` : "";
  if (pct < 0) notice(T("sttDlFailed"), T("moreVoice"));
  if (pct >= 100) notice(T("sttDlDone"));
  setVoiceState(voiceState);
}

/* Training mode (beta, v0.17.5): while it is on, what the user says is noted; at the end the ring waves with the
   analysis percentage in the core, NEXUS says "Análise completa" and the result opens (also kept in "Aprendizados"). */
let trainingOn = false, trainingPct = -1;
function onTrainingState(p) {
  trainingOn = !!(p && p.active);
  $("#app").classList.toggle("training-on", trainingOn);
  $("#trainingName").textContent = T(trainingOn ? "trainingFinish" : "trainingStart");
  $("#trainingHint").textContent = T(trainingOn ? "trainingFinishHint" : "trainingStartHint");
  $("#btnTraining").classList.toggle("on", trainingOn);
  setVoiceState(voiceState);
}
function toggleTraining() {
  if (!feature("training")) return;
  if (trainingOn) api().training_finish(); else api().training_start("");
}
function onTrainingProgress(pct) {
  trainingPct = pct >= 0 && pct < 100 ? pct : -1;
  $("#app").classList.toggle("dl", trainingPct >= 0 || sttDownload >= 0);
  $("#coreText").textContent = trainingPct >= 0 ? `${pct}%` : "";
  setVoiceState(voiceState);
}
const VERDICT_ICON = { agree: "✓", personal: "◆", disagree: "✕", unknown: "?" };
function trainItem(f) {
  return `<li class="v-${esc(f.verdict)}"><i>${VERDICT_ICON[f.verdict] || "·"}</i><span>${esc(f.fact)}`
    + `<small>${esc(T("verdict_" + f.verdict))}${f.note ? " · " + esc(f.note) : ""}${f.source ? " · " + esc(f.source.replace(/^https?:\/\/(www\.)?/, "").split("/")[0]) : ""}</small></span></li>`;
}
function showTrainingResult(r) {
  onTrainingProgress(100);
  if (!r || !r.ok) { notice(T("trainingFailed")); return; }
  $("#trainScore").textContent = r.score == null ? "—" : `${r.score}%`;
  $("#trainScoreLabel").textContent = T(r.score == null ? "trainingNoScore" : "trainingScore");
  $("#trainLearned").innerHTML = r.learned.map(trainItem).join("") || `<li class="empty">${esc(T("trainingNone"))}</li>`;
  $("#trainLeft").innerHTML = r.left_out.map(trainItem).join("") || `<li class="empty">${esc(T("trainingNone"))}</li>`;
  $("#trainingModal").hidden = false;
}
async function renderLearned() {
  const rows = await api().training_history();
  $("#learnedList").innerHTML = rows.map((r) => {
    const facts = r.facts || [], learned = facts.filter((f) => ["agree", "personal"].includes(f.verdict)).length;
    return `<li class="learned-item"><div class="learned-head" data-training="${r.id}">
      <span class="body">${esc(r.topic || T("trainingUntitled"))}<span class="meta">${esc((r.finished || r.started).replace("T", " ").slice(0, 16))} · ${learned}/${facts.length}</span></span>
      <span class="learned-score">${r.score == null ? "—" : r.score + "%"}</span>
      <button class="x" data-del-training="${r.id}">✕</button></div>
      <ul class="train-list">${facts.map(trainItem).join("")}</ul></li>`;
  }).join("") || `<li class="empty">${esc(T("noLearned"))}</li>`;
}

/* Memories by source (v0.17.5): NEXUS's own + imported from other AIs; "all" is the merged NEXUS memory */
let memFilter = "all", importAi = "chatgpt", importSources = {};
const memSource = (m) => (m.source || "").startsWith("import:") ? m.source.slice(7) : "nexus";
function renderMemSources(mems) {
  const counts = {};
  mems.forEach((m) => (counts[memSource(m)] = (counts[memSource(m)] || 0) + 1));
  const keys = Object.keys(counts);
  const box = $("#memSources");
  box.hidden = keys.length < 2;
  if (box.hidden) { memFilter = "all"; return; }
  const name = (k) => (k === "nexus" ? "NEXUS" : importSources[k] || k);
  box.innerHTML = [`<button type="button" class="chip-opt ${memFilter === "all" ? "on" : ""}" data-src="all">${esc(T("memAll"))} · ${mems.length}</button>`]
    .concat(keys.map((k) => `<button type="button" class="chip-opt ${memFilter === k ? "on" : ""}" data-src="${esc(k)}">${esc(name(k))} · ${counts[k]}</button>`)).join("");
}
async function openImport() {
  const r = await api().import_prompt(L);
  importSources = r.sources || {};
  $("#importPrompt").value = r.prompt;
  $("#importAnswer").value = "";
  $("#importResult").textContent = "";
  renderImportAis();
  $("#importModal").hidden = false;
}
function renderImportAis() {
  $("#importAis").innerHTML = Object.entries(importSources).map(([k, v]) =>
    `<button type="button" class="chip-opt ${k === importAi ? "on" : ""}" data-ai="${esc(k)}">${esc(k === "other" ? T("importOther") : v)}</button>`).join("");
}

/* Concept map (beta, v0.16.8): skills, knowledge and memories linked to the ring. The ring only spins; the
   cards float and slowly orbit with it, pulling the lines that connect them. */
let mapNodes = [], mapRunning = false;
async function openMap() {
  const d = await api().concept_map();
  buildMap(d);
  $("#mapDrawer").hidden = false;
  if (!mapRunning) { mapRunning = true; requestAnimationFrame(mapFrame); }
}
function buildMap(d) {
  const groups = [{ label: T("mapSkills"), kind: "skill",
    items: d.skills.map((x) => ({ t: T("sk_" + x.skill), sub: `${x.rank} · LV ${x.level}` })) }]
    .concat(d.knowledge.map((k) => ({ label: k.name, kind: "know", items: k.items.map((t) => ({ t })) })))
    .concat(d.memories.length ? [{ label: T("mapMemories"), kind: "mem", items: d.memories.map((t) => ({ t })) }] : [])
    .filter((g) => g.items.length);
  // every group gets a slice of the circle proportional to its size; its points spread evenly inside the slice
  mapNodes = [];
  const total = groups.reduce((t, g) => t + g.items.length + 1.5, 0);
  let start = -Math.PI / 2;
  groups.forEach((g, i) => {
    const sector = (Math.PI * 2 * (g.items.length + 1.5)) / total, n = g.items.length;
    const hub = { label: g.label, kind: g.kind + " hub", r: 0.42, a: start + sector / 2, phase: i * 1.7, parent: null,
      detail: g.items.map((x) => x.t) };
    mapNodes.push(hub);
    g.items.forEach((it, j) => {
      mapNodes.push({ label: it.t, sub: it.sub, kind: g.kind, r: 0.8 + (n > 3 ? (j % 3) * 0.1 : (j % 2) * 0.08),
        a: start + sector * (0.06 + 0.88 * (n > 1 ? j / (n - 1) : 0.5)), phase: i * 1.7 + j, parent: hub,
        detail: [it.t, it.sub].filter(Boolean) });
    });
    start += sector;
  });
  $("#mapNodes").innerHTML = mapNodes.map((n, k) =>
    `<button type="button" class="map-node ${n.kind}" data-node="${k}">${esc(n.label.length > 42 ? n.label.slice(0, 40) + "…" : n.label)}${n.sub ? `<small>${esc(n.sub)}</small>` : ""}</button>`).join("");
  $("#mapLinks").innerHTML = mapNodes.map(() => "<line/>").join("");
  mapNodes.forEach((n, k) => { n.el = $(`#mapNodes [data-node="${k}"]`); n.line = $("#mapLinks").children[k]; });
  $("#mapDetail").hidden = true;
}
function mapFrame(t) {
  if ($("#mapDrawer").hidden) { mapRunning = false; return; }
  const st = $("#mapStage"), w = st.clientWidth, h = st.clientHeight, cx = w / 2, cy = h / 2;
  const rx = Math.max(80, w / 2 - 100), ry = Math.max(60, h / 2 - 34);  // an ellipse that uses the whole box
  const spin = t * 0.000035;  // slow orbit together with the ring
  for (const n of mapNodes) {
    const a = n.a + spin, fl = Math.sin(t / 1500 + n.phase) * 7;
    n.x = cx + Math.cos(a) * (n.r * rx + fl);
    n.y = cy + Math.sin(a) * (n.r * ry + fl);
    n.el.style.translate = `${(n.x - n.el.offsetWidth / 2).toFixed(1)}px ${(n.y - n.el.offsetHeight / 2).toFixed(1)}px`;
    const from = n.parent || { x: cx, y: cy };
    n.line.setAttribute("x1", from.x.toFixed(1)); n.line.setAttribute("y1", from.y.toFixed(1));
    n.line.setAttribute("x2", n.x.toFixed(1)); n.line.setAttribute("y2", n.y.toFixed(1));
    n.line.setAttribute("class", n.parent ? "leaf" : "hub");
  }
  requestAnimationFrame(mapFrame);
}

/* Settings > Performance > Optimize (v0.16.8) */
async function runOptimize(kind) {
  $("#optResult").textContent = T("optWorking");
  const r = await api().optimize(kind);
  if (!r.ok) { $("#optResult").textContent = T("optFailed"); return; }
  $("#optResult").textContent = kind === "data" ? T("optDataDone", { file: r.backup.split(/[\\/]/).pop() })
    : T("optDone", { mb: r.freed_mb, rss: r.rss_mb, disk: r.freed_disk_mb });
  if (kind === "data") { $("#chat").innerHTML = ""; setExchange("user", ""); loadDashboard(); }
}

/* NEXUS's own mouse pointer (Settings > Interface): ring, dot or arrow in the ring colour, 3 sizes */
function setCursor(style = "ring", size = "medium") {
  const root = document.documentElement;
  if (style === "system") { root.style.setProperty("--cur", "default"); root.style.setProperty("--cur-hover", "pointer"); return; }
  const px = { small: 20, medium: 26, large: 34 }[size] || 26, c = px / 2;
  const ring = getComputedStyle(root).getPropertyValue("--c-ring").trim() || "#cfe4ff";
  const core = getComputedStyle(root).getPropertyValue("--c-core").trim() || "#2f86ff";
  const svg = (hover) => {
    const fill = hover ? core : ring;
    const body = style === "arrow"
      ? `<path d="M2 2 L${px * .78} ${px * .52} L${px * .46} ${px * .58} L${px * .3} ${px * .92} Z" fill="${fill}" stroke="#020611" stroke-width="1.4" stroke-linejoin="round"/>`
      : style === "dot"
        ? `<circle cx="${c}" cy="${c}" r="${px * (hover ? .26 : .2)}" fill="${fill}" stroke="#020611" stroke-width="1.2"/>`
        : `<circle cx="${c}" cy="${c}" r="${px * .36}" fill="none" stroke="#020611" stroke-width="3"/><circle cx="${c}" cy="${c}" r="${px * .36}" fill="none" stroke="${fill}" stroke-width="1.6"/><circle cx="${c}" cy="${c}" r="${hover ? px * .14 : px * .08}" fill="${fill}" stroke="#020611" stroke-width="1"/>`;
    const hot = style === "arrow" ? "2 2" : `${Math.round(c)} ${Math.round(c)}`;
    return `url("data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${px}" height="${px}" viewBox="0 0 ${px} ${px}">${body}</svg>`)}") ${hot}, ${hover ? "pointer" : "default"}`;
  };
  root.style.setProperty("--cur", svg(false));
  root.style.setProperty("--cur-hover", svg(true));
}

/* First run: a short scripted tutorial narrated by NEXUS - no AI (v0.20.0). It can be replayed from Settings >
   General or by asking. While it runs the AI is closed (typed or spoken words only move it: next / back / skip) and
   NEXUS loads the model, the voice, the app list and the integrations in the background. */
const TUTORIAL = [
  { text: "tut1", focus: "center" },
  { text: "tut2", focus: "center" },
  { text: "tut3", focus: "edges", computer: true },
  { text: "tut3s", focus: "keys", shortcuts: true },
  { text: "tut4", focus: "keys" },
  { text: "tut5", focus: "none" },
  { text: "tut6", focus: "none" },
];
let tutorialStep = -1, tutorialTimer, checkSpoken = null;
function tutorialSteps() {
  const sc = settings.ui_layout === "shortcuts";
  return TUTORIAL.filter((x) => !(x.computer && sc) && !(x.shortcuts && !sc));
}
const TUT_BG = ["ai", "voice", "apps", "integrations"];
let tutBg = {};
function startTutorial() {
  EXCLUSIVE.forEach((id) => ($("#" + id).hidden = true));
  $("#app").classList.remove("resting", "zen");
  api().tutorial_begin();
  renderTutBg();
  tutorialGo(0);
}
function renderTutBg() {
  const mark = { running: "…", done: "✓", skip: "–", error: "!" };
  const shown = TUT_BG.filter((k) => tutBg[k]);
  $("#tutBg").hidden = !shown.length;
  $("#tutBg").textContent = shown.length ? T("tutBg") + "  " + shown.map((k) => `${T("tutBg_" + k)} ${mark[tutBg[k]] || ""}`).join(" · ") : "";
}
function onTutorialBg(p) {
  if (TUT_BG.includes(p.task)) tutBg[p.task] = p.state;
  renderTutBg();
}
function tutorialSkip() {  // "Pular" goes to the last step: how to see it again and that the AI can help
  const last = tutorialSteps().length - 1;
  if (tutorialStep >= last) endTutorial(); else tutorialGo(last);
}
function onTutorialCmd(p) {
  if (tutorialStep < 0) return;
  if (p.cmd === "next") tutorialGo(tutorialStep + 1);
  else if (p.cmd === "back") tutorialGo(Math.max(0, tutorialStep - 1));
  else if (p.cmd === "skip") tutorialSkip();
  else { addMsg("system", T("tutBusy")); caption(T("tutBusy"), 6000); }
}
function tutorialGo(i) {
  const steps = tutorialSteps();
  clearTimeout(tutorialTimer);
  if (i >= steps.length) return endTutorial();
  tutorialStep = i;
  const st = steps[i], text = T(st.text, { name: profile ? ", " + profile.name.split(" ")[0] : "" });
  toggleGuide(st.focus !== "none" && st.focus !== "center");
  $("#guide").dataset.focus = st.focus;
  $("#tutorial").dataset.focus = st.focus;
  $("#tutorial").hidden = false;
  $("#tutText").textContent = text;
  $("#tutCount").textContent = `${i + 1} / ${steps.length}`;
  $("#tutNext").textContent = T(i === steps.length - 1 ? "tutDone" : "tutNext");
  $("#tutBack").hidden = i === 0;
  $("#tutSkip").hidden = i === steps.length - 1;
  setExchange("nexus", text);
  // v0.19.6: the next step comes when NEXUS finishes saying this one (event "tutorial_spoken"); the timer is only a
  // safety net (voice off, or the event lost) - before, a busy PC made the steps skip ahead of the voice
  const fallback = Math.max(4500, text.length * 75);
  tutorialTimer = setTimeout(() => tutorialGo(i + 1), fallback + 15000);
  api().speak_tutorial(text, i).then((r) => {
    if (tutorialStep === i && r && !r.voice) { clearTimeout(tutorialTimer); tutorialTimer = setTimeout(() => tutorialGo(i + 1), fallback); }
  });
}
function onTutorialSpoken(p) {
  if (!$("#tutorial").hidden && p.step === tutorialStep) { clearTimeout(tutorialTimer); tutorialTimer = setTimeout(() => tutorialGo(tutorialStep + 1), 900); }
}
async function endTutorial() {
  if (tutorialStep < 0) return;
  clearTimeout(tutorialTimer);
  tutorialStep = -1;
  $("#tutorial").hidden = true;
  api().tutorial_end();  // the AI is open again
  delete $("#guide").dataset.focus;
  toggleGuide(false);
  if (!settings.tutorial_done) settings = (await api().save_settings({ tutorial_done: true })).settings;
}

/* Terms of Use & Privacy Policy (v0.17.0): shown on the first start (and after a new version), readable any time
   in Settings > Privacy & terms. Until accepted: no microphone, no internet checks, no web fonts. */
function renderLegalDoc(target, doc) {
  const texts = (window.LEGAL || {})[L] || (window.LEGAL || {}).pt || {};
  $("#" + target).innerHTML = texts[doc] || "";
  $("#" + target).scrollTop = 0;
  $$(`[data-legal-tabs="${target === "legalDocModal" ? "modal" : "settings"}"] [data-doc]`)
    .forEach((b) => b.classList.toggle("on", b.dataset.doc === doc));
}
let legalResolve = null;
function showLegal() {
  renderLegalDoc("legalDocModal", "terms");
  $("#legalAge").checked = $("#legalAgree").checked = false;
  $("#legalAccept").disabled = true;
  $("#legalModal").hidden = false;
  return new Promise((resolve) => (legalResolve = resolve));
}
async function acceptLegal() {
  const st = await api().accept_terms();
  settings.terms_version = st.version;
  settings.terms_accepted_at = st.accepted_at;
  try { localStorage.setItem("nexus.terms", LEGAL_VERSION); } catch (e) { /* ignore */ }
  loadFonts(state.network || settings.network_mode || "hybrid");
  $("#legalModal").hidden = true;
  if (legalResolve) { legalResolve(); legalResolve = null; }
}
function renderLegalStatus() {
  const at = settings.terms_accepted_at ? new Date(settings.terms_accepted_at).toLocaleString(document.documentElement.lang) : "—";
  $("#legalStatus").textContent = T("legalStatusOk", { date: at, v: settings.terms_version || "—" });
  renderLegalDoc("legalDocSettings", "terms");
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
  renderMemSources(d.memories);
  $("#memoryList").innerHTML = d.memories.filter((m) => memFilter === "all" || memSource(m) === memFilter).map((m) => `
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
  renderThemes();
  $$("#bgCards [data-bg]").forEach((b) => b.classList.toggle("on", b.dataset.bg === (settings.bg_style || "glow")));
  $$("#centerCards [data-center]").forEach((b) => b.classList.toggle("on", b.dataset.center === (settings.center_style || "ring")));
  renderVoiceInfo();
}

function syncOutput(out) {
  const v = $("#settingsForm").elements[out.dataset.for].value;
  out.textContent = { tts_volume: v + "%", vad_silence: v + " s", tts_speed: (v > 0 ? "+" : "") + v, ring_scale: v + "%",
    exchange_size: v + " px" }[out.dataset.for] ?? v;
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

/* ------------------------------------------------------------------ downloads, storage, system check (v0.19.0) */
let liveTimer, stFirst = null;
const secVisible = (sec) => !$("#settings").hidden && !$(`.set-sec[data-sec="${sec}"]`).hidden;
const fmtBytes = (n) => n >= 2 ** 30 ? (n / 2 ** 30).toFixed(2) + " GB" : n >= 2 ** 20 ? (n / 2 ** 20).toFixed(1) + " MB"
  : n >= 1024 ? (n / 1024).toFixed(0) + " KB" : (n || 0) + " B";
const fmtTime = (s) => s == null ? "--" : s >= 3600 ? `${Math.floor(s / 3600)}h${String(Math.floor(s % 3600 / 60)).padStart(2, "0")}m`
  : s >= 60 ? `${Math.floor(s / 60)}m${String(s % 60).padStart(2, "0")}s` : `${s}s`;
async function renderDownloads() {
  const r = await api().downloads_state();
  const bar = (pct) => { const n = Math.round((pct || 0) / 5); return "[" + "#".repeat(n) + ".".repeat(20 - n) + "]"; };
  $("#dlHead").innerHTML = r.items.length ? r.items.map((d) => {
    const st = d.status === "done" ? `<span class="ok">${esc(T("dlDone"))}</span>` : d.status === "error" ? `<span class="bad">${esc(T("dlError"))}</span>`
      : d.stalled ? `<span class="warn">${esc(T("dlStalled", { s: d.idle_s }))}</span>` : `<span class="run">${esc(T("dlRunning"))}</span>`;
    return `<div>${st} ${esc(d.name)}  ${bar(d.pct)} ${d.pct == null ? "" : d.pct.toFixed(1) + "%"}  ${fmtBytes(d.done)}/${fmtBytes(d.total)}`
      + (d.status === "running" ? `  ${fmtBytes(d.speed)}/s  ETA ${fmtTime(d.eta_s)}` : "") + `</div>`;
  }).join("") : `<div class="muted">${esc(T("dlNone"))}</div>`;
  const log = $("#dlLog"), atEnd = log.scrollTop + log.clientHeight >= log.scrollHeight - 8;
  log.textContent = r.log.map((l) => `${l.ts}  ${l.level === "error" ? "ERR" : l.level === "ok" ? " OK" : "  >"}  ${l.name}  ${l.text}`).join("\n") || "$ _";
  if (atEnd) log.scrollTop = log.scrollHeight;
}
async function renderStorage(full) {
  const r = await api().storage_report(full);
  if (full || !stFirst) stFirst = r;
  const delta = r.data_bytes - stFirst.data_bytes;
  const usedPct = 100 * (1 - r.disk_free / r.disk_total);
  $("#stTotal").innerHTML = `<b>${fmtBytes(r.data_bytes)}</b> <span>${esc(T("stInData"))}</span>`
    + (delta ? `<span class="${delta > 0 ? "up" : "down"}">${delta > 0 ? "+" : ""}${fmtBytes(Math.abs(delta)).replace(/^/, delta < 0 ? "-" : "")}</span>` : "")
    + `<small>${esc(r.data_dir)}</small><i class="meter"><em style="width:${usedPct.toFixed(1)}%"></em></i>`
    + `<small>${esc(T("stDisk", { free: fmtBytes(r.disk_free), total: fmtBytes(r.disk_total) }))}</small>`;
  const cell = (label, bytes, sub = "") => `<div class="st-cell"><small class="mono">${esc(label)}</small><b>${fmtBytes(bytes)}</b><small>${esc(sub)}</small></div>`;
  $("#stGrid").innerHTML = cell(T("st_db"), r.db_bytes, "nexus.db") + r.parts.map((p) => cell(T("st_" + p.key), p.bytes,
    T("stFiles", { n: p.files }))).join("") + cell(T("st_program"), r.program_bytes, "NEXUS");
  $("#stTables").innerHTML = r.tables.map((t) => `<span>${esc(T("tb_" + t.key))} <b>${t.rows.toLocaleString()}</b></span>`).join("");
  if (full) $("#stModels").innerHTML = (r.voice_models || []).map((m) => cell(T("st_voiceModel"), m.bytes, "whisper " + m.name)).join("")
    + (r.ai_models || []).map((m) => cell(T("st_aiModel"), m.bytes, m.name)).join("");
}
async function runSystemCheck(btn) {
  if (btn) btn.disabled = true;
  const r = await api().system_check();
  $("#sysCheck").hidden = false;
  $("#sysCheck").innerHTML = r.checks.map((c) => `<div><span class="${c.ok ? "ok" : "warn"}">${c.ok ? "OK" : "!!"}</span> ${esc(T("boot_" + c.key))} <span class="muted">${esc(c.detail)}</span></div>`).join("")
    + `<div class="said">${esc(r.said)}</div>`;
  if (btn) btn.disabled = false;
  return r;
}

/* ------------------------------------------------------------------ accounts (v0.19.0) */
let loginResolve = null, loginPick = null;
function showLogin(acc) {
  $("#boot").classList.add("behind-login");
  renderLoginAccounts(acc.accounts || []);
  $("#loginModal").hidden = false;
  return new Promise((r) => (loginResolve = r));
}
function renderLoginAccounts(list) {
  $("#loginAccounts").innerHTML = list.map((a) => `<button type="button" class="login-acc" data-acc="${esc(a.id)}" data-pass="${a.has_password ? 1 : 0}">
      <i>${esc((a.name || T("accOwner")).slice(0, 1).toUpperCase())}</i><b>${esc(a.name || T("accOwner"))}</b>
      <small>${a.has_password ? "🔒 " + esc(T("accProtected")) : esc(T("accOpen"))}</small></button>`).join("");
  $("#loginPassForm").hidden = $("#loginNewForm").hidden = true;
  $("#loginAccounts").hidden = $("#loginActions").hidden = false;
}
async function loginAs(id, password = "") {
  const r = await api().account_login(id, password);
  if (!r.ok) {
    $("#loginError").textContent = T(r.error === "wait" ? "loginWait" : "loginWrong");
    $("#loginError").hidden = false;
    return;
  }
  if (r.restarting) { $("#loginStatus").textContent = T("loginOpening"); return; }
  $("#loginModal").hidden = true;
  $("#boot").classList.remove("behind-login");
  if (loginResolve) { loginResolve(); loginResolve = null; }
}
function wireLogin() {
  $("#loginAccounts").addEventListener("click", (e) => {
    const b = e.target.closest("[data-acc]");
    if (!b) return;
    if (b.dataset.pass === "1") {
      loginPick = b.dataset.acc;
      $("#loginPassName").textContent = b.querySelector("b").textContent;
      $("#loginAccounts").hidden = $("#loginActions").hidden = true;
      $("#loginPassForm").hidden = false; $("#loginError").hidden = true; $("#loginPass").value = "";
      setTimeout(() => $("#loginPass").focus(), 50);
    } else loginAs(b.dataset.acc);
  });
  $("#loginPassForm").onsubmit = (e) => { e.preventDefault(); loginAs(loginPick, $("#loginPass").value); };
  $("#loginBack").onclick = () => renderLoginAccounts([...$$("#loginAccounts [data-acc]")].map((b) => ({ id: b.dataset.acc,
    name: b.querySelector("b").textContent, has_password: b.dataset.pass === "1" })));
  $("#loginGuest").onclick = async () => { $("#loginStatus").textContent = T("loginGuestOpening"); await api().account_guest(); };
  $("#loginNewBtn").onclick = () => { $("#loginAccounts").hidden = $("#loginActions").hidden = true; $("#loginNewForm").hidden = false; $("#loginNewName").focus(); };
  $("#loginNewCancel").onclick = async () => renderLoginAccounts((await api().account_state()).accounts || []);
  $("#loginNewForm").onsubmit = async (e) => {
    e.preventDefault();
    const r = await api().account_create($("#loginNewName").value, $("#loginNewPass").value);
    if (!r.ok) { $("#loginNewError").textContent = T(r.error === "short" ? "accShort" : "accNeedName"); $("#loginNewError").hidden = false; return; }
    $("#loginNewName").value = $("#loginNewPass").value = "";
    renderLoginAccounts(r.accounts);
  };
}
async function renderAccount() {
  const r = await api().account_state();
  $("#accountCard").innerHTML = r.guest ? `<b>${esc(T("accGuest"))}</b><small>${esc(T("accGuestHint"))}</small>`
    : `<b>${esc(r.name || T("accOwner"))}</b><small>${esc(T("accActive"))}</small>`;
  $$("[data-account-only]").forEach((el) => (el.hidden = !!r.guest));
  $("#accountList").innerHTML = (r.accounts || []).map((a) => `<div class="account-row${a.active ? " on" : ""}">
      <i>${esc((a.name || T("accOwner")).slice(0, 1).toUpperCase())}</i><span>${esc(a.name || T("accOwner"))}${a.has_password ? " 🔒" : ""}</span>
      ${a.active ? `<small class="mono">${esc(T("accInUse"))}</small>` : `<button type="button" class="link-btn" data-acc-switch="${esc(a.id)}">${esc(T("accSwitch"))}</button>`}
      ${a.id === "owner" || a.active ? "" : `<button type="button" class="link-btn" data-acc-del="${esc(a.id)}">${esc(T("accDelete"))}</button>`}</div>`).join("");
}
function wireAccount() {
  $("#btnAccPass").onclick = async () => {
    const r = await api().account_set_password($("#accOldPass").value, $("#accNewPass").value);
    notice(T(r.ok ? "accPassSaved" : r.error === "short" ? "accShort" : "loginWrong"));
    if (r.ok) $("#accOldPass").value = $("#accNewPass").value = "";
  };
  $("#btnAccLock").onclick = async () => { const r = await api().account_lock(); if (r.ok) location.reload(); else notice(T("accNeedPass")); };
  $("#btnAccSwitchGuest").onclick = async () => { notice(T("loginGuestOpening")); await api().account_guest(); };
  $("#accountList").addEventListener("click", async (e) => {
    const sw = e.target.closest("[data-acc-switch]"), del = e.target.closest("[data-acc-del]");
    if (sw) { notice(T("loginOpening")); await api().account_switch(sw.dataset.accSwitch); }
    if (del) {
      const pw = prompt(T("accDeleteConfirm"));
      if (pw === null) return;
      const r = await api().account_delete(del.dataset.accDel, pw);
      notice(T(r.ok ? "accDeleted" : "loginWrong"));
      renderAccount();
    }
  });
}

/* Settings groups (v0.19.0): a header with an icon and an arrow; a click folds the group to its title, another click
   opens it again; "collapse all / expand all" on top. The folded groups are remembered on this PC. */
const GROUP_ICONS = { grpSystem: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM4 12h2M18 12h2M12 4v2M12 18v2",
  grpAi: "M9 4h6v4h4v6h-4v6H9v-6H5V8h4z", grpVoice: "M12 4a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V7a3 3 0 0 1 3-3zM6 12a6 6 0 0 0 12 0M12 18v3",
  grpLook: "M12 4a8 8 0 1 0 0 16c1 0 1.5-.8 1.5-1.6 0-1.2-1-1.4-1-2.4 0-.8.7-1.5 1.5-1.5H17a3 3 0 0 0 3-3c0-4.4-3.6-7.5-8-7.5z",
  grpConnect: "M8 7h11l-3-3M16 17H5l3 3", grpHardware: "M6 6h12v12H6zM9 9h6v6H9zM9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3",
  grpData: "M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z",
  grpAbout: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v6M12 7.5v.5" };
let foldedGroups = new Set();
try { foldedGroups = new Set(JSON.parse(localStorage.getItem("nexus.folded") || "[]")); } catch (e) { /* first run */ }
function initSetGroups() {
  for (const g of $$("#setNav .set-group")) {
    const id = g.dataset.i18n, label = g.textContent;
    const btn = document.createElement("button");
    btn.type = "button"; btn.className = "set-group"; btn.dataset.group = id;
    btn.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="${GROUP_ICONS[id] || ""}"/></svg><span data-i18n="${id}">${esc(label)}</span><i class="chev">▾</i>`;
    g.replaceWith(btn);
  }
  applyGroups();
}
function groupItems(header) {  // the section buttons under a group header, up to the next header
  const out = [];
  for (let el = header.nextElementSibling; el && !el.classList.contains("set-group"); el = el.nextElementSibling) out.push(el);
  return out;
}
function applyGroups() {
  for (const h of $$("#setNav button.set-group")) {
    const folded = foldedGroups.has(h.dataset.group);
    h.classList.toggle("folded", folded);
    groupItems(h).forEach((el) => el.classList.toggle("grp-hidden", folded));
    const n = groupItems(h).filter((el) => !el.hidden).length;
    h.title = `${n}`;
  }
  try { localStorage.setItem("nexus.folded", JSON.stringify([...foldedGroups])); } catch (e) { /* ignore */ }
}
function toggleGroup(id, fold) {
  if (fold ?? !foldedGroups.has(id)) foldedGroups.add(id); else foldedGroups.delete(id);
  applyGroups();
}

function showSection(sec) {
  $$("#setNav [data-sec]").forEach((b) => b.classList.toggle("on", b.dataset.sec === sec));
  const owner = $(`#setNav [data-sec="${sec}"]`);  // the group of the open section is never folded
  for (let el = owner?.previousElementSibling; el; el = el.previousElementSibling) {
    if (el.classList.contains("set-group")) { if (foldedGroups.has(el.dataset.group)) toggleGroup(el.dataset.group, false); break; }
  }
  $$(".set-sec").forEach((x) => (x.hidden = x.dataset.sec !== sec));
  clearInterval(integTimer);
  if (sec === "ai") renderModels();
  if (sec === "account") renderAccount();
  clearInterval(liveTimer);
  if (sec === "downloads") { renderDownloads(); liveTimer = setInterval(() => (secVisible("downloads") ? renderDownloads() : clearInterval(liveTimer)), 1000); }
  if (sec === "data") { renderStorage(true); liveTimer = setInterval(() => (secVisible("data") ? renderStorage(false) : clearInterval(liveTimer)), 2000); }
  if (sec === "integ") { renderIntegrations(); integTimer = setInterval(() => { if (!$("#settings").hidden) renderIntegrations(); }, 6000); }
  if (sec === "apps") { if (feature("media")) renderMedia(); if (feature("apps")) renderApps(false); }
  if (sec === "about") renderAbout();
  if (sec === "updates") renderUpdates();
  if (sec === "issues") renderIssues();
  clearInterval(amdTimer);
  if (sec === "amd") { renderAmd(); amdTimer = setInterval(() => { if (!$("#settings").hidden && amdVisible()) amdTick(); else clearInterval(amdTimer); }, 1500); }
}

/* ------------------------------------------------------------------ about, updates, possible errors (v0.20.0) */
function renderAbout() {
  $("#aboutVersion").textContent = $("#version").textContent + " · " + T("protoWord");
  const list = (id, items) => ($(id).innerHTML = items.filter(Boolean).map((x) => `<li>${esc(x)}</li>`).join(""));
  list("#aboutStableList", T("aboutStableItems").split("|"));
  // the beta list is the Beta section itself, so the two never disagree
  list("#aboutBetaList", $$("#betaList label span").map((x) => x.textContent + (feature(x.previousElementSibling.name.replace("beta_", "")) ? "  ✓" : "")));
  list("#aboutNotList", T("aboutNotItems").split("|"));
}
let updatesCache = null;
async function renderUpdates() {
  if (!updatesCache) updatesCache = await api().about_updates();
  const v = updatesCache.versions || [];
  $("#updatesList").innerHTML = v.length ? v.map((x, i) => `<details class="upd"${i === 0 ? " open" : ""}>
      <summary><b class="mono">${esc(x.version)}</b><span class="mono muted">${esc(x.kind)}${x.date ? " · " + esc(x.date) : ""}</span>
        ${x.version === "v" + updatesCache.version ? `<i class="upd-now mono">${esc(T("updNow"))}</i>` : ""}<small>${x.headline}</small></summary>
      <div class="upd-body">${x.html}</div></details>`).join("") : `<p class="hint">${esc(T("updatesNone"))}</p>`;
}
let issuesCache = null;
async function renderIssues() {
  if (!issuesCache) {
    issuesCache = (await api().about_errors()).errors || [];
    const areas = [...new Set(issuesCache.map((x) => x.area))];
    $("#issuesArea").innerHTML = `<option value="">${esc(T("issuesAll"))}</option>` +
      areas.map((a) => `<option value="${esc(a)}">${esc(T("area_" + a) || a)}</option>`).join("");
  }
  const q = ($("#issuesFind").value || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const area = $("#issuesArea").value;
  const plain = (x) => [x.id, x.title, x.symptom, x.cause, x.fix, x.tips].join(" ").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const shown = issuesCache.filter((x) => (!area || x.area === area) && (!q || plain(x).includes(q)));
  $("#issuesCount").textContent = T("issuesCount", { n: shown.length, total: issuesCache.length });
  const block = (label, text) => (text ? `<p><b>${esc(T(label))}</b></p><pre>${esc(text)}</pre>` : "");
  $("#issuesList").innerHTML = shown.map((x) => `<details class="issue" data-sev="${esc(x.severity)}">
      <summary><span class="mono iss-id">${esc(x.id)}</span><b>${esc(x.title)}</b><span class="mono iss-st">${esc(x.status)}</span></summary>
      ${block("issSymptom", x.symptom || x.cause)}${x.symptom ? block("issCause", x.cause) : ""}${block("issFix", x.fix)}${block("issTips", x.tips)}
    </details>`).join("");
}

/* ------------------------------------------------------------------ personalisation (v0.18.5) */
const THEMES = { nexus: ["#cfe4ff", "#2f86ff", "#0b1f5c"], amd: ["#ffd6d3", "#ed1c24", "#2a0507"], emerald: ["#d5ffea", "#16c47a", "#05271b"],
  violet: ["#ebdcff", "#8b5cf6", "#1a0b3b"], amber: ["#ffe9c4", "#f59e0b", "#2a1904"], graphite: ["#e6e8ec", "#9aa3b2", "#101318"],
  ice: ["#e8fbff", "#38bdf8", "#04233a"] };
function applyLook(src) {
  const root = document.documentElement.style;
  root.setProperty("--ring-scale", Math.max(0.6, Math.min(1.4, (+src.ring_scale || 100) / 100)));
  root.setProperty("--spin", { slow: 1.8, normal: 1, fast: 0.55 }[src.ring_speed] || 1);
  root.setProperty("--ex-size", Math.max(12, Math.min(24, +src.exchange_size || 14)) + "px");
  document.body.classList.toggle("bg-solid", src.bg_style === "solid");
  document.body.classList.toggle("bg-grid", src.bg_style === "grid");
  document.body.classList.toggle("font-clean", src.font_brand === "clean");
  document.body.classList.toggle("pet-mode", src.center_style === "pet");  // v0.19.6: ring or PET in the centre
  petHue(src.color_core || "#2f86ff");
}
function renderThemes() {
  const f = $("#settingsForm"), cur = f.elements.theme.value || settings.theme || "nexus";
  $("#themeGrid").innerHTML = Object.entries(THEMES).map(([id, [r, c, b]]) => `<button type="button" class="theme-chip ${id === cur ? "on" : ""}" data-theme="${id}"
      style="--t-ring:${r};--t-core:${c};--t-bg:${b}"><i></i><span>${esc(T("theme_" + id))}</span></button>`).join("");
}
function pickTheme(id) {
  const f = $("#settingsForm"), [r, c, b] = THEMES[id];
  f.elements.theme.value = id;
  f.elements.color_ring.value = r; f.elements.color_core.value = c; f.elements.color_bg.value = b;
  setColors({ color_ring: r, color_core: c, color_bg: b });
  renderThemes();
}
function previewLook() {
  const f = $("#settingsForm");
  applyLook({ ring_scale: f.elements.ring_scale.value, ring_speed: f.elements.ring_speed.value, exchange_size: f.elements.exchange_size.value,
    bg_style: f.elements.bg_style.value, font_brand: f.elements.font_brand.value, center_style: f.elements.center_style.value,
    color_core: f.elements.color_core.value });
}
function onPrefs(changed) {  // NEXUS changed its own look or voice ("muda o aro para vermelho")
  Object.assign(settings, changed);
  applyInterface();
  if (!$("#settings").hidden) fillSettings();
}

/* ------------------------------------------------------------------ AMD panel (v0.18.5) */
let amdTimer, amdHistory = [];
const amdVisible = () => !$('.set-sec[data-sec="amd"]').hidden;
const gb = (mb) => (mb / 1024).toFixed(1);
function amdTile(label, value, sub = "", pct = null) {
  return `<div class="amd-tile"><small class="mono">${esc(label)}</small><b>${value}</b>${pct === null ? "" : `<i class="meter"><em style="width:${Math.max(0, Math.min(100, pct))}%"></em></i>`}<small>${esc(sub)}</small></div>`;
}
async function renderAmd() {
  const r = await api().amd_status(), card = (r.cards || [])[0];
  $("#amdName").textContent = card ? card.name : T("amdNoCard");
  $("#amdDriver").textContent = card ? [card.adrenalin && `Adrenalin ${card.adrenalin}`, card.driver && `${T("amdDriver")} ${card.driver}`,
    r.tune && (r.tune.vulkan ? "Vulkan" : "ROCm / Vulkan")].filter(Boolean).join(" · ") : T("amdNoCardHint");
  $("#amdTech").innerHTML = (r.tech || []).map((t) => `<div class="amd-tech-row st-${t.status}"><b>${esc(T("tech_" + t.id))}</b>
      <span class="pill mono">${esc(T("techStatus_" + t.status))}</span><small>${esc(T("techd_" + t.id, { d: t.detail }))}</small></div>`).join("");
  $("#amdRefs").innerHTML = (r.refs || []).map((id) => `<button type="button" class="amd-ref" data-ref="${id}"><b>${esc(T("ref_" + id))}</b><small>${esc(T("refd_" + id))}</small></button>`).join("");
  amdCard = card;
  renderCompute();
  amdTick();
}
let amdCard = null, amdPending = null;
async function renderCompute() {  // v0.19.5: Vulkan / ROCm and the NPU
  const c = await api().amd_compute(), r = c.rocm;
  const backend = c.backend === "rocm" ? "ROCm" : c.vulkan ? "Vulkan" : "Auto";
  $("#amdBackend").innerHTML = `<div class="ac-line"><b>${esc(T("acNow"))}</b><span class="pill mono">${esc(backend)}</span>
      <span class="mono">${esc(c.card || "—")} · ${esc(r.gfx || "?")}</span></div>
    <small>${esc(r.supported ? T("acRocmYes", { gfx: r.gfx }) : r.installed ? T("acRocmNo", { gfx: r.gfx || "?", list: r.targets.join(", ") }) : T("acRocmNoOllama"))}</small>
    <div class="row-btns">${r.supported ? `<button type="button" class="btn-ghost" data-backend="${c.backend === "rocm" ? "auto" : "rocm"}">${esc(T(c.backend === "rocm" ? "acUseAuto" : "acUseRocm"))}</button>
      <button type="button" class="btn-ghost" id="btnAmdCompare">${esc(T("acCompare"))}</button>` : `<button type="button" class="btn-ghost" disabled>${esc(T("acUseRocm"))}</button>`}</div>
    <div class="ac-result mono" id="amdCompareResult"></div>`;
  const lem = c.lemonade || {};
  $("#amdNpu").innerHTML = `<div class="ac-line"><b>${esc(T("acNpu"))}</b><span class="pill mono">${esc(c.npus.length ? T("acNpuFound") : T("acNpuNone"))}</span>
      <span class="mono">${esc(c.npus.join(", ") || "—")}</span></div>
    <div class="ac-line"><b>Lemonade</b><span class="pill mono">${esc(lem.running ? T("acLemOn") : T("acLemOff"))}</span>
      <span class="mono">${esc(lem.running ? lem.url + " · " + (lem.models || []).slice(0, 3).join(", ") : "")}</span></div>
    <small>${esc(T(c.npus.length ? "acNpuHint" : "acNpuNoHint"))}</small>
    <div class="row-btns">${lem.running ? `<button type="button" class="btn-ghost" data-lemonade="${c.using_lemonade ? 0 : 1}">${esc(T(c.using_lemonade ? "acLemStop" : "acLemUse"))}</button>` : ""}
      <button type="button" class="btn-ghost" data-ref-open="lemonade">${esc(T("acLemGet"))}</button></div>`;
}
async function onComputeClick(e) {
  const b = e.target.closest("[data-backend]"), lem = e.target.closest("[data-lemonade]"), ref = e.target.closest("[data-ref-open]");
  if (ref) return api().amd_open_ref(ref.dataset.refOpen);
  if (lem) { const r = await api().amd_use_lemonade(lem.dataset.lemonade === "1"); notice(T(r.ok ? "acLemDone" : "acLemNotRunning")); return renderCompute(); }
  if (e.target.id === "btnAmdCompare") {
    e.target.disabled = true; $("#amdCompareResult").textContent = T("acComparing");
    const r = await api().amd_compare();
    $("#amdCompareResult").textContent = r.ok ? `ROCm ${r.rocm.tok_s} tok/s (${r.rocm.on_gpu_pct}%) · Vulkan ${r.vulkan.tok_s} tok/s (${r.vulkan.on_gpu_pct}%) → ${T("acBest", { b: r.best === "rocm" ? "ROCm" : "Vulkan" })}` : T("acCompareFail");
    e.target.disabled = false;
    return;
  }
  if (!b) return;
  amdPending = b.dataset.backend;
  $("#amdBackendConfirmText").textContent = T(amdPending === "rocm" ? "acConfirmRocm" : "acConfirmAuto");
  $("#amdBackendConfirm").hidden = false;
}
async function amdTick() {
  const r = await api().amd_live();
  if (r.error) { $("#amdTiles").innerHTML = `<p class="muted small">${esc(r.error)}</p>`; return; }
  const total = amdCard ? amdCard.vram_gb * 1024 : 0, model = (r.model || [])[0];
  amdHistory.push(r.gpu_pct); amdHistory = amdHistory.slice(-40);
  const engines = Object.entries(r.engines || {}).filter(([, v]) => v > 0.5).map(([k, v]) => `${k} ${Math.round(v)}%`).join(" · ");
  $("#amdTiles").innerHTML = amdTile(T("amdGpu"), Math.round(r.gpu_pct) + "<u>%</u>", engines || T("amdIdle"), r.gpu_pct)
    + amdTile(T("amdVram"), gb(r.vram_used_mb) + "<u>GB</u>", total ? `${T("amdOf")} ${gb(total)} GB` : "", total ? 100 * r.vram_used_mb / total : null)
    + amdTile(T("amdAiGpu"), Math.round(r.ai_gpu_pct) + "<u>%</u>", T("amdAiGpuSub"), r.ai_gpu_pct)
    + amdTile(T("amdAiVram"), gb(r.ai_vram_mb) + "<u>GB</u>", model ? model.name : T("amdNotLoaded"), total ? 100 * r.ai_vram_mb / total : null);
  const ai = r.ai || {}, last = ai.last || {};
  $("#amdAiTiles").innerHTML = amdTile(T("amdTokS"), ai.tok_s ?? "—", T("amdTokSSub"))
    + amdTile(T("amdFirst"), ai.first_s != null ? ai.first_s + "<u>s</u>" : "—", T("amdFirstSub"))
    + amdTile(T("amdLast"), last.total_s != null ? last.total_s + "<u>s</u>" : "—", last.gen_tokens ? `${last.gen_tokens} tokens` : T("amdNoAnswers"))
    + amdTile(T("amdModel"), model ? Math.round(100 * model.vram_mb / Math.max(1, model.size_mb)) + "<u>%</u>" : "—", T("amdModelSub"), model ? 100 * model.vram_mb / Math.max(1, model.size_mb) : null);
  const hist = ai.history || [], max = Math.max(30, ...hist);
  $("#amdSpeed").innerHTML = hist.length ? `<small class="mono">${esc(T("amdSpeedHist"))}</small><div>${hist.map((v) => `<i style="height:${Math.round(100 * v / max)}%" title="${v} tok/s"></i>`).join("")}</div>` : "";
  const off = 40 - amdHistory.length;  // newest sample on the right edge, like a live overlay
  const pts = amdHistory.map((v, i) => `${(300 * (i + off) / 39).toFixed(1)},${(58 - 56 * v / 100).toFixed(1)}`).join(" ");
  $("#amdGraph polyline").setAttribute("points", pts);
}

/* ------------------------------------------------------------------ integrations hub, apps, media (v0.18.0) */
const INTEG_ICON = { weather: "☁", currency: "$", crypto: "₿", clock: "◷", translate: "文", holidays: "▦", air: "≋",
  news: "▤", wikipedia: "W", calendar: "▣", calc: "∑", units: "⇄" };
let integTimer;
const hhmm = (ts) => ts ? new Date(ts * 1000).toTimeString().slice(0, 5) : "";

async function renderIntegrations() {
  const r = await api().integrations_status();
  const builtIn = r.items.filter((x) => x.kind !== "custom"), custom = r.items.filter((x) => x.kind === "custom");
  const sum = (k) => r.items.reduce((a, x) => a + (x[k] || 0), 0);
  $("#integSummary").textContent = T("integSummary", { on: builtIn.filter((x) => x.on).length, total: builtIn.length,
    uses: sum("uses"), cached: sum("cached"), net: sum("net") }) + (r.online ? "" : " · " + T("integOffline"));
  const open = $$(".integ-test:not([hidden])").map((el) => [el.closest("[data-cx]").dataset.cx, el.innerHTML]);
  $("#integGrid").innerHTML = builtIn.map(integCard).join("");
  $("#integCustomList").innerHTML = custom.map(integCard).join("") || `<p class="muted small">${esc(T("icNone"))}</p>`;
  for (const [id, html] of open) {
    const el = $(`[data-cx="${id}"] .integ-test`);
    if (el) { el.innerHTML = html; el.hidden = false; }
  }
}

function integCard(x) {
  const custom = x.kind === "custom";
  const name = custom ? x.name : T("cx_" + x.id), desc = custom ? x.keywords : T("cxd_" + x.id);
  const ttl = x.ttl ? (x.ttl >= 86400 ? `${Math.round(x.ttl / 86400)} d` : x.ttl >= 3600 ? `${Math.round(x.ttl / 3600)} h` : `${Math.round(x.ttl / 60)} min`) : "—";
  return `<div class="integ-card st-${x.state}${x.on ? "" : " off"}" data-cx="${esc(x.id)}">
    <div class="integ-top"><span class="integ-ico">${esc(INTEG_ICON[x.id] || "⌁")}</span><b>${esc(name)}</b>
      <input type="checkbox" class="cx-on" data-cx-toggle="${esc(x.id)}" ${x.on ? "checked" : ""} aria-label="on/off"></div>
    <small class="integ-desc">${esc(desc)}</small>
    <div class="integ-meta mono"><span class="pill">${esc(T("cxs_" + x.state, { until: hhmm(x.until) }))}</span>
      <span title="${esc(T("cxSource"))}">${esc(x.kind === "local" ? T("cxLocal") : x.provider)}</span></div>
    <div class="integ-meta mono"><span>${esc(T("cxUses", { n: x.uses, c: x.cached }))} · ${esc(T("cxTtl", { t: ttl }))}</span>
      <span class="integ-acts"><button type="button" class="link-btn" data-cx-test="${esc(x.id)}">${esc(T("cxTest"))}</button>${custom
        ? `<button type="button" class="link-btn" data-cx-del="${esc(x.id)}" aria-label="remove">✕</button>` : ""}</span></div>
    <div class="integ-test small mono" hidden></div></div>`;
}

async function onIntegClick(e) {
  const tog = e.target.closest("[data-cx-toggle]"), test = e.target.closest("[data-cx-test]"), del = e.target.closest("[data-cx-del]");
  if (tog) { await api().integration_toggle(tog.dataset.cxToggle, tog.checked); return renderIntegrations(); }
  if (del) { await api().integration_remove(del.dataset.cxDel); return renderIntegrations(); }
  if (!test) return;
  const id = test.dataset.cxTest, boxOf = () => $(`[data-cx="${id}"] .integ-test`);
  boxOf().hidden = false; boxOf().textContent = "…";
  const r = await api().integration_test(id);
  const box = boxOf();  // the grid may have been redrawn while the test ran
  if (!box) return;
  box.hidden = false;
  box.innerHTML = r.ok ? `<span class="ok">✓ ${r.ms} ms${r.cached ? " · " + esc(T("cxFromCache")) : ""}</span><br>${esc(r.preview || "")}`
    : `<span class="bad">✕ ${esc(r.error === "city" ? T("cxNeedCity") : r.error)}</span>`;
  renderIntegrations();
}

async function addCustomIntegration() {
  const r = await api().integration_add($("#icName").value, $("#icKeys").value, $("#icUrl").value, +$("#icTtl").value);
  if (!r.ok) return notice(T(r.error === "url" ? "icBadUrl" : "icBadKeys"));
  $("#icName").value = $("#icKeys").value = $("#icUrl").value = "";
  renderIntegrations();
}

let appsCache = [];
async function renderApps(refresh) {
  $("#appsList").innerHTML = `<p class="muted small">${esc(T("appsLoading"))}</p>`;
  appsCache = (await api().apps_list(!!refresh)).items || [];
  drawApps();
}
function drawApps() {
  const q = ($("#appsFilter").value || "").toLowerCase();
  const rows = appsCache.filter((a) => !q || a.name.toLowerCase().includes(q)).slice(0, 250);
  $("#appsList").innerHTML = rows.map((a) => `<div class="app-row k-${a.kind}" data-app="${esc(a.name)}">
      <span class="app-name">${esc(a.name)}</span>
      <span class="app-kind mono">${["work", "game"].map((k) => `<button type="button" class="${(a.kind === k || (k === "work" && a.kind === "launcher")) ? "on" : ""}" data-kind="${k}">${esc(T(k === "work" && a.kind === "launcher" ? "kindLauncher" : "kind_" + k))}</button>`).join("")}</span>
      <button type="button" class="link-btn" data-app-open>${esc(T("appOpen"))}</button></div>`).join("")
    || `<p class="muted small">${esc(T("appsNone"))}</p>`;
}
async function onAppsClick(e) {
  const row = e.target.closest("[data-app]");
  if (!row) return;
  const kind = e.target.closest("[data-kind]");
  if (kind) { appsCache = (await api().app_mark(row.dataset.app, kind.dataset.kind)).items; return drawApps(); }
  if (e.target.closest("[data-app-open]")) { const r = await api().app_open(row.dataset.app); if (r.said) notice(r.said); }
}

let volTimer;
async function renderMedia() {
  const r = await api().media_state(), cur = r.current;
  $("#mediaTitle").textContent = cur ? cur.title : T("mediaNothing");
  $("#mediaSub").textContent = cur ? [cur.artist, cur.app, T(cur.status === "playing" ? "mediaPlaying" : "mediaPaused")].filter(Boolean).join(" · ") : "";
  $("#mediaCard").classList.toggle("playing", !!cur && cur.status === "playing");
  if (r.volume != null) { $("#mediaVol").value = r.volume; $("#mediaVolOut").textContent = r.volume + "%"; }
}

let suspendedOn = false;
function onSuspended(p) {
  suspendedOn = !!p.on;
  $("#app").classList.toggle("suspended", suspendedOn);
  if (p.on) notice(T(p.app ? "suspendedOn" : "suspendedManual", { app: p.app || "" }), p.vram_freed_mb ? T("suspendedVram", { mb: p.vram_freed_mb }) : "");
  else notice(T("suspendedOff"));
  setVoiceState(voiceState);
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

/* Settings > Performance: Ollama on AMD cards without ROCm (v0.17.0) */
let gpuState = null;
async function renderGpuTune() {
  gpuState = await api().gpu_tune_status();
  const box = $("#gpuTune");
  box.hidden = !(gpuState.suggest || gpuState.applied) || !gpuState.installed;
  $("#gpuConfirm").hidden = true;
  $("#gpuTuneText").textContent = T(gpuState.applied ? "gpuOnText" : "gpuOffText");
  $("#btnGpuTune").textContent = T(gpuState.applied ? "gpuUndo" : "gpuApply");
}

async function renderPerf() {
  renderGpuTune();
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
  capturing = null;
  renderLegalStatus();
  renderKeys();
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
    if (capturing) {  // Settings > Shortcuts is waiting for keys
      e.preventDefault();
      e.stopPropagation();
      const combo = comboOf(e);
      if (!combo) return;
      const id = capturing;
      capturing = null;
      if (combo === "Esc") return renderKeys();
      return saveShortcut(id, combo === "Backspace" || combo === "Delete" ? "" : combo);
    }
    if (!$("#legalModal").hidden) return;  // v0.17.0: nothing works before the terms are accepted
    if (e.key === "Escape" && confirmId) { answerConfirm(false); return; }
    if (e.key === "Escape" && $("#app").classList.contains("zen")) { toggleZen(false); return; }
    if (e.key === "Escape" && tutorialStep >= 0) { tutorialSkip(); return; }
    if (e.key === "Escape" && !$("#guide").hidden) { toggleGuide(false); return; }
    const combo = comboOf(e), act = combo && actionFor(combo);
    const typing = e.target.closest && e.target.closest("input, textarea, select");
    if (act && !(typing && !e.ctrlKey && !e.altKey && !/^F\d/.test(combo))) {
      e.preventDefault();
      if (act.feature && !feature(act.feature)) return;
      if (act.panel && isOpen(act.panel)) { $("#" + act.panel).hidden = true; return; }  // the same keys close it
      if (act.id === "talk" && feature("hold_talk")) {
        if (!e.repeat && !holdKey) {
          holdKey = e.code;
          api().hold_start().then((r) => { if (!r.ok) { holdKey = null; notice(T("voiceLoading"), T("moreVoice")); } });
        }
        return;
      }
      if (act.id !== "guide") toggleGuide(false);
      act.run();
      return;
    }
    if (e.key === "Escape") {
      const open = $$(".modal:not([hidden]), .drawer:not([hidden])");
      if (open.length) open.forEach((m) => (m.hidden = true)); else dock("interrupt");
    }
  });

  // Click outside a modal/drawer box closes it (press and release on the backdrop, so selecting text doesn't).
  $$(".modal:not(#confirmModal):not(#legalModal), .drawer").forEach((m) => {
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
  $("#btnMapRail").onclick = () => openMap();
  $("#btnTraining").onclick = () => toggleTraining();
  $("#tabLearned").addEventListener("click", renderLearned);
  $("#learnedList").addEventListener("click", async (e) => {
    const del = e.target.closest("[data-del-training]");
    if (del) { await api().training_delete(+del.dataset.delTraining); return renderLearned(); }
    const head = e.target.closest("[data-training]");
    if (head) head.closest("li").classList.toggle("open");
  });
  $("#memSources").addEventListener("click", (e) => {
    const b = e.target.closest("[data-src]");
    if (b) { memFilter = b.dataset.src; renderDashboard(dash); }
  });
  $("#btnImportMem").onclick = () => openImport();
  initSetGroups();
  wireLogin();
  wireAccount();
  $("#btnSysCheck").onclick = (e) => runSystemCheck(e.target);
  $("#setNav").addEventListener("click", (e) => { const g = e.target.closest("button.set-group"); if (g) toggleGroup(g.dataset.group); });
  $("#grpCollapseAll").onclick = () => { $$("#setNav button.set-group").forEach((g) => foldedGroups.add(g.dataset.group)); applyGroups(); };
  $("#grpExpandAll").onclick = () => { foldedGroups.clear(); applyGroups(); };
  $("#integGrid").addEventListener("click", onIntegClick);
  $("#modelGrid").addEventListener("click", onModelsClick);
  $("#modelNo").onclick = () => { $("#modelConfirm").hidden = true; modelPending = null; };
  $("#modelYes").onclick = async () => {
    $("#modelConfirm").hidden = true;
    const r = await api().model_pull(modelPending);
    notice(r.ok ? T("modelDlStarted") : T("modelDlBusy"));
  };
  $("#integCustomList").addEventListener("click", onIntegClick);
  $("#btnIcAdd").onclick = addCustomIntegration;
  $("#appsList").addEventListener("click", onAppsClick);
  $("#appsFilter").oninput = drawApps;
  $("#btnAppsRefresh").onclick = () => renderApps(true);
  $("#btnSuspendNow").onclick = () => api().suspend("manual", "");
  $$("[data-media]").forEach((b) => (b.onclick = async () => { await api().media_action(b.dataset.media); setTimeout(renderMedia, 700); }));
  $("#mediaVol").oninput = (e) => {
    $("#mediaVolOut").textContent = e.target.value + "%";
    clearTimeout(volTimer); volTimer = setTimeout(() => api().media_action("volume", +e.target.value), 120);
  };
  $("#importAis").addEventListener("click", (e) => {
    const b = e.target.closest("[data-ai]");
    if (b) { importAi = b.dataset.ai; renderImportAis(); }
  });
  $("#btnImportCopy").onclick = (e) => copyText($("#importPrompt").value, e.currentTarget);
  $("#btnImportGo").onclick = async () => {
    const r = await api().import_memories(importAi, $("#importAnswer").value);
    $("#importResult").textContent = r.added || r.skipped ? T("importResult", { added: r.added, skipped: r.skipped }) : T("importNone");
    if (r.added) $("#importAnswer").value = "";
    loadDashboard();
  };
  $("#mapNodes").addEventListener("click", (e) => {
    const b = e.target.closest("[data-node]");
    if (!b) return;
    const n = mapNodes[+b.dataset.node];
    $("#mapDetail").innerHTML = `<b>${esc(n.label)}</b>` + (n.detail || []).filter((x) => x !== n.label).slice(0, 12).map((x) => `<span>${esc(x)}</span>`).join("");
    $("#mapDetail").hidden = false;
  });
  // hold-to-talk: releasing the key (or the Ctrl key) stops recording and sends
  const holdEnd = (e) => {
    if (!holdKey || (e && e.code !== holdKey && !["Control", "Shift", "Alt"].includes(e.key))) return;
    holdKey = null;
    api().hold_stop();
  };
  document.addEventListener("keyup", holdEnd);
  addEventListener("blur", () => holdEnd());
  $$("[data-opt]").forEach((b) => (b.onclick = () => {
    if (b.dataset.opt === "data") { $("#optConfirm").hidden = false; return; }  // second confirmation below
    runOptimize(b.dataset.opt);
  }));
  $("#optNo").onclick = () => ($("#optConfirm").hidden = true);
  $$("[data-legal-tabs]").forEach((tabs) => tabs.addEventListener("click", (e) => {
    const b = e.target.closest("[data-doc]");
    if (b) renderLegalDoc(tabs.dataset.legalTabs === "modal" ? "legalDocModal" : "legalDocSettings", b.dataset.doc);
  }));
  const legalReady = () => ($("#legalAccept").disabled = !($("#legalAge").checked && $("#legalAgree").checked));
  $("#legalAge").onchange = $("#legalAgree").onchange = legalReady;
  $("#legalAccept").onclick = acceptLegal;
  $("#legalDecline").onclick = () => api().quit();
  $("#btnRevoke").onclick = async () => {
    await api().revoke_terms();
    settings.terms_version = settings.terms_accepted_at = "";
    try { localStorage.setItem("nexus.terms", ""); } catch (e) { /* ignore */ }
    $("#settings").hidden = true;
    await showLegal();
  };
  $("#btnGpuTune").onclick = () => {
    $("#gpuConfirmText").textContent = T(gpuState && gpuState.applied ? "gpuConfirmUndo" : "gpuConfirmApply");
    $("#gpuConfirm").hidden = false;
  };
  $("#gpuNo").onclick = () => ($("#gpuConfirm").hidden = true);
  $("#gpuYes").onclick = async () => {
    $("#gpuConfirm").hidden = true;
    $("#gpuTuneText").textContent = T("gpuWorking");
    const r = await api().gpu_tune(!(gpuState && gpuState.applied));
    notice(T(r.restarted ? "gpuDone" : "gpuNoRestart"));
    renderGpuTune();
  };
  $("#optYes").onclick = () => { $("#optConfirm").hidden = true; runOptimize("data"); };
  $("#btnAiFix").onclick = () => { api().speak_help(aiHelpText); notice(aiHelpText, T("moreAi")); };
  document.addEventListener("keydown", activity);
  document.addEventListener("mousedown", activity);
  document.addEventListener("wheel", activity, { passive: true });
  initExclusivePanels();
  initMovable();
  $("#keysList").addEventListener("click", (e) => {
    const b = e.target.closest("[data-action]");
    if (!b) return;
    capturing = capturing === b.dataset.action ? null : b.dataset.action;
    renderKeys();
  });
  $("#btnKeysReset").onclick = async () => { settings = (await api().save_settings({ shortcuts: {} })).settings; renderKeys(); };
  $("#btnTutorial").onclick = () => { $("#settings").hidden = true; startTutorial(); };
  $("#tutNext").onclick = () => tutorialGo(tutorialStep + 1);
  $("#tutSkip").onclick = () => tutorialSkip();
  $("#tutBack").onclick = () => tutorialGo(Math.max(0, tutorialStep - 1));
  $("#issuesFind").oninput = () => renderIssues();
  $("#issuesArea").onchange = () => renderIssues();
  const cf = $("#settingsForm");
  ["cursor_style", "cursor_size"].forEach((n) => (cf.elements[n].onchange = () => setCursor(cf.elements.cursor_style.value, cf.elements.cursor_size.value)));
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
  $("#btnColorsReset").onclick = () => pickTheme("nexus");
  ["color_ring", "color_core", "color_bg"].forEach((n) => colorForm.elements[n].addEventListener("input", () => {
    colorForm.elements.theme.value = "custom"; renderThemes(); }));
  $("#themeGrid").addEventListener("click", (e) => { const b = e.target.closest("[data-theme]"); if (b) pickTheme(b.dataset.theme); });
  $$("#centerCards [data-center]").forEach((b) => (b.onclick = () => {
    colorForm.elements.center_style.value = b.dataset.center;
    $$("#centerCards [data-center]").forEach((x) => x.classList.toggle("on", x === b));
    previewLook();
  }));
  $$("#bgCards [data-bg]").forEach((b) => (b.onclick = () => {
    colorForm.elements.bg_style.value = b.dataset.bg;
    $$("#bgCards [data-bg]").forEach((x) => x.classList.toggle("on", x === b));
    previewLook();
  }));
  ["ring_scale", "exchange_size", "ring_speed", "font_brand"].forEach((n) => colorForm.elements[n].addEventListener("input", previewLook));
  $("#amdBackend").addEventListener("click", onComputeClick);
  $("#amdNpu").addEventListener("click", onComputeClick);
  $("#amdBackendNo").onclick = () => ($("#amdBackendConfirm").hidden = true);
  $("#amdBackendYes").onclick = async () => {
    $("#amdBackendConfirm").hidden = true; notice(T("acApplying"));
    const r = await api().amd_backend_set(amdPending);
    notice(T(r.ok ? "acApplied" : "acUnsupported")); renderCompute();
  };
  $("#amdRefs").addEventListener("click", (e) => { const b = e.target.closest("[data-ref]"); if (b) api().amd_open_ref(b.dataset.ref); });
  $("#btnAmdFree").onclick = async () => { const r = await api().amd_free(); notice(T("amdFreed", { gb: gb(r.freed_mb || 0) })); amdTick(); };
  $("#btnAmdWarm").onclick = async () => { await api().amd_warm(); notice(T("amdWarming")); };
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
  // v0.16.5: by default only the ring moves and the text under it stays put (Settings > Interface)
  const follow = !!settings.exchange_follow, onStage = $("#stage"), onCore = $("#core");
  for (const [el, use] of [[onStage, follow], [onCore, !follow]]) {
    el.style.setProperty("--dx", (use ? dx : 0) + "px");
    el.style.setProperty("--dy", (use ? dy : 0) + "px");
  }
  if (save) try { localStorage.setItem("nexus.ringPos", JSON.stringify([dx, dy])); } catch (e) { /* ignore */ }
  return [dx, dy];
}
let ringPos = [0, 0];

function wireRingDrag() {
  let pos = [0, 0];
  try { pos = JSON.parse(localStorage.getItem("nexus.ringPos")) || [0, 0]; } catch (e) { /* ignore */ }
  pos = ringPos = setRingPos(pos[0], pos[1], false);
  const core = $("#core");  // v0.16.5: no tooltip - the guide (F1) explains it
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
    pos = ringPos = setRingPos(start.pos[0] + dx, start.pos[1] + dy, false);
  });
  const end = () => {
    if (start && start.moved) setRingPos(pos[0], pos[1]);
    start = null;
    core.classList.remove("dragging"); $("#stage").classList.remove("dragging");
  };
  core.addEventListener("pointerup", end);
  core.addEventListener("pointercancel", end);
  core.addEventListener("dblclick", () => (pos = ringPos = setRingPos(0, 0)));
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

document.querySelectorAll("[data-rings]").forEach((el) => (el.innerHTML = ringsSVG(el.dataset.rings) + PET_HTML));
$$(".wordmark").forEach((el) => (el.innerHTML = wordmarkHTML()));
requestAnimationFrame(() => $("#boot .wordmark").classList.add("is-on"));
applyLang("pt");
wire();
wakeRing();

if (window.pywebview && window.pywebview.api) start();
else window.addEventListener("pywebviewready", start);
