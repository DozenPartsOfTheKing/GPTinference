"""Hybrid memory manager using PostgreSQL + Redis."""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from ..core.config import get_settings
from ..models.memory import (
    ConversationMemory,
    ConversationMessage,
    MemoryQuery,
    MemoryStats,
    UserMemory,
)
from .database_manager import get_database_manager

logger = logging.getLogger(__name__)


class HybridMemoryManager:
    """
    Hybrid memory manager using PostgreSQL for persistence and Redis for caching.
    
    Strategy:
    - PostgreSQL: Long-term storage, complex queries, relationships
    - Redis: Fast access, session data, temporary cache
    """
    
    def __init__(self):
        """Initialize hybrid memory manager."""
        self.redis: Optional[Redis] = None
        self.settings = get_settings()
        
        # Cache TTL settings
        self.CONVERSATION_CACHE_TTL = 3600  # 1 hour
        self.USER_CACHE_TTL = 1800  # 30 minutes
        self.STATS_CACHE_TTL = 300  # 5 minutes
    
    async def _get_redis(self) -> Redis:
        """Get Redis connection."""
        if self.redis is None:
            self.redis = redis.from_url(
                self.settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self.redis
    
    async def close(self):
        """Close connections."""
        if self.redis:
            await self.redis.close()
    
    # Conversation Management
    
    async def save_conversation_message(
        self,
        conversation_id: str,
        message: ConversationMessage,
        user_id: Optional[str] = None,
        ttl_hours: Optional[int] = None
    ) -> bool:
        """Save message to conversation (PostgreSQL + Redis cache)."""
        try:
            db = await get_database_manager()
            
            # Ensure conversation exists in PostgreSQL
            conversation = await db.get_conversation(conversation_id, include_messages=False)
            if not conversation:
                # Create conversation
                await db.create_conversation(
                    conversation_id=conversation_id,
                    user_identifier=user_id or "anonymous",
                    ttl_hours=ttl_hours or 24 * 7  # 7 days default
                )
            
            # Save message to PostgreSQL
            success = await db.add_message(
                conversation_id=conversation_id,
                message_id=message.id,
                role=message.role,
                content=message.content,
                tokens=message.tokens,
                model=message.model,
                metadata=message.metadata
            )
            
            if success:
                # Invalidate Redis cache for this conversation
                redis_client = await self._get_redis()
                cache_key = f"conversation:{conversation_id}"
                await redis_client.delete(cache_key)
                
                # Update user facts if it's a user message
                if message.role == "user" and user_id:
                    await self._extract_and_save_user_facts(user_id, message.content)
                
                logger.info(f"Saved message to conversation {conversation_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error saving conversation message: {e}")
            return False
    
    async def get_conversation_memory(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> Optional[ConversationMemory]:
        """Get conversation memory (Redis cache first, then PostgreSQL)."""
        try:
            redis_client = await self._get_redis()
            cache_key = f"conversation:{conversation_id}"
            
            # Try Redis cache first
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                try:
                    data = json.loads(cached_data)
                    conversation = ConversationMemory(**data)
                    
                    # Apply limit if requested
                    if limit and len(conversation.messages) > limit:
                        conversation.messages = conversation.messages[-limit:]
                    
                    logger.debug(f"Retrieved conversation {conversation_id} from cache")
                    return conversation
                except Exception as e:
                    logger.warning(f"Failed to parse cached conversation: {e}")
            
            # Fallback to PostgreSQL
            db = await get_database_manager()
            conversation_data = await db.get_conversation(
                conversation_id, 
                include_messages=True,
                message_limit=limit
            )
            
            if not conversation_data:
                return None
            
            # Convert to ConversationMemory model
            messages = []
            if 'messages' in conversation_data:
                for msg_data in conversation_data['messages']:
                    message = ConversationMessage(
                        id=msg_data['message_id'],
                        role=msg_data['role'],
                        content=msg_data['content'],
                        timestamp=msg_data['created_at'],
                        tokens=msg_data['tokens'],
                        model=msg_data['model'],
                        metadata=msg_data['metadata']
                    )
                    messages.append(message)
            
            # Extract topics from messages (simple keyword extraction)
            topics = self._extract_topics_from_messages(messages)
            
            conversation = ConversationMemory(
                conversation_id=conversation_data['conversation_id'],
                user_id=conversation_data['user_identifier'],
                messages=messages,
                topics=topics,
                created_at=conversation_data['created_at'],
                updated_at=conversation_data['updated_at'],
                total_tokens=conversation_data['total_tokens'] or 0,
                message_count=conversation_data['message_count'] or 0
            )
            
            # Cache in Redis for future requests
            try:
                await redis_client.setex(
                    cache_key,
                    self.CONVERSATION_CACHE_TTL,
                    conversation.json()
                )
            except Exception as e:
                logger.warning(f"Failed to cache conversation: {e}")
            
            logger.debug(f"Retrieved conversation {conversation_id} from database")
            return conversation
            
        except Exception as e:
            logger.error(f"Error getting conversation memory: {e}")
            return None
    
    async def delete_conversation_memory(self, conversation_id: str) -> bool:
        """Delete conversation memory."""
        try:
            db = await get_database_manager()
            
            # Soft delete in PostgreSQL
            async with db.get_connection() as conn:
                result = await conn.execute(
                    "UPDATE conversations SET is_active = FALSE WHERE conversation_id = $1",
                    conversation_id
                )
                
                # Clear Redis cache
                redis_client = await self._get_redis()
                cache_key = f"conversation:{conversation_id}"
                await redis_client.delete(cache_key)
                
                return result != "UPDATE 0"
                
        except Exception as e:
            logger.error(f"Error deleting conversation: {e}")
            return False
    
    # User Management
    
    async def get_user_memory(self, user_id: str) -> Optional[UserMemory]:
        """Get user memory (Redis cache first, then PostgreSQL)."""
        try:
            redis_client = await self._get_redis()
            cache_key = f"user:{user_id}"
            
            # Try Redis cache first
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                try:
                    data = json.loads(cached_data)
                    user_memory = UserMemory(**data)
                    logger.debug(f"Retrieved user {user_id} from cache")
                    return user_memory
                except Exception as e:
                    logger.warning(f"Failed to parse cached user: {e}")
            
            # Fallback to PostgreSQL
            db = await get_database_manager()
            user_data = await db.get_or_create_user(user_id)
            
            # Get recent conversation IDs
            async with db.get_connection() as conn:
                conversations = await conn.fetch(
                    """
                    SELECT conversation_id FROM conversations 
                    WHERE user_id = $1 AND is_active = TRUE
                    ORDER BY updated_at DESC LIMIT 10
                    """,
                    user_data['id']
                )
                conversation_history = [conv['conversation_id'] for conv in conversations]
            
            user_memory = UserMemory(
                user_id=user_id,
                preferences=user_data['preferences'] or {},
                facts=user_data['facts'] or [],
                conversation_history=conversation_history,
                created_at=user_data['created_at'],
                updated_at=user_data['updated_at'],
                last_active=user_data['last_active']
            )
            
            # Cache in Redis
            try:
                await redis_client.setex(
                    cache_key,
                    self.USER_CACHE_TTL,
                    user_memory.json()
                )
            except Exception as e:
                logger.warning(f"Failed to cache user: {e}")
            
            logger.debug(f"Retrieved user {user_id} from database")
            return user_memory
            
        except Exception as e:
            logger.error(f"Error getting user memory: {e}")
            return UserMemory(user_id=user_id)
    
    async def update_user_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """Update user preferences."""
        try:
            db = await get_database_manager()
            success = await db.update_user_preferences(user_id, preferences)
            
            if success:
                # Invalidate Redis cache
                redis_client = await self._get_redis()
                cache_key = f"user:{user_id}"
                await redis_client.delete(cache_key)
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
            return False
    
    async def add_user_fact(self, user_id: str, fact: str) -> bool:
        """Add fact about user."""
        try:
            db = await get_database_manager()
            success = await db.add_user_fact(user_id, fact)
            
            if success:
                # Invalidate Redis cache
                redis_client = await self._get_redis()
                cache_key = f"user:{user_id}"
                await redis_client.delete(cache_key)
            
            return success
            
        except Exception as e:
            logger.error(f"Error adding user fact: {e}")
            return False
    
    # System Memory
    
    async def get_system_memory(self, key: str) -> Optional[Any]:
        """Get system memory value."""
        try:
            db = await get_database_manager()
            return await db.get_system_memory(key)
        except Exception as e:
            logger.error(f"Error getting system memory: {e}")
            return None
    
    async def set_system_memory(
        self,
        key: str,
        value: Any,
        memory_type: str = 'system_facts',
        ttl_hours: Optional[int] = None
    ) -> bool:
        """Set system memory value."""
        try:
            db = await get_database_manager()
            return await db.set_system_memory(
                key=key,
                value=value,
                memory_type=memory_type,
                ttl_hours=ttl_hours
            )
        except Exception as e:
            logger.error(f"Error setting system memory: {e}")
            return False
    
    # Statistics
    
    async def get_memory_stats(self) -> MemoryStats:
        """Get memory statistics (cached)."""
        try:
            redis_client = await self._get_redis()
            cache_key = "memory:stats"
            
            # Try cache first
            cached_stats = await redis_client.get(cache_key)
            if cached_stats:
                try:
                    data = json.loads(cached_stats)
                    return MemoryStats(**data)
                except Exception as e:
                    logger.warning(f"Failed to parse cached stats: {e}")
            
            # Get fresh stats from PostgreSQL
            db = await get_database_manager()
            stats_data = await db.get_memory_stats()
            
            # Add Redis memory usage
            try:
                redis_info = await redis_client.info("memory")
                stats_data['memory_usage_mb'] = redis_info.get("used_memory", 0) / (1024 * 1024)
            except Exception:
                stats_data['memory_usage_mb'] = 0.0
            
            stats = MemoryStats(**stats_data)
            
            # Cache stats
            try:
                await redis_client.setex(
                    cache_key,
                    self.STATS_CACHE_TTL,
                    stats.json()
                )
            except Exception as e:
                logger.warning(f"Failed to cache stats: {e}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return MemoryStats()
    
    # Helper Methods
    
    def _extract_topics_from_messages(self, messages: List[ConversationMessage]) -> List[str]:
        """Extract topics from conversation messages."""
        topics = set()
        
        # Simple keyword-based topic extraction
        keywords = {
            "programming": ["код", "программа", "разработка", "python", "javascript", "api", "функция"],
            "ai": ["ai", "искусственный интеллект", "машинное обучение", "нейронная сеть", "модель"],
            "help": ["помощь", "как", "что делать", "проблема", "ошибка", "вопрос"],
            "casual": ["привет", "как дела", "спасибо", "пока", "здравствуй"],
            "devops": ["docker", "kubernetes", "сервер", "развертывание", "контейнер"],
        }
        
        for message in messages:
            if message.role == "user":
                content_lower = message.content.lower()
                for topic, words in keywords.items():
                    if any(word in content_lower for word in words):
                        topics.add(topic)
        
        return list(topics)
    
    async def _extract_and_save_user_facts(self, user_id: str, content: str) -> None:
        """Extract and save facts about user from message content."""
        try:
            facts_to_add = []
            content_lower = content.lower()
            
            # Programming languages
            prog_langs = ['python', 'javascript', 'java', 'c++', 'go', 'rust', 'php', 'ruby']
            for lang in prog_langs:
                if lang in content_lower:
                    facts_to_add.append(f"Интересуется программированием на {lang}")
            
            # Interests
            if any(word in content_lower for word in ['ai', 'машинное обучение', 'нейронные сети']):
                facts_to_add.append("Интересуется искусственным интеллектом")
            
            if any(word in content_lower for word in ['docker', 'kubernetes', 'devops']):
                facts_to_add.append("Работает с DevOps технологиями")
            
            # Name extraction (simple)
            if any(phrase in content_lower for phrase in ['меня зовут', 'я ', 'мое имя']):
                # Extract potential name (very basic)
                words = content.split()
                for i, word in enumerate(words):
                    if word.lower() in ['зовут', 'имя'] and i + 1 < len(words):
                        potential_name = words[i + 1].strip('.,!?')
                        if len(potential_name) > 1 and potential_name.isalpha():
                            facts_to_add.append(f"Имя: {potential_name}")
                        break
            
            # Language preference
            if any(word in content_lower for word in ['на русском', 'по-русски']):
                await self.update_user_preferences(user_id, {"language": "ru"})
            elif any(word in content_lower for word in ['in english', 'на английском']):
                await self.update_user_preferences(user_id, {"language": "en"})
            
            # Save extracted facts
            for fact in facts_to_add:
                await self.add_user_fact(user_id, fact)
                
        except Exception as e:
            logger.debug(f"Failed to extract user facts: {e}")


# Global hybrid memory manager instance
_hybrid_memory_manager: Optional[HybridMemoryManager] = None


def get_hybrid_memory_manager() -> HybridMemoryManager:
    """Get global hybrid memory manager instance."""
    global _hybrid_memory_manager
    if _hybrid_memory_manager is None:
        _hybrid_memory_manager = HybridMemoryManager()
    return _hybrid_memory_manager


async def close_hybrid_memory_manager():
    """Close global hybrid memory manager."""
    global _hybrid_memory_manager
    if _hybrid_memory_manager:
        await _hybrid_memory_manager.close()
        _hybrid_memory_manager = None
