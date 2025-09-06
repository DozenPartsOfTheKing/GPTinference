# 🪟 GPTInfernse для Windows

## 🚀 Быстрая установка для Windows

### Вариант 1: WSL2 (рекомендуется)

1. **Установите WSL2:**
   ```powershell
   # В PowerShell от администратора
   wsl --install
   # Перезагрузите компьютер
   ```

2. **Установите Docker Desktop:**
   - Скачайте с https://docker.com/products/docker-desktop
   - Включите WSL2 integration в настройках Docker Desktop

3. **Запустите в WSL2:**
   ```bash
   # В WSL2 терминале
   git clone <your-repo>
   cd GPTInfernse
   ./start
   ```

### Вариант 2: Нативный Windows

1. **Установите Docker Desktop для Windows**
2. **Установите Git for Windows**
3. **Запустите в PowerShell:**
   ```powershell
   git clone <your-repo>
   cd GPTInfernse
   
   # Запуск через Docker Compose
   docker compose up -d
   ```

## 🔧 Решение проблем

### "docker-compose не найден"
```bash
# Проверьте версию Docker
docker --version
docker compose version

# Если есть только docker compose (новая версия) - все будет работать
# Скрипты автоматически определят правильную команду
```

### WSL2 не видит Docker
1. Откройте Docker Desktop
2. Settings → Resources → WSL Integration
3. Включите интеграцию для вашего дистрибутива

### Медленная работа в WSL2
1. Убедитесь что проект находится в файловой системе WSL2 (`/home/user/`), а не в Windows (`/mnt/c/`)
2. Используйте `\\wsl$\Ubuntu\home\user\GPTInfernse` для доступа из Windows

## 🌐 Доступ к интерфейсу

После запуска откройте в браузере:
- **Главный интерфейс:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Мониторинг:** http://localhost:5555

## 💡 Советы для Windows

1. **Используйте WSL2** - работает быстрее чем нативный Windows
2. **Выделите больше памяти Docker** - в настройках Docker Desktop
3. **Отключите антивирус** для папки проекта (может замедлять)

## 🆘 Если ничего не работает

1. Перезапустите Docker Desktop
2. Перезапустите WSL2: `wsl --shutdown` и откройте заново
3. Проверьте что Docker запущен: `docker ps`
4. Используйте команды напрямую:
   ```bash
   docker compose up -d
   docker compose ps
   docker compose logs -f
   ```
