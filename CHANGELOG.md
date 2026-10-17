# Changelog — N.E.X.U.S

O NEXUS é desenvolvido em **releases funcionais**: cada versão é testada e funciona sozinha.
Durante o hackathon, todas as versões são **protótipos** (`0.x`). O esquema de versões muda quando
começarmos a versão definitiva.

Erros conhecidos e soluções: [erros.txt](erros.txt) · [errors.txt](errors.txt) · [errores.txt](errores.txt)

---

## v0.20.0 — Protótipo · 2026-10-16

**Etapa final: tutorial roteirizado e falado sem IA (com voltar, avançar e pular) enquanto o NEXUS se prepara em segundo
plano, aviso de protótipo, abas Sobre, Atualizações e Possíveis erros, funções com erros movidas para o Beta e o
contexto da conversa respeitado nas perguntas de continuação.**

### Novo
- **Tutorial roteirizado, sem IA**: o texto é fixo e falado; cada passo avança quando a fala termina. Botões **Voltar**,
  **Próximo** e **Pular** — pular leva ao último passo, que explica que dá para pedir "Nexus, mostra o tutorial" de novo
  e que a IA ajuda com qualquer dúvida. Esc também pula.
- **IA fechada durante o tutorial**: o que você fala ou escreve só move o tutorial ("próximo", "voltar", "pular", em
  PT/EN/ES); o resto recebe "a IA fica disponível quando o tutorial terminar". Nada vai para o modelo — sem conflito com
  a voz do tutorial e sem gastar a placa de vídeo.
- **Preparação em segundo plano** durante o tutorial (com o progresso no cartão: IA ✓ · voz ✓ · apps ✓ ·
  integrações ✓): a IA carrega e guarda o prompt em cache, a voz (Whisper) carrega ou é baixada, a lista de apps é lida
  e o clima e a cotação da sua cidade ficam em cache.
- **Aviso de protótipo**: "a IA pode cometer erros" embaixo da conversa, discreto no canto da tela, no primeiro passo
  do tutorial e em Configurações → Sobre.
- **Configurações → Sobre o NEXUS** (grupo novo):
  - **Sobre**: versão, o que **funciona**, o que está **em beta** (a mesma lista da seção Beta) e o que **ainda não
    funciona**, e a autoria.
  - **Atualizações**: cada versão do CHANGELOG com o resumo e o que foi novo, corrigido e medido.
  - **Possíveis erros**: os 70 problemas do catálogo que ainda podem acontecer (os corrigidos ficam em Atualizações),
    com busca, filtro por área, o que acontece, por quê e como resolver — no idioma do NEXUS.
- **Funções movidas para o Beta** (desligadas no modo usuário, ligadas no modo desenvolvedor):
  **letras de músicas** (dependem de serviços de fora; a API do Vagalume estava fora do ar nos testes),
  **suas integrações** (serviços da web por palavra-chave) e **AMD: ROCm e NPU (Lemonade)** (sem hardware para testar;
  na RX 6600 XT o ROCm manda a IA para o processador). Voltar para o Vulkan sempre funciona.
- **Autoria, nome e identidade visual**: arquivo NOTICE, README e Termos (versão 1.3): o código continua MIT; o nome
  N.E.X.U.S, os nomes NEX-1.0, o logo, o ícone, o PET e a identidade visual não fazem parte da licença.

### Corrigido
- **NX-LLM-051 — continuação perdia o contexto**: "e 50 desses em reais?" (depois de "e o euro?") respondia a cotação do
  real; agora usa a moeda e a quantia (50 euros = R$ 285,98). "que horas são lá?" (depois de "e lá, vai chover?") dava
  São Paulo; agora usa o último lugar citado (Paris).
- **NX-LLM-052 — obras inventadas** em recomendações e listas ("O Código Da Vinci" como ficção científica, "Iracema" de
  Machado de Assis): recomendações e listas de livros, filmes, séries e álbuns consultam a Wikipédia antes
  (ficção científica → "Duna"; Machado de Assis → "Memórias Póstumas de Brás Cubas").
- **NX-LLM-053 — "como eu abro os menus?"** abria um menu e dizia que Ctrl+Espaço mostra os menus: perguntas de "como
  fazer" recebem as instruções reais do NEXUS, e a ferramenta de abrir menus só abre quando você pede.
- Comandos digitados durante o tutorial não eram tratados (iam para a IA no meio da fala).

### Desempenho
- Depois do tutorial, "como está o tempo?" e "quanto está o dólar?" respondem em **0,000 s** (do cache preenchido
  durante o tutorial) — antes, a primeira vez levava **2,4 s** (clima) e 0,35 s (câmbio). A preparação inteira leva ~2 s
  enquanto o tutorial fala.
- Continuações de clima/horário ("e lá?") respondem em **0,2 s** sem o modelo (antes ~5 s pelo modelo, e com a cidade
  errada no horário).
- Avaliação de conversa: média **5,0 s** por resposta (v0.19.7: 5,5 s).

### Testes desta versão
- 347/347 testes unitários (12 novos: comandos do tutorial em PT/EN/ES, "50 desses", "lá" duas perguntas depois, obras
  consultadas, "como abro" explicado e "abre" abrindo, instruções do NEXUS no contexto, aba Atualizações, aba Possíveis
  erros nos 3 idiomas, novas funções beta desligadas, letras fora com o beta desligado, seções e botão Voltar na
  interface, documentos no executável).
- Avaliação de conversa com o modelo real: **36/37** — o caso do simulado falhou uma vez (variação do modelo, NX-LLM-012)
  e passou 3/3 ao repetir. Bateria de contexto: 13 conversas de continuação com o modelo real.
- Tutorial, Atualizações e Possíveis erros conferidos na prévia da interface.

---

## v0.19.7 — Protótipo · 2026-10-16

**Correções do uso real no modo convidado: a IA não inventa mais fatos nem letras, letras com a fonte que você diz,
tutorial no ritmo da voz e o convidado com a própria saudação.**

### Corrigido
- **NX-LLM-048 — fatos inventados** ("a abertura de Dragon Ball GT é The New Power", depois "KAT-TUN"): perguntas
  sobre músicas, séries, filmes, livros e pessoas obrigam a consultar a Wikipédia; a busca usa as palavras importantes
  (sem "quem canta a…"), lê os **3 melhores artigos** e devolve os **trechos sobre o detalhe** pedido (o resumo não
  citava a música); a IA só pode responder com nomes do texto encontrado e, se a consulta falhar, diz que não
  conseguiu verificar. Teste com o modelo real: Dragon Ball GT → Field of View, "Sorriso Resplandecente (Dan Dan Kokoro
  Hikareteku)"; Cavaleiros do Zodíaco → "Pegasus Fantasy"; Ada Lovelace continua sem consulta (conhecimento geral).
- **NX-LLM-049 — letras inventadas**: o NEXUS nunca escreve letras de memória. **Letras só de uma fonte que você diz**:
  "cante X, letra do **LRCLIB**" (base aberta feita para apps de música, sem chave) ou "do **Vagalume**" (API oficial
  com chave grátis em Configurações → Integrações; sem a chave — ou com a API fora do ar — a página abre no
  navegador); **Letras.mus.br** e **Genius** abrem no navegador (não têm API pública, e copiar dos sites vai contra
  os termos deles). A letra vem com a fonte e o link; "cante essa" usa a música da conversa; o contexto ("Dragon Ball
  GT") escolhe a certa entre músicas de mesmo nome, e um título traduzido que não existe na fonte tenta o original.
  Sem fonte, ele explica como pedir (e toca a música com o Navegador ligado).
- **NX-LLM-050 — tutorial pulando**: cada passo avança **quando a fala dele termina** (+0,9 s) em vez de um tempo fixo;
  a verificação de sistemas fala antes e o tutorial espera.
- **Modo convidado**: saudação própria ("Você está no modo convidado: nada desta conversa será guardado") e sem pedir
  para importar perfil; a verificação de sistemas não acusa mais a voz (o modelo embutido conta como pronto).

### Desempenho
- "Cante X": **0,4 s** com a letra real (LRCLIB) ou **0 s** perguntando a fonte — antes a IA levava ~15 s escrevendo uma
  letra inventada.
- O tutorial não acumula mais falas: com a voz levando 5 s por passo, cada passo dura 5,9 s (antes avançava em 4,5 s e
  as falas se empilhavam).
- Perguntas de fatos ficaram ~6 s mais lentas (consultam a Wikipédia) — em troca de respostas corretas.
- Avaliação de conversa 37/37 (média 5,5 s, mesmas 27 perguntas).

### Testes desta versão
- 335/335 testes unitários (6 novos: detalhe lido do artigo, consulta obrigatória para fatos de músicas/séries, fonte e
  música entendidas em PT/EN/ES, a música certa entre homônimas, sem fonte ele pergunta, saudação do convidado).
- Avaliação de conversa **37/37** com o modelo real; tutorial conferido na prévia com voz lenta.
- Autoteste do executável (`--selftest`).

---

## v0.19.6 — Protótipo · 2026-10-16

**Ícone do programa e o PET: a esfera do NEXUS no lugar do aro, com o olho seguindo o mouse.**

### Novo
- **Ícone do programa**: a esfera do NEXUS no executável (e na interface). `assets/nexus.ico` traz 16, 24, 32, 48, 64,
  128 e 256 px; em 16 e 24 px usa só o olho, recortado redondo, para continuar reconhecível na bandeja.
- **PET** (Configurações → Personalização → **No centro da tela: Aro ou PET**; também por voz: "modo pet", "volta pro
  aro"): a esfera fica no mesmo lugar do aro e tem **as mesmas animações**, exceto o aro em volta:
  - passeia pela tela, repousa, encaixa acima dos menus (e a miniatura também é o PET), cresce com a voz e brilha com o
    microfone;
  - o núcleo do aro fica sobre o olho e **respira** no mesmo ritmo de cada estado (mais rápido ao ouvir e ao pensar);
  - o olho **gira** como o anel segmentado interno do aro (6x mais rápido ao ouvir, 9x ao pensar, parado em pausa) e
    **segue o cursor do mouse** (volta ao centro depois de 4 s parado);
  - o olho **muda de cor com o tema** (vermelho no tema AMD, verde na Esmeralda...); com o microfone mudo ele apaga;
  - ondas no download e no modo suspenso, como o aro.

### Desempenho
- O PET roda a **60 fps estáveis**, igual ao aro (medido no estado "pensando", o mais animado).
- Camadas do PET em WebP sem perda: **442 KB → 322 KB (-27%)**.
- A frase da verificação de sistemas aparecia duas vezes (legenda e conversa); agora uma.

### Testes desta versão
- 329/329 testes unitários (2 novos: "modo pet" / "volta pro aro" sem a IA; as camadas do PET e o ícone no lugar).
- Autoteste do executável (`--selftest`).

---

## v0.19.5 — Protótipo · 2026-10-16

**Suporte a ROCm (onde a placa permite, com comparação na sua máquina) e à NPU dos Ryzen AI pelo AMD Lemonade Server.**

### Novo
- **Backend da IA: Vulkan ou ROCm** (Configurações → AMD): o NEXUS identifica o chip da Radeon (gfx1032, gfx1100,
  gfx1201...) e lê **da instalação do Ollama** para quais chips o ROCm dele tem bibliotecas (hoje: gfx906, gfx1030,
  gfx1100/1101/1102, gfx1150/1151, gfx1200/1201) — um Ollama mais novo com mais chips é reconhecido sozinho.
  - Placa com suporte: **Usar ROCm** / **Voltar ao automático** (com confirmação; cria/remove a variável de usuário
    `OLLAMA_VULKAN=0` e reinicia o Ollama) e **Comparar Vulkan × ROCm**: a mesma pergunta nos dois, mostrando tokens/s e
    quanto ficou na placa, e volta à sua escolha.
  - Placa sem suporte: o botão fica desligado e o NEXUS explica por quê (com o teste abaixo).
- **NPU (Ryzen AI)**: detecção das NPUs que o Windows conhece (AMD "NPU Compute Accelerator", Intel AI Boost...) e do
  **AMD Lemonade Server** (servidor local da AMD que roda modelos na NPU, compatível com OpenAI) — com ele rodando, **Usar
  a NPU (Lemonade)** troca o provedor da IA com um clique (e volta ao Ollama). Lemonade também entrou na lista de
  provedores e nas referências AMD.
- Tecnologias AMD: o estado do ROCm e do Ryzen AI agora vem desses testes reais (chip suportado, NPU encontrada,
  Lemonade rodando).

### Medido (RX 6600 XT, gfx1032)
- **ROCm forçado** (`OLLAMA_VULKAN=0` + `HSA_OVERRIDE_GFX_VERSION=10.3.0`, o truque do Linux): o Ollama diz "no
  ROCm-capable device is detected" e roda no processador — **9,1 tokens/s, 0% na placa**, contra **35,6 tokens/s no
  Vulkan** (92% na placa). Por isso o NEXUS só oferece ROCm onde ele funciona: escolher errado custaria 3,9x de
  velocidade.
- O NPU não pôde ser medido neste PC (o Ryzen 5 5600G não tem NPU).

### Corrigido
- Reiniciar o Ollama (otimização da placa) agora também fecha o `llama-server.exe` das versões novas e leva as
  variáveis gravadas para o usuário ao Ollama reiniciado.

### Testes desta versão
- 327/327 testes unitários (5 novos: chip de cada Radeon, ROCm só onde há bibliotecas, ROCm recusado em placa sem
  suporte, preset do Lemonade, detecção da NPU e do Lemonade).
- Autoteste do executável (`--selftest`).

---

## v0.19.0 — Protótipo · 2026-10-16

**Contas locais e modo convidado, monitor de downloads, armazenamento ao vivo, verificação de sistemas na primeira
abertura, tecnologias AMD explicadas, voz já instalada e grupos das Configurações recolhíveis.**

### Novo
- **Contas locais** (`nexus/accounts.py`): cada conta tem a própria pasta (memórias, conversas, agenda,
  configurações, backups); a conta principal continua com os dados de sempre (nada é movido).
  - **Senha opcional**: só um hash scrypt com sal é guardado; 5 erros em 1 minuto fazem esperar. Com senha (ou com mais
    de uma conta) o NEXUS abre na tela **"Quem está usando o NEXUS?"**: até entrar, **nenhuma chamada de dados
    responde**, o microfone não abre e os lembretes que tocarem esperam.
  - **Convidado**: uma pasta temporária, apagada ao fechar (e as que um travamento deixar são limpas no dia seguinte);
    sem backups. Um aviso "MODO CONVIDADO · NADA É GUARDADO" fica no topo.
  - **Trocar de conta** reinicia o NEXUS na pasta da outra conta (a senha é conferida antes; a nova janela recebe um
    código de uso único, válido por 30 s). Configurações → **Conta**: senha, **Bloquear agora**, trocar, apagar
    (com a senha da conta).
- **Downloads** (Configurações → Sistema → Downloads): um **terminal** com tudo o que o NEXUS baixa (modelos de IA,
  modelo de voz) — barra, porcentagem, tamanho, velocidade, tempo restante e **TRAVADO** quando nada chega por 20 s,
  com o registro de cada etapa.
- **Dados → Armazenamento ao vivo**: o total da pasta de dados (com quanto mudou desde que a aba abriu), o disco livre
  e cada parte — banco de dados (e quantas memórias, mensagens, documentos, tarefas... há dentro), biblioteca, áreas de
  trabalho, backups, logs, cache das integrações, temporários, o programa, os modelos de voz e cada modelo de IA.
  Atualiza a cada 2 s.
- **Verificação de sistemas**: na primeira abertura o NEXUS confere banco de dados, IA, placa de vídeo,
  reconhecimento de voz, voz, microfone, internet, disco e base de conhecimento e diz *"Todos os sistemas estão em
  completo funcionamento. NEXUS está pronto para uso."* — ou o que precisa de atenção. Botão **Verificar sistemas** em
  Configurações → Geral.
- **Tecnologias AMD no NEXUS** (aba AMD): Radeon + Vulkan (em uso), **ROCm** (usado pelo Ollama nas placas com suporte
  no Windows — RX 7000, RX 6800/6900, Radeon PRO; a RX 6600 XT não está na lista), Adrenalin (versão), processador
  Ryzen (parte do modelo que não cabe na placa e o Whisper), Ryzen AI / NPU (precisa de um processador Ryzen AI) e as
  métricas da Radeon — com o estado de cada uma neste PC.
- **Grupos das Configurações** com ícone, seta e destaque, **recolhíveis** (clique no grupo) e **Recolher tudo /
  Expandir tudo**; o grupo da seção aberta sempre se abre; a escolha fica lembrada.
- **A voz já vem com o NEXUS**: o modelo Whisper small vai junto no programa (`build_whisper.py`) — dá para falar logo
  depois de instalar.

### Desempenho
- **Primeira fala**: antes baixava 484 MB (~1 min nesta internet); agora o modelo empacotado carrega em **0,9 s**.
- **Abertura**: a animação completa (4,2 s) só na primeira vez do dia; nas outras a interface aparece em **1,5 s**
  (medido: 4,26 s → 1,46 s).
- O tamanho dos modelos de voz deixou de ser contado em dobro (o cache do Hugging Face usa links: 972 MB → 486 MB).
- Avaliação de conversa 37/37 (média 5,5 s, mesmas 27 perguntas); código: imports sem uso removidos.

### Corrigido
- NX-LLM-045: "isso é magenta, não rosa choque" — tons com nome, "claro/escuro" em qualquer cor, a correção reaplica a
  cor e "Pronto" sem mudança faz a IA chamar a ferramenta.
- NX-LLM-046: a música só abre no Spotify / YouTube Music / LiMusic quando o usuário cita o serviço.
- NX-LLM-047: a janela das Configurações agora arrasta em todas as seções (faixa do topo e título).
- As respostas instantâneas de navegação ("abre minhas memórias") entram no histórico da conversa.

### Testes desta versão
- 322/322 testes unitários (18 novos: tons e correção de cor, rede de segurança do "Pronto", serviço de música, contas
  — pasta própria, hash, senha certa/errada, espera após 5 erros, tela de quem usa, troca com código de uso único,
  convidado temporário, chamadas travadas sem dados, apagar com senha —, downloads com TRAVADO, armazenamento,
  tecnologias AMD, voz empacotada, navegação no histórico).
- Avaliação de conversa **37/37** e da área de trabalho **7/7** com o modelo real.
- Autoteste do executável (`--selftest`).

---

## v0.18.6 — Protótipo · 2026-10-16

**Modelos locais para PCs mais fracos e mais fortes, testados de verdade: catálogo NEX-1.0 Lite / Mini / Pro / Max,
o que cabe em cada PC, recomendação automática, download com progresso no aro e troca com um clique.**

### Novo
- **Configurações → Inteligência → Modelos locais** (`nexus/models.py`): um cartão por modelo com o nome do produto
  (**NEX-1.0 Lite**, **Mini**, **NEX-1.0**, **Pro**, **Max**), tamanho, uma barra com **quanto dele cabe na sua placa**
  (cabe, parte na RAM, só no processador ou não cabe), os números medidos no PC de referência, **RECOMENDADO** para o
  seu PC e **EM USO**.
  - **Baixar** pede confirmação (nome, tamanho) e o aro mostra **BAIXANDO MODELO** com a porcentagem; **Usar este**
    tira o modelo anterior da placa e carrega o novo em segundo plano. O nome mostrado vira o do modelo (ex.:
    "NEX-1.0 Pro").
  - Recomendação: o maior modelo que roda (quase) inteiro na placa — sem placa ou 4 GB → Lite; 6 GB → Mini; 8 GB →
    NEX-1.0; 12–16 GB → Pro; 24 GB → Max. Com **duas placas dedicadas** a memória delas soma (o Ollama divide o
    modelo entre elas).
- `tests/bench_models.py`: compara modelos no PC — partida a frio, quanto fica na placa, tokens/s, primeira palavra,
  resposta média e a **avaliação completa de conversa (37 verificações)** com cada um.

### Medido (Ryzen 5 5600G, 16 GB, RX 6600 XT 8 GB, Ollama 0.40.5/Vulkan)
| Modelo | Na placa | Partida a frio | Tokens/s | 1ª palavra | Resposta média | Avaliação |
|---|---|---|---|---|---|---|
| NEX-1.0 Lite (qwen3:1.7b) | 100% | 5,3 s | 30,2 | 0,4 s | 2,8 s | 32/37 |
| NEX-1.0 Mini (qwen3:4b-instruct-2507) | 100% | 17,9 s | 24,2 | 2,7 s | 6,6 s | 36/37 |
| **NEX-1.0** (qwen3:8b) | 92% | 14,5 s | 21,4 | 1,5 s | 5,5 s | **37/37** |
| NEX-1.0 Pro (qwen3:14b) | 58% | 31,8 s | 7,3 | 3,9 s | 12,9 s | 37/37 |
- Numa placa de 8 GB o **Pro é 2,4x mais lento** que o NEX-1.0 sem acertar mais: o NEX-1.0 continua o padrão para
  8 GB; o Pro é recomendado só onde cabe inteiro (12 GB ou mais).
- O **Lite** é rápido mas falhou em guardar memória, aprender, corrigir o simulado, explicar a piada e abrir o livro:
  bom para conversa simples em PCs fracos.
- A GPU integrada do Ryzen (Vega 7) não ajudaria: usa a mesma RAM que o processador já usa para a parte do modelo que
  não cabe na placa (e no PC de referência está desligada na BIOS).

### Corrigido
- NX-LLM-043: a tag "qwen3:4b" do Ollama é o modelo que **pensa** antes de responder — **69,6 s** por resposta; o Mini
  usa a versão instruct do mesmo modelo: **6,6 s** (10x mais rápido).
- NX-LLM-044: "toca … no YouTube" às vezes abria o YouTube Music (a IA escolhe só YouTube, Spotify ou LiMusic).
- A avaliação de conversa não abre mais nada de verdade no PC (navegador, apps, teclas de mídia).

### Testes desta versão
- 304/304 testes unitários (7 novos: recomendação por PC, o que cabe numa placa de 8 GB, só processador, nomes NEX,
  catálogo instalado/em uso/recomendado, troca recusada sem o modelo instalado, a tag pensante fora do catálogo).
- Avaliação de conversa **37/37** com o NEX-1.0 (e com o Pro); 36/37 com o Mini; 32/37 com o Lite.
- Autoteste do executável (`--selftest`).

---

## v0.18.5 — Protótipo · 2026-10-16

**Configurações reorganizadas em grupos, aba Personalização separada da Interface, painel AMD ao vivo e o NEXUS
mudando as próprias configurações quando você pede.**

### Novo
- **Configurações em grupos**: Sistema · Inteligência · Voz · Aparência · Conexões · Hardware · Dados e privacidade,
  com seções novas — **Memória e conversas** (memorizar, títulos, trocas lembradas), **Ativação e escuta** ("Nexus",
  segundo plano, proteção contra eco e ruído), **Personalização** e **AMD**.
- **Interface x Personalização**: Interface só liga e desliga (marcações, legendas, animações, menus, texto abaixo do
  aro, aro se movendo). Personalização reúne o que muda o visual:
  - **7 temas** com prévia (NEXUS, **AMD**, Esmeralda, Violeta, Âmbar, Grafite, Gelo) e as cores do aro, núcleo e fundo;
  - **tamanho do aro** (60–140%), **velocidade do giro**, **tamanho do texto** abaixo do aro, **fundo** (brilho, liso
    ou grade de HUD), **letra dos títulos** (futurista ou limpa), cursor, repouso e tempo do texto. Tudo com prévia
    ao vivo.
- **O NEXUS muda as próprias configurações** (`nexus/prefs.py`): "muda o aro para vermelho", "aro vermelho e núcleo
  branco", "deixa o fundo preto", "tema AMD", "voz feminina", "fala mais rápido", "aro maior", "letra maior",
  "desliga as animações" e **"desfaz"** — reconhecidos sem a IA, aplicados na hora e a tela muda junto. Em outras
  frases a IA usa a nova ferramenta `set_preference` (só as opções permitidas, cada valor validado). Sem dizer o
  valor ("quero mudar a cor do aro"), ele abre Personalização.
- **Abas exatas**: "abre a aba AMD", "abre a personalização", "abre as configurações de ativação", "abre minhas
  memórias", "abre os aprendizados", "abre o conhecimento" — seções das configurações e abas do painel.
- **Painel AMD** (Configurações → AMD), no espírito da sobreposição de desempenho do AMD Software: Adrenalin Edition e
  com o visual do N.E.X.U.S.:
  - a placa, a versão do **Adrenalin** e do driver e o backend do Ollama (Vulkan/ROCm), lidos do registro do driver;
  - **ao vivo** (a cada 1,5 s, ~2 ms por leitura): uso da placa por motor, memória de vídeo, quanto **a IA** usa da
    placa e da VRAM, com gráfico dos últimos 60 s — pelos contadores do Windows (os mesmos do Gerenciador de Tarefas);
  - **IA na placa**: tokens/s médios, tempo até a primeira palavra, a última resposta, quanto do modelo está na VRAM e
    o histórico de tokens/s;
  - **Liberar a placa agora** / **Carregar a IA de novo**, a otimização do Ollama para placas AMD (movida de
    Desempenho) e **referências da AMD**: Adrenalin, ROCm, GPUOpen, Developer Central, Ryzen AI, Ollama em placas
    AMD e o AMD Developer Hackathon.

### Desempenho
- **Mudar a aparência por voz**: **0 s** (antes o NEXUS só abria o menu; pela IA, 3–6 s).
- **Descrições das ferramentas mais curtas**: o prompt fixo caiu de 3.377 para 3.090 tokens **mesmo com a ferramenta
  nova** — partida a frio 14,6 s → 14,0 s (toda releitura do prompt fica ~0,6 s mais rápida).
- Avaliação de conversa nas mesmas 27 perguntas: média **5,3 s → 5,1 s**.

### Corrigido
- NX-LLM-042: a IA dizia "Pronto: tema AMD." sem chamar a ferramenta (nada mudava). Teste: 0/4 → 4/4.

### Testes desta versão
- 297/297 testes unitários (13 novos: frases de preferência sem a IA, tema com as três cores e desfazer, validação,
  mudança instantânea avisando a interface, rede de segurança do set_preference, seções e abas exatas, open_interface
  com abas, informações da placa pelo registro, contadores ao vivo, referências só da AMD, tokens/s e primeira palavra,
  lista de ferramentas enxuta).
- Avaliação de conversa **37/37** (2 novos: "muda o aro para vermelho" muda de verdade; "abre minhas memórias" abre a
  aba certa) e da área de trabalho 7/7 com o modelo real.
- Autoteste do executável (`--selftest`).

---

## v0.18.1 — Protótipo · 2026-10-16

**Correção: o NEXUS não fala mais sozinho (eco da própria voz, emojis lidos em voz alta e frases inventadas com o
microfone parado).**

### Corrigido
- **NX-VOZ-019 — o NEXUS ouvia a própria voz e respondia a ela.** Visto no uso real: depois de uma resposta que
  terminava com 😄, chegou a mensagem "Cara sorrindo de boca aberta e olha o sonho". A voz do Windows lia o emoji pelo
  nome, e com o microfone do DroidCam (com atraso, pelo Wi-Fi) o fim da fala chegava depois da proteção de eco.
  - Emojis aparecem na tela mas **não são lidos** em voz alta.
  - O NEXUS guarda o que disse nos últimos segundos: uma frase ouvida até 2,5 s depois que ele parou e que repete um
    trecho de 4 ou mais palavras dele é descartada. Mais tarde, só uma repetição quase literal — escolher uma das
    opções que ele ofereceu ("jogar um jogo de perguntas") continua valendo como resposta.
- **NX-VOZ-020 — frases inventadas pelo Whisper** com ruído ("Você tem um clima? Você tem um clima? Você tem um
  clima?", "Legendas pela comunidade Amara.org"): na escuta contínua, trechos de baixa confiança ou repetitivos, créditos
  de legenda e a mesma frase 3 vezes são descartados. O apertar-para-falar continua como antes.

### Qualidade (medido com áudio real: voz do NEXUS sintetizada, Whisper small)
- Eco: **3/3 descartados** (antes 0/3 — todos viravam mensagens do usuário).
- Respostas do usuário: **3/3 aceitas** ("Conta uma piada", "Quero jogar perguntas e respostas", "Me fala sobre
  filosofia estoica").
- Ruído puro: **3/3 sem texto** (o filtro novo sozinho deixava passar "Legendas pela comunidade Amara.org"; as regras
  foram combinadas).
- Na noite de 15/10, 5 de 12 mensagens "do usuário" pareciam eco ou ruído — cada uma custava uma resposta da IA (~5 s de
  placa de vídeo) e uma fala que ninguém pediu.

### Testes desta versão
- 284/284 testes unitários (5 novos: emojis não lidos, eco descartado logo depois da fala, respostas que reaproveitam
  palavras aceitas, frases inventadas e repetidas, e a escuta completa: eco, repetição e ruído nunca chegam à IA e a
  resposta real chega).
- Autoteste do executável (`--selftest`).

---

## v0.18.0 — Protótipo · 2026-10-16

**Central de integrações (12 integrações + as suas), respostas ao vivo sem a IA, controle de mídia e abrir aplicativos
com modo suspenso para jogos.**

### Novo
- **Central de integrações** (`nexus/connectors.py`, Configurações → Integrações): cada integração é um cartão com
  estado ao vivo (**dormindo · ativa agora · em cache até 14:32 · sem internet · erro**), fonte, quanto tempo guarda,
  quantas vezes foi usada e quantas vieram do cache, botão **Testar** e liga/desliga.
  - **Novas**: criptomoedas (CoinGecko), relógio mundial ("que horas são em Tóquio?"), tradutor (MyMemory: "traduza
    bom dia para inglês", "como se diz obrigado em japonês?"), feriados (Nager.Date: "qual o próximo feriado?"),
    qualidade do ar e índice UV (Open-Meteo/CAMS), nascer e pôr do sol, **calculadora** e **conversor de unidades**
    (no computador, sem internet). Já existentes: clima, câmbio, notícias, Wikipédia e calendário ICS (agora também
    Outlook).
  - **Suas integrações**: nome, palavras-chave e um endereço https com `{query}`; quando a mensagem tem uma das
    palavras, o NEXUS consulta e usa a resposta. Só https, resposta limitada.
  - **Modular**: nada roda em segundo plano. O NEXUS reconhece sem a IA qual integração a mensagem precisa e só ela é
    ativada; a resposta fica guardada (câmbio 1 h, clima 15 min, cripto 5 min, feriados 1 dia, tradução 30 dias) num
    arquivo da pasta de dados, então perguntar de novo não usa a internet. Sem internet, usa a última cópia e avisa
    que pode estar desatualizada. Integrações desligadas também saem da lista de ferramentas da IA.
  - Sua moeda e seu país (feriados) em Configurações → Integrações (padrão: pelo idioma).
- **Controle de mídia** (beta): "pausa a música", "continua", "próxima", "música anterior", "volume em 30", "aumenta
  o volume", "muta", "o que está tocando?" — instantâneo, sem a IA. Funciona com qualquer player dos controles de mídia
  do Windows (Spotify, **LiMusic**, YouTube no navegador…). Configurações → Apps e mídia mostra o que está tocando,
  botões e o volume do PC. Player preferido para "toca…": YouTube, YouTube Music, Spotify ou LiMusic.
- **Abrir aplicativos** (beta): "abre o Discord", "abre o vscode", "abre o zap", "vamos jogar RetroArch". A lista vem
  do menu Iniciar (programas, apps da Loja e atalhos da Steam); cada app é **trabalho**, **jogo** ou **launcher** e você
  pode mudar em Configurações → Apps e mídia.
  - **Modo suspenso para jogos**: ao abrir um jogo, o NEXUS avisa, tira a IA da placa de vídeo, minimiza, roda em
    prioridade baixa e só volta quando você diz "Nexus" ou volta para a janela (os lembretes continuam). Opcional:
    suspender também quando um jogo aberto por fora vem para a frente (Steam, Epic, Riot, Xbox, emuladores). Botão
    "Suspender agora". O aro mostra **SUSPENSO**.
- Termos de Uso / Política de Privacidade **versão 1.2**: lista os novos serviços (CoinGecko, MyMemory, Nager.Date),
  as integrações do usuário e explica que a lista de apps e o que está tocando ficam no computador.

### Desempenho
- **Perguntas ao vivo** (qwen3:8b na RX 6600 XT): dólar **7,4 s → 0,4 s** (do cache, **0 s**); euro 9,3 s → 0,2 s;
  clima 8,1 s → 2,4 s (cidade nova) / 0,2 s; notícias **29,9 s → 0,3 s**; relógio mundial 0,8 s; tradução 1,1 s;
  calculadora e unidades ~1 ms. Uma pergunta longa sobre o clima ("vale a pena ir de bicicleta?") 12,6 s → 6,1 s: o
  dado já vai no contexto e a IA responde numa rodada só.
- **Conexões reaproveitadas** com os serviços: cada nova conexão segura custava ~0,6 s; o clima (2 pedidos) ficou
  ~1 s mais rápido.
- Avaliação de conversa: média **6,3 s → 5,3 s** por resposta.
- **Modo suspenso**: libera **6,1 GB de VRAM** (o modelo inteiro) para o jogo em 0,6 s; ao acordar, o NEXUS recarrega o
  modelo em segundo plano (~16 s).

### Corrigido
- NX-LLM-041: perguntas ao vivo em duas rodadas (a IA chamava a ferramenta mesmo com o dado no contexto).
- NX-INT-007: "New York" no clima/relógio virava York, Nebraska (busca de cidade por idioma).

### Testes desta versão
- 279/279 testes unitários (21 novos: rota de cada integração e nada para conversa/gastos, argumentos tirados da
  mensagem, calculadora e unidades exatas, código nunca executado, resposta na hora com nome e símbolo, cache sem
  internet, cópia offline marcada, integração desligada sai das ferramentas, ferramenta lookup, integrações do
  usuário só https, estado de cada integração, frases de mídia, apps por nome/apelido, jogos x launchers x trabalho,
  jogo abre e suspende, calculadora sem a IA, beta desligado, termos 1.2).
- Avaliação de conversa **35/35** (3 novos: as perguntas ao vivo trazem o dado) e da área de trabalho 7/7 com o modelo
  real.
- Autoteste do executável (`--selftest`).

---

## v0.17.5 — Protótipo · 2026-10-16

**Modo treinamento com a aba Aprendizados e importação de memórias de outras IAs (as duas em beta).**

### Novo
- **Modo treinamento** (beta, `Ctrl+8`, botão no menu esquerdo ou por voz: "começa o treinamento sobre astronomia" /
  "termina o treinamento", em PT/EN/ES). Durante o treino o usuário ensina falando normalmente; cada frase é anotada na
  hora ("Anotado (3).") e as perguntas continuam indo para a IA. O rótulo do aro mostra **TREINAMENTO**.
  - Ao terminar, o NEXUS **analisa**: cada frase afirmativa vira um fato; os fatos sobre o usuário (eu/meu/minha) vão
    para as memórias; os gerais são conferidos com a **Wikipédia** (busca de texto completo, só com os termos aceitos,
    internet e integrações ligadas) e a **base local**, e a IA julga cada um (confirmado / contestado / não verificado)
    numa única chamada. O aro mostra **ANALISANDO** com as ondas e a porcentagem no núcleo, como no download da voz.
  - Fica o que foi confirmado (base de conhecimento, categoria **Aprendizados**, com a fonte); fica de fora o que foi
    contestado (com a correção) ou não pôde ser verificado. O NEXUS diz: "Análise completa. Aprendi 2, deixei 2 de
    fora, e a concordância com as fontes foi de 50 por cento." — a concordância conta só o que pôde ser comparado.
  - Nova aba **Aprendizados** no painel: cada treinamento com tema, data, concordância e os fatos (expande ao clicar).
- **Importar memórias de outras IAs** (beta, aba Memória → **Importar**): escolha ChatGPT, Claude, Gemini, Copilot ou
  outra, copie o prompt pronto (PT/EN/ES), cole na outra IA e cole a resposta de volta. Cada linha `- [categoria] texto`
  vira uma memória marcada com a origem; as repetidas são ignoradas. A aba Memória ganhou **filtros por origem**
  ("Todas · 3", "NEXUS · 2", "ChatGPT · 1").

### Desempenho
- **Lições do treinamento sem chamar a IA**: 1,88 s → 0,001 s por lição (medido com qwen3:8b na RX 6600 XT, 4 lições).
- **Extração dos fatos sem a IA**: a chamada de extração levava 8,8 s; a extração determinística leva 0,1 ms. Uma
  análise completa de 4 lições (busca na Wikipédia + julgamento) termina em 6,5 s.

### Corrigido
- NX-LLM-039: a extração pela IA perdia os fatos gerais e o julgamento era feito sem evidência.
- NX-LLM-040: a IA perguntava "quer que eu armazene?" a cada lição.

### Testes desta versão
- 258/258 testes unitários (10 novos: comandos de treino nos 3 idiomas, extração de fatos, anotação instantânea,
  análise e concordância, o que é salvo e o histórico, importação, origem e repetidas, prompt nos 3 idiomas, beta
  desligado para usuários).
- Avaliação de conversa 32/32 e da área de trabalho 7/7 com o modelo real.
- Teste com o modelo real: Júpiter confirmado (fonte: Wikipédia), Marte contestado (nota: Mercúrio), Lua não
  verificada, "meu planeta favorito é Saturno" salvo na memória; concordância 50%.
- Autoteste do executável (`--selftest`).

---

## v0.17.1 — Protótipo · 2026-10-16

**Licença MIT.**

### Novo
- **Licença MIT** (arquivo `LICENSE`, © 2026 Bryan Maciel de Almeida). As regras do hackathon AMD Developer Hackathon:
  ACT III (lablab.ai) pedem envios "originais, de código aberto e compatíveis com a Licença MIT", com repositório
  público no GitHub.
- Termos de Uso **versão 1.1** (PT/EN/ES): a cláusula 11 passa a explicar a licença — o código pode ser usado,
  modificado, distribuído e vendido mantendo o aviso de direitos autorais; uma versão modificada não pode se apresentar
  como o NEXUS oficial. Como o texto mudou, todos aceitam de novo uma vez.
- README: seção Licença com os componentes de terceiros e suas licenças (todas compatíveis com a MIT).

### Testes desta versão
- 248/248 testes unitários (1 novo: arquivo LICENSE MIT e a licença citada nos termos dos 3 idiomas).
- Autoteste do executável (`--selftest`).

---

## v0.17.0 — Protótipo · 2026-10-15

**Termos de Uso e Política de Privacidade (nada é captado nem enviado antes do aceite) e otimização do Ollama para
placas AMD.**

### Novo
- **Termos de Uso e Política de Privacidade** (PT/EN/ES, versão 1.0) na primeira abertura, antes de qualquer outra
  coisa: abas para ler os dois textos, confirmação de idade (18+ ou com consentimento de um responsável) e de leitura;
  "Recusar e sair" fecha o NEXUS. A tela não fecha com Esc nem com clique fora.
  - Escritos a partir do que o NEXUS realmente faz: o que fica no computador (e onde), o que sai e para quem
    (provedores de IA na nuvem, Open-Meteo, Google Notícias, Frankfurter, Wikipédia, Google/Cloudflare para medir a
    conexão, Hugging Face, Google Fonts, o navegador), o microfone (processado em memória, nunca gravado), a chave de API
    (DPAPI), bases legais da LGPD, direitos (acessar, exportar, corrigir, apagar, revogar), retenção, menores de idade,
    limites da IA, emergências, finanças, ações no computador, funções beta, sem garantia e contato pelo GitHub.
  - **Antes do aceite nada é captado nem enviado**: o microfone não abre, a conexão não é medida e as fontes da
    internet não são carregadas. Instalações existentes também veem a tela uma vez.
  - Nova seção **Configurações → Privacidade e termos**: data e versão do aceite, os dois textos para ler quando quiser
    e **Revogar o aceite** (fecha o microfone, para o acesso à internet e pede o aceite de novo).
- **Configurações → Desempenho → Placa de vídeo**: em placas AMD que o Ollama roda pelo Vulkan (sem ROCm), o botão
  **"Otimizar o Ollama para esta placa"** explica o efeito, pede confirmação, cria a variável de usuário
  `OLLAMA_FLASH_ATTENTION=0` e reinicia o Ollama; **"Desfazer"** remove e reinicia de novo. Placas NVIDIA (e AMD com
  ROCm) não veem a opção — nelas o Flash Attention ligado é o mais rápido.

### Desempenho
- **Ollama na RX 6600 XT (AMD, Vulkan)**: com o Flash Attention desligado, uma conversa de 8 perguntas passou de
  **16,4 s para 11,9 s por resposta (−27%)** no Ollama 0.40.4 e de **14,2 s para 9,0 s (−37%)** no 0.40.5 — leitura
  do prompt 6,8 s → 1,1 s. Custo: a geração fica ~30% mais lenta e
  ~0,5 GB do modelo vai para a RAM (o Flash Attention desligado reserva 564 MB de cálculo na placa, contra 112 MB).
  O driver AMD já estava atualizado (Adrenalin 26.8.1); o aviso "AMD driver is too old" do Ollama continua porque ele
  não tem ROCm para esse chip no Windows (NX-LLM-035).

### Testes desta versão
- 247/247 testes unitários (6 novos: aceite e revogação, versão dos termos igual na interface e no Python, textos
  nos 3 idiomas, todos os serviços externos citados na política, estado da otimização da placa).
- 32/32 verificações de conversa com qwen3:8b no Ollama 0.40.5 com a otimização: **média 6,3 s, mediana 5,6 s, máximo
  14,8 s** (v0.16.8: 14,0 s / 10,4 s / 48,4 s) e 7/7 na área de trabalho. A verificação "estudar JS" passou a aceitar
  também o NEXUS perguntando por qual tópico começar (antes só reconhecia "função" no singular).
- Interface conferida no modo de prévia: tela de aceite antes da saudação e sem fontes da internet, botão liberado só
  com as duas confirmações, Esc e clique fora não fecham, abas dos textos, seção nas Configurações, revogar e aceitar de
  novo, cartão da placa AMD com confirmação.

---

## v0.16.8 — Protótipo · 2026-10-15

**Mapa conceitual em volta do aro, download da voz no próprio aro, menus que encaixam nas metades da tela,
otimização de memória e "segurar para falar".**

### Novo
- **Mapa conceitual** (beta, Ctrl+7, borda direita ou "abre o mapa"): o aro do NEXUS no centro, girando, com as
  habilidades (rank e nível), as áreas de conhecimento e as memórias ligadas a ele por linhas; os cartões flutuam e
  orbitam devagar com o aro, puxando as linhas. Clique em um ponto para ver o que ele contém.
- **Download do reconhecimento de voz no aro**: na primeira vez que a voz é usada, os anéis ondulam e o núcleo mostra
  a porcentagem ("BAIXANDO A VOZ"); avisa quando termina ou se falhar.
- **Menus que encaixam**: arraste até a borda esquerda ou direita para ocupar aquela metade (com prévia), ou até o
  topo para a tela toda. **O aro acompanha o menu** enquanto ele é arrastado e fica acima dele; em tela cheia ele sai
  da frente e o menu ocupa tudo.
- **O NEXUS diz qual menu abriu** ("Abrindo as configurações") — opção em Configurações → Interface. A fala é a voz
  local do Windows: não usa a IA nem a API e não tem custo.
- **Ctrl+L** limpa o texto abaixo do aro na hora (configurável em Atalhos).
- **Segurar para falar** (beta): com a opção ligada, o microfone fica aberto enquanto a tecla de falar (Ctrl+Espaço)
  estiver apertada; ao soltar, ele para e envia.
- **Otimizar** (Configurações → Desempenho): liberar memória (RAM), limpar cache (e compactar o banco), limpar dados
  temporários (logs antigos e relatórios com mais de 30 dias) e limpar dados (conversas, notificações e registro de
  ações — com confirmação dupla e backup automático antes; memórias, conhecimento, agenda e tarefas ficam).
- **IA dupla (API + local)** aparece em Configurações → Inteligência como bloqueada ("em breve").

### Corrigido
- **O cursor do Windows ainda aparecia** (NX-UI-018): dentro dos menus e em botões desativados havia regras antigas com
  o cursor padrão. Agora tudo herda o cursor do NEXUS, exceto o que é clicável (cursor de clique) e o que é texto
  editável (barra de texto).

### Desempenho
- **Liberar memória** medido com o reconhecimento de voz carregado: o NEXUS usava **372 MB** e, depois de liberar,
  **3 MB em uso ativo** (368 MB devolvidos ao Windows; o modelo de voz volta sozinho, em ~1 s, quando a voz é usada).

### Testes desta versão
- 241/241 testes unitários (6 novos: medição de RAM do Windows, devolver memória, dados do mapa, abrir o mapa por
  voz, funções beta novas desligadas, nomes falados).
- 32/32 verificações de conversa com qwen3:8b (média 14,0 s, mediana 10,4 s) e 7/7 na área de trabalho.
- Interface conferida no modo de prévia: mapa conceitual, encaixe à esquerda/direita/tela toda com o aro seguindo o
  menu, download da voz no aro, Ctrl+L, fala do menu, otimização com confirmação dupla.

---

## v0.16.5 — Protótipo · 2026-10-15

**O NEXUS abre os menus para você — e o aro vai junto. Atalhos e cursor personalizáveis, tutorial narrado, tela
totalmente limpa e menus que maximizam.**

### Novo
- **A IA abre a interface**: "abre as configurações", "abre as configurações de voz", "mostra minhas conversas",
  "me leva para as configurações", "quero mudar a cor do aro", "personalizar os atalhos", "fecha isso" (PT/EN/ES).
  Pedidos assim são reconhecidos na hora, sem passar pela IA; frases mais livres ("Where can I change how NEXUS
  talks?") chegam à IA, que usa a nova ferramenta `open_interface` — e, se ela disser que abriu (ou que vai abrir)
  sem chamar a ferramenta, é obrigada a chamar (NX-LLM-038). Ao abrir um menu, **o
  aro diminui, voa até o topo e fica acima do menu esperando ordens**; ao fechar, volta para o centro. Funções beta
  desligadas não abrem e o NEXUS explica onde ligar.
- **Tutorial narrado na primeira vez**: o NEXUS fala e mostra, passo a passo, como falar com ele, onde ficam os menus
  (ou os atalhos, no modo somente atalhos), o guia F1 e as configurações. "Pular" ou Esc encerra; dá para rever
  pedindo "mostra o tutorial" ou em Configurações → Geral → Ver o tutorial.
- **Configurações → Atalhos**: todos os atalhos podem ser trocados (clique e aperte as teclas; Backspace remove;
  conflitos ficam em amarelo; "Restaurar os atalhos originais"). O guia F1 mostra os atalhos escolhidos.
- **Tela totalmente limpa** (extra do modo Somente atalhos + IA): **Ctrl+Shift+H** esconde tudo — nem o nome ao mexer o
  mouse, nem o cursor; só o aro. O mesmo atalho ou Esc traz de volta.
- **Texto abaixo do aro**: fica parado por padrão (arrastar ou o aro passear não leva o texto), com a opção de
  **acompanhar o aro**; pode ser **desligado**; some sozinho depois de um tempo aguardando (padrão 45 s); **Ctrl+I**
  mostra o estado e a conversa por alguns segundos, mesmo desligado ou na tela limpa.
- **Cursor do NEXUS**: anel, ponto ou seta na cor do aro (ou o do Windows), em 3 tamanhos. Texto que não dá para
  selecionar nem clicar não muda mais o cursor.
- **Maximizar menus**: arraste um menu até o topo da tela — aparece uma prévia transparente, como no Windows — e ele
  ocupa a tela; duplo clique no topo alterna; arrastar de novo restaura.
- O nome no canto agora é **N.E.X.U.S.**; o aro não mostra mais dica ao passar o mouse (o guia F1 explica).

### Corrigido
- **Comandos rápidos deixavam o aro "pensando"** (NX-UI-017): "repete", "pausa" e afins por texto ou voz marcavam o
  NEXUS como ocupado e o aro girava rápido sem parar.
- Os antigos atalhos extras Ctrl+H e Ctrl+J (conversas e notificações) deram lugar a Ctrl+2 e Ctrl+3 — e agora
  qualquer um pode ser personalizado.

### Desempenho
- **Abrir um menu pela voz é instantâneo**: o pedido é reconhecido localmente em **0,016 ms** em vez de esperar a IA —
  "quero mudar a cor do aro, me leva lá" levava **14,8 s** pela IA (e ela ainda respondia sem abrir); agora abre na
  hora.

### Testes desta versão
- 235/235 testes unitários (10 novos: pedidos de abrir/mudar algo do NEXUS em PT/EN/ES, o que continua indo para
  a IA, a ferramenta `open_interface` e funções beta, a rede de segurança, frases faladas, padrões novos).
- 32/32 verificações de conversa com qwen3:8b (nova: "quero mudar a cor do aro, me leva lá" abre Configurações >
  Interface) e 7/7 na área de trabalho. Tempo médio 15,4 s, mediana 12,3 s (v0.16.1: 12,1 s / 9,7 s — o prompt fixo
  ganhou a ferramenta e a regra de abrir a interface, ~150 tokens, e as rodadas variam ±2 s).
- Interface conferida no modo de prévia: aro acoplado acima dos menus, maximizar com prévia e restaurar, troca e
  conflito de atalhos, tela totalmente limpa, Ctrl+I, texto que some, texto fixo × acompanhando, cursor, tutorial.

---

## v0.16.1 — Protótipo · 2026-10-15

**Ajustes do novo visual: tela totalmente limpa, um menu por vez, dois modos de uso, avisos que não se acumulam e
inglês sem demora.**

### Novo
- **Tela totalmente limpa**: só o aro. O nome NEXUS e o significado aparecem apenas enquanto o mouse se mexe.
- **Modo de uso** (Configurações → Interface): **Computador** (menus para o mouse) ou **Somente atalhos + IA** — nada
  na tela; tudo por atalhos (F1 lista todos) e pela voz, inclusive minimizar (Ctrl+Shift+M), fechar (Ctrl+Shift+Q)
  e tela cheia/normal (F11).
- **Cada menu configurável**: barra superior, esquerda (modos da IA), direita (painel, trabalho, conversas) e embaixo
  (controles) podem **aparecer ao encostar o mouse**, ficar **sempre visíveis** ou ficar **desligados**.
- **Barra superior esvaziada**: só notificações, configurações e os botões da janela — e em tela cheia nem os botões
  da janela. Painel e habilidades foram para a borda direita; idioma e conexão ficam nas Configurações.
- **Um menu por vez**: abrir outro (por clique ou atalho) fecha o anterior, e **o mesmo atalho fecha** o menu que
  abriu (Ctrl+1 abre o painel, Ctrl+1 de novo fecha; vale também para Ctrl+, Ctrl+H, Ctrl+J e F1).
- **Menus móveis**: arraste qualquer painel pela parte de cima.
- **O aro se move sozinho** pela tela (pode desligar) e, **pensando, gira bem mais rápido até responder** — antes o
  estado "pensando" era trocado por "em espera" quando o reconhecimento de voz terminava.
- **Repouso**: depois de alguns minutos sem interação (padrão 3; 0 desliga), os textos somem e só o aro fica,
  passeando e brincando pela tela. Qualquer tecla, movimento do mouse ou fala acorda o NEXUS.
- **IA indisponível no próprio aro**: o núcleo fica vermelho, aparece "IA INDISPONÍVEL" e um botão **Como resolver**
  — o NEXUS fala os passos (a voz funciona sem a IA) e mostra o texto. Ele confere sozinho a cada 20 s e volta ao
  normal quando a IA responde.
- **Avisos**: o mesmo aviso não se acumula mais (mostra ×2, ×3), cada um sai no seu tempo (7 s; parado com o mouse
  em cima), no máximo 3 na tela, **✕** fecha um, **Ctrl+Shift+X** fecha todos e **mais** mostra uma explicação curta
  (ex.: por que o reconhecimento de voz está sendo baixado).
- Visual mais limpo dos painéis: fundos mais leves, bordas mais finas, uma "alça" no topo de cada painel.

### Corrigido
- **Os menus laterais demoravam a sair** (0,9 s) e às vezes **todos abriam juntos ao iniciar** (o NEXUS os mostrava
  por 3,5 s para você descobri-los). Agora saem em ~0,2 s e nada abre sozinho.
- **Vários menus abertos ao mesmo tempo** com atalhos ou cliques.

### Desempenho
- **Trocar de idioma não deixa mais a primeira resposta lenta** (NX-LLM-037): o idioma da resposta fazia parte do
  prompt fixo; trocar PT → EN mudava o começo do prompt e o "Hello" relia ~3 mil tokens. Agora o idioma vai junto de
  cada mensagem e o prompt fixo é igual nos três idiomas. Medido: **"Hello" depois de trocar para inglês 26,2 s →
  1,3 s** (leitura do prompt 25,7 s → 0,9 s).

### Testes desta versão
- 225/225 testes unitários (3 novos: prompt fixo igual nos três idiomas, idioma da resposta no contexto, padrões
  dos menus e do repouso).
- 31/31 verificações de conversa com qwen3:8b (média 12,1 s, mediana 9,7 s, máximo 22,8 s) e 7/7 na área de trabalho.
- Interface conferida no modo de prévia: tela limpa ao abrir, nome só com o mouse, atalhos que trocam e fecham
  menus, avisos (×3, máximo 3, "mais"), IA indisponível no aro, modo somente atalhos, menu fixo, repouso e arrastar.

---

## v0.16.0 — Protótipo · 2026-10-15

**Novo visual: uma tela limpa, só o NEXUS no centro — o resto nas bordas, nos atalhos e no guia (F1).**

### Novo
- **Tela principal redesenhada**: fundo azul-marinho com brilho no centro; um aro claro com marcações, arcos, anel
  pontilhado e anel segmentado em volta de um **núcleo azul brilhante** que "respira"; embaixo, o estado
  (**AGUARDANDO**, OUVINDO, PENSANDO…) e a última troca em duas linhas — a sua fala e a resposta do NEXUS.
- **"NEXUS" no canto superior esquerdo**, com o significado logo abaixo, menor (fonte larga Orbitron).
- Saíram da tela: telemetria nos cantos, molduras de HUD, miras vermelhas, linhas de varredura e o traço de pulso.
  O vermelho agora só aparece em erros e ações perigosas.
- **Guia (F1)**: um HUD por cima da tela que mostra o que cada borda faz (barra superior, modos da IA, trabalho e
  conversas, controles) e todos os atalhos. Fecha com F1, Esc ou clique. Também pelo "F1 · GUIA" no canto.
- **Atalhos para cada parte**: Ctrl+1 painel (agenda, tarefas, memória), Ctrl+2 conversas, Ctrl+3 notificações,
  Ctrl+4 biblioteca, Ctrl+5 área de trabalho, Ctrl+6 habilidades (os três últimos só com a função beta ligada),
  Ctrl+M texto ⇄ áudio — além dos que já existiam (Ctrl+, Ctrl+Shift+N, Ctrl+T, Ctrl+Espaço, Esc, F11).
- **Cores personalizáveis** (Configurações → Interface): aro, núcleo e fundo, com prévia ao vivo e "Cores originais".
  Todo o resto (barras, painéis, mensagens, botões) acompanha as cores escolhidas.
- "Marcações e brilho em volta do aro" (antes "HUD em volta do aro") desliga as marcações e o halo, para um aro simples.

### Desempenho
- **O aro dorme quando o NEXUS está quieto.** Até a v0.15.5 o laço de animação rodava 60 vezes por segundo para
  sempre, reescrevendo 3 variáveis CSS a cada quadro (o aro inteiro e o brilho eram recalculados) e redesenhando o
  traço de pulso. Medido na interface parada por 3 s: **62 → 0 quadros/s** e **217 → 0 escritas no DOM por segundo**.
  A "respiração" do núcleo virou uma animação CSS, e a voz e o microfone acordam o laço na hora (61 quadros/s
  enquanto há som).

### Testes desta versão
- 222/222 testes unitários (5 novos: todos os textos da interface nos 3 idiomas, textos do guia e das cores, cores
  padrão válidas).
- Interface conferida no modo de prévia (`index.html?mock`): tela parada, troca de duas linhas, guia, atalhos,
  modo texto, barras das bordas e troca de cores ao vivo.

---

## v0.15.5 — Protótipo · 2026-10-15

**Modo usuário, modo desenvolvedor e funções Beta — menos excesso na tela e respostas mais rápidas.**

### Novo
- **Configurações → Beta** com **Modo usuário** (padrão) e **Modo desenvolvedor**. O núcleo do NEXUS fica sempre
  ligado: voz, conversa, memória, agenda, lembretes, tarefas, base de conhecimento, conversas, arquivos, foco e
  emergência.
- **Funções beta**, desligadas no modo usuário até a versão final (cada uma pode ser ligada sabendo que pode ter
  bugs): **Área de trabalho** (a mais arriscada: roda comandos), **Biblioteca e modo podcast**, **Habilidades e
  níveis** e **Navegador** (abrir sites, pesquisar, tocar músicas). Desligada, a função some da tela **e** da lista
  de ferramentas da IA; se a IA tentar usá-la mesmo assim, a ferramenta recusa e explica onde ligar.
- **Modo desenvolvedor** liga tudo. As escolhas do modo usuário continuam guardadas para quando voltar.
- Desligar a Área de trabalho estando dentro de uma sai dela.

### Desempenho
- **Prompt menor no modo usuário**: 34 → 29 ferramentas, **~2.302 → ~1.994 tokens** de ferramentas (−308, ~8% do
  prompt fixo) — menos para ler quando o cache não serve e mais espaço para o histórico. Em 16 perguntas seguidas
  (`tests/bench_long_conversation.py`): **15,5 s → 14,4 s por resposta** no modo usuário; da 9ª pergunta em diante,
  **15,4 s → 13,3 s (−14%)**.
- **O gargalo real foi encontrado** (NX-LLM-035): o driver AMD desta máquina é antigo, então o Ollama usa Vulkan em vez
  de ROCm, e ali o Flash Attention lê o prompt a **75 tokens/s** — desligado, **265 tokens/s (3,5×)**, com a geração
  caindo de 33 para 23 tokens/s (medido com 5.500 tokens). É isso que faz cada resposta demorar 5–20 s para começar.
  Atualizar o driver AMD (libera o ROCm) ou usar `OLLAMA_FLASH_ATTENTION=0` resolve; documentado no catálogo.
- **Prompt do qwen3 montado pelo NEXUS** (experimental, desligado; NX-LLM-033): o template do Ollama põe
  " /no_think" e um bloco de pensamento vazio só no último turno, e os dois somem no turno seguinte — o cache quebra
  antes da última resposta. O NEXUS agora sabe escrever o prompt do qwen3 igual em todo turno (rota raw) e o cache
  passa a cobrir até o último token gerado, mas a média ficou dentro do ruído das medições (a pergunta anterior ainda
  muda, porque o bloco de contexto não volta ao histórico; devolvê-lo enchia a janela e ficou mais lento: 14,9 s contra
  13,5 s). Fica testado e pronto para quando valer a pena (`"llm_raw_prompt": true`).

### Corrigido
- **Lembrete marcado para depois de amanhã** (NX-LLM-036): depois de uma conversa longa, "me lembra amanhã às 10h" era
  salvo no dia 17 em vez do 16 — o calendário do contexto era uma lista sem rótulo e o modelo pegava o 2º item. Agora o
  contexto diz explicitamente qual é o dia de amanhã e o de depois de amanhã (reproduzido 3/3, corrigido 3/3).

### Testes desta versão
- 217/217 testes unitários (14 novos: funções beta e modos, ferramentas fora do prompt, calendário com "amanhã"
  rotulado, prompt do qwen3 montado pelo NEXUS e leitura de chamadas de ferramenta).
- 31/31 verificações de conversa com qwen3:8b no modo desenvolvedor (tempo médio 11,9 s, mediana 9,8 s, máximo
  27,3 s — igual à v0.15.1 dentro do ruído) e 7/7 na área de trabalho.

---

## v0.15.1 — Protótipo · 2026-10-15

**Só correções: respostas cortadas e confusas em conversas longas, e lentidão depois do título automático.**

### Corrigido
- **Respostas cortadas ou sem sentido em conversas longas** (NX-LLM-028): medido com qwen3:8b, as regras + 34
  ferramentas já ocupam **3.111 tokens**; com 12 trocas longas o prompt chegava a **7.746 de 8.192**, e numa
  conversa maior passava do limite — o Ollama então corta o **começo** (as regras). Foi isso que fez a pergunta do
  simulado parar em "d)" e "Letra A" virar registro de gasto. Agora o histórico enviado tem um orçamento (até
  2.500 tokens, sempre sobrando 1.200 para a resposta): as trocas mais antigas saem primeiro, respostas antigas
  longas são encurtadas e o histórico nunca começa por uma resposta sem a pergunta.
- **Resposta muito lenta depois de outra** (NX-LLM-029): o título automático e a extração de memórias rodavam com
  um prompt diferente e apagavam o único cache do Ollama — a mensagem seguinte reprocessava ~5 mil tokens
  (**38,5 s** só para ler o prompt). Agora essas tarefas reaproveitam exatamente o começo do prompt da conversa e
  só acrescentam o pedido no final, e o cache continua valendo.
- **Histórico que "deslizava" a cada mensagem** (NX-LLM-030): o começo do prompt mudava sempre e o cache do Ollama
  quase não servia. Agora a janela fica parada e, quando enche, pula de uma vez para a metade mais recente.
  Medido em 16 perguntas seguidas (`tests/bench_long_conversation.py`), da 9ª em diante: **19,2 s → 14,4 s por
  resposta (−25%)** e leitura do prompt **14,8 s → 10,5 s**.
- **Erros de API sempre diziam "inicie o Ollama"** (NX-LLM-031): agora cada caso tem sua mensagem — chave recusada,
  sem créditos/pagamento, limite de uso, modelo inexistente, provedor fora do ar, sem conexão, modo offline — e o
  motivo vai para `logs/nexus.log` (sem a chave), aparecendo também no "Relatar erro".
- **"Lê o livro X" respondia "lendo…" sem ler** (avaliação): a rede de segurança agora exige a ferramenta do livro.
- **Resposta em loop infinito** (NX-LLM-032): na avaliação, uma piada se repetiu até encher o contexto — **43 minutos**.
  Agora cada resposta tem um teto (~1.200 tokens) e um detector de repetição corta o loop na primeira frase completa.
- **"Letra A" virava o gasto de R$ 30** (a mesma falha do simulado, outra causa): o registro das últimas ações ia no
  contexto de toda mensagem; uma resposta curta e ambígua se agarrava a ele. Agora só entra quando a mensagem fala
  de algo que o NEXUS fez ("cancela o que você registrou", "o que você anotou").
- **Conversa temporária memorizava sozinha** (avaliação): "Eu tenho uma tartaruga chamada Jorge" foi guardado porque a
  própria IA chamou `remember`. Na conversa temporária isso agora só acontece com pedido explícito ("lembra que…").
- **Perfil Econômico** usava contexto 4.096, menor que as regras + ferramentas: passou para 6.144.
- Simulados: a IA não guarda mais perguntas/respostas como conhecimento ou notas (só `record_data` era proibido).
- Testes: o teste do arquivo de log trocava o tratador de erros do Python e escondia falhas dos testes seguintes.

### Testes desta versão
- 203/203 testes unitários (25 novos: orçamento e janela do histórico, prefixo das tarefas de fundo, erros de API,
  detector de loop, registro de ações, conversa temporária).
- 31/31 verificações de conversa com qwen3:8b (inclui simulado, piada, "lê o livro"); tempo médio 10,6 s,
  mediana 9,3 s, máximo 26,4 s (na rodada da v0.15.0 houve uma resposta de 43 min por loop).

---

## v0.15.0 — Protótipo · 2026-10-15

**Arquivos, Biblioteca com modo podcast, navegador, conexão automática e um visual mais suave.**

> A partir desta versão, o número reflete o peso da mudança: +0.0.1–0.0.2 para correções e otimizações,
> +0.0.5–0.0.8 para mudanças grandes com funções novas, e 0.(N+1).0 quando quase tudo muda. As partes mais
> difíceis deste pacote (modo treinamento, importar memórias de outras IAs, instalação mínima) vêm na 0.15.x.

### Arquivos (clipe no chat ou arrastar e soltar)
- Lê **PDF, DOCX, EPUB, TXT/MD/CSV/JSON e código, ZIP** (lista e lê os textos de dentro) e **imagens** (texto
  reconhecido pelo próprio Windows — sem download). Tudo no seu PC.
- Arquivos pequenos vão inteiros para a IA; grandes mandam o começo + os trechos que mais combinam com a pergunta
  (~7 mil caracteres, para caber no contexto). Na avaliação: "quanto é o aluguel no arquivo?" → valor do PDF.
- RAR fica para depois (precisa de uma ferramenta externa).

### Biblioteca e modo podcast (borda direita → *Biblioteca*)
- Adicione livros (PDF, EPUB, DOCX, TXT, MD — por botão ou arrastando), veja a lista com o progresso e leia na tela
  (leitor com páginas e tipografia de livro).
- **Podcast**: "lê o livro X" (ou o botão *Ouvir*) e o NEXUS lê em voz alta, parte por parte, continuando de onde
  você parou; pausar, continuar e parar pelo mini-player ou por voz ("pausa", "continua", "para").

### Navegador
- "Toca Bohemian Rhapsody no YouTube" abre o **primeiro vídeo encontrado** no navegador padrão (~0,8 s para achar);
  também abre links, pesquisas no Google e buscas no Spotify / YouTube Music.

### Conexão automática (novo padrão)
- **Automático** mede a internet a cada 5 min (latência + ~250 KB): sem internet → offline; lenta (> 1,2 s ou
  < 1,5 Mbit/s) → híbrido; rápida → **online primeiro** (consulta Wikipédia/notícias quando a base local não
  tem a resposta). Mede de novo quando uma consulta falha. O chip mostra "AUTO · ONLINE" e a medição.
  Neste PC: 180–240 ms, ~8 Mbit/s → online.

### Visual
- Mais suave e calmo: azul e vermelho menos saturados (vermelho → coral), cantos levemente arredondados, sombras
  suaves, transições mais lentas e fonte **Inter** no texto (mais legível).
- **Só o essencial é selecionável**: mensagens, o texto do leitor, conteúdo de arquivos e comandos. O NEXUS (aro,
  nome, barras, cartões) não seleciona mais — arrastar o aro não marca texto.

### Medido e descartado
- **Pré-checar "Nexus" com o Whisper tiny** (baixado com autorização): é 4–7× mais barato, mas perde o nome —
  8/8 em silêncio digital, 7/8 a 43 dB, 4/8 com ruído leve e 2/8 com ventilador; o small acerta 8/8 em todos.
  Ignorar o próprio nome é pior do que gastar processador, então toda fala usa o modelo completo. Economia de
  verdade aqui pede um detector de palavra-chave dedicado ("Nexus"), registrado para o futuro.

### Testes desta versão
- 178/178 testes unitários (17 novos: leitura de PDF/DOCX/EPUB, arquivo binário recusado, biblioteca, páginas e
  partes que terminam em frase, podcast encadeado salvando posição, navegador e modo offline, modo automático por
  qualidade da conexão, anexos grandes).
- Avaliação de conversa com qwen3:8b interrompida em 24/32 (o PC precisou ser desligado).

### Problema conhecido (corrigido na próxima versão, só de correções)
- Num simulado, depois de "Registra que gastei 30 reais em livros" na mesma conversa, a resposta "Letra A"
  foi tratada como registro do gasto em vez de ser corrigida. Passava na v0.14.

---

## v0.14.0 — Protótipo · 2026-10-14

**Leveza: menos trabalho em segundo plano, caches, troca IA local ⇄ API em um clique — e links falados pelo nome.**

### Corrigido
- **Links lidos letra por letra** (NX-VOZ-018): agora a voz fala só o nome do site ("Veja
  https://pt.wikipedia.org/wiki/Ada_Lovelace." → "Veja wikipedia."); a tela continua mostrando o link inteiro.

### Segundo plano
- **Fora de foco ou minimizado**: o aro, o HUD, o pulso e os indicadores param de animar (o aro deixa de ser
  desenhado — 0 quadros) e voltam ao focar. Opção em Configurações → Interface.
- **Só "Nexus…" vale com o NEXUS fora de foco** (Configurações → Microfone): conversas por perto e TV não viram
  comandos.
- **Minimizado com o microfone desligado**: depois de 10 min (ajustável) o Whisper sai da memória —
  **−258 MB de RAM** medidos — e volta sozinho (~1 s, do disco) quando a janela reaparece.

### Caches (medidos com `tests/bench_lightness.py`)
| | 1ª vez | repetido |
|---|---|---|
| Clima (São Paulo) | 5 155 ms | 0,07 ms (15 min) |
| Câmbio USD→BRL | 909 ms | 0,06 ms (1 h) |
| Frase falada repetida ("Executando em modo Direto.") | 72 ms | 0,01 ms |
| Busca na base de conhecimento | 0,4 ms | 0,003 ms (até a base mudar) |

Notícias também ficam 15 min e Wikipédia 1 dia; erros nunca são guardados.

### IA local ⇄ API
- Botão na borda esquerda e chave "IA LOCAL | API" em Configurações → Inteligência: cada lado guarda sua
  configuração (a chave da API continua criptografada). Na primeira vez, abre a escolha do provedor. Com API, quase
  toda a carga sai do PC (e as mensagens também).

### Medido e descartado
- **Pré-checar "Nexus" nos 2 primeiros segundos com o mesmo Whisper** não economiza: o Whisper sempre codifica uma
  janela fixa de 30 s, então a checagem custou 1,8 s contra 2,3 s da transcrição inteira, e o dobro quando "Nexus"
  foi dito; reduzir o decodificador (beam 1, sem tempos) poupou só ~10%. A pré-checagem fica pronta para o modelo
  **tiny** (~75 MB, muito mais leve) e só é usada se ele já estiver no PC — ele não é baixado sozinho.

### Testes desta versão
- 161/161 testes unitários (12 novos: links falados, caches online e da base, segundo plano, liberação do Whisper,
  troca local ⇄ API guardando as duas configurações).
- 28/28 verificações de conversa com qwen3:8b.

---

## v0.13.0 — Protótipo · 2026-10-14

**Habilidades com níveis e ranks, e as funções essenciais que faltavam: instância única, entrada rápida, backup
automático, chave de API criptografada e arquivo de log.**

### Habilidades
- O NEXUS e 8 áreas (Organização, Finanças, Programação, Estudo, Saúde, Conhecimento, Pesquisa, Voz) **sobem de
  nível com o uso**: cada assunto (+4 XP), cada ação real feita por ferramenta (+10 XP) e cada fala por voz (+3 XP).
- Ranks **E → D → C → B → A → S**. Selo "rank + nível" ao lado do nome na barra superior; clique para ver cada área
  com barra de progresso. Aviso discreto ao subir de nível (sem som no modo foco).
- **Custo zero**: o XP vem do que já aconteceu na resposta — nenhuma chamada extra à IA. Conversas temporárias não
  contam.

### Funções essenciais
- **Só um NEXUS aberto por vez**: abrir de novo mostra "O NEXUS já está aberto" (dois abertos disputavam microfone,
  banco de dados e IA — aconteceu durante o desenvolvimento).
- **Começar sem o formulário da landing**: na tela de boas-vindas, nome e profissão bastam.
- **Backup automático diário** (os 7 últimos ficam) + **Fazer backup agora**, **Restaurar** e **Abrir pasta** em
  Configurações → Dados. A restauração é aplicada ao reabrir, antes do banco abrir, e os dados atuais ficam guardados.
- **Chave de API criptografada** com a proteção do Windows (DPAPI, ligada ao seu usuário). Chaves salvas em texto
  pelas versões 0.10–0.12 são criptografadas na primeira abertura.
- **Arquivo de log** (`logs/nexus.log`, 3 × 1 MB): erros de segundo plano deixam rastro, e "Relatar erro" anexa o
  final do log.

### Testes desta versão
- 149/149 testes unitários (12 novos: curva de níveis e ranks, XP por tópico e ferramenta, aviso de nível, conversa
  temporária sem XP, backup válido, restauração recusa zip estranho, chave criptografada, log). Restauração testada
  de ponta a ponta (backup → mudança → reabrir → dado de volta). Instância única testada com dois processos.
- 28/28 verificações de conversa com qwen3:8b.

---

## v0.12.0 — Protótipo · 2026-10-14

**Modos offline/híbrido/online, perfis de desempenho medidos, requisitos e a resposta que sumia da tela.**

### Corrigido (da conversa real de 2026-10-14)
- **A resposta sumia da tela enquanto a voz continuava** (NX-UI-011): "vamos estudar JS" — a aula apareceu, foi
  falada e o texto foi trocado por "Registrei suas estratégias...". Todo texto antes de uma ferramenta era apagado
  como se fosse "vou verificar...". Agora só frases curtas (< 120 caracteres) somem; a resposta de verdade fica na
  tela e no histórico, e o resto é acrescentado.
- **Registrar "dados" sem pedido** (NX-LLM-027): aulas, explicações, planos e respostas de simulado são conversa,
  não dados. Quando você diz seu nome, ele vai para o perfil.

### Conexão (Configurações → Desempenho)
- **Offline**: nada sai do computador — IA, voz e memória locais; clima, notícias, câmbio, Wikipédia, calendário,
  provedores na nuvem, download de modelos de voz e até as fontes do Google ficam bloqueados.
- **Híbrido** (padrão): IA local + serviços online. **Online**: permite também IA na nuvem.
- Chip na barra superior mostra o modo (OFFLINE em âmbar).

### Perfis de desempenho (medidos com `tests/bench_hardware.py`)
| qwen3:8b na RX 6600 XT 8 GB | na placa | lê | escreve |
|---|---|---|---|
| contexto 4096 | 100% | 260 tok/s | 40 tok/s |
| contexto 8192 | 100% | 245 tok/s | 35 tok/s |
| contexto 12288 | 92% | 146 tok/s | 31 tok/s |
| contexto 16384 | 85% | 119 tok/s | 25 tok/s |
| só processador (Ryzen 5 5600G) | 0% | 47 tok/s | 7,5 tok/s |

Só ~6,2 GB dos 8 GB ficam livres para a IA; o que não cabe vai para o processador e fica até 2× mais lento.
- **Econômico**: contexto 4096, Whisper base, voz mais rápida, menos animações, IA liberada após 10 min.
- **Equilibrado** (padrão): contexto 8192 — o maior que cabe inteiro numa placa de 8 GB.
- **Força total**: tudo na placa, o maior contexto que **ainda cabe nela** (8192 em 8 GB, 32k em 12 GB+), mais
  histórico, Whisper medium e IA sempre carregada. Só aparece com 16 GB de RAM e placa de ~8 GB ou mais
  (detecção pela memória real da placa no registro do Windows; o WMI mostra no máximo 4 GB).
- Seção "Seu computador": processador, RAM, placa, maior contexto que cabe e se atende aos requisitos.

### Testes desta versão
- 137/137 testes unitários (8 novos: offline bloqueia serviços e IA na nuvem, IA local continua, tabela de memória
  da placa, perfis; 3 do texto mantido na tela).
- 28/28 verificações de conversa (nova: "vamos estudar JS" ensina e não registra dados) e 7/7 da área de trabalho
  com qwen3:8b.

---

## v0.11.0 — Protótipo · 2026-10-14

**Área de trabalho do NEXUS, modo foco e modo estudo.**

### Área de trabalho (borda direita → *Área de trabalho*)
- **Um espaço isolado por projeto**: pasta própria (`workspaces/<nome>` na pasta de dados), conversa própria e
  anotações do projeto. A conversa **não aparece** em Conversas nem na linha do tempo, e a IA não usa suas memórias,
  agenda nem outras conversas lá dentro (na avaliação ela não revelou a senha dita na conversa normal).
- **Liberdade total dentro da pasta**: a IA lista, lê, cria, edita, move e apaga arquivos e pastas sozinha.
  Fora dela, nada: caminhos com `..`, `C:\`, `~` ou a pasta interna `.nexus` são recusados.
- **Sem conflito consigo mesma**: cada escrita/edição/exclusão guarda a versão anterior (`.nexus/history`) e pode
  ser **desfeita** pelo painel; a edição só troca um trecho exato e único (não sobrescreve o que não leu).
- **Comandos só com a sua confirmação** (rodar código, instalar pacotes): diálogo "Permitir / Negar", aviso por voz,
  limite de 120 s, Esc ou 3 min sem resposta = negado.
- Tela própria: barra "ÁREA DE TRABALHO · nome" (abrir pasta, sair), painel de **arquivos** (clique para ver o
  conteúdo, com Copiar) e de **alterações** (desfazer cada uma ou a última).
- Rede de segurança nova (NX-WRK-001): se a IA diz que mudou um arquivo sem ter mudado, ou termina com "vou
  corrigir" sem corrigir, o pedido volta para ela agir.

### Modo foco e modo estudo (borda esquerda)
- **Modo foco**: sem distrações — lembretes só no sino (sem voz, pop-up ou som), HUD e pulso escondidos, aro mais
  calmo. Liga sozinho na área de trabalho (opcional em Configurações → Geral).
- **Modo Estudo**: a IA vira tutora — explica passo a passo com exemplo, confere se você entendeu com uma pergunta,
  usa a base de conhecimento e corrige simulados na hora.

### Testes desta versão
- 126/126 testes unitários (21 novos: 6 tentativas de sair da pasta bloqueadas, edição única, desfazer, comando
  negado/permitido, conversa separada, contexto sem dados pessoais, ferramentas certas em cada modo).
- `tests/workspace_eval.py` com qwen3:8b: 7/7 (criou `calc.py` e `test_calc.py`, pediu confirmação e rodou os testes,
  corrigiu o import que falhou, editou a função, não misturou com a conversa normal).
- 26/26 verificações de conversa normal com qwen3:8b (sem regressão fora da área de trabalho).

---

## v0.10.0 — Protótipo · 2026-10-14

**Notificações e lembretes automáticos, Configurações completas e qualquer provedor de IA.**

### Notificações e ações automáticas (com o NEXUS aberto, inclusive minimizado)
- **Lembretes com várias antecedências**: escolha entre 1 dia, 2 h, 1 h, 30, 15, 10 e 5 min (padrão: 1 h, 10 min e na
  hora). Vale para compromissos e tarefas com prazo. O aviso diz o tempo real que falta ("em 30 minutos" se o NEXUS
  abriu atrasado) e não avisa "em 1 hora" sobre algo criado 30 minutos antes. "Me lembra de beber água às 15h"
  continua avisando só na hora.
- **Central de notificações** (sino na barra superior, com contador): tudo que foi avisado fica listado.
- **Notificações do Windows**, **som de aviso** e **voz** (os lembretes são falados também no modo texto).
- **Horário silencioso** (ex.: 22:00 → 07:00): sem voz nem pop-up, só na central.
- **Resumo do dia** opcional (ex.: 08:00): o NEXUS fala seus compromissos e tarefas de hoje, uma vez por dia.

### Configurações completas (8 seções)
- **Geral**: idioma, falar a saudação, abrir em tela cheia, memória automática, título automático das conversas,
  quantas trocas a IA lembra.
- **Inteligência**: provedor (Ollama, LM Studio, OpenAI, Anthropic, Gemini, OpenRouter, Groq, DeepSeek, Mistral ou
  personalizado), endereço preenchido sozinho, **chave de API**, modelo, criatividade, contexto, modo e
  **Testar conexão**. Aviso em amarelo quando o provedor é na nuvem (os dados saem do computador).
- **Voz do NEXUS**: voz, efeito, velocidade, **volume**, testar.
- **Microfone**: **escolher o dispositivo** (NX-VOZ-002 resolvido, troca na hora), modelo do Whisper,
  **sensibilidade** e **pausa que encerra a fala**, palavra de ativação.
- **Notificações**, **Integrações**, **Interface** (HUD, legendas, reduzir animações, centralizar o aro) e
  **Dados** (abrir a pasta, relatar erro, limpar conversa, porta da ponte).

### UX/UI
- Atalhos: `Ctrl+,` Configurações · `Ctrl+Shift+N` nova conversa · `Ctrl+H` conversas · `Ctrl+J` notificações ·
  `Ctrl+T` transcrição.
- Configurações com navegação lateral, valores dos controles deslizantes visíveis e rodapé fixo com Salvar.

### Testes desta versão
- 105/105 testes unitários (12 novos: antecedências, tempo real restante, sem aviso retroativo, uma vez por
  antecedência, horário silencioso, central, resumo do dia, provedores).
- 26/26 verificações de conversa com qwen3:8b.
- Notificação do Windows testada neste PC.

---

## v0.9.0 — Protótipo · 2026-10-14

**Conversas com histórico e descrição, HUD novo, ícones do conhecimento e aro arrastável.**

### Conversas
- **Nova conversa** e **Conversas** na borda direita. Cada conversa ganha **título e descrição escritos pela IA** em
  segundo plano (depois da 1ª resposta e de novo na 4ª troca); dá para renomear (✎) e apagar (✕).
- Aba **Separadas**: cartões com título, descrição, data e número de mensagens; clique para **continuar** a conversa
  (o histórico dela volta a ser o contexto da IA).
- Aba **Todas · linha do tempo**: todas as mensagens em ordem cronológica, separadas por dia e por conversa;
  "Carregar mais antigas" para voltar no tempo.
- Só a conversa aberta vai para a IA (como as "sessões" da v0.5, NX-LLM-019); 2 h de silêncio abrem uma nova.
- Mensagens de versões anteriores foram separadas em conversas automaticamente (pausas de 2 h), com título provisório.
- Repetir usa a última resposta da conversa aberta.

### Visual (HUD)
- HUD próprio do NEXUS: cantos e réguas laterais da abertura sempre visíveis
  e discretos, linhas de varredura quase invisíveis e **telemetria ligada ao aro** (modelo e modo, hora e data,
  microfone e voz com indicadores).
- **Pulso**: uma linha sob o aro que oscila com a sua voz (vermelha) e a do NEXUS (azul).
- Custo de desempenho perto de zero: tudo é CSS estático, exceto o pulso (uma linha SVG atualizada junto com o aro).

### Outros
- **Ícones por área do conhecimento** (primeiros socorros, filosofia, finanças, programação, saúde, produtividade,
  anatomia, aprendido) nas etiquetas e na lista de documentos, nos 3 idiomas.
- **Aro arrastável** no modo áudio: arraste para mover (a posição é lembrada), duplo clique para centralizar.
  Base para, no futuro, reduzir o NEXUS só ao aro.

### Testes desta versão
- 93/93 testes unitários (12 novos: conversas, histórico isolado, reabrir, título, linha do tempo, silêncio de 2 h,
  apagar, limpeza das saudações, migração das mensagens antigas).
- 26/26 verificações de conversa com qwen3:8b (nova: título e descrição gerados pela IA — "Peso do coração humano").

---

## v0.8.1 — Protótipo · 2026-10-14

**Correção: abas do Painel sem rolagem.**

### Corrigido
- **Aba Saber (e Memória, Dados, Log) não rolava** (NX-UI-007, reaberto): a correção da v0.7 nunca funcionou. A regra
  `.tab-body { overflow-y: auto }` perdia para `.panel.grow { overflow: hidden }`, que tem prioridade maior no CSS;
  a verificação da v0.7 mediu o layout, mas não rolou a aba. Agora `.panel.tab-body` rola e foi verificado rolando com
  a roda do mouse até o último documento.

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

Prioridades definidas em 2026-10-14 (desempenho primeiro, para o NEXUS rodar em mais computadores):

### v0.14.0 — entregue (ver acima); pendente: pré-checagem com o Whisper tiny (precisa de download)
1. **Segundo plano / suspenso**: com a janela minimizada ou sem foco, pausar animações, HUD e o aro; liberar o
   Whisper e a IA da memória após um tempo sem uso (conforme o perfil).
2. **Escuta de baixo consumo para "Nexus"**: com a palavra de ativação (ou o NEXUS fora de foco), só o detector de voz
   roda; um trecho curto é checado com um modelo pequeno, e o Whisper completo só entra depois de ouvir "Nexus".
3. **Caches**: clima, notícias e câmbio por alguns minutos; buscas na base de conhecimento; áudio de frases
   repetidas (saudação, "Executando em modo…", lembretes).
4. **Troca rápida IA local ↔ API** em um clique, guardando as duas configurações (com API, quase toda a carga sai
   do PC).

### Novo visual (prioridade máxima, pedida em 2026-10-15)
- Entregue na v0.16.0: tela limpa, nome no canto, guia (F1), atalhos e cores personalizáveis.
- Entregue na v0.16.5: a IA abre menus e opções quando pedido, com o aro acoplado acima do menu.

### v0.15.x — Protótipo (depois do novo visual)
- Entregue na v0.15.5: Beta + modo usuário / desenvolvedor. A partir daqui, toda versão traz também melhorias
  medidas de desempenho.
- **Modo treinamento**: aprende enquanto está ativo; ao terminar, compara o que aprendeu com pesquisas online,
  mostrando o progresso no aro (anéis ondulando e a porcentagem no lugar de "NEXUS"), diz "Análise completa" e
  registra o resumo (aprendido, deixado de fora, % de concordância) na aba **Aprendizados**.
- **Importar memórias de outras IAs**: um prompt pronto para colar no ChatGPT, Claude etc.; memórias separadas por
  origem e um resumo unificado que vira a memória do NEXUS.
- **Instalação mínima** (só o idioma escolhido, conhecimento básico ou nenhum, com dupla confirmação) — junto com o
  instalador. RAR.

### v0.16.0 · mídia
- **Tocar música e controlar apps**: teclas de mídia do Windows (tocar, pausar, próxima), abrir apps e buscar por
  links de apps de música; verificar como o app pedido pelo usuário aceita comandos.

### v0.17.0 · manutenção
- Aviso de nova versão (GitHub) e, se aprovado o download do modelo, perfil "máxima inteligência".

### Versão final do protótipo
- **Instalador** (Inno Setup) e início automático com o Windows — reservado pelo usuário para a versão final do protótipo.

### Versões seguintes (a definir com o usuário)
Candidatos já levantados: perfil "máxima inteligência" (modelo maior, ex. 14B, dividido entre placa e RAM: mais
lento, porém melhor; medir antes), formulário real na landing (NX-INT-001),
fontes offline (NX-UI-001), e-mail e calendário com login (OAuth), cancelamento de eco, busca semântica com
embeddings, casa inteligente.
