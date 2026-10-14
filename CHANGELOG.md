# Changelog — N.E.X.U.S

O NEXUS é desenvolvido em **releases funcionais**: cada versão é testada e funciona sozinha.
Durante o hackathon, todas as versões são **protótipos** (`0.x`). O esquema de versões muda quando
começarmos a versão definitiva.

Erros conhecidos e soluções: [erros.txt](erros.txt) · [errors.txt](errors.txt) · [errores.txt](errores.txt)

---

## v0.4.0 — Protótipo · 2026-10-13

**Correções da primeira conversa real.** Análise completa nos catálogos de erros (NX-LLM-019, NX-LLM-020, NX-VOZ-015,
NX-VOZ-016, NX-ENV-007).

### Corrigido
- **Pergunta ambígua respondida com assunto antigo** (NX-LLM-019): "fale os valores exatos", logo após falar do peso
  do coração, foi respondida com gastos de uma conversa de 1 hora antes.
  - O histórico enviado à IA agora é só o da **sessão atual** (desde que o app abriu; 2 h de silêncio também encerram a sessão).
  - O log de ações vai para o contexto só se for da sessão e dos **últimos 15 minutos**.
  - Regra: perguntas curtas ("e de uma mulher?", "por quê?") referem-se à última resposta.
  - A busca na base usa também a pergunta anterior quando a mensagem é curta.
- **Valores imprecisos/contraditórios** (NX-LLM-020): peso do coração da mulher igual ao do homem e depois outro valor.
  - Novo livro **Anatomia** (PT/EN/ES): pesos de órgãos, sinais vitais, sangue, ossos, valores de referência.
  - Regra: dar média e faixa, dizer quando não existe valor exato e corrigir explicitamente o que disse antes.
- **"Aprenda que..." ecoado sem salvar**: a rede de segurança agora também olha o pedido do usuário ("aprenda que",
  "lembra que", "me lembra de", "registra") e exige a ferramenta correspondente.
- **Voz de "aparelho de fumante"** (NX-VOZ-015): o efeito J.A.R.V.I.S tinha modulação em anel (zumbido 16–24× acima do
  natural). Novo efeito: realce de presença nas consoantes, brilho sutil e ambiente curto; fidelidade 0,88 → 0,97.
- **Pronúncia "NÊXUS"** (NX-VOZ-016): a voz agora fala "NÉCSUS" (NÉ-QUI-SÚS) em português e espanhol (a tela continua N.E.X.U.S).
- **Dados de teste gravados na pasta real** (NX-ENV-007): os testes agora ficam em `tests/` e sempre usam uma pasta
  temporária; a pasta `data/` foi zerada (backup em `data_backup_20261013-2101/`).

### Novo
- Velocidade da voz até **+10** (Configurações → Velocidade).
- `tests/test_units.py` (sem IA, segundos) e `tests/conversation_eval.py` (IA real: reproduz a conversa do erro e a
  bateria de ferramentas).

### Testes desta versão
- 25/25 testes unitários; 10/10 verificações de conversa com qwen3:8b.

---

## v0.3.0 — Protótipo · 2026-10-13

**Interface minimalista e controle da conversa.**

### Novo
- **Tela limpa: só o aro NEXUS.** O aro **expande** com a voz da IA (envelope do áudio sincronizado com a
  reprodução) e **contrai** com a voz do usuário (nível do microfone ~16×/s). Respira levemente em repouso.
- **Barra superior** (mouse no topo): versão, status, relógio, idioma, **Painel** e Configurações.
- **Dock de ícones** (mouse embaixo): apenas mensagens · apenas áudio · mutar/desmutar microfone ·
  mutar/desmutar IA · interromper · repetir. As duas barras aparecem por 3,5 s ao iniciar, para o usuário descobri-las.
- **Painel** em gaveta: perfil, agenda, tarefas, memória, conhecimento, dados e log (antes ocupavam a tela).
- **Modo apenas áudio**: conversa contínua por voz, sem palavra de ativação (opcional em Configurações:
  "Só responder quando eu disser Nexus"). **Modo apenas mensagens**: chat, IA sem voz.
- **Controle por voz/texto** (`nexus/control.py`), em PT/EN/ES, instantâneo e **funcionando enquanto o NEXUS fala**:
  pausar, continuar, parar, repetir, "não entendi" (reexplica mais claro).
- **Repetir** (botão): "Acho que não entendeu, vou repetir." + a mesma resposta; "não entendi" depois disso
  gera uma explicação mais clara.
- **Interromper** cancela também a resposta que a IA ainda está gerando.
- Pausa retoma do início da frase interrompida.
- Ferramenta `conversation_control` para modelos que decidirem usá-la.

### Mudou
- O download do modelo de voz só acontece quando o usuário ativa o microfone (nunca sozinho no boot).
- `Ctrl+Espaço` (push-to-talk) funciona nos dois modos; `Esc` interrompe.

### Conhecido
- NX-LLM-018: o qwen3:8b resolve pedidos longos ("pode repetir?", "explica mais simples") conversando,
  sem chamar `conversation_control`; o resultado nos testes foi correto.
- NX-VOZ-012: com caixas de som, o NEXUS pode se ouvir; comandos durante a fala são mais confiáveis com fone.
- NX-VOZ-013: durante a fala, só comandos de controle são aceitos; outras frases são ignoradas (proteção contra eco).

---

## v0.2.0 — Protótipo · 2026-10-13

**Saudação e voz.**

### Novo
- **Saudação inteligente** (sem IA, instantânea):
  - sem perfil: "Olá, eu sou NEXUS, seu assistente virtual…" e pede o perfil;
  - primeira vez com perfil: apresentação completa com o nome do usuário;
  - usuário conhecido: "Olá {nome}, o que teremos para hoje?";
  - se o usuário pediu: "Olá {nome}, vamos continuar {assunto}?" (dito uma vez).
- Ferramenta `remind_next_session`: "na próxima vez que eu abrir, me lembra de…".
- **Motor de voz próprio** (`nexus/tts.py`), substituindo o pyttsx3:
  - escolha de **voz masculina ou feminina**, com as vozes OneCore do Windows (ex.: Microsoft Daniel, pt-BR masculina);
  - **efeitos** `J.A.R.V.I.S` (sutil, metálico) e `Robô` (forte), ou `Natural`;
  - a voz segue o idioma do texto (pt/en/es);
  - controle de velocidade e botão **Testar voz** nas Configurações, com a lista de vozes instaladas e aviso quando falta um gênero no idioma.
- A saudação entra no histórico, então responder "sim" à pergunta funciona.
- `NEXUS.exe --selftest`: verificação da release sem janela (voz, IA, base, microfone), salva em `selftest.json`.

### Corrigido
- NX-VOZ-007: a fala parava de funcionar (pyttsx3 removido).
- NX-VOZ-009: "silenciar"/Esc agora corta o áudio na hora.
- Rede de segurança contra ações fingidas reconhece também a 3ª pessoa ("aprendeu", "ficou salvo").

### Conhecido
- NX-VOZ-010: sem voz masculina instalada em inglês, a voz fica andrógina (fallback com tom rebaixado).
- NX-VOZ-006: ainda não há voz em espanhol no PC de referência.

---

## v0.1.0 — Protótipo · 2026-10-13

**App base.**

- App desktop em Python (pywebview) com a animação de boot da landing (anéis + N.E.X.U.S).
- IA local via Ollama (API nativa, contexto 8192, `qwen3:8b`) ou LM Studio; GPU AMD via Vulkan.
- 21 ferramentas: tarefas, agenda, lembretes, notas, coleções de dados, memória e conhecimento.
- Memória persistente (perfil, fatos, histórico, log de ações) em SQLite.
- Voz offline: Whisper (push-to-talk e palavra "Nexus") e fala SAPI.
- Base de conhecimento FTS5 com 6 livros em PT/EN/ES e importação de .md/.txt/.pdf.
- Perfil JSON da landing: arquivo, colar ou POST em `127.0.0.1:47800/profile`.
- Interface e respostas em português, inglês e espanhol.
- Catálogo de erros nos 3 idiomas; scripts de setup e build (PyInstaller).

---

## Próximas versões (planejamento)

### v0.5.0 — Protótipo (próxima)
A definir com o usuário.

### Versões seguintes (a definir com o usuário)
Candidatos já levantados: formulário real na landing (NX-INT-001), seleção de microfone (NX-VOZ-002),
fontes offline (NX-UI-001), aquecimento do modelo no boot (NX-LLM-011), integrações de rede (clima,
calendário, notícias, e-mail), busca semântica com embeddings, instalador e início automático com o
Windows, casa inteligente.
