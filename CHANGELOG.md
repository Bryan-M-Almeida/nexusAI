# Changelog — N.E.X.U.S

O NEXUS é desenvolvido em **releases funcionais**: cada versão é testada e funciona sozinha.
Durante o hackathon, todas as versões são **protótipos** (`0.x`). O esquema de versões muda quando
começarmos a versão definitiva.

Erros conhecidos e soluções: [erros.txt](erros.txt) · [errors.txt](errors.txt) · [errores.txt](errores.txt)

---

## v0.8.0 — Protótipo · 2026-10-14

**Voz que entende e para de ouvir na hora certa, conversa visível no modo áudio e correções da conversa real.**

### Voz (medido com `tests/bench_voice.py`: 20 frases sintetizadas, vozes Maria e Daniel, com ruído de ventilador)
| | v0.7 | v0.8 |
|---|---|---|
| Gravações encerradas com ruído médio/alto | **0/6** (ficava "ouvindo" até 30 s) | **6/6**, logo após o fim da fala |
| Erro de palavras (WER) | 24,5% | **12,1%** |
| "Nexus" reconhecido | 2/6 | **6/6** |
| Tempo de transcrição por frase | 3,2 s | **2,0 s** |

- **Microfone ativo por muito tempo** (NX-VOZ-004): o detector por volume foi trocado pelo **Silero VAD**, uma rede
  neural que separa voz de ruído (~0,2 ms por quadro, já incluída no faster-whisper; sem download novo).
- **Áudio mal reconhecido** (NX-VOZ-017): idioma fixo (Configurações ou perfil) em vez de adivinhar, busca beam 5,
  vocabulário inicial com "NEXUS" e o seu nome, normalização de volume para microfones baixos e descarte de
  trechos que o Whisper marca como "sem fala" (fim das frases fantasmas como "Obrigado.").
- **"Nexus" não ativava** (NX-VOZ-003): reconhece também "Nécsus", "Neksus", "Nexis", "Nek us"...

### Interface
- **Transcrição no modo áudio** (NX-UI-008): botão na barra inferior mostra a conversa à direita sem sair do modo
  áudio; com ela fechada, a resposta aparece como legenda enquanto é gerada.
- **Texto selecionável** e botão **Copiar** em cada mensagem.
- **Clicar fora fecha** Configurações, Painel e Perfil.
- **Sempre em tela cheia**, com minimizar / tela cheia (F11) / fechar na barra superior.
- **Interromper/Repetir desativados** quando não há nada para interromper ou repetir (NX-UI-009).
- Ao trocar o modo da IA, o NEXUS diz **"Executando em modo Direto/Assistente"**.
- Passar o mouse no aro mostra **N.E.X.U.S · NEX-1.0** (nome do modelo exibido ao usuário).
- Gaveta do Painel rola em telas pequenas (colunas com rolagem própria; uma coluna abaixo de 900 px).

### Conversa (da conversa real de 2026-10-14)
- **Simulados/quiz** (NX-LLM-024): cada resposta é corrigida na hora, nada de guardar respostas com `record_data`,
  "correto" só depois de conferir e "vamos começar?" no máximo uma vez.
- **"Não entendi a piada"** (NX-LLM-025): o pedido ao modelo leva as suas palavras e pede o significado (numa piada,
  o trocadilho), em vez de repetir a mesma frase.
- **Relatar erro**: diga "salve essa conversa para relatar erros" ou use o botão nas Configurações; a conversa,
  as ações recentes e as configurações vão para `reports/nexus-report-<data>.md` na pasta de dados. É feito na hora,
  sem passar pelo modelo (na avaliação ele também registrava o pedido como dado e respondia com um id).
- **Simulado de primeiros socorros abria o modo emergência** (NX-LLM-022, achado na avaliação): mensagens de estudo
  (simulado, quiz, prova, perguntas, curso…) não acionam mais o protocolo, a menos que soem urgentes
  ("agora", "socorro", "não respira"…).
- **Trava de segurança da RCP** (NX-LLM-021, achado na avaliação): mesmo com o manual no contexto, o modelo respondeu
  "não deixe por mais de 10 minutos… interrompa". Agora, respostas de acompanhamento em emergência são conferidas
  antes de aparecer/serem faladas; se mandarem parar a RCP ou citarem limite de minutos, são trocadas pela linha
  literal do manual ("Não pare até a vítima reagir, a equipe chegar ou você não aguentar mais").
- Caminhos de arquivo e trechos de código entre crases aparecem na tela, mas não são lidos em voz alta.
- Latência conferida contra a v0.7 com `tests/bench_latency.py` (mesmas 9 mensagens): 7,3 s × 7,2 s até a 1ª
  palavra. Sem regressão.

### Testes desta versão
- 81/81 testes unitários (22 novos: palavra de ativação, VAD com ruído, ganho, vocabulário, relatório, simulado ≠ emergência, trava da RCP).
- Verificações de conversa com qwen3:8b ampliadas com simulado, piada e relatório (resultado nas notas da release).

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
