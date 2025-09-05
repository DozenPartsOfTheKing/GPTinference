# 🔥 Полная перезагрузка GPTInfernse

## 🚀 Быстрый старт

### 1. Скопируй скрипты в свою рабочую директорию
```bash
cp /Users/masterpo/Documents/GPTInfernse/full_restart.sh ~/GPTinference/
cp /Users/masterpo/Documents/GPTInfernse/kill_all.sh ~/GPTinference/
chmod +x ~/GPTinference/full_restart.sh
chmod +x ~/GPTinference/kill_all.sh
```

### 2. Полная перезагрузка системы
```bash
cd ~/GPTinference

# Останови все процессы
./kill_all.sh

# Запусти все заново
./full_restart.sh
```

### 3. Открой в браузере
**http://localhost:3000**

## 🛠️ Что делают скрипты

### `kill_all.sh` - Убивает все процессы
- ❌ Останавливает API сервер (uvicorn)
- ❌ Останавливает фронтенд (python server)
- ❌ Останавливает Celery worker
- ❌ Освобождает порты 8000, 3000, 6379, 5555
- ❌ Останавливает Docker контейнеры (Ollama)
- ❌ Останавливает Redis

### `full_restart.sh` - Запускает все с нуля
- ✅ Проверяет зависимости (Python, Docker, venv)
- ✅ Запускает Ollama в Docker
- ✅ Устанавливает модели (llama3, mistral)
- ✅ Запускает Redis
- ✅ Устанавливает Python зависимости
- ✅ Запускает API сервер на порту 8000
- ✅ Запускает Celery worker
- ✅ Запускает фронтенд на порту 3000
- ✅ Проверяет работу всех сервисов

## 🎯 Результат

После выполнения скриптов у тебя будет:

```
✅ Ollama (localhost:11434)
✅ API Server (localhost:8000)  
✅ Frontend (localhost:3000)

🎉 ВСЕ СЕРВИСЫ ЗАПУЩЕНЫ УСПЕШНО!

🔗 Полезные ссылки:
  🌐 Интерфейс: http://localhost:3000
  📚 API Docs: http://localhost:8000/docs
  🏥 Health: http://localhost:8000/health/detailed
```

## 🔍 Диагностика

### Если что-то не работает:
```bash
# Проверь логи
tail -f logs/api.log
tail -f logs/worker.log
tail -f logs/frontend.log

# Проверь процессы
ps aux | grep -E "(uvicorn|python.*server|celery)"

# Проверь порты
lsof -i :8000
lsof -i :3000
lsof -i :11434

# Проверь Docker
docker ps
```

### Ручная проверка сервисов:
```bash
# Ollama
curl http://localhost:11434/api/tags

# API
curl http://localhost:8000/health/detailed

# Фронтенд
curl http://localhost:3000

# Тест чата
curl -X POST http://localhost:8000/chat/sync \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Привет!", "model": "llama3"}'
```

## 🎨 Особенности нового интерфейса

После перезапуска ты получишь:

- 🎨 **Светлую тему** с графитовыми акцентами по умолчанию
- 🌙 **Кнопку переключения темы** в заголовке
- 🔧 **Улучшенную обработку ошибок** с конкретными решениями
- 🚀 **Автоматическое переподключение** при сбоях
- 💬 **Современный дизайн** в стиле ChatGPT

## 🆘 Если ничего не помогает

### Экстренная очистка:
```bash
# Убей все Python процессы
sudo pkill -f python

# Убей все процессы на портах
sudo lsof -ti:8000,3000,11434 | xargs kill -9

# Останови все Docker контейнеры
docker stop $(docker ps -q)

# Перезапусти Docker
sudo systemctl restart docker

# Запусти заново
./full_restart.sh
```

### Полная переустановка:
```bash
# Удали виртуальное окружение
rm -rf venv

# Создай заново
python3 -m venv venv
source venv/bin/activate

# Установи зависимости
pip install -r requirements.txt

# Запусти
./full_restart.sh
```

---

**Эти скрипты решат все проблемы с запуском!** 🚀
