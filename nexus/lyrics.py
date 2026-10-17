"""Song lyrics from a source the user names (v0.19.6): "cante Sorriso Resplandecente, letra do LRCLIB".

NEXUS never writes lyrics from memory (the model invents them). It shows/reads them only when the user says where to
take them from, and always credits the source:
  - LRCLIB (lrclib.net): open lyrics database with a public API made for music apps - fetched and shown here;
  - Vagalume: through its official API (needs a free key in Settings > Integrations); when the API is unavailable,
    the song's page opens in the browser;
  - Letras.mus.br and Genius have no public API: their page opens in the browser (scraping sites is against their
    terms, so NEXUS doesn't do it)."""
import re
import unicodedata
from urllib.parse import quote

import httpx

from .config import settings

SOURCES = {  # id: (words the user says, kind)
    "lrclib": (r"lrclib|lrc lib|lrc", "api"),
    "vagalume": (r"vagalume|vaga lume|vagalumes", "api_or_page"),
    "letras": (r"letras\.mus\.br|letras mus|site letras|letras\.com|do letras|no letras", "page"),
    "genius": (r"genius", "page"),
}
NAMES = {"lrclib": "LRCLIB", "vagalume": "Vagalume", "letras": "Letras.mus.br", "genius": "Genius"}
PAGES = {"vagalume": "https://www.vagalume.com.br/search?q={q}", "letras": "https://www.letras.mus.br/?q={q}",
         "genius": "https://genius.com/search?q={q}"}
ASK = re.compile(r"\b(cant[ae]r?|canta|sing|letra|lyrics|letras)\b", re.I)


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


def source_in(text: str) -> str | None:
    n = _norm(text)
    return next((sid for sid, (words, _) in SOURCES.items() if re.search(rf"\b(?:{words})\b", n)), None)


_SOURCE_WORDS = r"lrclib|lrc lib|lrc|vagalumes?|vaga lume|letras\.mus\.br|letras mus|genius"


def song_in(text: str) -> str:
    """The song the user asked for, without the request words and the source."""
    t = re.sub(r"[\"“”«»]", '"', text)
    quoted = re.findall(r'"([^"]{2,80})"', t)
    if quoted:
        return quoted[0].strip()
    # the source and the words that introduce it, wherever they are ("..., letra do LRCLIB", "no genius")
    t = re.sub(rf"[,;]?\s*(?:usando|use|using|pela|pelo|pegando|pega|pegue|tira|tirando|from|com|with)?\s*"
               rf"(?:a\s+|el\s+|la\s+|the\s+)?(?:letra\s+|lyrics\s+)?(?:d[aeo]|del|de|no|na|en|from|in|on|of)?\s*"
               rf"(?:site\s+)?(?:el\s+|la\s+)?\b(?:{_SOURCE_WORDS})\b", " ", t, flags=re.I)
    t = re.sub(r"^\W*(?:nexus\W+)?(?:pode\s+|por favor\s+)?(?:qual\s+(?:[eé]\s+)?|what(?:'s| is)\s+)?"
               r"(?:cant[ae]r?|canta|sing|mostr[ae]|me mostra|show|pega|pegue|busca|busque|get|find)?\s*"
               r"(?:a\s+|the\s+|la\s+)?(?:letra|lyrics)?\s*(?:d[aeo]\s+|of\s+|for\s+|to\s+)?"
               r"(?:m[uú]sica\s+|can[cç][aã]o\s+|song\s+)?", "", t.strip(), flags=re.I)
    return re.sub(r"\s+", " ", t).strip(" ,.;:!?\"'")


def _lrclib(query: str, context: str = "") -> dict:
    r = httpx.get("https://lrclib.net/api/search", params={"q": query}, timeout=10,
                  headers={"User-Agent": "NEXUS-assistant (github.com/Bryan-M-Almeida/nexusAI)"})
    r.raise_for_status()
    found = [x for x in r.json() if x.get("plainLyrics")]
    if not found:
        return {"error": "not_found"}
    q = _norm(query)
    # same title first, then the fullest lyrics (the original release, not a short cover or an excerpt)
    # words of the conversation ("Dragon Ball GT") pick the right one among songs with the same name
    ctx = {w for w in re.findall(r"[a-z0-9]{3,}", _norm(context))} - set(re.findall(r"[a-z0-9]+", q))

    def rank(x):
        title = _norm(x.get("trackName", ""))
        about = _norm(" ".join(str(x.get(k) or "") for k in ("trackName", "albumName", "artistName")))
        cover = bool(re.search(r"cover|remix|karaoke|instrumental|english|version|tv size|live", title))
        return (sum(w in about for w in ctx), q in title, not cover, len(x.get("plainLyrics", "")))

    best = max(found, key=rank)
    return {"title": best.get("trackName", ""), "artist": best.get("artistName", ""), "text": best["plainLyrics"].strip(),
            "url": f"https://lrclib.net/search/{quote(query)}", "source": "LRCLIB"}


def _vagalume(query: str) -> dict:
    key = settings.get("vagalume_key", "")
    if not key:
        return {"error": "no_key"}
    found = httpx.get("https://api.vagalume.com.br/search.excerpt", params={"q": query, "limit": 1, "apikey": key},
                      timeout=10).json().get("response", {}).get("docs", [])
    if not found:
        return {"error": "not_found"}
    data = httpx.get("https://api.vagalume.com.br/search.php", params={"musid": found[0]["id"], "apikey": key},
                     timeout=10).json()
    mus = (data.get("mus") or [{}])[0]
    if not mus.get("text"):
        return {"error": "not_found"}
    return {"title": mus.get("name", ""), "artist": (data.get("art") or {}).get("name", ""), "text": mus["text"].strip(),
            "url": mus.get("url", ""), "source": "Vagalume"}


def fetch(source: str, query: str, context: str = "") -> dict:
    """{"title", "artist", "text", "url", "source"} | {"opened": url} (page in the browser) | {"error": ...}."""
    kind = SOURCES[source][1]
    if kind in ("api", "api_or_page"):
        try:
            got = _lrclib(query, context) if source == "lrclib" else _vagalume(query)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            got = {"error": f"unavailable: {type(exc).__name__}"}
        if "error" not in got or kind == "api":
            return got
    url = PAGES[source].format(q=quote(query))
    from . import browser

    browser.OPEN(url, new=2)
    return {"opened": url, "source": source}


def handle(text: str, recent_titles: list[str], code: str, context: str = "") -> str | None:
    """Instant path for "cante X, letra do LRCLIB" (also "mostra a letra de X no Vagalume", "pega do LRCLIB")."""
    from . import i18n

    source = source_in(text)
    if not source or not (ASK.search(_norm(text)) or re.search(r"\b(pega|pegue|use|usa|tira|from)\b", _norm(text))):
        return None
    song = song_in(text)
    if not song or re.fullmatch(r"(essa|esta|ela|isso|isto|ent[aã]o|it|that|this|esa|eso)", song, re.I):
        song = recent_titles[-1] if recent_titles else ""
    if not song:
        return i18n.STRINGS[code]["lyrics_which"]
    got = fetch(source, song, context + " " + text)
    # a translated title ("Sorriso Resplandecente") may not exist in the source: try the other titles just mentioned
    # in the conversation ("Dan Dan Kokoro Hikareteku")
    for other in [t for t in reversed(recent_titles) if t.lower() != song.lower()][:3]:
        if "error" not in got:
            break
        got = fetch(source, other, context + " " + text)
    T = i18n.STRINGS[code]
    if got.get("opened"):
        return T["lyrics_opened"].format(song=song, source=NAMES[source])
    if "error" in got:
        return T["lyrics_none"].format(song=song, source=NAMES[source])
    return T["lyrics_head"].format(title=got["title"], artist=got["artist"], source=got["source"], url=got["url"]) + "\n\n" + got["text"]
