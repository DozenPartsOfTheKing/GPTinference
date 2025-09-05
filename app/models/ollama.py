"""Ollama-related data models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    """Ollama model information."""
    
    name: str = Field(..., description="Model name")
    size: str = Field(..., description="Model size")
    digest: str = Field(..., description="Model digest/hash")
    modified_at: datetime = Field(..., description="Last modification time")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional model details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "llama3:latest",
                "size": "4.7GB",
                "digest": "sha256:abc123...",
                "modified_at": "2024-01-01T12:00:00Z"
            }
        }


class OllamaGenerateOptions(BaseModel):
    """Ollama generation options."""
    
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=0.9, ge=0.0, le=1.0)
    top_k: Optional[int] = Field(default=40, ge=1, le=100)
    repeat_penalty: Optional[float] = Field(default=1.1, ge=0.0, le=2.0)
    seed: Optional[int] = Field(default=None)
    num_ctx: Optional[int] = Field(default=2048, ge=1, le=8192)
    num_predict: Optional[int] = Field(default=-1)
    stop: Optional[List[str]] = Field(default=None)


class OllamaRequest(BaseModel):
    """Ollama API request."""
    
    model: str = Field(..., description="Model name")
    prompt: str = Field(..., description="Input prompt")
    stream: bool = Field(default=False, description="Enable streaming")
    options: Optional[OllamaGenerateOptions] = Field(default=None, description="Generation options")
    context: Optional[List[int]] = Field(default=None, description="Conversation context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "model": "llama3",
                "prompt": "Explain quantum computing",
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9
                }
            }
        }


class OllamaResponse(BaseModel):
    """Ollama API response."""
    
    model: str = Field(..., description="Model used")
    response: str = Field(..., description="Generated response")
    done: bool = Field(..., description="Whether generation is complete")
    context: Optional[List[int]] = Field(default=None, description="Updated context")
    total_duration: Optional[int] = Field(default=None, description="Total duration in nanoseconds")
    load_duration: Optional[int] = Field(default=None, description="Model load duration")
    prompt_eval_count: Optional[int] = Field(default=None, description="Prompt evaluation token count")
    prompt_eval_duration: Optional[int] = Field(default=None, description="Prompt evaluation duration")
    eval_count: Optional[int] = Field(default=None, description="Response token count")
    eval_duration: Optional[int] = Field(default=None, description="Response generation duration")
    
    @property
    def processing_time_seconds(self) -> Optional[float]:
        """Get processing time in seconds."""
        if self.total_duration:
            return self.total_duration / 1_000_000_000
        return None
    
    @property
    def tokens_per_second(self) -> Optional[float]:
        """Calculate tokens per second."""
        if self.eval_count and self.eval_duration:
            return self.eval_count / (self.eval_duration / 1_000_000_000)
        return None
    
    class Config:
        json_schema_extra = {
            "example": {
                "model": "llama3",
                "response": "Quantum computing is a revolutionary technology...",
                "done": True,
                "total_duration": 2500000000,
                "eval_count": 150,
                "eval_duration": 2000000000
            }
        }


class ModelListResponse(BaseModel):
    """Response for model list endpoint."""
    
    models: List[ModelInfo] = Field(..., description="Available models")
    
    class Config:
        json_schema_extra = {
            "example": {
                "models": [
                    {
                        "name": "llama3:latest",
                        "size": "4.7GB",
                        "digest": "sha256:abc123...",
                        "modified_at": "2024-01-01T12:00:00Z"
                    }
                ]
            }
        }
