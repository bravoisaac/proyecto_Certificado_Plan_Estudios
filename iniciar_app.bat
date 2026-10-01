@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Preparando la aplicacion por primera vez...

  set "PYTHON_EXE="
  set "PYTHON_ARGS="

  py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
  )

  if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('where python 2^>nul ^| findstr /i /v "\\Microsoft\\WindowsApps\\"') do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
  )

  if defined PYTHON_EXE (
    "!PYTHON_EXE!" !PYTHON_ARGS! -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul || set "PYTHON_EXE="
  )

  if not defined PYTHON_EXE goto :desktop

  "!PYTHON_EXE!" !PYTHON_ARGS! -m venv .venv || goto :error
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)

start "" "http://127.0.0.1:8000"
echo Aplicacion iniciada. No cierre esta ventana mientras la este usando.
echo.
".venv\Scripts\python.exe" server.py
goto :eof

:desktop
if exist "dist\EquivalenciasPlanEstudios.exe" (
  echo Python no esta instalado. Abriendo la aplicacion de escritorio portable...
  start "" "%CD%\dist\EquivalenciasPlanEstudios.exe"
  exit /b 0
)

:error
echo.
echo No se pudo preparar la aplicacion.
echo Instale Python 3.10 o superior desde https://www.python.org/downloads/windows/
echo o use dist\EquivalenciasPlanEstudios.exe, que no requiere Python.
pause
exit /b 1

