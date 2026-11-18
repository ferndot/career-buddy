@echo off
rem Double-click to start career-buddy. Needs Docker Desktop running.
cd /d "%~dp0"
docker info >nul 2>&1
if errorlevel 1 (
  echo Docker is not running. Start Docker Desktop, wait until it says Docker is running, then double-click this file again.
  pause
  exit /b 1
)
docker compose up --build -d
if errorlevel 1 (
  echo Could not start career-buddy. See the messages above.
  pause
  exit /b 1
)
echo career-buddy is running at http://localhost:8080
start "" http://localhost:8080
echo To stop it, double-click stop.bat.
pause
