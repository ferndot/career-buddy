#!/bin/sh
# Double-click to stop career-buddy. Your data in the data folder is kept.
cd "$(dirname "$0")" || exit 1
docker compose down
read -r -p "Press Enter to close. " _
