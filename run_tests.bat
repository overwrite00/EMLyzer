@echo off
:: EMLyzer - Esegui test suite (Windows)
:: Riusa il venv creato da start.bat
setlocal enabledelayedexpansion

title EMLyzer - Test Suite

echo.
echo  ============================================
echo   EMLyzer - Test Suite
echo  ============================================
echo.

set "BACKEND_DIR=%~dp0backend"
set "VENV_DIR=%~dp0.venv"
set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
set "FOUND_PYTHON="

:: ── Se il venv esiste, usalo direttamente ─────────────────────────────────────
if exist "%VENV_PYTHON%" goto :check_pytest

:: ── Venv non trovato: cerca Python e crealo ───────────────────────────────────
echo [INFO] Virtual environment non trovato.
echo [INFO] Cerco Python compatibile per creare il venv...
echo.

:: Priorita' 1: Python Launcher
where py >nul 2>&1
if not errorlevel 1 (
    for %%V in (3.13 3.12 3.11 3.14) do (
        if not defined FOUND_PYTHON (
            py -%%V --version >nul 2>&1
            if not errorlevel 1 (
                set "FOUND_PYTHON=py -%%V"
                echo [INFO] Trovato Python %%V tramite launcher
            )
        )
    )
)

:: Priorita' 2: python.exe generico con controllo versione
:: Usa Python stesso per il check — evita problemi con for/f e stringhe
if not defined FOUND_PYTHON (
    python --version >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; v=sys.version_info; exit(0 if v.major==3 and v.minor>=11 else 1)" >nul 2>&1
        if errorlevel 1 (
            for /f "tokens=2" %%V in ('python --version 2^>^&1') do (
                echo [ERRORE] Python %%V troppo vecchio. Richiesto 3.11+.
            )
            pause
            exit /b 1
        )
        set "FOUND_PYTHON=python"
        for /f "tokens=2" %%V in ('python --version 2^>^&1') do (
            echo [INFO] Trovato Python %%V nel PATH
        )
    )
)

if not defined FOUND_PYTHON (
    echo [ERRORE] Python 3.11+ non trovato.
    echo          Esegui prima start.bat oppure installa Python 3.13
    echo          da https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: Crea venv
echo [INFO] Creazione virtual environment con %FOUND_PYTHON%...
%FOUND_PYTHON% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [ERRORE] Impossibile creare il virtual environment.
    echo          Prova a eseguire start.bat prima.
    echo.
    pause
    exit /b 1
)

:: Installa dipendenze
echo [INFO] Installazione dipendenze...
"%VENV_PYTHON%" -m pip install -r "%BACKEND_DIR%\requirements.txt" -q
if errorlevel 1 (
    echo [ERRORE] Installazione dipendenze fallita.
    echo          Esegui: "%VENV_PYTHON%" -m pip install -r "%BACKEND_DIR%\requirements.txt"
    echo.
    pause
    exit /b 1
)
echo.

:check_pytest
:: ── Verifica che pytest sia disponibile ──────────────────────────────────────
"%VENV_PYTHON%" -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] pytest non trovato nel virtual environment.
    echo          Esegui: "%VENV_PYTHON%" -m pip install pytest pytest-asyncio httpx
    echo.
    pause
    exit /b 1
)

echo [INFO] Python nel venv:
"%VENV_PYTHON%" --version
echo.
echo [INFO] Esecuzione test...
echo.

cd /d "%BACKEND_DIR%"
"%VENV_PYTHON%" -m pytest tests\test_core.py -v --tb=short --asyncio-mode=auto %*
set "TEST_EXIT=%errorlevel%"

echo.
if "%TEST_EXIT%"=="0" (
    echo  [OK] Tutti i test superati.
) else if "%TEST_EXIT%"=="1" (
    echo  [FAIL] Alcuni test sono falliti. Controlla l'output sopra.
) else if "%TEST_EXIT%"=="2" (
    echo  [FAIL] Esecuzione interrotta ^(CTRL+C o errore di configurazione^).
) else if "%TEST_EXIT%"=="5" (
    echo  [AVVISO] Nessun test trovato.
) else (
    echo  [FAIL] Errore pytest ^(exit code: %TEST_EXIT%^).
)
echo.
pause
exit /b %TEST_EXIT%