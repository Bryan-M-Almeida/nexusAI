"""Small update package (v0.20.5): only what changes between versions, taken from the finished build.

    python build_update.py [dist\\NEXUS] [dist\\release]
      -> NEXUS-update-<version>-base<N>.zip  (+ .sha256)

Inside: NEXUS.exe (it carries all the Python code), _internal\\nexus (interface and seed data) and the documents.
The libraries, Python itself and the Whisper voice model stay out - they only change with a new BASE
(nexus/updater.py), and then the full installer is needed."""
import hashlib
import sys
import zipfile
from pathlib import Path

from nexus import __version__
from nexus.updater import BASE

DOCS = ("CHANGELOG.md", "erros.txt", "errors.txt", "errores.txt", "LICENSE", "NOTICE")


def build(src: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"NEXUS-update-{__version__}-base{BASE}.zip"
    files = [src / "NEXUS.exe", *sorted(p for p in (src / "_internal" / "nexus").rglob("*") if p.is_file()),
             *(src / "_internal" / d for d in DOCS if (src / "_internal" / d).exists())]
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in files:
            z.write(f, f.relative_to(src).as_posix())
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (out_dir / (target.name + ".sha256")).write_text(f"{digest}  {target.name}\n", "ascii")
    print(f"{target}  {target.stat().st_size / 2 ** 20:.1f} MB  ({len(files)} files)  sha256 {digest[:16]}...")
    return target


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else "dist/NEXUS"), Path(sys.argv[2] if len(sys.argv) > 2 else "dist/release"))
