#!/usr/bin/env bash
# EMLyzer - Esegui test suite
# Riusa il venv creato da start.sh (stessa logica di selezione Python)

# set -e rimosso: pytest restituisce exit code 1 se ci sono test falliti,
# il che terminerebbe lo script prima di mostrare il resoconto finale.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

echo ""
echo " ============================================"
echo "  EMLyzer - Test Suite"
echo " ============================================"
echo ""

# ── Se il venv non esiste, crealo ────────────────────────────────────────────
if [ ! -f "$VENV_PYTHON" ]; then
    echo "[INFO] Virtual environment non trovato."
    echo "[INFO] Cerco Python compatibile per creare il venv..."
    echo ""

    FOUND_PYTHON=""
    for candidate in python3.13 python3.12 python3.11 python3.14 python3 python; do
        if command -v "$candidate" &>/dev/null; then
            ver=$("$candidate" -c "import sys; print('{}.{}'.format(sys.version_info.major, sys.version_info.minor))" 2>/dev/null)
            [ -z "$ver" ] && continue
            minor="${ver##*.}"
            minor="${minor//[^0-9]/}"
            [ -z "$minor" ] && continue
            if [ "${ver%%.*}" = "3" ] && [ "$minor" -ge 11 ] 2>/dev/null; then
                FOUND_PYTHON="$candidate"
                echo "[INFO] Trovato: $candidate (Python $ver)"
                break
            fi
        fi
    done

    if [ -z "$FOUND_PYTHON" ]; then
        echo "[ERRORE] Python 3.11+ non trovato."
        echo "         Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
        echo "         Fedora/RHEL:   sudo dnf install python3 python3-pip"
        exit 1
    fi

    echo "[INFO] Creazione virtual environment..."
    if ! "$FOUND_PYTHON" -m venv "$VENV_DIR" 2>/tmp/emlyzer_venv_err; then
        cat /tmp/emlyzer_venv_err
        echo "[ERRORE] Creazione venv fallita."
        echo "         Ubuntu/Debian: sudo apt install python3-venv python3-pip"
        echo "         Fedora/RHEL:   sudo dnf install python3-pip"
        exit 1
    fi

    echo "[INFO] Installazione dipendenze..."
    if ! "$VENV_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt" -q 2>/tmp/emlyzer_pip_err; then
        echo "[ERRORE] Installazione dipendenze fallita:"
        cat /tmp/emlyzer_pip_err
        exit 1
    fi
    echo ""
fi

# ── Verifica che pytest sia disponibile ──────────────────────────────────────
if ! "$VENV_PYTHON" -m pytest --version &>/dev/null; then
    echo "[ERRORE] pytest non trovato nel virtual environment."
    echo "         Esegui: $VENV_PYTHON -m pip install pytest pytest-asyncio httpx"
    exit 1
fi

echo "[INFO] Python nel venv: $("$VENV_PYTHON" --version 2>&1)"
echo "[INFO] pytest: $("$VENV_PYTHON" -m pytest --version 2>&1)"
echo ""
echo "[INFO] Esecuzione test..."
echo ""

cd "$BACKEND_DIR"

# Esegui i test e cattura l'exit code senza far terminare lo script
"$VENV_PYTHON" -m pytest tests/test_core.py \
    -v --tb=short --asyncio-mode=auto "$@"
EXIT_CODE=$?

echo ""
if [ "$EXIT_CODE" = "0" ]; then
    echo " ✓  Tutti i test superati."
elif [ "$EXIT_CODE" = "1" ]; then
    echo " ✗  Alcuni test sono falliti. Controlla l'output sopra."
elif [ "$EXIT_CODE" = "2" ]; then
    echo " ✗  Esecuzione interrotta (CTRL+C o errore di configurazione)."
elif [ "$EXIT_CODE" = "5" ]; then
    echo " ⚠  Nessun test trovato."
else
    echo " ✗  Errore pytest (exit code: $EXIT_CODE)."
fi
echo ""

exit "$EXIT_CODE"