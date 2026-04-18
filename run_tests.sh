#!/usr/bin/env bash
# EMLyzer - Esegui test suite
# Riusa il venv creato da start.sh (stessa logica di selezione Python)

# set -e rimosso: pytest restituisce exit code 1 se ci sono test falliti,
# il che terminerebbe lo script prima di mostrare il resoconto finale.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

# ── Lingua output (it/en) — rilevata dalla locale del SO ─────────────────────
# Usa $LANG o $LANGUAGE; default italiano.
# Per forzare: LANG=en_US.UTF-8 ./run_tests.sh
SCRIPT_LANG="it"
_os_locale="${LANG:-${LANGUAGE:-}}"
case "$_os_locale" in en*) SCRIPT_LANG="en" ;; esac

if [ "$SCRIPT_LANG" = "en" ]; then
    _E="[ERROR]"   ; _W="[WARNING]" ; _I="[INFO]"
    _M_VENV_MISSING="Virtual environment not found."
    _M_VENV_SEARCHING="Looking for compatible Python to create the venv..."
    _M_VENV_CREATING="Creating virtual environment..."
    _M_VENV_FAILED="Virtual environment creation failed."
    _M_VENV_HINT_DEB="         Ubuntu/Debian: sudo apt install python3-venv python3-pip"
    _M_VENV_HINT_FED="         Fedora/RHEL:   sudo dnf install python3-pip"
    _M_PY_NOT_FOUND="Python 3.11+ not found."
    _M_PY_HINT_DEB="         Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    _M_PY_HINT_FED="         Fedora/RHEL:   sudo dnf install python3 python3-pip"
    _M_DEPS_INSTALLING="Installing dependencies..."
    _M_DEPS_FAILED="Dependencies installation failed:"
    _M_PYTEST_MISSING="pytest not found in the virtual environment."
    _M_PYTEST_HINT_PRE="         Run:"
    _M_PY_IN_VENV="Python in venv:"
    _M_RUNNING="Running tests..."
    _M_ALL_PASSED=" ✓  All tests passed."
    _M_SOME_FAILED=" ✗  Some tests failed. Check the output above."
    _M_INTERRUPTED=" ✗  Execution interrupted (CTRL+C or configuration error)."
    _M_NO_TESTS=" ⚠  No tests found."
    _M_PYTEST_ERR=" ✗  pytest error"
else
    _E="[ERRORE]"  ; _W="[AVVISO]" ; _I="[INFO]"
    _M_VENV_MISSING="Virtual environment non trovato."
    _M_VENV_SEARCHING="Cerco Python compatibile per creare il venv..."
    _M_VENV_CREATING="Creazione virtual environment..."
    _M_VENV_FAILED="Creazione venv fallita."
    _M_VENV_HINT_DEB="         Ubuntu/Debian: sudo apt install python3-venv python3-pip"
    _M_VENV_HINT_FED="         Fedora/RHEL:   sudo dnf install python3-pip"
    _M_PY_NOT_FOUND="Python 3.11+ non trovato."
    _M_PY_HINT_DEB="         Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    _M_PY_HINT_FED="         Fedora/RHEL:   sudo dnf install python3 python3-pip"
    _M_DEPS_INSTALLING="Installazione dipendenze..."
    _M_DEPS_FAILED="Installazione dipendenze fallita:"
    _M_PYTEST_MISSING="pytest non trovato nel virtual environment."
    _M_PYTEST_HINT_PRE="         Esegui:"
    _M_PY_IN_VENV="Python nel venv:"
    _M_RUNNING="Esecuzione test..."
    _M_ALL_PASSED=" ✓  Tutti i test superati."
    _M_SOME_FAILED=" ✗  Alcuni test sono falliti. Controlla l'output sopra."
    _M_INTERRUPTED=" ✗  Esecuzione interrotta (CTRL+C o errore di configurazione)."
    _M_NO_TESTS=" ⚠  Nessun test trovato."
    _M_PYTEST_ERR=" ✗  Errore pytest"
fi

echo ""
echo " ============================================"
echo "  EMLyzer - Test Suite"
echo " ============================================"
echo ""

# ── Se il venv non esiste, crealo ────────────────────────────────────────────
if [ ! -f "$VENV_PYTHON" ]; then
    echo "$_I $_M_VENV_MISSING"
    echo "$_I $_M_VENV_SEARCHING"
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
                if [ "$SCRIPT_LANG" = "en" ]; then
                    echo "$_I Found: $candidate (Python $ver)"
                else
                    echo "$_I Trovato: $candidate (Python $ver)"
                fi
                break
            fi
        fi
    done

    if [ -z "$FOUND_PYTHON" ]; then
        echo "$_E $_M_PY_NOT_FOUND"
        echo "$_M_PY_HINT_DEB"
        echo "$_M_PY_HINT_FED"
        exit 1
    fi

    echo "$_I $_M_VENV_CREATING"
    if ! "$FOUND_PYTHON" -m venv "$VENV_DIR" 2>/tmp/emlyzer_venv_err; then
        cat /tmp/emlyzer_venv_err
        echo "$_E $_M_VENV_FAILED"
        echo "$_M_VENV_HINT_DEB"
        echo "$_M_VENV_HINT_FED"
        exit 1
    fi

    echo "$_I $_M_DEPS_INSTALLING"
    if ! "$VENV_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt" -q 2>/tmp/emlyzer_pip_err; then
        echo "$_E $_M_DEPS_FAILED"
        cat /tmp/emlyzer_pip_err
        exit 1
    fi
    echo ""
fi

# ── Verifica che pytest sia disponibile ──────────────────────────────────────
if ! "$VENV_PYTHON" -m pytest --version &>/dev/null; then
    echo "$_E $_M_PYTEST_MISSING"
    echo "$_M_PYTEST_HINT_PRE $VENV_PYTHON -m pip install pytest pytest-asyncio httpx"
    exit 1
fi

echo "$_I $_M_PY_IN_VENV $("$VENV_PYTHON" --version 2>&1)"
echo "$_I pytest: $("$VENV_PYTHON" -m pytest --version 2>&1)"
echo ""
echo "$_I $_M_RUNNING"
echo ""

cd "$BACKEND_DIR"

# Esegui i test e cattura l'exit code senza far terminare lo script
"$VENV_PYTHON" -m pytest tests/test_core.py \
    -v --tb=short --asyncio-mode=auto "$@"
EXIT_CODE=$?

echo ""
if [ "$EXIT_CODE" = "0" ]; then
    echo "$_M_ALL_PASSED"
elif [ "$EXIT_CODE" = "1" ]; then
    echo "$_M_SOME_FAILED"
elif [ "$EXIT_CODE" = "2" ]; then
    echo "$_M_INTERRUPTED"
elif [ "$EXIT_CODE" = "5" ]; then
    echo "$_M_NO_TESTS"
else
    if [ "$SCRIPT_LANG" = "en" ]; then
        echo "$_M_PYTEST_ERR (exit code: $EXIT_CODE)."
    else
        echo "$_M_PYTEST_ERR (exit code: $EXIT_CODE)."
    fi
fi
echo ""

exit "$EXIT_CODE"
