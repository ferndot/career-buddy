#!/bin/sh
# Double-click to start career-buddy. Needs Docker Desktop running.
cd "$(dirname "$0")" || exit 1
if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop, wait until it says Docker is running, then double-click this file again."
  read -r -p "Press Enter to close. " _
  exit 1
fi
if ! docker compose up --build -d; then
  echo "Could not start career-buddy. See the messages above."
  read -r -p "Press Enter to close. " _
  exit 1
fi
echo "career-buddy is running at http://localhost:8080"
open http://localhost:8080
echo "To stop it, double-click stop.command."
read -r -p "Press Enter to close. " _
