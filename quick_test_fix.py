#!/usr/bin/env python3
"""
Быстрый тест исправления проблемы с database_manager
"""

import subprocess
import json
import time

def test_fix():
    """Тестировать исправление."""
    print("🛠️  ТЕСТ ИСПРАВЛЕНИЯ DATABASE_MANAGER")
    print("=" * 50)
    
    # 1. Перезапустим API и Worker
    print("🔄 Перезапуск сервисов...")
    containers = ['gptinfernse-api', 'gptinfernse-worker']
    
    for container in containers:
        try:
            restart_cmd = ['docker', 'restart', container]
            result = subprocess.run(restart_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ {container} перезапущен")
            else:
                print(f"❌ Ошибка перезапуска {container}: {result.stderr}")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    print("⏳ Ждем 8 секунд для запуска...")
    time.sleep(8)
    
    # 2. Отправим тестовый запрос
    print("\n📤 Тестовый запрос...")
    
    chat_request = {
        "prompt": "Исправление: запомни код 777",
        "model": "llama3.2",
        "conversation_id": "fix_test_conv",
        "stream": False
    }
    
    curl_cmd = [
        'curl', '-X', 'POST',
        'http://localhost:8000/chat/sync',
        '-H', 'Content-Type: application/json',
        '-H', 'X-User-ID: fix_test_user',
        '-d', json.dumps(chat_request),
        '--max-time', '30'
    ]
    
    try:
        result = subprocess.run(curl_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            try:
                response = json.loads(result.stdout)
                print(f"✅ Чат ответил: {response.get('response', 'N/A')[:50]}...")
                print(f"📊 Диалог: {response.get('conversation_id', 'N/A')}")
            except:
                print(f"❌ Не удалось разобрать ответ: {result.stdout}")
        else:
            print(f"❌ Ошибка запроса: {result.stderr}")
    
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    # 3. Проверим логи на ошибки
    print(f"\n🔍 Проверка ошибок в логах...")
    
    try:
        logs_cmd = ['docker', 'logs', '--tail', '20', 'gptinfernse-api']
        logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)
        
        if logs_result.returncode == 0:
            logs = logs_result.stdout + logs_result.stderr
            
            # Поиск ошибок
            error_lines = []
            for line in logs.split('\n'):
                if any(word in line.lower() for word in ['error', 'coroutine', 'runtimewarning']):
                    error_lines.append(line)
            
            if error_lines:
                print("❌ Найдены ошибки:")
                for error in error_lines[-3:]:  # Последние 3
                    print(f"  {error}")
            else:
                print("✅ Критических ошибок не найдено")
        
    except Exception as e:
        print(f"❌ Ошибка проверки логов: {e}")
    
    # 4. Проверим состояние БД
    print(f"\n📊 Проверка БД...")
    
    try:
        db_cmd = [
            'docker', 'exec', 'gptinfernse-postgres',
            'psql', '-U', 'gptinfernse', '-d', 'gptinfernse',
            '-c', '''
            SELECT 
                (SELECT COUNT(*) FROM users) as users,
                (SELECT COUNT(*) FROM conversations) as conversations,
                (SELECT COUNT(*) FROM messages) as messages;
            '''
        ]
        
        db_result = subprocess.run(db_cmd, capture_output=True, text=True)
        
        if db_result.returncode == 0:
            print("📈 Состояние БД:")
            print(db_result.stdout)
            
            # Проверим, есть ли данные
            if "0" not in db_result.stdout or db_result.stdout.count("0") < 3:
                print("🎉 ДАННЫЕ НАЙДЕНЫ В БД!")
            else:
                print("⚠️  БД все еще пуста")
        
    except Exception as e:
        print(f"❌ Ошибка проверки БД: {e}")
    
    # 5. Проверим Redis
    print(f"\n🔑 Проверка Redis...")
    
    try:
        redis_cmd = ['docker', 'exec', 'gptinfernse-redis', 'redis-cli', 'keys', 'conversation:*']
        redis_result = subprocess.run(redis_cmd, capture_output=True, text=True)
        
        if redis_result.returncode == 0:
            keys = redis_result.stdout.strip().split('\n') if redis_result.stdout.strip() else []
            if keys and keys[0]:
                print(f"🎉 НАЙДЕНЫ КЛЮЧИ ДИАЛОГОВ: {len(keys)}")
                for key in keys[:3]:
                    if key.strip():
                        print(f"  - {key}")
            else:
                print("⚠️  Ключи диалогов не найдены")
        
    except Exception as e:
        print(f"❌ Ошибка проверки Redis: {e}")

def main():
    """Основная функция."""
    test_fix()
    
    print("\n" + "=" * 50)
    print("📋 РЕЗУЛЬТАТ:")
    print("Если нет ошибок 'coroutine' и есть данные в БД - ИСПРАВЛЕНО! ✅")
    print("Если ошибки остались - нужны дополнительные исправления ❌")

if __name__ == "__main__":
    main()
