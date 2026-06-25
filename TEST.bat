@echo off
title Jyotish AI - Test
cd /d "%~dp0"
echo.
echo Installing Flask...
pip install flask flask-sqlalchemy flask-login werkzeug anthropic python-dotenv
echo.
echo Starting site... (errors will show here)
echo.
python app.py
echo.
echo === SITE STOPPED - READ ERROR ABOVE ===
pause
