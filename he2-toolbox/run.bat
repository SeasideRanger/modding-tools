@echo off
cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Python is not installed. Please install Python 3.12 from the Microsoft Store.
    pause
    exit /b 1
)

REM Extract and validate the Python version (major.minor only)
for /f "tokens=2 delims= " %%i in ('python --version 2^>nul') do set python_version=%%i
for /f "tokens=1-2 delims=." %%a in ("%python_version%") do set python_major_minor=%%a.%%b
if not "%python_major_minor%"=="3.12" (
    echo Python version is %python_version%. Please ensure Python 3.12.x is installed from the Microsoft Store.
    pause
    exit /b 1
)

REM Check if pip is available
python -m pip --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo pip is not available. Please install it manually.
    pause
    exit /b 1
)

REM Check if PyQt6 is installed
python -c "import PyQt6" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo PyQt6 is not installed. Please install it manually.
    pause
    exit /b 1
)

REM Check if pythonw is available
where pythonw >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo pythonw is not available. Please ensure it is installed.
    pause
    exit /b 1
)

REM If checks pass, run the Python script
start "" pythonw launch.py

exit