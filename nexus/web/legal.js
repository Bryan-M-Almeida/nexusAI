// Terms of Use and Privacy Policy shown on first start and in Settings > Privacy & terms (v0.17.0).
// Version 1.2 - 2026-10-16 (1.1: MIT License; 1.2: new integrations, apps and media). Keep nexus/legal.py VERSION in sync when the texts change in substance.
window.LEGAL = {
  pt: {
    terms: `
<h3>Termos de Uso do N.E.X.U.S</h3>
<p class="legal-meta">Versão 1.2 · 16/10/2026 · Protótipo</p>
<h4>1. O que é o NEXUS</h4>
<p>O N.E.X.U.S é um assistente pessoal para Windows, em fase de <b>protótipo</b> (versões 0.x), criado para um hackathon. Ele roda no seu computador: conversa por texto e voz, organiza agenda, tarefas, lembretes, notas e dados, e consulta uma base de conhecimento local.</p>
<h4>2. Aceite</h4>
<p>Ao clicar em "Aceitar e continuar" você declara que leu e concorda com estes Termos e com a Política de Privacidade. Se não concordar, não use o NEXUS. Quando estes textos mudarem de forma relevante, o NEXUS pedirá um novo aceite.</p>
<h4>3. Quem pode usar</h4>
<p>O NEXUS é destinado a maiores de 18 anos. Menores de 18 anos só devem usá-lo com o consentimento e o acompanhamento de um responsável legal.</p>
<h4>4. Limites da inteligência artificial</h4>
<p>As respostas são geradas por um modelo de IA e <b>podem conter erros, omissões ou informações desatualizadas</b>. Confira informações importantes em fontes confiáveis. O NEXUS <b>não substitui</b> profissionais de saúde, direito, finanças, segurança ou qualquer outra área.</p>
<h4>5. Emergências e saúde</h4>
<p>O modo emergência mostra orientações de primeiros socorros de um manual, apenas como apoio. <b>Em uma emergência, ligue primeiro para os serviços de emergência</b> (Brasil: SAMU 192 / Bombeiros 193; EUA: 911; União Europeia: 112). Nenhuma informação do NEXUS é diagnóstico ou tratamento médico.</p>
<h4>6. Finanças</h4>
<p>Cálculos, cotações e explicações sobre dinheiro são informativos e não são recomendação de investimento.</p>
<h4>7. Ações no seu computador</h4>
<p>Algumas funções agem no seu computador: a Área de trabalho cria e edita arquivos numa pasta isolada e só executa comandos depois da sua confirmação; o Navegador abre sites; o "Otimizar" pode apagar dados que você escolher (com backup antes); o ajuste de placa AMD altera uma variável de ambiente do seu usuário e reinicia o Ollama. Você é responsável por confirmar essas ações.</p>
<h4>8. Funções beta</h4>
<p>Funções marcadas como beta estão em teste e podem falhar ou mudar. Elas só funcionam se você as ligar em Configurações › Beta (ou usar o modo desenvolvedor).</p>
<h4>9. Serviços de terceiros</h4>
<p>Algumas funções usam serviços de terceiros (por exemplo: clima, notícias, câmbio, Wikipédia, download do modelo de voz e, se você escolher, provedores de IA na nuvem). Cada serviço tem seus próprios termos e políticas, e o NEXUS não controla a disponibilidade nem o conteúdo deles. Os custos de uma API paga, se você configurar uma, são de sua responsabilidade.</p>
<h4>10. Uso adequado</h4>
<p>Não use o NEXUS para atividades ilegais, para violar direitos de outras pessoas ou para gerar conteúdo que cause dano.</p>
<h4>11. Licença e propriedade intelectual</h4>
<p>O código-fonte do NEXUS é software livre, distribuído sob a <b>Licença MIT</b> (arquivo LICENSE do repositório) — © 2026 Bryan Maciel de Almeida. Você pode usar, copiar, modificar, distribuir e até vender o código, desde que mantenha o aviso de direitos autorais e o texto da licença. A licença cobre o código; ela não autoriza apresentar uma versão modificada como se fosse o NEXUS oficial ou endossada pelo autor. Componentes de terceiros seguem as próprias licenças (lista no README). Os seus dados e conteúdos continuam sendo seus.</p>
<h4>12. Sem garantia e limitação de responsabilidade</h4>
<p>Por ser um protótipo, o NEXUS é fornecido "no estado em que se encontra", sem garantias de funcionamento contínuo, ausência de erros ou adequação a um fim específico. Na máxima extensão permitida pela lei, o autor não se responsabiliza por perdas de dados, danos ou prejuízos decorrentes do uso. Faça backups (o NEXUS faz um automático por dia).</p>
<h4>13. Encerramento</h4>
<p>Você pode parar de usar o NEXUS a qualquer momento, apagar seus dados (Configurações › Dados e Desempenho › Otimizar) e desinstalá-lo.</p>
<h4>14. Lei aplicável</h4>
<p>Estes Termos seguem a legislação brasileira, incluindo o Código de Defesa do Consumidor e a Lei Geral de Proteção de Dados (Lei nº 13.709/2018), sem prejuízo dos direitos garantidos pela lei do seu país.</p>
<h4>15. Contato</h4>
<p>Dúvidas, pedidos e relatos de problemas: pelo repositório do projeto no GitHub (github.com/Bryan-M-Almeida/nexusAI), na seção Issues.</p>`,
    privacy: `
<h3>Política de Privacidade do N.E.X.U.S</h3>
<p class="legal-meta">Versão 1.2 · 16/10/2026</p>
<h4>1. Resumo</h4>
<p>O NEXUS funciona <b>no seu computador</b>. Não há conta, cadastro, anúncios nem telemetria: o autor do NEXUS <b>não recebe</b> seus dados. Algumas funções, que você controla, enviam informações a serviços de terceiros, descritas abaixo.</p>
<h4>2. Quais dados o NEXUS guarda</h4>
<ul>
<li><b>Perfil:</b> nome, profissão, rotina, interesses e objetivos que você informar.</li>
<li><b>Conversas e memórias:</b> mensagens, títulos das conversas e fatos que você pedir para lembrar (que podem incluir informações sensíveis, como saúde, se você as disser).</li>
<li><b>Organização:</b> agenda, tarefas, lembretes, notas, registros (por exemplo, gastos), notificações e o registro de ações.</li>
<li><b>Conteúdos:</b> base de conhecimento, livros da biblioteca, arquivos anexados e arquivos da Área de trabalho.</li>
<li><b>Configurações:</b> preferências e, se você usar uma API, a chave dela — guardada <b>criptografada</b> pelo Windows (DPAPI), legível só no seu usuário deste computador.</li>
<li><b>Registros técnicos:</b> log de erros (sem chaves de API), relatórios que você pedir e backups.</li>
</ul>
<p>Tudo isso fica em <b>%LOCALAPPDATA%\\NEXUS</b>, no seu computador.</p>
<h4>3. Microfone e voz</h4>
<p>O reconhecimento de voz (Whisper) e a fala (vozes do Windows) funcionam <b>localmente</b>. O áudio do microfone é processado na memória e <b>não é gravado em arquivo</b> nem enviado à internet. O microfone só é aberto depois do aceite destes termos, no modo áudio, e você pode silenciá-lo a qualquer momento.</p>
<h4>4. O que sai do computador (e quando)</h4>
<ul>
<li><b>IA:</b> com a IA local (Ollama/LM Studio), nada sai. Se você escolher um provedor na nuvem (OpenAI, Anthropic, Google, etc.), suas mensagens e o contexto necessário (por exemplo, trechos de memórias, agenda ou arquivos anexados) são enviados a esse provedor, sob a política dele.</li>
<li><b>Integrações:</b> clima, qualidade do ar e horário de outras cidades (Open-Meteo: a cidade), notícias (Google Notícias: o tema), câmbio (Frankfurter: as moedas), criptomoedas (CoinGecko: a moeda), tradução (MyMemory: o texto a traduzir), feriados (Nager.Date: o país), Wikipédia (o termo pesquisado), o calendário ICS que você informar e as integrações que você mesmo adicionar (o endereço que você escolheu recebe o que você pediu). Cada uma só é usada quando uma mensagem precisa dela, a resposta fica guardada no computador por um tempo, e todas podem ser desligadas em Configurações › Integrações ou com o modo offline. A calculadora e o conversor de unidades funcionam sem internet.</li>
<li><b>Aplicativos e mídia (beta):</b> para abrir aplicativos pelo nome, o NEXUS lê a lista do menu Iniciar; para controlar a música, lê o título e o artista do que está tocando nos controles de mídia do Windows. Essas informações ficam no computador e não são enviadas a ninguém.</li>
<li><b>Conexão automática:</b> para escolher entre offline, híbrido e online, o NEXUS mede a internet com pedidos a servidores do Google e da Cloudflare, sem enviar dados pessoais.</li>
<li><b>Downloads:</b> o modelo de voz é baixado uma vez do Hugging Face; as fontes da interface podem ser carregadas do Google Fonts (não no modo offline).</li>
<li><b>Navegador:</b> quando você pede para abrir um site, pesquisar ou tocar uma música, o seu navegador acessa esses sites (Google, YouTube, etc.).</li>
</ul>
<p>Em qualquer uma dessas comunicações, o serviço recebe também dados técnicos normais da internet, como o seu endereço IP. <b>Nada disso acontece antes do aceite destes termos.</b></p>
<h4>5. Para que os dados são usados</h4>
<p>Somente para o NEXUS funcionar para você: responder, lembrar, organizar e personalizar. Os dados não são vendidos, compartilhados para publicidade ou usados para treinar modelos pelo autor.</p>
<h4>6. Bases legais (LGPD)</h4>
<p>O tratamento local acontece por iniciativa sua, no seu próprio computador. O envio a serviços de terceiros ocorre com o seu <b>consentimento</b> (art. 7º, I, e art. 11, I, da LGPD), dado ao aceitar estes termos e ao ligar cada função; você pode revogá-lo desligando a função ou o aceite.</p>
<h4>7. Seus direitos</h4>
<p>Você pode, a qualquer momento: <b>acessar e exportar</b> seus dados (Configurações › Dados › Backup e a pasta de dados); <b>corrigir</b> perfil, memórias e registros; <b>apagar</b> conversas e outros dados (Configurações › Desempenho › Otimizar e o painel); <b>revogar o consentimento</b> (Configurações › Privacidade e termos); e desinstalar o NEXUS e apagar a pasta de dados.</p>
<h4>8. Segurança</h4>
<p>Os dados ficam protegidos pela conta do Windows; a chave de API é criptografada; os comandos da Área de trabalho exigem confirmação. Recomendamos proteger o computador com senha. Os backups ficam na mesma pasta e devem ser guardados com cuidado se você copiá-los.</p>
<h4>9. Retenção</h4>
<p>Os dados ficam até você apagá-los. Backups automáticos guardam os 7 últimos dias; logs antigos e relatórios podem ser apagados em Otimizar.</p>
<h4>10. Crianças e adolescentes</h4>
<p>O NEXUS não é destinado a menores de 18 anos sem o acompanhamento de um responsável, que deve consentir com o uso.</p>
<h4>11. Alterações</h4>
<p>Se esta política mudar de forma relevante, o NEXUS mostrará a nova versão e pedirá um novo aceite.</p>
<h4>12. Contato</h4>
<p>Pedidos sobre privacidade: pelo repositório do projeto no GitHub (github.com/Bryan-M-Almeida/nexusAI), na seção Issues. Como o NEXUS não envia seus dados ao autor, a maior parte dos pedidos pode ser atendida diretamente nas Configurações.</p>`,
  },
  en: {
    terms: `
<h3>N.E.X.U.S Terms of Use</h3>
<p class="legal-meta">Version 1.2 · 2026-10-16 · Prototype</p>
<h4>1. What NEXUS is</h4>
<p>N.E.X.U.S is a personal assistant for Windows at <b>prototype</b> stage (0.x versions), built for a hackathon. It runs on your computer: it talks by text and voice, organizes your schedule, tasks, reminders, notes and data, and uses a local knowledge base.</p>
<h4>2. Acceptance</h4>
<p>By clicking "Accept and continue" you confirm that you have read and agree to these Terms and the Privacy Policy. If you don't agree, don't use NEXUS. When these texts change in a relevant way, NEXUS will ask you to accept again.</p>
<h4>3. Who may use it</h4>
<p>NEXUS is intended for people aged 18 or over. Minors should only use it with the consent and supervision of a parent or legal guardian.</p>
<h4>4. Limits of artificial intelligence</h4>
<p>Answers are generated by an AI model and <b>may contain errors, omissions or outdated information</b>. Check important information with reliable sources. NEXUS <b>does not replace</b> health, legal, financial, safety or any other professionals.</p>
<h4>5. Emergencies and health</h4>
<p>Emergency mode shows first-aid guidance from a manual, as support only. <b>In an emergency, call emergency services first</b> (Brazil: SAMU 192 / Fire 193; US: 911; European Union: 112). Nothing from NEXUS is a medical diagnosis or treatment.</p>
<h4>6. Finance</h4>
<p>Calculations, exchange rates and explanations about money are informative and are not investment advice.</p>
<h4>7. Actions on your computer</h4>
<p>Some features act on your computer: the Workspace creates and edits files in an isolated folder and only runs commands after you confirm; the Browser opens websites; "Optimize" can delete data you choose (with a backup first); the AMD card tuning changes an environment variable of your user and restarts Ollama. You are responsible for confirming these actions.</p>
<h4>8. Beta features</h4>
<p>Features marked as beta are being tested and may fail or change. They only work if you turn them on in Settings › Beta (or use developer mode).</p>
<h4>9. Third-party services</h4>
<p>Some features use third-party services (for example: weather, news, exchange rates, Wikipedia, the voice model download and, if you choose, cloud AI providers). Each service has its own terms and policies, and NEXUS doesn't control their availability or content. The costs of a paid API, if you set one up, are your responsibility.</p>
<h4>10. Proper use</h4>
<p>Don't use NEXUS for illegal activities, to violate other people's rights or to create harmful content.</p>
<h4>11. License and intellectual property</h4>
<p>The NEXUS source code is free software, distributed under the <b>MIT License</b> (the repository's LICENSE file) — © 2026 Bryan Maciel de Almeida. You may use, copy, modify, distribute and even sell the code, as long as you keep the copyright notice and the license text. The license covers the code; it doesn't allow presenting a modified version as the official NEXUS or as endorsed by the author. Third-party components follow their own licenses (listed in the README). Your data and content remain yours.</p>
<h4>12. No warranty and limitation of liability</h4>
<p>As a prototype, NEXUS is provided "as is", without warranties of uninterrupted operation, absence of errors or fitness for a particular purpose. To the maximum extent permitted by law, the author is not liable for data loss, damage or losses arising from its use. Keep backups (NEXUS makes an automatic one every day).</p>
<h4>13. Ending use</h4>
<p>You can stop using NEXUS at any time, delete your data (Settings › Data and Performance › Optimize) and uninstall it.</p>
<h4>14. Applicable law</h4>
<p>These Terms are governed by Brazilian law, including the Consumer Protection Code and the General Data Protection Law (Law 13,709/2018), without prejudice to the rights granted by the law of your country.</p>
<h4>15. Contact</h4>
<p>Questions, requests and problem reports: through the project's GitHub repository (github.com/Bryan-M-Almeida/nexusAI), in the Issues section.</p>`,
    privacy: `
<h3>N.E.X.U.S Privacy Policy</h3>
<p class="legal-meta">Version 1.2 · 2026-10-16</p>
<h4>1. Summary</h4>
<p>NEXUS works <b>on your computer</b>. There is no account, sign-up, ads or telemetry: the author of NEXUS <b>does not receive</b> your data. Some features, which you control, send information to third-party services, described below.</p>
<h4>2. What NEXUS stores</h4>
<ul>
<li><b>Profile:</b> name, profession, routine, interests and goals you provide.</li>
<li><b>Conversations and memories:</b> messages, conversation titles and facts you ask it to remember (which may include sensitive information, such as health, if you say it).</li>
<li><b>Organization:</b> schedule, tasks, reminders, notes, records (for example, expenses), notifications and the action log.</li>
<li><b>Content:</b> knowledge base, library books, attached files and Workspace files.</li>
<li><b>Settings:</b> preferences and, if you use an API, its key — stored <b>encrypted</b> by Windows (DPAPI), readable only by your user on this computer.</li>
<li><b>Technical records:</b> error log (without API keys), reports you ask for and backups.</li>
</ul>
<p>All of it is in <b>%LOCALAPPDATA%\\NEXUS</b>, on your computer.</p>
<h4>3. Microphone and voice</h4>
<p>Speech recognition (Whisper) and speech (Windows voices) run <b>locally</b>. Microphone audio is processed in memory and is <b>not saved to a file</b> or sent to the internet. The microphone only opens after you accept these terms, in audio mode, and you can mute it at any time.</p>
<h4>4. What leaves the computer (and when)</h4>
<ul>
<li><b>AI:</b> with local AI (Ollama/LM Studio), nothing leaves. If you choose a cloud provider (OpenAI, Anthropic, Google, etc.), your messages and the context needed (for example, parts of memories, schedule or attached files) are sent to that provider, under its policy.</li>
<li><b>Integrations:</b> weather, air quality and the time in other cities (Open-Meteo: the city), news (Google News: the topic), exchange rates (Frankfurter: the currencies), crypto prices (CoinGecko: the currency), translation (MyMemory: the text to translate), public holidays (Nager.Date: the country), Wikipedia (the search term), the ICS calendar you provide and the integrations you add yourself (the address you chose receives what you asked). Each one is only used when a message needs it, the answer is kept on the computer for a while, and all can be turned off in Settings › Integrations or with offline mode. The calculator and unit converter work without internet.</li>
<li><b>Apps and media (beta):</b> to open apps by name, NEXUS reads the Start menu list; to control music, it reads the title and artist of what is playing from Windows' media controls. This information stays on the computer and is not sent to anyone.</li>
<li><b>Automatic connection:</b> to choose between offline, hybrid and online, NEXUS measures the internet with requests to Google and Cloudflare servers, without sending personal data.</li>
<li><b>Downloads:</b> the voice model is downloaded once from Hugging Face; interface fonts may be loaded from Google Fonts (not in offline mode).</li>
<li><b>Browser:</b> when you ask to open a site, search or play a song, your browser visits those sites (Google, YouTube, etc.).</li>
</ul>
<p>In any of these communications the service also receives normal internet technical data, such as your IP address. <b>None of this happens before you accept these terms.</b></p>
<h4>5. What the data is used for</h4>
<p>Only to make NEXUS work for you: answering, remembering, organizing and personalizing. The author doesn't sell the data, share it for advertising or use it to train models.</p>
<h4>6. Legal bases (LGPD / GDPR)</h4>
<p>Local processing happens at your own initiative, on your own computer. Sending data to third-party services is based on your <b>consent</b>, given when accepting these terms and when turning each feature on; you can withdraw it by turning the feature or the acceptance off.</p>
<h4>7. Your rights</h4>
<p>At any time you can: <b>access and export</b> your data (Settings › Data › Backup and the data folder); <b>correct</b> profile, memories and records; <b>delete</b> conversations and other data (Settings › Performance › Optimize and the panel); <b>withdraw consent</b> (Settings › Privacy & terms); and uninstall NEXUS and delete the data folder.</p>
<h4>8. Security</h4>
<p>The data is protected by your Windows account; the API key is encrypted; Workspace commands require confirmation. We recommend protecting the computer with a password. Backups are in the same folder and should be kept carefully if you copy them.</p>
<h4>9. Retention</h4>
<p>Data stays until you delete it. Automatic backups keep the last 7 days; old logs and reports can be deleted in Optimize.</p>
<h4>10. Children and teenagers</h4>
<p>NEXUS is not intended for people under 18 without the supervision of a parent or guardian, who must consent to its use.</p>
<h4>11. Changes</h4>
<p>If this policy changes in a relevant way, NEXUS will show the new version and ask you to accept again.</p>
<h4>12. Contact</h4>
<p>Privacy requests: through the project's GitHub repository (github.com/Bryan-M-Almeida/nexusAI), in the Issues section. Since NEXUS doesn't send your data to the author, most requests can be handled directly in Settings.</p>`,
  },
  es: {
    terms: `
<h3>Términos de Uso de N.E.X.U.S</h3>
<p class="legal-meta">Versión 1.2 · 16/10/2026 · Prototipo</p>
<h4>1. Qué es NEXUS</h4>
<p>N.E.X.U.S es un asistente personal para Windows en fase de <b>prototipo</b> (versiones 0.x), creado para un hackathon. Funciona en tu ordenador: conversa por texto y voz, organiza agenda, tareas, recordatorios, notas y datos, y usa una base de conocimiento local.</p>
<h4>2. Aceptación</h4>
<p>Al pulsar "Aceptar y continuar" declaras que has leído y aceptas estos Términos y la Política de Privacidad. Si no estás de acuerdo, no uses NEXUS. Cuando estos textos cambien de forma relevante, NEXUS pedirá una nueva aceptación.</p>
<h4>3. Quién puede usarlo</h4>
<p>NEXUS está destinado a mayores de 18 años. Los menores solo deben usarlo con el consentimiento y la supervisión de un tutor legal.</p>
<h4>4. Límites de la inteligencia artificial</h4>
<p>Las respuestas las genera un modelo de IA y <b>pueden contener errores, omisiones o información desactualizada</b>. Comprueba la información importante en fuentes fiables. NEXUS <b>no sustituye</b> a profesionales de salud, derecho, finanzas, seguridad ni de ningún otro ámbito.</p>
<h4>5. Emergencias y salud</h4>
<p>El modo emergencia muestra orientaciones de primeros auxilios de un manual, solo como apoyo. <b>En una emergencia, llama primero a los servicios de emergencia</b> (Brasil: SAMU 192 / Bomberos 193; EE. UU.: 911; Unión Europea: 112). Nada de NEXUS es un diagnóstico ni un tratamiento médico.</p>
<h4>6. Finanzas</h4>
<p>Los cálculos, cotizaciones y explicaciones sobre dinero son informativos y no constituyen recomendaciones de inversión.</p>
<h4>7. Acciones en tu ordenador</h4>
<p>Algunas funciones actúan en tu ordenador: el Área de trabajo crea y edita archivos en una carpeta aislada y solo ejecuta comandos tras tu confirmación; el Navegador abre sitios web; "Optimizar" puede borrar los datos que elijas (con copia de seguridad antes); el ajuste para tarjetas AMD cambia una variable de entorno de tu usuario y reinicia Ollama. Eres responsable de confirmar estas acciones.</p>
<h4>8. Funciones beta</h4>
<p>Las funciones marcadas como beta están en prueba y pueden fallar o cambiar. Solo funcionan si las activas en Configuración › Beta (o usas el modo desarrollador).</p>
<h4>9. Servicios de terceros</h4>
<p>Algunas funciones usan servicios de terceros (por ejemplo: clima, noticias, cambio de divisas, Wikipedia, la descarga del modelo de voz y, si lo eliges, proveedores de IA en la nube). Cada servicio tiene sus propios términos y políticas, y NEXUS no controla su disponibilidad ni su contenido. Los costes de una API de pago, si la configuras, son responsabilidad tuya.</p>
<h4>10. Uso adecuado</h4>
<p>No uses NEXUS para actividades ilegales, para vulnerar derechos de otras personas ni para generar contenido dañino.</p>
<h4>11. Licencia y propiedad intelectual</h4>
<p>El código fuente de NEXUS es software libre, distribuido bajo la <b>Licencia MIT</b> (archivo LICENSE del repositorio) — © 2026 Bryan Maciel de Almeida. Puedes usar, copiar, modificar, distribuir e incluso vender el código, siempre que mantengas el aviso de derechos de autor y el texto de la licencia. La licencia cubre el código; no permite presentar una versión modificada como si fuera el NEXUS oficial o respaldada por el autor. Los componentes de terceros siguen sus propias licencias (lista en el README). Tus datos y contenidos siguen siendo tuyos.</p>
<h4>12. Sin garantía y limitación de responsabilidad</h4>
<p>Por ser un prototipo, NEXUS se ofrece "tal cual", sin garantías de funcionamiento continuo, ausencia de errores o idoneidad para un fin concreto. En la máxima medida permitida por la ley, el autor no se responsabiliza de pérdidas de datos, daños o perjuicios derivados del uso. Haz copias de seguridad (NEXUS hace una automática cada día).</p>
<h4>13. Fin del uso</h4>
<p>Puedes dejar de usar NEXUS en cualquier momento, borrar tus datos (Configuración › Datos y Rendimiento › Optimizar) y desinstalarlo.</p>
<h4>14. Ley aplicable</h4>
<p>Estos Términos se rigen por la legislación brasileña, incluidos el Código de Defensa del Consumidor y la Ley General de Protección de Datos (Ley 13.709/2018), sin perjuicio de los derechos que te garantice la ley de tu país.</p>
<h4>15. Contacto</h4>
<p>Dudas, solicitudes y reportes de problemas: en el repositorio del proyecto en GitHub (github.com/Bryan-M-Almeida/nexusAI), sección Issues.</p>`,
    privacy: `
<h3>Política de Privacidad de N.E.X.U.S</h3>
<p class="legal-meta">Versión 1.2 · 16/10/2026</p>
<h4>1. Resumen</h4>
<p>NEXUS funciona <b>en tu ordenador</b>. No hay cuenta, registro, anuncios ni telemetría: el autor de NEXUS <b>no recibe</b> tus datos. Algunas funciones, que tú controlas, envían información a servicios de terceros, descritos abajo.</p>
<h4>2. Qué datos guarda NEXUS</h4>
<ul>
<li><b>Perfil:</b> nombre, profesión, rutina, intereses y objetivos que indiques.</li>
<li><b>Conversaciones y recuerdos:</b> mensajes, títulos de conversaciones y hechos que pidas recordar (que pueden incluir información sensible, como de salud, si la dices).</li>
<li><b>Organización:</b> agenda, tareas, recordatorios, notas, registros (por ejemplo, gastos), notificaciones y el registro de acciones.</li>
<li><b>Contenidos:</b> base de conocimiento, libros de la biblioteca, archivos adjuntos y archivos del Área de trabajo.</li>
<li><b>Configuración:</b> preferencias y, si usas una API, su clave — guardada <b>cifrada</b> por Windows (DPAPI), legible solo por tu usuario en este ordenador.</li>
<li><b>Registros técnicos:</b> registro de errores (sin claves de API), informes que solicites y copias de seguridad.</li>
</ul>
<p>Todo queda en <b>%LOCALAPPDATA%\\NEXUS</b>, en tu ordenador.</p>
<h4>3. Micrófono y voz</h4>
<p>El reconocimiento de voz (Whisper) y el habla (voces de Windows) funcionan <b>localmente</b>. El audio del micrófono se procesa en memoria y <b>no se guarda en archivos</b> ni se envía a internet. El micrófono solo se abre tras aceptar estos términos, en modo audio, y puedes silenciarlo en cualquier momento.</p>
<h4>4. Qué sale del ordenador (y cuándo)</h4>
<ul>
<li><b>IA:</b> con la IA local (Ollama/LM Studio), no sale nada. Si eliges un proveedor en la nube (OpenAI, Anthropic, Google, etc.), tus mensajes y el contexto necesario (por ejemplo, partes de recuerdos, agenda o archivos adjuntos) se envían a ese proveedor, bajo su política.</li>
<li><b>Integraciones:</b> clima, calidad del aire y hora de otras ciudades (Open-Meteo: la ciudad), noticias (Google Noticias: el tema), divisas (Frankfurter: las monedas), criptomonedas (CoinGecko: la moneda), traducción (MyMemory: el texto a traducir), festivos (Nager.Date: el país), Wikipedia (el término buscado), el calendario ICS que indiques y las integraciones que tú mismo añadas (la dirección que elegiste recibe lo que pediste). Cada una solo se usa cuando un mensaje la necesita, la respuesta se guarda en el equipo un tiempo, y todas se pueden desactivar en Configuración › Integraciones o con el modo sin conexión. La calculadora y el conversor de unidades funcionan sin internet.</li>
<li><b>Aplicaciones y multimedia (beta):</b> para abrir aplicaciones por nombre, NEXUS lee la lista del menú Inicio; para controlar la música, lee el título y el artista de lo que suena en los controles multimedia de Windows. Esta información se queda en el equipo y no se envía a nadie.</li>
<li><b>Conexión automática:</b> para elegir entre sin conexión, híbrido y en línea, NEXUS mide internet con peticiones a servidores de Google y Cloudflare, sin enviar datos personales.</li>
<li><b>Descargas:</b> el modelo de voz se descarga una vez de Hugging Face; las fuentes de la interfaz pueden cargarse de Google Fonts (no en modo sin conexión).</li>
<li><b>Navegador:</b> cuando pides abrir un sitio, buscar o poner una canción, tu navegador accede a esos sitios (Google, YouTube, etc.).</li>
</ul>
<p>En cualquiera de estas comunicaciones el servicio recibe también datos técnicos normales de internet, como tu dirección IP. <b>Nada de esto ocurre antes de aceptar estos términos.</b></p>
<h4>5. Para qué se usan los datos</h4>
<p>Solo para que NEXUS funcione para ti: responder, recordar, organizar y personalizar. El autor no vende los datos, no los comparte para publicidad ni los usa para entrenar modelos.</p>
<h4>6. Bases legales (LGPD / RGPD)</h4>
<p>El tratamiento local ocurre por tu propia iniciativa, en tu propio ordenador. El envío a servicios de terceros se basa en tu <b>consentimiento</b>, dado al aceptar estos términos y al activar cada función; puedes retirarlo desactivando la función o la aceptación.</p>
<h4>7. Tus derechos</h4>
<p>En cualquier momento puedes: <b>acceder y exportar</b> tus datos (Configuración › Datos › Copia de seguridad y la carpeta de datos); <b>corregir</b> perfil, recuerdos y registros; <b>borrar</b> conversaciones y otros datos (Configuración › Rendimiento › Optimizar y el panel); <b>retirar el consentimiento</b> (Configuración › Privacidad y términos); y desinstalar NEXUS y borrar la carpeta de datos.</p>
<h4>8. Seguridad</h4>
<p>Los datos están protegidos por tu cuenta de Windows; la clave de API está cifrada; los comandos del Área de trabajo requieren confirmación. Recomendamos proteger el ordenador con contraseña. Las copias de seguridad están en la misma carpeta y deben guardarse con cuidado si las copias.</p>
<h4>9. Conservación</h4>
<p>Los datos se conservan hasta que los borres. Las copias automáticas guardan los últimos 7 días; los registros antiguos y los informes se pueden borrar en Optimizar.</p>
<h4>10. Niños y adolescentes</h4>
<p>NEXUS no está destinado a menores de 18 años sin la supervisión de un tutor, que debe consentir su uso.</p>
<h4>11. Cambios</h4>
<p>Si esta política cambia de forma relevante, NEXUS mostrará la nueva versión y pedirá una nueva aceptación.</p>
<h4>12. Contacto</h4>
<p>Solicitudes sobre privacidad: en el repositorio del proyecto en GitHub (github.com/Bryan-M-Almeida/nexusAI), sección Issues. Como NEXUS no envía tus datos al autor, la mayoría de las solicitudes se pueden atender directamente en la Configuración.</p>`,
  },
};
