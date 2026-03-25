@echo off
REM ================================================================
REM  Fitness Bridge AI — Environment Setup Script
REM  Creates a Python 3.13 virtual environment and installs deps.
REM ================================================================

echo.
echo ===================================================
echo    Fitness Bridge AI — Environment Setup
echo ===================================================
echo.

REM --- Check that py launcher is available ---
where py >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python Launcher (py) not found.
    echo         Install Python 3.13 from https://python.org/downloads
    echo         and ensure "py launcher" is checked during install.
    pause
    exit /b 1
)

REM --- Check Python 3.13 is available ---
py -3.13 --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.13 is not installed.
    echo         Download it from https://python.org/downloads/release/python-3130/
    pause
    exit /b 1
)

echo [OK] Python 3.13 found.

REM --- Navigate to project root (one level up from scripts/) ---
cd /d "%~dp0.."

REM --- Remove old venv if it exists ---
if exist ".venv" (
    echo [INFO] Removing existing .venv...
    rmdir /s /q ".venv"
)

REM --- Create new venv with Python 3.13 ---
echo [INFO] Creating virtual environment with Python 3.13...
py -3.13 -m venv .venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [OK] Virtual environment created at .venv\

REM --- Activate venv ---
call .venv\Scripts\activate.bat

REM --- Upgrade pip ---
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip --quiet

REM --- Install dependencies ---
echo [INFO] Installing dependencies from requirements.txt...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Package installation failed. Check your requirements.txt and internet connection.
    pause
    exit /b 1
)

echo.
echo [OK] All packages installed successfully.

REM --- Create .env from example if not present ---
if not exist ".env" (
    echo [INFO] No .env file found. Copying from .env.example...
    copy ".env.example" ".env" >nul
    echo [ACTION REQUIRED] Fill in your API credentials in .env before running the app.
) else (
    echo [OK] .env file already exists.
)

echo.
echo ===================================================
echo    Setup Complete!
echo.
echo    Next steps:
echo      1. Edit .env with your Strava and Fitbit tokens
echo      2. Ensure Ollama is running: ollama serve
echo      3. Pull the model: ollama pull qwen2.5:4b
echo      4. Activate the env: .venv\Scripts\activate
echo      5. Run the app: streamlit run app.py
echo      6. Run tests: pytest
echo ===================================================
echo.
pause
