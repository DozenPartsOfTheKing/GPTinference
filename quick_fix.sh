#!/bin/bash

# 🔧 Быстрое исправление проблем GPTInfernse

echo "🔧 БЫСТРОЕ ИСПРАВЛЕНИЕ ПРОБЛЕМ"
echo "=============================="

cd ~/GPTinference

# 1. Освобождаем порт 3000 принудительно
echo "🔓 Освобождаем порт 3000..."
lsof -ti:3000 | xargs kill -9 2>/dev/null && echo "✅ Порт 3000 освобожден" || echo "⚠️ Порт 3000 уже свободен"

# 2. Останавливаем проблемный фронтенд
echo "🛑 Останавливаем проблемный фронтенд..."
pkill -f "temp_server.py" 2>/dev/null && echo "✅ Временный сервер остановлен"

# 3. Останавливаем проблемный Celery
echo "🛑 Останавливаем Celery..."
pkill -f "celery.*worker" 2>/dev/null && echo "✅ Celery остановлен"

# 4. Запускаем простой фронтенд без Celery
echo "🚀 Запускаем простой фронтенд..."

cd frontend

# Создаем минимальный рабочий сервер
cat > simple_server.py << 'EOF'
#!/usr/bin/env python3
import http.server
import socketserver
import requests
import json
from urllib.parse import urlparse

class SimpleHandler(http.server.SimpleHTTPRequestHandler):
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
    
    def proxy_to_api(self, method):
        try:
            api_url = f'http://localhost:8000{self.path}'
            
            if method == 'GET':
                response = requests.get(api_url, timeout=30)
            else:
                content_length = int(self.headers.get('Content-Length', 0))
                data = self.rfile.read(content_length) if content_length > 0 else None
                response = requests.post(api_url, data=data, 
                    headers={'Content-Type': 'application/json'}, timeout=30)
            
            self.send_response(response.status_code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response.content)
            
        except Exception as e:
            print(f"❌ Proxy error: {e}")
            self.send_error(500, str(e))
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

PORT = 3000
print(f"🌐 Запускаем фронтенд на http://localhost:{PORT}")
with socketserver.TCPServer(("", PORT), SimpleHandler) as httpd:
    httpd.serve_forever()
EOF

# Запускаем простой сервер в фоне
nohup python3 simple_server.py > ../logs/simple_frontend.log 2>&1 &
FRONTEND_PID=$!

cd ..

echo "✅ Простой фронтенд запущен (PID: $FRONTEND_PID)"

# 5. Ждем и проверяем
echo "⏳ Ждем запуска фронтенда..."
sleep 3

# Проверяем все сервисы
echo ""
echo "🔍 ПРОВЕРКА СЕРВИСОВ:"

# Ollama
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama работает"
else
    echo "❌ Ollama не работает"
fi

# API
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API сервер работает"
else
    echo "❌ API сервер не работает"
fi

# Frontend
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Фронтенд работает"
else
    echo "❌ Фронтенд не работает"
fi

echo ""
echo "🧪 ТЕСТ ЧАТА:"
response=$(curl -s -X POST http://localhost:8000/chat/sync \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Привет!", "model": "llama3"}' 2>/dev/null)

if echo "$response" | grep -q "response"; then
    echo "✅ Чат работает!"
    echo "📝 Ответ: $(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['response'][:50])..." 2>/dev/null || echo "OK")"
else
    echo "❌ Чат не работает"
    echo "📝 Ответ: $response"
fi

echo ""
echo "🎉 ГОТОВО!"
echo "🌐 Откройте: http://localhost:3000"
echo "📊 Логи фронтенда: tail -f logs/simple_frontend.log"

# Показываем активные процессы
echo ""
echo "🔄 Активные процессы:"
ps aux | grep -E "(uvicorn|python.*server|simple_server)" | grep -v grep | while read line; do
    echo "  📍 $line"
done
