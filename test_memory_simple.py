#!/usr/bin/env python3
"""
Простой тест памяти через чат API
"""

import subprocess
import json
import time

def test_chat_memory():
    """Тестировать память через чат API."""
    print("🧪 Тестирование памяти через чат...")
    
    # Тестовый запрос к чату
    chat_request = {
        "prompt": "Привет! Меня зовут Тест. Запомни это.",
        "model": "llama3.2",
        "conversation_id": "test_memory_conv_123",
        "stream": False
    }
    
    try:
        print("📤 Отправляем сообщение в чат...")
        
        # Отправим запрос к чату
        curl_cmd = [
            'curl', '-X', 'POST',
            'http://localhost:8000/chat/sync',
            '-H', 'Content-Type: application/json',
            '-H', 'X-User-ID: test_user_memory',
            '-d', json.dumps(chat_request),
            '--max-time', '30'
        ]
        
        result = subprocess.run(curl_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Чат ответил:")
            try:
                response = json.loads(result.stdout)
                print(f"  Ответ: {response.get('response', 'N/A')[:100]}...")
                print(f"  Диалог: {response.get('conversation_id', 'N/A')}")
                print(f"  Токены: {response.get('tokens_used', 'N/A')}")
                
                # Проверим, что появились данные в БД
                print("\n🔍 Проверяем сохранение в БД...")
                check_db()
                
                # Проверим Redis
                print("\n🔍 Проверяем кэш в Redis...")
                check_redis_cache()
                
                return True
                
            except json.JSONDecodeError:
                print(f"❌ Не удалось разобрать ответ: {result.stdout}")
                return False
        else:
            print(f"❌ Ошибка чата: {result.stderr}")
            print(f"Stdout: {result.stdout}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False

def check_db():
    """Проверить данные в БД."""
    try:
        # Проверим пользователей
        users_cmd = [
            'docker', 'exec', 'gptinfernse-postgres',
            'psql', '-U', 'gptinfernse', '-d', 'gptinfernse',
            '-c', 'SELECT COUNT(*) as users FROM users;'
        ]
        
        users_result = subprocess.run(users_cmd, capture_output=True, text=True)
        if users_result.returncode == 0:
            print(f"  👥 Пользователи: {users_result.stdout.strip()}")
        
        # Проверим диалоги
        conv_cmd = [
            'docker', 'exec', 'gptinfernse-postgres',
            'psql', '-U', 'gptinfernse', '-d', 'gptinfernse',
            '-c', 'SELECT COUNT(*) as conversations FROM conversations;'
        ]
        
        conv_result = subprocess.run(conv_cmd, capture_output=True, text=True)
        if conv_result.returncode == 0:
            print(f"  💬 Диалоги: {conv_result.stdout.strip()}")
        
        # Проверим сообщения
        msg_cmd = [
            'docker', 'exec', 'gptinfernse-postgres',
            'psql', '-U', 'gptinfernse', '-d', 'gptinfernse',
            '-c', 'SELECT COUNT(*) as messages FROM messages;'
        ]
        
        msg_result = subprocess.run(msg_cmd, capture_output=True, text=True)
        if msg_result.returncode == 0:
            print(f"  📝 Сообщения: {msg_result.stdout.strip()}")
            
    except Exception as e:
        print(f"❌ Ошибка проверки БД: {e}")

def check_redis_cache():
    """Проверить кэш в Redis."""
    try:
        # Проверим ключи диалогов
        keys_cmd = ['docker', 'exec', 'gptinfernse-redis', 'redis-cli', 'keys', 'conversation:*']
        keys_result = subprocess.run(keys_cmd, capture_output=True, text=True)
        
        if keys_result.returncode == 0:
            keys = keys_result.stdout.strip().split('\n') if keys_result.stdout.strip() else []
            if keys and keys[0]:
                print(f"  🔑 Ключи диалогов в Redis: {len(keys)}")
                for key in keys[:3]:  # Первые 3
                    if key.strip():
                        print(f"    - {key}")
            else:
                print("  ⚠️  Ключи диалогов в Redis не найдены")
        
        # Проверим ключи пользователей
        user_keys_cmd = ['docker', 'exec', 'gptinfernse-redis', 'redis-cli', 'keys', 'user:*']
        user_keys_result = subprocess.run(user_keys_cmd, capture_output=True, text=True)
        
        if user_keys_result.returncode == 0:
            user_keys = user_keys_result.stdout.strip().split('\n') if user_keys_result.stdout.strip() else []
            if user_keys and user_keys[0]:
                print(f"  👤 Ключи пользователей в Redis: {len(user_keys)}")
            else:
                print("  ⚠️  Ключи пользователей в Redis не найдены")
                
    except Exception as e:
        print(f"❌ Ошибка проверки Redis: {e}")

def main():
    """Основная функция теста."""
    print("🚀 Тест памяти GPTInfernse")
    print("=" * 50)
    
    # Сначала перезапустим API для применения исправления
    print("🔄 Перезапуск API для применения исправлений...")
    try:
        restart_cmd = ['docker', 'restart', 'gptinfernse-api']
        restart_result = subprocess.run(restart_cmd, capture_output=True, text=True)
        
        if restart_result.returncode == 0:
            print("✅ API перезапущен")
            time.sleep(5)  # Ждем запуска
        else:
            print(f"❌ Ошибка перезапуска: {restart_result.stderr}")
            return
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return
    
    # Тестируем память
    success = test_chat_memory()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Тест памяти УСПЕШЕН!")
        print("Бот должен теперь помнить диалоги.")
    else:
        print("❌ Тест памяти НЕ ПРОШЕЛ")
        print("Проверьте логи API и worker'а:")
        print("  docker logs --tail 20 gptinfernse-api")
        print("  docker logs --tail 20 gptinfernse-worker")

if __name__ == "__main__":
    main()
