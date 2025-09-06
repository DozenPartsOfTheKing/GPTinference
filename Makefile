# GPTInfernse - Простое управление
.PHONY: help start stop restart status logs logs-f build clean test

# Цвета
BLUE=\033[0;34m
GREEN=\033[0;32m
YELLOW=\033[1;33m
NC=\033[0m

help: ## Показать справку
	@echo "$(BLUE)🚀 GPTInfernse - Команды управления$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

start: ## Запустить все сервисы
	@echo "$(BLUE)🚀 Запуск GPTInfernse...$(NC)"
	@./docker-start.sh

stop: ## Остановить все сервисы
	@echo "$(BLUE)🛑 Остановка GPTInfernse...$(NC)"
	@./docker-stop.sh

restart: ## Перезапустить все сервисы
	@echo "$(BLUE)🔄 Перезапуск GPTInfernse...$(NC)"
	@./docker-stop.sh && ./docker-start.sh

status: ## Показать статус сервисов
	@echo "$(BLUE)📊 Статус сервисов:$(NC)"
	@if command -v docker-compose >/dev/null 2>&1; then \
		docker-compose ps; \
	elif docker compose version >/dev/null 2>&1; then \
		docker compose ps; \
	else \
		docker ps --filter "name=gptinfernse"; \
	fi

logs: ## Показать логи
	@if command -v docker-compose >/dev/null 2>&1; then \
		docker-compose logs --tail=50; \
	elif docker compose version >/dev/null 2>&1; then \
		docker compose logs --tail=50; \
	else \
		docker logs --tail=50 gptinfernse-api; \
	fi

logs-f: ## Следить за логами в реальном времени
	@./show-logs

build: ## Пересобрать образы
	@echo "$(BLUE)🔨 Сборка образов...$(NC)"
	@if command -v docker-compose >/dev/null 2>&1; then \
		docker-compose build --no-cache; \
	elif docker compose version >/dev/null 2>&1; then \
		docker compose build --no-cache; \
	else \
		echo "Docker Compose не найден!"; \
	fi

clean: ## Полная очистка (удалить все)
	@echo "$(YELLOW)🧹 Полная очистка...$(NC)"
	@./docker-stop.sh --clean

# Быстрые тесты
health: ## Проверить здоровье API
	@curl -s http://localhost:8000/health/detailed | jq . || echo "API недоступен"

models: ## Показать доступные модели
	@curl -s http://localhost:8000/models/ | jq . || echo "API недоступен"

chat-test: ## Тестовый запрос к чату
	@curl -X POST http://localhost:8000/chat/sync \
		-H "Content-Type: application/json" \
		-d '{"prompt": "Привет! Как дела?", "model": "llama3"}' | jq . || echo "Чат недоступен"

# Мониторинг
flower: ## Открыть Flower (мониторинг Celery)
	@echo "$(GREEN)🌸 Flower: http://localhost:5555 (admin/admin123)$(NC)"
	@open http://localhost:5555 2>/dev/null || xdg-open http://localhost:5555 2>/dev/null || echo "Откройте http://localhost:5555"

docs: ## Открыть API документацию
	@echo "$(GREEN)📚 API Docs: http://localhost:8000/docs$(NC)"
	@open http://localhost:8000/docs 2>/dev/null || xdg-open http://localhost:8000/docs 2>/dev/null || echo "Откройте http://localhost:8000/docs"

web: ## Открыть веб-интерфейс
	@echo "$(GREEN)🌐 GPTInfernse: http://localhost:3000$(NC)"
	@open http://localhost:3000 2>/dev/null || xdg-open http://localhost:3000 2>/dev/null || echo "Откройте http://localhost:3000"

# Разработка
dev: ## Запуск для разработки (без Docker)
	@echo "$(BLUE)🛠️ Режим разработки...$(NC)"
	@echo "Запустите в разных терминалах:"
	@echo "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
	@echo "  celery -A app.utils.celery_app worker --loglevel=info"
	@echo "  cd frontend && python3 server.py"

test: ## Запустить тесты
	@echo "$(BLUE)🧪 Запуск тестов...$(NC)"
	@pytest tests/ -v

format: ## Форматировать код
	@echo "$(BLUE)🎨 Форматирование кода...$(NC)"
	@black app/ tests/
	@isort app/ tests/

# Алиасы
up: start ## Алиас для start
down: stop ## Алиас для stop
ps: status ## Алиас для status

# По умолчанию показываем справку
.DEFAULT_GOAL := help