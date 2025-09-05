"""Tests for health endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_basic_health_check(client: TestClient):
    """Test basic health check endpoint."""
    response = client.get("/health/")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "service" in data
    assert "version" in data


def test_liveness_check(client: TestClient):
    """Test liveness check endpoint."""
    response = client.get("/health/live")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "alive"
    assert "timestamp" in data


def test_readiness_check(client: TestClient):
    """Test readiness check endpoint."""
    response = client.get("/health/ready")
    
    # This might fail if Ollama is not running, which is expected in tests
    assert response.status_code in [200, 503]
    
    data = response.json()
    assert "status" in data
    assert "timestamp" in data


def test_detailed_health_check(client: TestClient):
    """Test detailed health check endpoint."""
    response = client.get("/health/detailed")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert "timestamp" in data
    assert "service" in data
    assert "version" in data
    assert "components" in data
    
    # Check components structure
    components = data["components"]
    assert isinstance(components, dict)
    
    # Should have ollama and redis components
    for component in ["ollama", "redis"]:
        if component in components:
            assert "status" in components[component]
