# 🚀 Скрипты управления GPTInfernse

## Основные команды

### 🔄 Управление системой
```bash
# Полный перезапуск (рекомендуется)
./full_restart.sh

# Остановить все процессы
./kill_all.sh

# Посмотреть логи и диагностику
./debug_logs.sh

# Запуск через Docker
./docker_start.sh
```

### 📋 Makefile команды
```bash
# Показать все доступные команды
make help

# Быстрый запуск
make start

# Остановка
make stop

# Перезапуск
make restart

# Статус сервисов
make status

# Логи
make logs

# Тест API
make chat-test
```

## 🎯 Рекомендуемый workflow

1. **Первый запуск:**
   ```bash
   ./full_restart.sh
   ```

2. **Проверка статуса:**
   ```bash
   make status
   ```

3. **Если что-то не работает:**
   ```bash
   ./debug_logs.sh
   ```

4. **Остановка:**
   ```bash
   ./kill_all.sh
   ```

## 🌐 Ссылки после запуска

- **Интерфейс:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs  
- **Health Check:** http://localhost:8000/health/detailed

## 📁 Структура скриптов

- `full_restart.sh` - Полный перезапуск всей системы
- `kill_all.sh` - Остановка всех процессов
- `debug_logs.sh` - Диагностика и логи
- `docker_start.sh` - Запуск через Docker
- `Makefile` - Удобные команды для разработки
