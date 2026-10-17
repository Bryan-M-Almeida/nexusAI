"""Copies the voice model (faster-whisper "small") into ./whisper/small so the build ships with it (v0.19.0): the user
can talk right after installing, without the ~480 MB download on first use. Run by build.ps1 before PyInstaller.
The model comes from the local Hugging Face cache (downloaded once on this machine); nothing is downloaded here unless
the cache is empty, in which case faster-whisper fetches it from Hugging Face (Systran/faster-whisper-small)."""
import shutil
import sys
from pathlib import Path

NAME = sys.argv[1] if len(sys.argv) > 1 else "small"
DEST = Path(__file__).resolve().parent / "whisper" / NAME
FILES = ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt")


def main():
    if all((DEST / f).exists() for f in FILES):
        print(f"whisper {NAME}: already bundled in {DEST}")
        return
    from faster_whisper.utils import download_model

    src = Path(download_model(NAME))  # the cached snapshot (downloads only when missing)
    DEST.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        shutil.copyfile(src / f, DEST / f)  # copyfile follows the cache's links: real files in the build
    size = sum((DEST / f).stat().st_size for f in FILES) / 2 ** 20
    print(f"whisper {NAME}: {size:.0f} MB copied to {DEST}")


if __name__ == "__main__":
    main()
