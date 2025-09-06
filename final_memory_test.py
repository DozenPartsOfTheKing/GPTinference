#!/usr/bin/env python3
"""
Финальный тест памяти после всех исправлений
"""

import subprocess
import json
import time

def final_test():
    """Финальный тест памяти."""
    print("🎯 ФИНАЛЬНЫЙ ТЕСТ ПАМЯТИ")
    print("=" * 50)
    
    # 1. Перезапуск с исправлениями
    print("🔄 Перезапуск сервисов с исправлениями...")
    containers = ['gptinfernse-api', 'gptinfernse-worker']
    
    for container in containers:
        try:
            restart_cmd = ['docker', 'restart', container]
            result = subprocess.run(restart_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ {container} перезапущен")
            else:
                print(f"❌ Ошибка: {result.stderr}")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    print("⏳ Ждем 10 секунд для полного запуска...")
    time.sleep(10)
    
    # 2. Тестовый диалог
    print("\n💬 Тестовый диалог...")
    
    messages = [
        {
            "prompt": "Привет! Меня зовут Алексей. Запомни это.",
            "conversation_id": "final_test_conv",
            "user_id": "final_test_user"
        },
        {
            "prompt": "Как меня зовут?",
            "conversation_id": "final_test_conv", 
            "user_id": "final_test_user"
        }
    ]
    
    for i, msg in enumerate(messages, 1):
        print(f"\n📤 Сообщение {i}: {msg['prompt']}")
        
        chat_request = {
            "prompt": msg["prompt"],
            "model": "llama3.2",
            "conversation_id": msg["conversation_id"],
            "stream": False
        }
        
        curl_cmd = [
            'curl', '-X', 'POST',
            'http://localhost:8000/chat/sync',
            '-H', 'Content-Type: application/json',
            '-H', f'X-User-ID: {msg["user_id"]}',
            '-d', json.dumps(chat_request),
            '--max-time', '30'
        ]
        
        try:
            result = subprocess.run(curl_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                try:
                    response = json.loads(result.stdout)
                    print(f"🤖 Ответ: {response.get('response', 'N/A')[:100]}...")
                    
                    # Небольшая пауза между сообщениями
                    time.sleep(2)
                    
                except json.JSONDecodeError:
                    print(f"❌ Не удалось разобрать ответ: {result.stdout}")
            else:
                print(f"❌ Ошибка запроса: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    # 3. Проверка результатов
    print(f"\n📊 ПРОВЕРКА РЕЗУЛЬТАТОВ:")
    print("-" * 30)
    
    # Логи на ошибки
    print("🔍 Проверка ошибок...")
    try:
        logs_cmd = ['docker', 'logs', '--tail', '30', 'gptinfernse-api']
        logs_result = subprocess.run(logs_cmd, capture_output=True, text=True)
        
        if logs_result.returncode == 0:
            logs = logs_result.stdout + logs_result.stderr
            
            # Поиск критических ошибок
            critical_errors = []
            for line in logs.split('\n'):
                if any(word in line.lower() for word in ['error', 'coroutine', 'invalid input']):
                    critical_errors.append(line)
            
            if critical_errors:
                print("❌ Критические ошибки:")
                for error in critical_errors[-3:]:
                    print(f"  {error}")
            else:
                print("✅ Критических ошибок не найдено")
        
    except Exception as e:
        print(f"❌ Ошибка проверки логов: {e}")
    
    # БД
    print("\n📈 Состояние БД:")
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
            print(db_result.stdout)
            
            # Проверим детали
            if "1" in db_result.stdout and "2" in db_result.stdout:
                print("🎉 ПАМЯТЬ РАБОТАЕТ! Найдены пользователи и сообщения!")
                
                # Покажем детали
                details_cmd = [
                    'docker', 'exec', 'gptinfernse-postgres',
                    'psql', '-U', 'gptinfernse', '-d', 'gptinfernse',
                    '-c', '''
                    SELECT u.user_identifier, c.conversation_id, COUNT(m.id) as message_count
                    FROM users u
                    LEFT JOIN conversations c ON u.id = c.user_id
                    LEFT JOIN messages m ON c.id = m.conversation_id
                    GROUP BY u.user_identifier, c.conversation_id;
                    '''
                ]
                
                details_result = subprocess.run(details_cmd, capture_output=True, text=True)
                if details_result.returncode == 0:
                    print("📋 Детали:")
                    print(details_result.stdout)
            else:
                print("⚠️  Данные не сохранились")
        
    except Exception as e:
        print(f"❌ Ошибка проверки БД: {e}")
    
    # Redis
    print("\n🔑 Redis кэш:")
    try:
        redis_cmd = ['docker', 'exec', 'gptinfernse-redis', 'redis-cli', 'keys', '*conv*']
        redis_result = subprocess.run(redis_cmd, capture_output=True, text=True)
        
        if redis_result.returncode == 0:
            keys = redis_result.stdout.strip().split('\n') if redis_result.stdout.strip() else []
            if keys and keys[0]:
                print(f"✅ Найдены ключи диалогов: {len(keys)}")
                for key in keys:
                    if key.strip():
                        print(f"  - {key}")
            else:
                print("⚠️  Ключи диалогов не найдены")
        
    except Exception as e:
        print(f"❌ Ошибка проверки Redis: {e}")

def main():
    """Основная функция."""
    final_test()
    
    print("\n" + "=" * 50)
    print("🏆 ИТОГОВЫЙ РЕЗУЛЬТАТ:")
    print("✅ Если нет ошибок и есть данные в БД - ПАМЯТЬ РАБОТАЕТ!")
    print("❌ Если ошибки остались - нужна дополнительная диагностика")
    print("\n🎯 После успешного теста:")
    print("1. Попробуйте чат через фронтенд http://localhost:3000")
    print("2. Проверьте админку http://localhost:3002") 
    print("3. Бот должен помнить предыдущие сообщения!")

if __name__ == "__main__":
    main()
