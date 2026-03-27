@echo off
:: EMLyzer v0.3.0 - Avvio (Windows)
:: Seleziona automaticamente la versione corretta di Python
:: se nel sistema sono installate piu' versioni.

title EMLyzer v0.3.0

echo.
echo  ============================================
echo   EMLyzer v0.3.0
echo  ============================================
echo.

set "BACKEND_DIR=%~dp0backend"
set "VENV_DIR=%~dp0.venv"
set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
set "FOUND_PYTHON="

:: ── Cerca la versione migliore di Python disponibile ─────────────────────────
:: Ordine di preferenza: 3.13 > 3.12 > 3.11
:: Python Launcher (py.exe) e' disponibile se Python e' installato con l'installer ufficiale

echo [INFO] Ricerca versione Python compatibile...

:: Prova con il Python Launcher (py.exe) - disponibile su Windows con installer ufficiale
where py >nul 2>&1
if not errorlevel 1 (
    :: Prova 3.13
    py -3.13 --version >nul 2>&1
    if not errorlevel 1 (
        set "FOUND_PYTHON=py -3.13"
        echo [INFO] Trovato Python 3.13 tramite launcher ^(py -3.13^)
        goto :python_found
    )
    :: Prova 3.12
    py -3.12 --version >nul 2>&1
    if not errorlevel 1 (
        set "FOUND_PYTHON=py -3.12"
        echo [INFO] Trovato Python 3.12 tramite launcher ^(py -3.12^)
        goto :python_found
    )
    :: Prova 3.11
    py -3.11 --version >nul 2>&1
    if not errorlevel 1 (
        set "FOUND_PYTHON=py -3.11"
        echo [INFO] Trovato Python 3.11 tramite launcher ^(py -3.11^)
        goto :python_found
    )
    :: Prova 3.14 come ultima spiaggia
    py -3.14 --version >nul 2>&1
    if not errorlevel 1 (
        set "FOUND_PYTHON=py -3.14"
        echo [AVVISO] Trovato solo Python 3.14 - alcune librerie potrebbero non funzionare.
        echo          Si consiglia di installare Python 3.13: https://www.python.org/downloads/
        echo.
        goto :python_found
    )
)

:: Fallback: prova python3.13, python3.12, python3.11 nel PATH
for %%V in (3.13 3.12 3.11) do (
    python%%V --version >nul 2>&1
    if not errorlevel 1 (
        if not defined FOUND_PYTHON (
            set "FOUND_PYTHON=python%%V"
            echo [INFO] Trovato Python %%V nel PATH ^(python%%V^)
        )
    )
)
if defined FOUND_PYTHON goto :python_found

:: Fallback finale: python generico nel PATH
python --version >nul 2>&1
if not errorlevel 1 (
    :: Controlla che non sia una versione troppo vecchia
    for /f "tokens=2" %%V in ('python --version 2^>^&1') do set "GENERIC_VER=%%V"
    :: Accetta 3.11, 3.12, 3.13, 3.14 — blocca < 3.11
    if "%GENERIC_VER:~0,4%"=="3.11" ( set "FOUND_PYTHON=python" & echo [INFO] Trovato Python %GENERIC_VER% nel PATH & goto :python_found )
    if "%GENERIC_VER:~0,4%"=="3.12" ( set "FOUND_PYTHON=python" & echo [INFO] Trovato Python %GENERIC_VER% nel PATH & goto :python_found )
    if "%GENERIC_VER:~0,4%"=="3.13" ( set "FOUND_PYTHON=python" & echo [INFO] Trovato Python %GENERIC_VER% nel PATH & goto :python_found )
    if "%GENERIC_VER:~0,4%"=="3.14" (
        set "FOUND_PYTHON=python"
        echo [AVVISO] Python %GENERIC_VER% - alcune librerie potrebbero non funzionare.
        echo          Si consiglia Python 3.13: https://www.python.org/downloads/
        goto :python_found
    )
    echo [ERRORE] Python %GENERIC_VER% e' troppo vecchio. Richiesto 3.11 o superiore.
    echo          Installalo da https://python.org
    pause
    exit /b 1
)

:: Nessuna versione trovata
echo [ERRORE] Python non trovato nel sistema.
echo          Installalo da https://python.org (versione consigliata: 3.13)
echo          Durante l'installazione spunta "Add Python to PATH"
echo.
pause
exit /b 1

:python_found
echo [INFO] Usero': %FOUND_PYTHON%
echo.

:: Controlla che il backend esista
if not exist "%BACKEND_DIR%\main.py" (
    echo [ERRORE] File backend\main.py non trovato.
    echo          Esegui start.bat dalla cartella EMLyzer\
    echo.
    pause
    exit /b 1
)

:: ── Crea virtual environment con la versione corretta ────────────────────────
if not exist "%VENV_PYTHON%" (
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
) else (
    :: Verifica che il venv esistente usi una versione accettabile
    "%VENV_PYTHON%" --version >nul 2>&1
    if errorlevel 1 (
        echo [AVVISO] Virtual environment esistente non valido. Ricreazione...
        rmdir /s /q "%VENV_DIR%"
        %FOUND_PYTHON% -m venv "%VENV_DIR%"
        echo [INFO] Virtual environment ricreato.
        echo.
    )
)

:: ── Installa/aggiorna dipendenze ─────────────────────────────────────────────
echo [INFO] Installazione dipendenze...
"%VENV_PYTHON%" -m pip install -r "%BACKEND_DIR%\requirements.txt" -q
if errorlevel 1 (
    echo.
    echo [ERRORE] Installazione dipendenze fallita.
    echo          Prova manualmente per vedere l'errore:
    echo          "%VENV_PYTHON%" -m pip install -r "%BACKEND_DIR%\requirements.txt"
    echo.
    pause
    exit /b 1
)
echo [INFO] Dipendenze OK.
echo.

:: ── Crea .env se non esiste ──────────────────────────────────────────────────
if not exist "%BACKEND_DIR%\.env" (
    if exist "%BACKEND_DIR%\.env.example" (
        copy "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul
        echo [INFO] File .env creato da .env.example
        echo [INFO] Per cambiare lingua: modifica LANGUAGE nel file .env ^(it/en^)
        echo.
    )
)

:: ── Mostra versione Python effettivamente usata nel venv ─────────────────────
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

cd /d "%BACKEND_DIR%"
"%VENV_PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000

echo.
echo [INFO] Server fermato.
pause
