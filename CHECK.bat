@echo off
title Jyotish AI - Checking Setup
color 0E
echo.
echo  Checking your setup...
echo  ========================
echo.

python --version
if errorlevel 1 (
    echo.
    echo  ERROR: Python is NOT installed!
    echo.
    echo  Please do this:
    echo  1. Go to: https://www.python.org/downloads/
    echo  2. Click the big Download button
    echo  3. Run the installer
    echo  4. IMPORTANT: Check the box "Add Python to PATH"
    echo  5. Click Install Now
    echo  6. Come back and run START_SITE.bat again
    echo.
) else (
    echo  Python OK!
    echo.
    pip --version
    echo  pip OK!
    echo.
    echo  Now running the site...
    echo.
    cd /d "%~dp0"
    pip install flask flask-sqlalchemy flask-login werkzeug anthropic python-dotenv --quiet
    echo.
    echo  ======================================
    echo   Site starting at http://localhost:5000
    echo  ======================================
    echo.
    start http://localhost:5000
    python app.py
)

echo.
pause
