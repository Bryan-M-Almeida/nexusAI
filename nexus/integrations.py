"""Online integrations without accounts or API keys: weather (Open-Meteo), news (Google News RSS),
currency (Frankfurter / European Central Bank), Wikipedia and a read-only calendar feed (ICS link).

Every function returns plain data for the model; network errors become {"error": ...} so a missing internet
connection never breaks a conversation."""
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx

from .config import settings
from .db import db, now
from .i18n import lang

TIMEOUT = httpx.Timeout(10, connect=5)
HEADERS = {"User-Agent": "NEXUS-assistant/0.6 (hackathon prototype)"}


_client: httpx.Client | None = None


def _get(url, **params):
    # v0.18.0: one client keeps the connections open - each new TLS handshake cost ~0.6 s, and a weather answer
    # needs two requests to the same service
    global _client
    if _client is None:
        _client = httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True,
                               limits=httpx.Limits(max_keepalive_connections=8, keepalive_expiry=120))
    r = _client.get(url, params=params or None)
    r.raise_for_status()
    return r


def _offline(exc) -> dict:
    return {"error": f"service unavailable (no internet?): {type(exc).__name__}"}


# ---------------------------------------------------------------- weather
WMO = {  # WMO weather codes used by Open-Meteo
    0: ("céu limpo", "clear sky", "despejado"), 1: ("predominantemente limpo", "mainly clear", "mayormente despejado"),
    2: ("parcialmente nublado", "partly cloudy", "parcialmente nublado"), 3: ("nublado", "overcast", "nublado"),
    45: ("neblina", "fog", "niebla"), 48: ("neblina com geada", "rime fog", "niebla con escarcha"),
    51: ("garoa fraca", "light drizzle", "llovizna ligera"), 53: ("garoa", "drizzle", "llovizna"),
    55: ("garoa forte", "dense drizzle", "llovizna intensa"), 61: ("chuva fraca", "light rain", "lluvia ligera"),
    63: ("chuva", "rain", "lluvia"), 65: ("chuva forte", "heavy rain", "lluvia intensa"),
    66: ("chuva congelante", "freezing rain", "lluvia helada"), 67: ("chuva congelante forte", "heavy freezing rain", "lluvia helada intensa"),
    71: ("neve fraca", "light snow", "nieve ligera"), 73: ("neve", "snow", "nieve"), 75: ("neve forte", "heavy snow", "nieve intensa"),
    77: ("grãos de neve", "snow grains", "granos de nieve"), 80: ("pancadas de chuva", "rain showers", "chubascos"),
    81: ("pancadas de chuva fortes", "heavy rain showers", "chubascos fuertes"),
    82: ("pancadas de chuva violentas", "violent rain showers", "chubascos violentos"),
    85: ("pancadas de neve", "snow showers", "chubascos de nieve"), 86: ("pancadas de neve fortes", "heavy snow showers", "chubascos de nieve fuertes"),
    95: ("trovoada", "thunderstorm", "tormenta"), 96: ("trovoada com granizo", "thunderstorm with hail", "tormenta con granizo"),
    99: ("trovoada com granizo forte", "thunderstorm with heavy hail", "tormenta con granizo fuerte"),
}
_LANG_IDX = {"pt": 0, "en": 1, "es": 2}


def _describe(code) -> str:
    return WMO.get(int(code or 0), ("?", "?", "?"))[_LANG_IDX.get(lang(), 0)]


def get_weather(city: str = "", days: int = 3):
    city = (city or settings["home_city"]).strip()
    if not city:
        return {"error": "no city: ask the user which city (it can be saved in Settings > City)"}
    try:
        geo = _get("https://geocoding-api.open-meteo.com/v1/search", name=city, count=1, language=lang()).json()
        if not geo.get("results"):
            return {"error": f"city not found: {city}"}
        place = geo["results"][0]
        days = max(1, min(int(days or 3), 7))
        fc = _get("https://api.open-meteo.com/v1/forecast", latitude=place["latitude"], longitude=place["longitude"],
                  current="temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
                  daily="weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                  timezone="auto", forecast_days=days).json()
    except httpx.HTTPError as exc:
        return _offline(exc)
    cur, daily = fc["current"], fc["daily"]
    return {
        "place": f"{place['name']}, {place.get('admin1', '')} {place.get('country', '')}".replace(" ,", ",").strip(),
        "now": {"temp_c": cur["temperature_2m"], "feels_like_c": cur["apparent_temperature"],
                "humidity_pct": cur["relative_humidity_2m"], "wind_kmh": cur["wind_speed_10m"],
                "conditions": _describe(cur["weather_code"])},
        "forecast": [{"date": d, "min_c": lo, "max_c": hi, "rain_chance_pct": rain, "conditions": _describe(code)}
                     for d, lo, hi, rain, code in zip(daily["time"], daily["temperature_2m_min"], daily["temperature_2m_max"],
                                                      daily["precipitation_probability_max"], daily["weather_code"])],
        "source": "Open-Meteo",
    }


# ---------------------------------------------------------------- news
_NEWS_REGION = {"pt": "hl=pt-BR&gl=BR&ceid=BR:pt-419", "en": "hl=en-US&gl=US&ceid=US:en", "es": "hl=es-419&gl=MX&ceid=MX:es-419"}


def get_news(topic: str = "", limit: int = 5):
    region = _NEWS_REGION.get(lang(), _NEWS_REGION["pt"])
    url = (f"https://news.google.com/rss/search?q={quote(topic)}&{region}" if topic
           else f"https://news.google.com/rss?{region}")
    try:
        root = ET.fromstring(_get(url).content)
    except (httpx.HTTPError, ET.ParseError) as exc:
        return _offline(exc)
    items = []
    for item in root.iter("item"):
        title = item.findtext("title", "")
        source = item.findtext("source", "") or (title.rsplit(" - ", 1)[1] if " - " in title else "")
        items.append({"title": title.rsplit(" - ", 1)[0], "source": source, "published": item.findtext("pubDate", "")[:16]})
        if len(items) >= max(1, min(int(limit or 5), 10)):
            break
    return {"topic": topic or "top stories", "headlines": items, "source": "Google News"}


# ---------------------------------------------------------------- currency
def convert_currency(amount: float = 1, from_currency: str = "USD", to_currency: str = "BRL"):
    src, dst = from_currency.upper().strip(), to_currency.upper().strip()
    try:
        data = _get("https://api.frankfurter.app/latest", amount=float(amount), **{"from": src, "to": dst}).json()
    except httpx.HTTPStatusError:
        return {"error": f"unsupported currency pair {src}->{dst} (use ISO codes like USD, EUR, BRL)"}
    except httpx.HTTPError as exc:
        return _offline(exc)
    return {"amount": float(amount), "from": src, "to": dst, "result": data["rates"].get(dst), "rate_date": data["date"],
            "source": "Frankfurter (European Central Bank reference rates; not a trading quote)"}


# ---------------------------------------------------------------- wikipedia
def wikipedia(query: str):
    """Summary of the best article; for questions about a detail ("quem canta a abertura de X") also the lines of the
    3 best articles that mention it (v0.19.6: the lead of "Dragon Ball GT" never names its opening song, and for
    "Cavaleiros do Zodíaco" the answer is in "Trilha Sonora de Cavaleiros do Zodíaco" - the model invented both)."""
    code = lang()
    words = re.findall(r"\w+", query.lower())
    keywords = " ".join(w for w in words if w not in _STOP and w not in _QUESTION) or query
    try:
        titles = []
        if len(words) <= 3:  # a name: title search
            found = _get(f"https://{code}.wikipedia.org/w/api.php", action="opensearch", search=query, limit=1,
                         namespace=0, format="json").json()
            titles = found[1][:1]
        if not titles:  # a sentence -> full-text search with the meaningful words
            hits = _get(f"https://{code}.wikipedia.org/w/api.php", action="query", list="search", srsearch=keywords,
                        srlimit=3, format="json").json().get("query", {}).get("search", [])
            titles = [h["title"] for h in hits]
        if not titles:
            return {"error": f"no Wikipedia article for: {query}"}
        page = _get(f"https://{code}.wikipedia.org/api/rest_v1/page/summary/{quote(titles[0].replace(' ', '_'))}").json()
    except httpx.HTTPError as exc:
        return _offline(exc)
    out = {"title": page.get("title", titles[0]), "summary": (page.get("extract") or "")[:900],
           "url": page.get("content_urls", {}).get("desktop", {}).get("page", ""), "source": "Wikipedia"}
    details = []
    for title in titles:
        found = _article_details(code, title, keywords)
        if found:
            details.append(f"[{title}] {found}")
    if details:
        out["details"] = "\n".join(details)[:1500]
    return out


_STOP = {"de", "do", "da", "dos", "das", "o", "a", "os", "as", "e", "the", "of", "and", "el", "la", "los", "las", "del",
         "um", "uma", "é", "is", "es", "em", "in", "en", "no", "na", "que", "se", "por", "para", "com", "to"}
_QUESTION = {"qual", "quais", "quem", "what", "who", "which", "cual", "cuál", "quien", "quién", "canta", "cantou",
             "sings", "sang", "chama", "called", "llama", "foi", "was", "fue", "me", "diga", "tell", "sabe", "know"}
_SYNONYMS = {"abertura": ["abertura", "opening", "tema de abertura"], "opening": ["opening", "abertura"],
             "encerramento": ["encerramento", "ending", "tema de encerramento"], "ending": ["ending", "encerramento"],
             "musica": ["música", "music", "canção"], "música": ["música", "music", "canção"],
             "trilha": ["trilha sonora", "soundtrack"], "elenco": ["elenco", "cast", "dublagem", "voz"],
             "cast": ["cast", "elenco"], "autor": ["autor", "criado por", "escrito por", "author"],
             "dublagem": ["dublagem", "dublado", "voz"]}


def _article_details(code: str, title: str, query: str) -> str:
    """The lines of an article that mention what the question asks beyond the article's own name (with the next
    lines after a short match: lists such as "Abertura:" put the value there)."""
    title_words = set(re.findall(r"\w+", title.lower()))
    wanted = [w for w in re.findall(r"\w+", query.lower()) if w not in _STOP and w not in title_words and len(w) > 2]
    if not wanted:
        return ""
    terms = {t for w in wanted for t in _SYNONYMS.get(w, [w])}
    try:
        pages = _get(f"https://{code}.wikipedia.org/w/api.php", action="query", prop="extracts", explaintext=1,
                     titles=title, redirects=1, format="json").json()["query"]["pages"]
        text = next(iter(pages.values())).get("extract", "")
    except (httpx.HTTPError, KeyError, ValueError, StopIteration):
        return ""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    scored = []
    for i, ln in enumerate(lines):
        low = ln.lower()
        score = sum(t in low for t in terms)
        if score:
            chunk = " ".join(lines[i:i + (3 if len(ln) < 60 else 1)])
            scored.append((score, i, chunk[:420]))
    best, seen = [], []
    for score, i, chunk in sorted(scored, key=lambda x: (-x[0], x[1])):
        if not any(chunk[:120] in other or other[:120] in chunk for other in seen):
            best.append((i, chunk))
            seen.append(chunk)
        if len(best) == 2:
            break
    return " / ".join(chunk for _, chunk in sorted(best))


# ---------------------------------------------------------------- calendar (ICS feed, read-only)
def _unfold(text: str) -> list[str]:
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def _ics_datetime(key: str, value: str) -> datetime | None:
    try:
        if "VALUE=DATE" in key or re.fullmatch(r"\d{8}", value):
            return datetime.strptime(value[:8], "%Y%m%d")
        if value.endswith("Z"):
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
        return datetime.strptime(value[:15], "%Y%m%dT%H%M%S")  # local or TZID time: taken as local time
    except ValueError:
        return None


def parse_ics(text: str) -> list[dict]:
    events, cur = [], None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT" and cur is not None:
            events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            key, value = line.split(":", 1)
            name = key.split(";")[0]
            if name in ("DTSTART", "DTEND"):
                cur[name.lower()] = _ics_datetime(key, value)
            elif name in ("SUMMARY", "UID", "LOCATION", "RRULE"):
                cur[name.lower()] = value.replace("\\,", ",").replace("\\n", " ").strip()
    return events


def sync_calendar(days: int = 30):
    """Import upcoming events from the ICS link in Settings (Google Calendar: "Secret address in iCal format")."""
    url = settings["calendar_ics_url"].strip()
    if not url:
        return {"error": "no calendar link: add the ICS address in Settings > Calendar"}
    try:
        events = parse_ics(_get(url.replace("webcal://", "https://")).text)
    except httpx.HTTPError as exc:
        return _offline(exc)
    start, end = datetime.now() - timedelta(hours=1), datetime.now() + timedelta(days=days)
    kept, recurring = set(), 0
    for ev in events:
        if ev.get("rrule"):
            recurring += 1  # repeating events are not expanded in this prototype
            continue
        when = ev.get("dtstart")
        if not when or not (start <= when <= end) or not ev.get("uid"):
            continue
        uid = "ics:" + ev["uid"]
        kept.add(uid)
        title = ev.get("summary") or "(sem título)"
        notes = f"Calendário{' · ' + ev['location'] if ev.get('location') else ''}"
        iso_start = when.isoformat(timespec="minutes")
        iso_end = ev["dtend"].isoformat(timespec="minutes") if ev.get("dtend") else None
        row = db.one("SELECT id, start FROM events WHERE external_id = ?", (uid,))
        if row:
            db.execute("UPDATE events SET title=?, start=?, end=?, notes=?, reminded = CASE WHEN start != ? THEN 0 ELSE reminded END "
                       "WHERE id=?", (title, iso_start, iso_end, notes, iso_start, row["id"]))
        else:
            db.execute("INSERT INTO events(title, start, end, notes, remind_minutes, created, external_id) VALUES (?,?,?,?,?,?,?)",
                       (title, iso_start, iso_end, notes, 15, now(), uid))
    removed = 0
    for row in db.all("SELECT id, external_id FROM events WHERE external_id LIKE 'ics:%' AND start >= ?",
                      (start.isoformat(timespec="minutes"),)):
        if row["external_id"] not in kept:  # deleted or moved out of range in the source calendar
            db.execute("DELETE FROM events WHERE id = ?", (row["id"],))
            removed += 1
    db.set_state("calendar_synced", now())
    db.log_action("agenda", f"Calendário sincronizado: {len(kept)} eventos" + (f", {removed} removidos" if removed else ""))
    return {"ok": True, "events": len(kept), "removed": removed, "recurring_skipped": recurring}


def calendar_due() -> bool:
    """Sync at most every 30 minutes (called by the scheduler)."""
    if not settings["calendar_ics_url"].strip():
        return False
    last = db.get_state("calendar_synced")
    return not last or datetime.now() - datetime.fromisoformat(last) > timedelta(minutes=30)

