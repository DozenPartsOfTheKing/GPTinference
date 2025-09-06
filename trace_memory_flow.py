#!/usr/bin/env python3
"""
Детальный трейсинг потока сохранения памяти
"""

import subprocess
import json
import time

def get_detailed_logs(container, lines=50):
    """Получить детальные логи контейнера."""
    try:
        cmd = ['docker', 'logs', '--tail', str(lines), container]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return result.stdout + "\n" + result.stderr
        else:
            return f"Error getting logs: {result.stderr}"
    except Exception as e:
        return f"Exception: {e}"

def trace_chat_request():
    """Отследить полный путь чат-запроса."""
    print("🔍 ТРЕЙСИНГ ПОЛНОГО ПУТИ СОХРАНЕНИЯ ПАМЯТИ")
    print("=" * 60)
    
    # 1. Очистим логи (перезапустим контейнеры для чистых логов)
    print("🔄 Перезапуск контейнеров для чистых логов...")
    containers = ['gptinfernse-api', 'gptinfernse-worker']
    
    for container in containers:
        try:
            restart_cmd = ['docker', 'restart', container]
            subprocess.run(restart_cmd, capture_output=True, text=True)
            print(f"✅ {container} перезапущен")
        except Exception as e:
            print(f"❌ Ошибка перезапуска {container}: {e}")
    
    print("⏳ Ждем 10 секунд для полного запуска...")
    time.sleep(10)
    
    # 2. Отправим тестовый запрос
    print("\n📤 Отправляем тестовый запрос...")
    
    chat_request = {
        "prompt": "Тест памяти: запомни число 12345",
        "model": "llama3.2",
        "conversation_id": "trace_conv_999",
        "stream": False
    }
    
    curl_cmd = [
        'curl', '-X', 'POST',
        'http://localhost:8000/chat/sync',
        '-H', 'Content-Type: application/json',
        '-H', 'X-User-ID: trace_user_999',
        '-d', json.dumps(chat_request),
        '--max-time', '60',
        '-v'  # Verbose для детальной информации
    ]
    
    print(f"Команда: {' '.join(curl_cmd)}")
    
    try:
        result = subprocess.run(curl_cmd, capture_output=True, text=True)
        
        print(f"\n📊 Результат запроса:")
        print(f"Return code: {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        
        if result.returncode == 0:
            try:
                response = json.loads(result.stdout)
                print(f"\n✅ Чат ответил:")
                print(f"  Ответ: {response.get('response', 'N/A')[:100]}...")
                print(f"  Диалог: {response.get('conversation_id', 'N/A')}")
                print(f"  Время: {response.get('processing_time', 'N/A')}")
            except:
                print("❌ Не удалось разобрать JSON ответ")
        
    except Exception as e:
        print(f"❌ Ошибка выполнения запроса: {e}")
    
    # 3. Немедленно проверим логи
    print(f"\n🔍 ЛОГИ API (сразу после запроса):")
    print("-" * 40)
    api_logs = get_detailed_logs('gptinfernse-api', 30)
    print(api_logs)
    
    print(f"\n🔍 ЛОГИ WORKER (сразу после запроса):")
    print("-" * 40)
    worker_logs = get_detailed_logs('gptinfernse-worker', 30)
    print(worker_logs)
    
    # 4. Проверим состояние БД и Redis
    print(f"\n📊 СОСТОЯНИЕ ПОСЛЕ ЗАПРОСА:")
    print("-" * 40)
    
    # БД
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
        print(f"БД состояние: {db_result.stdout}")
        
    except Exception as e:
        print(f"❌ Ошибка проверки БД: {e}")
    
    # Redis
    try:
        redis_cmd = ['docker', 'exec', 'gptinfernse-redis', 'redis-cli', 'keys', '*']
        redis_result = subprocess.run(redis_cmd, capture_output=True, text=True)
        
        if redis_result.returncode == 0:
            keys = redis_result.stdout.strip().split('\n') if redis_result.stdout.strip() else []
            print(f"Redis ключи ({len(keys)}):")
            for key in keys[:10]:  # Первые 10
                if key.strip():
                    print(f"  - {key}")
        
    except Exception as e:
        print(f"❌ Ошибка проверки Redis: {e}")

def analyze_memory_flow():
    """Анализировать поток сохранения памяти в коде."""
    print(f"\n🔬 АНАЛИЗ ПОТОКА ПАМЯТИ В КОДЕ:")
    print("-" * 40)
    
    # Проверим, вызывается ли функция сохранения
    print("🔍 Поиск вызовов сохранения памяти в логах...")
    
    containers = ['gptinfernse-api', 'gptinfernse-worker']
    
    for container in containers:
        print(f"\n📋 Анализ логов {container}:")
        logs = get_detailed_logs(container, 100)
        
        # Поиск ключевых фраз
        memory_keywords = [
            'save_conversation_message',
            'Saving conversation to memory',
            'Failed to save conversation',
            'Memory manager',
            'database_manager',
            'hybrid_memory_manager'
        ]
        
        found_memory_logs = []
        lines = logs.split('\n')
        
        for i, line in enumerate(lines):
            for keyword in memory_keywords:
                if keyword.lower() in line.lower():
                    found_memory_logs.append(f"Line {i}: {line}")
        
        if found_memory_logs:
            print("  🔍 Найдены упоминания памяти:")
            for log in found_memory_logs[-5:]:  # Последние 5
                print(f"    {log}")
        else:
            print("  ❌ Упоминания памяти НЕ НАЙДЕНЫ!")
        
        # Поиск ошибок
        error_lines = []
        for i, line in enumerate(lines):
            if any(word in line.lower() for word in ['error', 'exception', 'traceback', 'failed']):
                error_lines.append(f"Line {i}: {line}")
        
        if error_lines:
            print("  ❌ Найдены ошибки:")
            for error in error_lines[-3:]:  # Последние 3
                print(f"    {error}")

def main():
    """Основная функция трейсинга."""
    print("🚀 ДЕТАЛЬНЫЙ ТРЕЙСИНГ ПАМЯТИ GPTInfernse")
    print("=" * 60)
    
    # Трейсим полный путь
    trace_chat_request()
    
    # Анализируем поток
    analyze_memory_flow()
    
    print("\n" + "=" * 60)
    print("📋 ВЫВОДЫ:")
    print("1. Если в логах НЕТ упоминаний 'save_conversation_message' - функция не вызывается")
    print("2. Если есть ошибки с 'database' или 'redis' - проблема с подключением")
    print("3. Если есть 'Failed to save' - ошибка в процессе сохранения")
    print("4. Проверьте, что worker обрабатывает задачи от API")

if __name__ == "__main__":
    main()
