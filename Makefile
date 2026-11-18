.DEFAULT_GOAL := run
.PHONY: run dev stop logs

# One command: build the image and start career-buddy in the background.
URL := http://localhost:8080

run:
	docker compose up --build -d
	@echo "career-buddy is running at $(URL) (make stop to shut it down)"
	@sh -c 'for i in $$(seq 120); do curl -fs $(URL) >/dev/null 2>&1 && break; sleep 1; done; \
	  (command -v open >/dev/null && open $(URL)) || (command -v xdg-open >/dev/null && xdg-open $(URL)) || cmd.exe /c start $(URL) || true'

# Foreground dev: API with auto-reload and UI with hot reload. Ctrl+C stops it.
dev:
	@echo "dev UI with hot reload at http://localhost:5173"
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

stop:
	docker compose down

logs:
	docker compose logs -f career-buddy
