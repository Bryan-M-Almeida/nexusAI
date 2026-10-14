# Changelog — N.E.X.U.S

O NEXUS é desenvolvido em **releases funcionais**: cada versão é testada e funciona sozinha.
Durante o hackathon, todas as versões são **protótipos** (`0.x`). O esquema de versões muda quando
começarmos a versão definitiva.

Erros conhecidos e soluções: [erros.txt](erros.txt) · [errors.txt](errors.txt) · [errores.txt](errores.txt)

---

## v0.7.0 — Protótipo · 2026-10-14

**Correções de usabilidade, modos da IA e conversa temporária.**

### Corrigido
- **Configurações demoravam para abrir / precisavam de vários cliques** (NX-UI-006): a tela só aparecia depois de
  consultar o Python — e o Ollama, que pode estar carregando o modelo na abertura. Agora abre na hora com as
  configurações já conhecidas; status da IA, modelos e vozes chegam em seguida.
- **Aba Saber sem rolagem** (NX-UI-007): as 21 categorias ocupavam 672 px num painel que cortava o excesso, deixando
  a lista de documentos com 0 px. Agora a aba inteira rola e as categorias são etiquetas compactas (152 px).

### Novo
- **Modos da IA** (borda esquerda): *Assistente* e *Direto*. Medido com `tests/bench_modes.py`: no Direto, respostas
  66% mais curtas (47 × 137 palavras) e 43% mais rápidas (7,7 s × 13,4 s). A instrução do modo vai no contexto da
  mensagem, não no prompt fixo, para trocar de modo sem perder o cache.
- **Conversa temporária** (borda direita): só em RAM, nunca salva, sem memória automática, descartada ao desligar.
- Laterais reveladas ao aproximar o mouse das bordas, como as barras superior e inferior; todas aparecem por 3,5 s ao abrir.

### Testes desta versão
- 59/59 testes unitários; 21/21 verificações de conversa com qwen3:8b (inclui conversa temporária e modo Direto).

---

## v0.6.0 — Protótipo · 2026-10-14

**Respostas ~3× mais rápidas, IA carregada na abertura e integrações online.**

### Desempenho
Medido com `tests/bench_latency.py` na RX 6600 XT (modelo descarregado no início, como ao abrir o app):

| | v0.5 | v0.6 |
|---|---|---|
| 1ª mensagem até a 1ª palavra | 30,2 s | **1,3 s** |
| Média até a 1ª palavra (6 mensagens típicas) | 14,9 s | **4,5 s** |
| Média total | 17,8 s | **5,3 s** |

- **IA carregada durante a animação de abertura** (`assistant.warm_up`): carrega o modelo e processa a parte fixa do
  prompt (regras, perfil, ferramentas). Chip IA âmbar enquanto carrega, azul quando pronta.
- **`localhost` → `127.0.0.1`** (NX-ENV-008): no Windows, `localhost` tentava IPv6 primeiro e cada chamada ao Ollama
  esperava ~2 s (medido 2,08 s × 0,008 s). Corrigido também para quem já tinha `localhost` salvo.
- **Contexto enxuto**: calendário/agenda/tarefas só quando a mensagem fala de tempo ou compromissos; memórias só as
  relevantes; trechos da base menores e só se quase tão relevantes quanto o primeiro (média 371 → ~210 tokens).
- **Fala em streaming**: no modo áudio, a primeira frase é falada assim que é gerada (~30% da resposta).
- Modelo mantido na memória da placa enquanto o app está aberto e liberado ao fechar a janela.
- A extração automática de memória não roda se a IA já salvou a memória naquela mensagem.

### Integrações (sem cadastro nem chave de API)
- **Clima** (Open-Meteo), **notícias** (Google Notícias RSS), **câmbio** (Frankfurter/BCE), **Wikipédia** e
  **calendário** via link ICS (Google Agenda/Outlook; somente leitura, sincroniza a cada 30 min, com lembretes).
- Configurações: liga/desliga, *Sua cidade* e *Link do calendário*.
- **Dados ao vivo nunca inventados** (NX-LLM-023): nos testes, sem a regra, o modelo inventou manchetes e disse que a
  previsão do tempo "não estava disponível". Agora, perguntas de clima/notícias/câmbio exigem a ferramenta.
- E-mail ficou para depois: exige login na conta do usuário.

### Testes desta versão
- 53/53 testes unitários (inclui importação de calendário ICS); 18/18 verificações de conversa com qwen3:8b
  (inclui clima, câmbio e notícias reais).

---

## v0.5.0 — Protótipo · 2026-10-14

**Modo emergência e memória automática confiável.** Motivada por uma conversa real sobre RCP (NX-LLM-021, NX-LLM-016).

### Corrigido
- **Primeiros socorros perigosos** (NX-LLM-021): a IA mandou posicionar as mãos "sobre o processo xifoide" e fazer RCP
  "por 10 a 15 minutos" — ambos errados. A busca por palavras não achava o manual ("preciso fazer RCP" trazia o capítulo
  de Existencialismo) e o modelo improvisava.
  - **Modo emergência** (`nexus/emergency.py`): RCP/parada, engasgo, sangramento, queimadura, fratura, convulsão, AVC,
    infarto, desmaio, intoxicação, hipoglicemia/choque elétrico e "preciso socorrer alguém", em PT/EN/ES.
  - A primeira mensagem é respondida **na hora (0 s) e literalmente pelo manual**, com o número de emergência
    (SAMU 192 / Bombeiros 193 · 911 · 112) — sem passar pela IA.
  - Perguntas seguintes sobre o mesmo tema vão para a IA **com o trecho do manual sempre no contexto** e a regra de não
    acrescentar posições, tempos ou doses que não estejam nele.
- **Memória automática salvando perguntas como "fatos"** (NX-LLM-016): 6 memórias falsas sobre RCP ("O usuário precisa
  fazer RCP"...) a partir de perguntas.
  - A extração só roda quando o usuário afirma algo sobre si (eu/meu/sou/tenho/prefiro…), nunca em perguntas ou emergências.
  - Ela lê só a mensagem do usuário (não a resposta do NEXUS, que virava "interesse").
  - Duplicatas com outras palavras não são salvas de novo (negação conta como correção); no máximo 3 fatos por mensagem.
  - As 6 memórias erradas foram apagadas do banco do usuário (backup em `data_backup_20261014-1306_antes_limpar_memorias/`).

### Testes desta versão
- 47/47 testes unitários; 14/14 verificações de conversa com qwen3:8b (inclui a conversa de RCP: resposta em 0 s com o
  protocolo correto e "não pare" na pergunta de duração).

---

## v0.4.1 — Protótipo · 2026-10-13

**Pronúncia do nome como em inglês/espanhol ("NÉK-sus").**
- Grafia falada escolhida por medição acústica: cada candidata foi comparada (espectro log-mel alinhado por DTW)
  com a voz inglesa dizendo "Nexus". Mais próximas: **"Nécsus"** para a voz masculina (Daniel) e **"Néc-sus"** para a
  feminina (Maria). As mais distantes eram "Néxus" (usada na v0.4.0) e "Néquissus".
- A grafia agora depende da voz usada (NX-VOZ-016).

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

### v0.8.0 — Protótipo (próxima) · prioridade média: identidade visual
- Redesenho completo: visual mais limpo, cores harmônicas, inspirado no HUD do Homem de Ferro com toques originais.
- Ícones originais por tipo de conhecimento (saúde, programação, finanças...).
- Base visual das laterais (modos à esquerda, projetos à direita).

### v0.9.0 — Protótipo · prioridade média: recursos novos
- **Projetos** na lateral direita: a IA consulta e atualiza o projeto ativo com o usuário.
- **Sistema de habilidades estilo Solo Leveling**: nível do NEXUS e de cada habilidade, subindo com o uso; minimalista.

### Versão final do protótipo
- **Instalador** (Inno Setup) e início automático com o Windows — reservado pelo usuário para a versão final do protótipo.

### Versões seguintes (a definir com o usuário)
Candidatos já levantados: formulário real na landing (NX-INT-001), seleção de microfone (NX-VOZ-002),
fontes offline (NX-UI-001), e-mail e calendário com login (OAuth), cancelamento de eco, busca semântica com
embeddings, casa inteligente.
