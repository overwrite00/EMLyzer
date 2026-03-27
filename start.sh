#!/usr/bin/env bash
# EMLyzer v0.3.0 - Avvio (Linux / macOS)
# Seleziona automaticamente la versione corretta di Python
# se nel sistema sono installate piu' versioni.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$SCRIPT_DIR/.venv"

echo ""
echo " ============================================"
echo "  EMLyzer v0.3.0"
echo " ============================================"
echo ""

# ── Cerca la versione migliore di Python disponibile ─────────────────────────
# Ordine di preferenza: 3.13 > 3.12 > 3.11 > 3.14 (ultimo perché ancora instabile)
FOUND_PYTHON=""

find_python() {
    # Lista di candidati in ordine di preferenza
    local candidates=("python3.13" "python3.12" "python3.11" "python3.14" "python3" "python")

    for candidate in "${candidates[@]}"; do
        if command -v "$candidate" &>/dev/null; then
            local ver
            ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            local major="${ver%%.*}"
            local minor="${ver##*.}"

            # Accetta solo 3.11+
            if [[ "$major" == "3" && "$minor" -ge 11 ]]; then
                echo "[INFO] Trovato: $candidate (Python $ver)"
                FOUND_PYTHON="$candidate"

                if [[ "$minor" == "14" ]]; then
                    echo "[AVVISO] Python 3.14 - alcune librerie potrebbero non essere pienamente supportate."
                    echo "         Si consiglia Python 3.13: https://www.python.org/downloads/"
                fi
                return 0
            else
                echo "[SKIP] $candidate (Python $ver) - versione troppo vecchia, richiesto 3.11+"
            fi
        fi
    done
    return 1
}

if ! find_python; then
    echo "[ERRORE] Nessuna versione compatibile di Python trovata (richiesto 3.11+)."
    echo "         Installa Python 3.13 da https://www.python.org/downloads/"
    echo "         oppure con il tuo package manager:"
    echo "           Ubuntu/Debian: sudo apt install python3.13"
    echo "           macOS:         brew install python@3.13"
    exit 1
fi

echo "[INFO] Usero': $FOUND_PYTHON"
echo ""

# ── Controlla che il backend esista ──────────────────────────────────────────
if [ ! -f "$BACKEND_DIR/main.py" ]; then
    echo "[ERRORE] File backend/main.py non trovato."
    echo "         Esegui start.sh dalla cartella EMLyzer/"
    exit 1
fi

# ── Crea o rigenera virtual environment ──────────────────────────────────────
VENV_PYTHON="$VENV_DIR/bin/python"

# Se il venv esiste, verifica che usi la versione corretta
if [ -f "$VENV_PYTHON" ]; then
    VENV_VER=$("$VENV_PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
    WANTED_VER=$("$FOUND_PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

    if [ "$VENV_VER" != "$WANTED_VER" ]; then
        echo "[INFO] Venv esistente usa Python $VENV_VER, versione preferita e' $WANTED_VER."
        echo "[INFO] Ricreazione virtual environment..."
        rm -rf "$VENV_DIR"
    fi
fi

if [ ! -f "$VENV_PYTHON" ]; then
    echo "[INFO] Creazione virtual environment con Python $("$FOUND_PYTHON" --version 2>&1)..."
    "$FOUND_PYTHON" -m venv "$VENV_DIR"
    echo "[INFO] Virtual environment creato in $VENV_DIR"
    echo ""
fi

# ── Installa/aggiorna dipendenze ──────────────────────────────────────────────
echo "[INFO] Installazione dipendenze..."
"$VENV_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt" -q
echo "[INFO] Dipendenze OK."

# ── Crea .env se non esiste ───────────────────────────────────────────────────
if [ ! -f "$BACKEND_DIR/.env" ] && [ -f "$BACKEND_DIR/.env.example" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    echo "[INFO] File .env creato da .env.example"
    echo "[INFO] Per cambiare lingua: modifica LANGUAGE nel file .env (it/en)"
fi

# ── Mostra info finali ────────────────────────────────────────────────────────
ACTUAL_VER=$("$VENV_PYTHON" --version 2>&1)
echo ""
echo "[INFO] Python nel venv: $ACTUAL_VER"
echo ""
echo "  Apri il browser su:  http://localhost:8000"
echo "  Documentazione API:  http://localhost:8000/docs"
echo "  Lingua:              pulsante IT/EN in alto a destra"
echo ""
echo "  Premi CTRL+C per fermare"
echo ""

cd "$BACKEND_DIR"
"$VENV_PYTHON" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
