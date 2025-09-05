"""Models management endpoints."""

import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ...services.ollama_manager import get_ollama_manager, OllamaManager
from ...models.ollama import ModelListResponse
from ...api.dependencies import check_user_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])


class PullModelRequest(BaseModel):
    """Request to pull a model."""
    name: str
    force: bool = False


@router.get("/", response_model=ModelListResponse)
async def list_models(
    force_refresh: bool = False,
    ollama_manager: OllamaManager = Depends(get_ollama_manager),
    user_id: str = Depends(check_user_rate_limit),
) -> ModelListResponse:
    """List all available models."""
    
    try:
        models_response = await ollama_manager.list_models(force_refresh=force_refresh)
        logger.info(f"User {user_id} listed {len(models_response.models)} models")
        return models_response
        
    except Exception as e:
        logger.error(f"Failed to list models for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to retrieve models: {str(e)}"
        )


@router.get("/{model_name}")
async def get_model_info(
    model_name: str,
    ollama_manager: OllamaManager = Depends(get_ollama_manager),
    user_id: str = Depends(check_user_rate_limit),
) -> Dict[str, any]:
    """Get information about a specific model."""
    
    try:
        models_response = await ollama_manager.list_models()
        
        # Find the specific model
        for model in models_response.models:
            if model.name == model_name:
                logger.info(f"User {user_id} requested info for model {model_name}")
                return {
                    "name": model.name,
                    "size": model.size,
                    "digest": model.digest,
                    "modified_at": model.modified_at,
                    "details": model.details,
                    "available": True,
                }
        
        # Model not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get model info for {model_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to retrieve model information: {str(e)}"
        )


@router.post("/pull")
async def pull_model(
    request: PullModelRequest,
    ollama_manager: OllamaManager = Depends(get_ollama_manager),
    user_id: str = Depends(check_user_rate_limit),
) -> Dict[str, str]:
    """Pull/download a model."""
    
    try:
        # Check if model already exists (unless force is True)
        if not request.force:
            is_available = await ollama_manager.is_model_available(request.name)
            if is_available:
                return {
                    "status": "already_available",
                    "model": request.name,
                    "message": f"Model '{request.name}' is already available",
                }
        
        # Pull the model
        logger.info(f"User {user_id} pulling model {request.name}")
        success = await ollama_manager.pull_model(request.name)
        
        if success:
            logger.info(f"Successfully pulled model {request.name} for user {user_id}")
            return {
                "status": "success",
                "model": request.name,
                "message": f"Model '{request.name}' pulled successfully",
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to pull model '{request.name}'"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pulling model {request.name} for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to pull model: {str(e)}"
        )


@router.get("/{model_name}/available")
async def check_model_availability(
    model_name: str,
    ollama_manager: OllamaManager = Depends(get_ollama_manager),
    user_id: str = Depends(check_user_rate_limit),
) -> Dict[str, bool]:
    """Check if a model is available."""
    
    try:
        is_available = await ollama_manager.is_model_available(model_name)
        logger.debug(f"User {user_id} checked availability of model {model_name}: {is_available}")
        
        return {
            "model": model_name,
            "available": is_available,
        }
        
    except Exception as e:
        logger.error(f"Error checking model availability for {model_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to check model availability: {str(e)}"
        )
