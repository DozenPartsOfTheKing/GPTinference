#!/bin/bash

# 🛑 Остановка Docker контейнеров GPTInfernse

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

echo -e "${BLUE}🛑 ОСТАНОВКА GPTInfernse Docker${NC}"
echo "================================"

# Определяем команду compose
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    log_info "Docker Compose не найден, пробуем остановить контейнеры напрямую..."
    docker stop $(docker ps -q --filter "name=gptinfernse") 2>/dev/null || true
    docker rm $(docker ps -aq --filter "name=gptinfernse") 2>/dev/null || true
    log_success "Контейнеры остановлены!"
    exit 0
fi

log_info "Используем команду: $COMPOSE_CMD"
log_info "Останавливаем все контейнеры..."
$COMPOSE_CMD down

if [[ "$1" == "--clean" ]]; then
    log_warning "Удаляем volumes и образы..."
    $COMPOSE_CMD down -v --rmi all --remove-orphans
    docker system prune -f
fi

log_success "Все контейнеры остановлены!"

echo ""
echo -e "${GREEN}🚀 Для запуска используйте:${NC}"
echo "  ./docker-start.sh"
