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
# v0.17: isola anche cache feed IOC e dati utente (campagne) — CONFIG_DIR resta
# quello reale del repo (backend/config/campaigns.json), è lettura sola.
os.environ["DATA_DIR"]       = str(_TMP_DIR / "data")
os.environ["CACHE_DIR"]      = str(_TMP_DIR / "data" / "cache")
os.environ["USER_DATA_DIR"]  = str(_TMP_DIR / "data")

import pytest  # noqa: E402 — dopo le variabili d'ambiente


@pytest.fixture(scope="session", autouse=True)
def _cleanup_tmp_dirs():
    """Rimuove la directory temporanea al termine dell'intera sessione di test."""
    yield
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def _reset_campaign_registry():
    """
    Azzera lo Snapshot del registry campagne tra un test e l'altro.

    Prima della v0.17 CAMPAIGNS_DB/CAMPAIGNS_BY_KEYWORDS erano globali di
    modulo popolate una sola volta all'import: i test erano silenziosamente
    ordine-dipendenti (nessun modo di forzare un reload). Ora il registry è
    uno Snapshot esplicito: questa fixture lo forza a ricaricarsi da disco a
    ogni test, cosicché una modifica fatta da un test (es. su un registry
    iniettato) non sopravviva al test successivo.
    """
    from core.analysis import campaign_registry
    campaign_registry._registry = campaign_registry.Snapshot()
    yield
    campaign_registry._registry = campaign_registry.Snapshot()
