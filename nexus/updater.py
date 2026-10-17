"""Updates (v0.20.5): new versions without downloading everything again.

Every release on GitHub carries two files:
  NEXUS-Setup-<version>.exe              the full installer (~540 MB: program, libraries and the voice model)
  NEXUS-update-<version>-base<N>.zip     only what changes between versions (~20 MB: NEXUS.exe, the interface,
                                         the documents) + its .sha256
BASE is the version of what does NOT change (Python, ONNX, CTranslate2, the Whisper model...). When a release needs
other libraries, BASE goes up and that release can only be installed with the full installer.

The small update is unpacked over the installed folder by a short script that waits for NEXUS to close and opens it
again. User data lives in %LOCALAPPDATA%\\NEXUS and is never touched. While the repository is private, GitHub answers
404 and the check says so."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import httpx

from . import __version__, downloads
from .config import DATA_DIR
from .logs import log

REPO = "Bryan-M-Almeida/nexusAI"
# not /releases/latest: GitHub leaves pre-releases out of it, and every 0.x was one (v1.0.0 check saw 0.19.7)
API = f"https://api.github.com/repos/{REPO}/releases?per_page=20"
BASE = 1  # bump when the libraries / bundled models change (the small update can't carry them)
UPDATE_RX = re.compile(r"^NEXUS-update-(\d+\.\d+\.\d+)-base(\d+)\.zip$")
SETUP_RX = re.compile(r"^NEXUS-Setup-(\d+\.\d+\.\d+)\.exe$")
DIR = DATA_DIR / "updates"
_state: dict = {}


def _v(text: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", text)[:3])


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def check(timeout: float = 8) -> dict:
    """{"ok", "current", "latest", "newer", "kind": "small"|"full"|None, "notes", "url", "size_mb"} or an error."""
    out = {"ok": False, "current": __version__}
    try:
        r = httpx.get(API, timeout=timeout, headers={"Accept": "application/vnd.github+json",
                                                     "User-Agent": f"NEXUS/{__version__}"})
    except httpx.HTTPError as exc:
        return {**out, "error": "offline", "detail": str(exc)[:120]}
    if r.status_code == 404:
        return {**out, "error": "not_public"}  # private repository (or no release yet)
    if r.status_code != 200:
        return {**out, "error": f"http {r.status_code}"}
    releases = [x for x in r.json() if not x.get("draft") and re.match(r"^v?\d+\.\d+\.\d+$", x.get("tag_name", ""))]
    if not releases:
        return {**out, "error": "not_public"}
    rel = max(releases, key=lambda x: _v(x["tag_name"]))  # the highest version, published or pre-release
    latest = rel.get("tag_name", "").lstrip("v")
    assets = {a["name"]: a for a in rel.get("assets", [])}
    newer = _v(latest) > _v(__version__)
    small = next((a for n, a in assets.items() if (m := UPDATE_RX.match(n)) and m.group(1) == latest
                  and int(m.group(2)) == BASE), None)
    setup = next((a for n, a in assets.items() if (m := SETUP_RX.match(n)) and m.group(1) == latest), None)
    kind = None
    if newer:
        kind = "small" if small and frozen() else "full" if setup else None
    chosen = small if kind == "small" else setup
    sha = assets.get(small["name"] + ".sha256") if small else None
    out.update(ok=True, latest=latest, newer=newer, kind=kind, notes=(rel.get("body") or "")[:4000],
               page=rel.get("html_url", ""), url=chosen["browser_download_url"] if chosen else "",
               name=chosen["name"] if chosen else "", size_mb=round(chosen["size"] / 2 ** 20, 1) if chosen else 0,
               sha_url=sha["browser_download_url"] if sha else "")
    _state.update(out)
    return out


def download(info: dict | None = None) -> dict:
    """Download the small update (blocking; shown in Settings > Downloads) and check its SHA-256."""
    info = info or _state
    if info.get("kind") != "small" or not info.get("url"):
        return {"ok": False, "error": "no small update"}
    DIR.mkdir(parents=True, exist_ok=True)
    target = DIR / info["name"]
    did = downloads.start("update", info["name"], int(info.get("size_mb", 0) * 2 ** 20))
    try:
        h = hashlib.sha256()
        with httpx.stream("GET", info["url"], follow_redirects=True, timeout=httpx.Timeout(30, read=120)) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length") or 0)
            done = 0
            with open(target, "wb") as f:
                for chunk in r.iter_bytes(1 << 16):
                    f.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    downloads.update(did, done, total or None)
        if info.get("sha_url"):
            expected = httpx.get(info["sha_url"], follow_redirects=True, timeout=20).text.split()[0].lower()
            if expected != h.hexdigest():
                target.unlink(missing_ok=True)
                raise ValueError("SHA-256 does not match: the file was damaged or changed")
        with zipfile.ZipFile(target) as z:
            bad = [n for n in z.namelist() if n.startswith(("/", "\\")) or ".." in Path(n).parts]
            if bad or "NEXUS.exe" not in z.namelist():
                target.unlink(missing_ok=True)
                raise ValueError("unexpected update package")
        downloads.finish(did, True)
        return {"ok": True, "file": str(target)}
    except Exception as exc:
        downloads.finish(did, False, str(exc)[:160])
        log.warning(f"update download failed: {exc}")
        return {"ok": False, "error": str(exc)[:160]}


def install(zip_path: str) -> dict:
    """Unpack over the installed folder after NEXUS closes, then open it again. The caller closes the window."""
    if not frozen():
        return {"ok": False, "error": "only in the installed NEXUS"}
    app_dir = Path(sys.executable).parent
    script = Path(tempfile.gettempdir()) / f"nexus-update-{int(time.time())}.ps1"
    script.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        f"Wait-Process -Id {os.getpid()} -Timeout 60 -ErrorAction SilentlyContinue\n"
        "Start-Sleep -Milliseconds 800\n"
        f"Expand-Archive -LiteralPath '{zip_path}' -DestinationPath '{app_dir}' -Force\n"
        f"Remove-Item -LiteralPath '{zip_path}' -Force -ErrorAction SilentlyContinue\n"
        f"Start-Process -FilePath '{app_dir / 'NEXUS.exe'}'\n"
        "Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue\n", "utf-8-sig")
    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File",
                      str(script)], creationflags=0x00000008 | 0x08000000)  # detached, no console window
    log.info(f"update scheduled from {zip_path}")
    return {"ok": True}


def state() -> dict:
    return dict(_state)


def manifest() -> dict:
    """Written next to the small update by release.ps1 (also used by the tests)."""
    return {"version": __version__, "base": BASE}


if __name__ == "__main__":  # python -m nexus.updater -> prints the manifest (release.ps1 names the zip with it)
    print(json.dumps(manifest()))
