# Programming Fundamentals
categoria: Programming

Quick reference of software development concepts, tools and good practices.

## Basic concepts
- Variable: a name holding a value. Common types: integer, float, string, boolean, null.
- Control flow: conditionals (if/else), loops (for, while) and break/continue.
- Function: a reusable block that takes parameters and returns a result. Small, single-purpose functions are easier to test.
- Scope: where a variable exists. Avoid mutable global variables.
- Algorithm: a finite sequence of steps that solves a problem.
- Compiled vs interpreted: C, C++, Rust and Go compile to machine code; Python and JavaScript run on an interpreter/VM.

## Data structures
- List/array: ordered sequence, O(1) index access.
- Dictionary/hash map: key-value pairs, average O(1) lookup.
- Set: unique elements, fast membership tests.
- Stack (LIFO) and queue (FIFO).
- Trees (hierarchies, binary search trees) and graphs (networks of nodes and edges).
Choosing the right structure usually matters more than micro-optimizations.

## Complexity (Big-O)
Describes how time or memory grows with input size (n).
- O(1) constant · O(log n) binary search · O(n) scanning a list · O(n log n) good sorting algorithms · O(n²) two nested loops · O(2^n) brute force over subsets.
Tip: a loop inside another over the same data is often O(n²); a dictionary frequently brings it down to O(n).

## Python quick reference
```python
nums = [3, 1, 2]
nums.sort()                          # sorts in place
squares = [n * n for n in nums]      # list comprehension
age = {"ana": 30}; age.get("bob", 0)
for i, n in enumerate(nums): print(i, n)
def add(a: int, b: int = 0) -> int: return a + b
with open("file.txt", encoding="utf-8") as f: text = f.read()
try:
    x = int("abc")
except ValueError as e:
    print("error:", e)
```
Virtual environments: `python -m venv .venv`, then `pip install package`. Keep dependencies in requirements.txt.

## JavaScript quick reference
```javascript
const nums = [3, 1, 2];
const doubled = nums.map(n => n * 2).filter(n => n > 2);
const { name, age = 0 } = person;            // destructuring
const res = await fetch("/api"); const data = await res.json();
```
Use `const` by default, `let` when you must reassign, avoid `var`. Compare with `===`.

## Git essentials
- `git init` / `git clone url` — start or copy a repository.
- `git status` — see what changed. `git diff` — see changes line by line.
- `git add file` and `git commit -m "message"` — save a point in history.
- `git switch -c my-branch` — create and switch to a branch.
- `git pull` / `git push` — sync with the remote.
- `git log --oneline --graph` — view history.
- `git stash` — shelve changes temporarily.
- Undo: `git restore file` (discard local changes), `git revert <hash>` (new commit that undoes another).
Good practice: small commits with clear messages; never commit passwords or API keys (.env in .gitignore).

## Debugging
1. Reproduce the bug reliably.
2. Read the whole error message and stack trace from the bottom up: the last line names the error type.
3. Isolate: shrink the problem to the smallest example that still fails.
4. Form a hypothesis and test it (prints, logs, a debugger with breakpoints).
5. Fix the cause, not the symptom, and write a test that would have caught it.
Rubber duck debugging: explaining the code out loud line by line often reveals the problem.

## Clean code and good practices
- Clear, descriptive names (`total_orders` instead of `to`).
- Short functions that do one thing.
- DRY (don't repeat yourself), but don't abstract too early.
- KISS (keep it simple) and YAGNI (you aren't gonna need it).
- Comment the "why", not the "what".
- Automated tests: unit (isolated functions), integration (parts together) and end-to-end.
- SOLID in object-oriented design; prefer composition over inheritance.

## Databases and SQL
```sql
SELECT name, SUM(amount) AS total FROM orders
WHERE date >= '2025-01-01' GROUP BY name HAVING total > 100 ORDER BY total DESC;
INSERT INTO customers (name, email) VALUES ('Ana', 'ana@ex.com');
UPDATE customers SET email = 'new@ex.com' WHERE id = 7;
SELECT c.name, o.amount FROM customers c JOIN orders o ON o.customer_id = c.id;
```
Relational (PostgreSQL, MySQL, SQLite): tables and relations, ACID transactions. NoSQL (MongoDB, Redis): documents, key-value, more flexibility. Index columns used in WHERE and JOIN.

## Web, HTTP and APIs
- HTTP: the client sends requests and the server responds. Methods: GET (read), POST (create), PUT/PATCH (update), DELETE (remove).
- Status codes: 2xx success (200 OK, 201 Created), 3xx redirect, 4xx client error (400, 401 unauthenticated, 403 forbidden, 404 not found), 5xx server error.
- REST: resources identified by URLs (/users/42), data usually in JSON.
- Frontend (HTML, CSS, JavaScript, frameworks like React) runs in the browser; backend (Python, Node, Java, Go) runs on the server.

## Basic security
- Never build SQL by concatenating user input: use parameterized queries (prevents SQL injection).
- Store passwords only as slow salted hashes (bcrypt, argon2), never in plain text.
- Escape data rendered in pages (prevents XSS).
- Keep dependencies updated and secrets in environment variables.
- Principle of least privilege: each part of the system accesses only what it needs.
- Always use HTTPS.
