# 🚀 Руководство по развертыванию GPTInfernse

## Быстрый старт (5 минут)

### 1. Предварительные требования
```bash
# Проверьте наличие Docker
docker --version
docker-compose --version

# Запустите Ollama (если еще не запущен)
ollama serve

# Установите базовые модели
ollama pull llama3
ollama pull mistral
```

### 2. Развертывание
```bash
# Клонируйте проект
git clone <your-repo>
cd GPTInfernse

# Быстрая установка
make install

# Или используйте скрипт
./scripts/deploy.sh install
```

### 3. Проверка
```bash
# Проверьте статус
make status

# Проверьте API
curl http://localhost:8000/health

# Тестовый запрос
make chat-test
```

## Подробное развертывание

### Шаг 1: Настройка окружения

```bash
# Создайте .env файл
cp config.env.example .env

# Отредактируйте настройки
nano .env
```

Ключевые настройки:
```env
# Ollama URL (измените если Ollama на другом хосте)
OLLAMA_BASE_URL=http://localhost:11434

# Безопасность (ОБЯЗАТЕЛЬНО измените в production)
SECRET_KEY=your-very-secure-secret-key-here

# Rate limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# Логирование
LOG_LEVEL=INFO
DEBUG=false
```

### Шаг 2: Запуск сервисов

```bash
# Полная установка
make install

# Или пошагово:
make build    # Сборка образов
make start    # Запуск сервисов
```

### Шаг 3: Проверка работоспособности

```bash
# Статус всех сервисов
make status

# Логи
make logs

# Здоровье API
make health

# Список моделей
make api-models
```

## Архитектура развертывания

### Сервисы

| Сервис | Порт | Описание |
|--------|------|----------|
| API Server | 8000 | Основной FastAPI сервер |
| Redis | 6379 | Кеш и очередь задач |
| Flower | 5555 | Мониторинг Celery |
| Prometheus | 9090 | Сбор метрик |
| Grafana | 3000 | Дашборды |
| Nginx | 80/443 | Reverse proxy |

### Компоненты

```
┌─────────────────┐
│   Nginx Proxy   │ ← Входная точка
└─────────────────┘
         │
┌─────────────────┐
│   FastAPI API   │ ← Обработка запросов
└─────────────────┘
         │
┌─────────────────┐
│   Redis Queue   │ ← Очередь задач
└─────────────────┘
         │
┌─────────────────┐
│ Celery Workers  │ ← Обработка AI задач
└─────────────────┘
         │
┌─────────────────┐
│ Ollama Service  │ ← AI модели
└─────────────────┘
```

## Production развертывание

### 1. Подготовка сервера

```bash
# Обновите систему
sudo apt update && sudo apt upgrade -y

# Установите Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Добавьте пользователя в группу docker
sudo usermod -aG docker $USER

# Установите Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Настройка безопасности

```bash
# Создайте сильный секретный ключ
openssl rand -hex 32

# Настройте SSL сертификаты
mkdir -p docker/nginx/ssl
# Скопируйте ваши сертификаты в docker/nginx/ssl/
```

### 3. Production конфигурация

```env
# .env для production
DEBUG=false
LOG_LEVEL=INFO
SECRET_KEY=your-production-secret-key
API_WORKERS=8
RATE_LIMIT_PER_MINUTE=30
RATE_LIMIT_PER_HOUR=500
```

### 4. Запуск в production

```bash
# Production развертывание
make prod-deploy

# Проверка
make status
make health
```

## Мониторинг

### Веб-интерфейсы

```bash
# Открыть все интерфейсы мониторинга
make docs      # API документация
make flower    # Celery мониторинг
make grafana   # Дашборды
make prometheus # Метрики
```

### Ключевые метрики

- **API Response Time**: Время ответа API
- **Queue Length**: Длина очереди задач
- **Worker Status**: Статус воркеров
- **Model Usage**: Использование моделей
- **Error Rate**: Частота ошибок
- **Memory/CPU**: Использование ресурсов

### Алерты

Настройте алерты в Grafana для:
- Высокое время ответа (>30s)
- Длинная очередь (>100 задач)
- Недоступные воркеры
- Ошибки API (>5%)
- Высокое использование памяти (>80%)

## Масштабирование

### Горизонтальное масштабирование

```bash
# Увеличить количество воркеров
docker-compose up --scale worker=4

# Добавить больше API серверов
docker-compose up --scale api=2
```

### Вертикальное масштабирование

```yaml
# docker-compose.yml
services:
  worker:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### Балансировка нагрузки

```nginx
# nginx.conf
upstream api_backend {
    server api1:8000;
    server api2:8000;
    server api3:8000;
}
```

## Резервное копирование

### Автоматические бэкапы

```bash
# Создание бэкапа
make backup

# Настройка cron для ежедневных бэкапов
echo "0 2 * * * cd /path/to/GPTInfernse && make backup" | crontab -
```

### Восстановление

```bash
# Остановить сервисы
make stop

# Восстановить данные Redis
docker run --rm -v redis_data:/data -v $(pwd)/backup:/backup redis:7-alpine sh -c "cp /backup/dump.rdb /data/"

# Запустить сервисы
make start
```

## Обновление

### Обновление сервиса

```bash
# Автоматическое обновление (с бэкапом)
make update

# Или вручную:
make backup
git pull
make build
make restart
```

### Обновление моделей

```bash
# Установка новых моделей
ollama pull phi3
ollama pull gemma

# Обновление существующих
ollama pull llama3:latest
```

## Устранение неполадок

### Частые проблемы

1. **API не отвечает**
   ```bash
   make logs
   docker-compose restart api
   ```

2. **Воркеры не обрабатывают задачи**
   ```bash
   make flower  # Проверить в веб-интерфейсе
   docker-compose restart worker
   ```

3. **Ollama недоступен**
   ```bash
   curl http://localhost:11434/api/tags
   ollama serve
   ```

4. **Redis недоступен**
   ```bash
   docker-compose logs redis
   docker-compose restart redis
   ```

### Диагностика

```bash
# Проверка всех сервисов
make status

# Детальная диагностика
curl http://localhost:8000/health/detailed

# Логи в реальном времени
make logs-f

# Использование ресурсов
docker stats
```

### Производительность

```bash
# Мониторинг производительности
htop
iotop
nethogs

# Профилирование API
curl -w "@curl-format.txt" http://localhost:8000/health
```

## Безопасность

### Рекомендации

1. **Измените стандартные пароли**
2. **Используйте HTTPS в production**
3. **Настройте файрвол**
4. **Ограничьте доступ к мониторингу**
5. **Регулярно обновляйте зависимости**

### Настройка файрвола

```bash
# UFW (Ubuntu)
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable

# Закрыть прямой доступ к сервисам
sudo ufw deny 5555   # Flower
sudo ufw deny 9090   # Prometheus
sudo ufw deny 3000   # Grafana
```

## Поддержка

### Логи

```bash
# Все логи
make logs

# Конкретный сервис
docker-compose logs api
docker-compose logs worker
docker-compose logs redis
```

### Метрики

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Flower: http://localhost:5555

### Контакты

- Документация: `/docs`
- Issues: GitHub Issues
- Мониторинг: Grafana Dashboards

---

**GPTInfernse готов к работе! 🚀**
