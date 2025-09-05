#!/bin/bash

# 🔍 GPTInfernse Debug & Logs Script
# Полная диагностика и логирование системы

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${BLUE}[DEBUG]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warning() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }
header() { echo -e "${PURPLE}=== $1 ===${NC}"; }

# Функция для детального тестирования API
test_api_detailed() {
    header "Детальное тестирование API"
    
    # Тест базового здоровья
    log "Тестирование /health..."
    if HEALTH_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}\nTIME:%{time_total}" http://localhost:8000/health 2>&1); then
        echo "$HEALTH_RESPONSE"
        HTTP_CODE=$(echo "$HEALTH_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
        if [ "$HTTP_CODE" = "200" ]; then
            success "Health endpoint работает"
        else
            error "Health endpoint вернул код $HTTP_CODE"
        fi
    else
        error "Не удалось подключиться к API"
        return 1
    fi
    
    echo ""
    
    # Тест детального здоровья
    log "Тестирование /health/detailed..."
    if DETAILED_HEALTH=$(curl -s -w "\nHTTP_CODE:%{http_code}" http://localhost:8000/health/detailed 2>&1); then
        echo "$DETAILED_HEALTH"
        HTTP_CODE=$(echo "$DETAILED_HEALTH" | grep "HTTP_CODE:" | cut -d: -f2)
        if [ "$HTTP_CODE" = "200" ]; then
            success "Detailed health endpoint работает"
        else
            error "Detailed health endpoint вернул код $HTTP_CODE"
        fi
    else
        error "Не удалось получить детальное здоровье"
    fi
    
    echo ""
    
    # Тест моделей
    log "Тестирование /models/..."
    if MODELS_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" http://localhost:8000/models/ 2>&1); then
        echo "$MODELS_RESPONSE"
        HTTP_CODE=$(echo "$MODELS_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
        if [ "$HTTP_CODE" = "200" ]; then
            success "Models endpoint работает"
        else
            error "Models endpoint вернул код $HTTP_CODE"
        fi
    else
        error "Не удалось получить список моделей"
    fi
    
    echo ""
    
    # Тест синхронного чата с детальным логированием
    log "Тестирование /chat/sync с простым запросом..."
    CHAT_PAYLOAD='{"prompt": "Привет", "model": "llama3", "max_tokens": 50}'
    log "Payload: $CHAT_PAYLOAD"
    
    if CHAT_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}\nTIME:%{time_total}" \
        -X POST http://localhost:8000/chat/sync \
        -H "Content-Type: application/json" \
        -d "$CHAT_PAYLOAD" 2>&1); then
        
        echo "=== CHAT RESPONSE ==="
        echo "$CHAT_RESPONSE"
        echo "===================="
        
        HTTP_CODE=$(echo "$CHAT_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
        TIME=$(echo "$CHAT_RESPONSE" | grep "TIME:" | cut -d: -f2)
        
        if [ "$HTTP_CODE" = "200" ]; then
            success "Chat endpoint работает (время: ${TIME}s)"
        else
            error "Chat endpoint вернул код $HTTP_CODE"
            
            # Попробуем понять причину ошибки
            if echo "$CHAT_RESPONSE" | grep -q "Model.*not found"; then
                error "Модель не найдена. Проверьте доступные модели в Ollama"
            elif echo "$CHAT_RESPONSE" | grep -q "Connection"; then
                error "Проблема подключения к Ollama"
            fi
        fi
    else
        error "Не удалось отправить запрос к чату"
    fi
}

# Проверка всех сервисов
check_all_services() {
    header "Проверка всех сервисов"
    
    # API Server
    log "Проверка API Server (порт 8000)..."
    if curl -s http://localhost:8000/health > /dev/null; then
        success "✅ API Server работает"
    else
        error "❌ API Server не отвечает"
        log "Проверьте логи: tail -f logs/api.log"
    fi
    
    # Ollama
    log "Проверка Ollama (порт 11434)..."
    if OLLAMA_RESPONSE=$(curl -s http://localhost:11434/api/tags); then
        success "✅ Ollama работает"
        MODEL_COUNT=$(echo "$OLLAMA_RESPONSE" | jq -r '.models | length' 2>/dev/null || echo "0")
        log "Найдено моделей: $MODEL_COUNT"
        
        if [ "$MODEL_COUNT" -gt 0 ]; then
            log "Доступные модели:"
            echo "$OLLAMA_RESPONSE" | jq -r '.models[].name' 2>/dev/null | while read model; do
                echo "  - $model"
            done
        else
            warning "Модели не найдены! Установите: ollama pull llama3"
        fi
    else
        error "❌ Ollama не отвечает"
        log "Запустите: ollama serve"
    fi
    
    # Redis
    log "Проверка Redis (порт 6379)..."
    if redis-cli ping > /dev/null 2>&1; then
        success "✅ Redis работает"
    else
        error "❌ Redis не работает"
        log "Запустите: sudo service redis-server start"
    fi
    
    # Celery Worker
    log "Проверка Celery Worker..."
    if pgrep -f "celery.*worker" > /dev/null; then
        success "✅ Celery Worker работает"
    else
        error "❌ Celery Worker не работает"
        log "Проверьте логи: tail -f logs/worker.log"
    fi
    
    # Frontend
    log "Проверка Frontend (порт 3000)..."
    if curl -s http://localhost:3000 > /dev/null; then
        success "✅ Frontend работает"
    else
        error "❌ Frontend не работает"
        log "Проверьте логи: tail -f logs/frontend.log"
    fi
}

# Показать все логи
show_all_logs() {
    header "Все логи системы"
    
    echo -e "${CYAN}=== API Server Logs ===${NC}"
    if [ -f logs/api.log ]; then
        tail -n 30 logs/api.log
    else
        warning "Файл logs/api.log не найден"
    fi
    
    echo -e "\n${CYAN}=== Celery Worker Logs ===${NC}"
    if [ -f logs/worker.log ]; then
        tail -n 30 logs/worker.log
    else
        warning "Файл logs/worker.log не найден"
    fi
    
    echo -e "\n${CYAN}=== Frontend Logs ===${NC}"
    if [ -f logs/frontend.log ]; then
        tail -n 30 logs/frontend.log
    else
        warning "Файл logs/frontend.log не найден"
    fi
    
    echo -e "\n${CYAN}=== System Logs (последние ошибки) ===${NC}"
    journalctl --since "10 minutes ago" --no-pager | grep -i error | tail -10 || echo "Нет системных ошибок"
}

# Мониторинг в реальном времени
live_monitoring() {
    header "Мониторинг в реальном времени"
    log "Нажмите Ctrl+C для выхода"
    
    while true; do
        clear
        echo -e "${PURPLE}=== GPTInfernse Live Monitor $(date) ===${NC}"
        
        # Статус сервисов
        echo -e "\n${CYAN}Статус сервисов:${NC}"
        curl -s http://localhost:8000/health > /dev/null && echo "✅ API" || echo "❌ API"
        curl -s http://localhost:11434/api/tags > /dev/null && echo "✅ Ollama" || echo "❌ Ollama"
        redis-cli ping > /dev/null 2>&1 && echo "✅ Redis" || echo "❌ Redis"
        pgrep -f "celery.*worker" > /dev/null && echo "✅ Worker" || echo "❌ Worker"
        curl -s http://localhost:3000 > /dev/null && echo "✅ Frontend" || echo "❌ Frontend"
        
        # Использование ресурсов
        echo -e "\n${CYAN}Ресурсы:${NC}"
        echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
        echo "RAM: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
        echo "Disk: $(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 ")"}')"
        
        # Последние логи
        echo -e "\n${CYAN}Последние события:${NC}"
        tail -n 5 logs/api.log 2>/dev/null | sed 's/^/API: /' || echo "API: нет логов"
        tail -n 3 logs/worker.log 2>/dev/null | sed 's/^/Worker: /' || echo "Worker: нет логов"
        
        sleep 5
    done
}

# Диагностика проблем
diagnose_issues() {
    header "Диагностика проблем"
    
    # Проверка портов
    log "Проверка занятых портов..."
    for port in 8000 11434 6379 3000; do
        if lsof -i :$port > /dev/null 2>&1; then
            PROCESS=$(lsof -i :$port | tail -1 | awk '{print $1 " (PID: " $2 ")"}')
            success "Порт $port занят: $PROCESS"
        else
            warning "Порт $port свободен"
        fi
    done
    
    # Проверка процессов
    log "Проверка процессов..."
    echo "Python процессы:"
    ps aux | grep python | grep -v grep | head -5
    
    echo "Celery процессы:"
    ps aux | grep celery | grep -v grep | head -3
    
    # Проверка дискового пространства
    log "Проверка дискового пространства..."
    df -h | grep -E "(Filesystem|/dev/)"
    
    # Проверка памяти
    log "Проверка памяти..."
    free -h
    
    # Проверка сетевых соединений
    log "Проверка сетевых соединений..."
    netstat -tlnp | grep -E "(8000|11434|6379|3000)" | head -10
}

# Исправление частых проблем
fix_common_issues() {
    header "Исправление частых проблем"
    
    log "1. Перезапуск Redis..."
    sudo service redis-server restart
    sleep 2
    
    log "2. Очистка старых процессов..."
    pkill -f "uvicorn.*app.main:app" 2>/dev/null || true
    pkill -f "celery.*worker" 2>/dev/null || true
    pkill -f "frontend/server.py" 2>/dev/null || true
    
    log "3. Очистка PID файлов..."
    rm -f .api.pid .worker.pid .frontend.pid
    
    log "4. Проверка прав доступа..."
    chmod +x start.sh start_with_frontend.sh 2>/dev/null || true
    
    log "5. Создание директорий..."
    mkdir -p logs data frontend
    
    success "Базовые исправления выполнены"
}

# Экспорт логов для анализа
export_logs() {
    header "Экспорт логов для анализа"
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    EXPORT_DIR="debug_export_$TIMESTAMP"
    
    mkdir -p "$EXPORT_DIR"
    
    # Копируем логи
    cp -r logs/ "$EXPORT_DIR/" 2>/dev/null || true
    
    # Системная информация
    {
        echo "=== System Info ==="
        uname -a
        echo ""
        echo "=== Python Version ==="
        python3 --version
        echo ""
        echo "=== Pip Packages ==="
        pip list
        echo ""
        echo "=== Environment Variables ==="
        env | grep -E "(OLLAMA|REDIS|CELERY|DEBUG)" | sort
        echo ""
        echo "=== Process List ==="
        ps aux | grep -E "(python|celery|uvicorn|ollama|redis)" | grep -v grep
        echo ""
        echo "=== Port Status ==="
        netstat -tlnp | grep -E "(8000|11434|6379|3000)"
        echo ""
        echo "=== Disk Space ==="
        df -h
        echo ""
        echo "=== Memory ==="
        free -h
    } > "$EXPORT_DIR/system_info.txt"
    
    # API тесты
    {
        echo "=== API Health Test ==="
        curl -s http://localhost:8000/health 2>&1 || echo "API не отвечает"
        echo ""
        echo "=== Ollama Test ==="
        curl -s http://localhost:11434/api/tags 2>&1 || echo "Ollama не отвечает"
        echo ""
        echo "=== Redis Test ==="
        redis-cli ping 2>&1 || echo "Redis не отвечает"
    } > "$EXPORT_DIR/api_tests.txt"
    
    # Создаем архив
    tar -czf "${EXPORT_DIR}.tar.gz" "$EXPORT_DIR"
    rm -rf "$EXPORT_DIR"
    
    success "Логи экспортированы в ${EXPORT_DIR}.tar.gz"
    log "Отправьте этот файл для анализа проблем"
}

# Главное меню
show_menu() {
    header "GPTInfernse Debug & Logs Menu"
    echo "1. Проверить все сервисы"
    echo "2. Детальное тестирование API"
    echo "3. Показать все логи"
    echo "4. Мониторинг в реальном времени"
    echo "5. Диагностика проблем"
    echo "6. Исправить частые проблемы"
    echo "7. Экспорт логов для анализа"
    echo "8. Выход"
    echo ""
    read -p "Выберите опцию (1-8): " choice
    
    case $choice in
        1) check_all_services ;;
        2) test_api_detailed ;;
        3) show_all_logs ;;
        4) live_monitoring ;;
        5) diagnose_issues ;;
        6) fix_common_issues ;;
        7) export_logs ;;
        8) exit 0 ;;
        *) error "Неверный выбор" ;;
    esac
}

# Главная функция
main() {
    case "${1:-menu}" in
        check) check_all_services ;;
        test) test_api_detailed ;;
        logs) show_all_logs ;;
        monitor) live_monitoring ;;
        diagnose) diagnose_issues ;;
        fix) fix_common_issues ;;
        export) export_logs ;;
        menu) show_menu ;;
        *) 
            echo "Использование: $0 [check|test|logs|monitor|diagnose|fix|export|menu]"
            exit 1
            ;;
    esac
}

main "$@"
