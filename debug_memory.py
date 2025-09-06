#!/usr/bin/env python3
"""
Диагностический скрипт для проверки системы памяти GPTInfernse
"""

import asyncio
import asyncpg
import redis.asyncio as redis
import json
import sys
from datetime import datetime


async def check_postgres():
    """Проверить подключение к PostgreSQL и состояние данных."""
    print("🔍 Проверка PostgreSQL...")
    
    try:
        # Подключение к базе данных
        conn = await asyncpg.connect(
            "postgresql://gptinfernse:gptinfernse_password@localhost:5432/gptinfernse"
        )
        print("✅ Подключение к PostgreSQL успешно")
        
        # Проверка таблиц
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        print(f"📊 Найдено таблиц: {len(tables)}")
        for table in tables:
            print(f"  - {table['table_name']}")
        
        # Проверка данных
        print("\n📈 Статистика данных:")
        
        # Пользователи
        user_count = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
        print(f"  👥 Активных пользователей: {user_count}")
        
        # Диалоги
        conv_count = await conn.fetchval("SELECT COUNT(*) FROM conversations WHERE is_active = TRUE")
        print(f"  💬 Активных диалогов: {conv_count}")
        
        # Сообщения
        msg_count = await conn.fetchval("SELECT COUNT(*) FROM messages")
        print(f"  📝 Всего сообщений: {msg_count}")
        
        # Последние диалоги
        recent_convs = await conn.fetch("""
            SELECT conversation_id, user_identifier, message_count, created_at, updated_at
            FROM conversations c
            LEFT JOIN users u ON c.user_id = u.id
            WHERE c.is_active = TRUE
            ORDER BY c.updated_at DESC
            LIMIT 5
        """)
        
        if recent_convs:
            print("\n🕒 Последние диалоги:")
            for conv in recent_convs:
                print(f"  - {conv['conversation_id'][:8]}... | {conv['user_identifier']} | {conv['message_count']} сообщений | {conv['updated_at']}")
        else:
            print("\n❌ Диалоги не найдены!")
        
        # Последние сообщения
        recent_msgs = await conn.fetch("""
            SELECT m.message_id, m.role, LEFT(m.content, 50) as content_preview, 
                   m.created_at, c.conversation_id
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            ORDER BY m.created_at DESC
            LIMIT 5
        """)
        
        if recent_msgs:
            print("\n💬 Последние сообщения:")
            for msg in recent_msgs:
                print(f"  - {msg['role']}: {msg['content_preview']}... | {msg['created_at']}")
        else:
            print("\n❌ Сообщения не найдены!")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка PostgreSQL: {e}")
        return False


async def check_redis():
    """Проверить подключение к Redis и кэш."""
    print("\n🔍 Проверка Redis...")
    
    try:
        # Подключение к Redis
        redis_client = redis.from_url(
            "redis://localhost:6379/0",
            encoding="utf-8",
            decode_responses=True
        )
        
        # Проверка подключения
        await redis_client.ping()
        print("✅ Подключение к Redis успешно")
        
        # Информация о памяти
        info = await redis_client.info("memory")
        memory_mb = info.get("used_memory", 0) / (1024 * 1024)
        print(f"💾 Использование памяти Redis: {memory_mb:.2f} MB")
        
        # Поиск ключей памяти
        conversation_keys = await redis_client.keys("memory:conversation:*")
        user_keys = await redis_client.keys("memory:user:*")
        system_keys = await redis_client.keys("memory:system:*")
        
        print(f"🔑 Ключи в Redis:")
        print(f"  - Диалоги: {len(conversation_keys)}")
        print(f"  - Пользователи: {len(user_keys)}")
        print(f"  - Системные: {len(system_keys)}")
        
        # Новые ключи (hybrid manager)
        hybrid_conv_keys = await redis_client.keys("conversation:*")
        hybrid_user_keys = await redis_client.keys("user:*")
        
        print(f"🔑 Гибридные ключи:")
        print(f"  - Диалоги: {len(hybrid_conv_keys)}")
        print(f"  - Пользователи: {len(hybrid_user_keys)}")
        
        # Показать примеры данных
        if hybrid_conv_keys:
            print("\n📋 Пример данных диалога:")
            sample_key = hybrid_conv_keys[0]
            data = await redis_client.get(sample_key)
            if data:
                try:
                    parsed = json.loads(data)
                    print(f"  Ключ: {sample_key}")
                    print(f"  ID диалога: {parsed.get('conversation_id', 'N/A')}")
                    print(f"  Пользователь: {parsed.get('user_id', 'N/A')}")
                    print(f"  Сообщений: {len(parsed.get('messages', []))}")
                except:
                    print(f"  Ключ: {sample_key} (не удалось разобрать)")
        
        await redis_client.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка Redis: {e}")
        return False


async def check_memory_integration():
    """Проверить интеграцию системы памяти."""
    print("\n🔍 Проверка интеграции памяти...")
    
    try:
        # Импорт менеджера памяти
        sys.path.append('/Users/masterpo/Documents/GPTInfernse')
        from app.services.hybrid_memory_manager import get_hybrid_memory_manager
        from app.models.memory import ConversationMessage
        
        memory_manager = get_hybrid_memory_manager()
        
        # Тестовое сохранение
        test_conversation_id = f"test_conv_{int(datetime.now().timestamp())}"
        test_user_id = "test_user"
        
        test_message = ConversationMessage(
            id="test_msg_1",
            role="user",
            content="Тестовое сообщение для проверки памяти",
            tokens=10
        )
        
        print(f"💾 Тестовое сохранение сообщения...")
        success = await memory_manager.save_conversation_message(
            conversation_id=test_conversation_id,
            message=test_message,
            user_id=test_user_id,
            ttl_hours=1
        )
        
        if success:
            print("✅ Тестовое сохранение успешно")
            
            # Попытка получить сообщение
            conversation = await memory_manager.get_conversation_memory(test_conversation_id)
            if conversation:
                print(f"✅ Тестовое получение успешно: {len(conversation.messages)} сообщений")
            else:
                print("❌ Не удалось получить сохраненный диалог")
        else:
            print("❌ Тестовое сохранение не удалось")
        
        await memory_manager.close()
        return success
        
    except Exception as e:
        print(f"❌ Ошибка интеграции памяти: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Основная функция диагностики."""
    print("🚀 Диагностика системы памяти GPTInfernse")
    print("=" * 50)
    
    postgres_ok = await check_postgres()
    redis_ok = await check_redis()
    integration_ok = await check_memory_integration()
    
    print("\n" + "=" * 50)
    print("📊 ИТОГИ ДИАГНОСТИКИ:")
    print(f"  PostgreSQL: {'✅ OK' if postgres_ok else '❌ FAIL'}")
    print(f"  Redis: {'✅ OK' if redis_ok else '❌ FAIL'}")
    print(f"  Интеграция: {'✅ OK' if integration_ok else '❌ FAIL'}")
    
    if not all([postgres_ok, redis_ok, integration_ok]):
        print("\n⚠️  ОБНАРУЖЕНЫ ПРОБЛЕМЫ!")
        if not postgres_ok:
            print("  - Проверьте подключение к PostgreSQL")
        if not redis_ok:
            print("  - Проверьте подключение к Redis")
        if not integration_ok:
            print("  - Проверьте конфигурацию системы памяти")
    else:
        print("\n🎉 Все системы работают корректно!")


if __name__ == "__main__":
    asyncio.run(main())
