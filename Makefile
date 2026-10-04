.PHONY: dev backend frontend stop test build setup

# Запуск обоих серверов на переднем плане; Ctrl+C останавливает оба.
# Именно вложенный make -j2, а не «… & … & wait»: фоновые команды sh
# получают SIGINT=ignore, и Ctrl+C убивал бы только make, оставляя
# uvicorn и vite работать сиротами. Здесь оба сервера остаются в группе
# процессов терминала и сигнал получают напрямую.
dev:
	$(MAKE) --no-print-directory -j2 backend frontend

backend:
	cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev -- --strictPort

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
