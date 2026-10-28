@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
echo GHOST em http://127.0.0.1:5000
python app.py
pause
