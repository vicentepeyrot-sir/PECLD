@echo off
chcp 65001 >nul
echo.
echo  Iniciando PECLD Painel...
echo.
start "" http://localhost:5000
python "%~dp0server.py"
pause
