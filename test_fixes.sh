#!/bin/bash

# 🔧 Скрипт для тестирования исправлений GPTInfernse

echo "🚀 Тестирование исправлений GPTInfernse"
echo "========================================"

# Проверяем, что Ollama запущен
echo "🔍 Проверка Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama работает на порту 11434"
    
    # Показываем доступные модели
    echo "📋 Доступные модели:"
    curl -s http://localhost:11434/api/tags | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'models' in data and data['models']:
        for model in data['models']:
            print(f'  - {model[\"name\"]} ({model.get(\"size\", \"unknown size\")})')
    else:
        print('  ❌ Модели не найдены')
except:
    print('  ❌ Ошибка парсинга ответа Ollama')
"
else
    echo "❌ Ollama недоступен на localhost:11434"
    echo "💡 Запустите: docker run -d -p 11434:11434 --name ollama ollama/ollama"
    echo "💡 Установите модели: docker exec ollama ollama pull llama3"
fi

echo ""

# Проверяем API сервер
echo "🔍 Проверка API сервера..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API сервер работает на порту 8000"
    
    # Проверяем детальное здоровье
    echo "🏥 Детальная проверка здоровья:"
    curl -s http://localhost:8000/health/detailed | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f'  Статус: {data.get(\"status\", \"unknown\")}')
    print(f'  Сервис: {data.get(\"service\", \"unknown\")}')
    
    if 'components' in data:
        for name, component in data['components'].items():
            status = component.get('status', 'unknown')
            emoji = '✅' if status == 'healthy' else '❌'
            print(f'  {emoji} {name}: {status}')
            
            if name == 'ollama' and 'models_count' in component:
                print(f'    Моделей найдено: {component[\"models_count\"]}')
except Exception as e:
    print(f'  ❌ Ошибка парсинга: {e}')
"
else
    echo "❌ API сервер недоступен на localhost:8000"
    echo "💡 Запустите: ./start_with_frontend.sh"
fi

echo ""

# Проверяем фронтенд
echo "🔍 Проверка фронтенда..."
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Фронтенд работает на порту 3000"
else
    echo "❌ Фронтенд недоступен на localhost:3000"
    echo "💡 Запустите: ./start_with_frontend.sh"
fi

echo ""

# Тестируем API endpoints
echo "🧪 Тестирование API endpoints..."

# Тест списка моделей
echo "📋 Тест /models/:"
curl -s -w "HTTP_CODE:%{http_code} TIME:%{time_total}\n" http://localhost:8000/models/ | head -5

echo ""

# Тест чата (только если есть модели)
echo "💬 Тест /chat/sync:"
curl -s -w "HTTP_CODE:%{http_code} TIME:%{time_total}\n" \
  -X POST http://localhost:8000/chat/sync \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Привет! Это тест.", "model": "llama3", "max_tokens": 50}' | head -5

echo ""
echo "========================================"

# Проверяем логи на ошибки
echo "🔍 Проверка логов на ошибки..."
if [ -f "logs/api.log" ]; then
    echo "📄 Последние ошибки в API логах:"
    tail -20 logs/api.log | grep -i error | tail -5 || echo "  ✅ Ошибок не найдено"
else
    echo "  ⚠️ Файл логов API не найден"
fi

echo ""

# Рекомендации
echo "💡 Рекомендации по исправлению:"
echo "1. Если Ollama не работает:"
echo "   docker run -d -p 11434:11434 --name ollama ollama/ollama"
echo "   docker exec ollama ollama pull llama3"
echo "   docker exec ollama ollama pull mistral"
echo ""
echo "2. Если API не работает:"
echo "   ./start_with_frontend.sh restart"
echo ""
echo "3. Если модели не найдены:"
echo "   docker exec ollama ollama list"
echo "   docker exec ollama ollama pull llama3"
echo ""
echo "4. Для полной диагностики:"
echo "   ./debug_logs.sh"
echo ""

# Показываем статус всех сервисов
echo "📊 Итоговый статус:"
OLLAMA_STATUS="❌"
API_STATUS="❌"
FRONTEND_STATUS="❌"

curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && OLLAMA_STATUS="✅"
curl -s http://localhost:8000/health > /dev/null 2>&1 && API_STATUS="✅"
curl -s http://localhost:3000 > /dev/null 2>&1 && FRONTEND_STATUS="✅"

echo "  $OLLAMA_STATUS Ollama (localhost:11434)"
echo "  $API_STATUS API Server (localhost:8000)"
echo "  $FRONTEND_STATUS Frontend (localhost:3000)"

if [[ "$OLLAMA_STATUS" == "✅" && "$API_STATUS" == "✅" && "$FRONTEND_STATUS" == "✅" ]]; then
    echo ""
    echo "🎉 Все сервисы работают! Откройте http://localhost:3000"
else
    echo ""
    echo "⚠️ Некоторые сервисы не работают. Используйте рекомендации выше."
fi

echo ""
echo "🔗 Полезные ссылки:"
echo "  🌐 Интерфейс: http://localhost:3000"
echo "  📚 API Docs: http://localhost:8000/docs"
echo "  🏥 Health: http://localhost:8000/health/detailed"
echo "  🎨 Demo: http://localhost:3000/demo.html"
