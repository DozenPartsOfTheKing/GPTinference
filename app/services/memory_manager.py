"""Memory management service."""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import redis.asyncio as redis
from redis.asyncio import Redis

from ..core.config import get_settings
from ..models.memory import (
    ConversationMemory,
    ConversationMessage,
    MemoryPriorityEnum,
    MemoryQuery,
    MemoryStats,
    MemoryTypeEnum,
    SystemMemory,
    UserMemory,
)

logger = logging.getLogger(__name__)


class MemoryManager:
    """Memory management service using Redis."""
    
    def __init__(self, redis_client: Optional[Redis] = None):
        """Initialize memory manager."""
        self.redis = redis_client
        self.settings = get_settings()
        
        # Redis key prefixes
        self.CONVERSATION_PREFIX = "memory:conversation:"
        self.USER_PREFIX = "memory:user:"
        self.SYSTEM_PREFIX = "memory:system:"
        self.STATS_PREFIX = "memory:stats:"
        
        # Default TTL values (in seconds)
        self.DEFAULT_CONVERSATION_TTL = 7 * 24 * 3600  # 7 days
        self.DEFAULT_USER_TTL = 30 * 24 * 3600  # 30 days
        self.DEFAULT_SYSTEM_TTL = None  # No expiration
    
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
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
    
    # Conversation Memory Methods
    
    async def save_conversation_message(
        self,
        conversation_id: str,
        message: ConversationMessage,
        user_id: Optional[str] = None,
        ttl_hours: Optional[int] = None
    ) -> bool:
        """Save a message to conversation memory."""
        try:
            redis_client = await self._get_redis()
            key = f"{self.CONVERSATION_PREFIX}{conversation_id}"
            
            # Get existing conversation or create new one
            conversation_data = await redis_client.get(key)
            if conversation_data:
                conversation = ConversationMemory.parse_raw(conversation_data)
            else:
                conversation = ConversationMemory(
                    conversation_id=conversation_id,
                    user_id=user_id
                )
            
            # Add message
            conversation.messages.append(message)
            conversation.message_count = len(conversation.messages)
            conversation.total_tokens += message.tokens or 0
            conversation.updated_at = datetime.utcnow()
            
            # Update topics based on message content
            await self._update_conversation_topics(conversation, message.content)
            
            # Set TTL
            ttl_seconds = None
            if ttl_hours:
                ttl_seconds = ttl_hours * 3600
                conversation.expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
            else:
                ttl_seconds = self.DEFAULT_CONVERSATION_TTL
                conversation.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            
            # Save to Redis
            await redis_client.setex(
                key,
                ttl_seconds,
                conversation.json()
            )
            
            # Update user memory
            if user_id:
                await self._update_user_conversation_history(user_id, conversation_id)
            
            logger.info(f"Saved message to conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving conversation message: {e}")
            return False
    
    async def get_conversation_memory(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> Optional[ConversationMemory]:
        """Get conversation memory."""
        try:
            redis_client = await self._get_redis()
            key = f"{self.CONVERSATION_PREFIX}{conversation_id}"
            
            conversation_data = await redis_client.get(key)
            if not conversation_data:
                return None
            
            conversation = ConversationMemory.parse_raw(conversation_data)
            
            # Limit messages if requested
            if limit and len(conversation.messages) > limit:
                conversation.messages = conversation.messages[-limit:]
            
            return conversation
            
        except Exception as e:
            logger.error(f"Error getting conversation memory: {e}")
            return None
    
    async def delete_conversation_memory(self, conversation_id: str) -> bool:
        """Delete conversation memory."""
        try:
            redis_client = await self._get_redis()
            key = f"{self.CONVERSATION_PREFIX}{conversation_id}"
            
            result = await redis_client.delete(key)
            logger.info(f"Deleted conversation memory {conversation_id}")
            return result > 0
            
        except Exception as e:
            logger.error(f"Error deleting conversation memory: {e}")
            return False
    
    # User Memory Methods
    
    async def save_user_memory(
        self,
        user_memory: UserMemory,
        ttl_hours: Optional[int] = None
    ) -> bool:
        """Save user memory."""
        try:
            redis_client = await self._get_redis()
            key = f"{self.USER_PREFIX}{user_memory.user_id}"
            
            user_memory.updated_at = datetime.utcnow()
            
            # Set TTL
            ttl_seconds = None
            if ttl_hours:
                ttl_seconds = ttl_hours * 3600
            else:
                ttl_seconds = self.DEFAULT_USER_TTL
            
            await redis_client.setex(
                key,
                ttl_seconds,
                user_memory.json()
            )
            
            logger.info(f"Saved user memory for {user_memory.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving user memory: {e}")
            return False
    
    async def get_user_memory(self, user_id: str) -> Optional[UserMemory]:
        """Get user memory."""
        try:
            redis_client = await self._get_redis()
            key = f"{self.USER_PREFIX}{user_id}"
            
            user_data = await redis_client.get(key)
            if not user_data:
                # Create new user memory
                return UserMemory(user_id=user_id)
            
            user_memory = UserMemory.parse_raw(user_data)
            user_memory.last_active = datetime.utcnow()
            
            # Update last active time
            await self.save_user_memory(user_memory)
            
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
            user_memory = await self.get_user_memory(user_id)
            user_memory.preferences.update(preferences)
            return await self.save_user_memory(user_memory)
            
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
            return False
    
    async def add_user_fact(self, user_id: str, fact: str) -> bool:
        """Add a fact about the user."""
        try:
            user_memory = await self.get_user_memory(user_id)
            if fact not in user_memory.facts:
                user_memory.facts.append(fact)
                return await self.save_user_memory(user_memory)
            return True
            
        except Exception as e:
            logger.error(f"Error adding user fact: {e}")
            return False
    
    # System Memory Methods
    
    async def save_system_memory(
        self,
        system_memory: SystemMemory,
        ttl_hours: Optional[int] = None
    ) -> bool:
        """Save system memory."""
        try:
            redis_client = await self._get_redis()
            key = f"{self.SYSTEM_PREFIX}{system_memory.key}"
            
            system_memory.updated_at = datetime.utcnow()
            system_memory.access_count += 1
            system_memory.last_accessed = datetime.utcnow()
            
            # Set TTL
            if ttl_hours:
                ttl_seconds = ttl_hours * 3600
                system_memory.expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
                await redis_client.setex(
                    key,
                    ttl_seconds,
                    system_memory.json()
                )
            else:
                await redis_client.set(key, system_memory.json())
            
            logger.info(f"Saved system memory: {system_memory.key}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving system memory: {e}")
            return False
    
    async def get_system_memory(self, key: str) -> Optional[SystemMemory]:
        """Get system memory."""
        try:
            redis_client = await self._get_redis()
            redis_key = f"{self.SYSTEM_PREFIX}{key}"
            
            memory_data = await redis_client.get(redis_key)
            if not memory_data:
                return None
            
            system_memory = SystemMemory.parse_raw(memory_data)
            
            # Update access statistics
            system_memory.access_count += 1
            system_memory.last_accessed = datetime.utcnow()
            await self.save_system_memory(system_memory)
            
            return system_memory
            
        except Exception as e:
            logger.error(f"Error getting system memory: {e}")
            return None
    
    async def delete_system_memory(self, key: str) -> bool:
        """Delete system memory."""
        try:
            redis_client = await self._get_redis()
            redis_key = f"{self.SYSTEM_PREFIX}{key}"
            
            result = await redis_client.delete(redis_key)
            logger.info(f"Deleted system memory: {key}")
            return result > 0
            
        except Exception as e:
            logger.error(f"Error deleting system memory: {e}")
            return False
    
    # Query and Statistics Methods
    
    async def query_memories(self, query: MemoryQuery) -> Dict[str, Any]:
        """Query memories based on filters."""
        try:
            redis_client = await self._get_redis()
            results = {
                "conversations": [],
                "users": [],
                "system_memories": [],
                "total_count": 0
            }
            
            # Query conversations
            if not query.memory_type or query.memory_type == MemoryTypeEnum.CONVERSATION:
                pattern = f"{self.CONVERSATION_PREFIX}*"
                if query.conversation_id:
                    pattern = f"{self.CONVERSATION_PREFIX}{query.conversation_id}"
                
                keys = await redis_client.keys(pattern)
                for key in keys[query.offset:query.offset + query.limit]:
                    data = await redis_client.get(key)
                    if data:
                        conversation = ConversationMemory.parse_raw(data)
                        if self._matches_query(conversation, query):
                            results["conversations"].append(conversation.dict())
            
            # Query users
            if not query.memory_type or query.memory_type == MemoryTypeEnum.USER_CONTEXT:
                pattern = f"{self.USER_PREFIX}*"
                if query.user_id:
                    pattern = f"{self.USER_PREFIX}{query.user_id}"
                
                keys = await redis_client.keys(pattern)
                for key in keys[query.offset:query.offset + query.limit]:
                    data = await redis_client.get(key)
                    if data:
                        user = UserMemory.parse_raw(data)
                        if self._matches_query(user, query):
                            results["users"].append(user.dict())
            
            # Query system memories
            if not query.memory_type or query.memory_type in [
                MemoryTypeEnum.SYSTEM_FACTS,
                MemoryTypeEnum.KNOWLEDGE,
                MemoryTypeEnum.PREFERENCES
            ]:
                pattern = f"{self.SYSTEM_PREFIX}*"
                keys = await redis_client.keys(pattern)
                for key in keys[query.offset:query.offset + query.limit]:
                    data = await redis_client.get(key)
                    if data:
                        system_memory = SystemMemory.parse_raw(data)
                        if self._matches_query(system_memory, query):
                            results["system_memories"].append(system_memory.dict())
            
            results["total_count"] = (
                len(results["conversations"]) +
                len(results["users"]) +
                len(results["system_memories"])
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error querying memories: {e}")
            return {"conversations": [], "users": [], "system_memories": [], "total_count": 0}
    
    async def get_memory_stats(self) -> MemoryStats:
        """Get memory statistics."""
        try:
            redis_client = await self._get_redis()
            
            # Count different types of memories
            conversation_keys = await redis_client.keys(f"{self.CONVERSATION_PREFIX}*")
            user_keys = await redis_client.keys(f"{self.USER_PREFIX}*")
            system_keys = await redis_client.keys(f"{self.SYSTEM_PREFIX}*")
            
            # Calculate memory usage (approximate)
            memory_info = await redis_client.info("memory")
            memory_usage_mb = memory_info.get("used_memory", 0) / (1024 * 1024)
            
            # Get conversation statistics
            total_messages = 0
            total_tokens = 0
            topics_count = {}
            model_usage = {}
            
            for key in conversation_keys[:100]:  # Sample first 100 for performance
                data = await redis_client.get(key)
                if data:
                    try:
                        conversation = ConversationMemory.parse_raw(data)
                        total_messages += conversation.message_count
                        total_tokens += conversation.total_tokens
                        
                        # Count topics
                        for topic in conversation.topics:
                            topics_count[topic] = topics_count.get(topic, 0) + 1
                        
                        # Count model usage
                        for message in conversation.messages:
                            if message.model:
                                model_usage[message.model] = model_usage.get(message.model, 0) + 1
                    except Exception:
                        continue
            
            # Prepare popular topics
            popular_topics = [
                {"topic": topic, "count": count}
                for topic, count in sorted(topics_count.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
            
            # Prepare model usage stats
            model_stats = {}
            for model, count in model_usage.items():
                model_stats[model] = {
                    "usage_count": count,
                    "avg_response_time": 2.5  # Placeholder - would need actual tracking
                }
            
            avg_conversation_length = total_messages / max(len(conversation_keys), 1)
            
            return MemoryStats(
                total_conversations=len(conversation_keys),
                total_users=len(user_keys),
                total_system_memories=len(system_keys),
                memory_usage_mb=memory_usage_mb,
                avg_conversation_length=avg_conversation_length,
                most_active_users=[],  # Would need additional tracking
                popular_topics=popular_topics,
                model_usage_stats=model_stats
            )
            
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return MemoryStats()
    
    # Helper Methods
    
    async def _update_conversation_topics(self, conversation: ConversationMemory, content: str):
        """Update conversation topics based on content."""
        # Simple keyword-based topic extraction
        # In production, you might want to use more sophisticated NLP
        keywords = {
            "programming": ["код", "программа", "разработка", "python", "javascript", "api"],
            "ai": ["ai", "искусственный интеллект", "машинное обучение", "нейронная сеть"],
            "help": ["помощь", "как", "что делать", "проблема", "ошибка"],
            "casual": ["привет", "как дела", "спасибо", "пока"],
        }
        
        content_lower = content.lower()
        for topic, words in keywords.items():
            if any(word in content_lower for word in words):
                if topic not in conversation.topics:
                    conversation.topics.append(topic)
    
    async def _update_user_conversation_history(self, user_id: str, conversation_id: str):
        """Update user's conversation history."""
        user_memory = await self.get_user_memory(user_id)
        
        # Add to conversation history (keep last 50)
        if conversation_id not in user_memory.conversation_history:
            user_memory.conversation_history.append(conversation_id)
            if len(user_memory.conversation_history) > 50:
                user_memory.conversation_history = user_memory.conversation_history[-50:]
        
        await self.save_user_memory(user_memory)
    
    def _matches_query(self, memory: Union[ConversationMemory, UserMemory, SystemMemory], query: MemoryQuery) -> bool:
        """Check if memory matches query filters."""
        # Check expiration
        if not query.include_expired:
            if hasattr(memory, 'expires_at') and memory.expires_at:
                if memory.expires_at < datetime.utcnow():
                    return False
        
        # Check user_id filter
        if query.user_id and hasattr(memory, 'user_id'):
            if memory.user_id != query.user_id:
                return False
        
        # Check conversation_id filter
        if query.conversation_id and hasattr(memory, 'conversation_id'):
            if memory.conversation_id != query.conversation_id:
                return False
        
        # Check tags filter
        if query.tags and hasattr(memory, 'tags'):
            if not any(tag in memory.tags for tag in query.tags):
                return False
        
        # Check priority filter
        if query.priority and hasattr(memory, 'priority'):
            if memory.priority != query.priority:
                return False
        
        return True


# Global memory manager instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get global memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


async def close_memory_manager():
    """Close global memory manager."""
    global _memory_manager
    if _memory_manager:
        await _memory_manager.close()
        _memory_manager = None
