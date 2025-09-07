"""Hybrid memory manager using PostgreSQL + Redis."""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from redis.asyncio import Redis

from ..utils.loguru_config import get_logger, MemoryLogContext, DatabaseLogContext
from ..utils.redis_tracer import trace_redis_operations

from ..core.config import get_settings
from ..models.memory import (
    ConversationMemory,
    ConversationMessage,
    SystemMemory,
    MemoryQuery,
    MemoryStats,
    UserMemory,
)
from .database_manager import get_database_manager

logger = get_logger(__name__)


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
        self.redis_tracer = None
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
            # Initialize Redis tracer
            self.redis_tracer = trace_redis_operations(self.redis)
            logger.info(
                f"🔴 Redis connection and tracer initialized (url={self.settings.redis_url})"
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
            with MemoryLogContext(
                "Save Conversation Message", 
                conversation_id=conversation_id, 
                user_id=user_id,
                message_role=message.role
            ) as mem_logger:
                
                mem_logger.info(f"💾 Saving {message.role} message: {message.content[:100]}...")
                
                try:
                    db = await get_database_manager()
                    
                    # Ensure conversation exists in PostgreSQL
                    mem_logger.debug("🔍 Checking if conversation exists...")
                    conversation = await db.get_conversation(conversation_id, include_messages=False)
                    if not conversation:
                        # Create conversation
                        mem_logger.info("🆕 Creating new conversation...")
                        await db.create_conversation(
                            conversation_id=conversation_id,
                            user_identifier=user_id or "anonymous",
                            ttl_hours=ttl_hours or 24 * 7  # 7 days default
                        )
                    
                    # Save message to PostgreSQL
                    mem_logger.debug("💾 Saving message to PostgreSQL...")
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
                        await self._get_redis()  # Initialize tracer
                        cache_key = f"conversation:{conversation_id}"
                        await self.redis_tracer.trace_delete(
                            cache_key, 
                            description=f"Invalidate cache after saving message"
                        )
                        # Re-cache fresh conversation state for faster subsequent reads
                        try:
                            refreshed = await self.get_conversation_memory(conversation_id)
                            if refreshed:
                                logger.info(
                                    f"🧩 Conversation cache refreshed: {conversation_id} "
                                    f"(messages={len(refreshed.messages)})"
                                )
                        except Exception as recache_err:
                            logger.warning(f"Failed to refresh conversation cache: {recache_err}")
                    
                        # Update user facts if it's a user message
                        if message.role == "user" and user_id:
                            await self._extract_and_save_user_facts(user_id, message.content)
                        
                        mem_logger.success(f"✅ Saved message to conversation {conversation_id}")
                        return True
                    
                    return False
                    
                except Exception as e:
                    mem_logger.error(f"❌ Error saving message: {e}")
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
            await self._get_redis()  # Initialize tracer
            cache_key = f"conversation:{conversation_id}"
            logger.info(
                f"🧠 Fetching conversation memory (id={conversation_id}, limit={limit})"
            )
            
            # Try Redis cache first
            cached_data = await self.redis_tracer.trace_get(
                cache_key, 
                description=f"Get conversation from cache (limit: {limit})"
            )
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
            
            logger.info(
                f"🗄️ Cache miss for {cache_key}. Falling back to PostgreSQL"
            )
            # Fallback to PostgreSQL
            db = await get_database_manager()
            conversation_data = await db.get_conversation(
                conversation_id, 
                include_messages=True,
                message_limit=limit
            )
            
            if not conversation_data:
                logger.info(f"No conversation found in DB for id={conversation_id}")
                return None
            
            # Convert to ConversationMemory model
            messages = []
            if 'messages' in conversation_data:
                for msg_data in conversation_data['messages']:
                    # Ensure metadata is a dict
                    raw_metadata = msg_data['metadata']
                    if isinstance(raw_metadata, str):
                        try:
                            raw_metadata = json.loads(raw_metadata)
                        except Exception:
                            raw_metadata = {}
                    message = ConversationMessage(
                        id=msg_data['message_id'],
                        role=msg_data['role'],
                        content=msg_data['content'],
                        timestamp=msg_data['created_at'],
                        tokens=msg_data['tokens'],
                        model=msg_data['model'],
                        metadata=raw_metadata
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
            logger.info(
                f"📦 Loaded from DB: messages={len(messages)}, total_tokens={conversation.total_tokens}"
            )
            
            # Cache in Redis for future requests
            try:
                await self.redis_tracer.trace_set(
                    cache_key,
                    conversation.json(),
                    ttl=self.CONVERSATION_CACHE_TTL,
                    description=f"Cache conversation from database"
                )
                # Debug: list keys for visibility
                await self.redis_tracer.trace_keys(
                    pattern="conversation:*",
                    description="Post-cache debug keys"
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
                preferences=(
                    json.loads(user_data['preferences']) if isinstance(user_data['preferences'], str)
                    else (user_data['preferences'] or {})
                ),
                facts=(user_data['facts'] or []),
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

    async def save_system_memory(
        self,
        system_memory: SystemMemory,
        ttl_hours: Optional[int] = None
    ) -> bool:
        """Save system memory entry using database persistence."""
        try:
            db = await get_database_manager()
            return await db.set_system_memory(
                key=system_memory.key,
                value=system_memory.value,
                memory_type=system_memory.memory_type.value if hasattr(system_memory.memory_type, 'value') else str(system_memory.memory_type),
                priority=system_memory.priority.value if hasattr(system_memory.priority, 'value') else str(system_memory.priority),
                tags=system_memory.tags,
                ttl_hours=ttl_hours
            )
        except Exception as e:
            logger.error(f"Error saving system memory: {e}")
            return False

    async def delete_system_memory(self, key: str) -> bool:
        """Delete system memory entry by key."""
        try:
            db = await get_database_manager()
            return await db.delete_system_memory(key)
        except Exception as e:
            logger.error(f"Error deleting system memory: {e}")
            return False

    async def list_system_prompts(self) -> List[Dict[str, Any]]:
        """List stored system prompts (tagged with 'system_prompt')."""
        try:
            db = await get_database_manager()
            rows = await db.list_system_memory(memory_type='system_facts', include_expired=False)
            prompts = [row for row in rows if row.get('tags') and 'system_prompt' in row['tags']]
            return prompts
        except Exception as e:
            logger.error(f"Error listing system prompts: {e}")
            return []

    async def save_system_prompt(
        self,
        key: str,
        content: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        model: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> bool:
        """Create or update a system prompt."""
        value = {
            "title": title or key,
            "content": content,
            "description": description,
            "model": model,
            "created_by": created_by,
        }
        try:
            db = await get_database_manager()
            return await db.set_system_memory(
                key=key,
                value=value,
                memory_type='system_facts',
                priority='medium',
                tags=['system_prompt'],
                ttl_hours=None,
            )
        except Exception as e:
            logger.error(f"Error saving system prompt: {e}")
            return False

    async def delete_system_prompt(self, key: str) -> bool:
        """Delete a stored system prompt by key."""
        return await self.delete_system_memory(key)

    async def set_active_system_prompt(self, key: str) -> bool:
        """Mark a stored system prompt as active by saving a pointer key."""
        try:
            # Ensure prompt exists
            prompt = await self.get_system_memory(key)
            if not prompt:
                return False
            return await self.set_system_memory(
                key='system_prompt_active',
                value={"key": key},
                memory_type='preferences',
            )
        except Exception as e:
            logger.error(f"Error setting active system prompt: {e}")
            return False

    async def get_active_system_prompt(self) -> Optional[Dict[str, Any]]:
        """Return the active system prompt content and metadata if set."""
        try:
            pointer = await self.get_system_memory('system_prompt_active')
            if not pointer or not isinstance(pointer, dict) or 'key' not in pointer:
                return None
            key = pointer['key']
            prompt_value = await self.get_system_memory(key)
            if prompt_value is None:
                return None
            return {"key": key, **(prompt_value if isinstance(prompt_value, dict) else {"content": str(prompt_value)})}
        except Exception as e:
            logger.error(f"Error getting active system prompt: {e}")
            return None
    
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

    # Admin-friendly listing
    async def list_recent_conversations(self, limit: int = 50, offset: int = 0, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            db = await get_database_manager()
            return await db.list_conversations(limit=limit, offset=offset, user_identifier=user_id)
        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            return []

    async def list_users(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        try:
            db = await get_database_manager()
            return await db.list_users(limit=limit, offset=offset)
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []
    
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
