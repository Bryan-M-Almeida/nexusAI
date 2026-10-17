"""Settings > About (v0.20.0): the update history (CHANGELOG.md) and the possible errors (erros.txt / errors.txt /
errores.txt) read straight from the documents that ship with NEXUS, so the app and the repository never disagree."""
import html
import re
import sys
from functools import lru_cache
from pathlib import Path

from .config import PKG_DIR

ROOT = Path(getattr(sys, "_MEIPASS", PKG_DIR.parent))  # the repository, or the unpacked executable
ERRORS_FILE = {"pt": "erros.txt", "en": "errors.txt", "es": "errores.txt"}
FIXED = {"CORRIGIDO", "FIXED", "CORREGIDO"}
STATUS_RX = re.compile(r"(?:Status|Estado)\s*:\s*([A-ZÁÉÍÓÚÃÕÇ]+)")
SEVERITY_RX = re.compile(r"(?:Severidade|Severity|Gravedad)\s*:\s*([A-ZÁÉÍÓÚÃÕÇ]+)")
FIELD_RX = re.compile(r"^  ([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .0-9]{1,22}?)\s*:\s?(.*)$")
SYMPTOM = {"sintoma", "symptom", "síntoma"}
FIX = {"solução", "solution", "solución", "contorno", "workaround", "mitigação", "mitigation", "mitigación",
       "correção", "correções", "fix", "corrección", "correcciones"}
TIPS = {"dicas", "dica", "tips", "tip", "consejos", "consejo", "limitação", "limitation", "limitación",
        "comportamento esperado", "expected behavior", "comportamiento esperado"}
CAUSE = {"causa", "cause"}


def _inline(text: str) -> str:
    """Tiny Markdown subset -> safe HTML: **bold**, `code`, [text](link) -> text."""
    text = html.escape(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", text)


def _md(lines: list[str]) -> str:
    out, item, table = [], None, []

    def flush():
        nonlocal item, table
        if item is not None:
            out.append(f"<li>{_inline(item)}</li>")
            item = None
        if table:
            rows = [r for r in table if not re.match(r"^\|[\s\-:|]+\|$", r)]
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
            body = "".join("<tr>" + "".join(f"<{'th' if i == 0 else 'td'}>{_inline(c)}</{'th' if i == 0 else 'td'}>"
                                            for c in row) + "</tr>" for i, row in enumerate(cells))
            out.append(f"<table>{body}</table>")
            table = []

    for line in lines:
        if line.startswith("|"):
            if item is not None:
                flush()
            table.append(line.strip())
            continue
        if table:
            flush()
        if line.startswith("### "):
            flush()
            out.append(f"<h4>{_inline(line[4:])}</h4>")
        elif re.match(r"^\s*- ", line):
            flush()
            item = re.sub(r"^\s*- ", "", line)
        elif line.strip() and item is not None:
            item += " " + line.strip()
        elif line.strip() and line.strip() != "---":
            flush()
            out.append(f"<p>{_inline(line.strip())}</p>")
        else:
            flush()
    flush()
    return re.sub(r"(<li>.*?</li>)+", lambda m: f"<ul>{m.group(0)}</ul>", "".join(out))


@lru_cache(maxsize=1)
def changelog() -> list[dict]:
    """[{version, date, headline, html}] newest first."""
    path = ROOT / "CHANGELOG.md"
    if not path.exists():
        return []
    versions, cur = [], None
    for line in path.read_text("utf-8").splitlines():
        m = re.match(r"^## (v[\d.]+)\s*[—-]\s*(.+?)(?:\s*·\s*(\d{4}-\d{2}-\d{2}))?\s*$", line)
        if m:
            cur = {"version": m.group(1), "kind": m.group(2).strip(), "date": m.group(3) or "", "lines": []}
            versions.append(cur)
        elif line.startswith("## "):
            cur = None  # "## Próximas versões" and other sections that are not a release
        elif cur is not None:
            cur["lines"].append(line)
    out = []
    for v in versions:
        lines = v.pop("lines")
        start = next((i for i, x in enumerate(lines) if x.strip().startswith("**")), None)
        head, body = [], lines
        if start is not None and not any(x.startswith("#") for x in lines[:start]):
            end = start
            while end < len(lines) and lines[end].strip():  # the bold headline can span lines
                head.append(lines[end].strip())
                end += 1
            body = lines[end:]
        v["headline"] = _inline(" ".join(head).strip("*")) if head else ""
        v["html"] = _md(body)
        out.append(v)
    return out


@lru_cache(maxsize=3)
def known_errors(code: str = "pt") -> list[dict]:
    """The catalogue entries that can still happen (not FIXED): id, title, area, severity, status, symptom, fix."""
    path = ROOT / ERRORS_FILE.get(code, "erros.txt")
    if not path.exists():
        return []
    items, cur, field = [], None, None
    for line in path.read_text("utf-8").splitlines():
        m = re.match(r"^\[(NX-([A-Z]+)-\d+)\]\s*(.+)$", line)
        if m:
            cur = {"id": m.group(1), "area": m.group(2), "title": m.group(3).strip(), "severity": "", "status": "",
                   "symptom": "", "cause": "", "fix": "", "tips": ""}
            items.append(cur)
            field = None
            continue
        if cur is None:
            continue
        if not line.strip() or line.startswith("==") or line.startswith("--"):
            if not line.strip():
                field = None
            continue
        if not line.startswith(" "):
            cur, field = None, None  # a new chapter of the document
            continue
        st, sev = STATUS_RX.search(line), SEVERITY_RX.search(line)
        if st or sev:
            cur["status"] = st.group(1) if st else cur["status"]
            cur["severity"] = sev.group(1) if sev else cur["severity"]
            field = None
            continue
        f = FIELD_RX.match(line)
        if f:
            name = f.group(1).strip().lower()
            field = ("symptom" if name in SYMPTOM else "fix" if name in FIX else "tips" if name in TIPS
                     else "cause" if name in CAUSE else None)
            if field:
                cur[field] += ("\n" if cur[field] else "") + f.group(2).strip()
            continue
        if field:
            cur[field] += ("\n" if re.match(r"^\s*(\d+\.|-)\s", line) else " ") + line.strip()
    return [x for x in items if x["status"] and x["status"] not in FIXED]
