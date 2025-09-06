#!/usr/bin/env python3
"""
Детальная диагностика памяти с проверкой логов ошибок
"""

import subprocess
import json
import re

def check_memory_errors_in_logs():
    """Найти ошибки памяти в логах."""
    print("🔍 Поиск ошибок памяти в логах...")
    
    containers = ['gptinfernse-api', 'gptinfernse-worker']
    
    for container in containers:
        print(f"\n📋 Анализ логов {container}:")
        try:
            # Получим больше логов для анализа
            cmd = ['docker', 'logs', '--tail', '100', container]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logs = result.stdout + result.stderr
                
                # Поиск ошибок памяти
                memory_errors = []
                database_errors = []
                redis_errors = []
                
                lines = logs.split('\n')
                for i, line in enumerate(lines):
                    line_lower = line.lower()
                    
                    # Ошибки памяти
                    if any(keyword in line_lower for keyword in ['memory', 'conversation', 'save', 'failed to save']):
                        if any(error_word in line_lower for error_word in ['error', 'failed', 'exception', 'traceback']):
                            memory_errors.append(f"Line {i}: {line}")
                    
                    # Ошибки БД
                    if any(keyword in line_lower for keyword in ['database', 'postgresql', 'asyncpg', 'connection']):
                        if any(error_word in line_lower for error_word in ['error', 'failed', 'exception']):
                            database_errors.append(f"Line {i}: {line}")
                    
                    # Ошибки Redis
                    if any(keyword in line_lower for keyword in ['redis', 'connection']):
                        if any(error_word in line_lower for error_word in ['error', 'failed', 'exception']):
                            redis_errors.append(f"Line {i}: {line}")
                
                # Вывод результатов
                if memory_errors:
                    print("❌ Ошибки памяти:")
                    for error in memory_errors[-5:]:  # Последние 5
                        print(f"  {error}")
                
                if database_errors:
                    print("❌ Ошибки БД:")
                    for error in database_errors[-3:]:  # Последние 3
                        print(f"  {error}")
                
                if redis_errors:
                    print("❌ Ошибки Redis:")
                    for error in redis_errors[-3:]:  # Последние 3
                        print(f"  {error}")
                
                if not memory_errors and not database_errors and not redis_errors:
                    print("✅ Критических ошибок не найдено")
                    
                    # Покажем последние сообщения о памяти
                    memory_logs = []
                    for i, line in enumerate(lines):
                        if any(keyword in line.lower() for keyword in ['memory', 'conversation', 'save']):
                            memory_logs.append(f"Line {i}: {line}")
                    
                    if memory_logs:
                        print("📋 Последние сообщения о памяти:")
                        for log in memory_logs[-3:]:
                            print(f"  {log}")
                
            else:
                print(f"❌ Не удалось получить логи: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Ошибка анализа логов: {e}")

def test_api_endpoints():
    """Протестировать API endpoints памяти."""
    print("\n🧪 Тестирование API endpoints...")
    
    # Тест health check памяти
    try:
        cmd = ['curl', '-s', 'http://localhost:8000/memory/health']
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("📡 Memory health check:")
            try:
                health_data = json.loads(result.stdout)
                print(f"  Status: {health_data.get('status', 'unknown')}")
                print(f"  Redis: {health_data.get('redis_connected', 'unknown')}")
            except:
                print(f"  Raw response: {result.stdout}")
        else:
            print(f"❌ Health check failed: {result.stderr}")
    
    except Exception as e:
        print(f"❌ Ошибка тестирования API: {e}")

def check_database_schema():
    """Проверить схему базы данных детально."""
    print("\n🔍 Детальная проверка схемы БД...")
    
    try:
        # Проверим все таблицы
        cmd = [
            'docker', 'exec', 'gptinfernse-postgres',
            'psql', '-U', 'gptinfernse', '-d', 'gptinfernse',
            '-c', """
            SELECT 
                schemaname,
                tablename,
                tableowner
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename;
            """
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("📊 Таблицы в базе данных:")
            print(result.stdout)
            
            # Проверим структуру ключевых таблиц
            key_tables = ['users', 'conversations', 'messages']
            
            for table in key_tables:
                print(f"\n🔍 Структура таблицы {table}:")
                struct_cmd = [
                    'docker', 'exec', 'gptinfernse-postgres',
                    'psql', '-U', 'gptinfernse', '-d', 'gptinfernse',
                    '-c', f'\\d {table}'
                ]
                
                struct_result = subprocess.run(struct_cmd, capture_output=True, text=True)
                if struct_result.returncode == 0:
                    print(struct_result.stdout)
                else:
                    print(f"❌ Таблица {table} не найдена или недоступна")
        
        else:
            print(f"❌ Ошибка проверки схемы: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def check_environment_variables():
    """Проверить переменные окружения в контейнерах."""
    print("\n🔍 Проверка переменных окружения...")
    
    containers = ['gptinfernse-api', 'gptinfernse-worker']
    important_vars = ['DATABASE_URL', 'REDIS_URL', 'REDIS_HOST']
    
    for container in containers:
        print(f"\n📋 Переменные в {container}:")
        
        for var in important_vars:
            try:
                cmd = ['docker', 'exec', container, 'printenv', var]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    value = result.stdout.strip()
                    # Скрыть пароли
                    if 'password' in value.lower():
                        value = re.sub(r':[^@]+@', ':***@', value)
                    print(f"  {var}: {value}")
                else:
                    print(f"  {var}: НЕ УСТАНОВЛЕНА")
                    
            except Exception as e:
                print(f"  {var}: Ошибка проверки - {e}")

def main():
    """Основная функция детальной диагностики."""
    print("🔬 Детальная диагностика памяти GPTInfernse")
    print("=" * 60)
    
    check_memory_errors_in_logs()
    test_api_endpoints()
    check_database_schema()
    check_environment_variables()
    
    print("\n" + "=" * 60)
    print("📋 РЕКОМЕНДАЦИИ:")
    print("1. Если найдены ошибки памяти - запустите fix_memory.py")
    print("2. Если таблицы отсутствуют - проверьте инициализацию БД")
    print("3. Если переменные окружения неверны - проверьте docker-compose.yml")
    print("4. Проверьте логи после каждого исправления")

if __name__ == "__main__":
    main()
