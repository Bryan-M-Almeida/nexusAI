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
  // Same ring stack as the landing page hero.
  const C = (r) => 2 * Math.PI * r;
  const dash = (r, frac, offset = 0) => `stroke-dasharray="${C(r) * frac} ${C(r) * (1 - frac)}"` + (offset ? ` stroke-dashoffset="${offset}"` : "");
  const boot = (delay, inner) => `<g class="ring-boot" style="--delay:${delay}s">${inner}</g>`;
  const spin = (dur, dir, inner) => `<g class="ring-spin" style="--dur:${dur}s;--dir:${dir}">${inner}</g>`;
  return `<svg class="hud-rings" viewBox="0 0 600 600" aria-hidden="true">
  <defs>
    <radialGradient id="${id}Core" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#0d1a2b" stop-opacity=".9"/><stop offset="60%" stop-color="#060b13" stop-opacity=".6"/><stop offset="100%" stop-color="#030508" stop-opacity="0"/></radialGradient>
    <filter id="${id}Glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <circle cx="300" cy="300" r="250" fill="url(#${id}Core)" class="ring-core"/>
  ${boot(0.9, `<g class="crosshair"><line x1="300" y1="0" x2="300" y2="34" class="st-red"/><line x1="300" y1="566" x2="300" y2="600" class="st-red"/>
    <line x1="300" y1="62" x2="300" y2="78" class="st-blue-bright"/><line x1="300" y1="522" x2="300" y2="538" class="st-red"/>
    <line x1="286" y1="72" x2="314" y2="72" class="st-red thin"/><line x1="286" y1="528" x2="314" y2="528" class="st-red thin"/></g>`)}
  ${boot(0, spin(140, "normal", `<circle cx="300" cy="300" r="292" class="st-faint" stroke-dasharray="2 7"/>`))}
  ${boot(0.15, spin(48, "reverse", `<circle cx="300" cy="300" r="272" class="st-band" ${dash(272, 0.72)}/><circle cx="300" cy="300" r="279" class="st-faint"/>`))}
  ${boot(0.3, spin(20, "normal", `<circle cx="300" cy="300" r="258" class="st-blue thin"/>
    <circle cx="300" cy="300" r="258" class="st-red bold" ${dash(258, 0.06)} filter="url(#${id}Glow)"/>
    <circle cx="300" cy="300" r="258" class="st-red bold" ${dash(258, 0.02, -810)}/>`))}
  ${boot(0.45, spin(28, "reverse", `<circle cx="300" cy="300" r="244" class="st-blue-bright bold" ${dash(244, 0.17)} filter="url(#${id}Glow)"/>
    <circle cx="300" cy="300" r="244" class="st-red" ${dash(244, 0.045, -140)}/>`))}
  ${boot(0.6, spin(90, "normal", `<circle cx="300" cy="300" r="230" class="st-ticks" stroke-dasharray="1.445 10.598"/><circle cx="300" cy="300" r="224" class="st-faint"/>`))}
  ${boot(0.75, `<g class="ring-sway" style="--dur:7s"><circle cx="300" cy="300" r="210" class="st-red bold" ${dash(210, 0.11, 36.3)} filter="url(#${id}Glow)"/></g>`)}
  ${boot(0.9, spin(60, "reverse", `<circle cx="300" cy="300" r="196" class="st-blue thin" ${dash(196, 0.9)}/>`))}
  ${boot(1, `<circle cx="300" cy="300" r="168" class="st-faint"/>`)}
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
      case "reset": if (streaming) { streaming.text = ""; streaming.el.querySelector(".txt").innerHTML = ""; } return;
      case "tool": return onTool(p);
      case "done": return onDone(p);
      case "error": return onError(p);
      case "refresh": return loadDashboard();
      case "voice": return setVoiceState(p);
      case "heard": return addMsg("user", p, true);
      case "alert": return onAlert(p);
      case "profile": return onProfile(p);
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
  $("#voiceToggle").checked = settings.voice_enabled;
  $("#wakeToggle").checked = settings.wake_mode;
  await new Promise((r) => setTimeout(r, Math.max(0, BOOT_MIN_MS - (Date.now() - t0))));
  $("#boot").classList.add("leaving");
  $("#app").hidden = false;
  requestAnimationFrame(() => $("#app").classList.add("on"));
  setTimeout(() => ($("#boot").hidden = true), 1200);
  await loadDashboard();
  for (const m of await api().history()) addMsg(m.role === "user" ? "user" : "nexus", m.content);
  const hello = await api().greet();
  addMsg("nexus", hello);
  if (!profile) openOnboarding();
  if (!st.llm.online || !st.llm.model_ready) addMsg("system", aiHelp(st.llm));
}

function aiHelp(llm) {
  return llm.online ? T("modelMissing", { model: llm.model }) : T("aiOfflineHelp", { model: llm.model });
}

function setAi(llm) {
  $("#chipAi").classList.toggle("on", !!(llm.online && llm.model_ready));
  $("#chipAi").title = llm.online ? llm.model : T("offline");
}

/* ------------------------------------------------------------------ conversation */
function addMsg(kind, text, spoken = false) {
  const el = document.createElement("div");
  el.className = `msg ${kind}`;
  const who = kind === "user" ? T("you") + (spoken ? " · 🎙 " + T("heard") : "") : kind === "nexus" ? "N.E.X.U.S" : "";
  el.innerHTML = (who ? `<span class="who">${esc(who)}</span>` : "") + `<div class="txt">${kind === "nexus" ? md(text) : esc(text)}</div>`;
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
}

function onTool(p) {
  const s = ensureStream();
  const chip = document.createElement("span");
  chip.className = "tool-chip";
  chip.textContent = "⚙ " + (T("tool")[p.name] || p.name);
  s.el.insertBefore(chip, s.el.querySelector(".txt"));
}

function onDone(p) {
  const s = ensureStream();
  s.el.querySelector(".txt").classList.remove("caret");
  s.el.querySelector(".txt").innerHTML = md(p.text);
  streaming = null;
  setVoiceState(settings.wake_mode ? "standby" : "idle");
  if (p.text && $("#voiceToggle").checked) api().speak(p.text);
}

function onError(p) {
  if (streaming) { streaming.el.remove(); streaming = null; }
  addMsg("system", p.message).classList.add("error");
  setVoiceState("idle");
  api().get_settings().then((r) => setAi(r.llm));
}

function onAlert(a) {
  const el = document.createElement("div");
  el.className = "toast";
  el.innerHTML = `<b>${esc(T("reminder"))}</b>${esc(a.text)}`;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 15000);
  addMsg("system", "⏰ " + a.text);
  loadDashboard();
}

function send(text) {
  text = text.trim();
  if (!text) return;
  api().stop_speaking();
  addMsg("user", text);
  api().send(text, false);
}

/* ------------------------------------------------------------------ voice */
function setVoiceState(state) {
  voiceState = state;
  if (state === "idle" && settings.wake_mode) state = "standby";
  $("#core").dataset.state = state;
  $("#coreLabel").textContent = T("st_" + state) || "";
  $("#btnMic").classList.toggle("live", state === "listening" || state === "awake");
  $("#chipVoice").classList.toggle("on", state !== "idle" || settings.wake_mode);
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
  $("#kbStats").innerHTML = d.knowledge.map((k) => `<div class="kb-stat"><b>${k.chunks}</b>${esc(k.category)}</div>`).join("");
  if (!$("#kbSearch").value) renderDocs(d.documents);
  $("#collectionList").innerHTML = d.collections.map((c) => `
    <li class="clickable" data-collection="${esc(c.collection)}"><span class="body">${esc(c.collection)}<span class="meta">${c.items} · ${esc(c.last.slice(0, 10))}</span></span></li>`).join("") || empty("noCollections");
  $("#noteList").innerHTML = d.notes.map((n) => `
    <li><span class="body"><b>${esc(n.title)}</b><span class="meta">${esc(n.content.slice(0, 140))}</span></span></li>`).join("") || empty("noNotes");
}

function renderDocs(docs) {
  $("#kbList").innerHTML = docs.map((doc) => `
    <li><span class="body">${esc(doc.title)}<span class="meta">${esc(doc.category)} · ${esc(doc.source.split(":")[0])}</span></span>
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

async function openSettings() {
  const r = await api().get_settings();
  const f = $("#settingsForm");
  for (const [k, v] of Object.entries(r.settings)) {
    const el = f.elements[k];
    if (!el) continue;
    if (el.type === "checkbox") el.checked = !!v; else el.value = v;
  }
  $("#modelList").innerHTML = r.llm.models.map((m) => `<option value="${esc(m)}">`).join("");
  voices = r.voices || [];
  renderVoiceInfo();
  $("#aiStatus").innerHTML = r.llm.online && r.llm.model_ready
    ? `<span class="ok">● ${esc(T("aiOk"))}</span> — ${esc(r.llm.model)}`
    : `<span class="bad">● ${esc(aiHelp(r.llm))}</span>`;
  setAi(r.llm);
  $("#settings").hidden = false;
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
    tts_speed: f.elements.tts_speed.value };
  settings = (await api().save_settings(changes)).settings;
  api().test_voice(T("voiceSample", { name: profile ? profile.name.split(" ")[0] : "" }));
}

/* ------------------------------------------------------------------ wiring */
function wire() {
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); send($("#prompt").value); $("#prompt").value = ""; });
  $("#btnMic").onclick = async () => {
    const r = await api().push_to_talk();
    if (!r.ok) addMsg("system", T("voiceLoading") + (r.error && r.error !== "loading" ? ` (${r.error})` : ""));
  };
  $("#btnStop").onclick = () => api().stop_speaking();
  $("#wakeToggle").onchange = (e) => { settings.wake_mode = e.target.checked; api().set_wake_mode(e.target.checked); setVoiceState("idle"); };
  $("#voiceToggle").onchange = (e) => { settings.voice_enabled = e.target.checked; api().save_settings({ voice_enabled: e.target.checked }); };
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.code === "Space") { e.preventDefault(); $("#btnMic").click(); }
    if (e.key === "Escape") { api().stop_speaking(); $$(".modal").forEach((m) => (m.hidden = true)); }
  });

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
  $("#btnTestVoice").onclick = testVoice;
  $("#settingsForm").elements.voice_gender.onchange = renderVoiceInfo;
  $("#settingsForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target, changes = {};
    for (const el of f.elements) if (el.name) changes[el.name] = el.type === "checkbox" ? el.checked : el.value;
    const r = await api().save_settings(changes);
    settings = r.settings;
    setAi(r.llm);
    applyLang(r.lang);
    $("#settings").hidden = true;
  });
  $("#btnReimport").onclick = () => { $("#settings").hidden = true; openOnboarding(); };
  $("#btnClearChat").onclick = async () => { await api().clear_history(); $("#chat").innerHTML = ""; $("#settings").hidden = true; };
  $$("[data-close]").forEach((b) => (b.onclick = () => (b.closest(".modal").hidden = true)));

  setInterval(() => ($("#clock").textContent = new Date().toLocaleTimeString(document.documentElement.lang, { hour: "2-digit", minute: "2-digit" })), 1000);
}

async function showCollection(name) {
  const rows = await api().collection(name);
  $("#recordView").innerHTML = `<div class="records"><b>${esc(name)}</b>${rows.map((r) => {
    const { id, created, ...rest } = r;
    return `<div>#${id} · ${esc(created.slice(0, 16).replace("T", " "))} · ${esc(Object.entries(rest).map(([k, v]) => `${k}: ${v}`).join(" · "))}</div>`;
  }).join("")}</div>`;
}

/* ------------------------------------------------------------------ init */
const api = () => window.pywebview.api;

document.querySelectorAll("[data-rings]").forEach((el) => (el.innerHTML = ringsSVG(el.dataset.rings)));
$$(".wordmark").forEach((el) => (el.innerHTML = wordmarkHTML()));
requestAnimationFrame(() => $("#boot .wordmark").classList.add("is-on"));
applyLang("pt");
wire();

if (window.pywebview && window.pywebview.api) start();
else window.addEventListener("pywebviewready", start);
