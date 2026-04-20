import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Isola i test dai dati di produzione ───────────────────────────────────────
# Redirige DB e directory uploads/reports verso una cartella temporanea per
# evitare che i test popolino backend/data/ e backend/uploads/.
# Le variabili d'ambiente devono essere impostate QUI, prima che qualunque
# modulo del progetto venga importato — config.py legge os.environ al momento
# dell'istanziazione di Settings(), che avviene al primo import.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="emlyzer_test_"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DIR / 'test.db'}"
os.environ["UPLOAD_DIR"]   = str(_TMP_DIR / "uploads")
os.environ["REPORTS_DIR"]  = str(_TMP_DIR / "reports")

import pytest  # noqa: E402 — dopo le variabili d'ambiente


@pytest.fixture(scope="session", autouse=True)
def _cleanup_tmp_dirs():
    """Rimuove la directory temporanea al termine dell'intera sessione di test."""
    yield
    shutil.rmtree(_TMP_DIR, ignore_errors=True)
