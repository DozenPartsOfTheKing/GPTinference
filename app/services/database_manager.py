"""Database manager for PostgreSQL operations."""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import asyncpg
from asyncpg import Pool

from ..core.config import get_settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """PostgreSQL database manager."""
    
    def __init__(self):
        """Initialize database manager."""
        self.pool: Optional[Pool] = None
        self.settings = get_settings()
    
    async def init_pool(self) -> None:
        """Initialize connection pool."""
        try:
            database_url = getattr(self.settings, 'database_url', None)
            if not database_url:
                # Fallback to individual components
                database_url = (
                    f"postgresql://gptinfernse:gptinfernse_password@"
                    f"postgres:5432/gptinfernse"
                )
            
            async def _init_connection(conn: asyncpg.Connection):
                # Ensure JSON/JSONB are decoded to Python objects
                await conn.set_type_codec(
                    'json', encoder=json.dumps, decoder=json.loads, schema='pg_catalog'
                )
                await conn.set_type_codec(
                    'jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog'
                )

            self.pool = await asyncpg.create_pool(
                database_url,
                min_size=2,
                max_size=10,
                command_timeout=60,
                init=_init_connection,
            )
            logger.info("Database connection pool initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    async def close_pool(self) -> None:
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    def get_connection(self):
        """Get database connection from pool."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized. Call init_pool() first.")
        return self.pool.acquire()
    
    # User Management
    
    async def get_or_create_user(
        self,
        user_identifier: str,
        display_name: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get existing user or create new one."""
        async with self.get_connection() as conn:
            # Try to get existing user
            user = await conn.fetchrow(
                """
                SELECT id, user_identifier, display_name, preferences, facts, 
                       created_at, updated_at, last_active
                FROM users 
                WHERE user_identifier = $1 AND is_active = TRUE
                """,
                user_identifier
            )
            
            if user:
                # Update last active
                await conn.execute(
                    "UPDATE users SET last_active = NOW() WHERE id = $1",
                    user['id']
                )
                return dict(user)
            
            # Create new user
            user_id = uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO users (id, user_identifier, display_name, preferences, facts)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id,
                user_identifier,
                display_name,
                preferences or {},
                []
            )
            
            # Return created user
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id
            )
            
            logger.info(f"Created new user: {user_identifier}")
            return dict(user)
    
    async def update_user_preferences(
        self,
        user_identifier: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """Update user preferences."""
        async with self.get_connection() as conn:
            result = await conn.execute(
                """
                UPDATE users 
                SET preferences = COALESCE(preferences, '{}'::jsonb) || $2::jsonb, updated_at = NOW()
                WHERE user_identifier = $1 AND is_active = TRUE
                """,
                user_identifier,
                preferences
            )
            return result != "UPDATE 0"
    
    async def add_user_fact(
        self,
        user_identifier: str,
        fact: str
    ) -> bool:
        """Add fact about user."""
        async with self.get_connection() as conn:
            result = await conn.execute(
                """
                UPDATE users 
                SET facts = array_append(facts, $2), updated_at = NOW()
                WHERE user_identifier = $1 AND is_active = TRUE
                AND NOT ($2 = ANY(facts))
                """,
                user_identifier,
                fact
            )
            return result != "UPDATE 0"
    
    # Conversation Management
    
    async def create_conversation(
        self,
        conversation_id: str,
        user_identifier: str,
        model_used: Optional[str] = None,
        ttl_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create new conversation."""
        async with self.get_connection() as conn:
            # Get user
            user = await self.get_or_create_user(user_identifier)
            
            # Calculate expiration
            expires_at = None
            if ttl_hours:
                expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
            
            conv_id = uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO conversations 
                (id, conversation_id, user_id, model_used, expires_at)
                VALUES ($1, $2, $3, $4, $5)
                """,
                conv_id,
                conversation_id,
                user['id'],
                model_used,
                expires_at
            )
            
            conversation = await conn.fetchrow(
                "SELECT * FROM conversations WHERE id = $1",
                conv_id
            )
            
            logger.info(f"Created conversation: {conversation_id}")
            return dict(conversation)
    
    async def get_conversation(
        self,
        conversation_id: str,
        include_messages: bool = True,
        message_limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get conversation with optional messages."""
        async with self.get_connection() as conn:
            # Get conversation
            conversation = await conn.fetchrow(
                """
                SELECT c.*, u.user_identifier, u.display_name
                FROM conversations c
                LEFT JOIN users u ON c.user_id = u.id
                WHERE c.conversation_id = $1 AND c.is_active = TRUE
                """,
                conversation_id
            )
            
            if not conversation:
                return None
            
            result = dict(conversation)
            
            if include_messages:
                # Get messages
                if message_limit:
                    # Fetch latest N messages and return in chronological order
                    query = """
                        SELECT message_id, role, content, tokens, model, metadata, created_at
                        FROM (
                            SELECT message_id, role, content, tokens, model, metadata, created_at
                            FROM messages
                            WHERE conversation_id = $1
                            ORDER BY created_at DESC
                            LIMIT $2
                        ) sub
                        ORDER BY created_at ASC
                    """
                    messages = await conn.fetch(query, conversation['id'], message_limit)
                else:
                    query = """
                        SELECT message_id, role, content, tokens, model, metadata, created_at
                        FROM messages 
                        WHERE conversation_id = $1 
                        ORDER BY created_at ASC
                    """
                    messages = await conn.fetch(query, conversation['id'])
                result['messages'] = [dict(msg) for msg in messages]
            
            return result
    
    async def add_message(
        self,
        conversation_id: str,
        message_id: str,
        role: str,
        content: str,
        tokens: Optional[int] = None,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add message to conversation."""
        async with self.get_connection() as conn:
            # Get conversation
            conv = await conn.fetchrow(
                "SELECT id FROM conversations WHERE conversation_id = $1 AND is_active = TRUE",
                conversation_id
            )
            
            if not conv:
                logger.warning(f"Conversation not found: {conversation_id}")
                return False
            
            # Add message
            await conn.execute(
                """
                INSERT INTO messages 
                (message_id, conversation_id, role, content, tokens, model, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                message_id,
                conv['id'],
                role,
                content,
                tokens,
                model,
                metadata or {}
            )
            
            # Update conversation stats
            await conn.execute(
                """
                UPDATE conversations 
                SET 
                    message_count = message_count + 1,
                    total_tokens = total_tokens + COALESCE($2, 0),
                    updated_at = NOW()
                WHERE id = $1
                """,
                conv['id'],
                tokens
            )
            
            return True
    
    # System Memory
    
    async def set_system_memory(
        self,
        key: str,
        value: Any,
        memory_type: str = 'system_facts',
        priority: str = 'medium',
        tags: Optional[List[str]] = None,
        ttl_hours: Optional[int] = None
    ) -> bool:
        """Set system memory value."""
        async with self.get_connection() as conn:
            expires_at = None
            if ttl_hours:
                expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
            
            await conn.execute(
                """
                INSERT INTO system_memory (key, value, memory_type, priority, tags, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    memory_type = EXCLUDED.memory_type,
                    priority = EXCLUDED.priority,
                    tags = EXCLUDED.tags,
                    expires_at = EXCLUDED.expires_at,
                    access_count = system_memory.access_count + 1,
                    updated_at = NOW(),
                    last_accessed = NOW()
                """,
                key,
                value,
                memory_type,
                priority,
                tags or [],
                expires_at
            )
            
            return True
    
    async def get_system_memory(self, key: str) -> Optional[Any]:
        """Get system memory value."""
        async with self.get_connection() as conn:
            result = await conn.fetchrow(
                """
                SELECT value FROM system_memory 
                WHERE key = $1 
                AND (expires_at IS NULL OR expires_at > NOW())
                """,
                key
            )
            
            if result:
                # Update access stats
                await conn.execute(
                    """
                    UPDATE system_memory 
                    SET access_count = access_count + 1, last_accessed = NOW()
                    WHERE key = $1
                    """,
                    key
                )
                return result['value']
            
            return None

    async def list_system_memory(
        self,
        memory_type: Optional[str] = None,
        include_expired: bool = False,
    ) -> List[Dict[str, Any]]:
        """List system memory entries with optional type filter.

        Returns a list of dicts with: key, value, memory_type, priority, tags, created_at, updated_at, expires_at, access_count, last_accessed
        """
        async with self.get_connection() as conn:
            conditions = []
            params: List[Any] = []
            if memory_type:
                conditions.append("memory_type = $1")
                params.append(memory_type)
            if not include_expired:
                conditions.append("(expires_at IS NULL OR expires_at > NOW())")
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            query = f"""
                SELECT key, value, memory_type, priority, tags, created_at, updated_at, expires_at, access_count, last_accessed
                FROM system_memory
                {where_clause}
                ORDER BY updated_at DESC
            """
            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]

    async def delete_system_memory(self, key: str) -> bool:
        """Delete a system memory entry by key."""
        async with self.get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM system_memory WHERE key = $1",
                key,
            )
            return result != "DELETE 0"

    async def list_conversations(
        self,
        limit: int = 50,
        offset: int = 0,
        user_identifier: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List recent conversations with basic stats."""
        async with self.get_connection() as conn:
            if user_identifier:
                query = """
                    SELECT c.conversation_id, c.message_count, c.total_tokens, c.updated_at
                    FROM conversations c
                    JOIN users u ON c.user_id = u.id
                    WHERE c.is_active = TRUE AND u.user_identifier = $1
                    ORDER BY c.updated_at DESC
                    LIMIT $2 OFFSET $3
                """
                rows = await conn.fetch(query, user_identifier, limit, offset)
            else:
                query = """
                    SELECT conversation_id, message_count, total_tokens, updated_at
                    FROM conversations
                    WHERE is_active = TRUE
                    ORDER BY updated_at DESC
                    LIMIT $1 OFFSET $2
                """
                rows = await conn.fetch(query, limit, offset)
            return [dict(r) for r in rows]

    async def list_users(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List users with basic info and facts."""
        async with self.get_connection() as conn:
            query = """
                SELECT user_identifier, preferences, facts, last_active, created_at, updated_at
                FROM users
                WHERE is_active = TRUE
                ORDER BY last_active DESC
                LIMIT $1 OFFSET $2
            """
            rows = await conn.fetch(query, limit, offset)
            return [dict(r) for r in rows]
    
    # Statistics
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        async with self.get_connection() as conn:
            stats = {}
            
            # Basic counts
            stats['total_users'] = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE is_active = TRUE"
            )
            
            stats['total_conversations'] = await conn.fetchval(
                "SELECT COUNT(*) FROM conversations WHERE is_active = TRUE"
            )
            
            stats['total_messages'] = await conn.fetchval(
                "SELECT COUNT(*) FROM messages"
            )
            
            stats['total_tokens'] = await conn.fetchval(
                "SELECT SUM(total_tokens) FROM conversations WHERE is_active = TRUE"
            ) or 0
            
            # Average conversation length
            avg_length = await conn.fetchval(
                "SELECT AVG(message_count) FROM conversations WHERE is_active = TRUE AND message_count > 0"
            )
            stats['avg_conversation_length'] = float(avg_length) if avg_length else 0.0
            
            # Popular topics
            topics = await conn.fetch(
                """
                SELECT unnest(topics) as topic, COUNT(*) as count
                FROM conversations 
                WHERE is_active = TRUE AND topics IS NOT NULL
                GROUP BY topic
                ORDER BY count DESC
                LIMIT 10
                """
            )
            stats['popular_topics'] = [
                {"topic": row['topic'], "count": row['count']} 
                for row in topics
            ]
            
            # Model usage
            models = await conn.fetch(
                """
                SELECT model_used, COUNT(*) as usage_count, AVG(total_tokens) as avg_tokens
                FROM conversations 
                WHERE is_active = TRUE AND model_used IS NOT NULL
                GROUP BY model_used
                ORDER BY usage_count DESC
                """
            )
            stats['model_usage_stats'] = {
                row['model_used']: {
                    "usage_count": row['usage_count'],
                    "avg_tokens": float(row['avg_tokens']) if row['avg_tokens'] else 0.0
                }
                for row in models
            }
            
            return stats
    
    # Cleanup
    
    async def cleanup_expired_data(self) -> int:
        """Clean up expired data."""
        async with self.get_connection() as conn:
            result = await conn.fetchval("SELECT cleanup_expired_data()")
            logger.info(f"Cleaned up {result} expired records")
            return result


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


async def get_database_manager() -> DatabaseManager:
    """Get global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.init_pool()
    return _db_manager


async def close_database_manager():
    """Close global database manager."""
    global _db_manager
    if _db_manager:
        await _db_manager.close_pool()
        _db_manager = None
