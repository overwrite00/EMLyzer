@echo off
:: EMLyzer - Avvio (Windows)
:: Compatibile con Windows 10/11, Python 3.11+
setlocal enabledelayedexpansion

set "BACKEND_DIR=%~dp0backend"
set "VENV_DIR=%~dp0.venv"
set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
set "FOUND_PYTHON="
set "FOUND_VER="
set "VERSION=0.14.0"

:: ── Lingua output (it/en) — rilevata dalla locale di sistema ──────────────────
:: Default: italiano. Se la lingua UI di Windows e' inglese, usa l'inglese.
set "SCRIPT_LANG=it"
for /f "usebackq tokens=*" %%L in (`powershell -NoProfile -Command "[System.Globalization.CultureInfo]::CurrentUICulture.TwoLetterISOLanguageName" 2^>nul`) do (
    if /i "%%L"=="en" set "SCRIPT_LANG=en"
)

if "!SCRIPT_LANG!"=="en" (
    set "_E=[ERROR]"
    set "_W=[WARNING]"
    set "_I=[INFO]"
    set "_M_BACKEND_MISSING=File backend\main.py not found."
    set "_M_BACKEND_HINT=         Run start.bat from the EMLyzer\ folder"
    set "_M_FE_BUILDING=Frontend bundle not found. Building frontend..."
    set "_M_FE_BUILT=Frontend compiled and copied."
    set "_M_FE_MISSING=Frontend bundle not found: backend\static\assets\index.js"
    set "_M_FE_COPY=         Copy files from the release or run:"
    set "_M_PORT_BUSY=Port 8000 is already in use."
    set "_M_PORT_HINT1=         Another instance of EMLyzer may be running,"
    set "_M_PORT_HINT2=         or another program is using port 8000."
    set "_M_PORT_HINT3=         Stop it before launching EMLyzer."
    set "_M_PORT_FIND=         To find the process: netstat -ano ^| findstr :8000"
    set "_M_PY_SEARCHING=Looking for compatible Python version..."
    set "_M_PY_OLD=too old. Required 3.11+."
    set "_M_PY_URL=         Install Python 3.13 from https://www.python.org/downloads/"
    set "_M_PY_PATH=         During installation check 'Add Python to PATH'"
    set "_M_PY_NOT_FOUND=Python not found on this system."
    set "_M_PY_NOT_FOUND2=         Install Python 3.13 from https://www.python.org/downloads/"
    set "_M_PY_PATH2=         During installation check 'Add Python to PATH'"
    set "_M_PY_USING=Using:"
    set "_M_PY_WARN14=Python - some libraries may not be supported."
    set "_M_PY_REC=         Recommended: Python 3.13 from https://www.python.org/downloads/"
    set "_M_VENV_RECREATING=Recreating virtual environment..."
    set "_M_VENV_CREATING_PRE=Creating virtual environment with"
    set "_M_VENV_CREATED=Virtual environment created."
    set "_M_VENV_FAILED=Cannot create virtual environment."
    set "_M_VENV_HINT=         Try manually:"
    set "_M_DEPS_INSTALLING=Installing dependencies..."
    set "_M_DEPS_OK=Dependencies OK."
    set "_M_DEPS_FAILED=Dependencies installation failed."
    set "_M_DEPS_RETRY=         Re-run without -q to see details:"
    set "_M_ENV_CREATED=.env file created from .env.example"
    set "_M_ENV_LANG=To change language: edit LANGUAGE in .env ^(it/en^)"
    set "_M_PY_IN_VENV=Python in venv:"
    set "_M_READY=  Application ready"
    set "_M_BROWSER=  Open browser at:  http://localhost:8000"
    set "_M_API_DOCS=  API docs:         http://localhost:8000/docs"
    set "_M_LANG_HINT=  Language:         IT/EN button top right"
    set "_M_CTRLC=  Press CTRL+C to stop"
    set "_M_SERVER_STOPPED=Server stopped."
) else (
    set "_E=[ERRORE]"
    set "_W=[AVVISO]"
    set "_I=[INFO]"
    set "_M_BACKEND_MISSING=File backend\main.py non trovato."
    set "_M_BACKEND_HINT=         Esegui start.bat dalla cartella EMLyzer\"
    set "_M_FE_BUILDING=Bundle frontend non trovato. Compilo il frontend..."
    set "_M_FE_BUILT=Frontend compilato e copiato."
    set "_M_FE_MISSING=Bundle frontend non trovato: backend\static\assets\index.js"
    set "_M_FE_COPY=         Copia i file dalla release oppure compila:"
    set "_M_PORT_BUSY=La porta 8000 e' gia' in uso."
    set "_M_PORT_HINT1=         Un'altra istanza di EMLyzer potrebbe essere attiva,"
    set "_M_PORT_HINT2=         oppure un altro programma usa la porta 8000."
    set "_M_PORT_HINT3=         Fermalo prima di avviare EMLyzer."
    set "_M_PORT_FIND=         Per trovare il processo: netstat -ano ^| findstr :8000"
    set "_M_PY_SEARCHING=Ricerca versione Python compatibile..."
    set "_M_PY_OLD=e' troppo vecchio. Richiesto 3.11+."
    set "_M_PY_URL=         Installa Python 3.13 da https://www.python.org/downloads/"
    set "_M_PY_PATH=         Durante l'installazione spunta 'Add Python to PATH'"
    set "_M_PY_NOT_FOUND=Python non trovato nel sistema."
    set "_M_PY_NOT_FOUND2=         Installa Python 3.13 da https://www.python.org/downloads/"
    set "_M_PY_PATH2=         Durante l'installazione spunta 'Add Python to PATH'"
    set "_M_PY_USING=Uso:"
    set "_M_PY_WARN14=Python - alcune librerie potrebbero non essere supportate."
    set "_M_PY_REC=         Si consiglia Python 3.13: https://www.python.org/downloads/"
    set "_M_VENV_RECREATING=Ricreazione virtual environment..."
    set "_M_VENV_CREATING_PRE=Creazione virtual environment con"
    set "_M_VENV_CREATED=Virtual environment creato."
    set "_M_VENV_FAILED=Impossibile creare il virtual environment."
    set "_M_VENV_HINT=         Prova manualmente:"
    set "_M_DEPS_INSTALLING=Installazione dipendenze..."
    set "_M_DEPS_OK=Dipendenze OK."
    set "_M_DEPS_FAILED=Installazione dipendenze fallita."
    set "_M_DEPS_RETRY=         Riesegui senza -q per vedere i dettagli:"
    set "_M_ENV_CREATED=File .env creato da .env.example"
    set "_M_ENV_LANG=Per cambiare lingua: modifica LANGUAGE nel file .env ^(it/en^)"
    set "_M_PY_IN_VENV=Python nel venv:"
    set "_M_READY=  Applicazione pronta"
    set "_M_BROWSER=  Apri il browser su:  http://localhost:8000"
    set "_M_API_DOCS=  Documentazione API:  http://localhost:8000/docs"
    set "_M_LANG_HINT=  Lingua:              pulsante IT/EN in alto a destra"
    set "_M_CTRLC=  Premi CTRL+C per fermare"
    set "_M_SERVER_STOPPED=Server fermato."
)

:: ── Leggi versione da config.py usando Python (piu' affidabile di for/f) ──────
:: Viene fatto dopo aver trovato Python, quindi piu' avanti nello script.
:: Per ora usiamo il valore hardcoded sopra come fallback.

title EMLyzer v%VERSION%

echo.
echo  ============================================
echo   EMLyzer v%VERSION%
echo  ============================================
echo.

:: ── Controlla che il backend esista ──────────────────────────────────────────
if not exist "%BACKEND_DIR%\main.py" (
    echo !_E! !_M_BACKEND_MISSING!
    echo !_M_BACKEND_HINT!
    echo.
    pause
    exit /b 1
)

:: ── Controlla che il bundle frontend esista (o lo builda automaticamente) ────
if not exist "%BACKEND_DIR%\static\assets\index.js" (
    where node >nul 2>&1
    if not errorlevel 1 (
        if exist "%~dp0frontend\package.json" (
            echo !_I! !_M_FE_BUILDING!
            cd /d "%~dp0frontend"
            call npm install -q
            call npm run build
            xcopy /e /y /q "%~dp0frontend\dist\*" "%BACKEND_DIR%\static\" >nul
            cd /d "%~dp0"
            echo !_I! !_M_FE_BUILT!
            echo.
        ) else (
            goto :bundle_error
        )
    ) else (
        :bundle_error
        echo !_E! !_M_FE_MISSING!
        echo !_M_FE_COPY!
        echo            cd frontend ^&^& npm install ^&^& npm run build
        echo            xcopy /e /y frontend\dist\* backend\static\
        echo.
        pause
        exit /b 1
    )
)

:: ── Controlla che la porta 8000 sia libera ────────────────────────────────────
netstat -an 2>nul | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo !_W! !_M_PORT_BUSY!
    echo !_M_PORT_HINT1!
    echo !_M_PORT_HINT2!
    echo !_M_PORT_HINT3!
    echo.
    echo !_M_PORT_FIND!
    echo.
    pause
    exit /b 1
)

:: ── Cerca Python compatibile ─────────────────────────────────────────────────
echo !_I! !_M_PY_SEARCHING!

:: Priorita' 1: Python Launcher (py.exe) - disponibile con installer ufficiale
where py >nul 2>&1
if not errorlevel 1 (
    for %%V in (3.13 3.12 3.11 3.14) do (
        if not defined FOUND_PYTHON (
            py -%%V --version >nul 2>&1
            if not errorlevel 1 (
                set "FOUND_PYTHON=py -%%V"
                set "FOUND_VER=%%V"
                if "!SCRIPT_LANG!"=="en" (
                    echo !_I! Found Python %%V via launcher ^(py -%%V^)
                ) else (
                    echo !_I! Trovato Python %%V tramite launcher ^(py -%%V^)
                )
            )
        )
    )
)
if defined FOUND_PYTHON goto :python_found

:: Priorita' 2: python.exe generico nel PATH
:: Usa Python stesso per estrarre la versione — piu' affidabile di stringhe batch
python --version >nul 2>&1
if errorlevel 1 goto :python_not_found

python -c "import sys; v=sys.version_info; exit(0 if v.major==3 and v.minor>=11 else 1)" >nul 2>&1
if errorlevel 1 (
    :: Versione troppo vecchia — mostra quale versione e' installata
    for /f "tokens=2" %%V in ('python --version 2^>^&1') do (
        echo !_E! Python %%V !_M_PY_OLD!
    )
    echo !_M_PY_URL!
    echo !_M_PY_PATH!
    echo.
    pause
    exit /b 1
)

:: Versione accettabile — leggi major.minor per il titolo
for /f "tokens=*" %%V in ('python -c "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))"') do (
    set "FOUND_VER=%%V"
)
set "FOUND_PYTHON=python"

:: Avviso per 3.14+
python -c "import sys; exit(0 if sys.version_info.minor >= 14 else 1)" >nul 2>&1
if not errorlevel 1 (
    echo !_W! !_M_PY_WARN14!
    echo !_M_PY_REC!
    echo.
)

for /f "tokens=2" %%V in ('python --version 2^>^&1') do (
    if "!SCRIPT_LANG!"=="en" (
        echo !_I! Found Python %%V in PATH
    ) else (
        echo !_I! Trovato Python %%V nel PATH
    )
)
goto :python_found

:python_not_found
echo !_E! !_M_PY_NOT_FOUND!
echo !_M_PY_NOT_FOUND2!
echo !_M_PY_PATH2!
echo.
pause
exit /b 1

:python_found
echo !_I! !_M_PY_USING! %FOUND_PYTHON%
echo.

:: ── Aggiorna titolo con versione reale da config.py ──────────────────────────
:: Ora che abbiamo Python, usiamolo per leggere la versione
for /f "tokens=*" %%V in ('%FOUND_PYTHON% -c "import re,sys; m=re.search(chr(39)+'([0-9.]+)'+chr(39), open(sys.argv[1]).read() if __import__(chr(111)+chr(115)).path.exists(sys.argv[1]) else chr(39)+chr(39)); print(m.group(1) if m else chr(48))" "%BACKEND_DIR%\utils\config.py" 2^>nul') do (
    if not "%%V"=="0" set "VERSION=%%V"
)
title EMLyzer v%VERSION%

:: ── Gestione virtual environment ─────────────────────────────────────────────
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" --version >nul 2>&1
    if errorlevel 1 (
        echo !_W! !_M_VENV_RECREATING!
        rmdir /s /q "%VENV_DIR%"
        goto :create_venv
    )
    :: Confronta versione venv con versione trovata
    "%VENV_PYTHON%" -c "import sys; v=sys.version_info; print(str(v.major)+'.'+str(v.minor))" > "%TEMP%\emlyzer_venv_ver.txt" 2>nul
    set /p VENV_VER= < "%TEMP%\emlyzer_venv_ver.txt"
    del "%TEMP%\emlyzer_venv_ver.txt" >nul 2>&1
    if not "!VENV_VER!"=="!FOUND_VER!" (
        if "!SCRIPT_LANG!"=="en" (
            echo !_I! Venv uses Python !VENV_VER!, current version is !FOUND_VER!.
        ) else (
            echo !_I! Venv usa Python !VENV_VER!, versione corrente e' !FOUND_VER!.
        )
        echo !_I! !_M_VENV_RECREATING!
        rmdir /s /q "%VENV_DIR%"
        goto :create_venv
    )
    goto :install_deps
)

:create_venv
echo !_I! !_M_VENV_CREATING_PRE! %FOUND_PYTHON%...
%FOUND_PYTHON% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo !_E! !_M_VENV_FAILED!
    echo !_M_VENV_HINT! %FOUND_PYTHON% -m venv "%VENV_DIR%"
    echo.
    pause
    exit /b 1
)
echo !_I! !_M_VENV_CREATED!
echo.

:install_deps
:: ── Aggiorna pip silenziosamente ─────────────────────────────────────────────
"%VENV_PYTHON%" -m pip install --upgrade pip -q >nul 2>&1

:: ── Installa/aggiorna dipendenze ─────────────────────────────────────────────
echo !_I! !_M_DEPS_INSTALLING!
"%VENV_PYTHON%" -m pip install -r "%BACKEND_DIR%\requirements.txt" -q
if errorlevel 1 (
    echo.
    echo !_E! !_M_DEPS_FAILED!
    echo !_M_DEPS_RETRY!
    echo          "%VENV_PYTHON%" -m pip install -r "%BACKEND_DIR%\requirements.txt"
    echo.
    pause
    exit /b 1
)
echo !_I! !_M_DEPS_OK!
echo.

:: ── Crea .env se non esiste ───────────────────────────────────────────────────
if not exist "%BACKEND_DIR%\.env" (
    if exist "%BACKEND_DIR%\.env.example" (
        copy "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul
        echo !_I! !_M_ENV_CREATED!
        echo !_I! !_M_ENV_LANG!
        echo.
    )
)

:: ── Mostra info finali ────────────────────────────────────────────────────────
echo !_I! !_M_PY_IN_VENV!
"%VENV_PYTHON%" --version
echo.
echo  ============================================
echo !_M_READY!
echo  ============================================
echo.
echo !_M_BROWSER!
echo !_M_API_DOCS!
echo !_M_LANG_HINT!
echo.
echo !_M_CTRLC!
echo  ============================================
echo.

:: ── Avvio server ─────────────────────────────────────────────────────────────
:: Nota: --reload rimosso perche' causa crash con multiprocessing su Windows
cd /d "%BACKEND_DIR%"
"%VENV_PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000

echo.
echo !_I! !_M_SERVER_STOPPED!
pause
