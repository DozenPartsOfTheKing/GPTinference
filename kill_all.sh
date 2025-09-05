#!/bin/bash

# 💀 Убить все процессы GPTInfernse

echo "💀 ОСТАНАВЛИВАЕМ ВСЕ ПРОЦЕССЫ GPTInfernse"
echo "========================================"

# Функции для вывода
log_info() { echo "ℹ️  $1"; }
log_success() { echo "✅ $1"; }
log_warning() { echo "⚠️  $1"; }

# Убиваем Python процессы
log_info "Останавливаем Python процессы..."

processes_killed=0

# API сервер (uvicorn)
if pkill -f "uvicorn.*main:app" 2>/dev/null; then
    log_success "API сервер остановлен"
    ((processes_killed++))
fi

# Фронтенд сервер
if pkill -f "python.*server.py" 2>/dev/null; then
    log_success "Фронтенд остановлен"
    ((processes_killed++))
fi

# Celery worker
if pkill -f "celery.*worker" 2>/dev/null; then
    log_success "Celery worker остановлен"
    ((processes_killed++))
fi

# Любые другие Python процессы связанные с проектом
if pkill -f "python.*main.py" 2>/dev/null; then
    log_success "Дополнительные Python процессы остановлены"
    ((processes_killed++))
fi

# Временный сервер фронтенда
if pkill -f "temp_server.py" 2>/dev/null; then
    log_success "Временный фронтенд остановлен"
    ((processes_killed++))
fi

# Убиваем процессы на портах
log_info "Освобождаем порты..."

ports_freed=0

for port in 8000 3000 6379 5555; do
    pid=$(lsof -ti:$port 2>/dev/null)
    if [ ! -z "$pid" ]; then
        if kill -9 $pid 2>/dev/null; then
            log_success "Порт $port освобожден (PID: $pid)"
            ((ports_freed++))
        else
            log_warning "Не удалось освободить порт $port"
        fi
    fi
done

# Останавливаем Docker контейнеры
log_info "Останавливаем Docker контейнеры..."

containers_stopped=0

if docker ps | grep -q ollama; then
    if docker stop ollama 2>/dev/null; then
        log_success "Ollama контейнер остановлен"
        ((containers_stopped++))
    else
        log_warning "Не удалось остановить Ollama"
    fi
fi

# Останавливаем Redis если запущен локально
if pgrep redis-server > /dev/null; then
    if pkill redis-server 2>/dev/null; then
        log_success "Redis остановлен"
        ((processes_killed++))
    fi
fi

# Ждем завершения процессов
log_info "Ждем завершения процессов..."
sleep 3

# Финальная проверка
log_info "Финальная проверка..."

still_running=0

# Проверяем порты
for port in 8000 3000 11434; do
    if lsof -ti:$port > /dev/null 2>&1; then
        log_warning "Порт $port все еще занят"
        ((still_running++))
    fi
done

# Проверяем процессы
if pgrep -f "uvicorn\|celery\|server.py" > /dev/null 2>&1; then
    log_warning "Некоторые процессы все еще работают"
    ((still_running++))
fi

echo ""
echo "📊 ИТОГИ:"
echo "  Процессов остановлено: $processes_killed"
echo "  Портов освобождено: $ports_freed"
echo "  Контейнеров остановлено: $containers_stopped"

if [ $still_running -eq 0 ]; then
    log_success "ВСЕ ПРОЦЕССЫ УСПЕШНО ОСТАНОВЛЕНЫ!"
else
    log_warning "Некоторые процессы могут все еще работать"
    echo ""
    echo "🔍 Для принудительной очистки:"
    echo "  sudo lsof -ti:8000,3000,11434 | xargs kill -9"
    echo "  docker kill ollama"
fi

echo ""
echo "🚀 Теперь можно запустить систему заново:"
echo "  ./full_restart.sh"
