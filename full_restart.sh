#!/bin/bash

# 🔥 Полная перезагрузка GPTInfernse
# Убивает все процессы и запускает систему с нуля

echo "🔥 ПОЛНАЯ ПЕРЕЗАГРУЗКА GPTInfernse"
echo "=================================="

# Функция для красивого вывода
log_info() { echo "ℹ️  $1"; }
log_success() { echo "✅ $1"; }
log_error() { echo "❌ $1"; }
log_warning() { echo "⚠️  $1"; }

# 1. УБИВАЕМ ВСЕ ПРОЦЕССЫ
echo ""
log_info "Останавливаем все процессы..."

# Убиваем Python процессы (API, фронтенд, воркеры)
log_info "Останавливаем Python процессы..."
pkill -f "uvicorn.*main:app" 2>/dev/null && log_success "API сервер остановлен" || log_warning "API сервер не был запущен"
pkill -f "python.*server.py" 2>/dev/null && log_success "Фронтенд остановлен" || log_warning "Фронтенд не был запущен"
pkill -f "celery.*worker" 2>/dev/null && log_success "Celery worker остановлен" || log_warning "Celery worker не был запущен"
pkill -f "python.*main.py" 2>/dev/null && log_success "Дополнительные Python процессы остановлены"

# Убиваем процессы на портах
log_info "Освобождаем порты..."
for port in 8000 3000 6379 5555; do
    pid=$(lsof -ti:$port 2>/dev/null)
    if [ ! -z "$pid" ]; then
        kill -9 $pid 2>/dev/null && log_success "Порт $port освобожден" || log_warning "Не удалось освободить порт $port"
    fi
done

# Ждем завершения процессов
sleep 3

# 2. ПРОВЕРЯЕМ ЗАВИСИМОСТИ
echo ""
log_info "Проверяем зависимости..."

# Проверяем Python
if command -v python3 &> /dev/null; then
    log_success "Python3 найден: $(python3 --version)"
else
    log_error "Python3 не найден!"
    exit 1
fi

# Проверяем виртуальное окружение
if [[ "$VIRTUAL_ENV" != "" ]]; then
    log_success "Виртуальное окружение активно: $VIRTUAL_ENV"
else
    log_warning "Виртуальное окружение не активно"
    if [ -f "venv/bin/activate" ]; then
        log_info "Активируем виртуальное окружение..."
        source venv/bin/activate
        log_success "Виртуальное окружение активировано"
    fi
fi

# Проверяем Docker (для Ollama)
if command -v docker &> /dev/null; then
    log_success "Docker найден"
else
    log_error "Docker не найден! Установите Docker для работы с Ollama"
fi

# 3. ЗАПУСКАЕМ OLLAMA
echo ""
log_info "Запускаем Ollama..."

# Проверяем, запущен ли контейнер Ollama
if docker ps | grep -q ollama; then
    log_success "Ollama уже запущен"
else
    log_info "Запускаем контейнер Ollama..."
    if docker run -d -p 11434:11434 --name ollama ollama/ollama 2>/dev/null; then
        log_success "Ollama запущен"
    else
        # Возможно контейнер уже существует, но остановлен
        if docker start ollama 2>/dev/null; then
            log_success "Ollama перезапущен"
        else
            log_error "Не удалось запустить Ollama"
        fi
    fi
fi

# Ждем запуска Ollama
log_info "Ждем запуска Ollama..."
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        log_success "Ollama готов к работе"
        break
    fi
    sleep 1
    echo -n "."
done

# Проверяем модели
log_info "Проверяем модели..."
models=$(curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'models' in data and data['models']:
        print(len(data['models']))
    else:
        print('0')
except:
    print('0')
" 2>/dev/null)

if [ "$models" -gt 0 ]; then
    log_success "Найдено моделей: $models"
else
    log_warning "Модели не найдены, устанавливаем базовые модели..."
    docker exec ollama ollama pull llama3 &
    docker exec ollama ollama pull mistral &
    log_info "Модели устанавливаются в фоне..."
fi

# 4. ЗАПУСКАЕМ REDIS
echo ""
log_info "Запускаем Redis..."

if command -v redis-server &> /dev/null; then
    if ! pgrep redis-server > /dev/null; then
        redis-server --daemonize yes --port 6379 2>/dev/null && log_success "Redis запущен" || log_warning "Не удалось запустить Redis"
    else
        log_success "Redis уже запущен"
    fi
else
    log_warning "Redis не установлен, используем встроенную память"
fi

# 5. УСТАНАВЛИВАЕМ ЗАВИСИМОСТИ
echo ""
log_info "Проверяем Python зависимости..."

if [ -f "requirements.txt" ]; then
    log_info "Устанавливаем зависимости..."
    pip install -r requirements.txt --quiet && log_success "Зависимости установлены" || log_error "Ошибка установки зависимостей"
else
    log_warning "requirements.txt не найден"
fi

# 6. ЗАПУСКАЕМ API СЕРВЕР
echo ""
log_info "Запускаем API сервер..."

# Создаем директорию для логов
mkdir -p logs

# Запускаем API в фоне
nohup python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
API_PID=$!

log_info "API сервер запускается (PID: $API_PID)..."

# Ждем запуска API
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        log_success "API сервер готов"
        break
    fi
    sleep 1
    echo -n "."
done

# 7. ЗАПУСКАЕМ CELERY WORKER
echo ""
log_info "Запускаем Celery worker..."

nohup celery -A app.workers.celery_app worker --loglevel=info > logs/worker.log 2>&1 &
WORKER_PID=$!

log_success "Celery worker запущен (PID: $WORKER_PID)"

# 8. ЗАПУСКАЕМ ФРОНТЕНД
echo ""
log_info "Запускаем фронтенд..."

# Переходим в директорию фронтенда
cd frontend

# Создаем улучшенный сервер фронтенда
cat > temp_server.py << 'EOF'
#!/usr/bin/env python3
import http.server
import socketserver
import requests
import json
from urllib.parse import urlparse
import os

class GPTInfernseHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '':
            self.path = '/index.html'
        elif self.path.startswith('/api/'):
            return self.proxy_to_api('GET')
        return super().do_GET()
    
    def do_POST(self):
        if self.path.startswith('/api/'):
            return self.proxy_to_api('POST')
        self.send_error(404)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def proxy_to_api(self, method):
        try:
            api_url = f'http://localhost:8000{self.path}'
            headers = {'Content-Type': 'application/json'}
            
            data = None
            if method == 'POST':
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    data = self.rfile.read(content_length)
            
            if method == 'GET':
                response = requests.get(api_url, headers=headers, timeout=30)
            else:
                response = requests.post(api_url, data=data, headers=headers, timeout=30)
            
            self.send_response(response.status_code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response.content)
            
        except Exception as e:
            print(f"Proxy error: {e}")
            self.send_error(500, str(e))
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

if __name__ == "__main__":
    PORT = 3000
    with socketserver.TCPServer(("", PORT), GPTInfernseHandler) as httpd:
        print(f"🌐 Фронтенд запущен на http://localhost:{PORT}")
        httpd.serve_forever()
EOF

# Запускаем фронтенд
nohup python3 temp_server.py > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!

cd ..

log_success "Фронтенд запущен (PID: $FRONTEND_PID)"

# 9. ФИНАЛЬНАЯ ПРОВЕРКА
echo ""
log_info "Финальная проверка системы..."

sleep 5

# Проверяем все сервисы
OLLAMA_OK=false
API_OK=false
FRONTEND_OK=false

# Ollama
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    OLLAMA_OK=true
    log_success "Ollama работает"
else
    log_error "Ollama не отвечает"
fi

# API
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    API_OK=true
    log_success "API сервер работает"
else
    log_error "API сервер не отвечает"
fi

# Frontend
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    FRONTEND_OK=true
    log_success "Фронтенд работает"
else
    log_error "Фронтенд не отвечает"
fi

# 10. ИТОГОВЫЙ ОТЧЕТ
echo ""
echo "🎯 ИТОГОВЫЙ СТАТУС"
echo "=================="

echo "Сервисы:"
echo "  $([ "$OLLAMA_OK" = true ] && echo "✅" || echo "❌") Ollama (localhost:11434)"
echo "  $([ "$API_OK" = true ] && echo "✅" || echo "❌") API Server (localhost:8000)"
echo "  $([ "$FRONTEND_OK" = true ] && echo "✅" || echo "❌") Frontend (localhost:3000)"

echo ""
echo "PIDs процессов:"
echo "  API: $API_PID"
echo "  Worker: $WORKER_PID"
echo "  Frontend: $FRONTEND_PID"

echo ""
echo "Логи:"
echo "  📄 API: tail -f logs/api.log"
echo "  📄 Worker: tail -f logs/worker.log"
echo "  📄 Frontend: tail -f logs/frontend.log"

echo ""
if [ "$OLLAMA_OK" = true ] && [ "$API_OK" = true ] && [ "$FRONTEND_OK" = true ]; then
    echo "🎉 ВСЕ СЕРВИСЫ ЗАПУЩЕНЫ УСПЕШНО!"
    echo ""
    echo "🔗 Полезные ссылки:"
    echo "  🌐 Интерфейс: http://localhost:3000"
    echo "  📚 API Docs: http://localhost:8000/docs"
    echo "  🏥 Health: http://localhost:8000/health/detailed"
    echo ""
    echo "💡 Для остановки всех сервисов:"
    echo "  kill $API_PID $WORKER_PID $FRONTEND_PID"
    echo "  docker stop ollama"
else
    echo "⚠️  НЕКОТОРЫЕ СЕРВИСЫ НЕ ЗАПУСТИЛИСЬ"
    echo ""
    echo "🔍 Для диагностики:"
    echo "  ./debug_logs.sh"
    echo "  tail -f logs/*.log"
fi

echo ""
echo "🚀 Система готова к работе!"
