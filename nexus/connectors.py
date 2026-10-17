"""Integrations hub (v0.18.0).

Every integration (weather, currency, crypto, world clock, translation, holidays, air quality, news, calculator,
unit converter and the ones the user adds) is a connector that sleeps until a message needs it:
  - route(text) recognises, without the model, which connector a message needs and its arguments;
  - call() serves the answer from the cache while it is fresh (rates for an hour, weather for 15 minutes, a
    translation for a month...) and only then goes to the internet; without internet an older copy is used and says so;
  - prepare(text) answers simple questions instantly ("quanto está o dólar?") or hands the fetched data to the model
    inside the message context, so the model answers in one step instead of calling a tool and waiting again.
Nothing runs in the background: a connector is "active" only while it fetches. The cache is a JSON file in the data
folder (only public data: rates, forecasts, holidays, translations)."""
import ast
import json
import math
import operator
import re
import threading
import time
import unicodedata
from datetime import date, datetime, timedelta
from urllib.parse import quote

import httpx

from . import i18n, integrations
from .config import DATA_DIR, settings

CACHE_PATH = DATA_DIR / "cache" / "connectors.json"
_lock = threading.Lock()
_cache: dict | None = None  # {"data": {key: [ts, result]}, "stats": {cid: {...}}}
_active: set = set()


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9%$.,+\-*/^()?' ]+", " ", text)).strip()


def _num(value: float, code: str, decimals: int = 2) -> str:
    s = f"{value:,.{decimals}f}"
    if decimals:
        s = s.rstrip("0").rstrip(".")
    if code in ("pt", "es"):
        s = s.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return s


def _money(value: float, code: str) -> str:
    decimals = 0 if abs(value) >= 1000 else (2 if abs(value) >= 1 else 4)
    s = f"{value:,.{decimals}f}"
    return s.replace(",", "\0").replace(".", ",").replace("\0", ".") if code in ("pt", "es") else s


# ---------------------------------------------------------------- cache + stats
def _load():
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_PATH.read_text("utf-8"))
        except (OSError, ValueError):
            _cache = {}
        _cache.setdefault("data", {})
        _cache.setdefault("stats", {})
    return _cache


def _save():
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = _load()
        if len(data["data"]) > 400:  # keep the newest entries
            data["data"] = dict(sorted(data["data"].items(), key=lambda kv: kv[1][0])[-300:])
        CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
    except OSError:
        pass


def clear_cache():
    global _cache
    with _lock:
        _cache = {"data": {}, "stats": (_cache or {}).get("stats", {})}
        _save()


def _stat(cid: str) -> dict:
    return _load()["stats"].setdefault(cid, {"uses": 0, "net": 0, "cached": 0, "last": 0, "error": "", "until": 0})


# ---------------------------------------------------------------- connectors
class Connector:
    def __init__(self, cid, kind, ttl, provider, parse, fetch, instant=None, needs_net=True, tool=None):
        self.id, self.kind, self.ttl, self.provider = cid, kind, ttl, provider
        self.parse, self.fetch, self.instant, self.needs_net, self.tool = parse, fetch, instant, needs_net, tool


CONNECTORS: dict[str, Connector] = {}


def _register(*args, **kw):
    c = Connector(*args, **kw)
    CONNECTORS[c.id] = c
    return c


def online_allowed() -> bool:
    from . import legal, netprobe

    return legal.accepted() and bool(settings.get("integrations", True)) and netprobe.effective() != "offline"


def enabled(cid: str) -> bool:
    c = CONNECTORS.get(cid)
    if c is None:
        return any(x["id"] == cid and x.get("on", True) for x in settings.get("custom_connectors", []))
    if c.needs_net and not settings.get("integrations", True):
        return False
    return bool(settings.get("connectors", {}).get(cid, True))


def call(cid: str, args: dict) -> dict:
    """Run one connector with the cache. Errors are never cached; without internet an older copy is returned."""
    c = CONNECTORS.get(cid) or _custom_connector(cid)
    if c is None:
        return {"error": f"unknown integration {cid}"}
    if not enabled(cid):
        return {"error": f"the '{cid}' integration is turned off (Settings > Integrations)"}
    key = cid + ":" + json.dumps(args, sort_keys=True, ensure_ascii=False, default=str) + ":" + i18n.lang()
    with _lock:
        st = _stat(cid)
        st["uses"] += 1
        st["last"] = time.time()
        hit = _load()["data"].get(key)
    if c.ttl and hit and time.time() - hit[0] < c.ttl:
        with _lock:
            st["cached"] += 1
        return {**hit[1], "cached_at": datetime.fromtimestamp(hit[0]).strftime("%H:%M")}
    if c.needs_net and not online_allowed():
        if hit:  # offline: the last copy, marked as such
            return {**hit[1], "stale_from": datetime.fromtimestamp(hit[0]).strftime("%Y-%m-%d %H:%M")}
        return {"error": "NEXUS is offline (no internet or the integrations are off)"}
    _active.add(cid)
    try:
        result = c.fetch(**args)
    except httpx.HTTPError as exc:
        result = integrations._offline(exc)
    except Exception as exc:  # a broken answer from a service must never break the conversation
        result = {"error": f"{type(exc).__name__}: {exc}"[:200]}
    finally:
        _active.discard(cid)
    with _lock:
        if c.needs_net:
            st["net"] += 1
        if isinstance(result, dict) and "error" in result:
            st["error"] = str(result["error"])[:160]
            if c.needs_net:
                from . import netprobe

                netprobe.report_failure()
        else:
            st["error"] = ""
            if c.ttl:
                _load()["data"][key] = [time.time(), result]
                st["until"] = time.time() + c.ttl
        _save()
    return result


# ---------------------------------------------------------------- places (shared by weather, air, clock)
def _place(city: str) -> dict | None:
    city = city.strip(" .,!?")
    if not city:
        return None
    key = "geo:" + _norm(city)
    hit = _load()["data"].get(key)
    if hit and time.time() - hit[0] < 30 * 86400:
        return hit[1]
    if not online_allowed():
        return hit[1] if hit else None
    # Names are searched in one language ("New York" in Portuguese found York, Nebraska): several results, the exact
    # name with the largest population wins, else the same in English.
    exact, first = [], []
    for code in dict.fromkeys((i18n.lang(), "en")):
        found = integrations._get("https://geocoding-api.open-meteo.com/v1/search", name=city, count=5,
                                  language=code).json().get("results") or []
        exact += [r for r in found if _norm(r["name"]) == _norm(city)]
        first = first or found[:1]
    if not (exact or first):
        return None
    p = max(exact or first, key=lambda r: r.get("population") or 0)
    place = {"name": p["name"], "country": p.get("country", ""), "admin": p.get("admin1", ""),
             "lat": p["latitude"], "lon": p["longitude"], "tz": p.get("timezone", ""), "cc": p.get("country_code", "")}
    with _lock:
        _load()["data"][key] = [time.time(), place]
    return place


TIME_WORDS_RX = (r"hoje|amanha|depois de amanha|agora|essa semana|esta semana|nesta semana|semana que vem|fim de semana|"
                 r"final de semana|today|tomorrow|now|tonight|this week|next week|this weekend|weekend|hoy|manana|ahora|"
                 r"pasado manana|la semana|fin de semana|a noite|a tarde|de manha|la fora|aqui")
NOT_PLACE = re.compile(rf"^({TIME_WORDS_RX}|casa|home|geral|tempo|dia|graus|reais|dolares|celsius|fahrenheit|"
                       r"o|a|os|as|um|uma|el|la|the|minha cidade|my city|mi ciudad|momento|rua|street|calle|geral|general)$")


def _city(raw: str) -> str:
    """'como está o tempo em São Paulo amanhã?' -> 'São Paulo' (the original spelling, for the geocoder)."""
    for m in re.finditer(r"\b(?:em|no|na|in|at|en|para|pra|for)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\- ]{1,40}?)\s*"
                         rf"(?=\b(?:{TIME_WORDS_RX.replace('amanha', 'amanh[ãa]').replace('manana', 'ma[ñn]ana')})\b|"
                         r"[?.!,;]|$)", raw, re.I):
        city = re.sub(r"^(o|a|el|la|the)\s+", "", m.group(1).strip(), flags=re.I)
        if not NOT_PLACE.match(_norm(city)):
            return city
    return ""


# ---------------------------------------------------------------- weather
WEATHER_RX = re.compile(
    r"\b(clima|previsao( do tempo)?|chover|chove|chuva|chovendo|temperatura|weather|forecast|rain(ing|y)?|temperature|"
    r"llover|llueve|lluvia|pronostico|que tiempo|tiempo hace|hara (frio|calor)|como (esta|ta|vai estar|vai ficar|sera|"
    r"estara) o tempo|o tempo (hoje|amanha|agora|la fora|aqui)|tempo la fora|faz(endo)? (frio|calor)|"
    r"esta (frio|calor)|vai (fazer|estar) (frio|calor)|(hot|cold) outside|umbrella|guarda ?chuva|paraguas|"
    r"sensacao termica|nascer do sol|por do sol|sol (se poe|nasce|vai nascer|vai se por)|sunrise|sunset|sun (rise|set)s?|"
    r"amanecer|atardecer|puesta del sol|sale el sol|se pone el sol)\b")
NOT_WEATHER = re.compile(r"\b(febre|fever|fiebre|corpo|body|cuerpo|cpu|gpu|placa|processador|processor|forno|oven|horno|"
                         r"agua|water|motor|engine|chuva de ideias)\b")
SUN_RX = re.compile(r"\b(nascer do sol|por do sol|sunrise|sunset|sun (rise|set)s?|amanecer|atardecer|puesta del sol|"
                    r"sol (se poe|nasce|vai nascer|vai se por)|sale el sol|se pone el sol)\b")


def _days_wanted(norm: str) -> int:
    if re.search(r"\b(semana|week|fim de semana|final de semana|weekend|proximos dias|next days|proximos dias)\b", norm):
        return 7
    if re.search(r"\b(depois de amanha|day after tomorrow|pasado manana)\b", norm):
        return 3
    return 2 if re.search(r"\b(amanha|tomorrow|manana)\b", norm) else 1


def parse_weather(norm, raw, strict=True):
    if strict and (not WEATHER_RX.search(norm) or NOT_WEATHER.search(norm)):
        return None
    city = _city(raw) or settings.get("home_city", "")
    if not city:
        return None  # the model asks which city
    return {"city": city, "days": _days_wanted(norm)}


def fetch_weather(city="", days=1):
    place = _place(city or settings.get("home_city", ""))
    if not place:
        return {"error": f"city not found: {city}"}
    days = max(1, min(int(days or 1), 7))
    fc = integrations._get(
        "https://api.open-meteo.com/v1/forecast", latitude=place["lat"], longitude=place["lon"],
        current="temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
        daily="weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
        timezone="auto", forecast_days=max(days, 2)).json()
    cur, d = fc["current"], fc["daily"]
    return {
        "place": ", ".join(x for x in (place["name"], place["admin"], place["country"]) if x),
        "city": place["name"],
        "now": {"temp_c": cur["temperature_2m"], "feels_like_c": cur["apparent_temperature"],
                "humidity_pct": cur["relative_humidity_2m"], "wind_kmh": cur["wind_speed_10m"],
                "conditions": integrations._describe(cur["weather_code"]), "wmo": cur["weather_code"]},
        "forecast": [{"date": t, "min_c": lo, "max_c": hi, "rain_chance_pct": rain, "conditions": integrations._describe(code), "wmo": code,
                      "sunrise": sr[11:16], "sunset": ss[11:16]}
                     for t, lo, hi, rain, code, sr, ss in zip(d["time"], d["temperature_2m_min"], d["temperature_2m_max"],
                                                              d["precipitation_probability_max"], d["weather_code"],
                                                              d["sunrise"], d["sunset"])][:max(days, 2)],
        "source": "Open-Meteo",
    }


def _cond(entry, code):
    """Conditions in the language of the message (the data may be cached in another one)."""
    wmo = entry.get("wmo")
    if wmo is None:
        return entry["conditions"]
    return integrations.WMO.get(int(wmo), (entry["conditions"],) * 3)[integrations._LANG_IDX.get(code, 0)]


def instant_weather(data, args, code, norm):
    if args["days"] > 3 or "forecast" not in data:
        return None  # a week: the model summarises
    T = TEXTS[code]
    if SUN_RX.search(norm):
        today = data["forecast"][0]
        return T["sun"].format(city=data["city"], rise=today["sunrise"], set=today["sunset"])
    if args["days"] >= 2:
        d = data["forecast"][args["days"] - 1]
        when = T["tomorrow"] if args["days"] == 2 else T["after_tomorrow"]
        return T["weather_day"].format(when=when, city=data["city"], cond=_cond(d, code), lo=_num(d["min_c"], code, 0),
                                       hi=_num(d["max_c"], code, 0), rain=d["rain_chance_pct"] or 0)
    now, today = data["now"], data["forecast"][0]
    return T["weather_now"].format(city=data["city"], temp=_num(now["temp_c"], code, 0), cond=_cond(now, code),
                                   feels=_num(now["feels_like_c"], code, 0), lo=_num(today["min_c"], code, 0),
                                   hi=_num(today["max_c"], code, 0), rain=today["rain_chance_pct"] or 0)


# ---------------------------------------------------------------- air quality
AIR_RX = re.compile(r"\b(qualidade do ar|poluicao|air quality|pollution|calidad del aire|contaminacion|indice uv|"
                    r"uv index|indice de uv|raios uv|radiacao uv|radiacion uv)\b")


def parse_air(norm, raw, strict=True):
    if strict and not AIR_RX.search(norm):
        return None
    city = _city(raw) or settings.get("home_city", "")
    return {"city": city} if city else None


def fetch_air(city=""):
    place = _place(city)
    if not place:
        return {"error": f"city not found: {city}"}
    aq = integrations._get("https://air-quality-api.open-meteo.com/v1/air-quality", latitude=place["lat"],
                           longitude=place["lon"], current="european_aqi,us_aqi,pm2_5,pm10,uv_index", timezone="auto").json()
    cur = aq["current"]
    return {"city": place["name"], "european_aqi": cur.get("european_aqi"), "us_aqi": cur.get("us_aqi"),
            "pm2_5": cur.get("pm2_5"), "pm10": cur.get("pm10"), "uv_index": cur.get("uv_index"),
            "source": "Open-Meteo Air Quality (CAMS)"}


def instant_air(data, args, code, norm):
    if data.get("european_aqi") is None:
        return None
    aqi = data["european_aqi"]
    level = TEXTS[code]["aqi"][min(5, int(aqi // 20))] if aqi < 100 else TEXTS[code]["aqi"][5]
    return TEXTS[code]["air"].format(city=data["city"], level=level, aqi=round(aqi), pm=_num(data["pm2_5"] or 0, code, 0),
                                     uv=_num(data["uv_index"] or 0, code, 0))


# ---------------------------------------------------------------- world clock
CLOCK_RX = re.compile(r"\b(que horas? (sao|e|son|es)|what time is it|what s the time|whats the time|horario (em|de|in|en|"
                      r"no|na)|hora (em|in|en|no|na)|time (in|at) |fuso horario|time ?zone|zona horaria|"
                      r"diferenca de (fuso|horario)|time difference|diferencia horaria)\b")


def parse_clock(norm, raw, strict=True):
    if strict and not CLOCK_RX.search(norm):
        return None
    city = _city(raw)
    return {"city": city} if city else None  # no place: the local time is already in the context


def fetch_clock(city=""):
    place = _place(city)
    if not place:
        return {"error": f"place not found: {city}"}
    fc = integrations._get("https://api.open-meteo.com/v1/forecast", latitude=place["lat"], longitude=place["lon"],
                           current="temperature_2m", timezone="auto").json()
    return {"city": place["name"], "country": place["country"], "timezone": fc.get("timezone", place["tz"]),
            "utc_offset_seconds": fc.get("utc_offset_seconds", 0), "source": "Open-Meteo"}


def _clock_now(data) -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc) + timedelta(seconds=data["utc_offset_seconds"])


def instant_clock(data, args, code, norm):
    there = _clock_now(data)
    local_off = -time.altzone if time.localtime().tm_isdst > 0 else -time.timezone
    diff = (data["utc_offset_seconds"] - local_off) / 3600
    diff_s = ("+" if diff > 0 else "") + (_num(diff, code, 1) if diff % 1 else str(int(diff)))
    T = TEXTS[code]
    return T["clock"].format(city=data["city"], country=data["country"], time=there.strftime("%H:%M"),
                             day=i18n.WEEKDAYS[code][there.weekday()],
                             diff=T["clock_same"] if diff == 0 else T["clock_diff"].format(h=diff_s))


# ---------------------------------------------------------------- currency
CURRENCIES = [  # (code, names after _norm) - the more specific first
    ("CAD", r"dolar(es)? canadense(s)?|canadian dollars?|dolar(es)? canadiense(s)?|cad"),
    ("AUD", r"dolar(es)? australiano(s)?|australian dollars?|aud"),
    ("NZD", r"dolar(es)? neozelandes(es)?|new zealand dollars?|nzd"),
    ("HKD", r"dolar(es)? de hong kong|hong kong dollars?|hkd"),
    ("SGD", r"dolar(es)? de singapura|singapore dollars?|sgd"),
    ("MXN", r"pesos? mexicanos?|mexican pesos?|mxn"),
    ("USD", r"dolar(es)?( americanos?)?|dollars?|usd|us\$|verdinhas?"),
    ("EUR", r"euros?|eur"),
    ("BRL", r"reais|real brasileiro|brazilian reais?|brl|r\$"),
    ("GBP", r"libras?( esterlinas?)?|pounds?( sterling)?|gbp"),
    ("JPY", r"ienes?|yen(es)?|jpy"),
    ("CNY", r"yuan(es)?|renminbi|cny"),
    ("CHF", r"francos? suicos?|swiss francs?|chf"),
    ("INR", r"rupias?( indianas?)?|rupees?|inr"),
    ("KRW", r"won(s)?|krw"),
    ("TRY", r"liras? turcas?|turkish liras?|try"),
    ("ZAR", r"rands?|zar"),
    ("SEK", r"coroas? suecas?|swedish kronor|sek"),
    ("NOK", r"coroas? norueguesas?|norwegian kroner|nok"),
    ("DKK", r"coroas? dinamarquesas?|danish kroner|dkk"),
    ("PLN", r"zlotys?|pln"),
]
CURRENCY_WORDS = {"pt": {}, "en": {}, "es": {}}
QUOTE_RX = re.compile(r"\b(cotacao|quanto (esta|ta|vale|custa|e|sai|da)|quant[oa]s? \w+ (sao|e|da|valem|vale)|valor|preco|price|rate|exchange|"
                      r"how much|worth|cuanto|cotizacion|tipo de cambio|a como|converte|converter|convert|conversion|"
                      r"em reais|hoje|today|hoy|esta valendo|ta valendo)\b|\?")
NOT_QUOTE = re.compile(r"\b(gastei|paguei|recebi|ganhei|spent|spend|paid|received|gaste|pague|recibi|registra|anota|"
                       r"tenho|have|tengo|sobrou|economizei|saved|ahorre|orcamento|budget|presupuesto|gasto|gastar|"
                       r"lembra|remind|recuerda|devo|deveria|should i|invest|investir|comprar|vender|buy|sell)\b")


def home_currency() -> str:
    return (settings.get("home_currency") or {"pt": "BRL", "en": "USD", "es": "USD"}[i18n.lang()]).upper()


def _currency_hits(norm):
    hits, taken = [], []
    for code, words in CURRENCIES:
        for m in re.finditer(rf"\b({words})(?![a-z])", norm):
            if any(a <= m.start() < b for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            hits.append((m.start(), code, m))
    return sorted(hits)


def parse_currency(norm, raw, strict=True):
    if strict and (not QUOTE_RX.search(norm) or NOT_QUOTE.search(norm)):
        return None
    hits = _currency_hits(norm)
    if not hits:
        return None
    amount, src = 1.0, None
    for pos, code, m in hits:
        before = re.search(r"(\d+(?:[.,]\d+)*)\s*(mil\s+)?$", norm[:pos].rstrip())
        if before:
            amount = float(before.group(1).replace(".", "").replace(",", ".") if "," in before.group(1)
                           else before.group(1).replace(",", ""))
            amount *= 1000 if before.group(2) else 1
            src = code
            break
    codes = [c for _, c, _ in hits]
    src = src or codes[0]
    others = [c for c in codes if c != src]
    dst = others[0] if others else (home_currency() if src != home_currency() else ("USD" if src != "USD" else "EUR"))
    return {"amount": amount, "from_currency": src, "to_currency": dst}


def fetch_currency(amount=1, from_currency="USD", to_currency="BRL"):
    return integrations.convert_currency(amount, from_currency, to_currency)


SYMBOLS = {"BRL": "R$", "USD": "US$", "EUR": "€", "GBP": "£", "JPY": "¥"}
CUR_NAMES = {  # code: (singular, plural)
    "pt": {"USD": ("dólar", "dólares"), "EUR": ("euro", "euros"), "BRL": ("real", "reais"), "GBP": ("libra", "libras"),
           "JPY": ("iene", "ienes"), "CAD": ("dólar canadense", "dólares canadenses"), "MXN": ("peso mexicano", "pesos mexicanos"),
           "CHF": ("franco suíço", "francos suíços"), "CNY": ("yuan", "yuans"), "AUD": ("dólar australiano", "dólares australianos")},
    "en": {"USD": ("dollar", "dollars"), "EUR": ("euro", "euros"), "BRL": ("Brazilian real", "Brazilian reais"),
           "GBP": ("pound", "pounds"), "JPY": ("yen", "yen"), "CAD": ("Canadian dollar", "Canadian dollars"),
           "MXN": ("Mexican peso", "Mexican pesos"), "CHF": ("Swiss franc", "Swiss francs"), "CNY": ("yuan", "yuan"),
           "AUD": ("Australian dollar", "Australian dollars")},
    "es": {"USD": ("dólar", "dólares"), "EUR": ("euro", "euros"), "BRL": ("real", "reales"), "GBP": ("libra", "libras"),
           "JPY": ("yen", "yenes"), "CAD": ("dólar canadiense", "dólares canadienses"), "MXN": ("peso mexicano", "pesos mexicanos"),
           "CHF": ("franco suizo", "francos suizos"), "CNY": ("yuan", "yuanes"), "AUD": ("dólar australiano", "dólares australianos")},
}


def _amount_name(amount: float, cur: str, code: str) -> str:
    shown = _money(amount, code)
    shown = shown[:-3] if shown.endswith((",00", ".00")) else shown
    names = CUR_NAMES[code].get(cur)
    return f"{shown} {names[0 if amount == 1 else 1]}" if names else f"{shown} {cur}"


def _priced(value: float, cur: str, code: str) -> str:
    return f"{SYMBOLS[cur]} {_money(value, code)}" if cur in SYMBOLS else f"{_money(value, code)} {cur}"


def instant_currency(data, args, code, norm):
    if data.get("result") is None:
        return None
    d = data.get("rate_date", "")
    when = f"{d[8:10]}/{d[5:7]}" if code != "en" else f"{d[5:7]}/{d[8:10]}"
    return TEXTS[code]["currency"].format(amount=_amount_name(args["amount"], args["from_currency"], code),
                                          result=_priced(data["result"], args["to_currency"], code), date=when)


# ---------------------------------------------------------------- crypto
COINS = [("bitcoin", r"bitcoins?|btc"), ("ethereum", r"ethereum|ether|eth"), ("solana", r"solana"),
         ("ripple", r"xrp|ripple"), ("dogecoin", r"dogecoin|doge"), ("cardano", r"cardano"),
         ("litecoin", r"litecoin|ltc"), ("binancecoin", r"bnb|binance coin"), ("tether", r"tether|usdt")]
COIN_NAMES = {"bitcoin": "bitcoin", "ethereum": "ethereum", "solana": "solana", "ripple": "XRP", "dogecoin": "dogecoin",
              "cardano": "cardano", "litecoin": "litecoin", "binancecoin": "BNB", "tether": "tether (USDT)"}


def parse_crypto(norm, raw, strict=True):
    if strict and (not QUOTE_RX.search(norm) or NOT_QUOTE.search(norm)):
        return None
    for cid, words in COINS:
        if re.search(rf"\b({words})\b", norm):
            hits = [c for _, c, _ in _currency_hits(norm)]
            return {"coin": cid, "vs": (hits[0] if hits else home_currency()).lower()}
    return None


def fetch_crypto(coin="bitcoin", vs="brl"):
    data = integrations._get("https://api.coingecko.com/api/v3/simple/price", ids=coin, vs_currencies=vs,
                             include_24hr_change="true").json()
    if coin not in data:
        return {"error": f"unknown coin {coin}"}
    return {"coin": coin, "currency": vs.upper(), "price": data[coin].get(vs),
            "change_24h_pct": round(data[coin].get(f"{vs}_24h_change") or 0, 2),
            "source": "CoinGecko (market price; not investment advice)"}


def instant_crypto(data, args, code, norm):
    if data.get("price") is None:
        return None
    ch = data["change_24h_pct"]
    return TEXTS[code]["crypto"].format(coin=COIN_NAMES.get(data["coin"], data["coin"]),
                                        price=_priced(data["price"], data["currency"], code),
                                        change=("+" if ch >= 0.05 else "") + (_num(ch, code, 1) if abs(ch) >= 0.05 else "0"))


# ---------------------------------------------------------------- translation
LANGS = [("en", r"ingles|english"), ("pt", r"portugues|portuguese"), ("es", r"espanhol|spanish|espanol|castelhano|castellano"),
         ("fr", r"frances|french"), ("de", r"alemao|german|aleman"), ("it", r"italiano|italian"),
         ("ja", r"japones|japanese"), ("zh-CN", r"chines|chinese|chino|mandarim|mandarin"), ("ko", r"coreano|korean"),
         ("ru", r"russo|russian|ruso"), ("ar", r"arabe|arabic"), ("nl", r"holandes|dutch|neerlandes"),
         ("tr", r"turco|turkish"), ("pl", r"polones|polish|polaco"), ("el", r"grego|greek|griego"),
         ("he", r"hebraico|hebrew|hebreo"), ("hi", r"hindi"), ("sv", r"sueco|swedish"), ("la", r"latim|latin")]
LANG_LABEL = {"pt": {"en": "inglês", "pt": "português", "es": "espanhol", "fr": "francês", "de": "alemão", "it": "italiano",
                     "ja": "japonês", "zh-CN": "chinês", "ko": "coreano", "ru": "russo", "ar": "árabe", "nl": "holandês",
                     "tr": "turco", "pl": "polonês", "el": "grego", "he": "hebraico", "hi": "hindi", "sv": "sueco", "la": "latim"},
              "en": {"en": "English", "pt": "Portuguese", "es": "Spanish", "fr": "French", "de": "German", "it": "Italian",
                     "ja": "Japanese", "zh-CN": "Chinese", "ko": "Korean", "ru": "Russian", "ar": "Arabic", "nl": "Dutch",
                     "tr": "Turkish", "pl": "Polish", "el": "Greek", "he": "Hebrew", "hi": "Hindi", "sv": "Swedish", "la": "Latin"},
              "es": {"en": "inglés", "pt": "portugués", "es": "español", "fr": "francés", "de": "alemán", "it": "italiano",
                     "ja": "japonés", "zh-CN": "chino", "ko": "coreano", "ru": "ruso", "ar": "árabe", "nl": "neerlandés",
                     "tr": "turco", "pl": "polaco", "el": "griego", "he": "hebreo", "hi": "hindi", "sv": "sueco", "la": "latín"}}
TRANSLATE_RX = [
    re.compile(r"^\W*(?:nexus\W+)?(?:traduz(?:a|ir|e)?|translate|traduce|traducir|traduzca)\s+(?:isso|isto|this|esto)?\s*:?\s*"
               r"[\"“'«]?(.+?)[\"”'»]?\s+(?:para|pro|pra|to|into|al|a|en|em)\s+(?:o\s+|el\s+)?([A-Za-zÀ-ÿ]+)\W*$", re.I),
    re.compile(r"\bcomo (?:(?:é|e) que )?(?:se )?(?:diz|fala|escreve|falo|digo|dice|escribe|digo)\s+[\"“'«]?(.+?)[\"”'»]?\s+"
               r"(?:em|en|no|na)\s+([A-Za-zÀ-ÿ]+)\W*$", re.I),
    re.compile(r"\bhow (?:do (?:you|i) )?(?:say|write)\s+[\"“']?(.+?)[\"”']?\s+in\s+([A-Za-z]+)\W*$", re.I),
    re.compile(r"\bwhat(?:'s| is) [\"“']?(.+?)[\"”']? in ([A-Za-z]+)\W*$", re.I),
]


def _lang_code(word: str) -> str | None:
    w = _norm(word)
    return next((c for c, rx in LANGS if re.fullmatch(rx, w)), None)


def parse_translate(norm, raw, strict=True):
    for rx in TRANSLATE_RX:
        m = rx.search(raw.strip())
        if m and _lang_code(m.group(2)):
            text = m.group(1).strip(" \"'“”«»")
            if 0 < len(text) <= 400:
                src = i18n.detect(text) or i18n.detect(raw) or i18n.lang()
                return {"text": text, "source": src, "target": _lang_code(m.group(2))}
    return None


def fetch_translate(text="", source="pt", target="en"):
    if source == target:
        source = "en" if target != "en" else "pt"
    data = integrations._get("https://api.mymemory.translated.net/get", q=text, langpair=f"{source}|{target}").json()
    out = (data.get("responseData") or {}).get("translatedText") or ""
    if not out or data.get("responseStatus") not in (200, "200"):
        return {"error": f"translation unavailable: {data.get('responseDetails', '')}"[:160]}
    return {"text": text, "translation": out, "source": source, "target": target, "provider": "MyMemory"}


def instant_translate(data, args, code, norm):
    if not data.get("translation"):
        return None
    return TEXTS[code]["translate"].format(text=args["text"], lang=LANG_LABEL[code].get(args["target"], args["target"]),
                                           out=data["translation"])


# ---------------------------------------------------------------- holidays
HOLIDAY_RX = re.compile(r"\b(feriados?|holidays?|festivos?|dias? festivos?|dia de folga|bank holidays?)\b")
NEXT_HOLIDAY_RX = re.compile(r"\b(proximo feriado|next (public |bank )?holiday|proximo festivo|quando e o (proximo )?feriado|"
                             r"when is the next holiday|cuando es el proximo festivo|tem feriado)\b")


def home_country() -> str:
    return (settings.get("home_country") or {"pt": "BR", "en": "US", "es": "ES"}[i18n.lang()]).upper()


def parse_holidays(norm, raw, strict=True):
    if strict and not HOLIDAY_RX.search(norm):
        return None
    return {"country": home_country()}


def fetch_holidays(country="BR"):
    today = date.today()
    rows = []
    for year in (today.year, today.year + 1):
        rows += integrations._get(f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country}").json()
    upcoming = [{"date": h["date"], "name": h["localName"], "name_en": h["name"], "national": bool(h.get("global", True))}
                for h in rows if h["date"] >= today.isoformat()]
    return {"country": country, "upcoming": upcoming[:8], "source": "Nager.Date"}


def instant_holidays(data, args, code, norm):
    nxt = next((h for h in data.get("upcoming", []) if h["national"]), None)
    if not nxt or not NEXT_HOLIDAY_RX.search(norm):
        return None
    d = date.fromisoformat(nxt["date"])
    days = (d - date.today()).days
    name = nxt["name"] if code != "en" or data["country"] in ("US", "GB", "CA", "AU") else nxt["name_en"]
    when = TEXTS[code]["today"] if days == 0 else TEXTS[code]["in_days"].format(n=days)
    return TEXTS[code]["holiday"].format(name=name, day=i18n.WEEKDAYS[code][d.weekday()],
                                         date=d.strftime("%d/%m") if code != "en" else d.strftime("%m/%d"), when=when)


# ---------------------------------------------------------------- news (the model summarises)
NEWS_RX = re.compile(r"\b(noticias?|manchetes?|news|headlines|titulares|o que (esta acontecendo|aconteceu) no mundo|"
                     r"what s happening in the world|que paso en el mundo)\b")


def parse_news(norm, raw, strict=True):
    if strict and not NEWS_RX.search(norm):
        return None
    m = re.search(r"\b(?:noticias?|news|manchetes?|headlines|titulares)\s+(?:sobre|about|de|do|da|dos|das|on|acerca de|del)\s+"
                  r"(.+?)\s*\??$", norm)
    topic = (m.group(1) if m else "").strip()
    topic = "" if re.fullmatch(rf"({TIME_WORDS_RX}|o dia|the day|el dia|mundo|world)", topic) else topic
    return {"topic": topic, "limit": 5}


def fetch_news(topic="", limit=5):
    return integrations.get_news(topic, limit)


def instant_news(data, args, code, norm):
    items = data.get("headlines") or []
    if not items:
        return None
    lines = [f"{i}. {h['title']}" + (f" ({h['source']})" if h.get("source") else "") for i, h in enumerate(items[:5], 1)]
    head = TEXTS[code]["news_topic"].format(topic=args["topic"]) if args.get("topic") else TEXTS[code]["news"]
    return "\n".join([head, *lines])


# ---------------------------------------------------------------- calculator (local)
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Mod: operator.mod}
CALC_START = re.compile(r"^\W*(?:nexus\W+)?(?:quanto (?:e|que e|da|eh|seria|fica)|calcul[ae]r?|what's|what s|whats|what is|"
                        r"how much is|calculate|compute|cuanto (?:es|da|son)|calcula|faz a conta(?: de)?|conta)\s+")


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "sqrt" and len(node.args) == 1:
        return math.sqrt(_eval(node.args[0]))
    raise ValueError("not arithmetic")


def parse_calc(norm, raw, strict=True):
    m = CALC_START.match(norm)
    if strict and not m and not re.match(r"^\W*(\d|\(|raiz|square root|-\d)", norm):
        return None  # "raiz quadrada de 144", "12*7": only when the whole message is arithmetic
    expr = (norm[m.end():] if m else norm).strip(" ?.=")
    shown = expr
    e = re.sub(r"(\d)\.(\d{3})(?!\d)", r"\1\2", expr) if i18n.lang() != "en" else expr.replace(",", "")
    e = re.sub(r"(\d),(\d)", r"\1.\2", e)
    e = re.sub(r"(\d+(?:\.\d+)?)\s*(?:%|por cento|percent|por ciento)\s*(?:de|of|del)\s*", r"(\1/100)*", e)
    e = re.sub(r"\b(?:ao|al) quadrado\b|\bsquared\b|\bal cuadrado\b", "**2", e)
    e = re.sub(r"\b(?:ao|al) cubo\b|\bcubed\b", "**3", e)
    e = re.sub(r"\b(?:a )?raiz (?:quadrada |cuadrada )?(?:de )?|\bsquare root of ", "sqrt ", e)
    e = re.sub(r"sqrt\s*(\d+(?:\.\d+)?)", r"sqrt(\1)", e)
    for words, op in ((r"dividido (?:por|entre)|divided by|sobre|over", "/"),
                      (r"elevado (?:a|ao)|to the power of|elevado al?", "**"),
                      (r"multiplicado por|multiplied by|vezes|times|x|por", "*"), (r"mais|plus|mas", "+"),
                      (r"menos|minus", "-")):
        e = re.sub(rf"\s*\b(?:{words})\b\s*", f" {op} ", e)
    e = e.replace("^", "**").replace("÷", "/")
    if not re.fullmatch(r"[\d\s.+\-*/()sqrt]+", e) or not re.search(r"[+\-*/]|sqrt", e) or not re.search(r"\d", e):
        return None
    try:
        value = _eval(ast.parse(e.strip(), mode="eval"))
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError, TypeError):
        return None
    return {"expression": shown, "value": value}


def fetch_calc(expression="", value=0.0):
    return {"expression": expression, "result": value}


def instant_calc(data, args, code, norm):
    v = data["result"]
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        v = int(v)
    shown = _num(v, code, 0) if isinstance(v, int) else _num(round(v, 4), code, 4)
    return TEXTS[code]["calc"].format(expr=data["expression"], result=shown)


# ---------------------------------------------------------------- unit converter (local)
UNITS = {  # symbol: (dimension, factor to base, names regex after _norm)
    "km": ("len", 1000, r"km|quilometros?|kilometers?|kilometres?|kilometros?"),
    "m": ("len", 1, r"m|metros?|meters?|metres?"),
    "cm": ("len", 0.01, r"cm|centimetros?|centimeters?|centimetres?"),
    "mm": ("len", 0.001, r"mm|milimetros?|millimeters?|millimetres?"),
    "mi": ("len", 1609.344, r"mi|milhas?|miles?|millas?"),
    "ft": ("len", 0.3048, r"ft|pes|pe|feet|foot|pies?"),
    "in": ("len", 0.0254, r"polegadas?|inch(es)?|pulgadas?"),
    "yd": ("len", 0.9144, r"yd|jardas?|yards?|yardas?"),
    "kg": ("mass", 1, r"kg|quilos?|quilogramas?|kilograms?|kilos?|kilogramos?"),
    "g": ("mass", 0.001, r"g|gramas?|grams?|gramos?"),
    "lb": ("mass", 0.45359237, r"lbs?|libras?|pounds?"),
    "oz": ("mass", 0.028349523125, r"oz|oncas?|ounces?|onzas?"),
    "t": ("mass", 1000, r"toneladas?|tons?|tonnes?"),
    "l": ("vol", 1, r"l|litros?|liters?|litres?"),
    "ml": ("vol", 0.001, r"ml|mililitros?|milliliters?|millilitres?"),
    "gal": ("vol", 3.785411784, r"gal|galao|galoes|gallons?|galon(es)?"),
    "km/h": ("speed", 1, r"km/h|kmh|quilometros por hora|kilometers per hour|kilometros por hora"),
    "mph": ("speed", 1.609344, r"mph|milhas por hora|miles per hour|millas por hora"),
    "m/s": ("speed", 3.6, r"m/s|metros por segundo|meters per second"),
    "kn": ("speed", 1.852, r"nos|knots?|nudos?"),
    "GB": ("data", 1, r"gb|gigas?|gigabytes?"), "MB": ("data", 1 / 1024, r"mb|megas?|megabytes?"),
    "TB": ("data", 1024, r"tb|terabytes?|teras?"), "KB": ("data", 1 / 1024 ** 2, r"kb|kilobytes?"),
    "°C": ("temp", None, r"(graus )?celsius|c|graus centigrados|degrees celsius|grados celsius|°c"),
    "°F": ("temp", None, r"(graus )?fahrenheit|f|degrees fahrenheit|grados fahrenheit|°f"),
    "K": ("temp", None, r"kelvin|k"),
}
UNIT_NAME = {"pt": {"km": "quilômetros", "m": "metros", "cm": "centímetros", "mm": "milímetros", "mi": "milhas", "ft": "pés",
                    "in": "polegadas", "yd": "jardas", "kg": "quilos", "g": "gramas", "lb": "libras", "oz": "onças",
                    "t": "toneladas", "l": "litros", "ml": "mililitros", "gal": "galões", "km/h": "km/h", "mph": "milhas por hora",
                    "m/s": "metros por segundo", "kn": "nós", "°C": "graus Celsius", "°F": "graus Fahrenheit", "K": "kelvin"},
             "en": {"km": "kilometers", "m": "meters", "cm": "centimeters", "mm": "millimeters", "mi": "miles", "ft": "feet",
                    "in": "inches", "yd": "yards", "kg": "kilograms", "g": "grams", "lb": "pounds", "oz": "ounces",
                    "t": "tonnes", "l": "liters", "ml": "milliliters", "gal": "gallons", "km/h": "km/h", "mph": "mph",
                    "m/s": "meters per second", "kn": "knots", "°C": "degrees Celsius", "°F": "degrees Fahrenheit", "K": "kelvin"},
             "es": {"km": "kilómetros", "m": "metros", "cm": "centímetros", "mm": "milímetros", "mi": "millas", "ft": "pies",
                    "in": "pulgadas", "yd": "yardas", "kg": "kilos", "g": "gramos", "lb": "libras", "oz": "onzas",
                    "t": "toneladas", "l": "litros", "ml": "mililitros", "gal": "galones", "km/h": "km/h", "mph": "millas por hora",
                    "m/s": "metros por segundo", "kn": "nudos", "°C": "grados Celsius", "°F": "grados Fahrenheit", "K": "kelvin"}}
for _code in ("GB", "MB", "TB", "KB"):
    for _l in UNIT_NAME.values():
        _l[_code] = _code
_UNIT_ALT = "(?:" + "|".join(sorted({w for _, _, rx in UNITS.values() for w in rx.replace("(", "(?:").split("|")}, key=len, reverse=True)) + ")"


def _unit(word: str) -> str | None:
    w = word.strip()
    return next((sym for sym, (_, _, rx) in UNITS.items() if re.fullmatch(rf"(?:{rx})", w)), None)


def parse_units(norm, raw, strict=True):
    n = norm.replace("º", "°")
    num = r"(-?\d+(?:[.,]\d+)?)"
    m = re.search(rf"{num}\s*({_UNIT_ALT})\s+(?:em|para|pra|in|to|into|en|a|=)\s+(?:quantos?\s+|how many\s+|cuantos?\s+)?"
                  rf"({_UNIT_ALT})\b", n)
    if m:
        value, a, b = m.group(1), m.group(2), m.group(3)
    else:
        m = re.search(rf"\b(?:quantos?|quantas?|how many|cuantos?|cuantas?)\s+({_UNIT_ALT})\s+(?:sao|tem|ha|cabem|in|are in|"
                      rf"are there in|make|son|hay|e|es|da|equivalem a)\s+{num}\s*({_UNIT_ALT})\b", n)
        if not m:
            return None
        b, value, a = m.group(1), m.group(2), m.group(3)
    ua, ub = _unit(a), _unit(b)
    if not ua or not ub or ua == ub or UNITS[ua][0] != UNITS[ub][0]:
        return None
    return {"value": float(value.replace(",", ".")), "from": ua, "to": ub}


def _convert(value, ua, ub):
    dim = UNITS[ua][0]
    if dim != "temp":
        return value * UNITS[ua][1] / UNITS[ub][1]
    c = {"°C": value, "°F": (value - 32) * 5 / 9, "K": value - 273.15}[ua]
    return {"°C": c, "°F": c * 9 / 5 + 32, "K": c + 273.15}[ub]


def fetch_units(value=0.0, **kw):
    ua, ub = kw.get("from"), kw.get("to")
    return {"value": value, "from": ua, "to": ub, "result": _convert(value, ua, ub)}


def instant_units(data, args, code, norm):
    r = data["result"]
    decimals = 0 if abs(r) >= 1000 else (2 if abs(r) >= 1 else 4)
    v = data["value"]
    return TEXTS[code]["units"].format(value=_num(v, code, 0 if float(v).is_integer() else 2), a=UNIT_NAME[code][data["from"]],
                                       result=_num(r, code, decimals), b=UNIT_NAME[code][data["to"]])


# ---------------------------------------------------------------- the user's own integrations
def _custom_list() -> list[dict]:
    return [c for c in settings.get("custom_connectors", []) if isinstance(c, dict) and c.get("id")]


def _custom_connector(cid: str) -> Connector | None:
    spec = next((c for c in _custom_list() if c["id"] == cid), None)
    if not spec:
        return None

    def fetch(query=""):
        url = spec["url"].replace("{query}", quote(query))
        r = integrations._get(url)
        if len(r.content) > 300_000:
            return {"error": "the answer is too large"}
        try:
            body = json.dumps(r.json(), ensure_ascii=False)
        except ValueError:
            body = re.sub(r"<[^>]+>", " ", r.text)
        return {"integration": spec["name"], "data": re.sub(r"\s+", " ", body)[:1800], "source": url.split("/")[2]}

    return Connector(cid, "custom", int(spec.get("ttl_min", 30)) * 60, spec["url"].split("/")[2] if "//" in spec["url"] else "",
                     None, fetch)


def _custom_route(norm: str, raw: str):
    from . import features

    if not features.enabled("custom_integrations"):  # v0.20.0: beta
        return None
    for spec in _custom_list():
        if not spec.get("on", True):
            continue
        words = [_norm(w) for w in str(spec.get("keywords", "")).split(",") if _norm(w)]
        hit = next((w for w in words if re.search(rf"\b{re.escape(w)}\b", norm)), None)
        if hit:
            query = re.sub(rf"\b{re.escape(hit)}\b", " ", raw, flags=re.I) if spec.get("strip_keyword", True) else raw
            return spec["id"], {"query": re.sub(r"\s+", " ", query).strip(" ?.!,")}
    return None


def add_custom(name: str, keywords: str, url: str, ttl_min: int = 30) -> dict:
    name, url = str(name).strip()[:40], str(url).strip()
    if not name or not re.match(r"^https://[^\s/]+\.[^\s/]+", url):
        return {"ok": False, "error": "url"}
    if not [k for k in str(keywords).split(",") if k.strip()]:
        return {"ok": False, "error": "keywords"}
    items = _custom_list()
    cid = "custom_" + (re.sub(r"[^a-z0-9]+", "_", _norm(name)).strip("_") or "x")
    while any(c["id"] == cid for c in items):
        cid += "_2"
    items.append({"id": cid, "name": name, "keywords": str(keywords)[:200], "url": url[:500],
                  "ttl_min": max(0, min(int(ttl_min or 30), 1440)), "on": True})
    settings.apply({"custom_connectors": items})
    return {"ok": True, "id": cid}


def remove_custom(cid: str) -> dict:
    settings.apply({"custom_connectors": [c for c in _custom_list() if c["id"] != cid]})
    return {"ok": True}


def toggle(cid: str, on: bool) -> dict:
    if cid in CONNECTORS:
        settings.apply({"connectors": {**settings.get("connectors", {}), cid: bool(on)}})
    else:
        settings.apply({"custom_connectors": [{**c, "on": bool(on)} if c["id"] == cid else c for c in _custom_list()]})
    return {"ok": True, "items": status()}


# ---------------------------------------------------------------- registry
_register("weather", "online", 900, "Open-Meteo", parse_weather, fetch_weather, instant_weather, tool="get_weather")
_register("currency", "online", 3600, "Frankfurter (BCE/ECB)", parse_currency, fetch_currency, instant_currency,
          tool="convert_currency")
_register("crypto", "online", 300, "CoinGecko", parse_crypto, fetch_crypto, instant_crypto)
_register("clock", "online", 6 * 3600, "Open-Meteo", parse_clock, fetch_clock, instant_clock)
_register("translate", "online", 30 * 86400, "MyMemory", parse_translate, fetch_translate, instant_translate)
_register("holidays", "online", 86400, "Nager.Date", parse_holidays, fetch_holidays, instant_holidays)
_register("air", "online", 1800, "Open-Meteo (CAMS)", parse_air, fetch_air, instant_air)
_register("news", "online", 900, "Google News", parse_news, fetch_news, instant_news, tool="get_news")
_register("wikipedia", "online", 86400, "Wikipedia", None, lambda query="": integrations.wikipedia(query), None,
          tool="wikipedia")
_register("calendar", "online", 0, "ICS", None, lambda days=30: integrations.sync_calendar(days), None, tool="sync_calendar")
_register("calc", "local", 0, "NEXUS", parse_calc, fetch_calc, instant_calc, needs_net=False)
_register("units", "local", 0, "NEXUS", parse_units, fetch_units, instant_units, needs_net=False)
ORDER = ["calc", "units", "translate", "crypto", "currency", "clock", "air", "holidays", "weather", "news"]
# lookup tool: services the model may ask for by name (the others have their own tools)
LOOKUP = ["crypto", "clock", "translate", "holidays", "air"]


def route(text: str, limit: int = 2) -> list[tuple[str, dict]]:
    """Which connectors this message needs, with their arguments (no model, no network)."""
    norm = _norm(text)
    if not norm or len(norm.split()) > 40:
        return []
    found = []
    for cid in ORDER:
        c = CONNECTORS[cid]
        if not enabled(cid):
            continue
        args = c.parse(norm, text)
        if args is not None:
            found.append((cid, args))
            if cid in ("calc", "units", "translate"):
                break  # exclusive: "quanto é 100 dólares em reais" is not a sum
            if cid == "crypto":  # "bitcoin em reais" is not also a currency question
                continue
        if len(found) >= limit:
            break
    if found and found[0][0] == "crypto":
        found = [f for f in found if f[0] != "currency"]
    custom = _custom_route(norm, text)
    if custom and len(found) < limit:
        found.append(custom)
    return found


INSTANT_MAX_WORDS = 14
# v0.20.0: follow-ups that point at the previous question ("e 50 desses em reais?", "e lá, vai chover?")
THERE_RX = re.compile(r"(?<![\wÀ-ÿ])(lá|ali|allí|allá|there|nessa cidade|naquela cidade|in that city|en esa ciudad)(?![\wÀ-ÿ])",
                      re.I)
THOSE_RX = re.compile(r"(\d+(?:[.,]\d+)*)?\s*(mil\s+)?\b(desses|destes|dessas|destas|deles|delas|disso|of those|of these|"
                      r"of them|those|these|de esos|de estos|de esas|de estas|esos|estos)\b")


def _follow_up(text: str, previous) -> tuple[str, list]:
    """Fill what a follow-up leaves out from the previous questions (newest first). Returns (text to route, hits)."""
    earlier = [previous] if isinstance(previous, str) else list(previous or [])
    earlier = [x for x in earlier if x]
    if not earlier:
        return text, []
    previous = earlier[0]
    norm = _norm(text)
    there = THERE_RX.search(text) and not _city(text)
    those = THOSE_RX.search(norm)
    if not there and not those:
        return text, []
    before = route(previous)
    if there:  # the last place the user NAMED ("e lá?" twice in a row still means Paris)
        city = next((_city(x) for x in earlier if _city(x)), "")
        if city:
            return f"{text} em {city}", []
    if those:
        prev = next((a for cid, a in before if cid == "currency"), None)
        if prev and enabled("currency"):
            m = those
            amount = 1.0
            if m.group(1):
                n = m.group(1)
                amount = float(n.replace(".", "").replace(",", ".") if "," in n else n.replace(",", ""))
                amount *= 1000 if m.group(2) else 1
            named = [c for _, c, _ in _currency_hits(norm) if c != prev["from_currency"]]
            dst = named[0] if named else prev["to_currency"]
            return text, [("currency", {"amount": amount, "from_currency": prev["from_currency"], "to_currency": dst})]
    return text, []


def prepare(text: str, previous=()) -> dict:
    """{"instant": reply or None, "block": context for the model, "used": [ids], "data": {id: result}}.
    `previous`: the user's earlier messages in this conversation, newest first (follow-ups like "e 50 desses?")."""
    out = {"instant": None, "block": "", "used": [], "data": {}}
    text, extra = _follow_up(text, previous)
    hits = extra or route(text)
    if not hits:
        return out
    code = i18n.detect(text) or i18n.lang()
    norm = _norm(text)
    lines = []
    for cid, args in hits:
        payload = args if cid != "calc" else {"expression": args["expression"], "value": args["value"]}
        data = call(cid, payload)
        out["used"].append(cid)
        out["data"][cid] = data
        if "error" in data:
            lines.append(f"- {cid}: unavailable ({data['error']}). Tell the user briefly; don't invent values.")
            continue
        stale = f" (offline copy from {data['stale_from']}: say it may be outdated)" if data.get("stale_from") else ""
        lines.append(f"- {cid}{stale}: " + json.dumps({k: v for k, v in data.items() if k not in ("cached_at",)},
                                                     ensure_ascii=False)[:1600])
    first = hits[0][0]
    c = CONNECTORS.get(first)
    simple = len(hits) == 1 and len(norm.split()) <= INSTANT_MAX_WORDS and not re.search(r"\b(e|and|y) (me|tambem|also|"
                                                                                          r"depois|then|luego)\b", norm)
    if simple and c and c.instant and "error" not in out["data"][first] and not out["data"][first].get("stale_from"):
        try:
            out["instant"] = c.instant(out["data"][first], hits[0][1], code if code in TEXTS else "pt", norm)
        except (KeyError, TypeError, ValueError, IndexError):
            out["instant"] = None
    if lines:
        out["block"] = ("\n## Live data from NEXUS integrations (already fetched for this message: if it answers the "
                        "question, use it and do NOT call a tool for it; mention the source briefly)\n" + "\n".join(lines))
    return out


def lookup(service: str, query: str) -> dict:
    """Tool for the model: one of the LOOKUP services, with a natural-language request."""
    c = CONNECTORS.get(service)
    if service not in LOOKUP or c is None:
        return {"error": f"unknown service {service}; use one of {LOOKUP}"}
    args = c.parse(_norm(query), query, strict=False)
    if args is None:
        if service == "translate":
            return {"error": "write the request as: translate <text> to <language>"}
        return {"error": f"couldn't understand the request for {service}: give a city / coin / place"}
    return call(service, args)


def status() -> list[dict]:
    """For Settings > Integrations: every connector with what it is doing now."""
    now = time.time()
    rows = []
    for cid, c in CONNECTORS.items():
        st = dict(_load()["stats"].get(cid, {}))
        rows.append({"id": cid, "kind": c.kind, "provider": c.provider, "ttl": c.ttl, "on": enabled(cid),
                     "state": _state(cid, c, st, now), "uses": st.get("uses", 0), "net": st.get("net", 0),
                     "cached": st.get("cached", 0), "last": st.get("last", 0), "until": st.get("until", 0),
                     "error": st.get("error", "")})
    for spec in _custom_list():
        st = dict(_load()["stats"].get(spec["id"], {}))
        rows.append({"id": spec["id"], "kind": "custom", "name": spec["name"], "keywords": spec.get("keywords", ""),
                     "url": spec["url"], "provider": spec["url"].split("/")[2] if "//" in spec["url"] else "",
                     "ttl": int(spec.get("ttl_min", 30)) * 60, "on": spec.get("on", True),
                     "state": _state(spec["id"], None, st, now), "uses": st.get("uses", 0), "net": st.get("net", 0),
                     "cached": st.get("cached", 0), "last": st.get("last", 0), "until": st.get("until", 0),
                     "error": st.get("error", "")})
    return rows


def _state(cid, c, st, now) -> str:
    if not enabled(cid):
        return "off"
    if cid in _active:
        return "active"
    if c is not None and c.needs_net and not online_allowed():
        return "offline"
    if st.get("error") and now - st.get("last", 0) < 600:
        return "error"
    if st.get("until", 0) > now:
        return "cached"
    return "sleeping"


TESTS = {"weather": "como está o tempo hoje?", "currency": "quanto está o dólar?", "crypto": "quanto está o bitcoin?",
         "clock": "que horas são em Tóquio?", "translate": "traduza bom dia para inglês", "holidays": "qual o próximo feriado?",
         "air": "como está a qualidade do ar?", "news": "quais as notícias de hoje?", "calc": "quanto é 15% de 230?",
         "units": "10 milhas em km", "wikipedia": "", "calendar": ""}


def test(cid: str) -> dict:
    """Settings > Integrations > Test: one real request (cache bypassed for the connector's own answer)."""
    t0 = time.perf_counter()
    if cid.startswith("custom_"):
        spec = next((c for c in _custom_list() if c["id"] == cid), None)
        word = str(spec.get("keywords", "")).split(",")[0].strip() if spec else ""
        result = call(cid, {"query": word})
    elif cid == "wikipedia":
        result = call("wikipedia", {"query": "AMD"})
    elif cid == "calendar":
        result = {"ok": True} if settings.get("calendar_ics_url") else {"error": "no calendar link"}
    else:
        sample = TESTS.get(cid, "")
        c = CONNECTORS[cid]
        args = c.parse(_norm(sample), sample, strict=False) if c.parse else None
        if cid in ("weather", "air") and args is None:
            return {"ok": False, "error": "city", "ms": 0}
        if cid == "clock":
            args = {"city": "Tóquio"}
        if cid == "calc":
            args = {"expression": args["expression"], "value": args["value"]}
        result = call(cid, args or {})
    ms = round((time.perf_counter() - t0) * 1000)
    if isinstance(result, dict) and "error" in result:
        return {"ok": False, "error": str(result["error"])[:160], "ms": ms}
    return {"ok": True, "ms": ms, "cached": bool(result.get("cached_at")) if isinstance(result, dict) else False,
            "preview": json.dumps(result, ensure_ascii=False)[:220]}


# ---------------------------------------------------------------- instant replies
TEXTS = {
    "pt": {
        "weather_now": "Agora em {city}: {temp} °C, {cond}, sensação de {feels} °C. Hoje: mínima de {lo} e máxima de {hi} °C, "
                       "com {rain}% de chance de chuva.",
        "weather_day": "{when} em {city}: {cond}, de {lo} a {hi} °C, com {rain}% de chance de chuva.",
        "tomorrow": "Amanhã", "after_tomorrow": "Depois de amanhã",
        "sun": "Hoje em {city} o sol nasce às {rise} e se põe às {set}.",
        "air": "Qualidade do ar em {city}: {level} (índice europeu {aqi}; PM2,5 de {pm} µg/m³). Índice UV agora: {uv}.",
        "aqi": ("boa", "razoável", "moderada", "ruim", "muito ruim", "extremamente ruim"),
        "clock": "Em {city} ({country}) são {time} de {day}, {diff}.",
        "clock_same": "o mesmo horário daqui", "clock_diff": "{h} h em relação a você",
        "currency": "{amount} = {result} (cotação de referência do BCE de {date}).",
        "crypto": "1 {coin} está {price} agora ({change}% em 24 h, CoinGecko).",
        "translate": "\"{text}\" em {lang}: \"{out}\".",
        "holiday": "O próximo feriado é {name}, {day}, {date} ({when}).",
        "today": "hoje", "in_days": "em {n} dias",
        "calc": "{expr} = {result}.",
        "units": "{value} {a} = {result} {b}.",
        "news": "As principais notícias agora:", "news_topic": "Notícias sobre {topic}:",
    },
    "en": {
        "weather_now": "Right now in {city}: {temp} °C, {cond}, feels like {feels} °C. Today: low {lo}, high {hi} °C, "
                       "{rain}% chance of rain.",
        "weather_day": "{when} in {city}: {cond}, {lo} to {hi} °C, {rain}% chance of rain.",
        "tomorrow": "Tomorrow", "after_tomorrow": "The day after tomorrow",
        "sun": "Today in {city} the sun rises at {rise} and sets at {set}.",
        "air": "Air quality in {city}: {level} (European index {aqi}; PM2.5 {pm} µg/m³). UV index now: {uv}.",
        "aqi": ("good", "fair", "moderate", "poor", "very poor", "extremely poor"),
        "clock": "In {city} ({country}) it is {time} on {day}, {diff}.",
        "clock_same": "the same time as here", "clock_diff": "{h} h from you",
        "currency": "{amount} = {result} (ECB reference rate of {date}).",
        "crypto": "1 {coin} is {price} right now ({change}% in 24 h, CoinGecko).",
        "translate": "\"{text}\" in {lang}: \"{out}\".",
        "holiday": "The next holiday is {name}, {day} {date} ({when}).",
        "today": "today", "in_days": "in {n} days",
        "calc": "{expr} = {result}.",
        "units": "{value} {a} = {result} {b}.",
        "news": "The top headlines right now:", "news_topic": "News about {topic}:",
    },
    "es": {
        "weather_now": "Ahora en {city}: {temp} °C, {cond}, sensación de {feels} °C. Hoy: mínima de {lo} y máxima de {hi} °C, "
                       "con {rain}% de probabilidad de lluvia.",
        "weather_day": "{when} en {city}: {cond}, de {lo} a {hi} °C, con {rain}% de probabilidad de lluvia.",
        "tomorrow": "Mañana", "after_tomorrow": "Pasado mañana",
        "sun": "Hoy en {city} el sol sale a las {rise} y se pone a las {set}.",
        "air": "Calidad del aire en {city}: {level} (índice europeo {aqi}; PM2,5 de {pm} µg/m³). Índice UV ahora: {uv}.",
        "aqi": ("buena", "razonable", "moderada", "mala", "muy mala", "extremadamente mala"),
        "clock": "En {city} ({country}) son las {time} del {day}, {diff}.",
        "clock_same": "la misma hora que aquí", "clock_diff": "{h} h respecto a ti",
        "currency": "{amount} = {result} (tipo de referencia del BCE del {date}).",
        "crypto": "1 {coin} está a {price} ahora ({change}% en 24 h, CoinGecko).",
        "translate": "\"{text}\" en {lang}: \"{out}\".",
        "holiday": "El próximo festivo es {name}, {day} {date} ({when}).",
        "today": "hoy", "in_days": "en {n} días",
        "calc": "{expr} = {result}.",
        "units": "{value} {a} = {result} {b}.",
        "news": "Los principales titulares ahora:", "news_topic": "Noticias sobre {topic}:",
    },
}
