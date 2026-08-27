@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel% equ 0 (
  set "PYTHON_CMD=py"
) else (
  set "PYTHON_CMD=python"
)

if not exist ".venv\Scripts\python.exe" (
  echo Preparando la aplicacion por primera vez...
  %PYTHON_CMD% -m venv .venv || goto :error
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)

start "" "http://127.0.0.1:8000"
echo Aplicacion iniciada. No cierre esta ventana mientras la este usando.
echo.
".venv\Scripts\python.exe" server.py
goto :eof

:error
echo.
echo No se pudo preparar la aplicacion. Revise que Python este instalado.
pause
exit /b 1

