@echo off
title Jyotish AI - Starting...
color 0A
echo.
echo  ==========================================
echo   JYOTISH AI - Starting Your Website
echo  ==========================================
echo.

cd /d "%~dp0"

echo  [1/2] Installing required packages...
pip install flask flask-sqlalchemy flask-login werkzeug anthropic python-dotenv pypdf --quiet

echo.
echo  [2/2] Starting website...
echo.
echo  ==========================================
echo   Website is LIVE at:
echo   http://localhost:5000
echo  ==========================================
echo.
echo  Opening browser automatically...
timeout /t 2 /nobreak >nul
start http://localhost:5000

echo  (Keep this window open. Close it to stop the site.)
echo.
python app.py

pause
