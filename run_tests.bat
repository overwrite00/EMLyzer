@echo off
:: EMLyzer - Esegui test suite (Windows)
:: Riusa il venv creato da start.bat

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

:: Se il venv esiste gia', usalo direttamente
if exist "%VENV_PYTHON%" goto :run_tests

:: Altrimenti cerca Python compatibile (stessa logica di start.bat)
echo [INFO] Virtual environment non trovato. Cerco Python compatibile...
echo.

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

if not defined FOUND_PYTHON (
    for %%V in (3.13 3.12 3.11) do (
        if not defined FOUND_PYTHON (
            python%%V --version >nul 2>&1
            if not errorlevel 1 (
                set "FOUND_PYTHON=python%%V"
                echo [INFO] Trovato python%%V nel PATH
            )
        )
    )
)

if not defined FOUND_PYTHON (
    python --version >nul 2>&1
    if not errorlevel 1 (
        set "FOUND_PYTHON=python"
        echo [INFO] Trovato python nel PATH
    )
)

if not defined FOUND_PYTHON (
    echo [ERRORE] Python non trovato. Esegui prima start.bat
    pause
    exit /b 1
)

echo [INFO] Creazione virtual environment con %FOUND_PYTHON%...
%FOUND_PYTHON% -m venv "%VENV_DIR%"
echo [INFO] Installazione dipendenze...
"%VENV_PYTHON%" -m pip install -r "%BACKEND_DIR%\requirements.txt" -q

:run_tests
echo [INFO] Python nel venv:
"%VENV_PYTHON%" --version
echo.
echo [INFO] Esecuzione test...
echo.

cd /d "%BACKEND_DIR%"
"%VENV_PYTHON%" -m pytest tests/ -v --tb=short %*

echo.
pause
