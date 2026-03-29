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
VERSION=$(grep -oP '(?<=VERSION: str = ")[^"]+' "$BACKEND_DIR/utils/config.py" 2>/dev/null || echo "0.3.3")

echo ""
echo " ============================================"
echo "  EMLyzer v$VERSION"
echo " ============================================"
echo ""

# ── Controlla che il backend esista ──────────────────────────────────────────
if [ ! -f "$BACKEND_DIR/main.py" ]; then
    echo "[ERRORE] File backend/main.py non trovato."
    echo "         Esegui start.sh dalla cartella EMLyzer/"
    exit 1
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
    echo "[AVVISO] La porta $PORT e' gia' in uso."
    echo "         Ferma il processo che la occupa e riprova."
    echo "         Per trovarlo: lsof -i :$PORT  oppure  ss -tlnp | grep $PORT"
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
echo "[INFO] Sistema: $DISTRO_ID $DISTRO_VERSION (famiglia: $DISTRO_FAMILY)"

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
        echo "[ERRORE] Operazione richiede privilegi di amministratore."
        echo "         Esegui manualmente: sudo $*"
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
            pyenv_bin=$(find "$pyenv_root/versions" -name "$candidate"                 -path "*/bin/$candidate" 2>/dev/null | sort -V | tail -1)
            [ -n "$pyenv_bin" ] && [ -x "$pyenv_bin" ] && python_bin="$pyenv_bin"
        fi
    fi

    # RHEL Software Collections (SCL) — percorsi non standard
    if [ -z "$python_bin" ]; then
        local scl_ver="${candidate#python}"   # "3.13" da "python3.13"
        local scl_pkg="${scl_ver/./}"         # "313"
        for scl_path in             "/opt/rh/python${scl_pkg}/root/usr/bin/${candidate}"             "/opt/rh/rh-python${scl_pkg}/root/usr/bin/${candidate}"; do
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
        if [ "$_RESOLVED_MINOR" -ge "$PYTHON_MIN_MINOR" ] &&            [ "$_RESOLVED_MINOR" -le "$PYTHON_MAX_MINOR" ] 2>/dev/null; then
            FOUND_PYTHON="$_RESOLVED_BIN"
            FOUND_PYTHON_VER="3.${_RESOLVED_MINOR}"
            echo "[INFO] Python $PYTHON_TARGET trovato: $FOUND_PYTHON"
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
            echo "[INFO] Python $PYTHON_TARGET trovato: $FOUND_PYTHON"
        else
            echo "[AVVISO] Python $PYTHON_TARGET non trovato nel sistema."
            echo "[AVVISO] Uso Python $best_ver come compatibile ($FOUND_PYTHON)."
            echo "         Riesegui start.sh dopo aver installato Python $PYTHON_TARGET."
        fi
        return 0
    fi

    # ── Nessuna versione accettabile trovata ──────────────────────────────────
    NEED_INSTALL=1
    if [ "$too_new_found" = "1" ]; then
        echo "[AVVISO] Python $too_new_ver trovato ma NON supportato da EMLyzer."
        echo "         EMLyzer richiede Python $PYTHON_TARGET (max 3.$PYTHON_MAX_MINOR)."
        echo "         Python $too_new_ver rimarra' intatto — installo $PYTHON_TARGET in parallelo."
    fi
    return 1
}

# ════════════════════════════════════════════════════════════════════════════
# INSTALLAZIONE PYTHON PER FAMIGLIA DI DISTRO
# ════════════════════════════════════════════════════════════════════════════

# --- Ubuntu / Mint / Pop!_OS / Kali ---
install_python_ubuntu() {
    echo "[INFO] Distribuzione Ubuntu/Debian-based rilevata."
    echo "[INFO] Provo i repository standard..."
    run_privileged apt-get update -qq 2>/dev/null || true

    # Prova prima la versione target, poi le fallback
    for ver in "$PYTHON_TARGET" "3.12" "3.11"; do
        [ "$ver" = "$PYTHON_TARGET" ] || echo "[INFO] Provo Python $ver come alternativa..."
        if run_privileged apt-get install -y "python${ver}" "python${ver}-venv" "python${ver}-pip" 2>/dev/null; then
            echo "[INFO] Python $ver installato dai repository standard."
            return 0
        fi
    done

    # Deadsnakes PPA: repository di terze parti con build aggiornate per Ubuntu
    if [ "$DISTRO_ID" = "ubuntu" ] || echo "$DISTRO_LIKE" | grep -q "ubuntu"; then
        echo "[INFO] Python $PYTHON_TARGET non nei repo standard."
        echo "[INFO] Aggiungo deadsnakes PPA (repository ufficiale per Python su Ubuntu)..."
        if ! command -v add-apt-repository &>/dev/null; then
            run_privileged apt-get install -y software-properties-common -qq
        fi
        if run_privileged add-apt-repository -y ppa:deadsnakes/ppa &&            run_privileged apt-get update -qq; then
            if run_privileged apt-get install -y                 "python${PYTHON_TARGET}"                 "python${PYTHON_TARGET}-venv"                 "python${PYTHON_TARGET}-pip"                 "python${PYTHON_TARGET}-dev" 2>/dev/null; then
                echo "[INFO] Python $PYTHON_TARGET installato da deadsnakes PPA."
                return 0
            fi
        fi
    fi

    echo "[AVVISO] Impossibile installare Python $PYTHON_TARGET automaticamente."
    return 1
}

# --- Debian pura ---
install_python_debian() {
    echo "[INFO] Distribuzione Debian pura rilevata."
    run_privileged apt-get update -qq 2>/dev/null || true

    for ver in "$PYTHON_TARGET" "3.12" "3.11"; do
        if run_privileged apt-get install -y "python${ver}" "python${ver}-venv" "python${ver}-pip" 2>/dev/null; then
            echo "[INFO] Python $ver installato."
            return 0
        fi
    done

    # Backports Debian
    echo "[INFO] Provo backports Debian..."
    local codename
    codename=$(grep -oP 'VERSION_CODENAME=\K\S+' /etc/os-release 2>/dev/null || lsb_release -cs 2>/dev/null || echo "")
    if [ -n "$codename" ]; then
        echo "deb http://deb.debian.org/debian ${codename}-backports main" |             run_privileged tee /etc/apt/sources.list.d/backports.list > /dev/null
        run_privileged apt-get update -qq
        for ver in "$PYTHON_TARGET" "3.12" "3.11"; do
            if run_privileged apt-get install -y -t "${codename}-backports"                 "python${ver}" "python${ver}-venv" 2>/dev/null; then
                echo "[INFO] Python $ver installato dai backports."
                return 0
            fi
        done
    fi

    return 1
}

# --- Fedora ---
install_python_fedora() {
    echo "[INFO] Distribuzione Fedora rilevata."
    for ver in "$PYTHON_TARGET" "3.12" "3.11"; do
        # Su Fedora il pacchetto python3.X include già venv;
        # python3.X-pip esiste solo su alcune versioni (non obbligatorio)
        if run_privileged dnf install -y "python${ver}" 2>/dev/null; then
            echo "[INFO] Python $ver installato."
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
    echo "[INFO] Distribuzione RHEL-based rilevata."
    # Prova prima la versione target, poi le fallback
    for ver in "$PYTHON_TARGET" "3.12" "3.11"; do
        if run_privileged dnf install -y "python${ver}" 2>/dev/null; then
            echo "[INFO] Python $ver installato."
            run_privileged dnf install -y "python${ver}-pip" 2>/dev/null || true
            return 0
        fi
    done

    # EPEL: repository aggiuntivo Red Hat con Python più aggiornato
    echo "[INFO] Provo tramite EPEL..."
    if ! rpm -q epel-release &>/dev/null; then
        run_privileged dnf install -y epel-release 2>/dev/null
    fi
    for ver in "$PYTHON_TARGET" "3.12" "3.11"; do
        if run_privileged dnf install -y "python${ver}" "python${ver}-pip" 2>/dev/null; then
            echo "[INFO] Python $ver installato da EPEL."
            return 0
        fi
    done
    run_privileged dnf install -y python3 python3-pip 2>/dev/null
    return $?
}

# --- Arch Linux / Manjaro ---
install_python_arch() {
    echo "[INFO] Distribuzione Arch-based rilevata."
    # Arch installa sempre l'ultima versione stabile di Python come 'python'.
    # Non è possibile installare versioni specifiche tramite pacman —
    # se la versione di sistema è > MAX, usiamo pyenv (gestito dopo).
    run_privileged pacman -Sy --noconfirm python python-pip python-virtualenv 2>/dev/null
    # Su Arch, venv è sempre incluso nel pacchetto python — nessuna azione extra
    return $?
}

# --- openSUSE / SLES ---
install_python_opensuse() {
    echo "[INFO] Distribuzione openSUSE rilevata."
    # Su openSUSE il nome pacchetto omette il punto: python313, python312, ecc.
    local target_pkg="${PYTHON_TARGET/./}"  # "3.13" -> "313"
    for pkg in "$target_pkg" "312" "311"; do
        if run_privileged zypper install -y "python${pkg}" 2>/dev/null; then
            echo "[INFO] Python installato (python${pkg})."
            return 0
        fi
    done
    run_privileged zypper install -y python3 python3-pip 2>/dev/null
    return $?
}

# --- macOS ---
install_python_macos() {
    echo "[INFO] macOS rilevato."
    if command -v brew &>/dev/null; then
        echo "[INFO] Installo Python $PYTHON_TARGET tramite Homebrew..."
        # Prova versione target, poi fallback
        brew install "python@${PYTHON_TARGET}" && return 0
        for ver in "3.12" "3.11"; do
            brew install "python@${ver}" && return 0
        done
        brew install python3 && return 0
    else
        echo "[AVVISO] Homebrew non trovato."
        echo "         Installa Homebrew da https://brew.sh"
        echo "         oppure Python $PYTHON_TARGET da https://www.python.org/downloads/"
        return 1
    fi
}

# --- Fallback: pyenv (senza sudo, compila da sorgente) ---
install_python_pyenv() {
    echo ""
    echo "[INFO] Tentativo installazione tramite pyenv (non richiede sudo)..."

    local pyenv_dir="$HOME/.pyenv"

    # Installa pyenv se non presente
    if ! command -v pyenv &>/dev/null && [ ! -f "$pyenv_dir/bin/pyenv" ]; then
        echo "[INFO] Installo pyenv..."

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
            echo "[ERRORE] curl non disponibile. Impossibile installare pyenv."
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
        echo "[ERRORE] Installazione pyenv fallita."
        return 1
    fi

    echo "[INFO] pyenv trovato. Installo Python $PYTHON_TARGET..."
    pyenv install -s "$PYTHON_TARGET" || {
        echo "[ERRORE] Compilazione Python $PYTHON_TARGET fallita."
        echo "         Verifica che le dipendenze di build siano installate."
        return 1
    }

    FOUND_PYTHON="$pyenv_dir/versions/$PYTHON_TARGET/bin/python3"
    [ -f "$FOUND_PYTHON" ] && return 0 || return 1
}

# ════════════════════════════════════════════════════════════════════════════
# LOGICA PRINCIPALE: cerca Python, installalo se manca o se troppo nuovo
# ════════════════════════════════════════════════════════════════════════════
echo "[INFO] Ricerca Python $PYTHON_TARGET (range accettabile: 3.$PYTHON_MIN_MINOR - 3.$PYTHON_MAX_MINOR)..."
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
                    echo "[INFO] La versione Python di sistema su Arch non e' compatibile."
                    echo "[INFO] Uso pyenv per installare Python $PYTHON_TARGET in parallelo..."
                    install_ok=0
                fi
            fi
            ;;
        opensuse) install_python_opensuse && install_ok=1 ;;
        macos)    install_python_macos    && install_ok=1 ;;
        *)
            echo "[AVVISO] Distribuzione '$DISTRO_ID' non riconosciuta."
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
            echo "[INFO] Python $PYTHON_TARGET trovato in $abs"
            return 0
        fi
        echo "[ERRORE] Python $PYTHON_TARGET installato ma non accessibile."
        echo "         Riavvia il terminale e riesegui start.sh"
        exit 1
    fi

    # Fallback: pyenv (compila da sorgente, non richiede sudo, non tocca il sistema)
    echo "[INFO] Package manager non disponibile o installazione fallita."
    echo "[INFO] Provo con pyenv (compila Python $PYTHON_TARGET senza modificare il sistema)..."
    if install_python_pyenv; then
        hash -r
        find_python && return 0
        echo "[ERRORE] pyenv installato ma Python $PYTHON_TARGET non trovato."
        exit 1
    fi

    # Nessun metodo riuscito
    echo ""
    echo "[ERRORE] Impossibile installare Python $PYTHON_TARGET automaticamente."
    echo ""
    echo "  Installa manualmente Python $PYTHON_TARGET:"
    case "$DISTRO_FAMILY" in
        ubuntu|debian)
            echo "    sudo apt install python${PYTHON_TARGET} python${PYTHON_TARGET}-venv python${PYTHON_TARGET}-pip"
            echo "    (se non disponibile: sudo add-apt-repository ppa:deadsnakes/ppa)"
            ;;
        fedora)
            echo "    sudo dnf install python${PYTHON_TARGET} python${PYTHON_TARGET}-pip" ;;
        rhel)
            echo "    sudo dnf install python${PYTHON_TARGET}"
            echo "    (se non disponibile: sudo dnf install epel-release)"
            ;;
        arch)
            echo "    sudo pacman -S python  (Arch ha sempre l'ultima versione stabile)" ;;
        opensuse)
            local pkg="${PYTHON_TARGET/./}"
            echo "    sudo zypper install python${pkg}" ;;
        macos)
            echo "    brew install python@${PYTHON_TARGET}" ;;
        *)
            echo "    Visita: https://www.python.org/downloads/" ;;
    esac
    echo ""
    echo "  Oppure usa pyenv (senza sudo): https://github.com/pyenv/pyenv"
    exit 1
}

if ! find_python; then
    echo ""
    echo "[INFO] Installo Python $PYTHON_TARGET per $DISTRO_ID $DISTRO_VERSION..."
    echo "       (il Python di sistema rimarra' intatto)"
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

    echo "[AVVISO] Il modulo venv non e' disponibile per $FOUND_PYTHON."
    echo "[INFO] Provo ad installare il pacchetto venv..."

    local ver
    ver=$("$FOUND_PYTHON" -c "import sys; print('{}.{}'.format(sys.version_info.major, sys.version_info.minor))" 2>/dev/null)

    case "$DISTRO_FAMILY" in
        ubuntu|debian)
            run_privileged apt-get install -y "python${ver}-venv" "python${ver}-pip" 2>/dev/null || \
            run_privileged apt-get install -y python3-venv python3-pip 2>/dev/null ;;
        fedora|rhel)
            # Su Fedora/RHEL venv è incluso in python3.X — installiamo pip se manca
            run_privileged dnf install -y "python${ver}-pip" 2>/dev/null ||             run_privileged dnf install -y python3-pip python3-virtualenv 2>/dev/null || true ;;
        arch)
            run_privileged pacman -Sy --noconfirm python-virtualenv 2>/dev/null ;;
        opensuse)
            run_privileged zypper install -y python3-virtualenv 2>/dev/null ;;
    esac

    # Ricontrolla
    "$FOUND_PYTHON" -m venv --help &>/dev/null && return 0
    echo "[ERRORE] Impossibile abilitare il supporto venv."
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
        echo "[INFO] Virtual environment corrotto. Ricreazione..."
        rm -rf "$VENV_DIR"
    elif [ "$VENV_VER" != "$WANTED_VER" ]; then
        echo "[INFO] Venv usa Python $VENV_VER, versione corrente e' $WANTED_VER. Ricreazione..."
        rm -rf "$VENV_DIR"
    fi
fi

if [ ! -f "$VENV_PYTHON" ]; then
    echo "[INFO] Creazione virtual environment con $("$FOUND_PYTHON" --version 2>&1)..."

    # Primo tentativo: normale
    if ! "$FOUND_PYTHON" -m venv "$VENV_DIR" 2>/tmp/emlyzer_venv_err; then
        echo "[AVVISO] Creazione venv fallita. Provo metodo alternativo..."
        cat /tmp/emlyzer_venv_err

        # Secondo tentativo: senza pip (Fedora/RHEL senza python3-pip)
        if ! "$FOUND_PYTHON" -m venv --without-pip "$VENV_DIR" 2>/tmp/emlyzer_venv_err2; then
            echo "[ERRORE] Impossibile creare il virtual environment."
            cat /tmp/emlyzer_venv_err2
            echo ""
            echo "  Ubuntu/Debian: sudo apt install python3-venv python3-pip"
            echo "  Fedora/RHEL:   sudo dnf install python3-pip"
            exit 1
        fi

        # Installa pip nel venv
        if [ ! -f "$VENV_DIR/bin/pip" ]; then
            echo "[INFO] Installazione pip nel virtual environment..."
            "$VENV_DIR/bin/python" -m ensurepip --upgrade 2>/dev/null || \
            "$VENV_DIR/bin/python" -m ensurepip 2>/dev/null || {
                echo "[ERRORE] Impossibile installare pip."
                echo "  Ubuntu/Debian: sudo apt install python3-pip"
                echo "  Fedora/RHEL:   sudo dnf install python3-pip"
                exit 1
            }
        fi
    fi

    echo "[INFO] Virtual environment creato in $VENV_DIR"
    echo ""
fi

# ════════════════════════════════════════════════════════════════════════════
# DIPENDENZE
# ════════════════════════════════════════════════════════════════════════════
"$VENV_PYTHON" -m pip install --upgrade pip -q 2>/dev/null || true

echo "[INFO] Installazione dipendenze..."
if ! "$VENV_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt" -q 2>/tmp/emlyzer_pip_err; then
    echo "[ERRORE] Installazione dipendenze fallita:"
    cat /tmp/emlyzer_pip_err
    exit 1
fi
echo "[INFO] Dipendenze OK."
echo ""

# ════════════════════════════════════════════════════════════════════════════
# FILE .env
# ════════════════════════════════════════════════════════════════════════════
if [ ! -f "$BACKEND_DIR/.env" ] && [ -f "$BACKEND_DIR/.env.example" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    echo "[INFO] File .env creato da .env.example"
    echo "[INFO] Modifica LANGUAGE in .env per cambiare lingua (it/en)"
fi

# ════════════════════════════════════════════════════════════════════════════
# AVVIO
# ════════════════════════════════════════════════════════════════════════════
echo "[INFO] Python: $("$VENV_PYTHON" --version 2>&1)"
echo ""
echo "  Apri il browser su:  http://localhost:$PORT"
echo "  Documentazione API:  http://localhost:$PORT/docs"
echo "  Lingua:              pulsante IT/EN in alto a destra"
echo ""
echo "  Premi CTRL+C per fermare"
echo ""

cd "$BACKEND_DIR"
exec "$VENV_PYTHON" -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload