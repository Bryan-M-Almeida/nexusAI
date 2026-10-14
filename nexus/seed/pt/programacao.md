# Fundamentos de Programação
categoria: Programação

Referência rápida de conceitos, ferramentas e boas práticas de desenvolvimento de software.

## Conceitos básicos
- Variável: nome que guarda um valor. Tipos comuns: inteiro, decimal (float), texto (string), booleano (verdadeiro/falso), nulo.
- Estruturas de controle: condicionais (if/else), laços (for, while), e interrupção (break/continue).
- Função: bloco reutilizável que recebe parâmetros e devolve um resultado. Funções pequenas e com uma única responsabilidade são mais fáceis de testar.
- Escopo: onde uma variável existe. Evite variáveis globais mutáveis.
- Algoritmo: sequência finita de passos para resolver um problema.
- Compilado vs. interpretado: C, C++, Rust e Go são compilados para código de máquina; Python e JavaScript são executados por um interpretador/VM.

## Estruturas de dados
- Lista/array: sequência ordenada, acesso por índice O(1).
- Dicionário/hash map: pares chave-valor, busca média O(1).
- Conjunto (set): elementos únicos, teste de pertencimento rápido.
- Pilha (LIFO) e fila (FIFO).
- Árvores (hierarquias, árvores de busca binária) e grafos (redes de nós e conexões).
Escolher a estrutura certa costuma importar mais que micro-otimizações.

## Complexidade (Big-O)
Mede como o tempo ou a memória cresce com o tamanho da entrada (n).
- O(1) constante · O(log n) busca binária · O(n) percorrer uma lista · O(n log n) bons algoritmos de ordenação · O(n²) dois laços aninhados · O(2^n) força bruta em subconjuntos.
Dica: um laço dentro de outro sobre os mesmos dados costuma ser O(n²); muitas vezes um dicionário resolve em O(n).

## Python — referência rápida
```python
nums = [3, 1, 2]
nums.sort()                          # ordena no lugar
quadrados = [n * n for n in nums]    # list comprehension
idade = {"ana": 30}; idade.get("bia", 0)
for i, n in enumerate(nums): print(i, n)
def soma(a: int, b: int = 0) -> int: return a + b
with open("arq.txt", encoding="utf-8") as f: texto = f.read()
try:
    x = int("abc")
except ValueError as e:
    print("erro:", e)
```
Ambientes virtuais: `python -m venv .venv` e depois `pip install pacote`. Guarde as dependências em requirements.txt.

## JavaScript — referência rápida
```javascript
const nums = [3, 1, 2];
const dobro = nums.map(n => n * 2).filter(n => n > 2);
const { nome, idade = 0 } = pessoa;          // desestruturação
const resp = await fetch("/api"); const dados = await resp.json();
```
Use `const` por padrão, `let` quando precisar reatribuir, evite `var`. Compare com `===`.

## Git essencial
- `git init` / `git clone url` — iniciar ou copiar um repositório.
- `git status` — ver o que mudou. `git diff` — ver as mudanças linha a linha.
- `git add arquivo` e `git commit -m "mensagem"` — salvar um ponto na história.
- `git switch -c minha-branch` — criar e trocar de branch.
- `git pull` / `git push` — sincronizar com o remoto.
- `git log --oneline --graph` — ver o histórico.
- `git stash` — guardar mudanças temporariamente.
- Desfazer: `git restore arquivo` (descarta mudanças locais), `git revert <hash>` (cria commit que desfaz outro).
Boas práticas: commits pequenos e com mensagem clara; nunca commitar senhas ou chaves de API (.env no .gitignore).

## Depuração (debugging)
1. Reproduza o erro de forma confiável.
2. Leia a mensagem de erro inteira e o stack trace, de baixo para cima: a última linha diz o tipo do erro.
3. Isole: reduza o problema ao menor exemplo que ainda falha.
4. Formule uma hipótese e teste-a (prints, logs, debugger com breakpoints).
5. Corrija a causa, não o sintoma, e escreva um teste que pegaria o erro.
Técnica do "pato de borracha": explicar o código em voz alta, linha por linha, costuma revelar o problema.

## Código limpo e boas práticas
- Nomes claros e descritivos (`total_pedidos` em vez de `tp`).
- Funções curtas que fazem uma coisa só.
- DRY (não se repita), mas sem abstrair cedo demais.
- KISS (mantenha simples) e YAGNI (não implemente o que ainda não precisa).
- Comente o "porquê", não o "o quê".
- Testes automatizados: unitários (funções isoladas), integração (partes juntas) e ponta a ponta.
- SOLID em orientação a objetos; prefira composição a herança.

## Bancos de dados e SQL
```sql
SELECT nome, SUM(valor) AS total FROM pedidos
WHERE data >= '2025-01-01' GROUP BY nome HAVING total > 100 ORDER BY total DESC;
INSERT INTO clientes (nome, email) VALUES ('Ana', 'ana@ex.com');
UPDATE clientes SET email = 'novo@ex.com' WHERE id = 7;
SELECT c.nome, p.valor FROM clientes c JOIN pedidos p ON p.cliente_id = c.id;
```
Relacional (PostgreSQL, MySQL, SQLite): tabelas e relações, transações ACID. NoSQL (MongoDB, Redis): documentos, chave-valor, maior flexibilidade. Crie índices nas colunas usadas em WHERE e JOIN.

## Web, HTTP e APIs
- HTTP: o cliente faz requisições e o servidor responde. Métodos: GET (ler), POST (criar), PUT/PATCH (atualizar), DELETE (remover).
- Status: 2xx sucesso (200 OK, 201 Created), 3xx redirecionamento, 4xx erro do cliente (400, 401 não autenticado, 403 proibido, 404 não encontrado), 5xx erro do servidor.
- REST: recursos identificados por URLs (/usuarios/42), dados geralmente em JSON.
- Frontend (HTML, CSS, JavaScript, frameworks como React) roda no navegador; backend (Python, Node, Java, Go) roda no servidor.

## Segurança básica
- Nunca monte SQL concatenando texto do usuário: use consultas parametrizadas (evita SQL injection).
- Armazene senhas apenas com hash lento e salt (bcrypt, argon2), nunca em texto puro.
- Escape dados exibidos em páginas (evita XSS).
- Mantenha dependências atualizadas e segredos em variáveis de ambiente.
- Princípio do menor privilégio: cada parte do sistema só acessa o que precisa.
- Use HTTPS sempre.
