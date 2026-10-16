@echo off
rem Gera dist\Financat.exe (um único arquivo, sem console).
setlocal
cd /d "%~dp0"

python -m pip install -r requirements-dev.txt || goto :erro
python -m pytest -q tests || goto :erro
python tools\gerar_icone.py || goto :erro
python -m PyInstaller --noconsole --onefile --clean --noconfirm --name Financat --icon assets\mascote.ico main.py || goto :erro

echo.
echo Pronto: %~dp0dist\Financat.exe
exit /b 0

:erro
echo.
echo Falhou. Veja as mensagens acima.
exit /b 1
