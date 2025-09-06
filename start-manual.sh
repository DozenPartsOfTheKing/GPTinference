#!/bin/bash

# 🚀 Ручной запуск GPTInfernse без docker-compose
# Для случаев когда compose не установлен

echo "🐳 Запуск GPTInfernse без docker-compose..."

# Создаем сеть
docker network create gptinfernse-network 2>/dev/null || true

# Создаем volumes
docker volume create redis_data 2>/dev/null || true
docker volume create ollama_data 2>/dev/null || true

# Создаем директории
mkdir -p logs

echo "🔴 Запуск Redis..."
docker run -d \
  --name gptinfernse-redis \
  --network gptinfernse-network \
  -p 6379:6379 \
  -v redis_data:/data \
  redis:7-alpine \
  redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru

echo "🧠 Запуск Ollama..."
docker run -d \
  --name gptinfernse-ollama \
  --network gptinfernse-network \
  -p 11434:11434 \
  -v ollama_data:/root/.ollama \
  -e OLLAMA_HOST=0.0.0.0 \
  -e OLLAMA_ORIGINS=* \
  ollama/ollama:latest

echo "⏳ Ждем запуска Ollama..."
sleep 10

echo "🚀 Собираем API образ..."
docker build -f Dockerfile.api -t gptinfernse-api .

echo "🚀 Запуск API..."
docker run -d \
  --name gptinfernse-api \
  --network gptinfernse-network \
  -p 8000:8000 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/app:/app/app:ro \
  -e REDIS_URL=redis://gptinfernse-redis:6379/0 \
  -e OLLAMA_BASE_URL=http://gptinfernse-ollama:11434 \
  -e DEBUG=true \
  gptinfernse-api

echo "⚡ Собираем Worker образ..."
docker build -f Dockerfile.worker -t gptinfernse-worker .

echo "⚡ Запуск Worker..."
docker run -d \
  --name gptinfernse-worker \
  --network gptinfernse-network \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/app:/app/app:ro \
  -e REDIS_URL=redis://gptinfernse-redis:6379/0 \
  -e OLLAMA_BASE_URL=http://gptinfernse-ollama:11434 \
  -e DEBUG=true \
  gptinfernse-worker

echo "🌐 Собираем Frontend образ..."
docker build -f frontend/Dockerfile.frontend -t gptinfernse-frontend frontend/

echo "🌐 Запуск Frontend..."
docker run -d \
  --name gptinfernse-frontend \
  --network gptinfernse-network \
  -p 3000:3000 \
  -e API_BASE_URL=http://localhost:8000 \
  gptinfernse-frontend

echo "🌸 Запуск Flower..."
docker run -d \
  --name gptinfernse-flower \
  --network gptinfernse-network \
  -p 5555:5555 \
  -e CELERY_BROKER_URL=redis://gptinfernse-redis:6379/0 \
  -e FLOWER_PORT=5555 \
  -e FLOWER_BASIC_AUTH=admin:admin123 \
  mher/flower:latest

echo ""
echo "⏳ Ждем запуска сервисов..."
sleep 15

echo ""
echo "📊 Статус контейнеров:"
docker ps --filter "name=gptinfernse"

echo ""
echo "🎉 Готово! Откройте в браузере:"
echo "  🌐 Интерфейс:     http://localhost:3000"
echo "  📚 API Docs:      http://localhost:8000/docs"
echo "  🌸 Flower:        http://localhost:5555 (admin/admin123)"

echo ""
echo "📄 Для просмотра логов:"
echo "  docker logs -f gptinfernse-api"
echo "  docker logs -f gptinfernse-worker"
echo "  docker logs -f gptinfernse-frontend"

echo ""
echo "🛑 Для остановки:"
echo "  ./stop-manual.sh"
