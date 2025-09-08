"""System prompts CRUD and activation endpoints."""

from ...utils.loguru_config import get_logger
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ...services.hybrid_memory_manager import get_hybrid_memory_manager
from ...api.dependencies import check_user_rate_limit

logger = get_logger(__name__)

router = APIRouter(prefix="/system-prompts", tags=["system-prompts"])


class SystemPromptCreateRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=255, description="Unique key for the prompt")
    content: str = Field(..., min_length=1, description="System prompt content")
    title: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)


class SystemPromptResponse(BaseModel):
    key: str
    title: Optional[str] = None
    description: Optional[str] = None
    content: str
    model: Optional[str] = None
    tags: List[str] = []
    created_by: Optional[str] = None


@router.get("/", response_model=List[Dict[str, Any]])
async def list_prompts(
    user_id: str = Depends(check_user_rate_limit),
    memory_manager = Depends(get_hybrid_memory_manager),
):
    """List all stored system prompts."""
    try:
        prompts = await memory_manager.list_system_prompts()
        return prompts
    except Exception as e:
        logger.error(f"Failed to list system prompts: {e}")
        raise HTTPException(status_code=500, detail="Failed to list system prompts")


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_prompt(
    request: SystemPromptCreateRequest,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager = Depends(get_hybrid_memory_manager),
):
    """Create or update a system prompt."""
    try:
        success = await memory_manager.save_system_prompt(
            key=request.key,
            content=request.content,
            title=request.title,
            description=request.description,
            model=request.model,
            created_by=user_id,
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save system prompt")
        return {"success": True, "key": request.key}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create system prompt: {e}")
        raise HTTPException(status_code=500, detail="Failed to create system prompt")


@router.get("/active")
async def get_active_prompt(
    user_id: str = Depends(check_user_rate_limit),
    memory_manager = Depends(get_hybrid_memory_manager),
):
    """Get the currently active system prompt."""
    try:
        active = await memory_manager.get_active_system_prompt()
        return {"active": active}
    except Exception as e:
        logger.error(f"Failed to get active system prompt: {e}")
        raise HTTPException(status_code=500, detail="Failed to get active system prompt")


@router.put("/{key}/activate")
async def activate_prompt(
    key: str,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager = Depends(get_hybrid_memory_manager),
):
    """Mark a system prompt as active by key."""
    try:
        success = await memory_manager.set_active_system_prompt(key)
        if not success:
            raise HTTPException(status_code=404, detail="Prompt not found")
        return {"success": True, "key": key}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate system prompt {key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to activate system prompt")


@router.get("/{key}")
async def get_prompt(
    key: str,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager = Depends(get_hybrid_memory_manager),
):
    """Get specific system prompt by key."""
    try:
        prompt = await memory_manager.get_system_memory(key)
        if prompt is None:
            raise HTTPException(status_code=404, detail="Prompt not found")
        return {"key": key, "value": prompt}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get system prompt {key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system prompt")


@router.delete("/{key}")
async def delete_prompt(
    key: str,
    user_id: str = Depends(check_user_rate_limit),
    memory_manager = Depends(get_hybrid_memory_manager),
):
    """Delete a system prompt by key."""
    try:
        success = await memory_manager.delete_system_prompt(key)
        if not success:
            raise HTTPException(status_code=404, detail="Prompt not found")
        # If the deleted prompt was active, unset active pointer
        active = await memory_manager.get_active_system_prompt()
        if active and active.get("key") == key:
            await memory_manager.set_system_memory(key='system_prompt_active', value=None, memory_type='preferences')
        return {"success": True, "key": key}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete system prompt {key}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete system prompt")


