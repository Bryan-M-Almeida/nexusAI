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
  const settings = { llm_base_url: "http://localhost:11434/v1", llm_model: "qwen3:8b", language: "auto", stt_model: "small",
    voice_gender: "male", voice_effect: "jarvis", tts_speed: 0, auto_memory: true, voice_enabled: true, bridge_port: 47800,
    integrations: true, home_city: "São Paulo", calendar_ics_url: "",
    ui_mode: "audio", mic_muted: false, require_wake_word: false };
  const llm = { online: true, model_ready: true, model: "qwen3:8b", models: ["qwen3:8b"] };
  const VOICES = [{ name: "Microsoft Maria", gender: "female", lang: "pt" }, { name: "Microsoft Zira", gender: "female", lang: "en" },
    { name: "Microsoft Daniel", gender: "male", lang: "pt" }];
  const REPLY = "Claro. Pela base local, o **estoicismo** foca no que depende de você.";
  const emit = (e, p, ms) => setTimeout(() => window.nexus.on(e, p), ms);
  const state = () => ({ ui_mode: settings.ui_mode, mic_muted: settings.mic_muted, voice_enabled: settings.voice_enabled, stt: "ready" });
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
      return { profile, lang: "pt", llm, settings, stt: "ready", version: "0.3.0" };
    },
    greet: async () => { speak(2.5, 200); return "Olá, Alex, o que teremos para hoje?"; },
    history: async () => [],
    dashboard: async () => ({
      profile,
      tasks: [{ id: 1, title: "Revisar PRs do NEXUS", due: iso(18), priority: "high" }, { id: 2, title: "Comprar café", due: null, priority: "normal" }],
      events: [{ id: 1, title: "Daily com o time", start: iso(9, 30), notes: "" }, { id: 2, title: "Pitch do hackathon", start: iso(15, 0, 1), notes: "Sala 2" }],
      memories: [{ id: 1, content: "Prefere café sem açúcar", category: "preferencia", created: iso(10), source: "chat" },
        { id: 2, content: "Trabalha melhor à tarde", category: "rotina", created: iso(10), source: "auto" }],
      actions: [{ ts: iso(10), kind: "tarefa", summary: "Criou tarefa #1: Revisar PRs do NEXUS" }],
      knowledge: [{ category: "Primeiros Socorros", docs: 1, chunks: 14 }, { category: "Filosofia", docs: 1, chunks: 15 }, { category: "Finanças", docs: 1, chunks: 11 }, { category: "Programação", docs: 1, chunks: 12 }],
      documents: [{ id: 1, title: "Manual de Primeiros Socorros", category: "Primeiros Socorros", source: "seed:pt/primeiros_socorros.md" }],
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
    set_mic: async (muted) => { settings.mic_muted = muted; return state(); },
    set_ai_voice: async (on) => { settings.voice_enabled = on; return state(); },
    interrupt: async () => emit("control", { action: "stop" }, 10),
    repeat: async () => { speak(3.5, 50); return { intro: "Acho que não entendeu, vou repetir.", text: REPLY }; },
    stop_speaking: async () => {}, push_to_talk: async () => { emit("voice", "listening", 10); window.mockUserTalks(2); emit("voice", "idle", 2200); return { ok: true }; },
    get_settings: async () => ({ settings, llm, langs: ["pt", "en", "es"], lang: "pt", voices: VOICES }),
    test_voice: async () => speak(2.5),
    save_settings: async (c) => { Object.assign(settings, c); return { settings, llm, lang: c.language && c.language !== "auto" ? c.language : "pt" }; },
    search_knowledge: async () => [], collection: async () => [], import_knowledge_files: async () => [],
    add_task: async () => ({}), complete_task: async () => ({}), delete_task: async () => ({}), delete_event: async () => ({}),
    forget: async () => ({}), delete_document: async () => {}, clear_history: async () => {},
    import_profile_text: async () => ({ ok: false, error: "mock" }), import_profile_file: async () => ({ ok: false }), learn: async () => ({}),
  } };
}
