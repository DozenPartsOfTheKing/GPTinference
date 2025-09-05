# 🚀 GPTInfernse

**Твой собственный ChatGPT - приватный, быстрый, бесплатный!**

GPTInfernse - это полнофункциональный AI-ассистент, который работает локально на твоем компьютере. Никаких подписок, лимитов и утечек данных - только ты и твой персональный ChatGPT!

## 🎯 Быстрый старт (2 минуты)

```bash
# Скачай и запусти
git clone <твой-репозиторий>
cd GPTInfernse
./start_with_frontend.sh

# Открой в браузере
open http://localhost:3000
```

**Готово! Твой ChatGPT работает!** 🎉

> 📖 **Новичок?** Читай [подробную инструкцию для чайников](README_NOOB.md)

## ✨ Особенности

- 🔄 **Асинхронная обработка** - FastAPI + Celery для высокой производительности
- 🎯 **Масштабируемость** - Поддержка множественных воркеров и моделей
- 🛡️ **Rate Limiting** - Защита от перегрузки с Redis-based лимитами
- 📊 **Мониторинг** - Prometheus + Grafana + Flower для полного контроля
- 🐳 **Docker** - Полная контейнеризация для легкого развертывания
- 🔒 **Безопасность** - JWT аутентификация и защищенные эндпоинты
- 📈 **Производительность** - Connection pooling, кеширование, оптимизации

## 🏗️ Архитектура

```
┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐
│   Клиенты       │    │   Nginx Proxy    │    │    API Gateway     │
│ (Web/CLI/SDK)   │ ─> │   (Rate Limit)   │ ─> │    (FastAPI)       │
│                 │    │                  │    │                    │
└─────────────────┘    └──────────────────┘    └────────────────────┘
                                                         │
                                                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Task Queue (Redis)                              │
└─────────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Worker Pool (Celery)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   Worker 1  │  │   Worker 2  │  │   Worker 3  │  │   Worker N  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 Ollama Service                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │
│  │   LLaMA 3   │  │   Mistral   │  │  CodeLLaMA  │  ...             │
│  └─────────────┘  └─────────────┘  └─────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

## 🚀 Быстрый старт

### Предварительные требования

- Docker и Docker Compose
- Ollama (запущенный локально или в Docker)
- Python 3.11+ (для разработки)

### 1. Установка Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Запуск Ollama
ollama serve

# Установка моделей
ollama pull llama3
ollama pull mistral
ollama pull codellama
```

### 2. Развертывание GPTInfernse

```bash
# Клонирование проекта
git clone <repository-url>
cd GPTInfernse

# Быстрая установка
./scripts/deploy.sh install

# Или пошагово:
./scripts/deploy.sh start
```

### 3. Проверка работы

```bash
# Проверка здоровья сервиса
curl http://localhost:8000/health

# Список доступных моделей
curl http://localhost:8000/models/

# Тестовый запрос
curl -X POST http://localhost:8000/chat/sync \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Привет! Как дела?", "model": "llama3"}'
```

## 🔧 Конфигурация

### Переменные окружения

Скопируйте `config.env.example` в `.env` и настройте:

```bash
# Основные настройки
APP_NAME=GPTInfernse
DEBUG=false
LOG_LEVEL=INFO

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT=300

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# Безопасность
SECRET_KEY=your-secret-key-here
```

### Docker Compose профили

```bash
# Минимальная конфигурация
docker-compose up api worker redis

# Полная конфигурация с мониторингом
docker-compose --profile monitoring up

# Только для разработки
docker-compose --profile dev up
```

## 📡 API Документация

### Основные эндпоинты

#### Здоровье сервиса
```http
GET /health
GET /health/detailed
GET /health/ready
GET /health/live
```

#### Управление моделями
```http
GET /models/                    # Список моделей
GET /models/{model_name}        # Информация о модели
POST /models/pull              # Загрузка модели
GET /models/{model_name}/available  # Проверка доступности
```

#### Чат
```http
POST /chat/                    # Асинхронный чат (возвращает task_id)
POST /chat/sync               # Синхронный чат
GET /chat/task/{task_id}      # Статус задачи
DELETE /chat/task/{task_id}   # Отмена задачи
GET /chat/history/{conv_id}   # История разговора
GET /chat/stats               # Статистика пользователя
```

### Примеры запросов

#### Синхронный чат
```bash
curl -X POST http://localhost:8000/chat/sync \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Объясни квантовые вычисления простыми словами",
    "model": "llama3",
    "temperature": 0.7,
    "max_tokens": 500
  }'
```

#### Асинхронный чат
```bash
# Отправка задачи
TASK_ID=$(curl -X POST http://localhost:8000/chat/ \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Напиши план проекта", "model": "llama3"}' \
  | jq -r '.task_id')

# Проверка статуса
curl http://localhost:8000/chat/task/$TASK_ID
```

## 🖥️ Использование CLI клиента

```bash
# Установка зависимостей для клиента
pip install aiohttp click rich

# Интерактивный режим
python client_example.py interactive

# Проверка здоровья
python client_example.py health

# Список моделей
python client_example.py models

# Отправка сообщения
python client_example.py chat "Привет, как дела?"

# Синхронный режим
python client_example.py chat "Объясни Docker" --sync --model mistral
```

## 📊 Мониторинг и управление

### Веб-интерфейсы

- **API Docs**: http://localhost:8000/docs
- **Flower (Celery)**: http://localhost:5555 (admin/admin123)
- **Grafana**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9090

### Метрики

```bash
# Метрики Prometheus
curl http://localhost:8000/metrics

# Статус воркеров Celery
curl http://localhost:5555/api/workers

# Здоровье всех компонентов
curl http://localhost:8000/health/detailed
```

### Логи

```bash
# Просмотр логов
./scripts/deploy.sh logs

# Следование за логами
./scripts/deploy.sh logs-f

# Логи конкретного сервиса
docker-compose logs -f api
docker-compose logs -f worker
```

## 🛠️ Разработка

### Настройка среды разработки

```bash
# Настройка окружения
./scripts/dev.sh setup

# Запуск сервера разработки
./scripts/dev.sh dev

# Запуск воркера
./scripts/dev.sh worker

# Тестирование
./scripts/dev.sh test

# Форматирование кода
./scripts/dev.sh format

# Линтинг
./scripts/dev.sh lint
```

### Структура проекта

```
GPTInfernse/
├── app/                    # Основное приложение
│   ├── api/               # API слой
│   │   ├── routes/        # Маршруты API
│   │   └── dependencies.py # Зависимости FastAPI
│   ├── core/              # Ядро приложения
│   │   └── config.py      # Конфигурация
│   ├── models/            # Модели данных
│   ├── services/          # Бизнес-логика
│   ├── utils/             # Утилиты
│   ├── workers/           # Celery воркеры
│   └── main.py           # Точка входа
├── docker/               # Docker конфигурации
├── scripts/              # Скрипты управления
├── tests/                # Тесты
├── docker-compose.yml    # Оркестрация
├── Dockerfile           # Образ приложения
└── requirements.txt     # Зависимости Python
```

### Добавление новых функций

1. **Новый эндпоинт**:
   ```python
   # app/api/routes/new_feature.py
   from fastapi import APIRouter
   
   router = APIRouter(prefix="/new-feature", tags=["new-feature"])
   
   @router.get("/")
   async def new_endpoint():
       return {"message": "Hello from new feature"}
   ```

2. **Новый воркер**:
   ```python
   # app/workers/new_worker.py
   from ..utils.celery_app import celery_app
   
   @celery_app.task
   def new_task(data):
       # Обработка задачи
       return result
   ```

## 🔒 Безопасность

### Аутентификация

```python
# Настройка JWT токенов
from fastapi.security import HTTPBearer
from jose import JWTError, jwt

# В production замените на реальную аутентификацию
security = HTTPBearer()

async def get_current_user(token: str = Depends(security)):
    # Проверка токена
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload
```

### Rate Limiting

```python
# Настройка лимитов в .env
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# Кастомные лимиты для пользователей
await rate_limiter.check_rate_limit(
    key=f"user:{user_id}",
    limit=100,
    window_seconds=3600
)
```

## 📈 Производительность

### Оптимизации

1. **Connection Pooling**: Автоматическое управление соединениями
2. **Кеширование**: Redis для частых запросов
3. **Асинхронность**: FastAPI + aiohttp для высокой пропускной способности
4. **Очереди**: Celery для обработки тяжелых задач
5. **Мониторинг**: Prometheus метрики для отслеживания производительности

### Масштабирование

```bash
# Увеличение количества воркеров
docker-compose up --scale worker=4

# Настройка ресурсов
docker-compose.yml:
  worker:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

## 🚀 Развертывание в production

### 1. Подготовка

```bash
# Создание production .env
cp config.env.example .env
# Настройте переменные для production

# Генерация SSL сертификатов
mkdir -p docker/nginx/ssl
# Добавьте ваши сертификаты
```

### 2. Развертывание

```bash
# Production развертывание
DEBUG=false docker-compose up -d

# Проверка
./scripts/deploy.sh status
```

### 3. Резервное копирование

```bash
# Создание бэкапа
./scripts/deploy.sh backup

# Автоматические бэкапы (cron)
0 2 * * * /path/to/GPTInfernse/scripts/deploy.sh backup
```

## 🔧 Устранение неполадок

### Частые проблемы

1. **Ollama не отвечает**:
   ```bash
   # Проверка Ollama
   curl http://localhost:11434/api/tags
   
   # Перезапуск
   ollama serve
   ```

2. **Redis недоступен**:
   ```bash
   # Проверка Redis
   docker-compose logs redis
   
   # Перезапуск
   docker-compose restart redis
   ```

3. **Воркеры не обрабатывают задачи**:
   ```bash
   # Проверка воркеров
   docker-compose logs worker
   
   # Масштабирование
   docker-compose up --scale worker=2
   ```

### Логи и отладка

```bash
# Детальные логи
LOG_LEVEL=DEBUG docker-compose up

# Профилирование
python -m cProfile -o profile.stats app/main.py

# Мониторинг ресурсов
docker stats
```

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Создайте Pull Request

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл `LICENSE` для подробностей.

## 🙏 Благодарности

- [Ollama](https://ollama.ai/) - За отличный инструмент для запуска LLM
- [FastAPI](https://fastapi.tiangolo.com/) - За современный веб-фреймворк
- [Celery](https://docs.celeryq.dev/) - За мощную систему очередей задач
- [Redis](https://redis.io/) - За быстрое хранилище данных

---

**GPTInfernse** - Ваш собственный AI-ассистент корпоративного уровня! 🚀
# GPTinference
