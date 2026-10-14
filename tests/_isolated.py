"""Import this FIRST in every test: points NEXUS_HOME to a fresh temporary folder before `nexus` is imported,
so tests can never write into the real data folder (see NX-ENV-007)."""
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

if "nexus" in sys.modules:
    raise RuntimeError("tests/_isolated.py must be imported before the nexus package")

ROOT = Path(__file__).resolve().parent.parent
TEMP_HOME = Path(tempfile.mkdtemp(prefix="nexus_test_"))
os.environ["NEXUS_HOME"] = str(TEMP_HOME)
sys.path.insert(0, str(ROOT))

from nexus.config import DATA_DIR  # noqa: E402

if DATA_DIR.resolve() != TEMP_HOME.resolve():
    raise RuntimeError(f"refusing to run: data dir is {DATA_DIR}, expected the temporary {TEMP_HOME}")
atexit.register(shutil.rmtree, TEMP_HOME, ignore_errors=True)


def load_example_profile():
    from nexus import profile

    return profile.import_profile((ROOT / "examples" / "profile.example.json").read_text("utf-8"))
