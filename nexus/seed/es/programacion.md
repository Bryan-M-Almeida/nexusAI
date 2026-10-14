# Fundamentos de Programación
categoria: Programación

Referencia rápida de conceptos, herramientas y buenas prácticas de desarrollo de software.

## Conceptos básicos
- Variable: nombre que guarda un valor. Tipos comunes: entero, decimal (float), texto (string), booleano, nulo.
- Estructuras de control: condicionales (if/else), bucles (for, while) y break/continue.
- Función: bloque reutilizable que recibe parámetros y devuelve un resultado. Las funciones pequeñas y con una sola responsabilidad son más fáciles de probar.
- Ámbito (scope): dónde existe una variable. Evita variables globales mutables.
- Algoritmo: secuencia finita de pasos que resuelve un problema.
- Compilado vs. interpretado: C, C++, Rust y Go se compilan a código máquina; Python y JavaScript se ejecutan en un intérprete/VM.

## Estructuras de datos
- Lista/array: secuencia ordenada, acceso por índice O(1).
- Diccionario/hash map: pares clave-valor, búsqueda media O(1).
- Conjunto (set): elementos únicos, comprobación de pertenencia rápida.
- Pila (LIFO) y cola (FIFO).
- Árboles (jerarquías, árboles binarios de búsqueda) y grafos (redes de nodos y aristas).
Elegir la estructura adecuada suele importar más que las microoptimizaciones.

## Complejidad (Big-O)
Describe cómo crece el tiempo o la memoria con el tamaño de la entrada (n).
- O(1) constante · O(log n) búsqueda binaria · O(n) recorrer una lista · O(n log n) buenos algoritmos de ordenación · O(n²) dos bucles anidados · O(2^n) fuerza bruta sobre subconjuntos.
Consejo: un bucle dentro de otro sobre los mismos datos suele ser O(n²); a menudo un diccionario lo reduce a O(n).

## Python — referencia rápida
```python
nums = [3, 1, 2]
nums.sort()                          # ordena en el sitio
cuadrados = [n * n for n in nums]    # list comprehension
edad = {"ana": 30}; edad.get("luis", 0)
for i, n in enumerate(nums): print(i, n)
def suma(a: int, b: int = 0) -> int: return a + b
with open("archivo.txt", encoding="utf-8") as f: texto = f.read()
try:
    x = int("abc")
except ValueError as e:
    print("error:", e)
```
Entornos virtuales: `python -m venv .venv` y luego `pip install paquete`. Guarda las dependencias en requirements.txt.

## JavaScript — referencia rápida
```javascript
const nums = [3, 1, 2];
const doble = nums.map(n => n * 2).filter(n => n > 2);
const { nombre, edad = 0 } = persona;        // desestructuración
const resp = await fetch("/api"); const datos = await resp.json();
```
Usa `const` por defecto, `let` si necesitas reasignar, evita `var`. Compara con `===`.

## Git esencial
- `git init` / `git clone url` — iniciar o copiar un repositorio.
- `git status` — ver qué cambió. `git diff` — ver los cambios línea a línea.
- `git add archivo` y `git commit -m "mensaje"` — guardar un punto en la historia.
- `git switch -c mi-rama` — crear y cambiar de rama.
- `git pull` / `git push` — sincronizar con el remoto.
- `git log --oneline --graph` — ver el historial.
- `git stash` — guardar cambios temporalmente.
- Deshacer: `git restore archivo` (descarta cambios locales), `git revert <hash>` (nuevo commit que deshace otro).
Buenas prácticas: commits pequeños con mensajes claros; nunca subas contraseñas ni claves de API (.env en .gitignore).

## Depuración
1. Reproduce el error de forma fiable.
2. Lee el mensaje de error completo y la traza de abajo arriba: la última línea indica el tipo de error.
3. Aísla: reduce el problema al ejemplo más pequeño que siga fallando.
4. Formula una hipótesis y pruébala (prints, logs, depurador con puntos de interrupción).
5. Corrige la causa, no el síntoma, y escribe una prueba que lo habría detectado.
Depuración del patito de goma: explicar el código en voz alta línea a línea suele revelar el problema.

## Código limpio y buenas prácticas
- Nombres claros y descriptivos (`total_pedidos` en vez de `tp`).
- Funciones cortas que hacen una sola cosa.
- DRY (no te repitas), pero sin abstraer demasiado pronto.
- KISS (mantenlo simple) y YAGNI (no lo vas a necesitar).
- Comenta el "por qué", no el "qué".
- Pruebas automatizadas: unitarias, de integración y de extremo a extremo.
- SOLID en orientación a objetos; prefiere composición a herencia.

## Bases de datos y SQL
```sql
SELECT nombre, SUM(importe) AS total FROM pedidos
WHERE fecha >= '2025-01-01' GROUP BY nombre HAVING total > 100 ORDER BY total DESC;
INSERT INTO clientes (nombre, email) VALUES ('Ana', 'ana@ej.com');
UPDATE clientes SET email = 'nuevo@ej.com' WHERE id = 7;
SELECT c.nombre, p.importe FROM clientes c JOIN pedidos p ON p.cliente_id = c.id;
```
Relacionales (PostgreSQL, MySQL, SQLite): tablas y relaciones, transacciones ACID. NoSQL (MongoDB, Redis): documentos, clave-valor, más flexibilidad. Crea índices en las columnas usadas en WHERE y JOIN.

## Web, HTTP y APIs
- HTTP: el cliente envía peticiones y el servidor responde. Métodos: GET (leer), POST (crear), PUT/PATCH (actualizar), DELETE (eliminar).
- Códigos: 2xx éxito (200 OK, 201 Created), 3xx redirección, 4xx error del cliente (400, 401 no autenticado, 403 prohibido, 404 no encontrado), 5xx error del servidor.
- REST: recursos identificados por URLs (/usuarios/42), datos normalmente en JSON.
- Frontend (HTML, CSS, JavaScript, frameworks como React) se ejecuta en el navegador; backend (Python, Node, Java, Go) en el servidor.

## Seguridad básica
- Nunca construyas SQL concatenando texto del usuario: usa consultas parametrizadas (evita la inyección SQL).
- Guarda las contraseñas solo como hash lento con sal (bcrypt, argon2), nunca en texto plano.
- Escapa los datos mostrados en páginas (evita XSS).
- Mantén las dependencias actualizadas y los secretos en variables de entorno.
- Principio de mínimo privilegio: cada parte del sistema accede solo a lo que necesita.
- Usa siempre HTTPS.
