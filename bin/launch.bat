@echo off
REM BIDSHub Launch Script for Windows
REM Port search: DEFAULT (8501) through DEFAULT+50 (8551)

REM Change to project root directory (parent of bin\)
cd /d "%~dp0\.."

setlocal enabledelayedexpansion

set DEFAULT_PORT=8501
set MAX_PORT=8551

echo ============================================================
echo            BIDSHub Launch Script
echo ============================================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found
    echo Please run: python -m venv venv
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat
echo [OK] Virtual environment activated
echo.

REM Check if streamlit is installed
where streamlit >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Streamlit not installed
    echo Please run: pip install -r requirements.txt
    exit /b 1
)

REM Find available port (DEFAULT..MAX)
echo Searching for available port in range %DEFAULT_PORT%-%MAX_PORT%...

set PORT=
for /l %%p in (%DEFAULT_PORT%,1,%MAX_PORT%) do (
    netstat -an | find "LISTENING" | find ":%%p " >nul
    if errorlevel 1 (
        set PORT=%%p
        goto :found_port
    )
)

echo [ERROR] No available ports in range %DEFAULT_PORT%-%MAX_PORT%
echo Please close some applications and try again
exit /b 1

:found_port
echo [OK] Found available port: %PORT%
echo.

REM Launch Streamlit
echo ------------------------------------------------------------
echo Launching BIDSHub on port %PORT%...
echo ------------------------------------------------------------
echo.
echo   Local URL:   http://localhost:%PORT%
echo.
echo Press Ctrl+C to stop the server
echo.
echo ============================================================
echo.

streamlit run app.py --server.port %PORT% --server.headless false
