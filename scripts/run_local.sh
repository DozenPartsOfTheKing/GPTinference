#!/bin/bash

# GPTInfernse Local Runner (без Docker)
# Запуск всех компонентов в локальном окружении

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка зависимостей
check_deps() {
    log_info "Проверка зависимостей..."
    
    # Python venv
    if [ -z "$VIRTUAL_ENV" ]; then
        log_error "Виртуальное окружение не активировано!"
        log_info "Выполните: source venv/bin/activate"
        exit 1
    fi
    
    # Redis
    if ! command -v redis-server &> /dev/null; then
        log_warning "Redis не установлен. Устанавливаю..."
        sudo apt update && sudo apt install redis-server -y
    fi
    
    # Ollama
    if ! curl -s http://localhost:11434/api/tags > /dev/null; then
        log_error "Ollama не доступен на localhost:11434"
        log_info "Запустите: ollama serve"
        exit 1
    fi
    
    log_success "Все зависимости в порядке"
}

# Установка переменных окружения
setup_env() {
    export DEBUG=true
    export LOG_LEVEL=INFO
    export API_HOST=0.0.0.0
    export API_PORT=8000
    export REDIS_HOST=localhost
    export REDIS_PORT=6379
    export OLLAMA_BASE_URL=http://localhost:11434
    export CELERY_BROKER_URL=redis://localhost:6379/0
    export CELERY_RESULT_BACKEND=redis://localhost:6379/0
    export SECRET_KEY=dev-secret-key-local
    
    log_success "Переменные окружения настроены"
}

# Запуск Redis
start_redis() {
    log_info "Запуск Redis..."
    
    if pgrep redis-server > /dev/null; then
        log_success "Redis уже запущен"
    else
        sudo service redis-server start
        sleep 2
        
        if redis-cli ping > /dev/null 2>&1; then
            log_success "Redis запущен успешно"
        else
            log_error "Не удалось запустить Redis"
            exit 1
        fi
    fi
}

# Запуск API сервера
start_api() {
    log_info "Запуск API сервера..."
    
    # Проверяем что порт свободен
    if lsof -i :8000 > /dev/null 2>&1; then
        log_warning "Порт 8000 занят. Останавливаю процесс..."
        pkill -f "uvicorn.*app.main:app" || true
        sleep 2
    fi
    
    # Запускаем в фоне
    nohup python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
    API_PID=$!
    echo $API_PID > .api.pid
    
    # Ждем запуска
    log_info "Ожидание запуска API сервера..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null; then
            log_success "API сервер запущен (PID: $API_PID)"
            return 0
        fi
        sleep 1
    done
    
    log_error "API сервер не запустился"
    return 1
}

# Запуск Celery worker
start_worker() {
    log_info "Запуск Celery worker..."
    
    # Останавливаем существующие воркеры
    pkill -f "celery.*worker" || true
    sleep 2
    
    # Запускаем в фоне
    nohup celery -A app.utils.celery_app.celery_app worker --loglevel=info --concurrency=2 > logs/worker.log 2>&1 &
    WORKER_PID=$!
    echo $WORKER_PID > .worker.pid
    
    sleep 3
    log_success "Celery worker запущен (PID: $WORKER_PID)"
}

# Остановка всех сервисов
stop_services() {
    log_info "Остановка сервисов..."
    
    # Остановка API
    if [ -f .api.pid ]; then
        API_PID=$(cat .api.pid)
        kill $API_PID 2>/dev/null || true
        rm -f .api.pid
        log_info "API сервер остановлен"
    fi
    
    # Остановка Worker
    if [ -f .worker.pid ]; then
        WORKER_PID=$(cat .worker.pid)
        kill $WORKER_PID 2>/dev/null || true
        rm -f .worker.pid
        log_info "Celery worker остановлен"
    fi
    
    # Остановка всех процессов
    pkill -f "uvicorn.*app.main:app" || true
    pkill -f "celery.*worker" || true
    
    log_success "Все сервисы остановлены"
}

# Проверка статуса
check_status() {
    log_info "Статус сервисов:"
    
    # API
    if curl -s http://localhost:8000/health > /dev/null; then
        log_success "✅ API сервер: Работает (http://localhost:8000)"
    else
        log_error "❌ API сервер: Не работает"
    fi
    
    # Redis
    if redis-cli ping > /dev/null 2>&1; then
        log_success "✅ Redis: Работает"
    else
        log_error "❌ Redis: Не работает"
    fi
    
    # Ollama
    if curl -s http://localhost:11434/api/tags > /dev/null; then
        log_success "✅ Ollama: Работает (http://localhost:11434)"
    else
        log_error "❌ Ollama: Не работает"
    fi
    
    # Worker
    if pgrep -f "celery.*worker" > /dev/null; then
        log_success "✅ Celery Worker: Работает"
    else
        log_error "❌ Celery Worker: Не работает"
    fi
}

# Тестирование
test_system() {
    log_info "Тестирование системы..."
    
    # Тест здоровья
    if curl -s http://localhost:8000/health | grep -q "healthy"; then
        log_success "✅ Health check прошел"
    else
        log_error "❌ Health check не прошел"
        return 1
    fi
    
    # Тест моделей
    if curl -s http://localhost:8000/models/ | grep -q "models"; then
        log_success "✅ Список моделей получен"
    else
        log_error "❌ Не удалось получить список моделей"
        return 1
    fi
    
    # Тест чата
    log_info "Тестирование чата..."
    RESPONSE=$(curl -s -X POST http://localhost:8000/chat/sync \
        -H "Content-Type: application/json" \
        -d '{"prompt": "Привет!", "model": "llama3"}')
    
    if echo "$RESPONSE" | grep -q "response"; then
        log_success "✅ Чат работает!"
        echo "Ответ: $(echo "$RESPONSE" | jq -r '.response' 2>/dev/null || echo "$RESPONSE")"
    else
        log_error "❌ Чат не работает"
        echo "Ответ: $RESPONSE"
        return 1
    fi
}

# Создание директории для логов
mkdir -p logs

# Основная логика
case "${1:-start}" in
    start)
        check_deps
        setup_env
        start_redis
        start_api
        start_worker
        sleep 3
        check_status
        log_success "🚀 GPTInfernse запущен!"
        log_info "API: http://localhost:8000/docs"
        log_info "Для остановки: $0 stop"
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        sleep 2
        $0 start
        ;;
    status)
        check_status
        ;;
    test)
        test_system
        ;;
    logs)
        echo "=== API Logs ==="
        tail -n 20 logs/api.log 2>/dev/null || echo "Нет логов API"
        echo ""
        echo "=== Worker Logs ==="
        tail -n 20 logs/worker.log 2>/dev/null || echo "Нет логов Worker"
        ;;
    help)
        echo "Использование: $0 [команда]"
        echo ""
        echo "Команды:"
        echo "  start    - Запустить все сервисы (по умолчанию)"
        echo "  stop     - Остановить все сервисы"
        echo "  restart  - Перезапустить все сервисы"
        echo "  status   - Показать статус сервисов"
        echo "  test     - Протестировать систему"
        echo "  logs     - Показать логи"
        echo "  help     - Показать эту справку"
        ;;
    *)
        log_error "Неизвестная команда: $1"
        $0 help
        exit 1
        ;;
esac
