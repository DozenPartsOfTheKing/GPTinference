# GPTInfernse Makefile
# Удобные команды для управления проектом

.PHONY: help install start stop restart status logs build clean test format lint dev

# Цвета для вывода
BLUE=\033[0;34m
GREEN=\033[0;32m
YELLOW=\033[1;33m
NC=\033[0m # No Color

help: ## Показать справку
	@echo "$(BLUE)GPTInfernse - Команды управления$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

install: ## Полная установка проекта
	@echo "$(BLUE)Установка GPTInfernse...$(NC)"
	@./scripts/deploy.sh install

start: ## Запустить все сервисы
	@echo "$(BLUE)Запуск сервисов...$(NC)"
	@./scripts/deploy.sh start

stop: ## Остановить все сервисы
	@echo "$(BLUE)Остановка сервисов...$(NC)"
	@./scripts/deploy.sh stop

restart: ## Перезапустить все сервисы
	@echo "$(BLUE)Перезапуск сервисов...$(NC)"
	@./scripts/deploy.sh restart

status: ## Показать статус сервисов
	@echo "$(BLUE)Статус сервисов:$(NC)"
	@./scripts/deploy.sh status

logs: ## Показать логи
	@./scripts/deploy.sh logs

logs-f: ## Следить за логами
	@./scripts/deploy.sh logs-f

build: ## Собрать Docker образы
	@echo "$(BLUE)Сборка образов...$(NC)"
	@./scripts/deploy.sh build

clean: ## Очистить контейнеры и образы
	@echo "$(YELLOW)Очистка...$(NC)"
	@./scripts/deploy.sh cleanup

backup: ## Создать резервную копию
	@echo "$(BLUE)Создание резервной копии...$(NC)"
	@./scripts/deploy.sh backup

update: ## Обновить сервис
	@echo "$(BLUE)Обновление сервиса...$(NC)"
	@./scripts/deploy.sh update

models: ## Установить рекомендуемые модели Ollama
	@echo "$(BLUE)Установка моделей Ollama...$(NC)"
	@./scripts/deploy.sh models

# Команды разработки
dev-setup: ## Настроить среду разработки
	@echo "$(BLUE)Настройка среды разработки...$(NC)"
	@./scripts/dev.sh setup

dev: ## Запустить сервер разработки
	@echo "$(BLUE)Запуск сервера разработки...$(NC)"
	@./scripts/dev.sh dev

worker: ## Запустить Celery worker
	@echo "$(BLUE)Запуск Celery worker...$(NC)"
	@./scripts/dev.sh worker

test: ## Запустить тесты
	@echo "$(BLUE)Запуск тестов...$(NC)"
	@./scripts/dev.sh test

format: ## Форматировать код
	@echo "$(BLUE)Форматирование кода...$(NC)"
	@./scripts/dev.sh format

lint: ## Проверить код линтерами
	@echo "$(BLUE)Проверка кода...$(NC)"
	@./scripts/dev.sh lint

dev-clean: ## Очистить среду разработки
	@echo "$(YELLOW)Очистка среды разработки...$(NC)"
	@./scripts/dev.sh clean

# Команды для тестирования API
health: ## Проверить здоровье API
	@curl -s http://localhost:8000/health/detailed | jq .

api-models: ## Получить список моделей
	@curl -s http://localhost:8000/models/ | jq .

chat-test: ## Тестовый запрос к чату
	@curl -X POST http://localhost:8000/chat/sync \
		-H "Content-Type: application/json" \
		-d '{"prompt": "Привет! Как дела?", "model": "llama3"}' | jq .

# Команды мониторинга
flower: ## Открыть Flower (мониторинг Celery)
	@echo "$(GREEN)Открываем Flower: http://localhost:5555$(NC)"
	@open http://localhost:5555 2>/dev/null || xdg-open http://localhost:5555 2>/dev/null || echo "Откройте http://localhost:5555 в браузере"

grafana: ## Открыть Grafana
	@echo "$(GREEN)Открываем Grafana: http://localhost:3000$(NC)"
	@open http://localhost:3000 2>/dev/null || xdg-open http://localhost:3000 2>/dev/null || echo "Откройте http://localhost:3000 в браузере"

prometheus: ## Открыть Prometheus
	@echo "$(GREEN)Открываем Prometheus: http://localhost:9090$(NC)"
	@open http://localhost:9090 2>/dev/null || xdg-open http://localhost:9090 2>/dev/null || echo "Откройте http://localhost:9090 в браузере"

docs: ## Открыть API документацию
	@echo "$(GREEN)Открываем API Docs: http://localhost:8000/docs$(NC)"
	@open http://localhost:8000/docs 2>/dev/null || xdg-open http://localhost:8000/docs 2>/dev/null || echo "Откройте http://localhost:8000/docs в браузере"

# Команды для production
prod-deploy: ## Развернуть в production
	@echo "$(BLUE)Развертывание в production...$(NC)"
	@DEBUG=false docker-compose up -d

prod-backup: ## Создать production backup
	@echo "$(BLUE)Создание production backup...$(NC)"
	@./scripts/deploy.sh backup

prod-restore: ## Восстановить из backup (требует указания пути)
	@echo "$(YELLOW)Восстановление из backup...$(NC)"
	@echo "Использование: make prod-restore BACKUP_PATH=/path/to/backup"

# Быстрые команды
up: start ## Алиас для start
down: stop ## Алиас для stop
ps: status ## Алиас для status

# Команда по умолчанию
.DEFAULT_GOAL := help
