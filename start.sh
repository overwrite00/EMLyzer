#!/usr/bin/env bash
# EMLyzer - Avvio (Linux / macOS)
# Compatibile con Debian/Ubuntu, Fedora/RHEL, macOS

# ── set -e rimosso: causa uscite silenziose in alcune shell/distro ────────────
# Usiamo controlli espliciti su ogni operazione critica.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

# ── Leggi la versione da config.py (evita hardcoding) ────────────────────────
VERSION=$(grep -oP '(?<=VERSION: str = ")[^"]+' "$BACKEND_DIR/utils/config.py" 2>/dev/null || echo "0.3.3")

echo ""
echo " ============================================"
echo "  EMLyzer v$VERSION"
echo " ============================================"
echo ""

# ── Cerca la versione migliore di Python disponibile ─────────────────────────
# Ordine di preferenza: 3.13 > 3.12 > 3.11 > 3.14 (ancora instabile)
FOUND_PYTHON=""

find_python() {
    local candidates=("python3.13" "python3.12" "python3.11" "python3.14" "python3" "python")
    for candidate in "${candidates[@]}"; do
        if command -v "$candidate" &>/dev/null; then
            local ver
            ver=$("$candidate" -c "import sys; print('{}.{}'.format(sys.version_info.major, sys.version_info.minor))" 2>/dev/null)
            # Salta se la versione non è stata letta
            [ -z "$ver" ] && continue
            local major minor
            major="${ver%%.*}"
            minor="${ver##*.}"
            # Rimuovi eventuale suffisso non numerico (es. "11a" su alcune build)
            minor="${minor//[^0-9]/}"
            [ -z "$minor" ] && continue

            if [ "$major" = "3" ] && [ "$minor" -ge 11 ] 2>/dev/null; then
                echo "[INFO] Trovato: $candidate (Python $ver)"
                FOUND_PYTHON="$candidate"
                if [ "$minor" -ge 14 ]; then
                    echo "[AVVISO] Python 3.14 - alcune librerie potrebbero non essere pienamente supportate."
                    echo "         Si consiglia Python 3.13: https://www.python.org/downloads/"
                fi
                return 0
            else
                echo "[SKIP] $candidate (Python $ver) - richiesto 3.11+"
            fi
        fi
    done
    return 1
}

if ! find_python; then
    echo "[ERRORE] Nessuna versione compatibile di Python trovata (richiesto 3.11+)."
    echo ""
    echo "         Installazione:"
    echo "           Ubuntu/Debian:  sudo apt install python3 python3-venv python3-pip"
    echo "           Fedora/RHEL:    sudo dnf install python3 python3-pip"
    echo "           macOS:          brew install python@3.13"
    echo "           Tutti:          https://www.python.org/downloads/"
    exit 1
fi

echo "[INFO] Uso: $FOUND_PYTHON"
echo ""

# ── Controlla che il backend esista ──────────────────────────────────────────
if [ ! -f "$BACKEND_DIR/main.py" ]; then
    echo "[ERRORE] File backend/main.py non trovato."
    echo "         Esegui start.sh dalla cartella EMLyzer/"
    exit 1
fi

# ── Controlla che la porta 8000 sia libera ────────────────────────────────────
PORT=8000
port_in_use=0
if command -v ss &>/dev/null; then
    ss -tlnp 2>/dev/null | grep -q ":$PORT " && port_in_use=1
elif command -v netstat &>/dev/null; then
    netstat -tlnp 2>/dev/null | grep -q ":$PORT " && port_in_use=1
else
    ( exec 3<>/dev/tcp/127.0.0.1/$PORT ) 2>/dev/null && port_in_use=1
fi

if [ "$port_in_use" = "1" ]; then
    echo "[AVVISO] La porta $PORT e' gia' in uso."
    echo "         Un'altra istanza di EMLyzer potrebbe essere attiva,"
    echo "         oppure un altro programma sta usando la porta $PORT."
    echo "         Fermalo prima di avviare EMLyzer."
    echo ""
    echo "         Per trovare il processo: lsof -i :$PORT"
    echo "         oppure:                  ss -tlnp | grep $PORT"
    exit 1
fi

# ── Crea o rigenera virtual environment ──────────────────────────────────────
WANTED_VER=$("$FOUND_PYTHON" -c "import sys; print('{}.{}'.format(sys.version_info.major, sys.version_info.minor))")

if [ -f "$VENV_PYTHON" ]; then
    VENV_VER=$("$VENV_PYTHON" -c "import sys; print('{}.{}'.format(sys.version_info.major, sys.version_info.minor))" 2>/dev/null)

    if [ -z "$VENV_VER" ] || [ "$VENV_VER" != "$WANTED_VER" ]; then
        if [ -z "$VENV_VER" ]; then
            echo "[INFO] Virtual environment corrotto. Ricreazione..."
        else
            echo "[INFO] Venv usa Python $VENV_VER, versione corrente e' $WANTED_VER."
            echo "[INFO] Ricreazione virtual environment..."
        fi
        rm -rf "$VENV_DIR"
    fi
fi

if [ ! -f "$VENV_PYTHON" ]; then
    echo "[INFO] Creazione virtual environment con $("$FOUND_PYTHON" --version 2>&1)..."

    if ! "$FOUND_PYTHON" -m venv "$VENV_DIR" 2>/tmp/emlyzer_venv_err; then
        echo "[AVVISO] Creazione venv fallita. Provo metodo alternativo..."
        cat /tmp/emlyzer_venv_err

        if ! "$FOUND_PYTHON" -m venv --without-pip "$VENV_DIR" 2>/tmp/emlyzer_venv_err2; then
            echo "[ERRORE] Impossibile creare il virtual environment."
            cat /tmp/emlyzer_venv_err2
            echo ""
            echo "         Soluzione:"
            echo "           Ubuntu/Debian: sudo apt install python3-venv python3-pip"
            echo "           Fedora/RHEL:   sudo dnf install python3-pip"
            exit 1
        fi

        if [ ! -f "$VENV_DIR/bin/pip" ]; then
            echo "[INFO] Installazione pip nel virtual environment..."
            "$VENV_DIR/bin/python" -m ensurepip --upgrade 2>/dev/null || \
            "$VENV_DIR/bin/python" -m ensurepip 2>/dev/null || {
                echo "[ERRORE] Impossibile installare pip nel virtual environment."
                echo "         Ubuntu/Debian: sudo apt install python3-pip"
                echo "         Fedora/RHEL:   sudo dnf install python3-pip"
                exit 1
            }
        fi
    fi

    echo "[INFO] Virtual environment creato in $VENV_DIR"
    echo ""
fi

# ── Aggiorna pip (silenziosamente, con fallback) ──────────────────────────────
"$VENV_PYTHON" -m pip install --upgrade pip -q 2>/dev/null || true

# ── Installa/aggiorna dipendenze ──────────────────────────────────────────────
echo "[INFO] Installazione dipendenze..."
if ! "$VENV_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt" -q 2>/tmp/emlyzer_pip_err; then
    echo "[ERRORE] Installazione dipendenze fallita:"
    cat /tmp/emlyzer_pip_err
    exit 1
fi
echo "[INFO] Dipendenze OK."
echo ""

# ── Crea .env se non esiste ───────────────────────────────────────────────────
if [ ! -f "$BACKEND_DIR/.env" ] && [ -f "$BACKEND_DIR/.env.example" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    echo "[INFO] File .env creato da .env.example"
    echo "[INFO] Modifica LANGUAGE in .env per cambiare lingua (it/en)"
fi

# ── Mostra info finali ────────────────────────────────────────────────────────
ACTUAL_VER=$("$VENV_PYTHON" --version 2>&1)
echo "[INFO] Python nel venv: $ACTUAL_VER"
echo ""
echo "  Apri il browser su:  http://localhost:$PORT"
echo "  Documentazione API:  http://localhost:$PORT/docs"
echo "  Lingua:              pulsante IT/EN in alto a destra"
echo ""
echo "  Premi CTRL+C per fermare"
echo ""

# ── Avvio server ─────────────────────────────────────────────────────────────
cd "$BACKEND_DIR"
exec "$VENV_PYTHON" -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload