#!/usr/bin/env python3
"""
Простая диагностика памяти без внешних зависимостей
"""

import subprocess
import json
import sys

def check_containers():
    """Проверить статус контейнеров."""
    print("🔍 Проверка контейнеров...")
    
    try:
        result = subprocess.run(['docker', 'ps', '--format', 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Docker доступен")
            print("📊 Статус контейнеров:")
            print(result.stdout)
            
            # Проверим конкретные контейнеры
            containers = ['gptinfernse-postgres', 'gptinfernse-redis', 'gptinfernse-api', 'gptinfernse-worker']
            running_containers = result.stdout
            
            for container in containers:
                if container in running_containers:
                    print(f"✅ {container} - запущен")
                else:
                    print(f"❌ {container} - НЕ запущен")
            
            return True
        else:
            print(f"❌ Ошибка Docker: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка проверки контейнеров: {e}")
        return False

def check_postgres_simple():
    """Простая проверка PostgreSQL через docker exec."""
    print("\n🔍 Проверка PostgreSQL...")
    
    try:
        # Проверим подключение к PostgreSQL
        cmd = [
            'docker', 'exec', 'gptinfernse-postgres', 
            'psql', '-U', 'gptinfernse', '-d', 'gptinfernse', 
            '-c', 'SELECT COUNT(*) as users FROM users;'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ PostgreSQL подключение успешно")
            print("📊 Результат запроса:")
            print(result.stdout)
            return True
        else:
            print(f"❌ Ошибка PostgreSQL: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка проверки PostgreSQL: {e}")
        return False

def check_redis_simple():
    """Простая проверка Redis через docker exec."""
    print("\n🔍 Проверка Redis...")
    
    try:
        # Проверим подключение к Redis
        cmd = ['docker', 'exec', 'gptinfernse-redis', 'redis-cli', 'ping']
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and 'PONG' in result.stdout:
            print("✅ Redis подключение успешно")
            
            # Проверим ключи памяти
            keys_cmd = ['docker', 'exec', 'gptinfernse-redis', 'redis-cli', 'keys', '*']
            keys_result = subprocess.run(keys_cmd, capture_output=True, text=True)
            
            if keys_result.returncode == 0:
                keys = keys_result.stdout.strip().split('\n') if keys_result.stdout.strip() else []
                print(f"🔑 Найдено ключей в Redis: {len(keys)}")
                
                # Покажем примеры ключей
                if keys and keys[0]:  # Проверим что есть реальные ключи
                    print("📋 Примеры ключей:")
                    for key in keys[:5]:  # Первые 5 ключей
                        if key.strip():
                            print(f"  - {key}")
                else:
                    print("⚠️  Ключи не найдены - память пуста!")
                    
            return True
        else:
            print(f"❌ Ошибка Redis: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка проверки Redis: {e}")
        return False

def check_logs():
    """Проверить логи контейнеров."""
    print("\n🔍 Проверка логов...")
    
    containers = ['gptinfernse-api', 'gptinfernse-worker']
    
    for container in containers:
        print(f"\n📋 Последние логи {container}:")
        try:
            cmd = ['docker', 'logs', '--tail', '10', container]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(result.stdout[-500:])  # Последние 500 символов
                if result.stderr:
                    print("STDERR:", result.stderr[-200:])
            else:
                print(f"❌ Не удалось получить логи: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Ошибка получения логов: {e}")

def main():
    """Основная функция диагностики."""
    print("🚀 Простая диагностика GPTInfernse")
    print("=" * 50)
    
    containers_ok = check_containers()
    
    if containers_ok:
        postgres_ok = check_postgres_simple()
        redis_ok = check_redis_simple()
        check_logs()
        
        print("\n" + "=" * 50)
        print("📊 ИТОГИ ДИАГНОСТИКИ:")
        print(f"  Контейнеры: {'✅ OK' if containers_ok else '❌ FAIL'}")
        print(f"  PostgreSQL: {'✅ OK' if postgres_ok else '❌ FAIL'}")
        print(f"  Redis: {'✅ OK' if redis_ok else '❌ FAIL'}")
        
        if not postgres_ok or not redis_ok:
            print("\n⚠️  ВОЗМОЖНЫЕ ПРОБЛЕМЫ:")
            if not postgres_ok:
                print("  - База данных не инициализирована или недоступна")
            if not redis_ok:
                print("  - Redis недоступен или память пуста")
                print("  - Возможно, сообщения не сохраняются")
    else:
        print("\n❌ Контейнеры не запущены. Запустите: ./start")

if __name__ == "__main__":
    main()
