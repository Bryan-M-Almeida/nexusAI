"""Opening the default browser (v0.15): links, web searches and "play X on YouTube" (opens the first video found)."""
import re
import urllib.parse
import webbrowser

import httpx


_opened: list[str] = []  # last URLs opened (tests read it instead of launching a real browser)
OPEN = webbrowser.open


def _blocked():
    from . import netprobe

    return netprobe.effective() == "offline"


def open_url(url: str) -> dict:
    url = str(url or "").strip()
    if not re.match(r"^https?://", url):
        if re.match(r"^[\w.-]+\.[a-z]{2,}(/.*)?$", url, re.I):
            url = "https://" + url
        else:
            return {"error": "not a web address"}
    if _blocked():
        return {"error": "NEXUS is in offline mode"}
    _opened.append(url)
    OPEN(url, new=2)
    return {"ok": True, "opened": url}


def web_search(query: str) -> dict:
    return open_url("https://www.google.com/search?q=" + urllib.parse.quote_plus(str(query)))


def youtube_first_video(query: str) -> str | None:
    """The first result of a YouTube search (its page lists videoIds in order)."""
    try:
        r = httpx.get("https://www.youtube.com/results", params={"search_query": query}, timeout=6,
                      headers={"Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8", "User-Agent": "Mozilla/5.0"},
                      follow_redirects=True)
        m = re.search(r'"videoId":"([\w-]{11})"', r.text)
        return m.group(1) if m else None
    except httpx.HTTPError:
        return None


def play_on_youtube(query: str) -> dict:
    """Open the first matching video (autoplay starts in the browser); falls back to the results page."""
    if _blocked():
        return {"error": "NEXUS is in offline mode"}
    vid = youtube_first_video(query)
    if vid:
        return {**open_url(f"https://www.youtube.com/watch?v={vid}"), "video": vid}
    return open_url("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(str(query)))


def music_search(query: str, service: str = "youtube") -> dict:
    service = (service or "youtube").lower()
    if "spotify" in service:
        return open_url("https://open.spotify.com/search/" + urllib.parse.quote(str(query)))
    if "music" in service and "youtube" in service or service == "ytmusic":
        return open_url("https://music.youtube.com/search?q=" + urllib.parse.quote_plus(str(query)))
    return play_on_youtube(query)

