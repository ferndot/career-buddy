@echo off
rem Double-click to stop career-buddy. Your data in the data folder is kept.
cd /d "%~dp0"
docker compose down
pause
