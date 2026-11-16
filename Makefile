.DEFAULT_GOAL := run
.PHONY: run dev stop logs

# One command: build the image and start career-buddy in the background.
run:
	docker compose up --build -d
	@echo "career-buddy is running at http://localhost:8080 (make stop to shut it down)"

# Foreground dev: API with auto-reload and UI with hot reload. Ctrl+C stops it.
dev:
	@echo "dev UI with hot reload at http://localhost:5173"
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

stop:
	docker compose down

logs:
	docker compose logs -f career-buddy
