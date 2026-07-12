@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_CMD="
set "VENV_PY=.venv\Scripts\python.exe"

where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_CMD=python"
  )
)

if "%PYTHON_CMD%"=="" (
  echo.
  echo [CoachOS]
  echo Python was not found, so the app cannot start.
  echo.
  echo Please install Python 3.11 or newer:
  echo https://www.python.org/downloads/windows/
  echo.
  echo During installation, please check this option:
  echo Add python.exe to PATH
  echo.
  echo After installing Python, close this window and double-click this BAT file again.
  echo.
  pause
  exit /b 1
)

if not exist "%VENV_PY%" (
  echo Creating Python virtual environment...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 (
    echo.
    echo Failed to create the virtual environment.
    echo Please make sure Python 3.11 or newer is installed and added to PATH.
    echo.
    pause
    exit /b 1
  )
)

if not exist "%VENV_PY%" (
  echo.
  echo The virtual environment Python was not found:
  echo %VENV_PY%
  echo.
  echo Please delete the .venv folder and run this BAT file again.
  echo.
  pause
  exit /b 1
)

echo Installing or updating required packages...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Package installation failed. Please check your internet connection and try again.
  echo.
  pause
  exit /b 1
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":8765 .*LISTENING"') do (
  taskkill /PID %%a /F >nul 2>nul
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":8766 .*LISTENING"') do (
  taskkill /PID %%a /F >nul 2>nul
)

echo Starting CoachOS...
echo The platform will open first. Use the homepage button when you want to enter RAC.
"%VENV_PY%" analysis_platform\dashboard_app.py analysis_platform\running_analytics.sqlite --port 8766

endlocal
