#!/bin/bash

# 🛑 Остановка GPTInfernse без docker-compose

echo "🛑 Остановка всех контейнеров GPTInfernse..."

# Останавливаем и удаляем контейнеры
docker stop gptinfernse-redis gptinfernse-ollama gptinfernse-api gptinfernse-worker gptinfernse-frontend gptinfernse-flower 2>/dev/null || true
docker rm gptinfernse-redis gptinfernse-ollama gptinfernse-api gptinfernse-worker gptinfernse-frontend gptinfernse-flower 2>/dev/null || true

# Удаляем сеть
docker network rm gptinfernse-network 2>/dev/null || true

echo "✅ Все контейнеры остановлены!"

if [[ "$1" == "--clean" ]]; then
    echo "🧹 Полная очистка..."
    # Удаляем volumes
    docker volume rm redis_data ollama_data 2>/dev/null || true
    # Удаляем образы
    docker rmi gptinfernse-api gptinfernse-worker gptinfernse-frontend 2>/dev/null || true
    echo "✅ Очистка завершена!"
fi

echo ""
echo "🚀 Для запуска используйте:"
echo "  ./start-manual.sh"
