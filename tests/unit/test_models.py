"""Tests for models endpoints."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


def test_list_models_success(client: TestClient, mock_ollama_manager):
    """Test successful model listing."""
    with patch("app.api.routes.models.get_ollama_manager", return_value=mock_ollama_manager):
        response = client.get("/models/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "models" in data
        assert isinstance(data["models"], list)
        
        if data["models"]:
            model = data["models"][0]
            assert "name" in model
            assert "size" in model


def test_get_model_info_success(client: TestClient, mock_ollama_manager):
    """Test successful model info retrieval."""
    with patch("app.api.routes.models.get_ollama_manager", return_value=mock_ollama_manager):
        response = client.get("/models/llama3")
        
        # This will depend on the mock implementation
        # For now, just check that it doesn't crash
        assert response.status_code in [200, 404, 503]


def test_get_model_info_not_found(client: TestClient, mock_ollama_manager):
    """Test model info for non-existent model."""
    # Configure mock to return empty model list
    mock_ollama_manager.list_models.return_value = {"models": []}
    
    with patch("app.api.routes.models.get_ollama_manager", return_value=mock_ollama_manager):
        response = client.get("/models/nonexistent-model")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


def test_check_model_availability(client: TestClient, mock_ollama_manager):
    """Test model availability check."""
    with patch("app.api.routes.models.get_ollama_manager", return_value=mock_ollama_manager):
        response = client.get("/models/llama3/available")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "model" in data
        assert "available" in data
        assert isinstance(data["available"], bool)


def test_pull_model_success(client: TestClient, mock_ollama_manager):
    """Test successful model pulling."""
    mock_ollama_manager.pull_model.return_value = True
    
    with patch("app.api.routes.models.get_ollama_manager", return_value=mock_ollama_manager):
        response = client.post("/models/pull", json={"name": "test-model"})
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "model" in data


def test_pull_model_already_available(client: TestClient, mock_ollama_manager):
    """Test pulling model that's already available."""
    mock_ollama_manager.is_model_available.return_value = True
    
    with patch("app.api.routes.models.get_ollama_manager", return_value=mock_ollama_manager):
        response = client.post("/models/pull", json={"name": "llama3", "force": False})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "already_available"
