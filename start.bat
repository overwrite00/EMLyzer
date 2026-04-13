@echo off
:: EMLyzer - Avvio (Windows)
:: Compatibile con Windows 10/11, Python 3.11+
setlocal enabledelayedexpansion

set "BACKEND_DIR=%~dp0backend"
set "VENV_DIR=%~dp0.venv"
set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
set "FOUND_PYTHON="
set "FOUND_VER="
set "VERSION=0.10.1"

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
    echo [ERRORE] File backend\main.py non trovato.
    echo          Esegui start.bat dalla cartella EMLyzer\
    echo.
    pause
    exit /b 1
)

:: ── Controlla che il bundle frontend esista (o lo builda automaticamente) ────
if not exist "%BACKEND_DIR%\static\assets\index.js" (
    where node >nul 2>&1
    if not errorlevel 1 (
        if exist "%~dp0frontend\package.json" (
            echo [INFO] Bundle frontend non trovato. Compilo il frontend...
            cd /d "%~dp0frontend"
            call npm install -q
            call npm run build
            xcopy /e /y /q "%~dp0frontend\dist\*" "%BACKEND_DIR%\static\" >nul
            cd /d "%~dp0"
            echo [INFO] Frontend compilato e copiato.
            echo.
        ) else (
            goto :bundle_error
        )
    ) else (
        :bundle_error
        echo [ERRORE] Bundle frontend non trovato: backend\static\assets\index.js
        echo          Copia i file dalla release oppure compila:
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
    echo [AVVISO] La porta 8000 e' gia' in uso.
    echo          Un'altra istanza di EMLyzer potrebbe essere attiva,
    echo          oppure un altro programma usa la porta 8000.
    echo          Fermalo prima di avviare EMLyzer.
    echo.
    echo          Per trovare il processo: netstat -ano ^| findstr :8000
    echo.
    pause
    exit /b 1
)

:: ── Cerca Python compatibile ─────────────────────────────────────────────────
echo [INFO] Ricerca versione Python compatibile...

:: Priorita' 1: Python Launcher (py.exe) - disponibile con installer ufficiale
where py >nul 2>&1
if not errorlevel 1 (
    for %%V in (3.13 3.12 3.11 3.14) do (
        if not defined FOUND_PYTHON (
            py -%%V --version >nul 2>&1
            if not errorlevel 1 (
                set "FOUND_PYTHON=py -%%V"
                set "FOUND_VER=%%V"
                echo [INFO] Trovato Python %%V tramite launcher ^(py -%%V^)
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
        echo [ERRORE] Python %%V e' troppo vecchio. Richiesto 3.11+.
    )
    echo          Installa Python 3.13 da https://www.python.org/downloads/
    echo          Durante l'installazione spunta "Add Python to PATH"
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
    echo [AVVISO] Python !FOUND_VER! - alcune librerie potrebbero non essere supportate.
    echo          Si consiglia Python 3.13: https://www.python.org/downloads/
    echo.
)

for /f "tokens=2" %%V in ('python --version 2^>^&1') do (
    echo [INFO] Trovato Python %%V nel PATH
)
goto :python_found

:python_not_found
echo [ERRORE] Python non trovato nel sistema.
echo          Installa Python 3.13 da https://www.python.org/downloads/
echo          Durante l'installazione spunta "Add Python to PATH"
echo.
pause
exit /b 1

:python_found
echo [INFO] Uso: %FOUND_PYTHON%
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
        echo [AVVISO] Virtual environment corrotto. Ricreazione...
        rmdir /s /q "%VENV_DIR%"
        goto :create_venv
    )
    :: Confronta versione venv con versione trovata
    "%VENV_PYTHON%" -c "import sys; v=sys.version_info; print(str(v.major)+'.'+str(v.minor))" > "%TEMP%\emlyzer_venv_ver.txt" 2>nul
    set /p VENV_VER= < "%TEMP%\emlyzer_venv_ver.txt"
    del "%TEMP%\emlyzer_venv_ver.txt" >nul 2>&1
    if not "!VENV_VER!"=="!FOUND_VER!" (
        echo [INFO] Venv usa Python !VENV_VER!, versione corrente e' !FOUND_VER!.
        echo [INFO] Ricreazione virtual environment...
        rmdir /s /q "%VENV_DIR%"
        goto :create_venv
    )
    goto :install_deps
)

:create_venv
echo [INFO] Creazione virtual environment con %FOUND_PYTHON%...
%FOUND_PYTHON% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [ERRORE] Impossibile creare il virtual environment.
    echo          Prova manualmente: %FOUND_PYTHON% -m venv "%VENV_DIR%"
    echo.
    pause
    exit /b 1
)
echo [INFO] Virtual environment creato.
echo.

:install_deps
:: ── Aggiorna pip silenziosamente ─────────────────────────────────────────────
"%VENV_PYTHON%" -m pip install --upgrade pip -q >nul 2>&1

:: ── Installa/aggiorna dipendenze ─────────────────────────────────────────────
echo [INFO] Installazione dipendenze...
"%VENV_PYTHON%" -m pip install -r "%BACKEND_DIR%\requirements.txt" -q
if errorlevel 1 (
    echo.
    echo [ERRORE] Installazione dipendenze fallita.
    echo          Riesegui senza -q per vedere i dettagli:
    echo          "%VENV_PYTHON%" -m pip install -r "%BACKEND_DIR%\requirements.txt"
    echo.
    pause
    exit /b 1
)
echo [INFO] Dipendenze OK.
echo.

:: ── Crea .env se non esiste ───────────────────────────────────────────────────
if not exist "%BACKEND_DIR%\.env" (
    if exist "%BACKEND_DIR%\.env.example" (
        copy "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul
        echo [INFO] File .env creato da .env.example
        echo [INFO] Per cambiare lingua: modifica LANGUAGE nel file .env ^(it/en^)
        echo.
    )
)

:: ── Mostra info finali ────────────────────────────────────────────────────────
echo [INFO] Python nel venv:
"%VENV_PYTHON%" --version
echo.
echo  ============================================
echo   Applicazione pronta
echo  ============================================
echo.
echo   Apri il browser su:  http://localhost:8000
echo   Documentazione API:  http://localhost:8000/docs
echo   Lingua:              pulsante IT/EN in alto a destra
echo.
echo   Premi CTRL+C per fermare
echo  ============================================
echo.

:: ── Avvio server ─────────────────────────────────────────────────────────────
:: Nota: --reload rimosso perche' causa crash con multiprocessing su Windows
cd /d "%BACKEND_DIR%"
"%VENV_PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000

echo.
echo [INFO] Server fermato.
pause