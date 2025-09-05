#!/bin/bash

# 🎯 ПОШАГОВЫЙ ЗАПУСК С ТЕСТАМИ
# Каждый этап отдельно с проверкой

echo "🎯 ПОШАГОВЫЙ ЗАПУСК GPTInfernse"
echo "==============================="

cd ~/GPTinference

# ФУНКЦИИ ДЛЯ ТЕСТОВ
test_ollama() {
    echo "🧪 Тестируем Ollama..."
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        models=$(curl -s http://localhost:11434/api/tags | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(len(data.get('models', [])))
except:
    print('0')
" 2>/dev/null)
        echo "✅ Ollama работает, моделей: $models"
        return 0
    else
        echo "❌ Ollama НЕ работает"
        return 1
    fi
}

test_api() {
    echo "🧪 Тестируем API..."
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ API работает"
        
        # Тест детального здоровья
        health=$(curl -s http://localhost:8000/health/detailed 2>/dev/null)
        if echo "$health" | grep -q "healthy"; then
            echo "✅ API здоровье OK"
            return 0
        else
            echo "⚠️ API работает, но есть проблемы со здоровьем"
            echo "$health"
            return 1
        fi
    else
        echo "❌ API НЕ работает"
        return 1
    fi
}

test_frontend() {
    echo "🧪 Тестируем Frontend..."
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo "✅ Frontend отвечает"
        
        # Тест проксирования API
        if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
            echo "✅ Frontend проксирует API"
            return 0
        else
            echo "⚠️ Frontend работает, но НЕ проксирует API"
            return 1
        fi
    else
        echo "❌ Frontend НЕ работает"
        return 1
    fi
}

test_chat() {
    echo "🧪 Тестируем чат..."
    response=$(curl -s -X POST http://localhost:8000/chat/sync \
        -H "Content-Type: application/json" \
        -d '{"prompt": "Привет!", "model": "llama3", "max_tokens": 20}' 2>/dev/null)
    
    if echo "$response" | grep -q "response"; then
        echo "✅ ЧАТ РАБОТАЕТ!"
        answer=$(echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('response', 'No response')[:50])
except:
    print('Parse error')
" 2>/dev/null)
        echo "📝 Ответ: $answer..."
        return 0
    else
        echo "❌ ЧАТ НЕ РАБОТАЕТ"
        echo "📝 Ошибка: $response"
        return 1
    fi
}

# ЭТАП 1: OLLAMA
echo ""
echo "🚀 ЭТАП 1: ЗАПУСК OLLAMA"
echo "========================"

echo "🛑 Останавливаем старые процессы..."
docker stop ollama 2>/dev/null || echo "Ollama не был запущен"

echo "🐳 Запускаем Ollama Docker..."
docker start ollama 2>/dev/null || docker run -d -p 11434:11434 --name ollama ollama/ollama

echo "⏳ Ждем запуска Ollama (30 сек)..."
for i in {1..30}; do
    if test_ollama; then
        break
    fi
    sleep 1
    echo -n "."
done

echo ""
if ! test_ollama; then
    echo "❌ ЭТАП 1 ПРОВАЛЕН! Ollama не запустился"
    echo "🔍 Диагностика:"
    docker ps | grep ollama
    docker logs ollama --tail 10
    exit 1
fi

echo "✅ ЭТАП 1 УСПЕШЕН!"

# ЭТАП 2: API
echo ""
echo "🚀 ЭТАП 2: ЗАПУСК API"
echo "===================="

echo "🛑 Останавливаем старый API..."
pkill -f "uvicorn.*main:app" 2>/dev/null || echo "API не был запущен"

echo "🚀 Запускаем API сервер..."
mkdir -p logs
nohup python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
API_PID=$!

echo "⏳ Ждем запуска API (20 сек)..."
for i in {1..20}; do
    if test_api; then
        break
    fi
    sleep 1
    echo -n "."
done

echo ""
if ! test_api; then
    echo "❌ ЭТАП 2 ПРОВАЛЕН! API не запустился"
    echo "🔍 Диагностика:"
    echo "PID: $API_PID"
    tail -10 logs/api.log
    exit 1
fi

echo "✅ ЭТАП 2 УСПЕШЕН!"

# ЭТАП 3: FRONTEND
echo ""
echo "🚀 ЭТАП 3: ЗАПУСК FRONTEND"
echo "=========================="

echo "🛑 Останавливаем старый Frontend..."
pkill -f "python.*server" 2>/dev/null || echo "Frontend не был запущен"
lsof -ti:3000 | xargs kill -9 2>/dev/null || echo "Порт 3000 свободен"

echo "🌐 Запускаем Frontend с проксированием..."
cd frontend

# Создаем правильный сервер
cat > working_server.py << 'EOF'
#!/usr/bin/env python3
import http.server
import socketserver
import requests
import json

class WorkingHandler(http.server.SimpleHTTPRequestHandler):
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
            
            if method == 'GET':
                response = requests.get(api_url, headers=headers, timeout=30)
            else:
                content_length = int(self.headers.get('Content-Length', 0))
                data = self.rfile.read(content_length) if content_length > 0 else None
                response = requests.post(api_url, data=data, headers=headers, timeout=30)
            
            self.send_response(response.status_code)
            self.send_header('Content-Type', response.headers.get('Content-Type', 'application/json'))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response.content)
            
            print(f"✅ Proxy: {method} {self.path} -> {response.status_code}")
            
        except Exception as e:
            print(f"❌ Proxy error: {e}")
            self.send_error(500, str(e))
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

PORT = 3000
print(f"🌐 Frontend запущен на http://localhost:{PORT}")
with socketserver.TCPServer(("", PORT), WorkingHandler) as httpd:
    httpd.serve_forever()
EOF

nohup python3 working_server.py > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!

cd ..

echo "⏳ Ждем запуска Frontend (10 сек)..."
for i in {1..10}; do
    if test_frontend; then
        break
    fi
    sleep 1
    echo -n "."
done

echo ""
if ! test_frontend; then
    echo "❌ ЭТАП 3 ПРОВАЛЕН! Frontend не запустился"
    echo "🔍 Диагностика:"
    echo "PID: $FRONTEND_PID"
    tail -10 logs/frontend.log
    exit 1
fi

echo "✅ ЭТАП 3 УСПЕШЕН!"

# ФИНАЛЬНЫЙ ТЕСТ
echo ""
echo "🧪 ФИНАЛЬНЫЙ ТЕСТ ЧАТА"
echo "======================"

if test_chat; then
    echo ""
    echo "🎉 ВСЕ ЭТАПЫ УСПЕШНЫ!"
    echo "===================="
    echo ""
    echo "🌐 Интерфейс: http://localhost:3000"
    echo "📚 API Docs: http://localhost:8000/docs"
    echo "🏥 Health: http://localhost:8000/health/detailed"
    echo ""
    echo "📊 Процессы:"
    echo "  API PID: $API_PID"
    echo "  Frontend PID: $FRONTEND_PID"
    echo ""
    echo "📄 Логи:"
    echo "  tail -f logs/api.log"
    echo "  tail -f logs/frontend.log"
    echo ""
    echo "🚀 СИСТЕМА ГОТОВА К РАБОТЕ!"
else
    echo ""
    echo "❌ ФИНАЛЬНЫЙ ТЕСТ ПРОВАЛЕН!"
    echo "Все сервисы запущены, но чат не работает"
    echo ""
    echo "🔍 Проверьте:"
    echo "  curl http://localhost:8000/models/"
    echo "  docker exec ollama ollama list"
fi
