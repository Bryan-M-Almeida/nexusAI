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
    tts_rate: 185, auto_memory: true, voice_enabled: true, wake_mode: false, bridge_port: 47800 };
  const llm = { online: true, model_ready: true, model: "qwen3:8b", models: ["qwen3:8b"] };
  const emit = (e, p, ms) => setTimeout(() => window.nexus.on(e, p), ms);
  window.pywebview = { api: {
    ui_ready: async () => {},
    boot: async () => {
      ["memory", "knowledge", "ai", "voice"].forEach((k, i) => emit("boot", { key: k, ok: true, detail: ["3", "198", "qwen3:8b", "small"][i] }, 600 + i * 200));
      return { profile, lang: "pt", llm, settings };
    },
    greet: async () => "Boa tarde, Alex. Sistemas online. Você tem 2 compromisso(s) hoje.",
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
      emit("tool", { name: "search_knowledge", args: {} }, 400);
      "Claro. Pela base local, o **estoicismo** foca no que depende de você.".split(" ").forEach((w, i) => emit("token", w + " ", 600 + i * 60));
      emit("done", { text: "Claro. Pela base local, o **estoicismo** foca no que depende de você." }, 1400);
    },
    speak: async () => { emit("voice", "speaking", 50); emit("voice", "idle", 2500); },
    stop_speaking: async () => {}, push_to_talk: async () => { emit("voice", "listening", 10); emit("voice", "idle", 3000); return { ok: true }; },
    set_wake_mode: async () => {}, get_settings: async () => ({ settings, llm, langs: ["pt", "en", "es"], lang: "pt" }),
    save_settings: async (c) => { Object.assign(settings, c); return { settings, llm, lang: c.language && c.language !== "auto" ? c.language : "pt" }; },
    search_knowledge: async () => [], collection: async () => [], import_knowledge_files: async () => [],
    add_task: async () => ({}), complete_task: async () => ({}), delete_task: async () => ({}), delete_event: async () => ({}),
    forget: async () => ({}), delete_document: async () => {}, clear_history: async () => {},
    import_profile_text: async () => ({ ok: false, error: "mock" }), import_profile_file: async () => ({ ok: false }), learn: async () => ({}),
  } };
}
