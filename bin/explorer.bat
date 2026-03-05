@echo off
REM BIDSHub CLI for Windows
REM Usage: hub.bat <command> [options]

REM Change to project root directory (parent of bin\)
cd /d "%~dp0\.."

setlocal enabledelayedexpansion

set APP_NAME=BIDSHub
set VENV_DIR=venv
set PID_FILE=.explorer.pid

if "%1"=="" goto help

set COMMAND=%1

if /i "%COMMAND%"=="install" goto install
if /i "%COMMAND%"=="start" goto start
if /i "%COMMAND%"=="stop" goto stop
if /i "%COMMAND%"=="restart" goto restart
if /i "%COMMAND%"=="status" goto status
if /i "%COMMAND%"=="logs" goto logs
if /i "%COMMAND%"=="update" goto update
if /i "%COMMAND%"=="test" goto test
if /i "%COMMAND%"=="clean" goto clean
if /i "%COMMAND%"=="config" goto config
if /i "%COMMAND%"=="help" goto help

echo [ERROR] Unknown command: %COMMAND%
echo.
goto help

:install
echo ============================================================
echo   Installing %APP_NAME%
echo ============================================================
echo.

REM Check Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found
    exit /b 1
)
echo [OK] Python found

REM Create virtual environment
if not exist "%VENV_DIR%" (
    echo [INFO] Creating virtual environment...
    python -m venv %VENV_DIR%
    echo [OK] Virtual environment created
) else (
    echo [WARN] Virtual environment already exists
)

REM Activate and install
call %VENV_DIR%\Scripts\activate.bat

echo [INFO] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [INFO] Installing dependencies...
pip install -r requirements.txt --quiet
echo [OK] Dependencies installed

echo [INFO] Initializing database...
python scripts\init_db.py
echo [OK] Database initialized

echo.
echo [OK] Installation complete!
echo [INFO] Run 'explorer.bat start' to launch
goto end

:start
echo ============================================================
echo   Starting %APP_NAME%
echo ============================================================
echo.

if not exist "%VENV_DIR%" (
    echo [ERROR] Virtual environment not found
    echo [INFO] Run 'explorer.bat install' first
    exit /b 1
)

echo [INFO] Launching application...
start /B python launch.py
echo [OK] Started
echo [INFO] Check status: explorer.bat status
goto end

:stop
echo ============================================================
echo   Stopping %APP_NAME%
echo ============================================================
echo.

taskkill /F /IM python.exe /FI "WINDOWTITLE eq streamlit*" >nul 2>nul
if errorlevel 1 (
    echo [WARN] No running processes found
) else (
    echo [OK] Stopped
)
goto end

:restart
echo ============================================================
echo   Restarting %APP_NAME%
echo ============================================================
echo.

call :stop
timeout /t 2 /nobreak >nul
call :start
goto end

:status
echo ============================================================
echo   %APP_NAME% Status
echo ============================================================
echo.

tasklist /FI "IMAGENAME eq python.exe" | find "python.exe" >nul
if errorlevel 1 (
    echo [ERROR] Not running
) else (
    echo [OK] Running
    
    REM Try to find port
    for /f "tokens=5" %%a in ('netstat -ano ^| find "LISTENING" ^| find ":850"') do (
        for /f "tokens=2 delims=:" %%b in ("%%a") do (
            echo   Port: %%b
            echo   URL:  http://localhost:%%b
            goto status_found
        )
    )
    :status_found
)

echo.

if exist "%VENV_DIR%" (
    echo [OK] Virtual environment: installed
) else (
    echo [ERROR] Virtual environment: not found
)

if exist "data\tracktbi.db" (
    echo [OK] Database: initialized
) else (
    echo [WARN] Database: not initialized
)
goto end

:logs
echo ============================================================
echo   %APP_NAME% Logs
echo ============================================================
echo.

set LOG_DIR=%USERPROFILE%\.streamlit\logs
if exist "%LOG_DIR%" (
    for /f %%i in ('dir /b /o-d "%LOG_DIR%\*.log" 2^>nul') do (
        echo [INFO] Showing: %%i
        type "%LOG_DIR%\%%i"
        goto end
    )
)
echo [WARN] No logs found
echo [INFO] Start the application first: explorer.bat start
goto end

:update
echo ============================================================
echo   Updating %APP_NAME%
echo ============================================================
echo.

if not exist ".git" (
    echo [ERROR] Not a git repository
    exit /b 1
)

echo [INFO] Pulling latest code...
git pull origin main
echo [OK] Code updated

if exist "%VENV_DIR%" (
    call %VENV_DIR%\Scripts\activate.bat
    echo [INFO] Updating dependencies...
    pip install --upgrade -r requirements.txt --quiet
    echo [OK] Dependencies updated
)

echo.
echo [OK] Update complete!
echo [INFO] Run 'explorer.bat restart' to apply changes
goto end

:test
echo ============================================================
echo   Running Tests
echo ============================================================
echo.

if not exist "%VENV_DIR%" (
    echo [ERROR] Virtual environment not found
    exit /b 1
)

call %VENV_DIR%\Scripts\activate.bat

echo [INFO] Testing database...
python scripts\init_db.py >nul 2>&1
echo [OK] Database: OK

echo [INFO] Testing imports...
python -c "import streamlit; import bids; import pennsieve; import pandas; import plotly" 2>nul
echo [OK] Dependencies: OK

echo [INFO] Testing modules...
python -c "from src import database, bids_loader, pennsieve_client, theme, utils" 2>nul
echo [OK] Modules: OK

echo.
echo [OK] All tests passed!
goto end

:clean
echo ============================================================
echo   Cleaning %APP_NAME%
echo ============================================================
echo.

echo [WARN] This will remove:
echo   - Virtual environment
echo   - Database
echo   - Cache files
echo.

set /p CONFIRM="Are you sure? (y/N): "
if /i not "%CONFIRM%"=="y" (
    echo [INFO] Cancelled
    goto end
)

REM Stop if running
call :stop >nul 2>&1

if exist "%VENV_DIR%" (
    echo [INFO] Removing virtual environment...
    rmdir /s /q %VENV_DIR%
    echo [OK] Virtual environment removed
)

if exist "data\tracktbi.db" (
    echo [INFO] Removing database...
    del /f data\tracktbi.db
    echo [OK] Database removed
)

echo [INFO] Removing cache files...
for /d /r %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
del /s /q *.pyc >nul 2>&1

echo.
echo [OK] Cleanup complete!
echo [INFO] Run 'explorer.bat install' to reinstall
goto end

:config
echo ============================================================
echo   %APP_NAME% Configuration
echo ============================================================
echo.

if exist ".env" (
    echo [OK] Configuration file: .env
    echo.
    type .env | findstr /v "^#" | findstr /v "^$"
) else (
    echo [WARN] No .env file found
    echo [INFO] Create from template: copy .env.example .env
)
goto end

:help
echo ============================================================
echo   %APP_NAME% CLI
echo ============================================================
echo.
echo Usage: hub.bat ^<command^> [options]
echo.
echo Commands:
echo   install   Install dependencies and initialize database
echo   start     Start the application
echo   stop      Stop the application
echo   restart   Restart the application
echo   status    Check application status
echo   logs      View application logs
echo   update    Pull latest code and update dependencies
echo   test      Run tests
echo   clean     Remove virtual environment and cache
echo   config    Show configuration
echo   help      Show this help message
echo.
echo Examples:
echo   hub.bat install      # First time setup
echo   hub.bat start        # Launch the app
echo   hub.bat status       # Check if running
echo   hub.bat logs         # View logs
echo   hub.bat restart      # Restart the app
echo.
goto end

:end
endlocal
