// Dev-only fake backend: open index.html?mock in a browser to work on the UI without Python.
if (!window.pywebview && location.search.includes("mock")) {
  const now = new Date();
  const iso = (h, m = 0, d = 0) => {
    const x = new Date(now); x.setDate(x.getDate() + d); x.setHours(h, m, 0, 0);
    return new Date(x - x.getTimezoneOffset() * 6e4).toISOString().slice(0, 16);
  };
  const profile = { name: "Alex Martins", profession: "Full-Stack Developer", routine: "Starts at 9 AM · deep focus in the afternoon",
    interests: ["AI", "games", "coffee"], goals: ["Ship NEXUS"], profile: "developer", tone: "técnico e direto",
    modules: ["código", "agenda", "foco/pomodoro"], language: "pt-BR" };
  const now_s = Date.now() / 1000;
  let mockCx = [["weather", "online", "Open-Meteo", 900, "cached", 6, 3], ["currency", "online", "Frankfurter (BCE/ECB)", 3600, "cached", 9, 7],
    ["crypto", "online", "CoinGecko", 300, "sleeping", 1, 0], ["clock", "online", "Open-Meteo", 21600, "sleeping", 2, 1],
    ["translate", "online", "MyMemory", 2592000, "cached", 3, 1], ["holidays", "online", "Nager.Date", 86400, "sleeping", 1, 0],
    ["air", "online", "Open-Meteo (CAMS)", 1800, "sleeping", 0, 0], ["news", "online", "Google News", 900, "active", 4, 1],
    ["wikipedia", "online", "Wikipedia", 86400, "sleeping", 2, 0], ["calendar", "online", "ICS", 0, "sleeping", 0, 0],
    ["calc", "local", "NEXUS", 0, "sleeping", 12, 0], ["units", "local", "NEXUS", 0, "sleeping", 3, 0]]
    .map(([id, kind, provider, ttl, st, uses, cached]) => ({ id, kind, provider, ttl, on: true, state: st, uses, cached, net: uses - cached,
      until: st === "cached" ? now_s + 1500 : 0, last: now_s - 60, error: "" }));
  mockCx.push({ id: "custom_gas", kind: "custom", name: "Preço da gasolina", keywords: "gasolina, combustível", url: "https://api.exemplo.com/gas?q={query}",
    provider: "api.exemplo.com", ttl: 3600, on: true, state: "sleeping", uses: 0, net: 0, cached: 0, until: 0, error: "" });
  const mockApps = [["RetroArch", "game"], ["PCSX2", "game"], ["Steam", "launcher"], ["XBOX", "launcher"], ["Visual Studio Code", "work"],
    ["Discord", "work"], ["Google Chrome", "work"], ["LiMusic", "work"], ["Notion", "work"], ["WhatsApp", "work"], ["Spotify", "work"]]
    .map(([name, kind]) => ({ name, kind, id: name }));
  let mockT = 0;
  const mockModel = () => [{ name: "qwen3:8b", size_mb: 6782, vram_mb: 6242 }];
  const mockAi = () => ({ count: 9, tok_s: 22.7, prompt_tok_s: 7604, first_s: 2.4, last: { gen_tokens: 72, tok_s: 22.4, total_s: 5.9 },
    history: [22.7, 23.1, 21.8, 22.4, 24.0, 22.9, 23.3, 22.1, 22.4] });
  let mockFull = false; let mockTrain = false; let mockTerms = /terms=1/.test(location.search), mockGpu = false;
  const settings = { ui_layout: "computer", bar_top: "hover", bar_left: "hover", bar_right: "hover", bar_bottom: "hover", ring_wander: true, rest_minutes: 3, show_exchange: true, exchange_follow: false, exchange_hide_seconds: 45, cursor_style: "ring", cursor_size: "medium", shortcuts: {}, tutorial_done: true, speak_menus: true, beta_map: true, beta_hold_talk: false, beta_training: true, beta_memory_import: true, app_mode: "user", beta_library: true, color_ring: "#cfe4ff", color_core: "#2f86ff", color_bg: "#0b1f5c", llm_base_url: "http://localhost:11434/v1", llm_model: "qwen3:8b", language: "auto", stt_model: "small",
    voice_gender: "male", voice_effect: "jarvis", tts_speed: 0, tts_volume: 100, llm_preset: "ollama", llm_api_key: "ollama",
    llm_temperature: 0.3, llm_context: 8192, history_turns: 12, auto_title: true, greet_on_start: true, start_fullscreen: true,
    mic_device: "", vad_threshold: 0.5, vad_silence: 0.7, reminder_leads: "60,10,0", speak_reminders: true,
    ai_target: "local", bg_wake_only: true, bg_release_minutes: 10, pause_when_unfocused: true, network_mode: "hybrid", performance: "balanced", stt_beam: 5, llm_keep_alive: "2h", llm_num_gpu: -1, desktop_notifications: true, notify_sound: true, quiet_hours: "", daily_briefing: "", show_hud: true, show_captions: true, reduce_motion: false, auto_memory: true, voice_enabled: true, bridge_port: 47800,
    integrations: true, home_city: "São Paulo", beta_media: true, beta_apps: true, theme: "nexus", ring_scale: 100, ring_speed: "normal", exchange_size: 14, bg_style: "glow", font_brand: "orbitron", music_player: "limusic", apps_suspend: "games", game_watch: false, home_currency: "", home_country: "", calendar_ics_url: "", ai_mode: "assistant",
    ui_mode: "audio", mic_muted: false, require_wake_word: false };
  const llm = { online: true, model_ready: true, model: "qwen3:8b", models: ["qwen3:8b"] };
  const VOICES = [{ name: "Microsoft Maria", gender: "female", lang: "pt" }, { name: "Microsoft Zira", gender: "female", lang: "en" },
    { name: "Microsoft Daniel", gender: "male", lang: "pt" }];
  const REPLY = "Claro. Pela base local, o **estoicismo** foca no que depende de você.";
  const emit = (e, p, ms) => setTimeout(() => window.nexus.on(e, p), ms);
  let temporary = false;
  const state = () => ({ ui_mode: settings.ui_mode, mic_muted: settings.mic_muted, voice_enabled: settings.voice_enabled, stt: "ready",
    ai_mode: settings.ai_mode, temporary });
  // Fake speech: a syllable-like envelope so the ring visibly breathes with the "voice".
  const speak = (seconds, delay = 0) => {
    if (settings.ui_mode !== "audio" || !settings.voice_enabled) return;
    const env = Array.from({ length: Math.round(seconds / 0.04) }, (_, i) => Math.max(0, Math.sin(i / 2.2)) * (0.5 + 0.5 * Math.random()));
    emit("voice", "speaking", delay); emit("speak_env", { env, dt: 0.04 }, delay); emit("voice", "idle", delay + seconds * 1000);
  };
  window.mockUserTalks = (seconds = 2) => {  // call from the console to see the ring shrink with the mic
    for (let i = 0; i < seconds * 16; i++) emit("mic_level", Math.abs(Math.sin(i / 3)) * 0.9, i * 62);
  };
  window.pywebview = { api: {
    ui_ready: async () => {},
    boot: async () => {
      ["memory", "knowledge", "ai", "voice"].forEach((k, i) => emit("boot", { key: k, ok: true, detail: ["3", "198", "qwen3:8b", "small"][i] }, 600 + i * 200));
      return { profile, lang: "pt", llm, settings, stt: "ready", version: "0.17.0", model_name: "NEX-1.0",
        terms: { accepted: mockTerms, version: "1.2", accepted_at: mockTerms ? new Date().toISOString() : "" } };
    },
    greet: async () => { speak(2.5, 200); return "Olá, Alex, o que teremos para hoje?"; },
    history: async () => [],
    dashboard: async () => ({
      profile,
      tasks: [{ id: 1, title: "Revisar PRs do NEXUS", due: iso(18), priority: "high" }, { id: 2, title: "Comprar café", due: null, priority: "normal" }],
      events: [{ id: 1, title: "Daily com o time", start: iso(9, 30), notes: "" }, { id: 2, title: "Pitch do hackathon", start: iso(15, 0, 1), notes: "Sala 2" }],
      memories: [{ id: 1, content: "Prefere café sem açúcar", category: "preferencia", created: iso(10), source: "chat" }, { id: 9, content: "Trabalha como desenvolvedor full-stack", category: "trabalho", created: iso(9), source: "import:chatgpt" },
        { id: 2, content: "Trabalha melhor à tarde", category: "rotina", created: iso(10), source: "auto" }],
      actions: [{ ts: iso(10), kind: "tarefa", summary: "Criou tarefa #1: Revisar PRs do NEXUS" }],
      knowledge: [{ category: "Primeiros Socorros", docs: 1, chunks: 10 }, { category: "Filosofia", docs: 1, chunks: 11 }, { category: "Finanças", docs: 1, chunks: 12 }, { category: "Programação", docs: 1, chunks: 13 }, { category: "Saúde", docs: 1, chunks: 14 }, { category: "Produtividade", docs: 1, chunks: 15 }, { category: "Anatomia", docs: 1, chunks: 10 }, { category: "First Aid", docs: 1, chunks: 11 }, { category: "Philosophy", docs: 1, chunks: 12 }, { category: "Finance", docs: 1, chunks: 13 }, { category: "Programming", docs: 1, chunks: 14 }, { category: "Health", docs: 1, chunks: 15 }, { category: "Productivity", docs: 1, chunks: 10 }, { category: "Anatomy", docs: 1, chunks: 11 }, { category: "Primeros Auxilios", docs: 1, chunks: 12 }, { category: "Filosofía", docs: 1, chunks: 13 }, { category: "Finanzas", docs: 1, chunks: 14 }, { category: "Programación", docs: 1, chunks: 15 }, { category: "Salud", docs: 1, chunks: 10 }, { category: "Productividad", docs: 1, chunks: 11 }, { category: "Anatomía", docs: 1, chunks: 12 }],
      documents: [{ id: 1, title: "Manual — Primeiros Socorros", category: "Primeiros Socorros", source: "seed:pt/x.md" }, { id: 2, title: "Manual — Filosofia", category: "Filosofia", source: "seed:pt/x.md" }, { id: 3, title: "Manual — Finanças", category: "Finanças", source: "seed:pt/x.md" }, { id: 4, title: "Manual — Programação", category: "Programação", source: "seed:pt/x.md" }, { id: 5, title: "Manual — Saúde", category: "Saúde", source: "seed:pt/x.md" }, { id: 6, title: "Manual — Produtividade", category: "Produtividade", source: "seed:pt/x.md" }, { id: 7, title: "Manual — Anatomia", category: "Anatomia", source: "seed:pt/x.md" }, { id: 8, title: "Manual — First Aid", category: "First Aid", source: "seed:pt/x.md" }, { id: 9, title: "Manual — Philosophy", category: "Philosophy", source: "seed:pt/x.md" }, { id: 10, title: "Manual — Finance", category: "Finance", source: "seed:pt/x.md" }, { id: 11, title: "Manual — Programming", category: "Programming", source: "seed:pt/x.md" }, { id: 12, title: "Manual — Health", category: "Health", source: "seed:pt/x.md" }, { id: 13, title: "Manual — Productivity", category: "Productivity", source: "seed:pt/x.md" }, { id: 14, title: "Manual — Anatomy", category: "Anatomy", source: "seed:pt/x.md" }, { id: 15, title: "Manual — Primeros Auxilios", category: "Primeros Auxilios", source: "seed:pt/x.md" }, { id: 16, title: "Manual — Filosofía", category: "Filosofía", source: "seed:pt/x.md" }, { id: 17, title: "Manual — Finanzas", category: "Finanzas", source: "seed:pt/x.md" }, { id: 18, title: "Manual — Programación", category: "Programación", source: "seed:pt/x.md" }, { id: 19, title: "Manual — Salud", category: "Salud", source: "seed:pt/x.md" }, { id: 20, title: "Manual — Productividad", category: "Productividad", source: "seed:pt/x.md" }, { id: 21, title: "Manual — Anatomía", category: "Anatomía", source: "seed:pt/x.md" }, { id: 99, title: "Horário da academia", category: "aprendido", source: "learned:academia" }],
      collections: [{ collection: "gastos", items: 3, last: iso(12) }],
      notes: [{ title: "Ideias", content: "Integração com smart home na fase 3" }],
    }),
    send: async (text) => {
      if (/^(repete|pausa|para|continua)/i.test(text)) { emit("control", { action: "repeat", intro: "Claro, vou repetir.", text: REPLY }, 50); speak(3, 100); return { control: "repeat" }; }
      emit("tool", { name: "search_knowledge", args: {} }, 400);
      REPLY.split(" ").forEach((w, i) => emit("token", w + " ", 600 + i * 60));
      emit("done", { text: REPLY, speak: true }, 1400);
      speak(4, 1450);
      return { control: null };
    },
    set_mode: async (m) => { settings.ui_mode = m; return state(); },
    set_ai_mode: async (m) => { settings.ai_mode = m; speak(1.5); return { ...state(), spoken: `Executando em modo ${m === "direct" ? "Direto" : "Assistente"}.` }; },
    conversations: async () => ({ current: 3, list: [
      { id: 3, title: "Simulado USMLE", description: "Questões de múltipla escolha corrigidas uma a uma.", created: iso(15), updated: iso(16), messages: 18 },
      { id: 2, title: "Peso do coração", description: "Valores médios do coração adulto por sexo.", created: iso(11, 0, -1), updated: iso(11, 20, -1), messages: 6 },
      { id: 1, title: "O que você pode fazer?", description: "", created: iso(9, 0, -2), updated: iso(9, 5, -2), messages: 2 }] }),
    timeline: async (before) => before ? [] : [
      { id: 1, role: "user", content: "O que você pode fazer?", ts: iso(9, 0, -2), conversation_id: 1, title: "O que você pode fazer?" },
      { id: 2, role: "assistant", content: "Posso cuidar da sua agenda, tarefas, dados e responder por voz.", ts: iso(9, 1, -2), conversation_id: 1, title: "O que você pode fazer?" },
      { id: 3, role: "user", content: "Quanto pesa o coração de um homem adulto?", ts: iso(11, 0, -1), conversation_id: 2, title: "Peso do coração" },
      { id: 4, role: "assistant", content: "Em média de 280 a 340 gramas.", ts: iso(11, 1, -1), conversation_id: 2, title: "Peso do coração" },
      { id: 5, role: "user", content: "Me dê uma aula para o USMLE", ts: iso(15), conversation_id: 3, title: "Simulado USMLE" }],
    open_conversation: async (id) => ({ ok: true, messages: [{ role: "user", content: "Quanto pesa o coração de um homem adulto?" }, { role: "assistant", content: "Em média de 280 a 340 gramas." }], ...state() }),
    new_conversation: async () => state(), delete_conversation: async () => ({}), rename_conversation: async () => ({}),
    set_background: async () => ({}),
    books: async () => [{ id: 1, title: "Dom Casmurro", kind: "epub", chars: 380000, position: 95000, progress: 0.25 },
      { id: 2, title: "Manual de Python", kind: "pdf", chars: 210000, position: 0, progress: 0 }],
    add_books: async () => ({ results: [], books: await window.pywebview.api.books() }),
    book_page: async (id, pos) => ({ text: "CAPÍTULO I\n\nDO TÍTULO\n\nUma noite destas, vindo da cidade para o Engenho Novo, encontrei no trem da Central um rapaz aqui do bairro, que eu conheço de vista e de chapéu. ".repeat(6),
      start: pos || 95000, end: (pos || 95000) + 2400, chars: 380000, book: { id, title: "Dom Casmurro", position: 95000, chars: 380000 } }),
    podcast_start: async (id) => ({ active: true, id, title: "Dom Casmurro", position: 95000, progress: 0.25, paused: false }),
    podcast_toggle: async () => ({ active: true, id: 1, title: "Dom Casmurro", progress: 0.25, paused: true }),
    podcast_stop: async () => ({ active: false }), delete_book: async () => [],
    attach_files: async () => ({ results: [{ ok: true, name: "relatorio.pdf", kind: "pdf" }], pending: [{ name: "relatorio.pdf", kind: "pdf" }] }),
    attach_blob: async (n) => ({ results: [{ ok: true, name: n, kind: "text" }], pending: [{ name: n, kind: "text" }] }),
    clear_attachments: async () => ({ pending: [] }),
    switch_ai: async (t) => { settings.ai_target = t; return { ...state(), ai_target: t, need_setup: t === "api", llm, settings }; },
    skills: async () => ({ level: 3, rank: "D", total_xp: 640, progress: 0.4, skills: [
      { skill: "organization", level: 4, rank: "D", xp: 380, progress: 0.1, next: 220 }, { skill: "programming", level: 3, rank: "D", xp: 250, progress: 0.4, next: 110 },
      { skill: "study", level: 2, rank: "E", xp: 90, progress: 0.25, next: 90 }, { skill: "finance", level: 1, rank: "E", xp: 20, progress: 0.33, next: 40 },
      { skill: "health", level: 1, rank: "E", xp: 0, progress: 0, next: 60 }, { skill: "knowledge", level: 2, rank: "E", xp: 70, progress: 0.08, next: 110 },
      { skill: "research", level: 1, rank: "E", xp: 30, progress: 0.5, next: 30 }, { skill: "voice", level: 1, rank: "E", xp: 12, progress: 0.2, next: 48 }] }),
    quick_profile: async () => ({ ok: true }), list_backups: async () => [{ name: "nexus-auto-20261014-180000.zip", size: 812345 }],
    create_backup: async () => ({ ok: true, file: "C:/x/nexus-backup-20261014-200000.zip", backups: [] }),
    restore_backup: async () => ({ ok: true }), open_backups_folder: async () => {},
    performance_info: async () => ({ hardware: { cpu: "AMD Ryzen 5 5600G with Radeon Graphics", cores: 12, ram_gb: 15.8,
      gpus: [{ name: "AMD Radeon RX 6600 XT", vram_gb: 8 }], vram_gb: 8 }, max_allowed: true, max_reason: "", max_context: 8192, minimum: true, recommended: true }),
    set_performance: async (p) => { settings.performance = p; return { settings, llm, state: state(), perf: {} }; },
    set_network: async (m) => { settings.network_mode = m; return state(); },
    set_focus: async (on) => ({ ...state(), focus: on }),
    workspaces: async () => [{ id: 1, name: "App de Finanças", description: "Controle de gastos em Python com gráficos.", files: 4, updated: iso(16) }],
    open_workspace: async () => ({ ...state(), focus: true, workspace: { id: 1, name: "App de Finanças" }, messages: [
        { role: "user", content: "Crie a estrutura do projeto com um main.py" }, { role: "assistant", content: "Criei `main.py`, `gastos.py` e `README.md`." }],
      files: [{ path: "README.md", dir: false, size: 812 }, { path: "src", dir: true, size: 0 }, { path: "src/gastos.py", dir: false, size: 2310 }, { path: "src/main.py", dir: false, size: 640 }],
      changes: [{ id: 3, op: "edit", path: "src/main.py", ts: iso(16, 5) }, { id: 2, op: "create", path: "src/gastos.py", ts: iso(16, 2) }, { id: 1, op: "command", path: "python src/main.py", ts: iso(16, 1) }] }),
    create_workspace: async (n) => window.pywebview.api.open_workspace(1),
    close_workspace: async () => ({ ...state(), workspace: null, focus: false, messages: [] }),
    delete_workspace: async () => [], open_workspace_folder: async () => {},
    read_workspace_file: async (p) => ({ path: p, content: "def main():\n    print('NEXUS')\n\nif __name__ == '__main__':\n    main()\n" }),
    undo_workspace: async () => ({ ok: true, path: "src/main.py", files: [], changes: [] }),
    confirm_command: async () => {}, state: async () => state(),
    report_issue: async () => ({ ok: true, file: "C:/NEXUS/reports/nexus-report-20261014-120000.md" }),
    toggle_fullscreen: async () => (mockFull = !mockFull), minimize: async () => {}, quit: async () => {},
    llm_status: async () => llm, speak_help: async () => speak(4),
    hold_start: async () => ({ ok: true }), hold_stop: async () => {},
    training_state: async () => ({ active: mockTrain, lessons: 0 }),
    training_start: async () => { mockTrain = true; emit("training", { active: true }); emit("done", { text: "Modo treinamento ativado. Pode me ensinar.", speak: true }, 50); },
    training_finish: async () => {
      mockTrain = false; emit("training", { active: false });
      [0, 25, 55, 92, 100].forEach((p, i) => emit("training_progress", p, 300 * i));
      emit("training_done", { ok: true, score: 50, lessons: 4, unchecked: 1,
        learned: [{ fact: "Júpiter é o maior planeta do Sistema Solar.", verdict: "agree", note: "Wikipédia confirma.", source: "https://pt.wikipedia.org/wiki/Jupiter" },
                  { fact: "Meu planeta favorito é Saturno.", verdict: "personal", note: "", source: "" }],
        left_out: [{ fact: "Marte é o planeta mais próximo do Sol.", verdict: "disagree", note: "Mercúrio é o mais próximo do Sol.", source: "https://pt.wikipedia.org/wiki/Marte" },
                   { fact: "A Lua leva cerca de 27 dias para orbitar a Terra.", verdict: "unknown", note: "sem evidência no resumo", source: "" }] }, 1600);
      emit("done", { text: "Análise completa. Aprendi 2, deixei 2 de fora, e a concordância com as fontes foi de 50 por cento.", speak: true }, 1700);
    },
    training_history: async () => [{ id: 1, topic: "astronomia", started: "2026-10-16T12:00:00", finished: "2026-10-16T12:05:00", score: 50,
      facts: [{ fact: "Júpiter é o maior planeta do Sistema Solar.", verdict: "agree", note: "", source: "" }, { fact: "Marte é o planeta mais próximo do Sol.", verdict: "disagree", note: "Mercúrio", source: "" }] }],
    training_delete: async () => [],
    import_prompt: async () => ({ prompt: "Liste tudo o que você sabe e lembra sobre mim... - [preferencia] ...", sources: { chatgpt: "ChatGPT", claude: "Claude", gemini: "Gemini", copilot: "Copilot", other: "IA" } }),
    import_memories: async (src, text) => ({ ok: true, added: (text.match(/^\s*-/gm) || []).length, skipped: 0 }),
    memory_sources: async () => [],
    // v0.18.0: integrations hub, apps, media
    integrations_status: async () => ({ online: true, home_city: "São Paulo", home_currency: "BRL", home_country: "BR", items: mockCx }),
    integration_toggle: async (id, on) => { const x = mockCx.find((c) => c.id === id); if (x) { x.on = on; x.state = on ? "sleeping" : "off"; } return { ok: true, items: mockCx }; },
    integration_test: async (id) => ({ ok: true, ms: 214, cached: id === "currency", preview: '{"amount": 1, "from": "USD", "to": "BRL", "result": 5.08}' }),
    integration_add: async (name, keys, url) => { if (!/^https:\/\//.test(url)) return { ok: false, error: "url" };
      mockCx.push({ id: "custom_" + mockCx.length, kind: "custom", name, keywords: keys, url, provider: url.split("/")[2], ttl: 1800, on: true, state: "sleeping", uses: 0, net: 0, cached: 0, until: 0, error: "" });
      return { ok: true, items: mockCx }; },
    integration_remove: async (id) => { mockCx = mockCx.filter((c) => c.id !== id); return { ok: true, items: mockCx }; },
    apps_list: async () => ({ items: mockApps }),
    // v0.18.5: AMD panel
    amd_status: async () => ({ cards: [{ name: "AMD Radeon RX 6600 XT", vram_gb: 8, driver: "32.0.21045.5002", adrenalin: "26.8.1" }],
      tune: { amd: true, vulkan: true, applied: true, suggest: true, installed: true }, model: mockModel(),
      ai: mockAi(), refs: ["adrenalin", "rocm", "gpuopen", "developer", "ryzen_ai", "ollama_amd", "hackathon"] }),
    amd_live: async () => { mockT += 1; const busy = mockT % 6 < 3; return { gpu_pct: busy ? 70 + Math.random() * 15 : 3 + Math.random() * 4,
      engines: busy ? { Copy: 78, "3D": 4 } : { "3D": 4 }, ai_gpu_pct: busy ? 69 : 0, nexus_gpu_pct: 0, vram_used_mb: 7681, shared_used_mb: 1161,
      ai_vram_mb: 6213, ai: mockAi(), model: mockModel() }; },
    amd_open_ref: async () => ({ ok: true }), amd_free: async () => ({ freed_mb: 6213 }), amd_warm: async () => ({ ok: true }),
    set_preferences: async (c) => { Object.assign(settings, c); return { ok: true, applied: c, settings }; },
    app_mark: async (name, kind) => { const a = mockApps.find((x) => x.name === name); if (a) a.kind = kind; return { items: mockApps }; },
    app_open: async (name) => ({ ok: true, said: `Abrindo ${name}.` }),
    media_state: async () => ({ sessions: [], current: { app: "LiMusic", title: "Midnight City", artist: "M83", status: "playing" }, volume: 38, muted: false }),
    media_action: async () => ({ ok: true }),
    suspend: async () => { emit("suspended", { on: true, reason: "manual", app: "", vram_freed_mb: 5630 }, 300); emit("suspended", { on: false, source: "window" }, 3500); return { ok: true }; },
    accept_terms: async () => { mockTerms = true; return { accepted: true, version: "1.2", accepted_at: new Date().toISOString() }; },
    revoke_terms: async () => { mockTerms = false; return { accepted: false, version: "1.2" }; },
    gpu_tune_status: async () => ({ amd: true, vulkan: true, applied: mockGpu, suggest: true, installed: true }),
    gpu_tune: async (on) => { mockGpu = !!on; return { amd: true, vulkan: true, applied: mockGpu, suggest: true, installed: true, restarted: true }; },
    optimize: async (k) => (k === "data" ? { ok: true, backup: "C:/x/nexus-backup-test.zip", rss_mb: 120 } : { ok: true, freed_mb: 312.4, rss_mb: 188.1, freed_disk_mb: 1.2 }),
    concept_map: async () => ({ skills: ["organization", "finance", "programming", "study", "health", "knowledge", "research", "voice"].map((s, i) => ({ skill: s, rank: "EDCBA"[i % 5], level: 1 + i })),
      knowledge: [{ name: "Anatomia", items: ["Corpo humano"] }, { name: "Finanças", items: ["Juros compostos", "Reserva de emergência", "Inflação"] },
        { name: "Primeiros Socorros", items: ["RCP", "Engasgo"] }, { name: "Filosofia", items: ["Estoicismo"] }, { name: "Programação", items: ["Python", "JavaScript"] }],
      memories: ["Prefere café sem açúcar", "Trabalha melhor à tarde"] }),
    set_temporary: async (on) => { temporary = on; return state(); },
    set_mic: async (muted) => { settings.mic_muted = muted; return state(); },
    set_ai_voice: async (on) => { settings.voice_enabled = on; return state(); },
    interrupt: async () => emit("control", { action: "stop" }, 10),
    repeat: async () => { speak(3.5, 50); return { intro: "Acho que não entendeu, vou repetir.", text: REPLY }; },
    stop_speaking: async () => {}, push_to_talk: async () => { emit("voice", "listening", 10); window.mockUserTalks(2); emit("voice", "idle", 2200); return { ok: true }; },
    get_settings: async () => ({ settings, llm, langs: ["pt", "en", "es"], lang: "pt", voices: VOICES,
      presets: [{ id: "ollama", name: "Ollama", url: "http://127.0.0.1:11434/v1", local: true, key: false },
        { id: "openai", name: "OpenAI", url: "https://api.openai.com/v1", local: false, key: true },
        { id: "custom", name: "Custom (OpenAI-compatible)", url: "", local: null, key: true }],
      mics: { devices: ["Microfone (High Definition Audio)", "Microfone (DroidCam Audio)"], default: "Microfone (DroidCam Audio)" } }),
    notifications: async () => ({ unread: 1, items: [{ id: 2, ts: iso(14, 50), kind: "event", title: "Compromisso", body: "Lembrete: Pitch do hackathon em 10 minutos, às 15:00.", read: 0 },
      { id: 1, ts: iso(8), kind: "briefing", title: "Resumo do dia", body: "Bom dia, Alex. Hoje você tem 1 compromisso(s): 15:00 Pitch do hackathon. E 2 tarefa(s) pendente(s).", read: 1 }] }),
    mark_notifications_read: async () => {}, clear_notifications: async () => {}, briefing_now: async () => {},
    test_notification: async () => emit("alert", { kind: "test", text: "Notificações funcionando.", notification: { id: 3 }, sound: true }, 50),
    test_llm: async () => llm, open_data_folder: async () => {},
    test_voice: async () => speak(2.5),
    save_settings: async (c) => { Object.assign(settings, c); return { settings, llm, lang: c.language && c.language !== "auto" ? c.language : "pt" }; },
    search_knowledge: async () => [], collection: async () => [], import_knowledge_files: async () => [],
    add_task: async () => ({}), complete_task: async () => ({}), delete_task: async () => ({}), delete_event: async () => ({}),
    forget: async () => ({}), delete_document: async () => {}, clear_history: async () => {},
    import_profile_text: async () => ({ ok: false, error: "mock" }), import_profile_file: async () => ({ ok: false }), learn: async () => ({}),
  } };
}
