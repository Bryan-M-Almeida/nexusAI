# N.E.X.U.S

**Networked Experiential Intelligence & User System** — um assistente pessoal inspirado no J.A.R.V.I.S que roda **100% local** no seu computador: lembra de você, gerencia sua agenda, tarefas e dados, responde por voz e aprende coisas novas.

Landing page: https://nexus-landing-dun.vercel.app

## O que ele faz

| Recurso | Como |
|---|---|
| Programa desktop | Janela nativa (pywebview / WebView2), com a mesma animação de boot da landing: anéis girando + N.E.X.U.S |
| IA local | Qualquer servidor compatível com OpenAI: **Ollama** (padrão) ou LM Studio. Funciona com GPU AMD |
| Memória persistente | Perfil, fatos sobre o usuário (salvos pela IA ou extraídos automaticamente), histórico de conversa e log de todas as ações |
| Ações em tempo real | A IA chama ferramentas: tarefas, agenda/cronograma, lembretes, notas e **coleções de dados livres** (gastos, treinos, leituras…) |
| Lembretes proativos | Agendador verifica eventos e prazos a cada 15 s e avisa na tela e por voz |
| Voz | Reconhecimento offline com Whisper (botão ou `Ctrl+Espaço`, ou escuta contínua com a palavra "Nexus") e fala offline com as vozes do Windows |
| Base de conhecimento | Livros iniciais em PT/EN/ES: primeiros socorros, filosofia, finanças, programação, saúde e produtividade. Busca local SQLite FTS5 |
| Aprende coisas novas | Pelo chat ("aprenda que…"), pelo botão Ensinar, importando .md/.txt/.pdf, ou soltando arquivos na pasta `inbox` |
| Idiomas | Português, English e Español (interface, respostas, voz e conhecimento) |

## Requisitos

Medidos no PC de referência com `tests/bench_hardware.py` (Ryzen 5 5600G, 16 GB, RX 6600 XT 8 GB, qwen3:8b).

| | Mínimo | Recomendado | Força total |
|---|---|---|---|
| Sistema | Windows 10/11 64 bits | Windows 11 64 bits | Windows 11 64 bits |
| Processador | 8 threads (ex.: Ryzen 5 / Core i5 recentes) | 8+ threads | 8+ threads |
| RAM | 16 GB | 16 GB | 16 GB ou mais |
| Placa de vídeo | nenhuma (só processador) | 8 GB (AMD RX 6600 XT, NVIDIA RTX 3060 8 GB ou melhor) | 8 GB+ (12 GB+ para contextos maiores) |
| Disco livre | ~10 GB | ~12 GB em SSD | ~13 GB em SSD |
| Velocidade da IA | ~7,5 tokens/s (respostas de 15–60 s) | ~35–40 tok/s (respostas de 2–10 s) | igual, com mais contexto quando a placa permite |

Espaço em disco: modelo qwen3:8b 5,2 GB, Ollama ~2,8 GB, NEXUS ~0,3 GB, voz Whisper small ~0,5 GB (medium ~1,5 GB).
Também é preciso o WebView2 (já vem no Windows 11). O NEXUS mostra em *Configurações → Desempenho* se o seu PC atende.

## Instalação (desenvolvimento)

Requisitos: Windows 10/11, Python 3.12+ e microfone.

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

### IA local (Ollama) com GPU AMD

1. Instale o Ollama: `winget install Ollama.Ollama` (ou https://ollama.com/download)
2. Baixe o modelo (cabe em 8 GB de VRAM):
   ```powershell
   ollama pull qwen3:8b
   ```
3. **Placas AMD**: as versões atuais do Ollama (testado na 0.40.3) já usam o backend **Vulkan** automaticamente quando o ROCm não está disponível. Na RX 6600 XT ele foi detectado sem nenhuma configuração. Confira com `ollama ps`: a coluna PROCESSOR deve mostrar `100% GPU`. Atualizar o driver AMD Adrenalin tende a melhorar o desempenho.
4. Alternativa: **LM Studio** (usa Vulkan em AMD). Ative o servidor local e, nas configurações do NEXUS, use `http://localhost:1234/v1`, com Context Length de 8192 ou mais.

Modelo padrão: `qwen3:8b`. Nos testes, foi o único que chamou todas as ferramentas corretamente; o `qwen2.5:7b` fingia registrar gastos, memórias e aprendizados. Para PCs mais fracos: `qwen3:4b` (menos preciso).

**Tempo de resposta (v0.6, RX 6600 XT):** 1ª mensagem ~1 s (a IA é carregada durante a animação de abertura), mensagens simples 1–4 s, com consulta online (clima, notícias) 11–14 s. No modo áudio a fala começa já na primeira frase. O limite é o processamento de prompt da placa via Vulkan (~60–150 tokens/s); atualizar o driver AMD Adrenalin é a melhoria mais provável. Benchmark: `tests\bench_latency.py --warm`.

Problemas e soluções: veja [erros.txt](erros.txt) (English: [errors.txt](errors.txt) · Español: [errores.txt](errores.txt)).

### Rodar

```powershell
.\.venv\Scripts\python run_nexus.py
```

Variáveis úteis: `NEXUS_DEBUG=1` (abre o DevTools), `NEXUS_HOME=<pasta>` (outra pasta de dados).

## Perfil do usuário (JSON da landing page)

O formulário de onboarding da landing gera um JSON. O NEXUS aceita chaves em inglês ou português:

```json
{
  "name": "Alex Martins",
  "profession": "Full-Stack Developer",
  "routine": "Starts at 9 AM · deep focus in the afternoon",
  "interests": ["AI", "games", "coffee"],
  "goals": ["Ship the NEXUS prototype"],
  "profile": "developer",
  "language": "pt-BR"
}
```

- Obrigatório: `name` (ou `nome`). `interests`/`goals` podem ser listas ou texto separado por vírgulas.
- `profile`: `developer`, `healthcare`, `student`, `designer`, `entrepreneur` (se omitido, é deduzido da profissão). Define tom de voz e módulos, como na seção PROFILES da landing.
- `language`: `pt-BR`, `en` ou `es` (use o `?lang=` da landing).
- Qualquer campo extra do formulário é guardado e usado pela IA.

Três formas de importar:
1. **Direto da landing**: com o NEXUS aberto, o formulário pode enviar para `http://127.0.0.1:47800/profile`:
   ```js
   fetch("http://127.0.0.1:47800/profile", {
     method: "POST",
     headers: { "Content-Type": "application/json" },
     body: JSON.stringify(formData),
   }).catch(() => baixarJson(formData)); // se o app não estiver aberto, oferece o download do .json
   ```
   O Chrome pode pedir permissão para um site acessar a rede local; o fallback de download cobre esse caso.
2. Botão **Escolher arquivo JSON** na tela de boas-vindas.
3. Colar o JSON na tela de boas-vindas.

Exemplo pronto em [examples/profile.example.json](examples/profile.example.json).

## Comandos de voz e exemplos

- "Nexus, me lembra de ligar para o dentista amanhã às 10"
- "Agenda reunião com o time sexta às 15h"
- "Registra que gastei 42 reais no mercado" → depois: "quanto gastei esse mês?"
- "Lembra que eu sou alérgico a dipirona"
- "Como faço massagem cardíaca?" (responde pela base de primeiros socorros)
- "Aprenda que a academia abre às 6h e fecha às 22h" / "What do the Stoics say about anxiety?"
- "Inicia um pomodoro"
- "Na próxima vez que eu abrir, me lembra de continuar o projeto do app" → no próximo início: *"Olá, Alex, vamos continuar o projeto do app?"*

Atalhos: `Ctrl+Espaço` fala (push-to-talk, nos dois modos), `Esc` interrompe a fala e a resposta em andamento (ou fecha janelas abertas), `F11` sai/entra da tela cheia, `Ctrl+,` Configurações, `Ctrl+Shift+N` nova conversa, `Ctrl+H` conversas, `Ctrl+J` notificações, `Ctrl+T` transcrição.

### Habilidades (v0.13)

O selo ao lado do nome na barra superior mostra o **rank (E → S) e o nível** do NEXUS; clique para ver cada área (Organização, Finanças, Programação, Estudo, Saúde, Conhecimento, Pesquisa, Voz). Elas sobem com o uso — cada assunto, cada ação feita e cada fala por voz — sem nenhuma chamada extra à IA.

### Backup e segurança (v0.13)

- **Backup automático** todo dia (os 7 últimos ficam em `backups/`); *Configurações → Dados* tem **Fazer backup agora** e **Restaurar** (aplicado ao reabrir; os dados atuais ficam guardados).
- A **chave de API** é guardada criptografada pelo Windows (só o seu usuário consegue ler).
- Só um NEXUS abre por vez. Erros ficam em `logs/nexus.log`.

### Conexão e desempenho (v0.12)

*Configurações → Desempenho*:
- **Offline**: nada sai do computador (sem clima, notícias, câmbio, Wikipédia, calendário, IA na nuvem nem fontes do Google). **Híbrido** (padrão): IA local + serviços online. **Online**: permite IA na nuvem.
- Perfis **Econômico**, **Equilibrado** (padrão) e **Força total** (só se a IA inteira couber na placa de vídeo com 16 GB de RAM). A seção mostra o seu hardware e se ele atende aos requisitos.

### Área de trabalho (v0.11)

*Borda direita → Área de trabalho*: crie um espaço por projeto (nome + descrição). Cada um tem **pasta, conversa e anotações próprias**, separadas das conversas normais e dos seus dados pessoais.

- A IA tem **liberdade total dentro da pasta**: lista, lê, cria, edita e apaga arquivos sozinha; nada fora dela.
- Toda alteração pode ser **desfeita** pelo painel da esquerda (*Alterações*); clique em um arquivo para ver o conteúdo.
- **Comandos** (rodar código, instalar pacotes) pedem a sua **confirmação** a cada vez.
- *Abrir pasta* abre a pasta no Explorer; *Sair* volta para a conversa normal.

Exemplo: *"Crie um calc.py com soma e média e um teste"* → *"Rode os testes"* (você confirma) → *"Faça a média aceitar lista vazia"*.

**Modo foco** (borda esquerda): sem distrações, lembretes só no sino; liga sozinho na área de trabalho. **Modo Estudo**: a IA explica passo a passo e confere se você entendeu.

### Notificações e lembretes (v0.10)

Com o NEXUS aberto (pode estar minimizado), compromissos e tarefas com prazo são avisados com as antecedências escolhidas em *Configurações → Notificações* (padrão: 1 h, 10 min e na hora): pelo **sino** da barra superior, por **notificação do Windows**, **som** e **voz** (também no modo texto). Há **horário silencioso** (só o sino) e um **resumo do dia** opcional, falado no horário escolhido.

### Configurações (v0.10)

Oito seções: Geral, **Inteligência** (provedor, chave de API, modelo, criatividade, contexto, testar conexão), Voz do NEXUS (voz, efeito, velocidade, volume), **Microfone** (dispositivo, modelo do Whisper, sensibilidade, pausa), Notificações, Integrações, Interface (HUD, legendas, animações) e Dados.

**Provedores de IA:** Ollama e LM Studio rodam no seu computador. OpenAI, Anthropic (Claude), Google Gemini, OpenRouter, Groq, DeepSeek, Mistral ou qualquer servidor compatível com a API da OpenAI também funcionam com uma chave de API; nesse caso as mensagens e o contexto saem do computador. Use modelos com suporte a ferramentas (*tool calling*), senão o NEXUS não consegue salvar lembretes e dados.

### Interface minimalista (v0.3)

A tela mostra só o **aro NEXUS**: ele se **expande** enquanto a IA fala (seguindo o volume da voz) e se **contrai** enquanto você fala.

- **Mouse no topo** → barra superior: versão, status da IA/voz, relógio, idioma, **Painel** (agenda, tarefas, memória, conhecimento, dados, log) e Configurações.
- **Mouse na borda esquerda** → modos da IA; **mouse na borda direita** → nova conversa, **Conversas** e conversa temporária (projetos chegam na v0.10).
- **Mouse embaixo** → ícones: **apenas mensagens** · **apenas áudio** · **transcrição** · **mutar/desmutar microfone** · **mutar/desmutar IA** · **interromper** · **repetir** (interromper/repetir ficam esmaecidos quando não há o que fazer).
- **Transcrição** (v0.8): mostra a conversa à direita sem sair do modo áudio. Todo texto é selecionável e cada mensagem tem **Copiar**.
- **Aro**: passe o mouse para ver **N.E.X.U.S · NEX-1.0** (o modelo atual). No modo áudio, **arraste** para mover e dê **duplo clique** para centralizar.
- **HUD** (v0.9): em volta do aro ficam modelo e modo, hora e data, microfone e voz; a linha de **pulso** sob o aro oscila com a sua voz (vermelha) e a do NEXUS (azul).
- **Conversas** (v0.9): cada conversa recebe título e descrição escritos pela IA. *Separadas* lista os cartões (clique para continuar, ✎ renomeia, ✕ apaga); *Todas* mostra tudo em ordem cronológica. Só a conversa aberta vai para a IA.
- Abre em **tela cheia**; minimizar / tela cheia / fechar ficam na barra superior. Clicar fora fecha Configurações e Painel.
- **Apenas áudio**: conversa contínua por voz, sem precisar dizer "Nexus" (dá para exigir a palavra em Configurações).
- **Apenas mensagens**: o aro sobe, aparece o chat e a IA não fala.
- **Repetir** (botão): "Acho que não entendeu, vou repetir." + a mesma resposta. Se você disser que **não entendeu**, ela explica de novo de forma mais clara.

### Controle da conversa por voz

| Você diz (PT / EN / ES) | O NEXUS |
|---|---|
| "pausa", "espera aí…", "segura aí que…", "hold on…", "espera un momento…" | pausa a fala (retoma do início da frase) |
| "continua", "pode continuar", "go on", "sigue" | continua de onde parou |
| "para", "chega", "para de falar", "stop", "basta" | para de falar e cancela a resposta |
| "repete", "o que você disse?", "say that again", "repite" | "Claro, vou repetir." + a mesma resposta |
| "não entendi", "não entendi a piada", "explica melhor", "I didn't understand", "no entendí" | "Tudo bem, vou explicar de outro jeito." e explica o significado (numa piada, o trocadilho) |

Esses comandos são reconhecidos **localmente** (instantâneo) e funcionam **mesmo enquanto o NEXUS fala**. Para frases mais elaboradas ("hã? fala de novo com outras palavras"), a IA decide pela conversa. Com caixas de som, use fone de ouvido para o NEXUS não se ouvir.

### Modos da IA e conversa temporária (v0.7)

- **Mouse na borda esquerda → Modo da IA**: *Assistente* (completo e cordial) ou *Direto* (o mínimo de palavras, exatamente o que foi pedido). Medido: respostas 66% mais curtas e 43% mais rápidas no modo Direto. Ao trocar, o NEXUS diz "Executando em modo …".
- **Mouse na borda direita → Conversa temporária**: conversa à toa que fica só na memória RAM, não é salva no histórico e não gera memórias automáticas. Ao desligar, é descartada. Selo âmbar no topo enquanto ativa. Pedidos explícitos ("me lembra de…", "aprenda que…") continuam funcionando.

### Integrações online (v0.6)

Sem cadastro nem chave de API. Ative/desative em *Configurações → Integrações*.

| Pergunte | Serviço |
|---|---|
| "Vai chover amanhã?", "How's the weather in Lisbon?" | Clima — Open-Meteo (defina *Sua cidade*) |
| "Quais as notícias de tecnologia?" | Notícias — Google Notícias (RSS) |
| "Quanto dá 100 dólares em reais?" | Câmbio — Frankfurter (taxas de referência do Banco Central Europeu) |
| "Quem foi Ada Lovelace?" | Wikipédia |
| "Atualiza minha agenda" | Calendário — link ICS do Google Agenda/Outlook (somente leitura, sincroniza a cada 30 min) |

O texto da pergunta (cidade, tema, termo de busca) é enviado a esses serviços. Dados ao vivo nunca são inventados: se a IA tentar responder sem consultar, o NEXUS exige a consulta.

### Modo emergência (v0.5)

Se você descrever uma emergência — "preciso fazer RCP", "ele não está respirando", "meu filho está engasgado",
"my dad is having a heart attack", "se está atragantando"… — o NEXUS responde **na hora, sem passar pela IA**, com
o número de emergência (SAMU 192 / Bombeiros 193 · 911 · 112) e o **protocolo literal do Manual de Primeiros Socorros**.
Perguntas seguintes sobre o mesmo tema vão para a IA, mas sempre com o trecho do manual e a regra de não inventar nada
fora dele. Isso não substitui o atendimento profissional: siga sempre as instruções da central de emergência.

### Saudação

| Situação | O NEXUS diz |
|---|---|
| Ainda sem perfil | "Olá, eu sou NEXUS, seu assistente virtual…" e pede o perfil |
| Primeira vez com perfil | Apresentação completa, usando o nome do usuário |
| Usuário já conhecido | "Olá {nome}, o que teremos para hoje?" |
| Usuário pediu para ser lembrado no próximo início | "Olá {nome}, vamos continuar {assunto}?" (só uma vez) |

### Voz do NEXUS

Em *Configurações*: **voz masculina ou feminina**, **efeito** (`J.A.R.V.I.S` limpo com brilho digital, `Robô` forte ou `Natural`), **velocidade** (de −5 a +10) e o botão **Testar voz**. O nome é falado como em inglês/espanhol: "NÉK-sus".

- Usa as vozes SAPI do Windows, inclusive as "OneCore" (ex.: **Microsoft Daniel**, masculina em pt-BR). Vozes encontradas no PC de teste: Maria (pt, fem.), Daniel (pt, masc.), Zira (en, fem.).
- Se o gênero escolhido não existir no idioma, o NEXUS usa a outra voz com o tom ajustado e avisa na tela. Instale mais vozes (ex.: David/Mark em inglês, qualquer voz em **espanhol**) em *Configurações do Windows → Hora e idioma → Fala → Adicionar vozes*.
- No primeiro uso do microfone, o modelo Whisper escolhido é baixado (tiny ≈ 75 MB, base ≈ 145 MB, small ≈ 480 MB).
- **Ouvir** (v0.8): o fim da fala é detectado pelo **Silero VAD** (rede neural; ruído de ventilador não segura mais a gravação) e o Whisper transcreve no idioma escolhido, com "NEXUS" e o seu nome no vocabulário. Se você fala outro idioma com o NEXUS, escolha-o em *Configurações → Idioma*.

### Relatar um erro

Diga **"salve essa conversa para relatar erros"** (ou use o botão em *Configurações*). A conversa, as ações recentes e as configurações vão para `reports/nexus-report-<data>.md` na pasta de dados; envie esse arquivo à equipe.

## Onde ficam os dados

- Desenvolvimento: `./data/`. Executável instalado: `%LOCALAPPDATA%\NEXUS\`.
- `nexus.db` (SQLite com tudo), `settings.json` e `inbox/`. Arquivos .md/.txt/.pdf colocados em `inbox/` são aprendidos no próximo boot.

## Testes

Os testes **sempre** usam uma pasta de dados temporária, então nunca tocam nos seus dados.

```powershell
.\.venv\Scripts\python tests\test_units.py          # segundos, sem IA
.\.venv\Scripts\python tests\conversation_eval.py   # alguns minutos, precisa do Ollama e de internet
.\.venv\Scripts\python tests\workspace_eval.py      # área de trabalho com a IA real (arquivos e comandos)
.\.venv\Scripts\python tests\bench_latency.py --warm # tempos de resposta
.\.venv\Scripts\python tests\bench_voice.py         # fim de fala e precisão do reconhecimento
.\.venv\Scripts\python tests\bench_hardware.py      # IA por tamanho de contexto (placa x processador) e voz
```

## Gerar o executável

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Gera `dist\NEXUS\NEXUS.exe`. Basta copiar a pasta `dist\NEXUS` para outro PC (o Ollama é instalado separadamente).

Para validar uma release (voz, IA, base de conhecimento, microfone) sem abrir a janela:

```powershell
dist\NEXUS\NEXUS.exe --selftest
```

O relatório é gravado em `selftest.json` na pasta de dados.

## Estrutura

```
nexus/
  app.py        janela desktop + API chamada pela interface
  assistant.py  cérebro: contexto, laço de ferramentas, memória automática, saudação
  llm.py        cliente OpenAI-compatível (Ollama / LM Studio) com streaming
  tools.py      ações: tarefas, agenda, lembretes, notas, dados, memória, conhecimento
  memory.py     fatos sobre o usuário, histórico e log de ações
  knowledge.py  base de conhecimento (SQLite FTS5) e importação de arquivos
  voice.py      Whisper (ouvir, conversa contínua), fila de fala com pausa/retomada/repetição
  control.py    comandos de conversa por voz/texto (repetir, explicar melhor, pausar, continuar, parar)
  emergency.py  modo emergência: protocolo de primeiros socorros instantâneo e literal do manual
  integrations.py clima, notícias, câmbio, Wikipédia e calendário ICS (sem chaves de API)
  tts.py        motor de voz: vozes SAPI/OneCore, gênero, efeitos J.A.R.V.I.S/robô
  scheduler.py  lembretes com antecedências, resumo do dia, sincronização do calendário
  notify.py     central de notificações, notificação do Windows, horário silencioso
  workspace.py  área de trabalho: pasta isolada, ferramentas de arquivo, desfazer, comandos confirmados
  hardware.py   detecção de processador, RAM e placa de vídeo (memória real) e o que cabe nela
  performance.py perfis Econômico / Equilibrado / Força total e requisitos
  skills.py     níveis e ranks das habilidades (XP do que aconteceu, sem chamadas extras à IA)
  backup.py     backup diário, backup manual e restauração
  logs.py       arquivo de log (logs/nexus.log)
  bridge.py     endpoint local para o formulário da landing
  profile.py    importação e normalização do perfil
  i18n.py       textos em PT/EN/ES
  seed/         livros iniciais (pt/, en/, es/)
  web/          interface (HTML/CSS/JS); abra web/index.html?mock no navegador para editar o visual sem o Python
```

## Versões

O NEXUS é entregue em **releases funcionais**. Durante o hackathon, todas são **protótipos** (`0.x`). Histórico completo e próximas versões em [CHANGELOG.md](CHANGELOG.md).

Versão atual: **v0.13.0 (protótipo)**.
