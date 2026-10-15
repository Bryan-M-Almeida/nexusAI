"""Knowledge base: seed books + anything the user teaches, searchable with SQLite FTS5."""
import re
import unicodedata
from pathlib import Path

from .config import INBOX_DIR, SEED_DIR
from .db import db, now

STOPWORDS = set(
    """a o e é de da do das dos em no na nos nas um uma uns umas para por com sem que se
    me te lhe nos vos eu tu ele ela eles elas você vocês meu minha seu sua isso isto aquilo
    como qual quais quando onde porque porquê mais menos muito pouco ao aos às ou mas
    the of and to in is it for on with what how why when which who are was be can do does
    nexus sobre faz fazer ser ter tem está estou tá pra pro já também então
    you your my this that have has from about there tell know should would could please
    el la los las del una por para con sin qué cómo cuál cuando donde pero muy está estoy tengo sobre""".split()
)
CHUNK_CHARS = 1400


def fts_query(text: str, max_terms: int = 12) -> str:
    """Turn free text into a forgiving FTS5 OR-query with prefix matching."""
    words = re.findall(r"\w+", text.lower())
    terms = []
    for w in words:
        if len(w) < 3 or w in STOPWORDS or w.isdigit():
            continue
        # Light stemming so "investimentos" also matches "investimento".
        stem = w[:-1] if len(w) > 5 and w.endswith("s") else w
        if stem not in terms:
            terms.append(stem)
    return " OR ".join(f'"{t}"*' for t in terms[:max_terms])


def _chunks(text: str):
    """Split markdown/plain text into (heading, content) chunks."""
    heading, buf = "", []
    for line in text.splitlines():
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if m and len(m.group(1)) >= 2:
            if "".join(buf).strip():
                yield heading, "\n".join(buf).strip()
            heading, buf = m.group(2).strip(), []
        elif not (m and len(m.group(1)) == 1):
            buf.append(line)
    if "".join(buf).strip():
        yield heading, "\n".join(buf).strip()


def _split_long(heading, content):
    if len(content) <= CHUNK_CHARS:
        yield heading, content
        return
    part = ""
    for para in re.split(r"\n\s*\n", content):
        if part and len(part) + len(para) > CHUNK_CHARS:
            yield heading, part.strip()
            part = ""
        part += para + "\n\n"
    if part.strip():
        yield heading, part.strip()


# v0.14: search results are cached until the knowledge base changes (every message runs at least one search).
_cache: dict = {}
_CACHE_MAX = 256


def _changed():
    _cache.clear()


def add_document(title: str, text: str, category: str, source: str) -> dict:
    _changed()
    """Insert or replace (same source) a document. Returns {id, chunks}."""
    existing = db.one("SELECT id FROM kb_docs WHERE source = ?", (source,))
    if existing:
        doc_id = existing["id"]
        db.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (doc_id,))
        db.execute("UPDATE kb_docs SET title=?, category=?, updated=? WHERE id=?", (title, category, now(), doc_id))
    else:
        doc_id = db.execute(
            "INSERT INTO kb_docs(title, category, source, created, updated) VALUES (?,?,?,?,?)",
            (title, category, source, now(), now()),
        ).lastrowid
    count = 0
    for heading, content in _chunks(text):
        for h, c in _split_long(heading or title, content):
            db.execute(
                "INSERT INTO kb_chunks(heading, content, category, doc_id) VALUES (?,?,?,?)",
                (h, c, category, doc_id),
            )
            count += 1
    return {"id": doc_id, "chunks": count}


def learn(title: str, content: str, category: str = "aprendido") -> dict:
    """Knowledge taught in conversation. Same title -> updates the previous entry."""
    slug = unicodedata.normalize("NFKD", title.lower()).encode("ascii", "ignore").decode()
    slug = re.sub(r"\W+", "-", slug).strip("-")
    result = add_document(title, f"## {title}\n{content}", category, f"learned:{slug}")
    db.log_action("conhecimento", f"Aprendeu: {title} ({category})")
    return result


def _read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    return path.read_text("utf-8", errors="ignore")


def _meta(text: str, fallback_title: str):
    title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), fallback_title)
    m = re.search(r"^categoria:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    return title, (m.group(1).strip() if m else None)


def import_file(path, category: str | None = None) -> dict:
    path = Path(path)
    text = _read_file(path)
    if not text.strip():
        raise ValueError(f"Não consegui extrair texto de {path.name}.")
    title, cat = _meta(text, path.stem.replace("_", " ").title())
    result = add_document(title, text, category or cat or "importado", f"file:{path.name}")
    db.log_action("conhecimento", f"Importou arquivo: {path.name} ({result['chunks']} trechos)")
    return {"title": title, **result}


def load_seed() -> int:
    """Index the bundled books once (re-indexes if a seed file changed)."""
    loaded = 0
    for path in sorted(SEED_DIR.rglob("*.md")):  # seed/pt/*.md and seed/en/*.md
        source = f"seed:{path.relative_to(SEED_DIR).as_posix()}"
        mtime = str(int(path.stat().st_mtime))
        if db.one("SELECT 1 FROM kb_docs WHERE source=? AND updated LIKE ?", (source, f"%#{mtime}")):
            continue
        text = path.read_text("utf-8")
        title, cat = _meta(text, path.stem)
        add_document(title, text, cat or path.stem, source)
        db.execute("UPDATE kb_docs SET updated = ? WHERE source = ?", (f"{now()}#{mtime}", source))
        loaded += 1
    return loaded


def scan_inbox() -> list[str]:
    learned = []
    for path in INBOX_DIR.iterdir():
        if path.suffix.lower() in (".md", ".txt", ".pdf"):
            try:
                import_file(path)
                learned.append(path.name)
                path.rename(path.with_suffix(path.suffix + ".learned"))
            except Exception as exc:  # keep booting even if one file is bad
                db.log_action("erro", f"Falha ao importar {path.name}: {exc}")
    return learned


def search(query: str, limit: int = 4, category: str | None = None) -> list[dict]:
    key = (query, limit, category)
    if key in _cache:
        return [dict(r) for r in _cache[key]]
    rows = _search(query, limit, category)
    if len(_cache) >= _CACHE_MAX:
        _cache.pop(next(iter(_cache)))
    _cache[key] = [dict(r) for r in rows]
    return rows


def _search(query: str, limit: int = 4, category: str | None = None) -> list[dict]:
    q = fts_query(query)
    if not q:
        return []
    sql = (
        "SELECT c.heading, c.content, c.category, d.title, bm25(kb_chunks, 2.0, 1.0) AS score "
        "FROM kb_chunks c JOIN kb_docs d ON d.id = c.doc_id WHERE kb_chunks MATCH ?"
    )
    params = [q]
    if category:
        sql += " AND c.category LIKE ?"
        params.append(f"%{category}%")
    sql += " ORDER BY score LIMIT ?"
    params.append(limit)
    return db.all(sql, params)


def stats() -> list[dict]:
    return db.all(
        "SELECT d.category, COUNT(DISTINCT d.id) AS docs, COUNT(c.rowid) AS chunks "
        "FROM kb_docs d LEFT JOIN kb_chunks c ON c.doc_id = d.id GROUP BY d.category ORDER BY d.category"
    )


def documents() -> list[dict]:
    return db.all("SELECT id, title, category, source, created FROM kb_docs ORDER BY category, title")


def delete_document(doc_id: int):
    doc = db.one("SELECT title FROM kb_docs WHERE id = ?", (doc_id,))
    _changed()
    db.execute("DELETE FROM kb_chunks WHERE doc_id = ?", (doc_id,))
    db.execute("DELETE FROM kb_docs WHERE id = ?", (doc_id,))
    if doc:
        db.log_action("conhecimento", f"Removeu documento: {doc['title']}")
