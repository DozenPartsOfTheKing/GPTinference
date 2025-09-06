"""Chat-related data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class TaskStatusEnum(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"


class ChatRequest(BaseModel):
    """Chat request model."""
    
    prompt: str = Field(..., min_length=1, max_length=10000, description="User prompt")
    model: str = Field(default="llama3.2", description="Model to use for generation")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID for context")
    max_tokens: Optional[int] = Field(default=1000, ge=1, le=4000, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: Optional[float] = Field(default=0.9, ge=0.0, le=1.0, description="Top-p sampling")
    stream: bool = Field(default=False, description="Enable streaming response")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Explain quantum computing in simple terms",
                "model": "llama3",
                "max_tokens": 500,
                "temperature": 0.7
            }
        }


class ChatResponse(BaseModel):
    """Chat response model."""
    
    response: str = Field(..., description="Generated response")
    conversation_id: str = Field(..., description="Conversation ID")
    model: str = Field(..., description="Model used for generation")
    processing_time: float = Field(..., description="Processing time in seconds")
    tokens_used: Optional[int] = Field(default=None, description="Number of tokens used")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Response creation time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "response": "Quantum computing is a revolutionary technology...",
                "conversation_id": "conv_123456",
                "model": "llama3",
                "processing_time": 2.5,
                "tokens_used": 150,
                "created_at": "2024-01-01T12:00:00Z"
            }
        }


class TaskStatus(BaseModel):
    """Task status model."""
    
    task_id: str = Field(..., description="Task identifier")
    status: TaskStatusEnum = Field(..., description="Current task status")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Task result if completed")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    progress: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Task progress percentage")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Task creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_123456",
                "status": "processing",
                "progress": 75.0,
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:01:30Z"
            }
        }


class ChatTaskRequest(BaseModel):
    """Internal task request model."""
    
    task_id: str = Field(..., description="Task identifier")
    user_id: Optional[str] = Field(default=None, description="User identifier")
    chat_request: ChatRequest = Field(..., description="Original chat request")
    priority: int = Field(default=5, ge=1, le=10, description="Task priority (1=highest, 10=lowest)")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_123456",
                "user_id": "user_789",
                "priority": 5,
                "retry_count": 0
            }
        }
