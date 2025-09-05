#!/bin/bash

# 💀 УБИТЬ ВСЕ НАХУЙ И ЗАПУСТИТЬ НОРМАЛЬНО

echo "💀 УБИВАЕМ ВСЕ ПРОЦЕССЫ НАХУЙ!"
echo "================================"

cd ~/GPTinference

# Убиваем ВСЕ Python процессы
echo "🔥 Убиваем все Python процессы..."
pkill -f python 2>/dev/null && echo "✅ Python процессы убиты"

# Убиваем процессы на ВСЕХ портах
echo "🔥 Освобождаем ВСЕ порты..."
for port in 8000 3000 3001 6379 5555 11434; do
    lsof -ti:$port 2>/dev/null | xargs kill -9 2>/dev/null && echo "✅ Порт $port освобожден"
done

# Убиваем Docker контейнеры
echo "🔥 Останавливаем Docker..."
docker stop ollama 2>/dev/null && echo "✅ Ollama остановлен"

# Ждем
sleep 3

echo ""
echo "🚀 ЗАПУСКАЕМ ВСЕ ЗАНОВО НОРМАЛЬНО!"
echo "=================================="

# Активируем venv если нужно
if [[ "$VIRTUAL_ENV" == "" ]]; then
    source venv/bin/activate
    echo "✅ Venv активирован"
fi

# 1. Запускаем Ollama
echo "🤖 Запускаем Ollama..."
docker start ollama 2>/dev/null || docker run -d -p 11434:11434 --name ollama ollama/ollama
echo "⏳ Ждем Ollama..."
sleep 10

# 2. Запускаем API
echo "🚀 Запускаем API..."
nohup python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
API_PID=$!
echo "✅ API запущен (PID: $API_PID)"
sleep 5

# 3. Запускаем простой фронтенд
echo "🌐 Запускаем фронтенд..."
cd frontend
nohup python3 -m http.server 3000 > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "✅ Фронтенд запущен (PID: $FRONTEND_PID)"
cd ..

sleep 3

echo ""
echo "🧪 ПРОВЕРЯЕМ ЧТО ВСЕ РАБОТАЕТ:"
echo "============================="

# Проверяем Ollama
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama работает"
else
    echo "❌ Ollama НЕ работает"
fi

# Проверяем API
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API работает"
else
    echo "❌ API НЕ работает"
fi

# Проверяем фронтенд
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Фронтенд работает"
else
    echo "❌ Фронтенд НЕ работает"
fi

# Тестируем чат
echo ""
echo "💬 ТЕСТИРУЕМ ЧАТ:"
response=$(curl -s -X POST http://localhost:8000/chat/sync \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Привет!", "model": "llama3"}' 2>/dev/null)

if echo "$response" | grep -q "response"; then
    echo "✅ ЧАТ РАБОТАЕТ!"
    echo "📝 Ответ: $(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin)['response'][:100])" 2>/dev/null)"
else
    echo "❌ ЧАТ НЕ РАБОТАЕТ"
    echo "📝 Ошибка: $response"
fi

echo ""
echo "🎉 ГОТОВО!"
echo "=========="
echo "🌐 Открывай: http://localhost:3000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "📊 Процессы:"
echo "  API PID: $API_PID"
echo "  Frontend PID: $FRONTEND_PID"
echo ""
echo "📄 Логи:"
echo "  tail -f logs/api.log"
echo "  tail -f logs/frontend.log"
