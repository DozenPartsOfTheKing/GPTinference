#!/bin/bash

# 🚀 Запуск GPTInfernse с альтернативными портами
# Для случаев когда стандартные порты заняты

echo "🐳 Запуск GPTInfernse с альтернативными портами..."
echo "Redis: 6380 (вместо 6379)"
echo "Ollama: 11435 (вместо 11434)"
echo ""

# Определяем команду compose
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ Docker Compose не найден!"
    echo "Используйте: ./start-manual.sh"
    exit 1
fi

# Останавливаем старые контейнеры
echo "🛑 Останавливаем старые контейнеры..."
$COMPOSE_CMD -f docker-compose.alt-ports.yml down 2>/dev/null || true

# Создаем директории
mkdir -p logs

# Запускаем с альтернативными портами
echo "🚀 Запускаем с альтернативными портами..."
$COMPOSE_CMD -f docker-compose.alt-ports.yml up -d --build

echo ""
echo "⏳ Ждем запуска сервисов..."
sleep 15

echo ""
echo "📊 Статус контейнеров:"
$COMPOSE_CMD -f docker-compose.alt-ports.yml ps

echo ""
echo "🎉 Готово! Откройте в браузере:"
echo "  🌐 Интерфейс:     http://localhost:3000"
echo "  📚 API Docs:      http://localhost:8000/docs"
echo "  🌸 Flower:        http://localhost:5555 (admin/admin123)"
echo ""
echo "📊 Альтернативные порты:"
echo "  Redis:            localhost:6380"
echo "  Ollama:           localhost:11435"
echo ""
echo "🛑 Для остановки:"
echo "  $COMPOSE_CMD -f docker-compose.alt-ports.yml down"
