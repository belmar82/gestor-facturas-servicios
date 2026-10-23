@echo off
rem Gestor de Facturas - Secretaria de Educacion de Soledad
cd /d "%~dp0"
where py >nul 2>&1 && (py app.py) || (python app.py)
if errorlevel 1 pause
