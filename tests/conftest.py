"""Pytest configuration and fixtures."""

import asyncio
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from app.main import app
from app.services.ollama_manager import OllamaManager
from app.services.rate_limiter import RateLimiter


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_ollama_manager():
    """Mock Ollama manager."""
    manager = MagicMock(spec=OllamaManager)
    
    # Mock health check
    manager.health_check = AsyncMock(return_value=True)
    
    # Mock list models
    manager.list_models = AsyncMock(return_value={
        "models": [
            {
                "name": "llama3:latest",
                "size": "4.7GB",
                "digest": "sha256:test123",
                "modified_at": "2024-01-01T00:00:00Z"
            }
        ]
    })
    
    # Mock is_model_available
    manager.is_model_available = AsyncMock(return_value=True)
    
    # Mock generate
    manager.generate = AsyncMock(return_value={
        "model": "llama3",
        "response": "Test response",
        "done": True,
        "total_duration": 1000000000,
        "eval_count": 10
    })
    
    return manager


@pytest.fixture
def mock_rate_limiter():
    """Mock rate limiter."""
    limiter = MagicMock(spec=RateLimiter)
    
    # Mock check methods
    limiter.check_rate_limit = AsyncMock(return_value=True)
    limiter.check_user_rate_limit = AsyncMock(return_value=True)
    limiter.check_global_rate_limit = AsyncMock(return_value=True)
    
    # Mock status method
    limiter.get_rate_limit_status = AsyncMock(return_value={
        "limit": 100,
        "remaining": 95,
        "reset_time": 1640995200,
        "window_seconds": 60
    })
    
    return limiter


@pytest.fixture
def sample_chat_request():
    """Sample chat request data."""
    return {
        "prompt": "Test prompt",
        "model": "llama3",
        "temperature": 0.7,
        "max_tokens": 100
    }


@pytest.fixture
def sample_chat_response():
    """Sample chat response data."""
    return {
        "response": "Test response",
        "conversation_id": "test-conv-123",
        "model": "llama3",
        "processing_time": 1.5,
        "tokens_used": 10,
        "created_at": "2024-01-01T00:00:00Z"
    }
