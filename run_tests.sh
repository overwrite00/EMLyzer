#!/usr/bin/env bash
# EMLyzer - Esegui test suite
# Riusa il venv creato da start.sh (stessa logica di selezione Python)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

echo ""
echo " ============================================"
echo "  EMLyzer - Test Suite"
echo " ============================================"
echo ""

# Se il venv non esiste, esegui start.sh prima
if [ ! -f "$VENV_PYTHON" ]; then
    echo "[INFO] Virtual environment non trovato. Esegui prima ./start.sh"
    echo "       oppure creo il venv ora cercando Python compatibile..."
    echo ""

    FOUND_PYTHON=""
    for candidate in python3.13 python3.12 python3.11 python3.14 python3 python; do
        if command -v "$candidate" &>/dev/null; then
            ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            minor="${ver##*.}"
            if [[ "${ver%%.*}" == "3" && "$minor" -ge 11 ]]; then
                FOUND_PYTHON="$candidate"
                echo "[INFO] Trovato: $candidate (Python $ver)"
                break
            fi
        fi
    done

    if [ -z "$FOUND_PYTHON" ]; then
        echo "[ERRORE] Python 3.11+ non trovato. Installa Python 3.13."
        exit 1
    fi

    "$FOUND_PYTHON" -m venv "$VENV_DIR"
    "$VENV_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt" -q
fi

echo "[INFO] Python nel venv: $("$VENV_PYTHON" --version 2>&1)"
echo "[INFO] Esecuzione test..."
echo ""

cd "$BACKEND_DIR"
"$VENV_PYTHON" -m pytest tests/ -v --tb=short "$@"
