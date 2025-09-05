#!/bin/bash

# 🚀 GPTInfernse - Полный запуск одной командой
# Автоматическая установка и запуск всех компонентов

set -e

# Цвета для красивого вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Логирование
log() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warning() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }
header() { echo -e "${PURPLE}=== $1 ===${NC}"; }

# Проверка и установка зависимостей
install_dependencies() {
    header "Установка зависимостей"
    
    # Обновление пакетов
    log "Обновление пакетов..."
    sudo apt update -qq
    
    # Установка Redis
    if ! command -v redis-server &> /dev/null; then
        log "Установка Redis..."
        sudo apt install -y redis-server
        success "Redis установлен"
    else
        success "Redis уже установлен"
    fi
    
    # Установка jq для работы с JSON
    if ! command -v jq &> /dev/null; then
        log "Установка jq..."
        sudo apt install -y jq
        success "jq установлен"
    else
        success "jq уже установлен"
    fi
    
    # Проверка Python venv
    if [ -z "$VIRTUAL_ENV" ]; then
        if [ -d "venv" ]; then
            log "Активация виртуального окружения..."
            source venv/bin/activate
            success "Виртуальное окружение активировано"
        else
            log "Создание виртуального окружения..."
            python3 -m venv venv
            source venv/bin/activate
            success "Виртуальное окружение создано и активировано"
        fi
    else
        success "Виртуальное окружение уже активно"
    fi
    
    # Установка Python зависимостей
    log "Установка Python зависимостей..."
    pip install -q -r requirements.txt
    success "Python зависимости установлены"
}

# Проверка Ollama
check_ollama() {
    header "Проверка Ollama"
    
    if curl -s http://localhost:11434/api/tags > /dev/null; then
        success "Ollama работает на localhost:11434"
        
        # Проверка моделей
        MODELS=$(curl -s http://localhost:11434/api/tags | jq -r '.models[].name' 2>/dev/null || echo "")
        if [ -n "$MODELS" ]; then
            success "Доступные модели:"
            echo "$MODELS" | while read model; do
                echo "  - $model"
            done
        else
            warning "Модели не найдены. Установите модель: ollama pull llama3"
        fi
    else
        error "Ollama не доступен на localhost:11434"
        log "Запустите Ollama: ollama serve"
        log "И установите модель: ollama pull llama3"
        exit 1
    fi
}

# Настройка окружения
setup_environment() {
    header "Настройка окружения"
    
    # Создание .env если не существует
    if [ ! -f ".env" ]; then
        log "Создание .env файла..."
        cp config.env.example .env
        success ".env файл создан"
    else
        success ".env файл уже существует"
    fi
    
    # Создание директорий
    mkdir -p logs
    mkdir -p data
    
    # Экспорт переменных окружения
    export DEBUG=true
    export LOG_LEVEL=INFO
    export API_HOST=0.0.0.0
    export API_PORT=8000
    export REDIS_HOST=localhost
    export REDIS_PORT=6379
    export OLLAMA_BASE_URL=http://localhost:11434
    export CELERY_BROKER_URL=redis://localhost:6379/0
    export CELERY_RESULT_BACKEND=redis://localhost:6379/0
    export SECRET_KEY=dev-secret-key-$(date +%s)
    
    success "Переменные окружения настроены"
}

# Запуск Redis
start_redis() {
    header "Запуск Redis"
    
    if pgrep redis-server > /dev/null; then
        success "Redis уже запущен"
    else
        log "Запуск Redis сервера..."
        sudo service redis-server start
        sleep 2
        
        if redis-cli ping > /dev/null 2>&1; then
            success "Redis успешно запущен"
        else
            error "Не удалось запустить Redis"
            exit 1
        fi
    fi
}

# Остановка существующих процессов
stop_existing() {
    log "Остановка существующих процессов..."
    
    # Остановка API
    pkill -f "uvicorn.*app.main:app" 2>/dev/null || true
    
    # Остановка Worker
    pkill -f "celery.*worker" 2>/dev/null || true
    
    # Удаление PID файлов
    rm -f .api.pid .worker.pid
    
    sleep 2
    success "Существующие процессы остановлены"
}

# Запуск API сервера
start_api() {
    header "Запуск API сервера"
    
    log "Запуск FastAPI сервера на порту 8000..."
    nohup python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
    API_PID=$!
    echo $API_PID > .api.pid
    
    log "Ожидание запуска API сервера..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            success "API сервер запущен (PID: $API_PID)"
            success "Доступен по адресу: http://localhost:8000"
            return 0
        fi
        sleep 1
        echo -n "."
    done
    
    error "API сервер не запустился за 30 секунд"
    cat logs/api.log
    exit 1
}

# Запуск Celery Worker
start_worker() {
    header "Запуск Celery Worker"
    
    log "Запуск Celery worker..."
    nohup celery -A app.utils.celery_app.celery_app worker --loglevel=info --concurrency=2 > logs/worker.log 2>&1 &
    WORKER_PID=$!
    echo $WORKER_PID > .worker.pid
    
    sleep 3
    success "Celery worker запущен (PID: $WORKER_PID)"
}

# Тестирование системы
test_system() {
    header "Тестирование системы"
    
    # Тест здоровья API
    log "Проверка здоровья API..."
    if HEALTH=$(curl -s http://localhost:8000/health/detailed); then
        if echo "$HEALTH" | jq -e '.status == "healthy"' > /dev/null 2>&1; then
            success "✅ API здоров"
        else
            warning "⚠️  API работает, но есть проблемы с компонентами"
        fi
    else
        error "❌ API не отвечает"
        return 1
    fi
    
    # Тест списка моделей
    log "Проверка доступности моделей..."
    if MODELS=$(curl -s http://localhost:8000/models/); then
        MODEL_COUNT=$(echo "$MODELS" | jq -r '.models | length' 2>/dev/null || echo "0")
        if [ "$MODEL_COUNT" -gt 0 ]; then
            success "✅ Найдено $MODEL_COUNT моделей"
        else
            warning "⚠️  Модели не найдены"
        fi
    else
        error "❌ Не удалось получить список моделей"
    fi
    
    # Тест чата (синхронный)
    log "Тестирование чата..."
    CHAT_RESPONSE=$(curl -s -X POST http://localhost:8000/chat/sync \
        -H "Content-Type: application/json" \
        -d '{"prompt": "Привет! Скажи одно слово.", "model": "llama3", "max_tokens": 10}' 2>/dev/null)
    
    if echo "$CHAT_RESPONSE" | jq -e '.response' > /dev/null 2>&1; then
        RESPONSE_TEXT=$(echo "$CHAT_RESPONSE" | jq -r '.response')
        success "✅ Чат работает! Ответ: \"$RESPONSE_TEXT\""
    else
        warning "⚠️  Чат не работает или модель недоступна"
        echo "Ответ сервера: $CHAT_RESPONSE"
    fi
}

# Показать информацию о запущенной системе
show_info() {
    header "Система запущена!"
    
    echo -e "${CYAN}🌐 Веб-интерфейсы:${NC}"
    echo "  📚 API Документация: http://localhost:8000/docs"
    echo "  🏥 Здоровье системы:  http://localhost:8000/health/detailed"
    echo "  🤖 Список моделей:    http://localhost:8000/models/"
    
    echo -e "\n${CYAN}💻 Использование CLI:${NC}"
    echo "  python client_example.py interactive    # Интерактивный чат"
    echo "  python client_example.py health         # Проверка здоровья"
    echo "  python client_example.py models         # Список моделей"
    echo "  python client_example.py chat \"Привет!\" # Быстрый чат"
    
    echo -e "\n${CYAN}🔧 Управление:${NC}"
    echo "  ./start.sh stop      # Остановить систему"
    echo "  ./start.sh restart   # Перезапустить"
    echo "  ./start.sh status    # Проверить статус"
    echo "  ./start.sh logs      # Показать логи"
    
    echo -e "\n${CYAN}📊 Мониторинг:${NC}"
    echo "  tail -f logs/api.log     # Логи API"
    echo "  tail -f logs/worker.log  # Логи Worker"
    
    echo -e "\n${GREEN}🎉 GPTInfernse готов к работе!${NC}"
}

# Остановка системы
stop_system() {
    header "Остановка системы"
    
    # Остановка API
    if [ -f .api.pid ]; then
        API_PID=$(cat .api.pid)
        if kill $API_PID 2>/dev/null; then
            success "API сервер остановлен (PID: $API_PID)"
        fi
        rm -f .api.pid
    fi
    
    # Остановка Worker
    if [ -f .worker.pid ]; then
        WORKER_PID=$(cat .worker.pid)
        if kill $WORKER_PID 2>/dev/null; then
            success "Celery worker остановлен (PID: $WORKER_PID)"
        fi
        rm -f .worker.pid
    fi
    
    # Принудительная остановка
    pkill -f "uvicorn.*app.main:app" 2>/dev/null || true
    pkill -f "celery.*worker" 2>/dev/null || true
    
    success "Система остановлена"
}

# Проверка статуса
check_status() {
    header "Статус системы"
    
    # API
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        success "✅ API сервер: Работает (http://localhost:8000)"
    else
        error "❌ API сервер: Не работает"
    fi
    
    # Redis
    if redis-cli ping > /dev/null 2>&1; then
        success "✅ Redis: Работает"
    else
        error "❌ Redis: Не работает"
    fi
    
    # Ollama
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        success "✅ Ollama: Работает (http://localhost:11434)"
    else
        error "❌ Ollama: Не работает"
    fi
    
    # Worker
    if pgrep -f "celery.*worker" > /dev/null; then
        success "✅ Celery Worker: Работает"
    else
        error "❌ Celery Worker: Не работает"
    fi
}

# Показать логи
show_logs() {
    header "Логи системы"
    
    echo -e "${CYAN}=== API Логи (последние 20 строк) ===${NC}"
    tail -n 20 logs/api.log 2>/dev/null || echo "Логи API не найдены"
    
    echo -e "\n${CYAN}=== Worker Логи (последние 20 строк) ===${NC}"
    tail -n 20 logs/worker.log 2>/dev/null || echo "Логи Worker не найдены"
}

# Главная функция
main() {
    case "${1:-start}" in
        start)
            header "🚀 Запуск GPTInfernse"
            install_dependencies
            check_ollama
            setup_environment
            start_redis
            stop_existing
            start_api
            start_worker
            sleep 3
            test_system
            show_info
            ;;
        stop)
            stop_system
            ;;
        restart)
            stop_system
            sleep 2
            $0 start
            ;;
        status)
            check_status
            ;;
        logs)
            show_logs
            ;;
        test)
            test_system
            ;;
        help|--help|-h)
            echo "🚀 GPTInfernse - Полный запуск одной командой"
            echo ""
            echo "Использование: $0 [команда]"
            echo ""
            echo "Команды:"
            echo "  start    - Запустить всю систему (по умолчанию)"
            echo "  stop     - Остановить систему"
            echo "  restart  - Перезапустить систему"
            echo "  status   - Показать статус всех компонентов"
            echo "  logs     - Показать логи"
            echo "  test     - Протестировать систему"
            echo "  help     - Показать эту справку"
            echo ""
            echo "Примеры:"
            echo "  $0           # Запустить систему"
            echo "  $0 start     # То же самое"
            echo "  $0 status    # Проверить статус"
            echo "  $0 stop      # Остановить"
            ;;
        *)
            error "Неизвестная команда: $1"
            $0 help
            exit 1
            ;;
    esac
}

# Запуск
main "$@"
