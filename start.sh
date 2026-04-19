#!/usr/bin/env bash
# EMLyzer - Avvio (Linux / macOS)
# Rileva la distribuzione, installa Python se necessario, crea il venv e avvia il tool.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$SCRIPT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
PORT=8000

# ── Versione Python — modifica SOLO queste righe per aggiornare ───────────────
# Per passare a Python 3.14: cambia TARGET="3.14", TARGET_MINOR="14", MAX_MINOR="14"
PYTHON_TARGET="3.13"        # Versione esatta da usare e installare
PYTHON_TARGET_MINOR="13"    # Minor di TARGET — usato nei confronti numerici
PYTHON_MIN_MINOR="11"       # Minor minimo accettabile (compatibilità minima)
PYTHON_MAX_MINOR="13"       # Minor massimo accettabile (versioni > NON sono supportate)

# ── Leggi versione da config.py ───────────────────────────────────────────────
# La versione è sempre letta da config.py — unica fonte di verità
VERSION=$(grep -oP '(?<=VERSION: str = ")[^"]+' "$BACKEND_DIR/utils/config.py" 2>/dev/null)
[ -z "$VERSION" ] && VERSION=$(grep -oP '(?<=VERSION = ")[^"]+' "$BACKEND_DIR/utils/config.py" 2>/dev/null)
[ -z "$VERSION" ] && VERSION="???"

# ── Lingua output (it/en) — rilevata dalla locale del SO ─────────────────────
# Usa $LANG o $LANGUAGE; default italiano.
# Per forzare: LANG=en_US.UTF-8 ./start.sh
SCRIPT_LANG="it"
_os_locale="${LANG:-${LANGUAGE:-}}"
case "$_os_locale" in en*) SCRIPT_LANG="en" ;; esac

if [ "$SCRIPT_LANG" = "en" ]; then
    _E="[ERROR]"   ; _W="[WARNING]" ; _I="[INFO]"
    _M_BACKEND_MISSING="File backend/main.py not found."
    _M_BACKEND_HINT="         Run start.sh from the EMLyzer/ folder"
    _M_FE_BUILDING="Frontend bundle not found. Building frontend..."
    _M_FE_BUILT="Frontend built and copied."
    _M_FE_MISSING="Frontend bundle not found: backend/static/assets/index.js"
    _M_FE_HINT="         Copy the files from the release package or run:"
    _M_FE_CMD1="           cd frontend && npm install && npm run build"
    _M_FE_CMD2="           cp -r frontend/dist/. backend/static/"
    _M_PORT_BUSY="Port $PORT is already in use."
    _M_PORT_HINT="         Stop the process using it and try again."
    _M_PORT_FIND="         To find it: lsof -i :$PORT  or  ss -tlnp | grep $PORT"
    _M_SUDO_NEEDED="This operation requires administrator privileges."
    _M_SUDO_HINT="         Run manually: sudo"
    _M_SEARCHING_PY="Searching for Python $PYTHON_TARGET (acceptable range: 3.$PYTHON_MIN_MINOR - 3.$PYTHON_MAX_MINOR)..."
    _M_INSTALL_PY2="         (system Python will remain intact)"
    _M_PKG_FAIL="Package manager unavailable or installation failed."
    _M_PYENV_TRY="Trying pyenv (builds Python $PYTHON_TARGET without modifying the system)..."
    _M_PYENV_NOT_FOUND="pyenv installed but Python $PYTHON_TARGET not found."
    _M_INSTALL_FAIL="Cannot install Python $PYTHON_TARGET automatically."
    _M_INSTALL_MANUAL="  Install Python $PYTHON_TARGET manually:"
    _M_INSTALL_PYENV="  Or use pyenv (no sudo): https://github.com/pyenv/pyenv"
    _M_PY_FOUND="Python $PYTHON_TARGET found:"
    _M_PY_NOT_FOUND_TARGET="Python $PYTHON_TARGET not found on this system."
    _M_PY_COMPAT_PRE="Using Python"
    _M_PY_COMPAT_MID="as compatible"
    _M_PY_RERUN="         Re-run start.sh after installing Python $PYTHON_TARGET."
    _M_PY_TOO_NEW_A="found but NOT supported by EMLyzer."
    _M_PY_TOO_NEW_B="         EMLyzer requires Python $PYTHON_TARGET (max 3.$PYTHON_MAX_MINOR)."
    _M_PY_TOO_NEW_C="will remain intact — installing $PYTHON_TARGET in parallel."
    _M_PY_INSTALLED_NOACC="Python $PYTHON_TARGET installed but not accessible."
    _M_RESTART_TERM="         Restart the terminal and re-run start.sh"
    _M_ARCH_INCOMPAT="The system Python version on Arch is not compatible."
    _M_ARCH_PYENV="Using pyenv to install Python $PYTHON_TARGET in parallel..."
    _M_DISTRO_UNKNOWN="Distribution"
    _M_DISTRO_UNKNOWN2="not recognized."
    _M_DISTRO_UBUNTU="Ubuntu/Debian-based distribution detected."
    _M_DISTRO_DEBIAN="Pure Debian distribution detected."
    _M_DISTRO_FEDORA="Fedora distribution detected."
    _M_DISTRO_RHEL="RHEL-based distribution detected."
    _M_DISTRO_ARCH="Arch-based distribution detected."
    _M_DISTRO_OPENSUSE="openSUSE distribution detected."
    _M_DISTRO_MACOS="macOS detected."
    _M_STD_REPOS="Trying standard repositories..."
    _M_ALT_VER="Trying Python"
    _M_ALT_VER2="as alternative..."
    _M_PY_VER_INSTALLED="Python"
    _M_PY_VER_INSTALLED2="installed."
    _M_PY_VER_STD="installed from standard repositories."
    _M_DEADSNAKES_PPA="Python $PYTHON_TARGET not in standard repos."
    _M_DEADSNAKES_ADD="Adding deadsnakes PPA (official Python repository for Ubuntu)..."
    _M_DEADSNAKES_OK="Python $PYTHON_TARGET installed from deadsnakes PPA."
    _M_INST_AUTO_FAIL="Cannot install Python $PYTHON_TARGET automatically."
    _M_BACKPORTS="Trying Debian backports..."
    _M_BACKPORTS_OK="installed from backports."
    _M_EPEL="Trying via EPEL..."
    _M_EPEL_OK="installed from EPEL."
    _M_BREW_INST="Installing Python $PYTHON_TARGET via Homebrew..."
    _M_BREW_MISSING="Homebrew not found."
    _M_BREW_HINT="         Install Homebrew from https://brew.sh"
    _M_BREW_HINT2="         or Python $PYTHON_TARGET from https://www.python.org/downloads/"
    _M_VENV_NO_MODULE="The venv module is not available for"
    _M_VENV_INST_PKG="Trying to install the venv package..."
    _M_VENV_FAIL="Cannot enable venv support."
    _M_VENV_CORRUPT="Virtual environment corrupted. Recreating..."
    _M_VENV_UPGRADE_PRE="Virtual environment uses Python"
    _M_VENV_UPGRADE_MID="current version is"
    _M_VENV_UPGRADE_POST="Recreating..."
    _M_VENV_CREATING="Creating virtual environment with"
    _M_VENV_ALT="venv creation failed. Trying alternative method..."
    _M_VENV_CREATED="Virtual environment created in $VENV_DIR"
    _M_VENV_HARD_FAIL="Cannot create the virtual environment."
    _M_VENV_HINT_DEB="  Ubuntu/Debian: sudo apt install python3-venv python3-pip"
    _M_VENV_HINT_RPM="  Fedora/RHEL:   sudo dnf install python3-pip"
    _M_PIP_INST="Installing pip in the virtual environment..."
    _M_PIP_FAIL="Cannot install pip."
    _M_PIP_HINT_DEB="  Ubuntu/Debian: sudo apt install python3-pip"
    _M_PIP_HINT_RPM="  Fedora/RHEL:   sudo dnf install python3-pip"
    _M_DEPS_INST="Installing dependencies..."
    _M_DEPS_OK="Dependencies OK."
    _M_DEPS_FAIL="Dependencies installation failed:"
    _M_ENV_CREATED="File .env created from .env.example"
    _M_ENV_LANG="Edit LANGUAGE in .env to change language (it/en)"
    _M_PY_LABEL="Python:"
    _M_OPEN="  Open in browser:     http://localhost:$PORT"
    _M_DOCS="  API Documentation:   http://localhost:$PORT/docs"
    _M_LANG_UI="  Language:            IT/EN toggle button (top right)"
    _M_STOP="  Press CTRL+C to stop"
    _M_STOPPED="Server stopped."
    _M_PYENV_TRY2="Trying installation via pyenv (no sudo required)..."
    _M_PYENV_INST="Installing pyenv..."
    _M_PYENV_CURL_MISS="curl not available. Cannot install pyenv."
    _M_PYENV_INIT_FAIL="pyenv installation failed."
    _M_PYENV_FOUND="pyenv found. Installing Python $PYTHON_TARGET..."
    _M_PYENV_COMPILE_FAIL="Python $PYTHON_TARGET build failed."
    _M_PYENV_BUILD_DEPS="         Verify that build dependencies are installed."
else
    _E="[ERRORE]"  ; _W="[AVVISO]" ; _I="[INFO]"
    _M_BACKEND_MISSING="File backend/main.py non trovato."
    _M_BACKEND_HINT="         Esegui start.sh dalla cartella EMLyzer/"
    _M_FE_BUILDING="Bundle frontend non trovato. Compilo il frontend..."
    _M_FE_BUILT="Frontend compilato e copiato."
    _M_FE_MISSING="Bundle frontend non trovato: backend/static/assets/index.js"
    _M_FE_HINT="         Copia i file dalla release o esegui:"
    _M_FE_CMD1="           cd frontend && npm install && npm run build"
    _M_FE_CMD2="           cp -r frontend/dist/. backend/static/"
    _M_PORT_BUSY="La porta $PORT e' gia' in uso."
    _M_PORT_HINT="         Ferma il processo che la occupa e riprova."
    _M_PORT_FIND="         Per trovarlo: lsof -i :$PORT  oppure  ss -tlnp | grep $PORT"
    _M_SUDO_NEEDED="Operazione richiede privilegi di amministratore."
    _M_SUDO_HINT="         Esegui manualmente: sudo"
    _M_SEARCHING_PY="Ricerca Python $PYTHON_TARGET (range accettabile: 3.$PYTHON_MIN_MINOR - 3.$PYTHON_MAX_MINOR)..."
    _M_INSTALL_PY2="         (il Python di sistema rimarra' intatto)"
    _M_PKG_FAIL="Package manager non disponibile o installazione fallita."
    _M_PYENV_TRY="Provo con pyenv (compila Python $PYTHON_TARGET senza modificare il sistema)..."
    _M_PYENV_NOT_FOUND="pyenv installato ma Python $PYTHON_TARGET non trovato."
    _M_INSTALL_FAIL="Impossibile installare Python $PYTHON_TARGET automaticamente."
    _M_INSTALL_MANUAL="  Installa manualmente Python $PYTHON_TARGET:"
    _M_INSTALL_PYENV="  Oppure usa pyenv (senza sudo): https://github.com/pyenv/pyenv"
    _M_PY_FOUND="Python $PYTHON_TARGET trovato:"
    _M_PY_NOT_FOUND_TARGET="Python $PYTHON_TARGET non trovato nel sistema."
    _M_PY_COMPAT_PRE="Uso Python"
    _M_PY_COMPAT_MID="come compatibile"
    _M_PY_RERUN="         Riesegui start.sh dopo aver installato Python $PYTHON_TARGET."
    _M_PY_TOO_NEW_A="trovato ma NON supportato da EMLyzer."
    _M_PY_TOO_NEW_B="         EMLyzer richiede Python $PYTHON_TARGET (max 3.$PYTHON_MAX_MINOR)."
    _M_PY_TOO_NEW_C="rimarra' intatto — installo $PYTHON_TARGET in parallelo."
    _M_PY_INSTALLED_NOACC="Python $PYTHON_TARGET installato ma non accessibile."
    _M_RESTART_TERM="         Riavvia il terminale e riesegui start.sh"
    _M_ARCH_INCOMPAT="La versione Python di sistema su Arch non e' compatibile."
    _M_ARCH_PYENV="Uso pyenv per installare Python $PYTHON_TARGET in parallelo..."
    _M_DISTRO_UNKNOWN="Distribuzione"
    _M_DISTRO_UNKNOWN2="non riconosciuta."
    _M_DISTRO_UBUNTU="Distribuzione Ubuntu/Debian-based rilevata."
    _M_DISTRO_DEBIAN="Distribuzione Debian pura rilevata."
    _M_DISTRO_FEDORA="Distribuzione Fedora rilevata."
    _M_DISTRO_RHEL="Distribuzione RHEL-based rilevata."
    _M_DISTRO_ARCH="Distribuzione Arch-based rilevata."
    _M_DISTRO_OPENSUSE="Distribuzione openSUSE rilevata."
    _M_DISTRO_MACOS="macOS rilevato."
    _M_STD_REPOS="Provo i repository standard..."
    _M_ALT_VER="Provo Python"
    _M_ALT_VER2="come alternativa..."
    _M_PY_VER_INSTALLED="Python"
    _M_PY_VER_INSTALLED2="installato."
    _M_PY_VER_STD="installato dai repository standard."
    _M_DEADSNAKES_PPA="Python $PYTHON_TARGET non nei repo standard."
    _M_DEADSNAKES_ADD="Aggiungo deadsnakes PPA (repository ufficiale per Python su Ubuntu)..."
    _M_DEADSNAKES_OK="Python $PYTHON_TARGET installato da deadsnakes PPA."
    _M_INST_AUTO_FAIL="Impossibile installare Python $PYTHON_TARGET automaticamente."
    _M_BACKPORTS="Provo backports Debian..."
    _M_BACKPORTS_OK="installato dai backports."
    _M_EPEL="Provo tramite EPEL..."
    _M_EPEL_OK="installato da EPEL."
    _M_BREW_INST="Installo Python $PYTHON_TARGET tramite Homebrew..."
    _M_BREW_MISSING="Homebrew non trovato."
    _M_BREW_HINT="         Installa Homebrew da https://brew.sh"
    _M_BREW_HINT2="         oppure Python $PYTHON_TARGET da https://www.python.org/downloads/"
    _M_VENV_NO_MODULE="Il modulo venv non e' disponibile per"
    _M_VENV_INST_PKG="Provo ad installare il pacchetto venv..."
    _M_VENV_FAIL="Impossibile abilitare il supporto venv."
    _M_VENV_CORRUPT="Virtual environment corrotto. Ricreazione..."
    _M_VENV_UPGRADE_PRE="Venv usa Python"
    _M_VENV_UPGRADE_MID="versione corrente e'"
    _M_VENV_UPGRADE_POST="Ricreazione..."
    _M_VENV_CREATING="Creazione virtual environment con"
    _M_VENV_ALT="Creazione venv fallita. Provo metodo alternativo..."
    _M_VENV_CREATED="Virtual environment creato in $VENV_DIR"
    _M_VENV_HARD_FAIL="Impossibile creare il virtual environment."
    _M_VENV_HINT_DEB="  Ubuntu/Debian: sudo apt install python3-venv python3-pip"
    _M_VENV_HINT_RPM="  Fedora/RHEL:   sudo dnf install python3-pip"
    _M_PIP_INST="Installazione pip nel virtual environment..."
    _M_PIP_FAIL="Impossibile installare pip."
    _M_PIP_HINT_DEB="  Ubuntu/Debian: sudo apt install python3-pip"
    _M_PIP_HINT_RPM="  Fedora/RHEL:   sudo dnf install python3-pip"
    _M_DEPS_INST="Installazione dipendenze..."
    _M_DEPS_OK="Dipendenze OK."
    _M_DEPS_FAIL="Installazione dipendenze fallita:"
    _M_ENV_CREATED="File .env creato da .env.example"
    _M_ENV_LANG="Modifica LANGUAGE in .env per cambiare lingua (it/en)"
    _M_PY_LABEL="Python:"
    _M_OPEN="  Apri il browser su:  http://localhost:$PORT"
    _M_DOCS="  Documentazione API:  http://localhost:$PORT/docs"
    _M_LANG_UI="  Lingua:              pulsante IT/EN in alto a destra"
    _M_STOP="  Premi CTRL+C per fermare"
    _M_STOPPED="Server fermato."
    _M_PYENV_TRY2="Tentativo installazione tramite pyenv (non richiede sudo)..."
    _M_PYENV_INST="Installo pyenv..."
    _M_PYENV_CURL_MISS="curl non disponibile. Impossibile installare pyenv."
    _M_PYENV_INIT_FAIL="Installazione pyenv fallita."
    _M_PYENV_FOUND="pyenv trovato. Installo Python $PYTHON_TARGET..."
    _M_PYENV_COMPILE_FAIL="Compilazione Python $PYTHON_TARGET fallita."
    _M_PYENV_BUILD_DEPS="         Verifica che le dipendenze di build siano installate."
fi

echo ""
echo " ============================================"
echo "  EMLyzer v$VERSION"
echo " ============================================"
echo ""

# ── Controlla che il backend esista ──────────────────────────────────────────
if [ ! -f "$BACKEND_DIR/main.py" ]; then
    echo "$_E $_M_BACKEND_MISSING"
    echo "$_M_BACKEND_HINT"
    exit 1
fi

# ── Controlla che il bundle frontend esista (o lo builda automaticamente) ────
FRONTEND_DIR="$SCRIPT_DIR/frontend"
if [ ! -f "$BACKEND_DIR/static/assets/index.js" ]; then
    if command -v node &>/dev/null && [ -f "$FRONTEND_DIR/package.json" ]; then
        echo "$_I $_M_FE_BUILDING"
        cd "$FRONTEND_DIR"
        npm install -q && npm run build
        cp -r "$FRONTEND_DIR/dist/." "$BACKEND_DIR/static/"
        cd "$SCRIPT_DIR"
        echo "$_I $_M_FE_BUILT"
        echo ""
    else
        echo "$_E $_M_FE_MISSING"
        echo "$_M_FE_HINT"
        echo "$_M_FE_CMD1"
        echo "$_M_FE_CMD2"
        exit 1
    fi
fi

# ── Controlla che la porta sia libera ────────────────────────────────────────
port_in_use=0
if command -v ss &>/dev/null; then
    ss -tlnp 2>/dev/null | grep -q ":$PORT " && port_in_use=1
elif command -v netstat &>/dev/null; then
    netstat -tlnp 2>/dev/null | grep -q ":$PORT " && port_in_use=1
else
    ( exec 3<>/dev/tcp/127.0.0.1/$PORT ) 2>/dev/null && port_in_use=1
fi
if [ "$port_in_use" = "1" ]; then
    echo "$_W $_M_PORT_BUSY"
    echo "$_M_PORT_HINT"
    echo "$_M_PORT_FIND"
    exit 1
fi

# ════════════════════════════════════════════════════════════════════════════
# RILEVAMENTO DISTRIBUZIONE
# ════════════════════════════════════════════════════════════════════════════
DISTRO_ID=""
DISTRO_LIKE=""
DISTRO_VERSION=""
DISTRO_FAMILY=""
OS_TYPE="linux"

detect_distro() {
    if [ "$(uname -s)" = "Darwin" ]; then
        OS_TYPE="macos"
        DISTRO_FAMILY="macos"
        DISTRO_ID="macos"
        DISTRO_VERSION="$(sw_vers -productVersion 2>/dev/null || echo 'unknown')"
        return
    fi

    if [ -f /etc/os-release ]; then
        # shellcheck source=/dev/null
        . /etc/os-release
        DISTRO_ID="${ID:-unknown}"
        DISTRO_LIKE="${ID_LIKE:-}"
        DISTRO_VERSION="${VERSION_ID:-unknown}"
    elif [ -f /etc/redhat-release ]; then
        DISTRO_ID="rhel"
        DISTRO_VERSION=$(grep -oP '[0-9]+\.[0-9]+' /etc/redhat-release | head -1)
    elif [ -f /etc/debian_version ]; then
        DISTRO_ID="debian"
        DISTRO_VERSION=$(cat /etc/debian_version)
    fi

    # Normalizza in famiglia
    case "$DISTRO_ID" in
        ubuntu|linuxmint|pop|elementary|zorin|neon|kali)
            DISTRO_FAMILY="ubuntu" ;;
        debian)
            DISTRO_FAMILY="debian" ;;
        fedora)
            DISTRO_FAMILY="fedora" ;;
        rhel|centos|rocky|almalinux|ol|scientific)
            DISTRO_FAMILY="rhel" ;;
        arch|manjaro|endeavouros|garuda|artix)
            DISTRO_FAMILY="arch" ;;
        opensuse*|sles|sled)
            DISTRO_FAMILY="opensuse" ;;
        *)
            # Fallback su ID_LIKE
            case "$DISTRO_LIKE" in
                *ubuntu*|*debian*)  DISTRO_FAMILY="ubuntu" ;;
                *fedora*|*rhel*)    DISTRO_FAMILY="rhel" ;;
                *arch*)             DISTRO_FAMILY="arch" ;;
                *suse*)             DISTRO_FAMILY="opensuse" ;;
                *)                  DISTRO_FAMILY="unknown" ;;
            esac
            ;;
    esac
}

detect_distro
if [ "$SCRIPT_LANG" = "en" ]; then
    echo "$_I System: $DISTRO_ID $DISTRO_VERSION (family: $DISTRO_FAMILY)"
else
    echo "$_I Sistema: $DISTRO_ID $DISTRO_VERSION (famiglia: $DISTRO_FAMILY)"
fi

# ════════════════════════════════════════════════════════════════════════════
# VERIFICA SUDO
# ════════════════════════════════════════════════════════════════════════════
HAS_SUDO=0
check_sudo() {
    if [ "$(id -u)" = "0" ]; then
        HAS_SUDO=1  # siamo root
        return
    fi
    if sudo -n true 2>/dev/null; then
        HAS_SUDO=1
    elif sudo -v 2>/dev/null; then
        HAS_SUDO=1
    fi
}
check_sudo

# Wrapper: esegui con sudo se disponibile, altrimenti fallisci con messaggio
run_privileged() {
    if [ "$(id -u)" = "0" ]; then
        "$@"
    elif [ "$HAS_SUDO" = "1" ]; then
        sudo "$@"
    else
        echo "$_E $_M_SUDO_NEEDED"
        echo "$_M_SUDO_HINT $*"
        return 1
    fi
}

# ════════════════════════════════════════════════════════════════════════════
# RICERCA PYTHON
# Strategia:
#   1. Cerca la versione esatta target (python3.13)
#   2. Accetta versioni compatibili nel range [MIN..MAX] come fallback
#   3. Se trova SOLO versioni > MAX (es. 3.14+): segnala e forza installazione
#   4. Se trova SOLO versioni < MIN (es. 3.10): segnala e forza installazione
# Per aggiornare: modifica PYTHON_TARGET/MAX_MINOR in cima allo script.
# ════════════════════════════════════════════════════════════════════════════
FOUND_PYTHON=""
FOUND_PYTHON_VER=""
NEED_INSTALL=0      # 1 = nessuna versione accettabile trovata, serve installare

# Risolve un candidato Python e ne verifica la versione.
# Setta le variabili globali _RESOLVED_BIN e _RESOLVED_MINOR.
# Cerca nel PATH e nei percorsi assoluti standard (per binari appena installati).
# Ritorna 0 se trovato e valido, 1 altrimenti.
_RESOLVED_BIN=""
_RESOLVED_MINOR=""

_resolve_python() {
    local candidate="$1"
    local python_bin=""

    # Cerca prima nel PATH
    if command -v "$candidate" &>/dev/null; then
        python_bin=$(command -v "$candidate")
    else
        # Percorsi assoluti standard — copre il caso "appena installato, non ancora in PATH"
        local dir
        for dir in /usr/bin /usr/local/bin /opt/homebrew/bin; do
            if [ -x "$dir/$candidate" ]; then
                python_bin="$dir/$candidate"
                break
            fi
        done
        # macOS homebrew con versione specifica (python@3.13)
        local ver_path="/opt/homebrew/opt/python@${candidate#python}/bin/$candidate"
        [ -z "$python_bin" ] && [ -x "$ver_path" ] && python_bin="$ver_path"
    fi

    # pyenv — gestisce versioni installate senza sudo
    if [ -z "$python_bin" ]; then
        local pyenv_root="${PYENV_ROOT:-$HOME/.pyenv}"
        # pyenv shims (se 'pyenv init' è stato eseguito)
        [ -x "$pyenv_root/shims/$candidate" ] && python_bin="$pyenv_root/shims/$candidate"
        # pyenv versione specifica
        if [ -z "$python_bin" ]; then
            local pyenv_bin
            pyenv_bin=$(find "$pyenv_root/versions" -name "$candidate" \
                -path "*/bin/$candidate" 2>/dev/null | sort -V | tail -1)
            [ -n "$pyenv_bin" ] && [ -x "$pyenv_bin" ] && python_bin="$pyenv_bin"
        fi
    fi

    # RHEL Software Collections (SCL) — percorsi non standard
    if [ -z "$python_bin" ]; then
        local scl_ver="${candidate#python}"   # "3.13" da "python3.13"
        local scl_pkg="${scl_ver/./}"         # "313"
        for scl_path in \
            "/opt/rh/python${scl_pkg}/root/usr/bin/${candidate}" \
            "/opt/rh/rh-python${scl_pkg}/root/usr/bin/${candidate}"; do
            if [ -x "$scl_path" ]; then python_bin="$scl_path"; break; fi
        done
    fi

    [ -z "$python_bin" ] && return 1

    local ver minor
    ver=$("$python_bin" -c "import sys; print('{}.{}'.format(sys.version_info.major, sys.version_info.minor))" 2>/dev/null)
    [ -z "$ver" ] && return 1
    [ "${ver%%.*}" = "3" ] || return 1
    minor="${ver##*.}"
    minor="${minor//[^0-9]/}"
    [ -z "$minor" ] && return 1

    _RESOLVED_BIN="$python_bin"
    _RESOLVED_MINOR="$minor"
    return 0
}


find_python() {
    NEED_INSTALL=0
    local too_new_found=0
    local too_new_ver=""

    # ── Passo 1: cerca ESATTAMENTE la versione target ─────────────────────────
    if _resolve_python "python${PYTHON_TARGET}"; then
        if [ "$_RESOLVED_MINOR" -ge "$PYTHON_MIN_MINOR" ] && \
           [ "$_RESOLVED_MINOR" -le "$PYTHON_MAX_MINOR" ] 2>/dev/null; then
            FOUND_PYTHON="$_RESOLVED_BIN"
            FOUND_PYTHON_VER="3.${_RESOLVED_MINOR}"
            echo "$_I $_M_PY_FOUND $FOUND_PYTHON"
            return 0
        fi
    fi

    # ── Passo 2: scansiona le versioni compatibili ────────────────────────────
    local best_bin="" best_ver="" best_minor=0

    for candidate in "python3.12" "python3.11" "python3" "python"; do
        _resolve_python "$candidate" || continue

        if [ "$_RESOLVED_MINOR" -gt "$PYTHON_MAX_MINOR" ] 2>/dev/null; then
            too_new_found=1
            too_new_ver="3.${_RESOLVED_MINOR}"
            continue
        fi
        if [ "$_RESOLVED_MINOR" -lt "$PYTHON_MIN_MINOR" ] 2>/dev/null; then
            continue
        fi
        if [ "$_RESOLVED_MINOR" -gt "$best_minor" ] 2>/dev/null; then
            best_minor="$_RESOLVED_MINOR"
            best_bin="$_RESOLVED_BIN"
            best_ver="3.${_RESOLVED_MINOR}"
        fi
    done

    if [ -n "$best_bin" ]; then
        FOUND_PYTHON="$best_bin"
        FOUND_PYTHON_VER="$best_ver"
        if [ "$best_minor" = "$PYTHON_TARGET_MINOR" ]; then
            echo "$_I $_M_PY_FOUND $FOUND_PYTHON"
        else
            echo "$_W $_M_PY_NOT_FOUND_TARGET"
            echo "$_W $_M_PY_COMPAT_PRE $best_ver $_M_PY_COMPAT_MID ($FOUND_PYTHON)."
            echo "$_M_PY_RERUN"
        fi
        return 0
    fi

    # ── Nessuna versione accettabile trovata ──────────────────────────────────
    NEED_INSTALL=1
    if [ "$too_new_found" = "1" ]; then
        echo "$_W Python $too_new_ver $_M_PY_TOO_NEW_A"
        echo "$_M_PY_TOO_NEW_B"
        echo "$_W Python $too_new_ver $_M_PY_TOO_NEW_C"
    fi
    return 1
}

# ════════════════════════════════════════════════════════════════════════════
# INSTALLAZIONE PYTHON PER FAMIGLIA DI DISTRO
# ════════════════════════════════════════════════════════════════════════════

# --- Ubuntu / Mint / Pop!_OS / Kali ---
install_python_ubuntu() {
    echo "$_I $_M_DISTRO_UBUNTU"
    echo "$_I $_M_STD_REPOS"
    run_privileged apt-get update -qq 2>/dev/null || true

    # Prova prima la versione target, poi le fallback
    for ver in "$PYTHON_TARGET" "3.12" "3.11"; do
        [ "$ver" = "$PYTHON_TARGET" ] || echo "$_I $_M_ALT_VER $ver $_M_ALT_VER2"
        if run_privileged apt-get install -y "python${ver}" "python${ver}-venv" "python${ver}-pip" 2>/dev/null; then
            echo "$_I $_M_PY_VER_INSTALLED $ver $_M_PY_VER_STD"
            return 0
        fi
    done

    # Deadsnakes PPA: repository di terze parti con build aggiornate per Ubuntu
    if [ "$DISTRO_ID" = "ubuntu" ] || echo "$DISTRO_LIKE" | grep -q "ubuntu"; then
        echo "$_I $_M_DEADSNAKES_PPA"
        echo "$_I $_M_DEADSNAKES_ADD"
        if ! command -v add-apt-repository &>/dev/null; then
            run_privileged apt-get install -y software-properties-common -qq
        fi
        if run_privileged add-apt-repository -y ppa:deadsnakes/ppa && \
           run_privileged apt-get update -qq; then
            if run_privileged apt-get install -y \
                "python${PYTHON_TARGET}" \
                "python${PYTHON_TARGET}-venv" \
                "python${PYTHON_TARGET}-pip" \
                "python${PYTHON_TARGET}-dev" 2>/dev/null; then
                echo "$_I $_M_DEADSNAKES_OK"
                return 0
            fi
        fi
    fi

    echo "$_W $_M_INST_AUTO_FAIL"
    return 1
}

# --- Debian pura ---
install_python_debian() {
    echo "$_I $_M_DISTRO_DEBIAN"
    run_privileged apt-get update -qq 2>/dev/null || true

    for ver in "$PYTHON_TARGET" "3.12" "3.11"; do
        if run_privileged apt-get install -y "python${ver}" "python${ver}-venv" "python${ver}-pip" 2>/dev/null; then
            echo "$_I $_M_PY_VER_INSTALLED $ver $_M_PY_VER_INSTALLED2"
            return 0
        fi
    done

    # Backports Debian
    echo "$_I $_M_BACKPORTS"
    local codename
    codename=$(grep -oP 'VERSION_CODENAME=\K\S+' /etc/os-release 2>/dev/null || lsb_release -cs 2>/dev/null || echo "")
    if [ -n "$codename" ]; then
        echo "deb http://deb.debian.org/debian ${codename}-backports main" | \
            run_privileged tee /etc/apt/sources.list.d/backports.list > /dev/null
        run_privileged apt-get update -qq
        for ver in "$PYTHON_TARGET" "3.12" "3.11"; do
            if run_privileged apt-get install -y -t "${codename}-backports" \
                "python${ver}" "python${ver}-venv" 2>/dev/null; then
                echo "$_I $_M_PY_VER_INSTALLED $ver $_M_BACKPORTS_OK"
                return 0
            fi
        done
    fi

    return 1
}

# --- Fedora ---
install_python_fedora() {
    echo "$_I $_M_DISTRO_FEDORA"
    for ver in "$PYTHON_TARGET" "3.12" "3.11"; do
        # Su Fedora il pacchetto python3.X include già venv;
        # python3.X-pip esiste solo su alcune versioni (non obbligatorio)
        if run_privileged dnf install -y "python${ver}" 2>/dev/null; then
            echo "$_I $_M_PY_VER_INSTALLED $ver $_M_PY_VER_INSTALLED2"
            # Installa pip se disponibile come pacchetto separato (non fatale se manca)
            run_privileged dnf install -y "python${ver}-pip" 2>/dev/null || true
            run_privileged dnf install -y python3-pip 2>/dev/null || true
            return 0
        fi
    done
    run_privileged dnf install -y python3 python3-pip python3-virtualenv 2>/dev/null
    return $?
}

# --- RHEL / Rocky / AlmaLinux / CentOS ---
install_python_rhel() {
    echo "$_I $_M_DISTRO_RHEL"
    # Prova prima la versione target, poi le fallback
    for ver in "$PYTHON_TARGET" "3.12" "3.11"; do
        if run_privileged dnf install -y "python${ver}" 2>/dev/null; then
            echo "$_I $_M_PY_VER_INSTALLED $ver $_M_PY_VER_INSTALLED2"
            run_privileged dnf install -y "python${ver}-pip" 2>/dev/null || true
            return 0
        fi
    done

    # EPEL: repository aggiuntivo Red Hat con Python più aggiornato
    echo "$_I $_M_EPEL"
    if ! rpm -q epel-release &>/dev/null; then
        run_privileged dnf install -y epel-release 2>/dev/null
    fi
    for ver in "$PYTHON_TARGET" "3.12" "3.11"; do
        if run_privileged dnf install -y "python${ver}" "python${ver}-pip" 2>/dev/null; then
            echo "$_I $_M_PY_VER_INSTALLED $ver $_M_EPEL_OK"
            return 0
        fi
    done
    run_privileged dnf install -y python3 python3-pip 2>/dev/null
    return $?
}

# --- Arch Linux / Manjaro ---
install_python_arch() {
    echo "$_I $_M_DISTRO_ARCH"
    # Arch installa sempre l'ultima versione stabile di Python come 'python'.
    # Non è possibile installare versioni specifiche tramite pacman —
    # se la versione di sistema è > MAX, usiamo pyenv (gestito dopo).
    run_privileged pacman -Sy --noconfirm python python-pip python-virtualenv 2>/dev/null
    # Su Arch, venv è sempre incluso nel pacchetto python — nessuna azione extra
    return $?
}

# --- openSUSE / SLES ---
install_python_opensuse() {
    echo "$_I $_M_DISTRO_OPENSUSE"
    # Su openSUSE il nome pacchetto omette il punto: python313, python312, ecc.
    local target_pkg="${PYTHON_TARGET/./}"  # "3.13" -> "313"
    for pkg in "$target_pkg" "312" "311"; do
        if run_privileged zypper install -y "python${pkg}" 2>/dev/null; then
            echo "$_I $_M_PY_VER_INSTALLED python${pkg} $_M_PY_VER_INSTALLED2"
            return 0
        fi
    done
    run_privileged zypper install -y python3 python3-pip 2>/dev/null
    return $?
}

# --- macOS ---
install_python_macos() {
    echo "$_I $_M_DISTRO_MACOS"
    if command -v brew &>/dev/null; then
        echo "$_I $_M_BREW_INST"
        # Prova versione target, poi fallback
        brew install "python@${PYTHON_TARGET}" && return 0
        for ver in "3.12" "3.11"; do
            brew install "python@${ver}" && return 0
        done
        brew install python3 && return 0
    else
        echo "$_W $_M_BREW_MISSING"
        echo "$_M_BREW_HINT"
        echo "$_M_BREW_HINT2"
        return 1
    fi
}

# --- Fallback: pyenv (senza sudo, compila da sorgente) ---
install_python_pyenv() {
    echo ""
    echo "$_I $_M_PYENV_TRY2"

    local pyenv_dir="$HOME/.pyenv"

    # Installa pyenv se non presente
    if ! command -v pyenv &>/dev/null && [ ! -f "$pyenv_dir/bin/pyenv" ]; then
        echo "$_I $_M_PYENV_INST"

        # Dipendenze build — tenta per famiglia
        case "$DISTRO_FAMILY" in
            ubuntu|debian)
                if [ "$HAS_SUDO" = "1" ]; then
                    sudo apt-get install -y -qq \
                        build-essential libssl-dev zlib1g-dev libbz2-dev \
                        libreadline-dev libsqlite3-dev libffi-dev liblzma-dev \
                        curl 2>/dev/null || true
                fi ;;
            fedora|rhel)
                if [ "$HAS_SUDO" = "1" ]; then
                    sudo dnf install -y \
                        gcc make openssl-devel zlib-devel bzip2-devel \
                        readline-devel sqlite-devel libffi-devel xz-devel \
                        curl 2>/dev/null || true
                fi ;;
        esac

        if ! command -v curl &>/dev/null; then
            echo "$_E $_M_PYENV_CURL_MISS"
            return 1
        fi

        curl -fsSL https://pyenv.run | bash

        # Aggiungi pyenv al PATH per questa sessione
        export PYENV_ROOT="$pyenv_dir"
        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)"
    elif [ -f "$pyenv_dir/bin/pyenv" ]; then
        export PYENV_ROOT="$pyenv_dir"
        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)"
    fi

    if ! command -v pyenv &>/dev/null; then
        echo "$_E $_M_PYENV_INIT_FAIL"
        return 1
    fi

    echo "$_I $_M_PYENV_FOUND"
    pyenv install -s "$PYTHON_TARGET" || {
        echo "$_E $_M_PYENV_COMPILE_FAIL"
        echo "$_M_PYENV_BUILD_DEPS"
        return 1
    }

    FOUND_PYTHON="$pyenv_dir/versions/$PYTHON_TARGET/bin/python3"
    [ -f "$FOUND_PYTHON" ] && return 0 || return 1
}

# ════════════════════════════════════════════════════════════════════════════
# LOGICA PRINCIPALE: cerca Python, installalo se manca o se troppo nuovo
# ════════════════════════════════════════════════════════════════════════════
echo "$_I $_M_SEARCHING_PY"
echo ""

_do_install_python() {
    # Tenta installazione via package manager della distro, poi pyenv come fallback
    local install_ok=0
    case "$DISTRO_FAMILY" in
        ubuntu)   install_python_ubuntu   && install_ok=1 ;;
        debian)   install_python_debian   && install_ok=1 ;;
        fedora)   install_python_fedora   && install_ok=1 ;;
        rhel)     install_python_rhel     && install_ok=1 ;;
        arch)
            # Arch installa solo l'ultima versione Python — se è > MAX, pyenv
            install_python_arch && install_ok=1
            if [ "$install_ok" = "1" ]; then
                # Verifica se la versione installata è accettabile
                hash -r
                if ! find_python; then
                    echo "$_I $_M_ARCH_INCOMPAT"
                    echo "$_I $_M_ARCH_PYENV"
                    install_ok=0
                fi
            fi
            ;;
        opensuse) install_python_opensuse && install_ok=1 ;;
        macos)    install_python_macos    && install_ok=1 ;;
        *)
            echo "$_W $_M_DISTRO_UNKNOWN '$DISTRO_ID' $_M_DISTRO_UNKNOWN2"
            ;;
    esac

    if [ "$install_ok" = "1" ]; then
        hash -r  # aggiorna cache bash
        # Cerca anche nei percorsi assoluti standard — la sessione bash corrente
        # potrebbe non avere ancora python3.13 nella cache PATH
        if find_python; then
            return 0
        fi
        # Ultimo tentativo: percorso assoluto diretto
        local abs="/usr/bin/python${PYTHON_TARGET}"
        if [ -x "$abs" ]; then
            FOUND_PYTHON="$abs"
            FOUND_PYTHON_VER="$PYTHON_TARGET"
            echo "$_I $_M_PY_FOUND $abs"
            return 0
        fi
        echo "$_E $_M_PY_INSTALLED_NOACC"
        echo "$_M_RESTART_TERM"
        exit 1
    fi

    # Fallback: pyenv (compila da sorgente, non richiede sudo, non tocca il sistema)
    echo "$_I $_M_PKG_FAIL"
    echo "$_I $_M_PYENV_TRY"
    if install_python_pyenv; then
        hash -r
        find_python && return 0
        echo "$_E $_M_PYENV_NOT_FOUND"
        exit 1
    fi

    # Nessun metodo riuscito
    echo ""
    echo "$_E $_M_INSTALL_FAIL"
    echo ""
    echo "$_M_INSTALL_MANUAL"
    case "$DISTRO_FAMILY" in
        ubuntu|debian)
            echo "    sudo apt install python${PYTHON_TARGET} python${PYTHON_TARGET}-venv python${PYTHON_TARGET}-pip"
            if [ "$DISTRO_FAMILY" = "ubuntu" ]; then
                if [ "$SCRIPT_LANG" = "en" ]; then
                    echo "    (if unavailable: sudo add-apt-repository ppa:deadsnakes/ppa)"
                else
                    echo "    (se non disponibile: sudo add-apt-repository ppa:deadsnakes/ppa)"
                fi
            fi
            ;;
        fedora)
            echo "    sudo dnf install python${PYTHON_TARGET} python${PYTHON_TARGET}-pip" ;;
        rhel)
            echo "    sudo dnf install python${PYTHON_TARGET}"
            if [ "$SCRIPT_LANG" = "en" ]; then
                echo "    (if unavailable: sudo dnf install epel-release)"
            else
                echo "    (se non disponibile: sudo dnf install epel-release)"
            fi
            ;;
        arch)
            if [ "$SCRIPT_LANG" = "en" ]; then
                echo "    sudo pacman -S python  (Arch always ships the latest stable Python)"
            else
                echo "    sudo pacman -S python  (Arch ha sempre l'ultima versione stabile)"
            fi
            ;;
        opensuse)
            local pkg="${PYTHON_TARGET/./}"
            echo "    sudo zypper install python${pkg}" ;;
        macos)
            echo "    brew install python@${PYTHON_TARGET}" ;;
        *)
            echo "    https://www.python.org/downloads/" ;;
    esac
    echo ""
    echo "$_M_INSTALL_PYENV"
    exit 1
}

if ! find_python; then
    echo ""
    if [ "$SCRIPT_LANG" = "en" ]; then
        echo "$_I Installing Python $PYTHON_TARGET for $DISTRO_ID $DISTRO_VERSION..."
    else
        echo "$_I Installo Python $PYTHON_TARGET per $DISTRO_ID $DISTRO_VERSION..."
    fi
    echo "$_M_INSTALL_PY2"
    echo ""
    _do_install_python
fi

echo ""

# ════════════════════════════════════════════════════════════════════════════
# VERIFICA E INSTALLAZIONE PACCHETTI VENV/PIP
# ════════════════════════════════════════════════════════════════════════════
# Su alcune distro python3.X-venv è un pacchetto separato
ensure_venv_support() {
    # Testa se venv funziona
    if "$FOUND_PYTHON" -m venv --help &>/dev/null; then
        return 0
    fi

    echo "$_W $_M_VENV_NO_MODULE $FOUND_PYTHON."
    echo "$_I $_M_VENV_INST_PKG"

    local ver
    ver=$("$FOUND_PYTHON" -c "import sys; print('{}.{}'.format(sys.version_info.major, sys.version_info.minor))" 2>/dev/null)

    case "$DISTRO_FAMILY" in
        ubuntu|debian)
            run_privileged apt-get install -y "python${ver}-venv" "python${ver}-pip" 2>/dev/null || \
            run_privileged apt-get install -y python3-venv python3-pip 2>/dev/null ;;
        fedora|rhel)
            # Su Fedora/RHEL venv è incluso in python3.X — installiamo pip se manca
            run_privileged dnf install -y "python${ver}-pip" 2>/dev/null || \
            run_privileged dnf install -y python3-pip python3-virtualenv 2>/dev/null || true ;;
        arch)
            run_privileged pacman -Sy --noconfirm python-virtualenv 2>/dev/null ;;
        opensuse)
            run_privileged zypper install -y python3-virtualenv 2>/dev/null ;;
    esac

    # Ricontrolla
    "$FOUND_PYTHON" -m venv --help &>/dev/null && return 0
    echo "$_E $_M_VENV_FAIL"
    return 1
}

ensure_venv_support || exit 1

# ════════════════════════════════════════════════════════════════════════════
# GESTIONE VIRTUAL ENVIRONMENT
# ════════════════════════════════════════════════════════════════════════════
WANTED_VER=$("$FOUND_PYTHON" -c "import sys; print('{}.{}'.format(sys.version_info.major, sys.version_info.minor))")

if [ -f "$VENV_PYTHON" ]; then
    VENV_VER=$("$VENV_PYTHON" -c "import sys; print('{}.{}'.format(sys.version_info.major, sys.version_info.minor))" 2>/dev/null)

    if [ -z "$VENV_VER" ]; then
        echo "$_I $_M_VENV_CORRUPT"
        rm -rf "$VENV_DIR"
    elif [ "$VENV_VER" != "$WANTED_VER" ]; then
        echo "$_I $_M_VENV_UPGRADE_PRE $VENV_VER, $_M_VENV_UPGRADE_MID $WANTED_VER. $_M_VENV_UPGRADE_POST"
        rm -rf "$VENV_DIR"
    fi
fi

if [ ! -f "$VENV_PYTHON" ]; then
    echo "$_I $_M_VENV_CREATING $("$FOUND_PYTHON" --version 2>&1)..."

    # Primo tentativo: normale
    if ! "$FOUND_PYTHON" -m venv "$VENV_DIR" 2>/tmp/emlyzer_venv_err; then
        echo "$_W $_M_VENV_ALT"
        cat /tmp/emlyzer_venv_err

        # Secondo tentativo: senza pip (Fedora/RHEL senza python3-pip)
        if ! "$FOUND_PYTHON" -m venv --without-pip "$VENV_DIR" 2>/tmp/emlyzer_venv_err2; then
            echo "$_E $_M_VENV_HARD_FAIL"
            cat /tmp/emlyzer_venv_err2
            echo ""
            echo "$_M_VENV_HINT_DEB"
            echo "$_M_VENV_HINT_RPM"
            exit 1
        fi

        # Installa pip nel venv
        if [ ! -f "$VENV_DIR/bin/pip" ]; then
            echo "$_I $_M_PIP_INST"
            "$VENV_DIR/bin/python" -m ensurepip --upgrade 2>/dev/null || \
            "$VENV_DIR/bin/python" -m ensurepip 2>/dev/null || {
                echo "$_E $_M_PIP_FAIL"
                echo "$_M_PIP_HINT_DEB"
                echo "$_M_PIP_HINT_RPM"
                exit 1
            }
        fi
    fi

    echo "$_I $_M_VENV_CREATED"
    echo ""
fi

# ════════════════════════════════════════════════════════════════════════════
# DIPENDENZE
# ════════════════════════════════════════════════════════════════════════════
"$VENV_PYTHON" -m pip install --upgrade pip -q 2>/dev/null || true

echo "$_I $_M_DEPS_INST"
if ! "$VENV_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt" -q 2>/tmp/emlyzer_pip_err; then
    echo "$_E $_M_DEPS_FAIL"
    cat /tmp/emlyzer_pip_err
    exit 1
fi
echo "$_I $_M_DEPS_OK"
echo ""

# ════════════════════════════════════════════════════════════════════════════
# FILE .env
# ════════════════════════════════════════════════════════════════════════════
if [ ! -f "$BACKEND_DIR/.env" ] && [ -f "$BACKEND_DIR/.env.example" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    echo "$_I $_M_ENV_CREATED"
    echo "$_I $_M_ENV_LANG"
fi

# ════════════════════════════════════════════════════════════════════════════
# AVVIO
# ════════════════════════════════════════════════════════════════════════════
echo "$_I $_M_PY_LABEL $("$VENV_PYTHON" --version 2>&1)"
echo ""
echo "$_M_OPEN"
echo "$_M_DOCS"
echo "$_M_LANG_UI"
echo ""
echo "$_M_STOP"
echo ""

cd "$BACKEND_DIR"
exec "$VENV_PYTHON" -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload
