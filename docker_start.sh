#!/bin/bash

# 🐳 GPTInfernse Docker Full Stack
# Запуск фронт + бек + Ollama в Docker с полным логированием

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${BLUE}[DOCKER]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warning() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }
header() { echo -e "${PURPLE}=== $1 ===${NC}"; }

# Проверка Docker
check_docker() {
    header "Проверка Docker"
    
    if ! command -v docker &> /dev/null; then
        error "Docker не установлен!"
        log "Установите Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        error "Docker Compose не установлен!"
        log "Установите Docker Compose"
        exit 1
    fi
    
    if ! docker info > /dev/null 2>&1; then
        error "Docker не запущен!"
        log "Запустите Docker Desktop или Docker daemon"
        exit 1
    fi
    
    success "Docker готов к работе"
}

# Подготовка окружения
prepare_environment() {
    header "Подготовка окружения"
    
    # Создание директорий
    mkdir -p logs data/redis data/ollama
    
    # Создание .env для Docker
    if [ ! -f ".env.docker" ]; then
        log "Создание .env.docker файла..."
        cat > .env.docker << 'EOF'
# Docker Environment
COMPOSE_PROJECT_NAME=gptinfernse
DOCKER_BUILDKIT=1

# Application
APP_NAME=GPTInfernse
DEBUG=true
LOG_LEVEL=DEBUG

# API
API_HOST=0.0.0.0
API_PORT=8000

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_TIMEOUT=300

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Security
SECRET_KEY=docker-secret-key-12345

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
EOF
        success ".env.docker создан"
    else
        success ".env.docker уже существует"
    fi
    
    # Права доступа
    chmod +x debug_logs.sh 2>/dev/null || true
    
    success "Окружение подготовлено"
}

# Сборка образов
build_images() {
    header "Сборка Docker образов"
    
    log "Сборка основного образа приложения..."
    if docker-compose -f docker-compose.full.yml build --no-cache; then
        success "Образы собраны успешно"
    else
        error "Ошибка сборки образов"
        exit 1
    fi
}

# Запуск сервисов
start_services() {
    header "Запуск сервисов"
    
    log "Запуск всех сервисов..."
    if docker-compose -f docker-compose.full.yml --env-file .env.docker up -d; then
        success "Сервисы запущены"
    else
        error "Ошибка запуска сервисов"
        show_logs
        exit 1
    fi
    
    # Ожидание готовности сервисов
    log "Ожидание готовности сервисов..."
    
    # Ждем Redis
    for i in {1..30}; do
        if docker-compose -f docker-compose.full.yml exec -T redis redis-cli ping > /dev/null 2>&1; then
            success "✅ Redis готов"
            break
        fi
        sleep 2
        echo -n "."
    done
    
    # Ждем Ollama
    log "Ожидание Ollama (может занять несколько минут при первом запуске)..."
    for i in {1..60}; do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            success "✅ Ollama готов"
            break
        fi
        sleep 5
        echo -n "."
    done
    
    # Ждем API
    log "Ожидание API сервера..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            success "✅ API готов"
            break
        fi
        sleep 3
        echo -n "."
    done
    
    # Ждем Frontend
    log "Ожидание фронтенда..."
    for i in {1..20}; do
        if curl -s http://localhost:3000 > /dev/null 2>&1; then
            success "✅ Frontend готов"
            break
        fi
        sleep 2
        echo -n "."
    done
}

# Установка моделей в Ollama
install_models() {
    header "Установка моделей Ollama"
    
    MODELS=("llama3" "mistral")
    
    for model in "${MODELS[@]}"; do
        log "Установка модели $model..."
        if docker-compose -f docker-compose.full.yml exec -T ollama ollama pull "$model"; then
            success "Модель $model установлена"
        else
            warning "Не удалось установить модель $model"
        fi
    done
}

# Проверка статуса всех сервисов
check_status() {
    header "Статус сервисов"
    
    # Docker контейнеры
    log "Статус Docker контейнеров:"
    docker-compose -f docker-compose.full.yml ps
    
    echo ""
    
    # Проверка эндпоинтов
    log "Проверка эндпоинтов:"
    
    # API
    if curl -s http://localhost:8000/health > /dev/null; then
        success "✅ API (http://localhost:8000)"
    else
        error "❌ API недоступен"
    fi
    
    # Ollama
    if curl -s http://localhost:11434/api/tags > /dev/null; then
        success "✅ Ollama (http://localhost:11434)"
        MODEL_COUNT=$(curl -s http://localhost:11434/api/tags | jq -r '.models | length' 2>/dev/null || echo "0")
        log "   Моделей установлено: $MODEL_COUNT"
    else
        error "❌ Ollama недоступен"
    fi
    
    # Frontend
    if curl -s http://localhost:3000 > /dev/null; then
        success "✅ Frontend (http://localhost:3000)"
    else
        error "❌ Frontend недоступен"
    fi
    
    # Redis
    if docker-compose -f docker-compose.full.yml exec -T redis redis-cli ping > /dev/null 2>&1; then
        success "✅ Redis"
    else
        error "❌ Redis недоступен"
    fi
    
    # Flower
    if curl -s http://localhost:5555 > /dev/null; then
        success "✅ Flower (http://localhost:5555)"
    else
        warning "⚠️ Flower недоступен"
    fi
}

# Тестирование системы
test_system() {
    header "Тестирование системы"
    
    # Тест API здоровья
    log "Тест API здоровья..."
    if HEALTH=$(curl -s http://localhost:8000/health/detailed); then
        if echo "$HEALTH" | jq -e '.status == "healthy"' > /dev/null 2>&1; then
            success "✅ API здоров"
        else
            warning "⚠️ API работает, но есть проблемы"
            echo "$HEALTH" | jq .
        fi
    else
        error "❌ API не отвечает"
    fi
    
    # Тест чата
    log "Тест чата..."
    CHAT_PAYLOAD='{"prompt": "Привет", "model": "llama3", "max_tokens": 20}'
    if CHAT_RESPONSE=$(curl -s -X POST http://localhost:8000/chat/sync \
        -H "Content-Type: application/json" \
        -d "$CHAT_PAYLOAD"); then
        
        if echo "$CHAT_RESPONSE" | jq -e '.response' > /dev/null 2>&1; then
            success "✅ Чат работает"
            RESPONSE=$(echo "$CHAT_RESPONSE" | jq -r '.response')
            log "   Ответ: $RESPONSE"
        else
            error "❌ Чат не работает"
            echo "Ответ: $CHAT_RESPONSE"
        fi
    else
        error "❌ Не удалось протестировать чат"
    fi
}

# Показать логи
show_logs() {
    header "Логи сервисов"
    
    log "Показ логов всех сервисов..."
    docker-compose -f docker-compose.full.yml logs --tail=50
}

# Следить за логами
follow_logs() {
    header "Мониторинг логов в реальном времени"
    log "Нажмите Ctrl+C для выхода"
    
    docker-compose -f docker-compose.full.yml logs -f
}

# Остановка сервисов
stop_services() {
    header "Остановка сервисов"
    
    log "Остановка всех сервисов..."
    docker-compose -f docker-compose.full.yml down
    
    success "Сервисы остановлены"
}

# Полная очистка
cleanup() {
    header "Полная очистка"
    
    warning "Это удалит все контейнеры, образы и данные!"
    read -p "Продолжить? (y/N): " confirm
    
    if [[ $confirm =~ ^[Yy]$ ]]; then
        log "Остановка и удаление контейнеров..."
        docker-compose -f docker-compose.full.yml down -v --remove-orphans
        
        log "Удаление образов..."
        docker rmi $(docker images "gptinfernse*" -q) 2>/dev/null || true
        
        log "Очистка системы Docker..."
        docker system prune -f
        
        success "Очистка завершена"
    else
        log "Очистка отменена"
    fi
}

# Показать информацию
show_info() {
    header "🎉 GPTInfernse запущен в Docker!"
    
    echo -e "${CYAN}🌐 Веб-интерфейсы:${NC}"
    echo "  🎨 Главный интерфейс:    http://localhost:3000"
    echo "  📚 API Документация:     http://localhost:8000/docs"
    echo "  🏥 Здоровье системы:     http://localhost:8000/health/detailed"
    echo "  🌸 Flower (Celery):      http://localhost:5555 (admin/admin123)"
    echo "  🔄 Nginx (балансировщик): http://localhost:80"
    
    echo -e "\n${CYAN}🔧 Управление:${NC}"
    echo "  $0 status     # Проверить статус"
    echo "  $0 logs       # Показать логи"
    echo "  $0 logs-f     # Следить за логами"
    echo "  $0 test       # Протестировать систему"
    echo "  $0 stop       # Остановить"
    echo "  $0 restart    # Перезапустить"
    
    echo -e "\n${CYAN}📊 Мониторинг:${NC}"
    echo "  docker-compose -f docker-compose.full.yml ps    # Статус контейнеров"
    echo "  docker-compose -f docker-compose.full.yml logs  # Все логи"
    echo "  docker stats                                     # Использование ресурсов"
    
    echo -e "\n${GREEN}🚀 Откройте http://localhost:3000 в браузере!${NC}"
}

# Главная функция
main() {
    case "${1:-start}" in
        start)
            header "🐳 Запуск GPTInfernse в Docker"
            check_docker
            prepare_environment
            build_images
            start_services
            install_models
            sleep 5
            check_status
            test_system
            show_info
            ;;
        stop)
            stop_services
            ;;
        restart)
            stop_services
            sleep 3
            $0 start
            ;;
        status)
            check_status
            ;;
        logs)
            show_logs
            ;;
        logs-f)
            follow_logs
            ;;
        test)
            test_system
            ;;
        build)
            build_images
            ;;
        models)
            install_models
            ;;
        cleanup)
            cleanup
            ;;
        debug)
            # Запуск debug скрипта для Docker
            if [ -f debug_logs.sh ]; then
                ./debug_logs.sh
            else
                error "debug_logs.sh не найден"
            fi
            ;;
        help|--help|-h)
            echo "🐳 GPTInfernse Docker Manager"
            echo ""
            echo "Использование: $0 [команда]"
            echo ""
            echo "Команды:"
            echo "  start     - Запустить всю систему в Docker (по умолчанию)"
            echo "  stop      - Остановить все сервисы"
            echo "  restart   - Перезапустить систему"
            echo "  status    - Показать статус всех сервисов"
            echo "  logs      - Показать логи"
            echo "  logs-f    - Следить за логами в реальном времени"
            echo "  test      - Протестировать систему"
            echo "  build     - Пересобрать образы"
            echo "  models    - Установить модели Ollama"
            echo "  cleanup   - Полная очистка (удалить все)"
            echo "  debug     - Запустить отладчик"
            echo "  help      - Показать эту справку"
            echo ""
            echo "После запуска система будет доступна на:"
            echo "  🎨 http://localhost:3000  - Веб-интерфейс"
            echo "  📚 http://localhost:8000  - API"
            echo "  🌸 http://localhost:5555  - Flower"
            ;;
        *)
            error "Неизвестная команда: $1"
            $0 help
            exit 1
            ;;
    esac
}

main "$@"
