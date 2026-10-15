"""Reading files (v0.15): PDF, DOCX, EPUB, plain text / code / CSV / JSON, ZIP archives and images (text via the OCR
built into Windows - no download). Everything stays on this computer."""
import html
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

TEXT_EXT = {".txt", ".md", ".csv", ".json", ".log", ".py", ".js", ".ts", ".html", ".css", ".xml", ".yaml", ".yml",
            ".ini", ".cfg", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".sql", ".sh", ".bat", ".ps1", ".tsx", ".jsx"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff"}
BOOK_EXT = {".pdf", ".epub", ".docx", ".txt", ".md"}
SUPPORTED = TEXT_EXT | IMAGE_EXT | {".pdf", ".docx", ".epub", ".zip"}
MAX_CHARS = 2_000_000


class FileError(Exception):
    pass


def _strip_xml(xml: str) -> str:
    xml = re.sub(r"<(?:head|script|style)\b.*?</(?:head|script|style)>", " ", xml, flags=re.S | re.I)
    xml = re.sub(r"</?(?:w:p|p|br|div|h\d|li|tr)\b[^>]*>", "\n", xml, flags=re.I)  # block tags -> line breaks
    xml = re.sub(r"<[^>]+>", "", xml)
    return html.unescape(xml)


def _pdf(path: Path) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(str(path), strict=False)  # tolerate slightly damaged PDFs
    pages = [(p.extract_text() or "") for p in reader.pages]
    return "\n\n".join(pages), len(pages)


def _docx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
    xml = re.sub(r"<w:tab/>", "\t", xml)
    return _strip_xml(xml)


def _epub(path: Path) -> str:
    """EPUB = a zip of XHTML chapters; the reading order comes from the OPF spine."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        opf = next((n for n in names if n.endswith(".opf")), None)
        order = []
        if opf:
            data = z.read(opf).decode("utf-8", errors="ignore")
            base = opf.rsplit("/", 1)[0] + "/" if "/" in opf else ""
            items = dict(re.findall(r'<item[^>]*id="([^"]+)"[^>]*href="([^"]+)"', data))
            items.update({k: v for v, k in re.findall(r'<item[^>]*href="([^"]+)"[^>]*id="([^"]+)"', data)})
            order = [base + items[i] for i in re.findall(r'<itemref[^>]*idref="([^"]+)"', data) if i in items]
        order = [n for n in order if n in names] or sorted(n for n in names if n.endswith((".xhtml", ".html", ".htm")))
        return "\n\n".join(_strip_xml(z.read(n).decode("utf-8", errors="ignore")) for n in order)


def _zip(path: Path) -> str:
    out = []
    with zipfile.ZipFile(path) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        out.append("Files in the archive:\n" + "\n".join(f"- {i.filename} ({i.file_size} B)" for i in infos[:200]))
        for i in infos:
            if Path(i.filename).suffix.lower() in TEXT_EXT and i.file_size < 400_000:
                out.append(f"\n--- {i.filename} ---\n" + z.read(i).decode("utf-8", errors="replace"))
            if sum(len(x) for x in out) > MAX_CHARS:
                break
    return "\n".join(out)


_OCR_PS = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait(-1) | Out-Null; $task.Result }
[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] > $null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] > $null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime] > $null
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($args[0])) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$result.Lines | ForEach-Object { $_.Text }
"""


def _image(path: Path) -> str:
    if sys.platform != "win32":
        raise FileError("image text recognition needs Windows")
    quoted = "'" + str(path.resolve()).replace("'", "''") + "'"
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", "& {" + _OCR_PS + "} " + quoted],
                       capture_output=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise FileError("the image could not be read: " + r.stderr.decode("utf-8", errors="ignore")[-300:].strip())
    return r.stdout.decode("utf-8", errors="replace").strip()


def read(path) -> dict:
    """{"name", "kind", "text", "pages"} or FileError."""
    path = Path(path)
    if not path.is_file():
        raise FileError(f"file not found: {path}")
    ext, pages = path.suffix.lower(), None
    try:
        if ext == ".pdf":
            text, pages = _pdf(path)
            kind = "pdf"
        elif ext == ".docx":
            text, kind = _docx(path), "docx"
        elif ext == ".epub":
            text, kind = _epub(path), "epub"
        elif ext == ".zip":
            text, kind = _zip(path), "zip"
        elif ext in IMAGE_EXT:
            text, kind = _image(path), "image"
        elif ext == ".json":
            text, kind = json.dumps(json.loads(path.read_text("utf-8", errors="replace")), indent=1, ensure_ascii=False), "text"
        elif ext in TEXT_EXT or path.stat().st_size < 2_000_000:
            raw = path.read_bytes()
            if b"\x00" in raw[:4096]:
                raise FileError(f"{ext or 'this'} files are not supported yet")
            text, kind = raw.decode("utf-8", errors="replace"), "text"
        else:
            raise FileError(f"{ext} files are not supported yet")
    except FileError:
        raise
    except Exception as exc:  # damaged / encrypted files
        raise FileError(f"could not read {path.name}: {exc}") from exc
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()[:MAX_CHARS]
    if not text:
        raise FileError(f"no text found in {path.name}" + (" (scanned PDF?)" if ext == ".pdf" else ""))
    return {"name": path.name, "kind": kind, "text": text, "pages": pages}
