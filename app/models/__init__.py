"""Data models."""

from .chat import ChatRequest, ChatResponse, TaskStatus
from .ollama import ModelInfo, OllamaResponse

__all__ = [
    "ChatRequest",
    "ChatResponse", 
    "TaskStatus",
    "ModelInfo",
    "OllamaResponse",
]
