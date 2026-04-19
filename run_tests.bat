@echo off
:: EMLyzer - Esegui test suite (Windows)
:: Riusa il venv creato da start.bat
setlocal enabledelayedexpansion

title EMLyzer - Test Suite

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
    set "_M_VENV_MISSING=Virtual environment not found."
    set "_M_VENV_SEARCHING=Looking for compatible Python to create the venv..."
    set "_M_VENV_CREATING_PRE=Creating virtual environment with"
    set "_M_VENV_FAILED=Cannot create virtual environment."
    set "_M_VENV_HINT=         Try running start.bat first."
    set "_M_PY_NOT_FOUND=Python 3.11+ not found."
    set "_M_PY_HINT=         Run start.bat first or install Python 3.13"
    set "_M_PY_URL=         from https://www.python.org/downloads/"
    set "_M_PY_TOO_OLD=too old. Required 3.11+."
    set "_M_PY_URL2=         Install Python 3.13 from https://www.python.org/downloads/"
    set "_M_PY_PATH=         During installation check 'Add Python to PATH'"
    set "_M_DEPS_INSTALLING=Installing dependencies..."
    set "_M_DEPS_FAILED=Dependencies installation failed."
    set "_M_DEPS_RETRY=         Re-run without -q to see details:"
    set "_M_PYTEST_MISSING=pytest not found in the virtual environment."
    set "_M_PYTEST_HINT_PRE=         Run:"
    set "_M_PY_IN_VENV=Python in venv:"
    set "_M_RUNNING=Running tests..."
    set "_M_ALL_PASSED= [OK] All tests passed."
    set "_M_SOME_FAILED= [FAIL] Some tests failed. Check the output above."
    set "_M_NO_TESTS= [WARNING] No tests found."
) else (
    set "_E=[ERRORE]"
    set "_W=[AVVISO]"
    set "_I=[INFO]"
    set "_M_VENV_MISSING=Virtual environment non trovato."
    set "_M_VENV_SEARCHING=Cerco Python compatibile per creare il venv..."
    set "_M_VENV_CREATING_PRE=Creazione virtual environment con"
    set "_M_VENV_FAILED=Impossibile creare il virtual environment."
    set "_M_VENV_HINT=         Prova a eseguire start.bat prima."
    set "_M_PY_NOT_FOUND=Python 3.11+ non trovato."
    set "_M_PY_HINT=         Esegui prima start.bat oppure installa Python 3.13"
    set "_M_PY_URL=         da https://www.python.org/downloads/"
    set "_M_PY_TOO_OLD=troppo vecchio. Richiesto 3.11+."
    set "_M_PY_URL2=         Installa Python 3.13 da https://www.python.org/downloads/"
    set "_M_PY_PATH=         Durante l'installazione spunta 'Add Python to PATH'"
    set "_M_DEPS_INSTALLING=Installazione dipendenze..."
    set "_M_DEPS_FAILED=Installazione dipendenze fallita."
    set "_M_DEPS_RETRY=         Riesegui senza -q per vedere i dettagli:"
    set "_M_PYTEST_MISSING=pytest non trovato nel virtual environment."
    set "_M_PYTEST_HINT_PRE=         Esegui:"
    set "_M_PY_IN_VENV=Python nel venv:"
    set "_M_RUNNING=Esecuzione test..."
    set "_M_ALL_PASSED= [OK] Tutti i test superati."
    set "_M_SOME_FAILED= [FAIL] Alcuni test sono falliti. Controlla l'output sopra."
    set "_M_NO_TESTS= [AVVISO] Nessun test trovato."
)

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
echo !_I! !_M_VENV_MISSING!
echo !_I! !_M_VENV_SEARCHING!
echo.

:: Priorita' 1: Python Launcher
where py >nul 2>&1
if not errorlevel 1 (
    for %%V in (3.13 3.12 3.11 3.14) do (
        if not defined FOUND_PYTHON (
            py -%%V --version >nul 2>&1
            if not errorlevel 1 (
                set "FOUND_PYTHON=py -%%V"
                if "!SCRIPT_LANG!"=="en" (
                    echo !_I! Found Python %%V via launcher
                ) else (
                    echo !_I! Trovato Python %%V tramite launcher
                )
            )
        )
    )
)

:: Priorita' 2: python.exe generico con controllo versione
if not defined FOUND_PYTHON (
    python --version >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; v=sys.version_info; exit(0 if v.major==3 and v.minor>=11 else 1)" >nul 2>&1
        if errorlevel 1 (
            for /f "tokens=2" %%V in ('python --version 2^>^&1') do (
                echo !_E! Python %%V !_M_PY_TOO_OLD!
            )
            echo !_M_PY_URL2!
            echo !_M_PY_PATH!
            pause
            exit /b 1
        )
        set "FOUND_PYTHON=python"
        for /f "tokens=2" %%V in ('python --version 2^>^&1') do (
            if "!SCRIPT_LANG!"=="en" (
                echo !_I! Found Python %%V in PATH
            ) else (
                echo !_I! Trovato Python %%V nel PATH
            )
        )
    )
)

if not defined FOUND_PYTHON (
    echo !_E! !_M_PY_NOT_FOUND!
    echo !_M_PY_HINT!
    echo !_M_PY_URL!
    echo.
    pause
    exit /b 1
)

:: Crea venv
echo !_I! !_M_VENV_CREATING_PRE! %FOUND_PYTHON%...
%FOUND_PYTHON% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo !_E! !_M_VENV_FAILED!
    echo !_M_VENV_HINT!
    echo.
    pause
    exit /b 1
)

:: Installa dipendenze
echo !_I! !_M_DEPS_INSTALLING!
"%VENV_PYTHON%" -m pip install -r "%BACKEND_DIR%\requirements.txt" -q
if errorlevel 1 (
    echo !_E! !_M_DEPS_FAILED!
    echo !_M_DEPS_RETRY!
    echo          "%VENV_PYTHON%" -m pip install -r "%BACKEND_DIR%\requirements.txt"
    echo.
    pause
    exit /b 1
)
echo.

:check_pytest
:: ── Verifica che pytest sia disponibile ──────────────────────────────────────
"%VENV_PYTHON%" -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo !_E! !_M_PYTEST_MISSING!
    echo !_M_PYTEST_HINT_PRE! "%VENV_PYTHON%" -m pip install pytest pytest-asyncio httpx
    echo.
    pause
    exit /b 1
)

echo !_I! !_M_PY_IN_VENV!
"%VENV_PYTHON%" --version
echo.
echo !_I! !_M_RUNNING!
echo.

cd /d "%BACKEND_DIR%"
"%VENV_PYTHON%" -m pytest tests\test_core.py -v --tb=short --asyncio-mode=auto %*
set "TEST_EXIT=%errorlevel%"

echo.
if "%TEST_EXIT%"=="0" (
    echo !_M_ALL_PASSED!
) else if "%TEST_EXIT%"=="1" (
    echo !_M_SOME_FAILED!
) else if "%TEST_EXIT%"=="2" (
    if "!SCRIPT_LANG!"=="en" (
        echo  [FAIL] Execution interrupted ^(CTRL+C or configuration error^).
    ) else (
        echo  [FAIL] Esecuzione interrotta ^(CTRL+C o errore di configurazione^).
    )
) else if "%TEST_EXIT%"=="5" (
    echo !_M_NO_TESTS!
) else (
    if "!SCRIPT_LANG!"=="en" (
        echo  [FAIL] pytest error ^(exit code: %TEST_EXIT%^).
    ) else (
        echo  [FAIL] Errore pytest ^(exit code: %TEST_EXIT%^).
    )
)
echo.
pause
exit /b %TEST_EXIT%
