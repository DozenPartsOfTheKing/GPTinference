#!/bin/bash

# Скрипт для запуска админки GPTInfernse

set -e

echo "🔧 Запуск GPTInfernse Admin Panel..."

# Проверяем, что мы в правильной директории
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Ошибка: docker-compose.yml не найден"
    echo "   Запустите скрипт из корневой директории проекта"
    exit 1
fi

# Проверяем доступность Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен или недоступен"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен или недоступен"
    exit 1
fi

# Проверяем, запущен ли основной API
echo "🔍 Проверка основного API..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Основной API доступен"
else
    echo "⚠️  Основной API недоступен на localhost:8000"
    echo "   Запустите основную систему: ./docker-start.sh"
    
    read -p "Продолжить запуск админки? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Проверяем, не запущена ли уже админка
if curl -s http://localhost:3002 > /dev/null 2>&1; then
    echo "⚠️  Админка уже запущена на порту 3002"
    echo "🌐 Откройте http://localhost:3002 в браузере"
    exit 0
fi

# Собираем и запускаем админку
echo "🏗️  Сборка образа админки..."
docker-compose build admin

echo "🚀 Запуск админки..."
docker-compose up -d admin

# Ждем запуска
echo "⏳ Ожидание запуска сервиса..."
for i in {1..30}; do
    if curl -s http://localhost:3002 > /dev/null 2>&1; then
        echo "✅ Админка запущена успешно!"
        echo ""
        echo "🌐 Админка доступна по адресу: http://localhost:3002"
        echo "📊 Dashboard: http://localhost:3002"
        echo "🧠 Модели: http://localhost:3002#models"
        echo "💾 Память: http://localhost:3002#memory"
        echo ""
        echo "📋 Полезные команды:"
        echo "   Логи админки: docker logs gptinfernse-admin"
        echo "   Остановка: docker-compose stop admin"
        echo "   Перезапуск: docker-compose restart admin"
        echo ""
        
        # Пытаемся открыть в браузере (macOS)
        if command -v open &> /dev/null; then
            echo "🔗 Открываем админку в браузере..."
            open http://localhost:3002
        fi
        
        exit 0
    fi
    
    echo "   Попытка $i/30..."
    sleep 2
done

echo "❌ Не удалось запустить админку за 60 секунд"
echo "📋 Проверьте логи: docker logs gptinfernse-admin"
echo "🔧 Проверьте статус: docker-compose ps admin"

exit 1
