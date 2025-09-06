#!/usr/bin/env python3
"""
Скрипт для исправления проблем с памятью GPTInfernse
"""

import subprocess
import sys

def init_database():
    """Инициализировать базу данных."""
    print("🔧 Инициализация базы данных...")
    
    try:
        # Проверим, созданы ли таблицы
        cmd = [
            'docker', 'exec', 'gptinfernse-postgres', 
            'psql', '-U', 'gptinfernse', '-d', 'gptinfernse', 
            '-c', "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            tables = result.stdout
            print("📊 Существующие таблицы:")
            print(tables)
            
            # Проверим основные таблицы
            required_tables = ['users', 'conversations', 'messages', 'system_memory']
            missing_tables = []
            
            for table in required_tables:
                if table not in tables:
                    missing_tables.append(table)
            
            if missing_tables:
                print(f"❌ Отсутствуют таблицы: {missing_tables}")
                print("🔧 Применяем схему базы данных...")
                
                # Применим схему
                schema_cmd = [
                    'docker', 'exec', '-i', 'gptinfernse-postgres',
                    'psql', '-U', 'gptinfernse', '-d', 'gptinfernse'
                ]
                
                with open('database/schema.sql', 'r') as f:
                    schema_sql = f.read()
                
                schema_result = subprocess.run(schema_cmd, input=schema_sql, text=True, capture_output=True)
                
                if schema_result.returncode == 0:
                    print("✅ Схема базы данных применена успешно")
                    return True
                else:
                    print(f"❌ Ошибка применения схемы: {schema_result.stderr}")
                    return False
            else:
                print("✅ Все необходимые таблицы существуют")
                return True
        else:
            print(f"❌ Ошибка проверки таблиц: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return False

def test_memory_save():
    """Тестировать сохранение в память через API."""
    print("\n🧪 Тестирование сохранения памяти...")
    
    try:
        # Тестовый запрос к API памяти
        import json
        
        test_message = {
            "id": "test_msg_123",
            "role": "user", 
            "content": "Тестовое сообщение для проверки памяти",
            "tokens": 10
        }
        
        curl_cmd = [
            'curl', '-X', 'POST',
            'http://localhost:8000/memory/conversation/test_conv_123/message',
            '-H', 'Content-Type: application/json',
            '-H', 'X-User-ID: test_user',
            '-d', json.dumps(test_message)
        ]
        
        result = subprocess.run(curl_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("📤 API запрос выполнен:")
            print(result.stdout)
            
            # Проверим, появились ли данные в БД
            check_cmd = [
                'docker', 'exec', 'gptinfernse-postgres',
                'psql', '-U', 'gptinfernse', '-d', 'gptinfernse',
                '-c', 'SELECT COUNT(*) FROM messages;'
            ]
            
            check_result = subprocess.run(check_cmd, capture_output=True, text=True)
            
            if check_result.returncode == 0:
                print("📊 Сообщения в БД:")
                print(check_result.stdout)
            
            return True
        else:
            print(f"❌ Ошибка API запроса: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False

def check_worker_logs():
    """Проверить детальные логи worker'а."""
    print("\n🔍 Проверка логов worker'а...")
    
    try:
        cmd = ['docker', 'logs', '--tail', '50', 'gptinfernse-worker']
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("📋 Логи worker'а:")
            print(result.stdout)
            if result.stderr:
                print("STDERR:")
                print(result.stderr)
        else:
            print(f"❌ Ошибка получения логов: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def restart_services():
    """Перезапустить сервисы для применения изменений."""
    print("\n🔄 Перезапуск сервисов...")
    
    try:
        # Перезапустим worker и api
        services = ['gptinfernse-worker', 'gptinfernse-api']
        
        for service in services:
            print(f"🔄 Перезапуск {service}...")
            restart_cmd = ['docker', 'restart', service]
            result = subprocess.run(restart_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ {service} перезапущен")
            else:
                print(f"❌ Ошибка перезапуска {service}: {result.stderr}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка перезапуска: {e}")
        return False

def main():
    """Основная функция исправления."""
    print("🛠️  Исправление проблем с памятью GPTInfernse")
    print("=" * 60)
    
    # 1. Инициализация БД
    db_ok = init_database()
    
    if db_ok:
        # 2. Перезапуск сервисов
        restart_ok = restart_services()
        
        if restart_ok:
            # 3. Тестирование
            test_ok = test_memory_save()
            
            # 4. Проверка логов
            check_worker_logs()
            
            print("\n" + "=" * 60)
            print("📊 РЕЗУЛЬТАТЫ ИСПРАВЛЕНИЯ:")
            print(f"  База данных: {'✅ OK' if db_ok else '❌ FAIL'}")
            print(f"  Перезапуск: {'✅ OK' if restart_ok else '❌ FAIL'}")
            print(f"  Тестирование: {'✅ OK' if test_ok else '❌ FAIL'}")
            
            if all([db_ok, restart_ok, test_ok]):
                print("\n🎉 Проблемы исправлены! Память должна работать.")
            else:
                print("\n⚠️  Некоторые проблемы остались. Проверьте логи выше.")
        else:
            print("\n❌ Не удалось перезапустить сервисы")
    else:
        print("\n❌ Не удалось инициализировать базу данных")

if __name__ == "__main__":
    main()
