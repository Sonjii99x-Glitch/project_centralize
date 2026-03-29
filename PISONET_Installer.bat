@echo off
REM PISONET Centralized Installer for Windows
REM This script sets up the PISONET server on a Windows machine

echo ========================================
echo    PISONET Centralized Installer
echo ========================================
echo.

set INSTALL_DIR=%~dp0
cd /d "%INSTALL_DIR%"

echo Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install Python dependencies
    pause
    exit /b 1
)

echo.
echo Creating data directory...
if not exist data mkdir data

echo.
echo Initializing database...
python -c "from server import init_db; init_db(); print('Database initialized')"
if %errorlevel% neq 0 (
    echo ERROR: Failed to initialize database
    pause
    exit /b 1
)

echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo To start the PISONET server:
echo   python server.py
echo.
echo Then open http://localhost:5000 in your browser
echo.
echo Default admin password: 1234
echo.
pause