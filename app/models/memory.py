"""Memory-related data models."""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class MemoryTypeEnum(str, Enum):
    """Memory type enumeration."""
    CONVERSATION = "conversation"  # История диалога
    USER_CONTEXT = "user_context"  # Контекст пользователя
    SYSTEM_FACTS = "system_facts"  # Системные факты
    PREFERENCES = "preferences"    # Пользовательские предпочтения
    KNOWLEDGE = "knowledge"        # Накопленные знания


class MemoryPriorityEnum(str, Enum):
    """Memory priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConversationMessage(BaseModel):
    """Single conversation message."""
    
    id: str = Field(..., description="Message ID")
    role: str = Field(..., description="Message role (user/assistant/system)")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    tokens: Optional[int] = Field(default=None, description="Token count")
    model: Optional[str] = Field(default=None, description="Model used for generation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ConversationMemory(BaseModel):
    """Conversation memory model."""
    
    conversation_id: str = Field(..., description="Conversation identifier")
    user_id: Optional[str] = Field(default=None, description="User identifier")
    messages: List[ConversationMessage] = Field(default_factory=list, description="Conversation messages")
    summary: Optional[str] = Field(default=None, description="Conversation summary")
    topics: List[str] = Field(default_factory=list, description="Conversation topics")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration time")
    total_tokens: int = Field(default=0, description="Total tokens used")
    message_count: int = Field(default=0, description="Number of messages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv_123456",
                "user_id": "user_789",
                "messages": [
                    {
                        "id": "msg_1",
                        "role": "user",
                        "content": "Hello, how are you?",
                        "timestamp": "2024-01-01T12:00:00Z",
                        "tokens": 5
                    }
                ],
                "summary": "User greeting conversation",
                "topics": ["greeting", "casual"],
                "total_tokens": 50,
                "message_count": 2
            }
        }


class UserMemory(BaseModel):
    """User-specific memory model."""
    
    user_id: str = Field(..., description="User identifier")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    context: Dict[str, Any] = Field(default_factory=dict, description="User context information")
    facts: List[str] = Field(default_factory=list, description="Known facts about user")
    conversation_history: List[str] = Field(default_factory=list, description="Recent conversation IDs")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    last_active: datetime = Field(default_factory=datetime.utcnow, description="Last activity time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_789",
                "preferences": {
                    "language": "ru",
                    "model": "llama3.2",
                    "temperature": 0.7
                },
                "context": {
                    "timezone": "UTC+3",
                    "profession": "developer"
                },
                "facts": [
                    "Предпочитает краткие ответы",
                    "Интересуется AI и машинным обучением"
                ],
                "conversation_history": ["conv_123", "conv_456"]
            }
        }


class SystemMemory(BaseModel):
    """System-wide memory model."""
    
    key: str = Field(..., description="Memory key")
    value: Union[str, int, float, bool, Dict[str, Any], List[Any]] = Field(..., description="Memory value")
    memory_type: MemoryTypeEnum = Field(..., description="Type of memory")
    priority: MemoryPriorityEnum = Field(default=MemoryPriorityEnum.MEDIUM, description="Memory priority")
    tags: List[str] = Field(default_factory=list, description="Memory tags")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration time")
    access_count: int = Field(default=0, description="Number of times accessed")
    last_accessed: Optional[datetime] = Field(default=None, description="Last access time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "key": "model_performance_stats",
                "value": {
                    "llama3.2": {"avg_response_time": 2.5, "success_rate": 0.98},
                    "llama3": {"avg_response_time": 3.1, "success_rate": 0.95}
                },
                "memory_type": "system_facts",
                "priority": "high",
                "tags": ["performance", "models"],
                "access_count": 42
            }
        }


class MemoryQuery(BaseModel):
    """Memory query model."""
    
    memory_type: Optional[MemoryTypeEnum] = Field(default=None, description="Filter by memory type")
    user_id: Optional[str] = Field(default=None, description="Filter by user ID")
    conversation_id: Optional[str] = Field(default=None, description="Filter by conversation ID")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags")
    priority: Optional[MemoryPriorityEnum] = Field(default=None, description="Filter by priority")
    limit: int = Field(default=50, ge=1, le=1000, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Results offset")
    include_expired: bool = Field(default=False, description="Include expired memories")
    
    class Config:
        json_schema_extra = {
            "example": {
                "memory_type": "conversation",
                "user_id": "user_789",
                "limit": 10,
                "offset": 0,
                "include_expired": False
            }
        }


class MemoryStats(BaseModel):
    """Memory statistics model."""
    
    total_conversations: int = Field(default=0, description="Total conversations")
    total_users: int = Field(default=0, description="Total users")
    total_system_memories: int = Field(default=0, description="Total system memories")
    memory_usage_mb: float = Field(default=0.0, description="Memory usage in MB")
    avg_conversation_length: float = Field(default=0.0, description="Average conversation length")
    most_active_users: List[Dict[str, Any]] = Field(default_factory=list, description="Most active users")
    popular_topics: List[Dict[str, Any]] = Field(default_factory=list, description="Popular conversation topics")
    model_usage_stats: Dict[str, Any] = Field(default_factory=dict, description="Model usage statistics")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_conversations": 1250,
                "total_users": 89,
                "total_system_memories": 156,
                "memory_usage_mb": 45.2,
                "avg_conversation_length": 8.5,
                "most_active_users": [
                    {"user_id": "user_123", "conversations": 45, "messages": 234}
                ],
                "popular_topics": [
                    {"topic": "programming", "count": 89},
                    {"topic": "ai", "count": 67}
                ],
                "model_usage_stats": {
                    "llama3.2": {"usage_count": 890, "avg_response_time": 2.3},
                    "llama3": {"usage_count": 234, "avg_response_time": 3.1}
                }
            }
        }


class MemoryCreateRequest(BaseModel):
    """Request to create memory."""
    
    memory_type: MemoryTypeEnum = Field(..., description="Type of memory to create")
    data: Dict[str, Any] = Field(..., description="Memory data")
    ttl_hours: Optional[int] = Field(default=None, ge=1, le=8760, description="TTL in hours (max 1 year)")
    priority: MemoryPriorityEnum = Field(default=MemoryPriorityEnum.MEDIUM, description="Memory priority")
    tags: List[str] = Field(default_factory=list, description="Memory tags")


class MemoryUpdateRequest(BaseModel):
    """Request to update memory."""
    
    data: Optional[Dict[str, Any]] = Field(default=None, description="Updated memory data")
    ttl_hours: Optional[int] = Field(default=None, ge=1, le=8760, description="Updated TTL in hours")
    priority: Optional[MemoryPriorityEnum] = Field(default=None, description="Updated priority")
    tags: Optional[List[str]] = Field(default=None, description="Updated tags")


class MemoryResponse(BaseModel):
    """Memory operation response."""
    
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Response data")
    memory_id: Optional[str] = Field(default=None, description="Memory identifier")
    expires_at: Optional[datetime] = Field(default=None, description="Memory expiration time")
