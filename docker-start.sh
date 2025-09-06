#!/bin/bash

# 🐳 Docker-based запуск GPTInfernse
# Полностью контейнеризованное решение

set -e  # Остановка при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для красивого вывода
log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

echo -e "${BLUE}🐳 ЗАПУСК GPTInfernse через Docker${NC}"
echo "=================================="

# 1. Проверяем Docker
log_info "Проверяем Docker..."
if ! command -v docker &> /dev/null; then
    log_error "Docker не установлен!"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    log_error "Docker Compose не установлен!"
    exit 1
fi

log_success "Docker найден: $(docker --version)"

# 2. Останавливаем старые контейнеры
log_info "Останавливаем старые контейнеры..."
docker-compose down --remove-orphans 2>/dev/null || docker compose down --remove-orphans 2>/dev/null || true

# 3. Очищаем старые образы (опционально)
if [[ "$1" == "--clean" ]]; then
    log_warning "Очищаем старые образы..."
    docker system prune -f
    docker-compose build --no-cache || docker compose build --no-cache
fi

# 4. Создаем необходимые директории
log_info "Создаем директории..."
mkdir -p logs
chmod 755 logs

# 5. Собираем и запускаем контейнеры
log_info "Собираем и запускаем контейнеры..."

# Используем docker-compose или docker compose в зависимости от версии
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

log_info "Используем команду: $COMPOSE_CMD"

# Сборка образов
log_info "Собираем образы..."
$COMPOSE_CMD build

# Запуск в фоне
log_info "Запускаем сервисы..."
$COMPOSE_CMD up -d

# 6. Ждем запуска сервисов
log_info "Ждем запуска сервисов..."

# Функция проверки сервиса
check_service() {
    local service_name=$1
    local url=$2
    local max_attempts=30
    local attempt=1

    log_info "Проверяем $service_name..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            log_success "$service_name готов"
            return 0
        fi
        
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    log_error "$service_name не запустился за $((max_attempts * 2)) секунд"
    return 1
}

# Проверяем сервисы по очереди
sleep 5

echo ""
check_service "Redis" "http://localhost:6379" || true
check_service "Ollama" "http://localhost:11434/api/tags" || true
check_service "API" "http://localhost:8000/health" || true
check_service "Frontend" "http://localhost:3000" || true

# 7. Устанавливаем модели Ollama
log_info "Проверяем модели Ollama..."
sleep 10

models_count=$(curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(len(data.get('models', [])))
except:
    print('0')
" 2>/dev/null || echo "0")

if [ "$models_count" -lt 2 ]; then
    log_warning "Устанавливаем базовые модели..."
    docker exec gptinfernse-ollama ollama pull llama3.2 &
    docker exec gptinfernse-ollama ollama pull mistral &
    log_info "Модели устанавливаются в фоне..."
else
    log_success "Найдено моделей: $models_count"
fi

# 8. Показываем статус
echo ""
log_info "Проверяем статус всех сервисов..."
$COMPOSE_CMD ps

# 9. Финальная проверка
echo ""
log_info "Финальная проверка..."

services_ok=0
total_services=4

# Проверяем каждый сервис
if curl -s http://localhost:6379 > /dev/null 2>&1 || docker exec gptinfernse-redis redis-cli ping > /dev/null 2>&1; then
    log_success "✅ Redis работает"
    ((services_ok++))
else
    log_error "❌ Redis не отвечает"
fi

if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    log_success "✅ Ollama работает"
    ((services_ok++))
else
    log_error "❌ Ollama не отвечает"
fi

if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    log_success "✅ API работает"
    ((services_ok++))
else
    log_error "❌ API не отвечает"
fi

if curl -s http://localhost:3000 > /dev/null 2>&1; then
    log_success "✅ Frontend работает"
    ((services_ok++))
else
    log_error "❌ Frontend не отвечает"
fi

# 10. Итоговый отчет
echo ""
echo -e "${BLUE}🎯 ИТОГОВЫЙ СТАТУС${NC}"
echo "=================="
echo "Запущено сервисов: $services_ok/$total_services"

if [ $services_ok -eq $total_services ]; then
    echo ""
    log_success "🎉 ВСЕ СЕРВИСЫ ЗАПУЩЕНЫ УСПЕШНО!"
    echo ""
    echo -e "${GREEN}🔗 Полезные ссылки:${NC}"
    echo "  🌐 Интерфейс:     http://localhost:3000"
    echo "  📚 API Docs:      http://localhost:8000/docs"
    echo "  🏥 Health Check:  http://localhost:8000/health/detailed"
    echo "  🌸 Flower:        http://localhost:5555"
    echo ""
    echo -e "${BLUE}📊 Управление:${NC}"
    echo "  Логи:           $COMPOSE_CMD logs -f"
    echo "  Статус:         $COMPOSE_CMD ps"
    echo "  Остановка:      $COMPOSE_CMD down"
    echo "  Перезапуск:     $COMPOSE_CMD restart"
else
    echo ""
    log_warning "⚠️  НЕКОТОРЫЕ СЕРВИСЫ НЕ ЗАПУСТИЛИСЬ"
    echo ""
    echo -e "${YELLOW}🔍 Для диагностики:${NC}"
    echo "  $COMPOSE_CMD logs"
    echo "  $COMPOSE_CMD ps"
    echo "  docker ps -a"
fi

echo ""
log_success "🚀 Система готова к работе!"
