@echo off
set PROJECT_DIR=D:\wati-doc-collector

start "Flask - WATI Doc Collector" cmd /k "cd /d %PROJECT_DIR% && venv\Scripts\activate && python app.py"

timeout /t 5 /nobreak >nul

start "Ngrok Tunnel - WATI" cmd /k "cd /d %PROJECT_DIR% && venv\Scripts\activate && python run_tunnel.py"
