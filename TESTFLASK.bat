@echo off
title Flask Test
cd /d "%~dp0"
echo.
echo Testing Flask only (simple test)...
echo.
pip install flask -q
echo.
echo If Flask works you will see a green tick message.
echo Then go to Chrome and type:  127.0.0.1:8080
echo.
python test_flask.py
pause
