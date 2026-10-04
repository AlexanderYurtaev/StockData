.PHONY: dev backend frontend stop test build setup

# Запуск обоих серверов на переднем плане; Ctrl+C останавливает оба
dev:
	cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 &
	cd frontend && npm run dev &
	wait

backend:
	cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

# Остановка серверов, запущенных в фоне (по портам 8000 и 5173)
stop:
	@lsof -ti :8000 | xargs kill 2>/dev/null || true
	@lsof -ti :5173 | xargs kill 2>/dev/null || true
	@echo "Серверы остановлены (порты 8000 и 5173 свободны)."

# Установка зависимостей с нуля (бэкенд — uv, фронтенд — npm)
setup:
	cd backend && uv sync
	cd frontend && npm install

test:
	cd backend && uv run pytest

build:
	cd frontend && npm run build
