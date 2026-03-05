@echo off
REM BIDSHub CLI wrapper for Windows
REM Forwards all commands to bin\explorer.bat

cd /d "%~dp0"
call bin\explorer.bat %*
