"""Library (v0.15): books the user adds (PDF, EPUB, DOCX, TXT, MD), read on screen or aloud ("podcast mode").
The extracted text is kept in DATA_DIR/library/<id>.txt, so opening a page or continuing the podcast never parses
the original file again; the reading position is saved as it goes."""
import re
from pathlib import Path

from . import files
from .config import DATA_DIR
from .db import db, now
from .i18n import detect

LIB_DIR = DATA_DIR / "library"
PAGE_CHARS = 2400       # one screen of reading
PODCAST_CHARS = 700     # one spoken part: short enough to stop/pause quickly, long enough to sound natural
player = None           # set by the app: player(book_id, position) starts the podcast (used by the AI tools)


def _title_from(path: Path, text: str) -> str:
    name = re.sub(r"[_\-]+", " ", path.stem).strip()
    return name[:120] or text[:60]


def add(path) -> dict:
    path = Path(path)
    if path.suffix.lower() not in files.BOOK_EXT:
        raise files.FileError(f"{path.suffix} is not a book format (PDF, EPUB, DOCX, TXT, MD)")
    data = files.read(path)
    LIB_DIR.mkdir(parents=True, exist_ok=True)
    language = detect(data["text"][:3000]) or ""
    bid = db.execute("INSERT INTO books(title, kind, source, chars, position, language, added) VALUES (?,?,?,?,?,?,?)",
                     (_title_from(path, data["text"]), data["kind"], str(path), len(data["text"]), 0, language,
                      now())).lastrowid
    (LIB_DIR / f"{bid}.txt").write_text(data["text"], encoding="utf-8")
    return get(bid)


def get(bid: int) -> dict | None:
    row = db.one("SELECT * FROM books WHERE id = ?", (int(bid),))
    if row:
        row["progress"] = round(row["position"] / max(row["chars"], 1), 3)
    return row


def listing() -> list[dict]:
    rows = db.all("SELECT * FROM books ORDER BY COALESCE(last_read, added) DESC")
    for r in rows:
        r["progress"] = round(r["position"] / max(r["chars"], 1), 3)
    return rows


def find(title: str) -> dict | None:
    """Book by (part of) its title, for voice commands like "read Dom Casmurro"."""
    t = f"%{title.strip()}%"
    return db.one("SELECT * FROM books WHERE title LIKE ? ORDER BY COALESCE(last_read, added) DESC LIMIT 1", (t,))


def text(bid: int) -> str:
    return (LIB_DIR / f"{int(bid)}.txt").read_text(encoding="utf-8")


def _boundary(t: str, pos: int, limit: int, soft=("\n\n", ". ", "! ", "? ", "\n")) -> int:
    """End of a chunk starting at pos: the last paragraph/sentence break before pos+limit."""
    end = min(len(t), pos + limit)
    if end >= len(t):
        return len(t)
    for sep in soft:
        cut = t.rfind(sep, pos + limit // 3, end)
        if cut != -1:
            return cut + len(sep)
    return end


def page(bid: int, position: int) -> dict:
    t = text(bid)
    position = max(0, min(int(position), len(t)))
    end = _boundary(t, position, PAGE_CHARS)
    set_position(bid, position)
    return {"text": t[position:end], "start": position, "end": end, "chars": len(t)}


def next_part(bid: int, position: int) -> tuple[str, int]:
    t = text(bid)
    end = _boundary(t, position, PODCAST_CHARS)
    return t[position:end].strip(), end


def set_position(bid: int, position: int):
    db.execute("UPDATE books SET position = ?, last_read = ? WHERE id = ?", (int(position), now(), int(bid)))


def delete(bid: int):
    (LIB_DIR / f"{int(bid)}.txt").unlink(missing_ok=True)
    db.execute("DELETE FROM books WHERE id = ?", (int(bid),))
