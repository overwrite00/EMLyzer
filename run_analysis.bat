@echo off
REM EMLyzer Email Analysis Test Runner
REM Uses the project's virtual environment

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0"
set "VENV_PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo ERROR: Virtual environment not found at %VENV_PYTHON%
    echo Please run start.bat first to set up the environment
    exit /b 1
)

echo.
echo ========================================
echo EMLyzer Email Analysis Test
echo ========================================
echo.
echo Using Python: %VENV_PYTHON%
"%VENV_PYTHON%" --version
echo.

cd /d "%PROJECT_DIR%"
"%VENV_PYTHON%" analyze_email_samples.py
exit /b %ERRORLEVEL%
