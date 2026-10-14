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

Modelo padrão: `qwen3:8b`. Nos testes, foi o único que chamou todas as ferramentas corretamente; o `qwen2.5:7b` fingia registrar gastos, memórias e aprendizados. Para PCs mais fracos: `qwen3:4b` (menos preciso). Tempo de resposta medido na RX 6600 XT: 11 a 25 s.

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

Atalhos: `Ctrl+Espaço` fala (push-to-talk, nos dois modos), `Esc` interrompe a fala e a resposta em andamento (ou fecha janelas abertas).

### Interface minimalista (v0.3)

A tela mostra só o **aro NEXUS**: ele se **expande** enquanto a IA fala (seguindo o volume da voz) e se **contrai** enquanto você fala.

- **Mouse no topo** → barra superior: versão, status da IA/voz, relógio, idioma, **Painel** (agenda, tarefas, memória, conhecimento, dados, log) e Configurações.
- **Mouse embaixo** → ícones: **apenas mensagens** · **apenas áudio** · **mutar/desmutar microfone** · **mutar/desmutar IA** · **interromper** · **repetir**.
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
| "não entendi", "explica melhor", "I didn't understand", "no entendí" | "Acho que não entendeu…" e reexplica mais claro |

Esses comandos são reconhecidos **localmente** (instantâneo) e funcionam **mesmo enquanto o NEXUS fala**. Para frases mais elaboradas ("hã? fala de novo com outras palavras"), a IA decide pela conversa. Com caixas de som, use fone de ouvido para o NEXUS não se ouvir.

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

## Onde ficam os dados

- Desenvolvimento: `./data/`. Executável instalado: `%LOCALAPPDATA%\NEXUS\`.
- `nexus.db` (SQLite com tudo), `settings.json` e `inbox/`. Arquivos .md/.txt/.pdf colocados em `inbox/` são aprendidos no próximo boot.

## Testes

Os testes **sempre** usam uma pasta de dados temporária, então nunca tocam nos seus dados.

```powershell
.\.venv\Scripts\python tests\test_units.py          # segundos, sem IA
.\.venv\Scripts\python tests\conversation_eval.py   # alguns minutos, precisa do Ollama
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
  tts.py        motor de voz: vozes SAPI/OneCore, gênero, efeitos J.A.R.V.I.S/robô
  scheduler.py  lembretes em tempo real
  bridge.py     endpoint local para o formulário da landing
  profile.py    importação e normalização do perfil
  i18n.py       textos em PT/EN/ES
  seed/         livros iniciais (pt/, en/, es/)
  web/          interface (HTML/CSS/JS); abra web/index.html?mock no navegador para editar o visual sem o Python
```

## Versões

O NEXUS é entregue em **releases funcionais**. Durante o hackathon, todas são **protótipos** (`0.x`). Histórico completo e próximas versões em [CHANGELOG.md](CHANGELOG.md).

Versão atual: **v0.4.1 (protótipo)**.
